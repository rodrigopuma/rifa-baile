"""Reserva atômica de números.

Estratégia (válida para PostgreSQL e SQLite):
1. No PostgreSQL, bloqueia as linhas pedidas em ordem crescente (SELECT ... FOR UPDATE),
   evitando deadlocks entre pedidos com números sobrepostos.
2. Executa um UPDATE condicional (status = 'available'). Se a quantidade de linhas afetadas
   for menor que a pedida, alguém chegou antes: a transação é desfeita por inteiro.
3. A tabela order_numbers possui índice único parcial (number_id WHERE active), que impede
   que o mesmo número fique em dois pedidos ativos mesmo diante de um bug na aplicação.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import is_postgres, utcnow
from ..models import OrderNumber, RaffleNumber


class NumbersUnavailable(Exception):
    def __init__(self, numbers: list[int]):
        super().__init__(f"Números indisponíveis: {numbers}")
        self.numbers = numbers


def unavailable_among(db: Session, campaign_id: uuid.UUID, numbers: Iterable[int]) -> list[int]:
    rows = db.execute(
        select(RaffleNumber.number).where(
            RaffleNumber.campaign_id == campaign_id,
            RaffleNumber.number.in_(list(numbers)),
            RaffleNumber.status != "available",
        )
    ).scalars()
    return sorted(rows)


def reserve(db: Session, campaign_id: uuid.UUID, numbers: list[int], order_id: uuid.UUID) -> None:
    """Reserva todos os números para o pedido ou levanta NumbersUnavailable (sem reservar nenhum)."""
    wanted = sorted(set(numbers))
    if is_postgres(db):
        rows = db.execute(
            select(RaffleNumber.id, RaffleNumber.number, RaffleNumber.status)
            .where(RaffleNumber.campaign_id == campaign_id, RaffleNumber.number.in_(wanted))
            .order_by(RaffleNumber.number)
            .with_for_update()
        ).all()
        taken = [r.number for r in rows if r.status != "available"]
        if taken:
            raise NumbersUnavailable(taken)

    result = db.execute(
        update(RaffleNumber)
        .where(
            RaffleNumber.campaign_id == campaign_id,
            RaffleNumber.number.in_(wanted),
            RaffleNumber.status == "available",
        )
        .values(status="reserved", order_id=order_id, updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != len(wanted):
        raise NumbersUnavailable([])  # o chamador desfaz a transação e consulta quais

    ids = db.execute(
        select(RaffleNumber.id, RaffleNumber.number).where(
            RaffleNumber.campaign_id == campaign_id, RaffleNumber.number.in_(wanted)
        )
    ).all()
    db.add_all(OrderNumber(order_id=order_id, number_id=r.id, number=r.number, active=True) for r in ids)
    db.flush()


def release_order_numbers(db: Session, order_id: uuid.UUID, from_status: tuple[str, ...]) -> int:
    """Devolve à disponibilidade os números do pedido que estejam nos estados indicados."""
    res = db.execute(
        update(RaffleNumber)
        .where(RaffleNumber.order_id == order_id, RaffleNumber.status.in_(from_status))
        .values(status="available", order_id=None, updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    db.execute(
        update(OrderNumber)
        .where(OrderNumber.order_id == order_id, OrderNumber.active.is_(True))
        .values(active=False)
        .execution_options(synchronize_session=False)
    )
    return res.rowcount


def confirm_numbers_for_payment(db: Session, campaign_id: uuid.UUID, order_id: uuid.UUID,
                                numbers: list[int]) -> bool:
    """Marca como pagos os números do pedido. Cobre o caso normal (números reservados para o
    pedido) e o pagamento tardio (números já liberados, mas ainda livres). Só tem sucesso se
    TODOS os números estiverem livres ou vinculados a este pedido; caso contrário, nada é
    alterado pelo chamador (que usa um SAVEPOINT) e o pedido vai para análise."""
    res = db.execute(
        update(RaffleNumber)
        .where(
            RaffleNumber.campaign_id == campaign_id,
            RaffleNumber.number.in_(numbers),
            (RaffleNumber.status == "available") | (RaffleNumber.order_id == order_id),
        )
        .values(status="paid", order_id=order_id, updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if res.rowcount != len(numbers):
        return False
    db.execute(
        update(OrderNumber)
        .where(OrderNumber.order_id == order_id)
        .values(active=True)
        .execution_options(synchronize_session=False)
    )
    return True
