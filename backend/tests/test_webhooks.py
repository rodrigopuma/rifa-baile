"""Webhooks do Mercado Pago: assinatura, duplicidade e consulta à API."""
from __future__ import annotations

import json
import uuid

import httpx
from sqlalchemy import func, select

from app.config import get_settings
from app.db import new_session
from app.models import AuditLog, Order
from app.providers import set_provider
from app.providers.base import CreatePixRequest, PayerInfo
from app.providers.mercadopago import MercadoPagoProvider, sign_for_tests, verify_webhook_signature

from .conftest import number_statuses, place
from .fakes import FakeMercadoPago

SECRET = "segredo-webhook-teste"


def _mp_mode():
    s = get_settings()
    s.payment_mode = "mercadopago_test"
    s.mp_webhook_secret = SECRET
    s.mp_access_token = "TEST-xxx"


def _notify(client, payment_id: str, request_id: str, *, secret: str = SECRET):
    sig = sign_for_tests(secret, payment_id, request_id, "1731760000")
    return client.post(
        f"/api/webhooks/mercadopago?data.id={payment_id}&type=payment",
        json={"action": "payment.updated", "type": "payment", "data": {"id": payment_id}},
        headers={"x-signature": sig, "x-request-id": request_id},
    )


def _count(action: str) -> int:
    with new_session() as db:
        return db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.action == action)).scalar_one()


def test_webhook_approves_via_api_lookup(client, campaign):
    fake = FakeMercadoPago()
    set_provider(fake)
    created = place(client, [1, 2]).json()
    _mp_mode()
    pid = next(iter(fake.payments))

    # Webhook chega dizendo "approved", mas o provedor ainda diz pending: nada muda.
    assert _notify(client, pid, "req-1").status_code == 200
    assert number_statuses(campaign.id, [1, 2]) == {1: "reserved", 2: "reserved"}

    fake.set(pid, "approved", "accredited")
    assert _notify(client, pid, "req-2").status_code == 200
    with new_session() as db:
        assert db.get(Order, uuid.UUID(created["order"]["id"])).status == "paid"


def test_duplicate_webhooks_are_idempotent(client, campaign):
    fake = FakeMercadoPago()
    set_provider(fake)
    place(client, [3])
    _mp_mode()
    pid = next(iter(fake.payments))
    fake.set(pid, "approved", "accredited")
    for _ in range(3):
        assert _notify(client, pid, "req-dup").status_code == 200  # mesmo x-request-id
    for i in range(3):
        assert _notify(client, pid, f"req-other-{i}").status_code == 200  # ids diferentes
    assert _count("order_paid") == 1
    assert _count("payment_status_changed") == 1


def test_invalid_signature_rejected(client, campaign):
    fake = FakeMercadoPago()
    set_provider(fake)
    place(client, [4])
    _mp_mode()
    pid = next(iter(fake.payments))
    fake.set(pid, "approved", "accredited")
    assert _notify(client, pid, "req-x", secret="errado").status_code == 401
    r = client.post(f"/api/webhooks/mercadopago?data.id={pid}&type=payment", json={})
    assert r.status_code == 401
    assert number_statuses(campaign.id, [4]) == {4: "reserved"}


def test_webhook_disabled_in_simulator(client, campaign):
    assert client.post("/api/webhooks/mercadopago", json={}).status_code == 404


def test_signature_manifest_matches_documentation_format():
    sig = sign_for_tests("s", "ABC123", "rid", "1700000000")
    # id alfanumérico deve ser convertido para minúsculas no manifesto
    assert verify_webhook_signature("s", sig, "rid", "abc123")
    assert not verify_webhook_signature("s", sig, "rid2", "abc123")
    assert not verify_webhook_signature("s", None, "rid", "abc123")


def test_mercadopago_http_contract():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST":
            body = json.loads(request.content)
            return httpx.Response(201, json={
                "id": 123456, "status": "pending", "status_detail": "pending_waiting_transfer",
                "transaction_amount": body["transaction_amount"], "external_reference": body["external_reference"],
                "live_mode": False, "date_of_expiration": body["date_of_expiration"],
                "point_of_interaction": {"transaction_data": {"qr_code": "000201...", "qr_code_base64": "AAA",
                                                              "ticket_url": "https://mp/ticket"}},
            })
        if request.method == "PUT":
            return httpx.Response(200, json={"id": 123456, "status": "cancelled", "status_detail": "by_collector",
                                             "transaction_amount": 30.0, "external_reference": "x"})
        return httpx.Response(200, json={"results": []})

    from datetime import datetime, timezone

    client = httpx.Client(base_url="https://api.mercadopago.com", transport=httpx.MockTransport(handler))
    mp = MercadoPagoProvider("TEST-token", client=client)
    pp = mp.create_pix(CreatePixRequest(
        external_reference="ord-1", amount_cents=3000, description="Rifa - pedido RF-1",
        expires_at=datetime(2026, 11, 16, 18, 30, tzinfo=timezone.utc), idempotency_key="ord-1",
        payer=PayerInfo(full_name="Maria da Silva Souza", email="m@ex.com", cpf="52998224725"),
        notification_url="https://api.exemplo.com/api/webhooks/mercadopago",
    ))
    req = seen[0]
    body = json.loads(req.content)
    assert req.headers["X-Idempotency-Key"] == "ord-1"
    assert req.headers["Authorization"] == "Bearer TEST-token"
    assert body["payment_method_id"] == "pix"
    assert body["transaction_amount"] == 30.0
    assert body["date_of_expiration"] == "2026-11-16T18:30:00.000+00:00"
    assert body["payer"]["identification"] == {"type": "CPF", "number": "52998224725"}
    assert body["payer"]["first_name"] == "Maria" and body["payer"]["last_name"] == "da Silva Souza"
    assert pp.id == "123456" and pp.amount_cents == 3000 and pp.qr_code_base64 == "AAA"

    cancelled = mp.cancel_payment("123456")
    assert json.loads(seen[1].content) == {"status": "cancelled"}
    assert cancelled.status == "cancelled"
    assert mp.find_by_reference("nada") is None
