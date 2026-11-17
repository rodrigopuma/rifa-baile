"""Preço do pedido. Sempre calculado no servidor (valores vindos do navegador são ignorados)."""
from __future__ import annotations


def order_total_cents(price_cents: int, bundle_size: int, bundle_price_cents: int, quantity: int) -> int:
    """A cada `bundle_size` números do pedido, o grupo custa `bundle_price_cents`; o que sobrar de
    um grupo completo é cobrado ao preço normal. Ex.: 3 por R$ 25 com número a R$ 10:
    3 → 25, 4 → 35, 5 → 45, 6 → 50."""
    if bundle_size >= 2 and bundle_price_cents > 0:
        groups, rest = divmod(quantity, bundle_size)
        return groups * bundle_price_cents + rest * price_cents
    return quantity * price_cents
