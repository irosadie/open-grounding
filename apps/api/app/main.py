from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings
from app.infrastructure.tenant_bootstrap import verify_and_bootstrap_tenant
from app.interfaces.http.errors import register_exception_handlers
from app.interfaces.http.routes import auth_router, system_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Verify and bootstrap the deployment tenant at startup.
    # Fails fast if DEPLOYMENT_TENANT_ID is missing, malformed, or mismatched.
    app.state.tenant_bootstrap_result = await verify_and_bootstrap_tenant(get_settings())
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Vibecoding Starter API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    register_exception_handlers(app)
    app.include_router(system_router)
    app.include_router(auth_router)
    return app


app = create_app()
