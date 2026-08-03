from typing import Any

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

