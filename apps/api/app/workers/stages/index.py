"""Index stage — upsert chunk vectors to Qdrant."""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.infrastructure.rag_catalog import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyIndexGenerationRepository,
    SqlAlchemyIndexProfileRepository,
)
from app.workers.stages.parse import _chunks_cache, _vectors_cache

logger = logging.getLogger(__name__)


async def index_chunks(
    document_version_id: str,
    tenant_id: str,
    session: AsyncSession,
    settings: Settings,
) -> int:
    """Upsert chunk vectors to Qdrant collection. Returns number of vectors upserted."""
    repo = SqlAlchemyDocumentVersionRepository(session)
    index_repo = SqlAlchemyIndexProfileRepository(session)
    generation_repo = SqlAlchemyIndexGenerationRepository(session)
    document_repo = SqlAlchemyDocumentRepository(session)

    await repo.update_lifecycle_state(
        tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="INDEXING"
    )

    chunks = _chunks_cache.get(document_version_id)
    vectors = _vectors_cache.get(document_version_id)

    if not chunks or not vectors:
        raise ValueError(f"No chunks/vectors found for {document_version_id}. Prior stages must run first.")

    if len(chunks) != len(vectors):
        raise ValueError(f"Chunks ({len(chunks)}) and vectors ({len(vectors)}) count mismatch.")

    index_profile = await index_repo.find_active(tenant_id=tenant_id)
    if index_profile is None:
        raise ValueError("No active index profile found.")

    version = await repo.find_by_id(tenant_id=tenant_id, version_id=document_version_id)
    if version is None:
        raise ValueError(f"Document version {document_version_id} not found.")

    # Resolve knowledge base id from the document record (needed for retrieval policy filter)
    document = await document_repo.find_by_id(tenant_id=tenant_id, document_id=version.document_id)
    if document is None:
        raise ValueError(f"Document {version.document_id} not found.")
    knowledge_base_id = document.knowledge_base_id

    # Create ACTIVE index generation FIRST so its id can be stamped on every point payload.
    generation = await generation_repo.create(
        tenant_id=tenant_id,
        document_version_id=document_version_id,
        index_profile_id=index_profile.id,
        status="ACTIVE",
    )
    generation_id = generation.id

    qdrant_url = getattr(settings, "qdrant_url", None) or "http://127.0.0.1:6334"
    qdrant_api_key = getattr(settings, "qdrant_api_key", None)

    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    client = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    # Ensure collection exists
    distance_map = {"cosine": Distance.COSINE, "dot": Distance.DOT, "euclid": Distance.EUCLID}
    distance = distance_map.get(index_profile.distance_metric, Distance.COSINE)

    collections = await client.get_collections()
    existing = [c.name for c in collections.collections]
    if index_profile.collection not in existing:
        await client.create_collection(
            collection_name=index_profile.collection,
            vectors_config=VectorParams(size=index_profile.dimensions, distance=distance),
        )
        logger.info("[index] created Qdrant collection: %s", index_profile.collection)

    # Build points with the full policy-filterable payload
    classification = version.classification.value if hasattr(version.classification, "value") else str(version.classification)
    acl_principals = list(version.acl_principals or ())
    effective_from = version.effective_from.isoformat() if version.effective_from else None
    effective_to = version.effective_to.isoformat() if version.effective_to else None

    points = []
    for i, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
        chunk_id = str(uuid4())
        payload: dict[str, object] = {
            "tenant_id": tenant_id,
            "knowledge_base_id": knowledge_base_id,
            "document_version_id": document_version_id,
            "generation_id": generation_id,
            "chunk_id": chunk_id,
            "chunk_index": i,
            "text": chunk_text,
            "classification": classification,
            "acl_principals": acl_principals,
            "is_active": True,
        }
        if effective_from is not None:
            payload["effective_from"] = effective_from
        if effective_to is not None:
            payload["effective_to"] = effective_to
        points.append(
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload=payload,
            )
        )

    # Upsert in batches
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        await client.upsert(collection_name=index_profile.collection, points=batch)

    await client.close()
    logger.info("[index] upserted %d vectors to collection %s (generation=%s)", len(points), index_profile.collection, generation_id)

    return len(points)
