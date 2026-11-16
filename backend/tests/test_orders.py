"""Seleção múltipla, indisponibilidade, cobrança, aprovação e comprovante (simulador)."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db import new_session
from app.models import AuditLog, Order

from .conftest import buyer, number_statuses, place


def test_public_campaign_hides_reserved_count(client, campaign):
    place(client, [1, 2, 3])
    data = client.get("/api/campaign").json()
    assert data["available_count"] == 97
    assert data["total_numbers"] == 100
    assert "reserved" not in str(data.keys())
    av = client.get("/api/campaign/availability").json()
    assert av["unavailable"] == [1, 2, 3]  # reservados aparecem só como indisponíveis
    assert av["available_count"] == 97


def test_multi_select_single_order_price_from_server(client, campaign):
    r = place(client, [7, 3, 5, 3], unit_price_cents=1, total_cents=1)  # valores do navegador ignorados
    assert r.status_code == 201, r.text
    order = r.json()["order"]
    assert order["numbers"] == [3, 5, 7]
    assert order["quantity"] == 3
    assert order["unit_price_cents"] == 1000
    assert order["total_cents"] == 3000
    assert order["status"] == "awaiting_payment"
    assert order["pix"]["qr_code_base64"]
    assert order["pix"]["qr_code"].startswith("SIMULADOR-PIX-SEM-VALOR")
    assert number_statuses(campaign.id, [3, 5, 7]) == {3: "reserved", 5: "reserved", 7: "reserved"}


def test_unavailable_numbers_rejected_atomically(client, campaign):
    assert place(client, [10, 11]).status_code == 201
    r = place(client, [9, 10, 12])
    assert r.status_code == 409
    assert r.json()["detail"]["unavailable"] == [10]
    # nada do segundo pedido ficou reservado
    assert number_statuses(campaign.id, [9, 12]) == {9: "available", 12: "available"}


def test_validation_errors(client, campaign):
    assert place(client, [0]).status_code == 422
    assert place(client, [101]).status_code == 422
    assert place(client, []).status_code == 422
    bad = {**buyer(), "cpf": "123.456.789-00"}
    assert client.post("/api/orders", json={"numbers": [1], **bad}).status_code == 422
    bad = {**buyer(), "phone": "8133334444"}  # fixo, não celular
    assert client.post("/api/orders", json={"numbers": [1], **bad}).status_code == 422
    bad = {**buyer(), "privacy_consent": False}
    assert client.post("/api/orders", json={"numbers": [1], **bad}).status_code == 422


def test_pending_orders_limit_per_contact(client, campaign):
    assert place(client, [1], i=500).status_code == 201
    assert place(client, [2], i=500).status_code == 201
    r = place(client, [3], i=500)
    assert r.status_code == 429


def test_order_requires_token(client, campaign):
    created = place(client, [20]).json()
    oid, token = created["order"]["id"], created["access_token"]
    assert client.get(f"/api/orders/{oid}").status_code == 404
    assert client.get(f"/api/orders/{oid}", headers={"X-Order-Token": "errado"}).status_code == 404
    ok = client.get(f"/api/orders/{oid}", headers={"X-Order-Token": token})
    assert ok.status_code == 200
    assert "email" not in ok.text and "phone" not in ok.text


def test_approval_confirms_and_receipt(client, campaign):
    created = place(client, [30, 31]).json()
    order, token = created["order"], created["access_token"]
    h = {"X-Order-Token": token}
    assert client.get(f"/api/receipts/{order['id']}", headers=h).status_code == 409

    r = client.post(f"/api/dev/simulator/payments/{order['simulator_payment_id']}/approve")
    assert r.status_code == 200 and r.json()["order_status"] == "paid"

    view = client.get(f"/api/orders/{order['id']}", headers=h).json()
    assert view["status"] == "paid"
    assert view["participant_name"].startswith("Participante Teste")
    assert view["paid_cents"] == 2000
    assert view["pix"] is None
    assert number_statuses(campaign.id, [30, 31]) == {30: "paid", 31: "paid"}

    receipt = client.get(f"/api/receipts/{order['id']}", headers=h).json()
    assert receipt["numbers"] == [30, 31] and receipt["code"] == order["code"]
    assert client.get(f"/api/receipts/{order['id']}").status_code == 404

    # repetir a aprovação não gera efeito duplicado
    assert client.post(f"/api/dev/simulator/payments/{order['simulator_payment_id']}/approve").status_code == 409
    with new_session() as db:
        n = db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.action == "order_paid")).scalar_one()
        assert n == 1


def test_rejected_payment_releases(client, campaign):
    order = place(client, [40]).json()["order"]
    client.post(f"/api/dev/simulator/payments/{order['simulator_payment_id']}/reject")
    assert number_statuses(campaign.id, [40]) == {40: "available"}
    with new_session() as db:
        assert db.get(Order, __import__("uuid").UUID(order["id"])).status == "cancelled"


def test_refund_releases_numbers(client, campaign):
    created = place(client, [50]).json()
    pid = created["order"]["simulator_payment_id"]
    client.post(f"/api/dev/simulator/payments/{pid}/approve")
    client.post(f"/api/dev/simulator/payments/{pid}/refund")
    view = client.get(f"/api/orders/{created['order']['id']}", headers={"X-Order-Token": created["access_token"]})
    assert view.json()["status"] == "refunded"
    assert number_statuses(campaign.id, [50]) == {50: "available"}


def test_no_active_campaign(client, campaign):
    with new_session() as db:
        from app.models import Campaign

        c = db.get(Campaign, campaign.id)
        c.status = "paused"
        db.commit()
    assert place(client, [1]).status_code == 409
    assert client.get("/api/campaign").json()["status"] == "paused"
