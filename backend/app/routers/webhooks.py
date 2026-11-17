"""Webhook do Mercado Pago.

1. Valida a assinatura x-signature (HMAC-SHA256 com a chave secreta do painel do MP).
2. Deduplica por x-request-id.
3. NUNCA confia no corpo: consulta o pagamento na API e aplica a transição idempotente.
Responde 200 rapidamente; em falha de consulta, responde 500 para o MP reenviar.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import new_session, utcnow
from ..models import WebhookEvent
from ..providers import get_provider
from ..providers.base import ProviderError
from ..providers.mercadopago import verify_webhook_signature
from ..services.payments import apply_provider_payment

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
log = logging.getLogger("rifa.webhooks")


@router.post("/mercadopago")
async def mercadopago_webhook(request: Request) -> Response:
    s = get_settings()
    if s.payment_mode in ("simulator", "manual_pix"):
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    q = request.query_params
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    topic = q.get("type") or q.get("topic") or body.get("type") or body.get("topic") or ""
    data_id = q.get("data.id") or str((body.get("data") or {}).get("id") or "")
    request_id = request.headers.get("x-request-id", "")

    if not verify_webhook_signature(s.mp_webhook_secret, request.headers.get("x-signature"),
                                    request_id, q.get("data.id")):
        log.warning("Webhook com assinatura inválida (request-id=%s)", request_id)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Assinatura inválida")

    if topic != "payment" or not data_id:
        return Response(status_code=200)

    with new_session() as db:
        code = await run_in_threadpool(_process, db, request_id, topic, data_id)
    return Response(status_code=code)


def _process(db: Session, request_id: str, topic: str, data_id: str) -> int:
    event = None
    if request_id:
        existing = db.execute(
            select(WebhookEvent).where(WebhookEvent.provider == "mercadopago",
                                       WebhookEvent.request_id == request_id)
        ).scalar_one_or_none()
        if existing and existing.processed_at:
            return 200  # notificação duplicada
        if existing is None:
            event = WebhookEvent(provider="mercadopago", request_id=request_id, topic=topic, resource_id=data_id)
            db.add(event)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                return 200  # outra instância está processando
        else:
            event = existing

    try:
        pp = get_provider().get_payment(data_id)
    except ProviderError as exc:
        log.warning("Não foi possível consultar pagamento %s: %s", data_id, exc)
        if exc.status_code == 404:
            return 200
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Consulta ao provedor falhou") from exc

    apply_provider_payment(db, pp, actor_type="webhook", actor_id=request_id)
    if event is not None:
        event = db.get(WebhookEvent, event.id)
        if event:
            event.processed_at = utcnow()
            db.commit()
    return 200
