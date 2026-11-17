"""Arquivo único de configuração (campanha.json + REGULAMENTO.md)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.db import new_session
from app.models import Campaign, RaffleNumber
from app.services.campaign_config import CampaignConfigError, apply_from_file, draw_rule

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cfg_dir(tmp_path):
    shutil.copy(ROOT / "campanha.json", tmp_path / "campanha.json")
    shutil.copy(ROOT / "REGULAMENTO.md", tmp_path / "REGULAMENTO.md")
    return tmp_path


def _edit(path: Path, **changes):
    data = json.loads(path.read_text())
    for dotted, value in changes.items():
        sec, key = dotted.split("__")
        data[sec][key] = value
    path.write_text(json.dumps(data, ensure_ascii=False))


def test_real_config_file_creates_campaign(fresh_db, cfg_dir):
    with new_session() as db:
        r = apply_from_file(db, path=cfg_dir / "campanha.json")
        assert r["applied"] and r["created"]
        c = db.execute(select(Campaign)).scalar_one()
        assert (c.status, c.price_cents, c.total_numbers) == ("active", 1000, 200)
        assert (c.bundle_size, c.bundle_price_cents) == (3, 2500)
        # prêmio garantido + prêmio maior acima de N números vendidos (campanha.json → premio / premio_extra)
        assert c.prize_title == "R$ 150,00 garantido · R$ 250,00 se passar de 100 números vendidos"
        assert c.organizer_name == "Rodrigo"
        assert "{{" not in c.regulation_text and "resto da divisão" in c.regulation_text
        assert "R$ 10,00" in c.regulation_text and "001 a 200" in c.regulation_text
        assert "4 números = R$ 35,00" in c.regulation_text          # pacote descrito com exemplos
        assert "mais de 100 números" in c.regulation_text and "R$ 250,00" in c.regulation_text
        n = db.execute(select(func.count()).select_from(RaffleNumber)).scalar_one()
        assert n == 200
        # mesmo conteúdo: não reaplica
        assert apply_from_file(db, path=cfg_dir / "campanha.json")["applied"] is False


def test_changes_are_applied_and_guards_respected(client, cfg_dir):
    p = cfg_dir / "campanha.json"
    with new_session() as db:
        # a fixture `client` já tem uma campanha ativa (100 números, R$ 10): o arquivo a atualiza
        with pytest.raises(CampaignConfigError):
            # preço muda depois do primeiro pedido → bloqueado
            client.post("/api/orders", json={"numbers": [1], "full_name": "Fulano de Tal", "email": "f@x.com",
                                              "phone": "81988887777", "cpf": "52998224725",
                                              "privacy_consent": True})
            apply_from_file(db, path=p)
    # sem pacote e sem prêmio extra: igual à campanha de teste (R$ 10, sem desconto)
    _edit(p, campanha__preco_reais=10.0, campanha__quantidade_numeros=150, campanha__premio="R$ 150,00",
          campanha__pacote={}, campanha__premio_extra={})
    with new_session() as db:
        r = apply_from_file(db, path=p)
        assert r["applied"] and not r["created"]
        c = db.execute(select(Campaign)).scalar_one()
        assert (c.total_numbers, c.prize_title) == (150, "R$ 150,00")
    assert client.get("/api/campaign").json()["prize_title"] == "R$ 150,00"


def test_invalid_config_is_reported(fresh_db, cfg_dir):
    p = cfg_dir / "campanha.json"
    _edit(p, campanha__preco_reais=0)
    with new_session() as db, pytest.raises(CampaignConfigError):
        apply_from_file(db, path=p)
    p.write_text("{ quebrado")
    with new_session() as db, pytest.raises(CampaignConfigError):
        apply_from_file(db, path=p)


@pytest.mark.parametrize("total, uniform", [(100, True), (200, True), (250, True), (1000, True), (150, False)])
def test_draw_rule(total, uniform):
    regra, exemplo = draw_rule(total)
    assert ("resto da divisão" in regra) is uniform
    assert exemplo
