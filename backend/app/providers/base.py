from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class ProviderError(Exception):
    """Falha de comunicação ou resposta inesperada do provedor de pagamentos."""

    def __init__(self, message: str, *, status_code: int | None = None, retriable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retriable = retriable


@dataclass
class PayerInfo:
    full_name: str
    email: str
    cpf: str | None  # apenas dígitos; nunca persistido


@dataclass
class CreatePixRequest:
    external_reference: str
    amount_cents: int
    description: str
    expires_at: datetime
    idempotency_key: str
    payer: PayerInfo
    notification_url: str | None


@dataclass
class ProviderPayment:
    id: str
    status: str          # status bruto do provedor (padrão Mercado Pago)
    status_detail: str
    amount_cents: int
    external_reference: str
    live_mode: bool
    qr_code: str = ""
    qr_code_base64: str = ""
    ticket_url: str = ""
    expires_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(Protocol):
    name: str

    def create_pix(self, req: CreatePixRequest) -> ProviderPayment: ...

    def get_payment(self, payment_id: str) -> ProviderPayment: ...

    def cancel_payment(self, payment_id: str) -> ProviderPayment: ...

    def find_by_reference(self, external_reference: str) -> ProviderPayment | None: ...
