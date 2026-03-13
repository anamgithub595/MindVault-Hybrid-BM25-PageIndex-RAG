"""
app/main.py
────────────
FastAPI application factory.
Registers routers, middleware, startup/shutdown hooks, global exception handlers.
Zero business logic lives here.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.documents import docs_router, health_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.query import router as query_router
from app.core.config import get_settings
from app.core.exceptions import (
    DocumentNotFoundError,
    EmptyQueryError,
    FileTooLargeError,
    LLMProviderError,
    MindVaultError,
    NoResultsError,
    PageIndexRetrievalError,
    PageIndexSubmitError,
    PageIndexTimeoutError,
    UnsupportedFileTypeError,
)
from app.db.database import create_all_tables

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("mindvault")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="MindVault",
        description=(
            "Enterprise Knowledge Base — Hybrid BM25 + PageIndex RAG\n\n"
            "**Pipeline:** Document Upload → BM25 Index (SQLite) + PageIndex Tree (cloud) "
            "→ Parallel Retrieval → RRF Fusion → LLM Answer with Citations"
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Static files (UI) ─────────────────────────────────────────────
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_ui():
            return FileResponse(str(static_dir / "index.html"))

    # ── Routers ───────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    app.include_router(docs_router)

    # ── Lifecycle ─────────────────────────────────────────────────────
    @app.on_event("startup")
    async def startup():
        logger.info("MindVault starting…")
        await create_all_tables()
        logger.info("DB tables ready.")
        logger.info(f"Pipeline: BM25 + PageIndex (alpha={settings.hybrid_alpha})")

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("MindVault shutting down.")

    # ── Exception handlers ────────────────────────────────────────────
    def _err(code: int, msg: str):
        return JSONResponse(status_code=code, content={"detail": msg})

    @app.exception_handler(UnsupportedFileTypeError)
    async def _(r: Request, e: UnsupportedFileTypeError):
        return _err(415, str(e))

    @app.exception_handler(FileTooLargeError)
    async def _(r: Request, e: FileTooLargeError):
        return _err(413, str(e))

    @app.exception_handler(EmptyQueryError)
    async def _(r: Request, e: EmptyQueryError):
        return _err(400, "Query is empty after normalisation.")

    @app.exception_handler(NoResultsError)
    async def _(r: Request, e: NoResultsError):
        return _err(404, "No matching pages found.")

    @app.exception_handler(LLMProviderError)
    async def _(r: Request, e: LLMProviderError):
        return _err(502, f"LLM error: {e}")

    @app.exception_handler(PageIndexSubmitError)
    async def _(r: Request, e: PageIndexSubmitError):
        return _err(502, f"PageIndex submit error: {e}")

    @app.exception_handler(PageIndexTimeoutError)
    async def _(r: Request, e: PageIndexTimeoutError):
        return _err(504, f"PageIndex timeout: {e}")

    @app.exception_handler(PageIndexRetrievalError)
    async def _(r: Request, e: PageIndexRetrievalError):
        return _err(502, f"PageIndex retrieval error: {e}")

    @app.exception_handler(DocumentNotFoundError)
    async def _(r: Request, e: DocumentNotFoundError):
        return _err(404, str(e))

    @app.exception_handler(MindVaultError)
    async def _(r: Request, e: MindVaultError):
        return _err(400, str(e))

    return app


app = create_app()


'''


"""
app/main.py
────────────
FastAPI application factory.
Registers routers, middleware, startup/shutdown hooks, global exception handlers.
Zero business logic lives here.
"""
from __future__ import annotations
import logging
import sys

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import (
    MindVaultError, UnsupportedFileTypeError, FileTooLargeError,
    EmptyQueryError, NoResultsError, LLMProviderError, DocumentNotFoundError,
    PageIndexSubmitError, PageIndexTimeoutError, PageIndexRetrievalError,
)
from app.db.database import create_all_tables
from app.api.routes.query import router as query_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.documents import docs_router, health_router

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("mindvault")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="MindVault",
        description=(
            "Enterprise Knowledge Base — Hybrid BM25 + PageIndex RAG\n\n"
            "**Pipeline:** Document Upload → BM25 Index (SQLite) + PageIndex Tree (cloud) "
            "→ Parallel Retrieval → RRF Fusion → LLM Answer with Citations"
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    app.include_router(docs_router)

    # ── Lifecycle ─────────────────────────────────────────────────────
    @app.on_event("startup")
    async def startup():
        logger.info("MindVault starting…")
        await create_all_tables()
        logger.info("DB tables ready.")
        logger.info(f"Pipeline: BM25 + PageIndex (alpha={settings.hybrid_alpha})")

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("MindVault shutting down.")

    # ── Exception handlers ────────────────────────────────────────────
    def _err(code: int, msg: str):
        return JSONResponse(status_code=code, content={"detail": msg})

    @app.exception_handler(UnsupportedFileTypeError)
    async def _(r: Request, e: UnsupportedFileTypeError):
        return _err(415, str(e))

    @app.exception_handler(FileTooLargeError)
    async def _(r: Request, e: FileTooLargeError):
        return _err(413, str(e))

    @app.exception_handler(EmptyQueryError)
    async def _(r: Request, e: EmptyQueryError):
        return _err(400, "Query is empty after normalisation.")

    @app.exception_handler(NoResultsError)
    async def _(r: Request, e: NoResultsError):
        return _err(404, "No matching pages found.")

    @app.exception_handler(LLMProviderError)
    async def _(r: Request, e: LLMProviderError):
        return _err(502, f"LLM error: {e}")

    @app.exception_handler(PageIndexSubmitError)
    async def _(r: Request, e: PageIndexSubmitError):
        return _err(502, f"PageIndex submit error: {e}")

    @app.exception_handler(PageIndexTimeoutError)
    async def _(r: Request, e: PageIndexTimeoutError):
        return _err(504, f"PageIndex timeout: {e}")

    @app.exception_handler(PageIndexRetrievalError)
    async def _(r: Request, e: PageIndexRetrievalError):
        return _err(502, f"PageIndex retrieval error: {e}")

    @app.exception_handler(DocumentNotFoundError)
    async def _(r: Request, e: DocumentNotFoundError):
        return _err(404, str(e))

    @app.exception_handler(MindVaultError)
    async def _(r: Request, e: MindVaultError):
        return _err(400, str(e))

    return app


app = create_app()


'''
