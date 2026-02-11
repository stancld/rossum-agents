"""FastAPI application entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, Request, status
from gunicorn.app.base import BaseApplication

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from rossum_agent.api.routes import chats, files, health, messages, slack
from rossum_agent.api.services.agent_service import AgentService
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.api.services.file_service import FileService

logger = logging.getLogger(__name__)

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB (supports image uploads)

GUNICORN_TIMEOUT = 120
GUNICORN_GRACEFUL_TIMEOUT = 30
GUNICORN_KEEPALIVE = 5

limiter = Limiter(key_func=get_remote_address)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_SIZE:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"Request body too large. Maximum size is {MAX_REQUEST_SIZE // 1024} KB."},
            )
        return await call_next(request)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


def _init_services(app: FastAPI) -> None:
    """Initialize services and store them in app.state.

    Skips initialization if services are already set (e.g., during testing).
    """
    if not hasattr(app.state, "chat_service"):
        app.state.chat_service = ChatService()
    if not hasattr(app.state, "agent_service"):
        app.state.agent_service = AgentService()
    if not hasattr(app.state, "file_service"):
        app.state.file_service = FileService(app.state.chat_service.storage)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for startup and shutdown events."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("Rossum Agent API starting up...")

    _init_services(app)

    if app.state.chat_service.is_connected():
        logger.info("Redis connection established")
    else:
        logger.warning("Redis connection failed - some features may not work")

    yield

    logger.info("Rossum Agent API shutting down...")
    app.state.chat_service.storage.close()


app = FastAPI(
    title="Rossum Agent API",
    description="REST API for Rossum Agent - AI-powered document processing assistant",
    version="0.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(RequestSizeLimitMiddleware)


def _build_cors_origin_regex() -> str:
    """Build CORS origin regex including any additional allowed hosts."""
    patterns = [r".*\.rossum\.(app|ai)"]
    additional_hosts = os.environ.get("ADDITIONAL_ALLOWED_ROSSUM_HOSTS", "")
    if additional_hosts:
        patterns.extend(p.strip() for p in additional_hosts.split(",") if p.strip())
    return rf"https://({'|'.join(patterns)})"


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://elis.rossum.ai",
        "https://elis.develop.r8.lol",
    ],
    allow_origin_regex=_build_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(chats.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(slack.router, prefix="/api/v1")


def _run_uvicorn(args: argparse.Namespace) -> None:
    uvicorn.run(
        "rossum_agent.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        ws="wsproto",
    )


def _run_gunicorn(args: argparse.Namespace) -> None:
    """Run the server with gunicorn using UvicornWorker."""
    if args.reload:
        print("Error: --reload is not supported with gunicorn. Use uvicorn for development.")
        sys.exit(1)

    class StandaloneApplication(BaseApplication):
        def __init__(self, app_uri: str, options: dict | None = None):
            self.app_uri = app_uri
            self.options = options or {}
            super().__init__()

        def load_config(self) -> None:
            for key, value in self.options.items():
                if key in self.cfg.settings and value is not None:  # ty: ignore[possibly-missing-attribute]
                    self.cfg.set(key.lower(), value)  # ty: ignore[possibly-missing-attribute]

        def load(self):
            return self.app_uri

    options = {
        "bind": f"{args.host}:{args.port}",
        "workers": args.workers,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "timeout": GUNICORN_TIMEOUT,
        "graceful_timeout": GUNICORN_GRACEFUL_TIMEOUT,
        "keepalive": GUNICORN_KEEPALIVE,
    }

    StandaloneApplication("rossum_agent.api.main:app", options).run()


def main() -> None:
    """CLI entry point for the API server."""
    parser = argparse.ArgumentParser(description="Run the Rossum Agent API server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (default: 1)")
    parser.add_argument(
        "--server",
        choices=["uvicorn", "gunicorn"],
        default="uvicorn",
        help="Server backend to use (default: uvicorn)",
    )

    args = parser.parse_args()

    if args.server == "gunicorn":
        _run_gunicorn(args)
    else:
        _run_uvicorn(args)


if __name__ == "__main__":
    main()
