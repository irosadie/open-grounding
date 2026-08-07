from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


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


class CreateMcpServerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    transport: Literal["stdio", "http", "sse"]
    command: str | None = Field(default=None, max_length=1024)
    args: list[str] = Field(default_factory=list, max_length=64)
    url: str | None = Field(default=None, max_length=2048)
    auth_type: Literal["none", "bearer", "header"] = "none"
    credential: str | None = Field(default=None, max_length=4096)
    credential_header: str | None = Field(default=None, max_length=120)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_payload_bytes: int = Field(default=1_048_576, ge=65_536, le=10_485_760)
    allow_insecure: bool = False
    enabled: bool = True

    model_config = {"extra": "forbid"}


class McpServerResponse(BaseModel):
    id: str
    name: str
    transport: str
    command: str | None
    args: list[str]
    url: str | None
    authType: str | None
    hasCredential: bool
    headers: dict[str, str]
    timeoutSeconds: int
    maxPayloadBytes: int
    allowInsecure: bool
    enabled: bool
    status: str
    lastError: str | None
    createdAt: str
    updatedAt: str


class McpToolResponse(BaseModel):
    id: str
    serverId: str
    name: str
    description: str
    inputSchema: dict[str, object]
    allowed: bool
    isStale: bool
    lastDiscoveredAt: str


class McpInvocationResponse(BaseModel):
    id: str
    serverId: str
    toolId: str
    userId: str
    argsHash: str
    status: str
    resultText: str | None
    durationMs: int
    createdAt: str


class InvokeToolRequest(BaseModel):
    arguments: dict[str, object] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class UpdateMcpToolRequest(BaseModel):
    allowed: bool

    model_config = {"extra": "forbid"}


# --- RAG ingestion schemas ---------------------------------------------------


class CreateIntakeRequest(BaseModel):
    knowledge_base_id: str = Field(min_length=1, max_length=120)
    filename: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=1)
    source_revision: str | None = Field(default=None, max_length=512)
    title: str | None = Field(default=None, max_length=512)
    metadata: dict[str, str] | None = Field(default=None)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return v
        if len(v) > 20:
            raise ValueError("metadata cannot have more than 20 keys")
        for key, value in v.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("metadata keys and values must be strings")
            if len(key) > 256:
                raise ValueError(f"metadata key '{key[:32]}...' exceeds 256 characters")
            if len(value) > 256:
                raise ValueError(f"metadata value for key '{key}' exceeds 256 characters")
        return v


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


class ParsedTextResponse(BaseModel):
    version_id: str
    parsed_text: str | None
    lifecycle_state: str


class UpdateParsedTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000_000)

    model_config = {"extra": "forbid"}


class DecompositionOverride(BaseModel):
    enabled: bool | None = Field(default=None, description="Override KB decomposition config for this request")
    max_sub_queries: int | None = Field(default=None, ge=1, le=5, description="Override max sub-queries for this request")


class PlannerOverride(BaseModel):
    enabled: bool | None = Field(default=None, description="Override KB planner config for this request")
    max_tasks: int | None = Field(default=None, ge=1, le=8, description="Override maximum planned tasks")
    task_types: list[str] | None = Field(default=None, min_length=1, description="Allowed planner task types")

    model_config = {"extra": "forbid"}


class MemoryOverride(BaseModel):
    enabled: bool | None = Field(default=None, description="Override memory retrieval for this request")


class RagQueryRequest(BaseModel):
    conversation_id: str | None = Field(default=None, max_length=120, description="Optional server-owned conversation identifier")
    message: str = Field(min_length=1, max_length=8_000, description="Question to answer from permitted evidence")
    knowledge_base_ids: list[str] = Field(min_length=1, max_length=20, description="Knowledge bases the caller may select")
    mode: str = Field(default="grounded", pattern="^(grounded)$", description="Only grounded mode is supported")
    stream: bool = Field(default=False, description="Request an SSE response when enabled")
    decomposition: DecompositionOverride | None = Field(default=None, description="Optional per-request decomposition override")
    planner: PlannerOverride | None = Field(default=None, description="Optional per-request planner override")
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


class RetrievalConfigRequest(BaseModel):
    dense_weight: float = Field(default=1.0, ge=0.0, le=5.0)
    sparse_weight: float = Field(default=1.0, ge=0.0, le=5.0)
    fusion_k: int = Field(default=60, ge=1, le=200)
    dense_candidates: int = Field(default=50, ge=1, le=200)
    sparse_candidates: int = Field(default=50, ge=1, le=200)
    fused_candidates: int = Field(default=40, ge=1, le=200)
    enabled: bool = True

    model_config = {"extra": "forbid"}


class RetrievalConfigResponse(BaseModel):
    index_profile_id: str = Field(alias="indexProfileId")
    dense_weight: float = Field(alias="denseWeight")
    sparse_weight: float = Field(alias="sparseWeight")
    fusion_k: int = Field(alias="fusionK")
    dense_candidates: int = Field(alias="denseCandidates")
    sparse_candidates: int = Field(alias="sparseCandidates")
    fused_candidates: int = Field(alias="fusedCandidates")
    enabled: bool

    model_config = {"populate_by_name": True}


# --- Numeric confidence schemas ---------------------------------------------


