from __future__ import annotations

from ..config import get_settings
from .base import PaymentProvider

_provider: PaymentProvider | None = None


def get_provider() -> PaymentProvider:
    global _provider
    if _provider is None:
        s = get_settings()
        if s.payment_mode == "simulator":
            from .simulator import SimulatorProvider

            _provider = SimulatorProvider()
        elif s.payment_mode == "manual_pix":
            from .manual import ManualProvider

            _provider = ManualProvider()
        else:
            from .mercadopago import MercadoPagoProvider

            _provider = MercadoPagoProvider(s.mp_access_token, s.mp_api_base)
    return _provider


def set_provider(provider: PaymentProvider | None) -> None:
    """Usado em testes para injetar um provedor falso."""
    global _provider
    _provider = provider
