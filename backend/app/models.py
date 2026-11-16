"""Modelos ORM. O esquema autoritativo para o Supabase está em supabase/migrations/*.sql;
estes modelos o espelham (e são usados para criar o banco em testes/SQLite)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow

JSONType = JSON().with_variant(JSONB(), "postgresql")
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")  # autoincrement no SQLite

# ---- Estados -------------------------------------------------------------
CAMPAIGN_STATUSES = ("draft", "active", "paused", "closed")
NUMBER_STATUSES = ("available", "reserved", "paid")
ORDER_STATUSES = ("pending", "paid", "cancelled", "expired", "refunded", "in_review")
PAYMENT_STATUSES = ("pending", "approved", "cancelled", "expired", "refunded", "in_review", "rejected")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(_in("status", CAMPAIGN_STATUSES), name="ck_campaigns_status"),
        CheckConstraint("price_cents > 0", name="ck_campaigns_price"),
        CheckConstraint("total_numbers > 0 AND total_numbers <= 100000", name="ck_campaigns_total"),
        # Apenas uma campanha ativa por vez
        Index(
            "uq_campaigns_one_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    subtitle: Mapped[str] = mapped_column(String(240), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    prize_title: Mapped[str] = mapped_column(String(200), default="")
    price_cents: Mapped[int] = mapped_column(Integer)
    total_numbers: Mapped[int] = mapped_column(Integer)
    draw_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    organizer_name: Mapped[str] = mapped_column(String(200), default="")
    organizer_contact: Mapped[str] = mapped_column(String(200), default="")
    regulation_text: Mapped[str] = mapped_column(Text, default="")
    authorization_info: Mapped[str] = mapped_column(Text, default="")
    header_image_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class RaffleNumber(Base):
    __tablename__ = "numbers"
    __table_args__ = (
        UniqueConstraint("campaign_id", "number", name="uq_numbers_campaign_number"),
        CheckConstraint(_in("status", NUMBER_STATUSES), name="ck_numbers_status"),
        CheckConstraint(
            "(status = 'available' AND order_id IS NULL) OR (status <> 'available' AND order_id IS NOT NULL)",
            name="ck_numbers_order_consistency",
        ),
        Index("ix_numbers_campaign_status", "campaign_id", "status"),
        Index("ix_numbers_order", "order_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="available")
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (Index("ix_participants_email_phone", "email", "phone"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(20))  # somente dígitos, com DDD
    cpf_masked: Mapped[str] = mapped_column(String(20), default="")  # CPF completo NÃO é armazenado
    privacy_accepted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(_in("status", ORDER_STATUSES), name="ck_orders_status"),
        CheckConstraint("total_cents = unit_price_cents * quantity", name="ck_orders_total"),
        Index("ix_orders_status_checkout", "status", "checkout_expires_at"),
        Index("ix_orders_participant", "participant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(16), unique=True)  # código legível, ex.: RF-7K3Q9P
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"))
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    total_cents: Mapped[int] = mapped_column(Integer)
    access_token_hash: Mapped[str] = mapped_column(String(64))
    checkout_expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    payment_expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    review_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    participant: Mapped[Participant] = relationship(lazy="joined")
    campaign: Mapped[Campaign] = relationship()
    numbers: Mapped[list["OrderNumber"]] = relationship(
        back_populates="order", order_by="OrderNumber.number", lazy="selectin"
    )
    payment: Mapped["Payment | None"] = relationship(back_populates="order", uselist=False, lazy="selectin")


class OrderNumber(Base):
    __tablename__ = "order_numbers"
    __table_args__ = (
        # Segunda linha de defesa: um número só pode pertencer a UM pedido ativo.
        Index(
            "uq_order_numbers_active_number",
            "number_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active = 1"),
        ),
        UniqueConstraint("order_id", "number_id", name="uq_order_numbers_order_number"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    number_id: Mapped[int] = mapped_column(ForeignKey("numbers.id"))
    number: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    order: Mapped[Order] = relationship(back_populates="numbers")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(_in("status", PAYMENT_STATUSES), name="ck_payments_status"),
        UniqueConstraint("provider", "provider_payment_id", name="uq_payments_provider_id"),
        Index("ix_payments_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Uma cobrança por pedido: evita cobranças duplicadas.
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_payment_id: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    provider_status: Mapped[str] = mapped_column(String(32), default="")
    status_detail: Mapped[str] = mapped_column(String(64), default="")
    amount_cents: Mapped[int] = mapped_column(Integer)
    live_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    qr_code: Mapped[str] = mapped_column(Text, default="")
    qr_code_base64: Mapped[str] = mapped_column(Text, default="")
    ticket_url: Mapped[str] = mapped_column(String(500), default="")
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    raw_last: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    order: Mapped[Order] = relationship(back_populates="payment")


class AdminUser(Base):
    __tablename__ = "admin_users"

    # Mesmo UUID do usuário em auth.users (Supabase Auth)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(String(16))  # system | admin | webhook | participant
    actor_id: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class WebhookEvent(Base):
    """Registro de notificações recebidas (deduplicação por x-request-id)."""

    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "request_id", name="uq_webhook_events_request"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(20))
    request_id: Mapped[str] = mapped_column(String(100))
    topic: Mapped[str] = mapped_column(String(40), default="")
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class SimulatedPayment(Base):
    """Estado do 'lado do provedor' quando PAYMENT_MODE=simulator. Nunca usado com Mercado Pago."""

    __tablename__ = "dev_simulated_payments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_reference: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    status_detail: Mapped[str] = mapped_column(String(64), default="pending_waiting_transfer")
    amount_cents: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
