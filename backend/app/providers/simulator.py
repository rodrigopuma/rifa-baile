"""Simulador LOCAL de Pix — claramente identificado e bloqueado em produção.

Imita o comportamento relevante do Mercado Pago: cobrança 'pending', aprovação,
cancelamento de cobrança pendente, expiração (status 'cancelled' + detail 'expired')
e estorno. O estado do "lado do provedor" fica na tabela dev_simulated_payments.
Nenhum dinheiro real circula e o QR Code gerado NÃO é um código Pix válido.
"""
from __future__ import annotations

import base64
import io
import secrets
from datetime import datetime

import qrcode

from ..db import new_session, utcnow
from ..models import SimulatedPayment
from .base import CreatePixRequest, ProviderError, ProviderPayment


def _qr_png_base64(payload: str) -> str:
    img = qrcode.make(payload, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class SimulatorProvider:
    name = "simulator"

    def _to_payment(self, sp: SimulatedPayment, with_qr: bool = False) -> ProviderPayment:
        payload = f"SIMULADOR-PIX-SEM-VALOR|ref={sp.external_reference}|id={sp.id}|centavos={sp.amount_cents}"
        return ProviderPayment(
            id=sp.id,
            status=sp.status,
            status_detail=sp.status_detail,
            amount_cents=sp.amount_cents,
            external_reference=sp.external_reference,
            live_mode=False,
            qr_code=payload if with_qr else "",
            qr_code_base64=_qr_png_base64(payload) if with_qr else "",
            ticket_url="",
            expires_at=sp.expires_at,
            raw={"simulator": True, "id": sp.id, "status": sp.status, "status_detail": sp.status_detail},
        )

    def _lazy_expire(self, sp: SimulatedPayment, now: datetime) -> None:
        if sp.status == "pending" and sp.expires_at <= now:
            sp.status, sp.status_detail = "cancelled", "expired"

    def create_pix(self, req: CreatePixRequest) -> ProviderPayment:
        with new_session() as s:
            existing = s.query(SimulatedPayment).filter_by(external_reference=req.external_reference).first()
            if existing:  # idempotência por referência
                return self._to_payment(existing, with_qr=True)
            sp = SimulatedPayment(
                id=f"SIM{secrets.randbelow(10**12):012d}",
                external_reference=req.external_reference,
                amount_cents=req.amount_cents,
                expires_at=req.expires_at,
            )
            s.add(sp)
            s.commit()
            return self._to_payment(sp, with_qr=True)

    def get_payment(self, payment_id: str) -> ProviderPayment:
        with new_session() as s:
            sp = s.get(SimulatedPayment, payment_id)
            if not sp:
                raise ProviderError("Pagamento simulado não encontrado", status_code=404, retriable=False)
            self._lazy_expire(sp, utcnow())
            s.commit()
            return self._to_payment(sp)

    def cancel_payment(self, payment_id: str) -> ProviderPayment:
        with new_session() as s:
            sp = s.get(SimulatedPayment, payment_id)
            if not sp:
                raise ProviderError("Pagamento simulado não encontrado", status_code=404, retriable=False)
            self._lazy_expire(sp, utcnow())
            if sp.status != "pending":
                raise ProviderError(f"Não é possível cancelar pagamento em '{sp.status}'",
                                    status_code=400, retriable=False)
            sp.status, sp.status_detail = "cancelled", "by_collector"
            s.commit()
            return self._to_payment(sp)

    def find_by_reference(self, external_reference: str) -> ProviderPayment | None:
        with new_session() as s:
            sp = s.query(SimulatedPayment).filter_by(external_reference=external_reference).first()
            return self._to_payment(sp) if sp else None

    # ---- Ações exclusivas do simulador ------------------------------------
    def simulate(self, payment_id: str, action: str) -> ProviderPayment:
        transitions = {
            "approve": ({"pending"}, ("approved", "accredited")),
            "reject": ({"pending"}, ("rejected", "cc_rejected_other_reason")),
            "expire": ({"pending"}, ("cancelled", "expired")),
            "refund": ({"approved"}, ("refunded", "refunded")),
        }
        if action not in transitions:
            raise ProviderError("Ação inválida", status_code=400, retriable=False)
        allowed, (status, detail) = transitions[action]
        with new_session() as s:
            sp = s.get(SimulatedPayment, payment_id)
            if not sp:
                raise ProviderError("Pagamento simulado não encontrado", status_code=404, retriable=False)
            # Aprovar após o prazo visual de 15 min é permitido (Pix ainda vale até o vencimento
            # de 30 min no MP): reproduz o cenário de "pagamento tardio".
            self._lazy_expire(sp, utcnow())
            if sp.status not in allowed:
                raise ProviderError(f"Transição inválida a partir de '{sp.status}'", status_code=409,
                                    retriable=False)
            sp.status, sp.status_detail = status, detail
            s.commit()
            return self._to_payment(sp)
