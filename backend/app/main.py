from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import admin, cron, public, simulator, webhooks
from .worker import loop_forever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rifa")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    log.info("Modo de pagamento: %s", s.payment_mode)
    if s.payment_mode != "mercadopago_live":
        log.warning("AMBIENTE DE TESTES: nenhuma cobrança real será realizada.")
    if s.auto_apply_campaign_config:
        await run_in_threadpool(_apply_campaign_config)
    stop = asyncio.Event()
    task = asyncio.create_task(loop_forever(stop)) if s.run_background_reconciler else None
    yield
    stop.set()
    if task:
        await task


def _apply_campaign_config() -> None:
    """Aplica o campanha.json se ele mudou desde a última vez. Nunca impede a API de subir."""
    from .db import new_session
    from .services.campaign_config import CampaignConfigError, apply_from_file

    try:
        with new_session() as db:
            result = apply_from_file(db)
        log.info("campanha.json: %s", result)
    except CampaignConfigError as exc:
        log.error("campanha.json NÃO aplicado: %s", exc)
    except Exception:  # noqa: BLE001
        log.exception("Falha ao aplicar campanha.json")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Rifa Solidária — Formatura CPOR/R",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if s.environment != "production" else None,
        openapi_url="/api/openapi.json" if s.environment != "production" else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type", "X-Order-Token"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store")
        if s.public_base_url.startswith("https://"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    app.include_router(public.router)
    app.include_router(webhooks.router)
    app.include_router(admin.router)
    app.include_router(cron.router)
    if s.payment_mode == "simulator":
        app.include_router(simulator.router)
    return app


app = create_app()
