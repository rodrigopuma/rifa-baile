"""Modo manual (PAYMENT_MODE=manual_pix): reserva sem pagamento online e confirmação pelo organizador."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config import Settings, get_settings
from app.db import new_session
from app.models import AuditLog, Order, Payment
from app.providers import set_provider
from app.services.payments import reconcile_once

from .conftest import admin_token, expire_checkout, number_statuses


@pytest.fixture
def manual(client):
    """Liga o modo manual (a fixture fresh_db restaura as configurações no fim do teste)."""
    get_settings().payment_mode = "manual_pix"
    set_provider(None)
    return client


def reserve(client: TestClient, numbers: list[int], i: int = 1, **extra):
    """Pedido do jeito que o site faz no modo manual: só nome e WhatsApp."""
    body = {"numbers": numbers, "full_name": f"Participante Manual {i}",
            "phone": f"(81) 9{7000 + i:04d}-{2000 + i:04d}", "privacy_consent": True, **extra}
    return client.post("/api/orders", json=body)


def admin(fresh_db) -> dict:
    return {"Authorization": f"Bearer {admin_token(fresh_db)}"}


def test_reservation_needs_only_name_and_whatsapp(manual, campaign):
    r = reserve(manual, [5, 6])
    assert r.status_code == 201, r.text
    order = r.json()["order"]
    assert order["status"] == "awaiting_payment"
    assert order["payment_mode"] == "manual"
    assert order["pix"] is None and "simulator_payment_id" not in order
    assert order["total_cents"] == 2000
    assert number_statuses(campaign.id, [5, 6]) == {5: "reserved", 6: "reserved"}

    info = manual.get("/api/campaign").json()
    assert info["payment_mode"] == "manual"
    assert info["payer_cpf_required"] is False
    assert info["reservation_hold_minutes"] == 1440
    with new_session() as db:
        p = db.execute(select(Payment)).scalar_one()
        assert (p.provider, p.status, p.amount_cents, p.qr_code) == ("manual", "pending", 2000, "")


def test_cpf_sent_by_mistake_is_never_stored(manual, campaign):
    r = reserve(manual, [9], cpf="529.982.247-25", email="alguem@exemplo.com")
    assert r.status_code == 201
    with new_session() as db:
        assert db.execute(select(Order)).scalar_one().participant.cpf_masked == ""


def test_email_still_required_outside_manual_mode(client, campaign):
    body = {"numbers": [1], "full_name": "Fulano de Tal", "phone": "(81) 98888-7777",
            "cpf": "52998224725", "privacy_consent": True}
    r = client.post("/api/orders", json=body)
    assert r.status_code == 422 and "E-mail" in r.text


def test_same_whatsapp_limit_but_other_people_not_blocked(manual, campaign):
    assert reserve(manual, [1], i=10).status_code == 201
    assert reserve(manual, [2], i=11).status_code == 201   # outra pessoa, também sem e-mail
    assert reserve(manual, [3], i=12).status_code == 201
    assert reserve(manual, [4], i=10).status_code == 201
    assert reserve(manual, [5], i=10).status_code == 429   # o mesmo WhatsApp com 2 pedidos abertos


def test_admin_confirms_payment_and_participant_gets_receipt(manual, campaign, fresh_db):
    h = admin(fresh_db)
    created = reserve(manual, [30, 31]).json()
    order, token = created["order"], created["access_token"]
    tok = {"X-Order-Token": token}
    assert manual.get(f"/api/receipts/{order['id']}", headers=tok).status_code == 409  # ainda não pago

    r = manual.post(f"/api/admin/orders/{order['id']}/confirm", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "paid"
    assert r.json()["payment"]["status"] == "approved"

    view = manual.get(f"/api/orders/{order['id']}", headers=tok).json()
    assert view["status"] == "paid" and view["paid_cents"] == 2000
    assert number_statuses(campaign.id, [30, 31]) == {30: "paid", 31: "paid"}
    receipt = manual.get(f"/api/receipts/{order['id']}", headers=tok).json()
    assert receipt["numbers"] == [30, 31] and receipt["payment_mode"] == "manual"

    # confirmar de novo não duplica nada
    assert manual.post(f"/api/admin/orders/{order['id']}/confirm", headers=h).status_code == 200
    with new_session() as db:
        n = db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.action == "order_paid")).scalar_one()
        assert n == 1
        log = db.execute(select(AuditLog).where(AuditLog.action == "order_paid")).scalar_one()
        assert log.actor_type == "admin" and log.details["manual"] is True


def test_overview_counts_reserved_and_paid(manual, campaign, fresh_db):
    h = admin(fresh_db)
    a = reserve(manual, [1, 2], i=21).json()["order"]
    reserve(manual, [3], i=22)
    manual.post(f"/api/admin/orders/{a['id']}/confirm", headers=h)
    ov = manual.get("/api/admin/overview", headers=h).json()
    assert ov["payment_mode"] == "manual"
    assert ov["numbers"] == {"available": 97, "reserved": 1, "paid": 2}
    assert ov["gross_cents"] == 2000 and ov["pending_payments"] == 1


def test_admin_cancel_releases_immediately(manual, campaign, fresh_db):
    h = admin(fresh_db)
    o = reserve(manual, [40]).json()["order"]
    r = manual.post(f"/api/admin/orders/{o['id']}/cancel", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert number_statuses(campaign.id, [40]) == {40: "available"}
    assert manual.post(f"/api/admin/orders/{o['id']}/cancel", headers=h).status_code == 409
    assert reserve(manual, [40], i=2).status_code == 201  # o número voltou para a venda


def test_refund_undoes_a_confirmation(manual, campaign, fresh_db):
    h = admin(fresh_db)
    o = reserve(manual, [50]).json()["order"]
    assert manual.post(f"/api/admin/orders/{o['id']}/refund", headers=h).status_code == 409  # ainda pendente
    manual.post(f"/api/admin/orders/{o['id']}/confirm", headers=h)
    r = manual.post(f"/api/admin/orders/{o['id']}/refund", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "refunded"
    assert number_statuses(campaign.id, [50]) == {50: "available"}


def test_reservation_expires_and_frees_numbers(manual, campaign):
    created = reserve(manual, [60, 61]).json()
    oid, token = created["order"]["id"], created["access_token"]
    expire_checkout(oid)
    # consultar o pedido já vence a reserva
    view = manual.get(f"/api/orders/{oid}", headers={"X-Order-Token": token}).json()
    assert view["status"] == "expired"
    assert number_statuses(campaign.id, [60, 61]) == {60: "available", 61: "available"}


def test_expired_reservations_are_freed_for_other_buyers(manual, campaign):
    oid = reserve(manual, [70], i=31).json()["order"]["id"]
    expire_checkout(oid)
    assert manual.get("/api/campaign/availability").json()["unavailable"] == []   # liberação "preguiçosa"
    assert reserve(manual, [70], i=32).status_code == 201


def test_background_reconciler_expires_reservations(manual, campaign):
    oid = reserve(manual, [80], i=41).json()["order"]["id"]
    expire_checkout(oid)
    with new_session() as db:
        stats = reconcile_once(db)
    assert stats["checkout_expired"] == 1 and stats["errors"] == 0
    assert number_statuses(campaign.id, [80]) == {80: "available"}


def test_checkout_timeout_endpoint_expires_in_manual_mode(manual, campaign):
    created = reserve(manual, [85], i=42).json()
    oid, tok = created["order"]["id"], {"X-Order-Token": created["access_token"]}
    # antes do prazo, nada acontece
    assert manual.post(f"/api/orders/{oid}/checkout-timeout", headers=tok).json()["status"] == "awaiting_payment"
    expire_checkout(oid)
    assert manual.post(f"/api/orders/{oid}/checkout-timeout", headers=tok).json()["status"] == "expired"


def test_late_confirmation_works_if_numbers_still_free(manual, campaign, fresh_db):
    h = admin(fresh_db)
    oid = reserve(manual, [90], i=51).json()["order"]["id"]
    expire_checkout(oid)
    manual.get("/api/campaign/availability")  # vence a reserva
    r = manual.post(f"/api/admin/orders/{oid}/confirm", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "paid"
    assert number_statuses(campaign.id, [90]) == {90: "paid"}
    with new_session() as db:
        assert db.execute(select(func.count()).select_from(AuditLog)
                          .where(AuditLog.action == "late_payment_reconciled")).scalar_one() == 1


def test_late_confirmation_conflicts_if_someone_else_took_the_number(manual, campaign, fresh_db):
    h = admin(fresh_db)
    first = reserve(manual, [91], i=61).json()["order"]["id"]
    expire_checkout(first)
    assert reserve(manual, [91], i=62).status_code == 201   # outra pessoa ficou com o número
    r = manual.post(f"/api/admin/orders/{first}/confirm", headers=h)
    assert r.status_code == 409 and "outro participante" in r.json()["detail"]
    assert number_statuses(campaign.id, [91]) == {91: "reserved"}   # a reserva da 2ª pessoa segue intacta


def test_confirm_and_refund_are_refused_outside_manual_mode(client, campaign, fresh_db):
    from .conftest import place

    h = admin(fresh_db)
    o = place(client, [12]).json()["order"]
    assert client.post(f"/api/admin/orders/{o['id']}/confirm", headers=h).status_code == 409
    assert client.post(f"/api/admin/orders/{o['id']}/refund", headers=h).status_code == 409
    assert number_statuses(campaign.id, [12]) == {12: "reserved"}


def test_manual_payment_sync_does_not_call_any_provider(manual, campaign, fresh_db):
    h = admin(fresh_db)
    reserve(manual, [14])
    pid = manual.get("/api/admin/payments", headers=h).json()["items"][0]["id"]
    r = manual.post(f"/api/admin/payments/{pid}/sync", headers=h)
    assert r.status_code == 200 and r.json()["provider"] == "manual"


def test_mercadopago_webhook_is_closed_in_manual_mode(manual):
    assert manual.post("/api/webhooks/mercadopago", json={}).status_code == 404


def test_confirm_unknown_order_is_404(manual, fresh_db):
    h = admin(fresh_db)
    assert manual.post(f"/api/admin/orders/{uuid.uuid4()}/confirm", headers=h).status_code == 404


def test_manual_settings_do_not_need_mercadopago_credentials():
    s = Settings(payment_mode="manual_pix", environment="production")
    assert s.is_manual and s.public_payment_mode == "manual" and not s.is_live
    with pytest.raises(ValidationError):
        Settings(payment_mode="manual_pix", manual_hold_minutes=5)
