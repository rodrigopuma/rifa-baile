"""Conciliação de pagamentos.

Roda em segundo plano dentro da API (RUN_BACKGROUND_RECONCILER=true) e também pode ser
executada por cron/agendador externo:  python -m app.worker --once
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from fastapi.concurrency import run_in_threadpool

from .config import get_settings
from .db import new_session
from .services.payments import reconcile_once

log = logging.getLogger("rifa.worker")


def run_once() -> dict[str, int]:
    with new_session() as db:
        return reconcile_once(db)


async def loop_forever(stop: asyncio.Event) -> None:
    interval = get_settings().reconcile_interval_seconds
    while not stop.is_set():
        try:
            stats = await run_in_threadpool(run_once)
            if any(stats.values()):
                log.info("Conciliação: %s", stats)
        except Exception:  # noqa: BLE001
            log.exception("Falha na rodada de conciliação")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        print(run_once())
    else:
        asyncio.run(loop_forever(asyncio.Event()))


if __name__ == "__main__":
    main()
