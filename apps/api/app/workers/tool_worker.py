"""Tool execution worker — BullMQ Worker for tool-execution queue.

Replaces the TypeScript tool-execution processor. Calls McpRuntimeService
directly without HTTP roundtrip.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bullmq import Job, Worker

from app.core.settings import Settings
from app.domain.models import UserRole
from app.domain.tenant_context import TenantContext

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


def create_tool_worker(
    settings: Settings,
    session_factory: "async_sessionmaker",
    redis_url: str,
) -> Worker:
    """Create BullMQ Worker for tool-execution queue."""

    async def handle_tool_execution(job: Job, token: str) -> dict[str, object]:
        data = job.data
        tenant_id = data["tenant_id"]
        tool_id = data["tool_definition_id"]
        input_data = data.get("input_data", {})
        logger.info("[tool-execution] job=%s tool=%s tenant=%s", job.id, tool_id, tenant_id)

        tenant = TenantContext(
            tenant_id=tenant_id,
            membership_id=tenant_id,
            user_id=data.get("query_id", tenant_id),
            role=UserRole.USER,
        )

        from app.application.mcp_runtime_service import McpRuntimeService
        from app.application.provider_credential_service import ProviderCredentialService
        from app.infrastructure.mcp.connection_manager import McpConnectionManager
        from app.infrastructure.rag_catalog import (
            SqlAlchemyMcpServerRepository,
            SqlAlchemyMcpToolRepository,
            SqlAlchemyMcpInvocationRepository,
            SqlAlchemyProviderCredentialRepository,
        )

        async with session_factory() as session:
            service = McpRuntimeService(
                settings=settings,
                servers=SqlAlchemyMcpServerRepository(session),
                tools=SqlAlchemyMcpToolRepository(session),
                invocations=SqlAlchemyMcpInvocationRepository(session),
                credentials=ProviderCredentialService(session, settings),
                connections=McpConnectionManager(),
            )
            result = await service.invoke_tool(
                tenant=tenant,
                tool_id=tool_id,
                arguments=input_data,
            )

        logger.info("[tool-execution] job=%s completed", job.id)
        return result

    worker = Worker(
        "tool-execution",
        handle_tool_execution,
        {"connection": redis_url, "concurrency": 5},
    )

    worker.on("failed", lambda job, err: logger.error(
        "[tool-execution] job=%s failed: %s", job.id if job else "?", err
    ))

    return worker
