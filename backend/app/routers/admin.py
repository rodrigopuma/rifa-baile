from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import AdminUser, AuditLog, Campaign, Order, OrderNumber, Participant, Payment
from ..providers.base import ProviderError
from ..schemas import CampaignSettingsIn, CampaignStatusIn
from ..security import require_admin
from ..services import audit
from ..services import campaigns as campaign_svc
from ..services.payments import request_cancellation, sync_payment
from ..validators import format_phone, only_digits

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _current_campaign(db: Session) -> Campaign:
    c = campaign_svc.get_active_campaign(db) or db.execute(
        select(Campaign).order_by(Campaign.updated_at.desc())
    ).scalars().first()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhuma campanha cadastrada")
    return c


def _order_row(o: Order) -> dict[str, Any]:
    p = o.participant
    return {
        "id": str(o.id),
        "code": o.code,
        "status": o.status,
        "numbers": [n.number for n in o.numbers],
        "quantity": o.quantity,
        "total_cents": o.total_cents,
        "created_at": o.created_at.isoformat(),
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "checkout_expires_at": o.checkout_expires_at.isoformat(),
        "cancel_requested_at": o.cancel_requested_at.isoformat() if o.cancel_requested_at else None,
        "review_reason": o.review_reason,
        "participant": {
            "id": str(p.id), "full_name": p.full_name, "email": p.email,
            "phone": format_phone(p.phone), "cpf_masked": p.cpf_masked,
        },
        "payment": _payment_row(o.payment) if o.payment else None,
    }


def _payment_row(p: Payment) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "order_id": str(p.order_id),
        "provider": p.provider,
        "provider_payment_id": p.provider_payment_id,
        "status": p.status,
        "provider_status": p.provider_status,
        "status_detail": p.status_detail,
        "amount_cents": p.amount_cents,
        "live_mode": p.live_mode,
        "created_at": p.created_at.isoformat(),
        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
        "expires_at": p.expires_at.isoformat() if p.expires_at else None,
    }


def _search_filter(db: Session, campaign: Campaign, q: str):
    q = q.strip()
    if not q:
        return None
    digits = only_digits(q)
    conds = []
    if q.isdigit():
        # Busca numérica: número da rifa (exato) ou trecho do telefone
        if int(q) <= campaign.total_numbers:
            conds.append(Order.id.in_(select(OrderNumber.order_id).where(OrderNumber.number == int(q))))
        if len(q) >= 4:
            conds.append(Participant.phone.like(f"%{q}%"))
        return or_(*conds) if conds else Order.id.is_(None)
    like = f"%{q.lower()}%"
    conds = [
        func.lower(Participant.full_name).like(like),
        func.lower(Participant.email).like(like),
        func.lower(Order.code).like(like),
    ]
    if len(digits) >= 4 and not any(c.isalpha() for c in q):
        conds.append(Participant.phone.like(f"%{digits}%"))  # ex.: "(81) 98001"
    try:
        conds.append(Order.id == uuid.UUID(q))
    except ValueError:
        pass
    return or_(*conds)


@router.get("/me")
def me(admin: AdminUser = Depends(require_admin)) -> dict:
    return {"id": str(admin.id), "email": admin.email, "name": admin.name}


