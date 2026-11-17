"""Provedor 'manual': não existe cobrança automática. O pagamento é feito direto na chave Pix
do organizador e confirmado por ele no painel (ver services/manual.py). Este objeto só existe
para que nenhum código chame, por engano, o Mercado Pago ou o simulador neste modo."""
from __future__ import annotations

from .base import CreatePixRequest, ProviderError, ProviderPayment


class ManualProvider:
    name = "manual"

    def _no(self) -> ProviderError:
        return ProviderError("Modo manual: não há provedor de pagamento para consultar.",
                             status_code=400, retriable=False)

    def create_pix(self, req: CreatePixRequest) -> ProviderPayment:
        raise self._no()

    def get_payment(self, payment_id: str) -> ProviderPayment:
        raise self._no()

    def cancel_payment(self, payment_id: str) -> ProviderPayment:
        raise self._no()

    def find_by_reference(self, external_reference: str) -> ProviderPayment | None:
        return None
