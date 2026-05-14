"""CoinBot FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from coinbot_api import __version__
from coinbot_api.api import advisor, crypto, crypto_derivs, crypto_research, crypto_whale, data, token_unlock
from coinbot_common.config import get_settings


def _include_with_api_alias(app: FastAPI, routers: Iterable[APIRouter]) -> None:
    """Register routers at their native path and under the /api alias."""
    for router in routers:
        app.include_router(router)
        app.include_router(router, prefix="/api")


def create_app() -> FastAPI:
    """Create and configure the CoinBot FastAPI app."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        """Return API health status."""
        return {"status": "ok", "service": "coinbot-api", "version": __version__}

    _include_with_api_alias(
        app,
        (
            data.router,
            crypto.router,
            crypto_derivs.router,
            advisor.router,
            crypto_research.router,
            crypto_whale.router,
            token_unlock.router,
        ),
    )
    return app


app = create_app()
