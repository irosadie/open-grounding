from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class SuccessEnvelope(BaseModel):
    success: bool = True
    message: str
    data: Any | None = None
    meta: Any | None = None


# --- RAG ingestion schemas ---------------------------------------------------


class CreateIntakeRequest(BaseModel):
    knowledge_base_id: str = Field(min_length=1, max_length=120)
    filename: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=1)
    source_revision: str | None = Field(default=None, max_length=512)
    title: str | None = Field(default=None, max_length=512)


class IntakeResponse(BaseModel):
    document_id: str
    document_version_id: str
    upload_key: str
    upload_url: str | None = None
    expires_in: int = 3600


class CompleteIntakeRequest(BaseModel):
    document_version_id: str = Field(min_length=1, max_length=120)
    content_checksum: str = Field(min_length=1, max_length=128)


class IngestionStatusResponse(BaseModel):
    document_id: str
    document_version_id: str
    lifecycle_state: str
    stage: str | None = None
    attempts: int = 0
    quality: dict[str, Any] | None = None


class DecompositionOverride(BaseModel):
    enabled: bool | None = Field(default=None, description="Override KB decomposition config for this request")
    max_sub_queries: int | None = Field(default=None, ge=1, le=5, description="Override max sub-queries for this request")


class MemoryOverride(BaseModel):
    enabled: bool | None = Field(default=None, description="Override memory retrieval for this request")


class RagQueryRequest(BaseModel):
    conversation_id: str | None = Field(default=None, max_length=120, description="Optional server-owned conversation identifier")
    message: str = Field(min_length=1, max_length=8_000, description="Question to answer from permitted evidence")
    knowledge_base_ids: list[str] = Field(min_length=1, max_length=20, description="Knowledge bases the caller may select")
    mode: str = Field(default="grounded", pattern="^(grounded)$", description="Only grounded mode is supported")
    stream: bool = Field(default=False, description="Request an SSE response when enabled")
    decomposition: DecompositionOverride | None = Field(default=None, description="Optional per-request decomposition override")
    memory: MemoryOverride | None = Field(default=None, description="Optional per-request memory override")

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {"examples": [{"message": "What is the retention policy?", "knowledge_base_ids": ["knowledge-base-id"], "stream": False}]},
    }


class RagQueryStreamRequest(RagQueryRequest):
    stream: Literal[True] = Field(default=True, description="SSE requests always stream")


class RagQueryCitationResponse(BaseModel):
    citation_id: str
    document_version_id: str
    title: str
    locator: str | None = None
    snippet: str


class RagQueryResponse(BaseModel):
    answer: dict[str, object] | None = None
    route: Literal["grounded", "clarify", "abstain"]
    evidence_level: Literal["high", "medium", "low", "none"]
    citations: list[RagQueryCitationResponse]
    limitations: list[str]
    trace_id: str

    model_config = {"populate_by_name": True}


class RagAnswerFeedbackRequest(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5, description="Optional 1-5 rating for the retained answer")
    comment: str | None = Field(default=None, max_length=2_000, description="Optional bounded feedback comment")

    model_config = {
        "extra": "forbid",
    }


# --- Knowledge base schemas --------------------------------------------------

class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    model_config = {"extra": "forbid"}


class KnowledgeBaseResponse(BaseModel):
    id: str
    tenant_id: str
    slug: str
    name: str
    status: str
    created_at: str
    updated_at: str

    model_config = {"populate_by_name": True}


# --- Model profile schemas --------------------------------------------------

class CreateModelProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    profile_kind: str = Field(pattern=r"^(DENSE_EMBEDDING|SPARSE_EMBEDDING|RERANKER|GENERATION)$")
    provider: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=255)
    modality: str = Field(default="TEXT", pattern=r"^(TEXT|IMAGE|MULTIMODAL)$")
    dimensions: int | None = Field(default=None, ge=1)
    config_json: str | None = Field(default=None)

    model_config = {"extra": "forbid"}


# --- Index profile schemas --------------------------------------------------

class CreateIndexProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    embedding_profile_id: str = Field(min_length=1)
    sparse_profile_id: str | None = Field(default=None)
    reranker_profile_id: str | None = Field(default=None)
    collection: str = Field(min_length=1, max_length=255)
    dimensions: int = Field(ge=1)
    distance_metric: str = Field(default="cosine", pattern=r"^(cosine|dot|euclid)$")
    chunking_strategy: str = Field(default="RECURSIVE", pattern=r"^(RECURSIVE|SENTENCE|FIXED|PARAGRAPH)$")
    chunk_size_tokens: int = Field(default=400, ge=50, le=2000)
    chunk_overlap_tokens: int = Field(default=50, ge=0, le=500)
    parent_chunk_size: int = Field(default=1500, ge=100, le=5000)

    model_config = {"extra": "forbid"}


# --- Provider credential schemas --------------------------------------------

class SetProviderCredentialRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=60)
    key_name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=4096, description="Credential value — never returned in responses")

    model_config = {"extra": "forbid"}


# --- Decomposition config schemas -------------------------------------------

class CreateDecompositionConfigRequest(BaseModel):
    enabled: bool = Field(default=True)
    model_profile_id: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=1)
    user_prompt_template: str = Field(min_length=1)
    max_sub_queries: int = Field(default=3, ge=1, le=5)
    max_depth: int = Field(default=2, ge=1, le=3)
    min_complexity_score: float = Field(default=0.6, ge=0.0, le=1.0)
    guardrails: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class DecompositionConfigResponse(BaseModel):
    id: str
    knowledge_base_id: str
    enabled: bool
    model_profile_id: str
    system_prompt: str
    user_prompt_template: str
    max_sub_queries: int
    max_depth: int
    min_complexity_score: float
    guardrails: dict[str, Any]
    created_at: str
    updated_at: str


# --- Memory config schemas ---------------------------------------------------

class CreateMemoryConfigRequest(BaseModel):
    enabled: bool = Field(default=False)
    summarization_model_profile_id: str = Field(min_length=1, max_length=120)
    embedding_profile_id: str = Field(min_length=1, max_length=120)
    retention_days: int = Field(default=90, ge=1, le=365)
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    min_turns_to_summarize: int = Field(default=3, ge=1, le=20)
    system_prompt: str = Field(min_length=1)

    model_config = {"extra": "forbid"}


class MemoryConfigResponse(BaseModel):
    id: str
    knowledge_base_id: str
    enabled: bool
    summarization_model_profile_id: str
    embedding_profile_id: str
    retention_days: int
    retrieval_top_k: int
    min_turns_to_summarize: int
    system_prompt: str
    created_at: str
    updated_at: str


class MemoryChunkResponse(BaseModel):
    id: str
    knowledge_base_id: str
    user_id: str
    conversation_id: str | None
    summary: str
    turn_count: int
    expires_at: str
    created_at: str


class MemoryChunkListResponse(BaseModel):
    items: list[MemoryChunkResponse]
    total: int
    page: int
    page_size: int
