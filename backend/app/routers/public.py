from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Order
from ..ratelimit import SlidingWindowLimiter, enforce
from ..schemas import OrderCreate
from ..security import token_matches
from ..services import campaigns as campaign_svc
from ..services import manual as manual_svc
from ..services.orders import create_order, public_order_view, receipt_view
from ..services.payments import request_cancellation

router = APIRouter(prefix="/api", tags=["público"])

order_limiter = SlidingWindowLimiter(limit=get_settings().order_rate_limit_per_10min, window_seconds=600)
lookup_limiter = SlidingWindowLimiter(limit=240, window_seconds=600)


@router.get("/health")
def health() -> dict:
    return {"ok": True, "payment_mode": get_settings().public_payment_mode}


@router.get("/campaign")
def campaign_info(db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    if s.is_manual:
        manual_svc.expire_due(db)
    c = campaign_svc.get_public_campaign(db)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhuma campanha publicada.")
    counts = campaign_svc.counts(db, c.id)
    return {
        "id": str(c.id),
        "name": c.name,
        "subtitle": c.subtitle,
        "description": c.description,
        "prize_title": c.prize_title,
        "price_cents": c.price_cents,
        "bundle_size": c.bundle_size,
        "bundle_price_cents": c.bundle_price_cents,
        "total_numbers": c.total_numbers,
        "available_count": counts["available"],  # não expõe a contagem de reservados
        "draw_date": c.draw_date.isoformat() if c.draw_date else None,
        "organizer_name": c.organizer_name,
        "organizer_contact": c.organizer_contact,
        "regulation_text": c.regulation_text,
        "authorization_info": c.authorization_info,
        "header_image_url": c.header_image_url,
        "status": c.status,
        "payment_mode": s.public_payment_mode,
        "checkout_window_minutes": s.checkout_window_minutes,
        "max_numbers_per_order": s.max_numbers_per_order,
        "payer_cpf_required": s.payer_cpf_required and not s.is_manual,
        "reservation_hold_minutes": s.manual_hold_minutes if s.is_manual else None,
    }


@router.get("/campaign/availability")
def availability(db: Session = Depends(get_db)) -> dict:
    if get_settings().is_manual:
        manual_svc.expire_due(db)
    c = campaign_svc.get_public_campaign(db)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhuma campanha publicada.")
    unavailable = campaign_svc.unavailable_numbers(db, c.id)
    return {
        "campaign_id": str(c.id),
        "total_numbers": c.total_numbers,
        "unavailable": unavailable,  # reservados e pagos, indistintos
        "available_count": c.total_numbers - len(unavailable),
    }


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def post_order(body: OrderCreate, request: Request, db: Session = Depends(get_db)) -> dict:
    enforce(order_limiter, request)
    order, token = create_order(db, numbers=body.numbers, full_name=body.full_name, email=body.email or "",
                                phone=body.phone, cpf=body.cpf)
    return {"order": public_order_view(order), "access_token": token}


def _load_order(db: Session, order_id: str, token: str | None) -> Order:
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado") from None
    order = db.get(Order, oid)
    # Mesma resposta para "não existe" e "token incorreto": evita enumeração.
    if order is None or not token_matches(token, order.access_token_hash):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")
    return order


@router.get("/orders/{order_id}")
def get_order(order_id: str, request: Request, x_order_token: str | None = Header(default=None),
              db: Session = Depends(get_db)) -> dict:
    enforce(lookup_limiter, request)
    order = _load_order(db, order_id, x_order_token)
    if get_settings().is_manual and order.status == "pending":
        manual_svc.expire_order(db, order.id)  # vence a reserva se o prazo acabou
        db.refresh(order)
    return public_order_view(order)


@router.post("/orders/{order_id}/checkout-timeout")
def checkout_timeout(order_id: str, request: Request, x_order_token: str | None = Header(default=None),
                     db: Session = Depends(get_db)) -> dict:
    """Chamado pelo navegador ao fim dos 15 minutos. A conciliação em segundo plano faz o
    mesmo caso o navegador seja fechado."""
    enforce(lookup_limiter, request)
    order = _load_order(db, order_id, x_order_token)
    from ..db import utcnow

    if order.status == "pending" and utcnow() >= order.checkout_expires_at:
        if get_settings().is_manual:
            order = manual_svc.expire_order(db, order.id)
        else:
            order = request_cancellation(db, order.id, reason="checkout_timeout", actor_type="participant")
    return public_order_view(db.get(Order, order.id))  # type: ignore[arg-type]


@router.get("/receipts/{order_id}")
def get_receipt(order_id: str, request: Request, x_order_token: str | None = Header(default=None),
                db: Session = Depends(get_db)) -> dict:
    enforce(lookup_limiter, request)
    order = _load_order(db, order_id, x_order_token)
    if order.status != "paid":
        raise HTTPException(status.HTTP_409_CONFLICT, "Comprovante disponível apenas para pedidos pagos.")
    return receipt_view(order)
