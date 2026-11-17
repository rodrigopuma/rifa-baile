"""Aviso no celular quando entra uma reserva (ntfy.sh). Nunca atrapalha a reserva: falhas só vão para o log."""
from __future__ import annotations

import logging
import threading

import httpx

from ..config import get_settings
from ..models import Order
from .campaign_config import brl

log = logging.getLogger("rifa.notify")


def build_payload(order: Order, numbers: list[int], width: int) -> dict:
    s = get_settings()
    nums = ", ".join(str(n).zfill(width) for n in sorted(numbers))
    qtd = len(numbers)
    return {
        "topic": s.ntfy_topic,
        "title": f"Nova reserva · {brl(order.total_cents)}",
        # sem telefone/CPF: o aviso passa por um serviço externo; o contato fica só no painel
        "message": f"{order.participant.full_name} reservou {qtd} {'número' if qtd == 1 else 'números'}: {nums}\nPedido {order.code}",
        "tags": ["tickets"],
        "priority": 4,
        "click": f"{s.frontend_url.rstrip('/')}/admin?q={order.code}",
    }


def _send(server: str, payload: dict) -> None:
    try:
        r = httpx.post(server.rstrip("/") + "/", json=payload, timeout=5.0)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - aviso é opcional
        log.warning("Falha ao enviar notificação ntfy: %s", exc)


def notify_new_reservation(order: Order, numbers: list[int], width: int) -> None:
    """Dispara em segundo plano; sem NTFY_TOPIC não faz nada."""
    s = get_settings()
    if not s.ntfy_topic:
        return
    try:
        payload = build_payload(order, numbers, width)
    except Exception as exc:  # noqa: BLE001
        log.warning("Notificação ignorada: %s", exc)
        return
    threading.Thread(target=_send, args=(s.ntfy_server, payload), daemon=True).start()
