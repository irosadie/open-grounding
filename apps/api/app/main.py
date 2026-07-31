from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.interfaces.http.errors import register_exception_handlers
from app.interfaces.http.routes import auth_router, system_router


def create_app() -> FastAPI:
    app = FastAPI(title="Vibecoding Starter API", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    register_exception_handlers(app)
    app.include_router(system_router)
    app.include_router(auth_router)
    return app


app = create_app()
