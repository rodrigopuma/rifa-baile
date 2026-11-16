from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from ..models import Campaign, OrderNumber, RaffleNumber


def get_active_campaign(db: Session) -> Campaign | None:
    return db.execute(select(Campaign).where(Campaign.status == "active")).scalar_one_or_none()


def get_public_campaign(db: Session) -> Campaign | None:
    """Campanha exibida no site: a ativa ou, na falta dela, a pausada/encerrada mais recente."""
    c = get_active_campaign(db)
    if c:
        return c
    return db.execute(
        select(Campaign).where(Campaign.status.in_(("paused", "closed"))).order_by(Campaign.updated_at.desc())
    ).scalars().first()


def create_numbers(db: Session, campaign_id: uuid.UUID, start: int, end: int) -> None:
    if end < start:
        return
    db.execute(insert(RaffleNumber), [
        {"campaign_id": campaign_id, "number": n, "status": "available"} for n in range(start, end + 1)
    ])


def resize_numbers(db: Session, campaign: Campaign, new_total: int) -> None:
    current = campaign.total_numbers
    if new_total == current:
        return
    if new_total > current:
        create_numbers(db, campaign.id, current + 1, new_total)
    else:
        busy = db.execute(
            select(func.count()).select_from(RaffleNumber).where(
                RaffleNumber.campaign_id == campaign.id, RaffleNumber.number > new_total,
                RaffleNumber.status != "available",
            )
        ).scalar_one()
        if busy:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Não é possível reduzir: há números reservados ou pagos acima do novo total.")
        used = db.execute(
            select(func.count()).select_from(RaffleNumber).where(
                RaffleNumber.campaign_id == campaign.id, RaffleNumber.number > new_total,
            ).where(RaffleNumber.id.in_(select(OrderNumber.number_id)))
        ).scalar_one()
        if used:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Não é possível reduzir: há histórico de pedidos para números acima do novo total.")
        db.execute(delete(RaffleNumber).where(RaffleNumber.campaign_id == campaign.id,
                                              RaffleNumber.number > new_total))
    campaign.total_numbers = new_total


def counts(db: Session, campaign_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(RaffleNumber.status, func.count()).where(RaffleNumber.campaign_id == campaign_id)
        .group_by(RaffleNumber.status)
    ).all()
    out = {"available": 0, "reserved": 0, "paid": 0}
    out.update({k: v for k, v in rows})
    return out


def unavailable_numbers(db: Session, campaign_id: uuid.UUID) -> list[int]:
    return list(db.execute(
        select(RaffleNumber.number).where(RaffleNumber.campaign_id == campaign_id,
                                          RaffleNumber.status != "available").order_by(RaffleNumber.number)
    ).scalars())
