"""Proteção e funcionalidades do painel administrativo."""
from __future__ import annotations

import time
import uuid

import jwt
import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.db import new_session
from app.models import Campaign

from .conftest import admin_token, place


def test_admin_requires_valid_admin(client, fresh_db):
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/api/admin/overview", headers={"Authorization": "Bearer lixo"}).status_code == 401
    # assinatura errada
    forged = jwt.encode({"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": int(time.time()) + 60},
                        "outro-segredo", algorithm="HS256")
    assert client.get("/api/admin/overview", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    # token expirado
    expired = jwt.encode({"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": int(time.time()) - 10},
                         get_settings().supabase_jwt_secret, algorithm="HS256")
    assert client.get("/api/admin/overview", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    # usuário autenticado, mas não cadastrado como administrador
    stranger = admin_token(fresh_db, register=False)
    assert client.get("/api/admin/overview", headers={"Authorization": f"Bearer {stranger}"}).status_code == 403
    ok = admin_token(fresh_db)
    assert client.get("/api/admin/overview", headers={"Authorization": f"Bearer {ok}"}).status_code == 200


def test_every_admin_route_is_protected(client):
    from app.main import app

    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/admin"):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            url = path.replace("{payment_id}", str(uuid.uuid4())).replace("{order_id}", str(uuid.uuid4())) \
                      .replace("{campaign_id}", str(uuid.uuid4()))
            r = client.request(method, url, json={})
            assert r.status_code == 401, (method, path, r.status_code)


def test_no_manual_approval_endpoint(client):
    from app.main import app

    paths = [getattr(r, "path", "") for r in app.routes if getattr(r, "path", "").startswith("/api/admin")]
    assert not any("approve" in p for p in paths)


def test_overview_search_and_export(client, campaign, fresh_db):
    h = {"Authorization": f"Bearer {admin_token(fresh_db)}"}
    a = place(client, [1, 2], i=901).json()
    place(client, [3], i=902)
    client.post(f"/api/dev/simulator/payments/{a['order']['simulator_payment_id']}/approve")

    ov = client.get("/api/admin/overview", headers=h).json()
    assert ov["numbers"] == {"available": 97, "reserved": 1, "paid": 2}
    assert ov["gross_cents"] == 2000
    assert ov["pending_payments"] == 1

    by_number = client.get("/api/admin/orders", params={"q": "3"}, headers=h).json()
    assert [o["numbers"] for o in by_number["items"]] == [[3]]
    by_phone = client.get("/api/admin/orders", params={"q": "98901"}, headers=h).json()
    assert by_phone["total"] == 1 and by_phone["items"][0]["numbers"] == [1, 2]
    by_code = client.get("/api/admin/orders", params={"q": a["order"]["code"].lower()}, headers=h).json()
    assert by_code["total"] == 1
    by_name = client.get("/api/admin/orders", params={"q": "teste 902"}, headers=h).json()
    assert by_name["total"] == 1

    people = client.get("/api/admin/participants", headers=h).json()["items"]
    paid = {p["full_name"]: p["paid_numbers"] for p in people}
    assert paid["Participante Teste 901"] == [1, 2]

    csv = client.get("/api/admin/export.csv", headers=h)
    assert csv.status_code == 200 and "participantes.csv" in csv.headers["content-disposition"]
    assert "Participante Teste 901" in csv.text and "20,00" in csv.text

    pays = client.get("/api/admin/payments", headers=h).json()
    assert pays["total"] == 2
    pid = next(p["id"] for p in pays["items"] if p["status"] == "pending")
    assert client.post(f"/api/admin/payments/{pid}/sync", headers=h).json()["status"] == "pending"

    logs = client.get("/api/admin/audit-logs", headers=h).json()["items"]
    assert any(log["action"] == "export_csv" for log in logs)


def test_admin_cancel_pending(client, campaign, fresh_db):
    h = {"Authorization": f"Bearer {admin_token(fresh_db)}"}
    o = place(client, [60]).json()["order"]
    r = client.post(f"/api/admin/orders/{o['id']}/cancel", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.post(f"/api/admin/orders/{o['id']}/cancel", headers=h).status_code == 409


def test_settings_and_single_active_campaign(client, campaign, fresh_db):
    h = {"Authorization": f"Bearer {admin_token(fresh_db)}"}
    body = {"name": "Rifa Solidária", "subtitle": "Formatura", "description": "d", "price_cents": 1000,
            "total_numbers": 120, "draw_date": "2027-01-10", "organizer_name": "Rodrigo", "prize_title": "R$ 100,00",
            "organizer_contact": "c@x.com", "regulation_text": "r", "authorization_info": "",
            "header_image_url": ""}
    r = client.put(f"/api/admin/campaigns/{campaign.id}", json=body, headers=h)
    assert r.status_code == 200 and r.json()["total_numbers"] == 120
    assert client.get("/api/campaign").json()["available_count"] == 120

    place(client, [119])
    assert client.put(f"/api/admin/campaigns/{campaign.id}", json={**body, "total_numbers": 110},
                      headers=h).status_code == 409
    assert client.put(f"/api/admin/campaigns/{campaign.id}", json={**body, "price_cents": 500},
                      headers=h).status_code == 409
    assert client.put(f"/api/admin/campaigns/{campaign.id}", json={**body, "header_image_url": "http://x"},
                      headers=h).status_code == 422

    new = client.post("/api/admin/campaigns", json={**body, "name": "Segunda"}, headers=h).json()
    assert new["status"] == "draft"
    r = client.post(f"/api/admin/campaigns/{new['id']}/status", json={"status": "active"}, headers=h)
    assert r.status_code == 409
    client.post(f"/api/admin/campaigns/{campaign.id}/status", json={"status": "closed"}, headers=h)
    r = client.post(f"/api/admin/campaigns/{new['id']}/status", json={"status": "active"}, headers=h)
    assert r.status_code == 200
    with new_session() as db:
        from sqlalchemy import select

        assert len(db.execute(select(Campaign).where(Campaign.status == "active")).all()) == 1


def test_live_mode_requires_explicit_acknowledgement():
    base = dict(payment_mode="mercadopago_live", mp_access_token="APP_USR-x", mp_webhook_secret="s",
                public_base_url="https://api.exemplo.com")
    with pytest.raises(ValidationError):
        Settings(**base)
    from app.config import LIVE_ACK_PHRASE

    assert Settings(**base, live_payments_acknowledgement=LIVE_ACK_PHRASE).is_live
    with pytest.raises(ValidationError):
        Settings(payment_mode="mercadopago_test")  # sem credenciais
    with pytest.raises(ValidationError):
        Settings(pix_expiration_minutes=20)  # abaixo do mínimo do MP
    with pytest.raises(ValidationError):
        Settings(environment="production", payment_mode="simulator")
