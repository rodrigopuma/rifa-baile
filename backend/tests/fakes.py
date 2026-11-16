"""Provedor falso com o mesmo contrato do Mercado Pago, para testes controlados."""
from __future__ import annotations

import itertools
import threading
from dataclasses import replace

from app.providers.base import CreatePixRequest, ProviderError, ProviderPayment


class FakeMercadoPago:
    name = "mercadopago"

    def __init__(self):
        self.payments: dict[str, ProviderPayment] = {}
        self.by_key: dict[str, str] = {}
        self._ids = itertools.count(9_000_000_001)
        self._lock = threading.Lock()
        self.create_calls = 0
        self.cancel_calls = 0
        # Comportamentos configuráveis
        self.fail_create: ProviderError | None = None
        self.create_but_lose_response = False   # cria no provedor, mas "perde" a resposta (timeout)
        self.cancel_unsupported = False
        self.live_mode = False
        self.amount_override: int | None = None

    def create_pix(self, req: CreatePixRequest) -> ProviderPayment:
        with self._lock:
            self.create_calls += 1
            if self.fail_create and not self.create_but_lose_response:
                raise self.fail_create
            if req.idempotency_key in self.by_key:
                return self.payments[self.by_key[req.idempotency_key]]
            pid = str(next(self._ids))
            pp = ProviderPayment(
                id=pid, status="pending", status_detail="pending_waiting_transfer",
                amount_cents=self.amount_override or req.amount_cents, external_reference=req.external_reference,
                live_mode=self.live_mode, qr_code=f"000201FAKE{pid}", qr_code_base64="iVBORw0KGgo=",
                ticket_url=f"https://example.test/{pid}", expires_at=req.expires_at,
            )
            self.payments[pid] = pp
            self.by_key[req.idempotency_key] = pid
            if self.create_but_lose_response:
                raise ProviderError("timeout simulado")
            return pp

    def get_payment(self, payment_id: str) -> ProviderPayment:
        if payment_id not in self.payments:
            raise ProviderError("not found", status_code=404, retriable=False)
        return self.payments[payment_id]

    def cancel_payment(self, payment_id: str) -> ProviderPayment:
        self.cancel_calls += 1
        pp = self.get_payment(payment_id)
        if self.cancel_unsupported:
            raise ProviderError("cancelamento indisponível", status_code=400, retriable=False)
        if pp.status != "pending":
            raise ProviderError("status inválido para cancelamento", status_code=400, retriable=False)
        return self.set(payment_id, "cancelled", "by_collector")

    def find_by_reference(self, external_reference: str) -> ProviderPayment | None:
        for pp in self.payments.values():
            if pp.external_reference == external_reference:
                return pp
        return None

    # utilitário dos testes: muda o estado "no provedor"
    def set(self, payment_id: str, status: str, detail: str = "") -> ProviderPayment:
        pp = replace(self.payments[payment_id], status=status, status_detail=detail)
        self.payments[payment_id] = pp
        return pp
