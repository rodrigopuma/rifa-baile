"""Endpoints EXCLUSIVOS do simulador local (PAYMENT_MODE=simulator).
Retornam 404 em qualquer outro modo. Simulam o provedor mudando o estado e enviando a
"notificação", que segue exatamente o mesmo fluxo de conciliação do webhook real."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..providers import get_provider
from ..providers.base import ProviderError
from ..services.payments import apply_provider_payment

router = APIRouter(prefix="/api/dev/simulator", tags=["simulador (somente testes)"])


@router.post("/payments/{payment_id}/{action}")
def simulate(payment_id: str, action: str, db: Session = Depends(get_db)) -> dict:
    if get_settings().payment_mode != "simulator":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    provider = get_provider()
    try:
        pp = provider.simulate(payment_id, action)  # type: ignore[attr-defined]
    except ProviderError as exc:
        raise HTTPException(exc.status_code or 400, str(exc)) from exc
    order = apply_provider_payment(db, pp, actor_type="webhook", actor_id="simulator")
    return {"payment_id": pp.id, "provider_status": pp.status, "order_status": order.status if order else None}
