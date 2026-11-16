"""Aplica o campanha.json (e o REGULAMENTO.md) ao banco imediatamente.

Uso:  python -m scripts.aplicar_campanha            # aplica mesmo sem alterações
      python -m scripts.aplicar_campanha --ver      # só mostra o regulamento gerado
"""
from __future__ import annotations

import argparse

from app.config import get_settings
from app.db import Base, get_engine, new_session
from app.services.campaign_config import CampaignConfigError, apply_from_file, load


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", action="store_true", help="mostra o regulamento gerado e sai")
    args = ap.parse_args()
    if args.ver:
        _, reg, _ = load()
        print(reg)
        return
    if get_settings().database_url.startswith("sqlite"):
        Base.metadata.create_all(get_engine())
    with new_session() as db:
        try:
            result = apply_from_file(db, force=True)
        except CampaignConfigError as exc:
            raise SystemExit(f"Erro: {exc}") from None
    print("Campanha aplicada:", result)


if __name__ == "__main__":
    main()