class ConfidenceConfigResponse(BaseModel):
    retrieval_profile_id: str = Field(alias="retrievalProfileId")
    feature_weights: dict[str, float] | None = Field(alias="featureWeights")
    abstention_threshold: float = Field(alias="abstentionThreshold")
    emit_numeric_score: bool = Field(alias="emitNumericScore")
    min_labeled_entries: int = Field(alias="minLabeledEntries")
    active_model_id: str | None = Field(alias="activeModelId")
    updated_at: str | None = Field(alias="updatedAt")
    warning: str | None = None

    model_config = {"populate_by_name": True}


class ConfidenceConfigUpdateRequest(BaseModel):
    feature_weights: dict[str, float] | None = None
    abstention_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    emit_numeric_score: bool | None = None
    min_labeled_entries: int | None = Field(default=None, ge=1, le=100_000)

    model_config = {"extra": "forbid"}

    @field_validator("feature_weights")
    @classmethod
    def validate_feature_weights(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        if value is not None and any(weight < 0 for weight in value.values()):
            raise ValueError("Feature weights must be non-negative.")
        return value


class CalibrationFixtureResponse(BaseModel):
    id: str
    retrieval_profile_id: str = Field(alias="retrievalProfileId")
    version: str
    source: str
    entry_count: int = Field(alias="entryCount")
    is_active: bool = Field(alias="isActive")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


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


class CreatePlannerConfigRequest(BaseModel):
    enabled: bool = True
    model_profile_id: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=1)
    user_prompt_template: str = Field(min_length=1)
    max_tasks: int = Field(default=4, ge=1, le=8)
    task_timeout_seconds: int = Field(default=15, ge=1, le=60)
    task_types: list[str] = Field(default_factory=lambda: ["RAG", "MCP", "GENERAL"], min_length=1)
    mcp_enabled: bool = False
    guardrails: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class PlannerConfigResponse(BaseModel):
    id: str
    knowledge_base_id: str
    enabled: bool
    model_profile_id: str
    system_prompt: str
    user_prompt_template: str
    max_tasks: int
    task_timeout_seconds: int
    task_types: list[str]
    mcp_enabled: bool
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


# --- Additional confidence DTOs --------------------------------------------


class FixtureEntryResponse(BaseModel):
    id: str
    fixture_id: str = Field(alias="fixtureId")
    answer_run_id: str | None = Field(alias="answerRunId")
    query: str
    answer: str
    confidence_label: str = Field(alias="confidenceLabel")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class UnlabeledAnswerRunResponse(BaseModel):
    answer_run_id: str = Field(alias="answerRunId")
    query_preview: str = Field(alias="queryPreview")
    answer_preview: str = Field(alias="answerPreview")

    model_config = {"populate_by_name": True}


class LabelRequest(BaseModel):
    answer_run_id: str
    label: str

    model_config = {"extra": "forbid"}

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        allowed = {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "ABSTAIN"}
        if value not in allowed:
            raise ValueError(f"label must be one of {sorted(allowed)}")
        return value


class BulkLabelRequest(BaseModel):
    labels: dict[str, str]

    model_config = {"extra": "forbid"}

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "ABSTAIN"}
        bad = [lbl for lbl in value.values() if lbl not in allowed]
        if bad:
            raise ValueError(f"Invalid labels: {bad}")
        return value


class CalibrateRequest(BaseModel):
    fixture_id: str

    model_config = {"extra": "forbid"}


class CalibrateResponse(BaseModel):
    job_id: str = Field(alias="jobId")

    model_config = {"populate_by_name": True}


class CalibrationStatusResponse(BaseModel):
    job_id: str = Field(alias="jobId")
    status: str
    model_version_id: str | None = Field(alias="modelVersionId")
    pr_curve_svg: str | None = Field(alias="prCurveSvg")
    f1_optimal_threshold: float | None = Field(alias="f1OptimalThreshold")

    model_config = {"populate_by_name": True}


class ThresholdEvalResponse(BaseModel):
    threshold: float
    precision: float
    recall: float
    f1: float


class PromoteRequest(BaseModel):
    promoted_by: str | None = None

    model_config = {"extra": "forbid"}


class GenerateSyntheticRequest(BaseModel):
    knowledge_base_id: str
    count: int = Field(default=50, ge=1, le=500)

    model_config = {"extra": "forbid"}


# --- Async RAG query schemas -------------------------------------------------


class AsyncRagQueryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8192)
    knowledge_base_ids: list[str] = Field(min_length=1, max_length=20)
    conversation_id: str | None = None
    webhook_url: str | None = Field(default=None, max_length=2048)
    mode: Literal["grounded"] = "grounded"
    decomposition: dict[str, Any] | None = None
    planner: dict[str, Any] | None = None
    memory: dict[str, Any] | None = None

    @field_validator("webhook_url")
    @classmethod
    def webhook_must_be_https(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("https://"):
            raise ValueError("webhook_url must use https://")
        return v


class AsyncRagQueryResponse(BaseModel):
    jobId: str
    conversationId: str


class RagQueryJobResponse(BaseModel):
    jobId: str
    status: str
    result: dict[str, Any] | None
    error: str | None
    createdAt: str
    completedAt: str | None
