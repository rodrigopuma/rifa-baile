"""Máquina de estados de pagamentos, cancelamento e conciliação.

Princípios:
- O status de um pagamento SEMPRE vem de uma consulta ao provedor (nunca do corpo do webhook
  nem de ação manual). Não existe aprovação manual.
- Transições são idempotentes: reaplicar o mesmo status não gera efeitos nem logs duplicados.
- Números só voltam a ficar livres quando o provedor confirma um estado terminal
  (cancelado, expirado, rejeitado, estornado). Enquanto a cobrança puder ser aprovada,
  os números continuam reservados.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import utcnow
from ..models import Order, Payment
from ..providers import get_provider
from ..providers.base import ProviderError, ProviderPayment
from . import audit
from .reservations import confirm_numbers_for_payment, release_order_numbers

log = logging.getLogger("rifa.payments")

TERMINAL_FAILURES = ("cancelled", "expired", "rejected")


def map_provider_status(status: str, detail: str = "") -> str:
    if status == "approved":
        return "approved"
    if status in ("pending", "authorized"):
        return "pending"
    if status in ("in_process", "in_mediation"):
        return "in_review"
    if status == "rejected":
        return "rejected"
    if status == "cancelled":
        return "expired" if detail == "expired" else "cancelled"
    if status in ("refunded", "charged_back"):
        return "refunded"
    return "in_review"


def _lock_order(db: Session, order_id: uuid.UUID) -> Order:
    return db.execute(
        select(Order).where(Order.id == order_id).with_for_update(of=Order).execution_options(populate_existing=True)
    ).scalar_one()


def _find_payment(db: Session, provider: str, provider_payment_id: str) -> Payment | None:
    return db.execute(
        select(Payment)
        .where(Payment.provider == provider, Payment.provider_payment_id == provider_payment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _set_review(db: Session, order: Order, reason: str, actor_type: str) -> None:
    if order.status != "in_review" or order.review_reason != reason:
        order.status = "in_review"
        order.review_reason = reason
        audit.log(db, "order_in_review", actor_type=actor_type, entity_type="order", entity_id=order.id,
                  details={"reason": reason})


def _on_approved(db: Session, order: Order, payment: Payment, pp: ProviderPayment, actor_type: str) -> None:
    settings = get_settings()
    if order.status == "paid":
        return
    problems = []
    if pp.amount_cents != order.total_cents:
        problems.append(f"valor pago ({pp.amount_cents}) difere do pedido ({order.total_cents})")
    if pp.external_reference and pp.external_reference != str(order.id):
        problems.append("referência externa não corresponde ao pedido")
    if pp.live_mode and not settings.is_live:
        problems.append("pagamento em produção recebido com o sistema em modo de testes")
    if order.status == "refunded":
        problems.append("pedido já estornado")
    if problems:
        _set_review(db, order, "; ".join(problems), actor_type)
        return

    was_closed = order.status in ("cancelled", "expired")
    numbers = [n.number for n in order.numbers]
    sp = db.begin_nested()
    try:
        ok = confirm_numbers_for_payment(db, order.campaign_id, order.id, numbers)
    except IntegrityError:
        ok = False
    if not ok:
        sp.rollback()
        _set_review(
            db, order,
            "Pagamento aprovado, mas parte dos números já pertence a outro pedido. "
            "Realize o estorno pelo Mercado Pago ou contate o participante.",
            actor_type,
        )
        return
    sp.commit()
    now = utcnow()
    order.status = "paid"
    order.paid_at = now
    order.closed_at = now
    order.review_reason = ""
    audit.log(db, "late_payment_reconciled" if was_closed else "order_paid", actor_type=actor_type,
              entity_type="order", entity_id=order.id,
              details={"numbers": numbers, "amount_cents": pp.amount_cents})


def _on_failed(db: Session, order: Order, new_status: str, actor_type: str) -> None:
    if order.status == "pending":
        released = release_order_numbers(db, order.id, ("reserved",))
        order.status = "expired" if new_status == "expired" else "cancelled"
        order.closed_at = utcnow()
        audit.log(db, "order_closed", actor_type=actor_type, entity_type="order", entity_id=order.id,
                  details={"status": order.status, "released": released})
    elif order.status == "paid":
        _set_review(db, order, f"Provedor informou '{new_status}' para pedido já pago", actor_type)


def _on_refunded(db: Session, order: Order, actor_type: str) -> None:
    if order.status in ("paid", "pending", "in_review"):
        released = release_order_numbers(db, order.id, ("reserved", "paid"))
        order.status = "refunded"
        order.closed_at = utcnow()
        audit.log(db, "order_refunded", actor_type=actor_type, entity_type="order", entity_id=order.id,
                  details={"released": released})


def apply_provider_payment(db: Session, pp: ProviderPayment, *, actor_type: str = "system",
                           actor_id: str = "") -> Order | None:
    """Aplica o estado informado pelo provedor. Idempotente. Faz commit."""
    provider_name = get_provider().name
    payment = _find_payment(db, provider_name, pp.id)
    if payment is None:
        # Cobrança criada no provedor mas não registrada (ex.: timeout na criação).
        try:
            order_id = uuid.UUID(pp.external_reference)
        except ValueError:
            order_id = None
        order = db.get(Order, order_id) if order_id else None
        if order is None:
            audit.log(db, "payment_unknown", actor_type=actor_type, entity_type="payment", entity_id=pp.id,
                      details={"status": pp.status, "external_reference": pp.external_reference})
            db.commit()
            return None
        if order.payment is not None:
            audit.log(db, "payment_duplicate_for_order", actor_type=actor_type, entity_type="order",
                      entity_id=order.id, details={"provider_payment_id": pp.id, "status": pp.status})
            if map_provider_status(pp.status, pp.status_detail) == "approved":
                order = _lock_order(db, order.id)
                _set_review(db, order, f"Segunda cobrança aprovada ({pp.id}) para o mesmo pedido: estornar.",
                            actor_type)
            db.commit()
            return order
        payment = Payment(order_id=order.id, provider=provider_name, provider_payment_id=pp.id,
                          idempotency_key=f"recovered:{pp.id}", amount_cents=pp.amount_cents,
                          status="pending", expires_at=pp.expires_at, live_mode=pp.live_mode,
                          qr_code=pp.qr_code, qr_code_base64=pp.qr_code_base64, ticket_url=pp.ticket_url)
        db.add(payment)
        db.flush()
        audit.log(db, "payment_recovered", actor_type=actor_type, entity_type="payment", entity_id=pp.id)

    order = _lock_order(db, payment.order_id)
    new_status = map_provider_status(pp.status, pp.status_detail)
    old_status = payment.status

    payment.provider_status = pp.status
    payment.status_detail = pp.status_detail
    payment.live_mode = pp.live_mode
    payment.raw_last = pp.raw
    payment.last_synced_at = utcnow()
    if pp.expires_at:
        payment.expires_at = pp.expires_at

    if new_status != old_status:
        payment.status = new_status
        if new_status == "approved":
            payment.approved_at = utcnow()
        audit.log(db, "payment_status_changed", actor_type=actor_type, actor_id=actor_id,
                  entity_type="payment", entity_id=payment.provider_payment_id,
                  details={"from": old_status, "to": new_status, "provider_status": pp.status,
                           "detail": pp.status_detail})

    # Efeitos no pedido (idempotentes; também corrigem estados inconsistentes)
    if new_status == "approved":
        _on_approved(db, order, payment, pp, actor_type)
    elif new_status in TERMINAL_FAILURES:
        _on_failed(db, order, new_status, actor_type)
    elif new_status == "refunded":
        _on_refunded(db, order, actor_type)

    db.commit()
    return order


def sync_payment(db: Session, payment: Payment, *, actor_type: str = "system", actor_id: str = "") -> Order | None:
    pp = get_provider().get_payment(payment.provider_payment_id)
    return apply_provider_payment(db, pp, actor_type=actor_type, actor_id=actor_id)


def request_cancellation(db: Session, order_id: uuid.UUID, *, reason: str, actor_type: str = "system",
                         actor_id: str = "") -> Order:
    """Encerra o checkout: solicita o cancelamento da cobrança ao provedor.
    Os números só são liberados quando o provedor confirmar o cancelamento/expiração."""
    provider = get_provider()
    order = _lock_order(db, order_id)
    if order.status != "pending":
        db.commit()
        return order

    if order.cancel_requested_at is None:
        order.cancel_requested_at = utcnow()
        audit.log(db, "cancel_requested", actor_type=actor_type, actor_id=actor_id, entity_type="order",
                  entity_id=order.id, details={"reason": reason})
    payment = order.payment
    db.commit()  # não segura bloqueios durante chamadas de rede

    if payment is None:
        try:
            pp = provider.find_by_reference(str(order.id))
        except ProviderError as exc:
            log.warning("Busca por referência falhou para %s: %s", order.id, exc)
            return order
        if pp is not None:
            apply_provider_payment(db, pp, actor_type=actor_type, actor_id=actor_id)
            # se ainda pendente, tenta cancelar na próxima rodada
            return db.get(Order, order.id)  # type: ignore[return-value]
        order = _lock_order(db, order.id)
        if order.status == "pending" and order.payment is None:
            release_order_numbers(db, order.id, ("reserved",))
            order.status = "cancelled"
            order.closed_at = utcnow()
            audit.log(db, "order_closed", actor_type=actor_type, entity_type="order", entity_id=order.id,
                      details={"status": "cancelled", "reason": "cobrança não foi criada"})
        db.commit()
        return order

    try:
        pp = provider.get_payment(payment.provider_payment_id)
        if pp.status in ("pending", "in_process", "authorized"):
            try:
                pp = provider.cancel_payment(payment.provider_payment_id)
            except ProviderError as exc:
                # Pode ter sido aprovado no meio do caminho: consulta de novo.
                log.info("Cancelamento não aceito para %s: %s", payment.provider_payment_id, exc)
                audit.log(db, "cancel_not_accepted", actor_type=actor_type, entity_type="payment",
                          entity_id=payment.provider_payment_id, details={"error": str(exc)[:300]})
                db.commit()
                pp = provider.get_payment(payment.provider_payment_id)
    except ProviderError as exc:
        log.warning("Falha ao consultar/cancelar %s: %s", payment.provider_payment_id, exc)
        audit.log(db, "cancel_failed", actor_type=actor_type, entity_type="payment",
                  entity_id=payment.provider_payment_id, details={"error": str(exc)[:300]})
        db.commit()
        return order
    apply_provider_payment(db, pp, actor_type=actor_type, actor_id=actor_id)
    return db.get(Order, order.id)  # type: ignore[return-value]


def reconcile_once(db: Session, batch: int = 50) -> dict[str, int]:
    """Uma rodada de conciliação. Seguro para rodar em paralelo (transições idempotentes)."""
    s = get_settings()
    now = utcnow()
    stats = {"checkout_expired": 0, "synced": 0, "errors": 0}

    # 1) Checkouts cujo prazo visual terminou: solicitar cancelamento
    due = db.execute(
        select(Order.id).where(Order.status == "pending", Order.checkout_expires_at <= now,
                               Order.cancel_requested_at.is_(None)).limit(batch)
    ).scalars().all()
    for oid in due:
        try:
            request_cancellation(db, oid, reason="checkout_timeout")
            stats["checkout_expired"] += 1
        except Exception:  # noqa: BLE001
            db.rollback()
            stats["errors"] += 1
            log.exception("Erro ao encerrar checkout %s", oid)

    # 2) Pedidos pendentes já encerrados (aguardando confirmação do provedor) e
    #    cobranças não sincronizadas recentemente: consultar o provedor.
    stale = now - timedelta(minutes=2)
    rows = db.execute(
        select(Order.id, Order.cancel_requested_at, Order.payment_expires_at, Payment.id)
        .join(Payment, Payment.order_id == Order.id, isouter=True)
        .where(Order.status == "pending")
        .where((Payment.last_synced_at.is_(None)) | (Payment.last_synced_at <= stale)
               | (Order.cancel_requested_at.is_not(None)))
        .limit(batch)
    ).all()
    for oid, cancel_requested_at, payment_expires_at, pay_id in rows:
        try:
            if pay_id is None:
                created = db.get(Order, oid)
                if created and created.created_at <= now - timedelta(seconds=s.orphan_order_grace_seconds):
                    request_cancellation(db, oid, reason="cobrança não registrada")
                continue
            payment = db.get(Payment, pay_id)
            assert payment is not None
            order = sync_payment(db, payment)
            stats["synced"] += 1
            # Cancelamento ainda não confirmado: tenta de novo após o vencimento do Pix.
            if (order is not None and order.status == "pending" and cancel_requested_at is not None
                    and payment_expires_at <= now):
                request_cancellation(db, oid, reason="pix_vencido")
        except ProviderError as exc:
            db.rollback()
            stats["errors"] += 1
            log.warning("Conciliação falhou para %s: %s", oid, exc)
        except Exception:  # noqa: BLE001
            db.rollback()
            stats["errors"] += 1
            log.exception("Erro inesperado na conciliação de %s", oid)
    return stats
