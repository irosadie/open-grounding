from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings
from app.infrastructure.database import create_session_factory
from app.infrastructure.profile_seed import seed_default_profiles
from app.infrastructure.tenant_bootstrap import verify_and_bootstrap_tenant
from app.interfaces.http.errors import register_exception_handlers
from app.interfaces.http.routes import auth_router, index_profile_router, kb_router, model_profile_router, rag_query_router, rag_router, system_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.tenant_bootstrap_result = await verify_and_bootstrap_tenant(settings)
    session_factory = create_session_factory(settings)
    async with session_factory() as session:
        await seed_default_profiles(session, settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Vibecoding Starter API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    register_exception_handlers(app)
    app.include_router(system_router)
    app.include_router(auth_router)
    app.include_router(rag_router)
    app.include_router(rag_query_router)
    app.include_router(kb_router)
    app.include_router(model_profile_router)
    app.include_router(index_profile_router)
    return app


app = create_app()
