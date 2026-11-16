"""Concorrência: o mesmo número jamais pode ser reservado/vendido duas vezes."""
from __future__ import annotations

import random
import threading
from collections import Counter

from fastapi import HTTPException
from sqlalchemy import select

from app.db import new_session
from app.models import OrderNumber, RaffleNumber
from app.services.orders import create_order

from .conftest import VALID_CPFS


def _attempt(i: int, numbers: list[int], results: list, barrier: threading.Barrier) -> None:
    barrier.wait()
    with new_session() as db:
        try:
            order, _ = create_order(db, numbers=numbers, full_name=f"Pessoa Concorrente {i}",
                                    email=f"c{i}@exemplo.com", phone=f"819{i:08d}", cpf=VALID_CPFS[i % 8])
            results.append(("ok", sorted(n.number for n in order.numbers)))
        except HTTPException as exc:
            results.append((exc.status_code, numbers))


def test_concurrent_overlapping_orders(campaign):
    rng = random.Random(42)
    workers = 16
    wanted = [sorted(rng.sample(range(1, 21), 4)) for _ in range(workers)]
    wanted[0] = wanted[1] = [5, 6, 7]  # disputa direta pelo mesmo conjunto
    results: list = []
    barrier = threading.Barrier(workers)
    threads = [threading.Thread(target=_attempt, args=(i, wanted[i], results, barrier)) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == workers
    assert all(r[0] in ("ok", 409, 503) for r in results), results
    won = [n for status, nums in results if status == "ok" for n in nums]
    assert len(won) == len(set(won)), "número reservado em dois pedidos!"
    assert sum(1 for s, n in results if s == "ok" and n == [5, 6, 7]) <= 1

    with new_session() as db:
        reserved = db.execute(select(RaffleNumber.number).where(RaffleNumber.status == "reserved")).scalars().all()
        assert sorted(reserved) == sorted(won)
        active = db.execute(select(OrderNumber.number).where(OrderNumber.active.is_(True))).scalars().all()
        assert Counter(active) == Counter(won)


def test_same_number_many_buyers(campaign):
    workers = 12
    results: list = []
    barrier = threading.Barrier(workers)
    threads = [threading.Thread(target=_attempt, args=(100 + i, [42], results, barrier)) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for s, _ in results if s == "ok") == 1
