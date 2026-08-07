from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class RagQueryJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class RagQueryJob:
    id: str
    tenant_id: str
    user_id: str
    status: RagQueryJobStatus
    request: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    webhook_url: str | None
    created_at: datetime
    completed_at: datetime | None
