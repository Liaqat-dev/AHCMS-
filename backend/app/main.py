"""Application factory: middleware, routers, exception handlers, CORS."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.exceptions.handlers import register_exception_handlers
from app.middleware.catch_all import CatchAllMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware


def create_app() -> FastAPI:
    configure_logging("DEBUG" if settings.DEBUG else "INFO")

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Rate limiting (innermost of our middleware; runs closest to the route).
    app.add_middleware(RateLimitMiddleware)

    # Wraps the rate limiter and runs inside CORS/RequestID, so unhandled 500s
    # keep their CORS headers and correlation id.
    app.add_middleware(CatchAllMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,  # required for the refresh-cookie flow (later)
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Outermost middleware: assign a correlation id before anything else runs.
    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
