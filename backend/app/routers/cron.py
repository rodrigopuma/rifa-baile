"""Endpoint para agendadores externos (ex.: cron-job.org). Opcional: a API já concilia
sozinha enquanto está acordada. Protegido pelo cabeçalho X-Cron-Secret."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from ..config import get_settings
from ..worker import run_once

router = APIRouter(prefix="/api/cron", tags=["cron"])


@router.post("/reconcile")
async def reconcile(x_cron_secret: str | None = Header(default=None)) -> dict:
    secret = get_settings().cron_secret
    if not secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Segredo inválido")
    return await run_in_threadpool(run_once)
