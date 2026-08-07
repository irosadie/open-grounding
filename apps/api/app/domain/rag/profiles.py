"""Immutable, versioned RAG model and index profile value objects.

These domain value objects describe provider-neutral configuration for the
embedding, sparse-encoder, reranker, and generation ports. They carry only
non-secret metadata; provider credentials remain in runtime configuration or
a secret provider and are never stored in a profile or returned by
diagnostics.

Profiles are immutable and versioned. Changing an embedding dimension,
distance metric, sparse profile, or provider reference creates a new profile
identity rather than mutating an active one, so derived index generations
never mix incompatible vector dimensions or models.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalConfig:
    """Per-index-profile retrieval and RRF configuration."""

    index_profile_id: str
    dense_weight: float = 1.0
    sparse_weight: float = 1.0
    fusion_k: int = 60
    dense_candidates: int = 50
    sparse_candidates: int = 50
    fused_candidates: int = 40
    enabled: bool = True

    @classmethod
    def defaults(cls, index_profile_id: str) -> "RetrievalConfig":
        return cls(index_profile_id=index_profile_id)


class DistanceMetric:
    COSINE = "cosine"
    DOT = "dot"
    EUCLID = "euclid"


@dataclass(frozen=True)
class ModelProfile:
    """Immutable metadata for an embedding, sparse, reranker, or generation model."""

    id: str
    tenant_id: str
    name: str
    profile_kind: str
    provider: str
    model: str
    modality: str
    dimensions: int | None
    config_json: str | None
    version: str
    is_active: bool = False
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class IndexProfile:
    """Immutable metadata for a vector index collection configuration."""

    id: str
    tenant_id: str
    name: str
    embedding_profile_id: str
    sparse_profile_id: str | None
    reranker_profile_id: str | None
    collection: str
    dimensions: int
    distance_metric: str
    chunking_strategy: str
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    parent_chunk_size: int
    version: str
    is_active: bool = False
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class ProfileCompatibility:
    """Result of validating an index profile against its embedding profile.

    The foundation validates profile compatibility without making a model
    inference call. Incompatible dimensions, distance metrics, or missing
    sparse references are rejected before any derived index is published.
    """

    is_compatible: bool
    reason: str | None = None

    @classmethod
    def ok(cls) -> "ProfileCompatibility":
        return cls(is_compatible=True)

    @classmethod
    def incompatible(cls, reason: str) -> "ProfileCompatibility":
        return cls(is_compatible=False, reason=reason)


def validate_index_profile_compatibility(
    *,
    index: IndexProfile,
    embedding: ModelProfile,
) -> ProfileCompatibility:
    """Validate that an index profile is compatible with its embedding profile.

    Checks that the referenced embedding profile declares the same vector
    dimensions as the index profile. Does not make any model inference call.
    """
    if embedding.dimensions is None:
        return ProfileCompatibility.incompatible("Embedding profile does not declare vector dimensions")
    if index.embedding_profile_id != embedding.id:
        return ProfileCompatibility.incompatible("Index profile does not reference the supplied embedding profile")
    if index.dimensions != embedding.dimensions:
        return ProfileCompatibility.incompatible(f"Index dimensions {index.dimensions} do not match embedding dimensions {embedding.dimensions}")
    return ProfileCompatibility.ok()
