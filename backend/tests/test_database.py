"""Verificações específicas do PostgreSQL/Supabase (executadas com TEST_DATABASE_URL)."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import get_engine, new_session

from .conftest import place

pytestmark = pytest.mark.skipif(
    not __import__("os").environ.get("TEST_DATABASE_URL"), reason="requer PostgreSQL (TEST_DATABASE_URL)"
)


def test_public_availability_table_follows_numbers(client, campaign):
    created = place(client, [5, 6]).json()
    with get_engine().connect() as c:
        rows = dict(c.execute(text("select number, available from number_availability "
                                   "where campaign_id = :c and number in (5, 6, 7)"), {"c": campaign.id}).all())
    assert rows == {5: False, 6: False, 7: True}
    client.post(f"/api/dev/simulator/payments/{created['order']['simulator_payment_id']}/reject")
    with get_engine().connect() as c:
        avail = c.execute(text("select bool_and(available) from number_availability "
                               "where campaign_id = :c and number in (5, 6)"), {"c": campaign.id}).scalar()
    assert avail is True


def test_anon_role_cannot_read_personal_data(client, campaign):
    place(client, [9])
    with get_engine().connect() as c:
        c.execute(text("set role anon"))
        assert c.execute(text("select count(*) from number_availability")).scalar() == 100
        with pytest.raises(Exception):
            c.execute(text("select * from participants"))
        c.rollback()


def test_db_rejects_number_in_two_active_orders(client, campaign):
    place(client, [11])
    with new_session() as db:
        num_id, order_id = db.execute(text(
            "select n.id, o.id from numbers n join order_numbers o2 on o2.number_id = n.id "
            "join orders o on o.id = o2.order_id where n.number = 11")).one()
        db.execute(text("update order_numbers set active = true"))
        with pytest.raises(IntegrityError):
            other = place(client, [12]).json()["order"]["id"]
            db.execute(text("insert into order_numbers (order_id, number_id, number, active) "
                            "values (:o, :n, 11, true)"), {"o": other, "n": num_id})
            db.flush()
        db.rollback()


def test_only_one_active_campaign_constraint(campaign):
    with get_engine().connect() as c:
        with pytest.raises(IntegrityError):
            c.execute(text("insert into campaigns (name, price_cents, total_numbers, status) "
                           "values ('X', 100, 10, 'active')"))
