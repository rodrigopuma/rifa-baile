"""Pacote promocional (a cada N números do mesmo pedido, o grupo custa menos) e prêmio com meta."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.db import new_session
from app.models import Campaign
from app.schemas import CampaignSettingsIn
from app.services.campaign_config import CampaignConfigError, apply_from_file
from app.services.pricing import order_total_cents

from .conftest import admin_token, place

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("qty, total", [(1, 1000), (2, 2000), (3, 2500), (4, 3500), (5, 4500), (6, 5000),
                                        (7, 6000), (9, 7500), (50, 42000)])
def test_bundle_every_group_of_three(qty, total):
    assert order_total_cents(1000, 3, 2500, qty) == total


def test_no_bundle_is_plain_multiplication():
    assert order_total_cents(1000, 0, 0, 7) == 7000


@pytest.fixture
def bundled(campaign):
    """Campanha de teste com pacote 3 por R$ 25 (número a R$ 10)."""
    with new_session() as db:
        c = db.get(Campaign, campaign.id)
        c.bundle_size, c.bundle_price_cents = 3, 2500
        db.commit()
    return campaign


def test_server_applies_bundle_discount(client, bundled):
    # números 1..: pedidos de tamanhos diferentes, cada um de uma pessoa diferente
    nums = iter(range(1, 100))
    expected = {1: 1000, 3: 2500, 4: 3500, 6: 5000, 7: 6000}
    for i, (qty, total) in enumerate(expected.items(), start=1):
        r = place(client, [next(nums) for _ in range(qty)], i=700 + i)
        assert r.status_code == 201, r.text
        order = r.json()["order"]
        assert order["unit_price_cents"] == 1000          # preço do número avulso continua o mesmo
        assert order["total_cents"] == total
        assert order["discount_cents"] == qty * 1000 - total


def test_browser_cannot_set_the_price(client, bundled):
    r = place(client, [1, 2, 3], total_cents=1, unit_price_cents=1, bundle_price_cents=1)
    assert r.json()["order"]["total_cents"] == 2500


def test_public_campaign_exposes_bundle(client, bundled):
    info = client.get("/api/campaign").json()
    assert (info["price_cents"], info["bundle_size"], info["bundle_price_cents"]) == (1000, 3, 2500)


def test_revenue_uses_discounted_total(client, bundled, fresh_db):
    h = {"Authorization": f"Bearer {admin_token(fresh_db)}"}
    from app.config import get_settings
    from app.providers import set_provider

    get_settings().payment_mode = "manual_pix"
    set_provider(None)
    created = client.post("/api/orders", json={"numbers": [1, 2, 3, 4], "full_name": "Maria da Silva",
                                               "phone": "(81) 98765-4321", "privacy_consent": True}).json()
    client.post(f"/api/admin/orders/{created['order']['id']}/confirm", headers=h)
    ov = client.get("/api/admin/overview", headers=h).json()
    assert ov["gross_cents"] == 3500
    assert "35,00" in client.get("/api/admin/export.csv", headers=h).text


def test_bundle_settings_validation():
    base = dict(name="Rifa", price_cents=1000, total_numbers=100)
    assert CampaignSettingsIn(**base).bundle_size == 0
    assert CampaignSettingsIn(**base, bundle_size=3, bundle_price_cents=2500).bundle_price_cents == 2500
    for bad in (dict(bundle_size=3, bundle_price_cents=3000),   # não dá desconto
                dict(bundle_size=3, bundle_price_cents=3500),   # mais caro que avulso
                dict(bundle_size=1, bundle_price_cents=500),    # pacote de 1 não existe
                dict(bundle_size=3, bundle_price_cents=0),
                dict(bundle_size=0, bundle_price_cents=2500)):
        with pytest.raises(ValidationError):
            CampaignSettingsIn(**base, **bad)


def test_price_and_bundle_locked_after_first_order(client, bundled, fresh_db):
    h = {"Authorization": f"Bearer {admin_token(fresh_db)}"}
    body = {"name": "Rifa Solidária", "subtitle": "", "description": "", "prize_title": "", "price_cents": 1000,
            "bundle_size": 3, "bundle_price_cents": 2500, "total_numbers": 100, "draw_date": None,
            "organizer_name": "", "organizer_contact": "", "regulation_text": "", "authorization_info": "",
            "header_image_url": ""}
    url = f"/api/admin/campaigns/{bundled.id}"
    assert client.put(url, json=body, headers=h).status_code == 200          # sem pedidos: igual, ok
    place(client, [1], i=801)
    assert client.put(url, json=body, headers=h).status_code == 200          # sem mudar o preço: ok
    assert client.put(url, json={**body, "bundle_price_cents": 2000}, headers=h).status_code == 409
    assert client.put(url, json={**body, "bundle_size": 0, "bundle_price_cents": 0}, headers=h).status_code == 409


def test_config_file_with_bundle_and_prize_goal(fresh_db, tmp_path):
    shutil.copy(ROOT / "REGULAMENTO.md", tmp_path / "REGULAMENTO.md")
    cfg = json.loads((ROOT / "campanha.json").read_text(encoding="utf-8"))
    cfg["campanha"].update(premio="R$ 150,00", premio_extra={"acima_de_numeros": 100, "premio": "R$ 250,00"},
                           preco_reais=10.0, pacote={"quantidade": 3, "preco_reais": 25.0})
    p = tmp_path / "campanha.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    with new_session() as db:
        apply_from_file(db, path=p)
        c = db.execute(select(Campaign)).scalar_one()
        assert (c.price_cents, c.bundle_size, c.bundle_price_cents) == (1000, 3, 2500)
        assert "R$ 150,00 garantido" in c.prize_title and "R$ 250,00" in c.prize_title
        assert "Pacote: a cada 3 números" in c.regulation_text
        assert "garantido independentemente" in c.regulation_text

    # um pacote inválido é recusado com mensagem clara
    cfg["campanha"]["pacote"] = {"quantidade": 3, "preco_reais": 31.0}
    p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    with new_session() as db, pytest.raises(CampaignConfigError, match="menor"):
        apply_from_file(db, path=p, force=True)


def test_config_without_bundle_or_extra_prize(fresh_db, tmp_path):
    shutil.copy(ROOT / "REGULAMENTO.md", tmp_path / "REGULAMENTO.md")
    cfg = json.loads((ROOT / "campanha.json").read_text(encoding="utf-8"))
    cfg["campanha"].pop("pacote"), cfg["campanha"].pop("premio_extra")
    (tmp_path / "campanha.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    with new_session() as db:
        apply_from_file(db, path=tmp_path / "campanha.json")
        c = db.execute(select(Campaign)).scalar_one()
        assert (c.bundle_size, c.bundle_price_cents, c.prize_title) == (0, 0, "R$ 150,00")
        assert "Pacote" not in c.regulation_text and "Prêmio: R$ 150,00, ressalvado" in c.regulation_text


def test_config_change_of_bundle_blocked_after_orders(client, bundled, tmp_path):
    """Com pedidos feitos, mudar o pacote pelo campanha.json é recusado (como o preço)."""
    shutil.copy(ROOT / "REGULAMENTO.md", tmp_path / "REGULAMENTO.md")
    cfg = json.loads((ROOT / "campanha.json").read_text(encoding="utf-8"))
    cfg["campanha"]["pacote"] = {"quantidade": 4, "preco_reais": 30.0}
    (tmp_path / "campanha.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    place(client, [1], i=901)
    with new_session() as db, pytest.raises(CampaignConfigError, match="primeiro pedido"):
        apply_from_file(db, path=tmp_path / "campanha.json")


def test_minimum_numbers_rule_in_regulation(fresh_db, tmp_path):
    shutil.copy(ROOT / "REGULAMENTO.md", tmp_path / "REGULAMENTO.md")
    cfg = json.loads((ROOT / "campanha.json").read_text(encoding="utf-8"))
    assert cfg["campanha"]["minimo_numeros"] == 15
    p = tmp_path / "campanha.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    with new_session() as db:
        apply_from_file(db, path=p)
        reg = db.execute(select(Campaign)).scalar_one().regulation_text
    assert "6.3. A rifa tem mínimo de 15 números" in reg and "devolvendo integralmente" in reg
    assert "ressalvado o mínimo de números previsto no item 6.3" in reg

    cfg["campanha"]["minimo_numeros"] = 0                      # sem mínimo: a cláusula some
    p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    with new_session() as db:
        apply_from_file(db, path=p, force=True)
        reg = db.execute(select(Campaign)).scalar_one().regulation_text
    assert "6.3" not in reg and "ressalvado" not in reg and "\n\n\n" not in reg
