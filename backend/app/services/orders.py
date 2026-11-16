"""Criação de pedidos e geração da cobrança Pix."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import utcnow
from ..models import Campaign, Order, Participant, Payment
from ..providers import get_provider
from ..providers.base import CreatePixRequest, PayerInfo, ProviderError, ProviderPayment
from ..security import hash_token, new_access_token, new_order_code
from ..validators import mask_cpf
from . import audit
from .campaigns import get_active_campaign
from .reservations import NumbersUnavailable, release_order_numbers, reserve, unavailable_among

log = logging.getLogger("rifa.orders")


def _conflict(numbers: list[int]) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"message": "Alguns números acabaram de ficar indisponíveis.", "unavailable": numbers},
    )


def _get_or_create_participant(db: Session, full_name: str, email: str, phone: str, cpf: str | None) -> Participant:
    p = db.execute(
        select(Participant).where(Participant.email == email, Participant.phone == phone)
        .order_by(Participant.created_at.desc())
    ).scalars().first()
    if p is None:
        p = Participant(full_name=full_name, email=email, phone=phone)
        db.add(p)
    p.full_name = full_name
    if cpf:
        p.cpf_masked = mask_cpf(cpf)
    p.privacy_accepted_at = utcnow()
    db.flush()
    return p


def _pending_orders_for_contact(db: Session, email: str, phone: str) -> int:
    return db.execute(
        select(func.count()).select_from(Order).join(Participant)
        .where(Order.status == "pending", or_(Participant.email == email, Participant.phone == phone))
    ).scalar_one()


def create_order(db: Session, *, numbers: list[int], full_name: str, email: str, phone: str,
                 cpf: str | None) -> tuple[Order, str]:
    s = get_settings()
    campaign = get_active_campaign(db)
    if campaign is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Não há campanha ativa no momento.")
    if s.is_live and not campaign.authorization_info.strip():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Campanha sem informações de autorização: cobranças reais bloqueadas.")

    wanted = sorted(set(numbers))
    if not wanted:
        raise HTTPException(422, "Selecione ao menos um número.")
    if len(wanted) > s.max_numbers_per_order:
        raise HTTPException(422,
                            f"Máximo de {s.max_numbers_per_order} números por pedido.")
    if wanted[0] < 1 or wanted[-1] > campaign.total_numbers:
        raise HTTPException(422, "Número fora do intervalo da campanha.")
    if _pending_orders_for_contact(db, email, phone) >= s.max_pending_orders_per_contact:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Você já possui pedidos aguardando pagamento. Conclua-os ou aguarde o prazo.")

    taken = unavailable_among(db, campaign.id, wanted)
    if taken:
        raise _conflict(taken)

    # O preço vem SEMPRE do banco; valores enviados pelo navegador são ignorados.
    unit = campaign.price_cents
    now = utcnow()
    token = new_access_token()
    order = _reserve_with_retry(db, campaign, wanted, full_name, email, phone, cpf, unit, now, token)

    pp = _create_charge(db, campaign, order, full_name, email, cpf)
    return _attach_payment(db, order, pp), token


def _reserve_with_retry(db: Session, campaign: Campaign, wanted: list[int], full_name: str, email: str,
                        phone: str, cpf: str | None, unit: int, now, token: str) -> Order:
    s = get_settings()
    for attempt in range(3):
        try:
            participant = _get_or_create_participant(db, full_name, email, phone, cpf)
            order = Order(
                id=uuid.uuid4(), code=new_order_code(), campaign_id=campaign.id, participant_id=participant.id,
                status="pending", unit_price_cents=unit, quantity=len(wanted), total_cents=unit * len(wanted),
                access_token_hash=hash_token(token),
                checkout_expires_at=now + timedelta(minutes=s.checkout_window_minutes),
                payment_expires_at=now + timedelta(minutes=s.pix_expiration_minutes),
            )
            db.add(order)
            db.flush()
            reserve(db, campaign.id, wanted, order.id)
            audit.log(db, "order_created", actor_type="participant", entity_type="order", entity_id=order.id,
                      details={"numbers": wanted, "total_cents": order.total_cents})
            db.commit()
            return order
        except NumbersUnavailable:
            db.rollback()
            raise _conflict(unavailable_among(db, campaign.id, wanted) or wanted) from None
        except IntegrityError:
            db.rollback()  # colisão do índice único de números ativos ou do código do pedido
            taken = unavailable_among(db, campaign.id, wanted)
            if taken:
                raise _conflict(taken) from None
        except OperationalError:
            db.rollback()  # deadlock/serialização/lock: tenta novamente
            time.sleep(0.05 * (attempt + 1))
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Muitas solicitações simultâneas. Tente novamente.")


def _create_charge(db: Session, campaign: Campaign, order: Order, full_name: str, email: str,
                   cpf: str | None) -> ProviderPayment:
    s = get_settings()
    provider = get_provider()
    notification_url = None
    if provider.name == "mercadopago" and s.public_base_url.startswith("https://"):
        notification_url = f"{s.public_base_url.rstrip('/')}/api/webhooks/mercadopago"
    req = CreatePixRequest(
        external_reference=str(order.id),
        amount_cents=order.total_cents,
        description=f"{campaign.name} - pedido {order.code}",
        expires_at=order.payment_expires_at,
        idempotency_key=str(order.id),
        payer=PayerInfo(full_name=full_name, email=email, cpf=cpf),
        notification_url=notification_url,
    )
    try:
        pp = provider.create_pix(req)
    except ProviderError as exc:
        log.warning("Falha ao criar Pix para %s: %s", order.id, exc)
        pp_found = None
        try:
            pp_found = provider.find_by_reference(str(order.id))
        except ProviderError:
            pp_found = None
        if pp_found is None:
            if exc.retriable and exc.status_code is None:
                # Resultado incerto (timeout): mantém reservado; a conciliação decide depois.
                audit.log(db, "charge_uncertain", entity_type="order", entity_id=order.id,
                          details={"error": str(exc)[:300]})
                db.commit()
                raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                                    "Não foi possível confirmar a geração do Pix. Tente novamente em instantes.")
            release_order_numbers(db, order.id, ("reserved",))
            order.status = "cancelled"
            order.closed_at = utcnow()
            audit.log(db, "charge_failed", entity_type="order", entity_id=order.id,
                      details={"error": str(exc)[:300]})
            db.commit()
            raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                                "Não foi possível gerar o Pix agora. Tente novamente.") from exc
        pp = pp_found

    if pp.live_mode and not s.is_live:
        # Trava: credencial de produção usada com o sistema em modo de teste.
        try:
            provider.cancel_payment(pp.id)
        except ProviderError:
            pass
        release_order_numbers(db, order.id, ("reserved",))
        order.status = "cancelled"
        order.closed_at = utcnow()
        audit.log(db, "live_charge_blocked", entity_type="order", entity_id=order.id)
        db.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Pagamentos reais estão desabilitados neste ambiente.")
    return pp


def _attach_payment(db: Session, order: Order, pp: ProviderPayment) -> Order:
    provider = get_provider()
    payment = Payment(
        order_id=order.id, provider=provider.name, provider_payment_id=pp.id, idempotency_key=str(order.id),
        status="pending", provider_status=pp.status, status_detail=pp.status_detail,
        amount_cents=pp.amount_cents, live_mode=pp.live_mode, qr_code=pp.qr_code,
        qr_code_base64=pp.qr_code_base64, ticket_url=pp.ticket_url, expires_at=pp.expires_at,
        raw_last=pp.raw, last_synced_at=utcnow(),
    )
    db.add(payment)
    try:
        audit.log(db, "charge_created", entity_type="payment", entity_id=pp.id,
                  details={"order_id": str(order.id), "amount_cents": pp.amount_cents})
        db.commit()
    except IntegrityError:
        db.rollback()  # já registrado por um webhook concorrente
    db.expire_all()
    return db.get(Order, order.id)  # type: ignore[return-value]


# ---- Representação pública -------------------------------------------------

DISPLAY = {
    "paid": "paid",
    "cancelled": "cancelled",
    "expired": "expired",
    "refunded": "refunded",
    "in_review": "in_review",
}


def public_order_view(order: Order) -> dict[str, Any]:
    s = get_settings()
    now = utcnow()
    checkout_open = order.status == "pending" and now < order.checkout_expires_at
    if order.status == "pending":
        display = "awaiting_payment" if checkout_open else "awaiting_confirmation"
    else:
        display = DISPLAY[order.status]
    payment = order.payment
    first_name = order.participant.full_name.split()[0] if order.participant else ""
    data: dict[str, Any] = {
        "id": str(order.id),
        "code": order.code,
        "status": display,
        "numbers": [n.number for n in order.numbers],
        "quantity": order.quantity,
        "unit_price_cents": order.unit_price_cents,
        "total_cents": order.total_cents,
        "created_at": order.created_at.isoformat(),
        "checkout_expires_at": order.checkout_expires_at.isoformat(),
        "server_time": now.isoformat(),
        "participant_first_name": first_name,
        "payment_mode": s.public_payment_mode,
        "pix": None,
    }
    if checkout_open and payment is not None:
        data["pix"] = {
            "qr_code": payment.qr_code,
            "qr_code_base64": payment.qr_code_base64,
            "ticket_url": payment.ticket_url,
        }
        if s.payment_mode == "simulator":
            data["simulator_payment_id"] = payment.provider_payment_id
    if order.status == "paid":
        data["paid_at"] = order.paid_at.isoformat() if order.paid_at else None
        data["participant_name"] = order.participant.full_name
        data["paid_cents"] = payment.amount_cents if payment else order.total_cents
    return data


def receipt_view(order: Order) -> dict[str, Any]:
    campaign = order.campaign
    return {
        "order_id": str(order.id),
        "code": order.code,
        "status": order.status,
        "participant_name": order.participant.full_name,
        "numbers": [n.number for n in order.numbers],
        "total_cents": order.total_cents,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "campaign_name": campaign.name,
        "total_numbers": campaign.total_numbers,
        "campaign_subtitle": campaign.subtitle,
        "prize_title": campaign.prize_title,
        "draw_date": campaign.draw_date.isoformat() if campaign.draw_date else None,
        "organizer_name": campaign.organizer_name,
        "provider_payment_id": order.payment.provider_payment_id if order.payment else None,
        "payment_mode": get_settings().public_payment_mode,
    }
