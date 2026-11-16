"""Infraestrutura de testes.

Por padrão os testes usam SQLite em arquivo temporário. Para rodar contra PostgreSQL
(aplicando as migrations reais do Supabase), defina:
    TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/rifa_test
"""
from __future__ import annotations

import os
import tempfile
import time
import uuid
from datetime import timedelta
from pathlib import Path

import jwt
import pytest

_tmpdir = tempfile.mkdtemp(prefix="rifa-tests-")
PG_URL = os.environ.get("TEST_DATABASE_URL", "")
os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": PG_URL or f"sqlite:///{_tmpdir}/test.db",
    "PAYMENT_MODE": "simulator",
    "SUPABASE_JWT_SECRET": "test-secret-0123456789-0123456789-abcdef",
    "RUN_BACKGROUND_RECONCILER": "false",
    "AUTO_APPLY_CAMPAIGN_CONFIG": "false",
    "MAX_PENDING_ORDERS_PER_CONTACT": "2",
    "ORDER_RATE_LIMIT_PER_10MIN": "1000",
    "PAYER_CPF_REQUIRED": "true",
})

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import db as dbmod  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, new_session, utcnow  # noqa: E402
from app.models import AdminUser, Campaign, Order  # noqa: E402
from app.providers import set_provider  # noqa: E402
from app.services.campaigns import create_numbers  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
VALID_CPFS = ["52998224725", "11144477735", "39053344705", "15350946056", "29141777638",
              "86288366757", "71428793860", "31706690797"]


def _reset_postgres(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("drop schema if exists public cascade; create schema public;"))
        conn.execute(text("drop schema if exists auth cascade; create schema auth;"))
        conn.execute(text("create table auth.users (id uuid primary key)"))
        for role in ("anon", "authenticated"):
            conn.execute(text(f"do $$ begin if not exists (select 1 from pg_roles where rolname='{role}') "
                              f"then create role {role}; end if; end $$;"))
        # Padrões do Supabase: anon/authenticated têm USAGE no schema public
        conn.execute(text("grant usage on schema public to anon, authenticated"))
        for f in sorted(MIGRATIONS.glob("*.sql")):
            conn.exec_driver_sql(f.read_text())
        # admin_users.id referencia auth.users: em testes removemos a FK para simplificar.
        conn.execute(text("alter table public.admin_users drop constraint if exists admin_users_id_fkey"))


@pytest.fixture(autouse=True)
def fresh_db():
    engine = dbmod.init_engine(os.environ["DATABASE_URL"])
    if engine.dialect.name == "postgresql":
        _reset_postgres(engine)
    else:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    set_provider(None)
    s = get_settings()
    snapshot = s.model_dump()
    from app.routers.public import lookup_limiter, order_limiter

    order_limiter.reset()
    lookup_limiter.reset()
    yield engine
    for k, v in snapshot.items():
        setattr(s, k, v)
    set_provider(None)


@pytest.fixture
def campaign(fresh_db) -> Campaign:
    with new_session() as db:
        c = Campaign(name="Rifa Solidária", subtitle="Formatura", price_cents=1000, total_numbers=100,
                     status="active", regulation_text="Regulamento", organizer_name="Rodrigo")
        db.add(c)
        db.flush()
        create_numbers(db, c.id, 1, 100)
        db.commit()
        return c


@pytest.fixture
def client(campaign) -> TestClient:
    from app.main import app

    return TestClient(app)


_counter = {"n": 0}


def buyer(i: int | None = None) -> dict:
    if i is None:
        _counter["n"] += 1
        i = _counter["n"]
    return {
        "full_name": f"Participante Teste {i}",
        "email": f"p{i}@exemplo.com",
        "phone": f"(81) 9{8000 + i:04d}-{1000 + i:04d}",
        "cpf": VALID_CPFS[i % len(VALID_CPFS)],
        "privacy_consent": True,
    }


def place(client: TestClient, numbers: list[int], i: int | None = None, **extra):
    return client.post("/api/orders", json={"numbers": numbers, **buyer(i), **extra})


def admin_token(fresh_db, *, register: bool = True, email: str = "admin@exemplo.com") -> str:
    uid = uuid.uuid4()
    if register:
        with new_session() as db:
            db.add(AdminUser(id=uid, email=email, name="Admin"))
            db.commit()
    now = int(time.time())
    return jwt.encode({"sub": str(uid), "aud": "authenticated", "iat": now, "exp": now + 3600},
                      get_settings().supabase_jwt_secret, algorithm="HS256")


def expire_checkout(order_id: str, *, also_pix: bool = False) -> None:
    """Simula a passagem do tempo movendo os prazos para o passado."""
    with new_session() as db:
        o = db.get(Order, uuid.UUID(order_id))
        o.checkout_expires_at = utcnow() - timedelta(seconds=1)
        if also_pix:
            o.payment_expires_at = utcnow() - timedelta(seconds=1)
            from app.models import SimulatedPayment

            if o.payment:
                sp = db.get(SimulatedPayment, o.payment.provider_payment_id)
                if sp:
                    sp.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()


def number_statuses(campaign_id, numbers: list[int]) -> dict[int, str]:
    from sqlalchemy import select

    from app.models import RaffleNumber

    with new_session() as db:
        rows = db.execute(select(RaffleNumber.number, RaffleNumber.status).where(
            RaffleNumber.campaign_id == campaign_id, RaffleNumber.number.in_(numbers))).all()
        return dict(rows)
