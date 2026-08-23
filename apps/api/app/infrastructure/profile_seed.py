"""Default model and index profile seeding for development.

Seeds a FastEmbed dense embedding profile and a default index profile
if none exist for the deployment tenant. Safe to call multiple times —
idempotent via existence check.

Default profiles:
- Dense: BAAI/bge-small-en-v1.5 (FastEmbed, 384 dims, TEXT)
- Index: open-grounding-default (RECURSIVE chunking, COSINE, collection=rag)
"""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.infrastructure.rag_catalog import (
    IndexProfileRecord,
    ModelProfileRecord,
    SqlAlchemyIndexGenerationRepository,
)
from app.infrastructure.database import utc_now
from sqlalchemy import select


async def seed_default_profiles(session: AsyncSession, settings: Settings) -> None:
    """Seed default FastEmbed model and index profiles if none exist."""
    tenant_id = settings.deployment_tenant_id
    if tenant_id is None:
        return

    # Check if any model profile exists for this tenant
    result = await session.execute(
        select(ModelProfileRecord).where(
            ModelProfileRecord.tenant_id == tenant_id,
        ).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return  # Already seeded

    # Create default dense embedding profile
    dense_id = str(uuid4())
    dense = ModelProfileRecord(
        id=dense_id,
        tenant_id=tenant_id,
        name="FastEmbed BGE Small EN",
        profile_kind="DENSE_EMBEDDING",
        provider="fastembed",
        model="BAAI/bge-small-en-v1.5",
        modality="TEXT",
        dimensions=384,
        config_json=None,
        version="v1",
        is_active=True,
    )
    session.add(dense)

    # Create default sparse embedding profile
    sparse_id = str(uuid4())
    sparse = ModelProfileRecord(
        id=sparse_id,
        tenant_id=tenant_id,
        name="FastEmbed SPLADE",
        profile_kind="SPARSE_EMBEDDING",
        provider="fastembed",
        model="prithivida/Splade_PP_COO_1",
        modality="TEXT",
        dimensions=None,
        config_json=None,
        version="v1",
        is_active=True,
    )
    session.add(sparse)
    await session.flush()  # ensure FK refs are persisted before index profile insert

    # Create default index profile
    index_id = str(uuid4())
    index_profile = IndexProfileRecord(
        id=index_id,
        tenant_id=tenant_id,
        name="Default (FastEmbed BGE + SPLADE)",
        embedding_profile_id=dense_id,
        sparse_profile_id=sparse_id,
        reranker_profile_id=None,
        collection="rag",
        dimensions=384,
        distance_metric="cosine",
        chunking_strategy="RECURSIVE",
        chunk_size_tokens=400,
        chunk_overlap_tokens=50,
        parent_chunk_size=1500,
        version="v1",
        is_active=True,
    )
    session.add(index_profile)
    await session.commit()
