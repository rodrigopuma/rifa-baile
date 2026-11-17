"""Modo manual (PAYMENT_MODE=manual_pix): reserva de números + confirmação pelo organizador.

Fluxo:
1. O participante escolhe os números e informa nome e WhatsApp. Os números ficam RESERVADOS
   por MANUAL_HOLD_MINUTES (padrão: 24 h).
2. Ele paga por Pix direto na chave do organizador e manda o comprovante pelo WhatsApp.
3. O organizador confere o pagamento no app do banco e clica em "Confirmar pagamento" no painel.
   Só então os números viram PAGOS e o participante recebe o comprovante.
4. Se ninguém confirmar até o fim do prazo, a reserva vence e os números voltam a ficar livres.

Garantias mantidas do fluxo automático: a reserva é atômica (mesmo SELECT ... FOR UPDATE e
índice único), o preço vem do banco, e toda ação do organizador fica no audit_log.
Aqui QUEM decide é o organizador; por isso estas funções só são chamadas por rotas de admin
(confirmar, cancelar, estornar) ou pelo vencimento automático das reservas.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import Order, Payment
from . import audit
from .payments import _lock_order
from .reservations import confirm_numbers_for_payment, release_order_numbers

log = logging.getLogger("rifa.manual")

PROVIDER = "manual"


def attach_payment(db: Session, order: Order) -> Order:
    """Cria o registro de pagamento (pendente) do pedido. Não há cobrança em nenhum provedor."""
    db.add(Payment(
        order_id=order.id, provider=PROVIDER, provider_payment_id=order.code,
        idempotency_key=str(order.id), status="pending", provider_status="awaiting_manual_confirmation",
        status_detail="", amount_cents=order.total_cents, live_mode=False,
        expires_at=order.checkout_expires_at, last_synced_at=utcnow(),
    ))
    audit.log(db, "manual_reservation_created", actor_type="participant", entity_type="order",
              entity_id=order.id, details={"numbers": [n.number for n in order.numbers],
                                           "total_cents": order.total_cents})
    db.commit()
    db.expire_all()
    return db.get(Order, order.id)  # type: ignore[return-value]


def _set_payment(order: Order, status_: str, detail: str, *, approved: bool = False) -> None:
    p = order.payment
    if p is None:
        return
    p.status = status_
    p.provider_status = status_
    p.status_detail = detail
    p.last_synced_at = utcnow()
    if approved:
        p.approved_at = utcnow()


def _close(db: Session, order: Order, new_status: str, detail: str, *, actor_type: str, actor_id: str = "",
           release_from: tuple[str, ...] = ("reserved",)) -> int:
    released = release_order_numbers(db, order.id, release_from)
    order.status = new_status
    order.closed_at = utcnow()
    _set_payment(order, new_status, detail)
    audit.log(db, "order_closed", actor_type=actor_type, actor_id=actor_id, entity_type="order",
              entity_id=order.id, details={"status": new_status, "reason": detail, "released": released})
    return released


def expire_order(db: Session, order_id: uuid.UUID) -> Order:
    """Vence a reserva se o prazo acabou e o pedido continua pendente. Idempotente."""
    order = _lock_order(db, order_id)
    if order.status == "pending" and order.checkout_expires_at <= utcnow():
        _close(db, order, "expired", "reserva vencida sem confirmação", actor_type="system")
    db.commit()
    return order


def expire_due(db: Session, batch: int = 100) -> int:
    """Libera os números de todas as reservas vencidas. Barato o bastante para rodar a cada consulta."""
    now = utcnow()
    ids = db.execute(
        select(Order.id).where(Order.status == "pending", Order.checkout_expires_at <= now).limit(batch)
    ).scalars().all()
    for oid in ids:
        try:
            expire_order(db, oid)
        except Exception:  # noqa: BLE001
            db.rollback()
            log.exception("Falha ao vencer a reserva %s", oid)
    return len(ids)


def reconcile(db: Session) -> dict[str, int]:
    """Substitui a conciliação com o provedor no modo manual: só vence reservas."""
    return {"checkout_expired": expire_due(db), "synced": 0, "errors": 0}


def confirm(db: Session, order_id: uuid.UUID, *, admin_id: str) -> Order:
    """O organizador confirmou que o Pix caiu. Também aceita reserva já vencida/cancelada
    (pagamento tardio), desde que todos os números ainda estejam livres."""
    order = _lock_order(db, order_id)
    if order.status == "paid":
        db.commit()
        return order  # idempotente
    if order.status not in ("pending", "expired", "cancelled"):
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Este pedido não pode ser confirmado no estado atual.")

    was_closed = order.status in ("expired", "cancelled")
    numbers = [n.number for n in order.numbers]
    sp = db.begin_nested()
    try:
        ok = confirm_numbers_for_payment(db, order.campaign_id, order.id, numbers)
    except IntegrityError:
        ok = False
    if not ok:
        sp.rollback()
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Parte dos números já pertence a outro participante (a reserva venceu e alguém os pegou). "
            "Combine a devolução do Pix com o participante.",
        )
    sp.commit()
    now = utcnow()
    order.status = "paid"
    order.paid_at = now
    order.closed_at = now
    order.review_reason = ""
    _set_payment(order, "approved", "confirmado pelo organizador", approved=True)
    audit.log(db, "late_payment_reconciled" if was_closed else "order_paid", actor_type="admin",
              actor_id=admin_id, entity_type="order", entity_id=order.id,
              details={"numbers": numbers, "amount_cents": order.total_cents, "manual": True})
    db.commit()
    return order


def cancel(db: Session, order_id: uuid.UUID, *, admin_id: str) -> Order:
    """Cancela uma reserva pendente e libera os números na hora."""
    order = _lock_order(db, order_id)
    if order.status != "pending":
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Apenas reservas pendentes podem ser canceladas.")
    _close(db, order, "cancelled", "cancelada pelo organizador", actor_type="admin", actor_id=admin_id)
    db.commit()
    return order


def refund(db: Session, order_id: uuid.UUID, *, admin_id: str) -> Order:
    """Desfaz uma confirmação (pagamento devolvido ou clique errado): libera os números."""
    order = _lock_order(db, order_id)
    if order.status != "paid":
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Apenas pedidos pagos podem ser estornados.")
    released = release_order_numbers(db, order.id, ("reserved", "paid"))
    order.status = "refunded"
    order.closed_at = utcnow()
    _set_payment(order, "refunded", "estornado pelo organizador")
    audit.log(db, "order_refunded", actor_type="admin", actor_id=admin_id, entity_type="order",
              entity_id=order.id, details={"released": released, "manual": True})
    db.commit()
    return order