@router.get("/overview")
def overview(admin: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    c = _current_campaign(db)
    counts = campaign_svc.counts(db, c.id)
    gross = db.execute(
        select(func.coalesce(func.sum(Order.total_cents), 0)).where(Order.campaign_id == c.id,
                                                                     Order.status == "paid")
    ).scalar_one()
    by_status = dict(db.execute(
        select(Order.status, func.count()).where(Order.campaign_id == c.id).group_by(Order.status)
    ).all())
    pending_payments = db.execute(
        select(func.count()).select_from(Payment).join(Order).where(
            Order.campaign_id == c.id, Payment.status.in_(("pending", "in_review")))
    ).scalar_one()
    return {
        "campaign": {"id": str(c.id), "name": c.name, "status": c.status, "total_numbers": c.total_numbers,
                     "price_cents": c.price_cents},
        "numbers": counts,
        "gross_cents": int(gross),
        "orders_by_status": by_status,
        "pending_payments": pending_payments,
        "payment_mode": get_settings().public_payment_mode,
    }


@router.get("/orders")
def list_orders(q: str = "", status_filter: str | None = Query(default=None, alias="status"),
                page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=200),
                admin: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    c = _current_campaign(db)
    stmt = select(Order).join(Participant).where(Order.campaign_id == c.id)
    cond = _search_filter(db, c, q)
    if cond is not None:
        stmt = stmt.where(cond)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().unique().all()
    return {"total": total, "page": page, "items": [_order_row(o) for o in rows]}


@router.get("/participants")
def list_participants(q: str = "", admin: AdminUser = Depends(require_admin),
                      db: Session = Depends(get_db)) -> dict:
    """Participantes com seus números pagos e reservados."""
    c = _current_campaign(db)
    stmt = select(Order).join(Participant).where(Order.campaign_id == c.id,
                                                 Order.status.in_(("paid", "pending", "in_review")))
    cond = _search_filter(db, c, q)
    if cond is not None:
        stmt = stmt.where(cond)
    orders = db.execute(stmt.order_by(Participant.full_name)).scalars().unique().all()
    people: dict[str, dict[str, Any]] = {}
    for o in orders:
        p = o.participant
        entry = people.setdefault(str(p.id), {
            "id": str(p.id), "full_name": p.full_name, "email": p.email, "phone": format_phone(p.phone),
            "paid_numbers": [], "reserved_numbers": [], "orders": [],
        })
        key = "paid_numbers" if o.status == "paid" else "reserved_numbers"
        entry[key].extend(n.number for n in o.numbers)
        entry["orders"].append({"code": o.code, "status": o.status})
    items = sorted(people.values(), key=lambda e: e["full_name"].lower())
    for e in items:
        e["paid_numbers"].sort()
        e["reserved_numbers"].sort()
    return {"total": len(items), "items": items}


@router.get("/export.csv")
def export_csv(admin: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    c = _current_campaign(db)
    orders = db.execute(
        select(Order).where(Order.campaign_id == c.id).order_by(Order.created_at)
    ).scalars().unique().all()
    buf = io.StringIO()
    buf.write("﻿")  # BOM: abre corretamente no Excel
    w = csv.writer(buf, delimiter=";")
    w.writerow(["pedido", "status", "participante", "email", "whatsapp", "numeros", "quantidade",
                "valor_total", "criado_em_utc", "pago_em_utc", "id_pagamento", "status_pagamento"])
    for o in orders:
        p = o.participant
        w.writerow([
            o.code, o.status, p.full_name, p.email, format_phone(p.phone),
            " ".join(str(n.number) for n in o.numbers), o.quantity,
            f"{o.total_cents / 100:.2f}".replace(".", ","), o.created_at.isoformat(),
            o.paid_at.isoformat() if o.paid_at else "",
            o.payment.provider_payment_id if o.payment else "", o.payment.status if o.payment else "",
        ])
    audit.log(db, "export_csv", actor_type="admin", actor_id=str(admin.id), entity_type="campaign",
              entity_id=c.id, details={"rows": len(orders)})
    db.commit()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="participantes.csv"'})


@router.get("/payments")
def list_payments(status_filter: str | None = Query(default=None, alias="status"),
                  page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
                  admin: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    c = _current_campaign(db)
    stmt = select(Payment, Order.code).join(Order).where(Order.campaign_id == c.id)
    if status_filter:
        stmt = stmt.where(Payment.status == status_filter)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(Payment.created_at.desc()).offset((page - 1) * page_size)
                      .limit(page_size)).all()
    return {"total": total, "items": [{**_payment_row(p), "order_code": code} for p, code in rows]}


@router.post("/payments/{payment_id}/sync")
def sync(payment_id: uuid.UUID, admin: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento não encontrado")
    audit.log(db, "payment_sync_requested", actor_type="admin", actor_id=str(admin.id),
              entity_type="payment", entity_id=payment.provider_payment_id)
    db.commit()
    try:
        sync_payment(db, payment, actor_type="admin", actor_id=str(admin.id))
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Consulta ao provedor falhou: {exc}") from exc
    db.expire_all()
    return _payment_row(db.get(Payment, payment_id))  # type: ignore[arg-type]


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: uuid.UUID, admin: AdminUser = Depends(require_admin),
                 db: Session = Depends(get_db)) -> dict:
    """Solicita ao provedor o cancelamento de uma cobrança pendente. Números só são liberados
    após a confirmação do provedor. Não existe ação de aprovação manual."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")
    if order.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Apenas pedidos pendentes podem ser cancelados")
    order = request_cancellation(db, order_id, reason="admin", actor_type="admin", actor_id=str(admin.id))
    db.expire_all()
    return _order_row(db.get(Order, order_id))  # type: ignore[arg-type]


@router.get("/audit-logs")
def audit_logs(entity_id: str | None = None, page: int = Query(default=1, ge=1),
               admin: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    stmt = select(AuditLog)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    rows = db.execute(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * 100).limit(100)).scalars().all()
    return {"items": [{
        "id": r.id, "created_at": r.created_at.isoformat(), "actor_type": r.actor_type, "actor_id": r.actor_id,
        "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id, "details": r.details,
    } for r in rows]}


# ---- Configurações ---------------------------------------------------------

def _campaign_out(c: Campaign) -> dict[str, Any]:
    return {
        "id": str(c.id), "name": c.name, "subtitle": c.subtitle, "description": c.description,
        "prize_title": c.prize_title,
        "price_cents": c.price_cents, "total_numbers": c.total_numbers,
        "draw_date": c.draw_date.isoformat() if c.draw_date else None,
        "organizer_name": c.organizer_name, "organizer_contact": c.organizer_contact,
        "regulation_text": c.regulation_text, "authorization_info": c.authorization_info,
        "header_image_url": c.header_image_url, "status": c.status,
        "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat(),
    }


@router.get("/campaigns")
def list_campaigns(admin: AdminUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(Campaign).order_by(Campaign.created_at.desc())).scalars().all()
    return {"items": [_campaign_out(c) for c in rows]}


@router.post("/campaigns", status_code=status.HTTP_201_CREATED)
def create_campaign(body: CampaignSettingsIn, admin: AdminUser = Depends(require_admin),
                    db: Session = Depends(get_db)) -> dict:
    c = Campaign(status="draft", **body.model_dump())
    db.add(c)
    db.flush()
    campaign_svc.create_numbers(db, c.id, 1, body.total_numbers)
    audit.log(db, "campaign_created", actor_type="admin", actor_id=str(admin.id), entity_type="campaign",
              entity_id=c.id, details=body.model_dump(mode="json", exclude={"regulation_text"}))
    db.commit()
    return _campaign_out(c)


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: uuid.UUID, body: CampaignSettingsIn, admin: AdminUser = Depends(require_admin),
                    db: Session = Depends(get_db)) -> dict:
    c = db.execute(select(Campaign).where(Campaign.id == campaign_id).with_for_update()).scalar_one_or_none()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campanha não encontrada")
    data = body.model_dump()
    has_orders = db.execute(select(func.count()).select_from(Order).where(Order.campaign_id == c.id)).scalar_one()
    if has_orders and data["price_cents"] != c.price_cents:
        raise HTTPException(status.HTTP_409_CONFLICT, "O preço não pode ser alterado após o primeiro pedido.")
    before = _campaign_out(c)
    campaign_svc.resize_numbers(db, c, data.pop("total_numbers"))
    for k, v in data.items():
        setattr(c, k, v)
    changed = {k: v for k, v in _campaign_out(c).items() if before.get(k) != v and k != "updated_at"}
    changed.pop("regulation_text", None)
    audit.log(db, "campaign_updated", actor_type="admin", actor_id=str(admin.id), entity_type="campaign",
              entity_id=c.id, details={"changed": list(changed.keys())})
    db.commit()
    return _campaign_out(c)


@router.post("/campaigns/{campaign_id}/status")
def set_campaign_status(campaign_id: uuid.UUID, body: CampaignStatusIn, admin: AdminUser = Depends(require_admin),
                        db: Session = Depends(get_db)) -> dict:
    c = db.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campanha não encontrada")
    if body.status == "active" and get_settings().is_live and not c.authorization_info.strip():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Informe os dados de autorização antes de ativar com cobranças reais.")
    old = c.status
    c.status = body.status
    try:
        audit.log(db, "campaign_status_changed", actor_type="admin", actor_id=str(admin.id),
                  entity_type="campaign", entity_id=c.id, details={"from": old, "to": body.status})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe outra campanha ativa. Encerre-a antes.") from None
    return _campaign_out(c)
