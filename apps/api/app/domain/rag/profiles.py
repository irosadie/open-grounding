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


class DistanceMetric:
    COSINE = "cosine"
    DOT = "dot"
    EUCLID = "euclid"


@dataclass(frozen=True)
class ModelProfile:
    """Immutable metadata for an embedding, sparse, reranker, or generation model.

    Stores the provider reference, model identifier, and capability metadata
    without secrets. Used to validate provider compatibility before any model
    inference call is made.
    """

    id: str
    profile_kind: str
    provider: str
    model: str
    dimensions: int | None
    version: str
    is_active: bool = False


@dataclass(frozen=True)
class IndexProfile:
    """Immutable metadata for a vector index collection configuration.

    References a compatible embedding model profile, declares vector
    dimensions, distance metric, sparse profile reference, and the Qdrant
    collection identity. An active index generation MUST reference a
    compatible immutable index profile.
    """

    id: str
    embedding_profile_id: str
    sparse_profile_id: str | None
    collection: str
    dimensions: int
    distance_metric: str
    version: str
    is_active: bool = False


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
