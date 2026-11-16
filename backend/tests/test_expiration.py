"""Prazo de 15 minutos, cancelamento, expiração e pagamento tardio."""
from __future__ import annotations

import uuid

from app.db import new_session
from app.models import Order
from app.providers import set_provider
from app.services.payments import reconcile_once

from .conftest import expire_checkout, number_statuses, place
from .fakes import FakeMercadoPago


def _status(order_id: str) -> str:
    with new_session() as db:
        return db.get(Order, uuid.UUID(order_id)).status


def test_checkout_timeout_cancels_and_releases(client, campaign):
    created = place(client, [1, 2]).json()
    oid, h = created["order"]["id"], {"X-Order-Token": created["access_token"]}
    # antes do prazo, o encerramento não tem efeito
    assert client.post(f"/api/orders/{oid}/checkout-timeout", headers=h).json()["status"] == "awaiting_payment"
    expire_checkout(oid)
    view = client.post(f"/api/orders/{oid}/checkout-timeout", headers=h).json()
    assert view["status"] == "cancelled"
    assert view["pix"] is None
    assert number_statuses(campaign.id, [1, 2]) == {1: "available", 2: "available"}


def test_reconciler_closes_abandoned_checkout(client, campaign):
    created = place(client, [3]).json()
    expire_checkout(created["order"]["id"])
    with new_session() as db:
        stats = reconcile_once(db)
    assert stats["checkout_expired"] == 1
    assert _status(created["order"]["id"]) == "cancelled"
    assert number_statuses(campaign.id, [3]) == {3: "available"}


def test_numbers_stay_reserved_while_charge_can_be_approved(client, campaign):
    """Se o provedor não aceitar o cancelamento, os números NÃO são liberados até o Pix
    expirar de fato (confirmado pelo provedor)."""
    fake = FakeMercadoPago()
    fake.cancel_unsupported = True
    set_provider(fake)
    created = place(client, [4, 5]).json()
    oid = created["order"]["id"]
    expire_checkout(oid)
    with new_session() as db:
        reconcile_once(db)
    assert _status(oid) == "pending"
    assert number_statuses(campaign.id, [4, 5]) == {4: "reserved", 5: "reserved"}
    view = client.get(f"/api/orders/{oid}", headers={"X-Order-Token": created["access_token"]}).json()
    assert view["status"] == "awaiting_confirmation" and view["pix"] is None

    # Pix vence no provedor (MP: status cancelled / detail expired)
    pid = next(iter(fake.payments))
    fake.set(pid, "cancelled", "expired")
    with new_session() as db:
        reconcile_once(db)
    assert _status(oid) == "expired"
    assert number_statuses(campaign.id, [4, 5]) == {4: "available", 5: "available"}


def test_late_payment_within_pix_validity_is_accepted(client, campaign):
    """Participante paga depois dos 15 min visuais, mas antes do vencimento do Pix."""
    fake = FakeMercadoPago()
    fake.cancel_unsupported = True
    set_provider(fake)
    created = place(client, [6]).json()
    oid = created["order"]["id"]
    expire_checkout(oid)
    with new_session() as db:
        reconcile_once(db)
    pid = next(iter(fake.payments))
    fake.set(pid, "approved", "accredited")
    with new_session() as db:
        reconcile_once(db)
    assert _status(oid) == "paid"
    assert number_statuses(campaign.id, [6]) == {6: "paid"}


def test_approved_during_cancellation(client, campaign):
    """Pagamento aprovado entre a consulta e o pedido de cancelamento."""
    fake = FakeMercadoPago()
    set_provider(fake)
    created = place(client, [7]).json()
    oid = created["order"]["id"]
    pid = next(iter(fake.payments))
    original_cancel = fake.cancel_payment

    def racing_cancel(payment_id):
        fake.set(payment_id, "approved", "accredited")
        return original_cancel(payment_id)  # falha: já aprovado

    fake.cancel_payment = racing_cancel
    expire_checkout(oid)
    with new_session() as db:
        reconcile_once(db)
    assert _status(oid) == "paid"
    assert number_statuses(campaign.id, [7]) == {7: "paid"}


def test_late_payment_after_release_reacquires_free_numbers(client, campaign):
    fake = FakeMercadoPago()
    set_provider(fake)
    created = place(client, [8, 9]).json()
    oid = created["order"]["id"]
    expire_checkout(oid)
    with new_session() as db:
        reconcile_once(db)  # cancelado e liberado
    assert _status(oid) == "cancelled"
    # Cenário anômalo: o provedor aprova mesmo assim (conciliação de pagamento tardio)
    pid = next(iter(fake.payments))
    fake.set(pid, "approved", "accredited")
    from app.services.payments import apply_provider_payment

    with new_session() as db:
        apply_provider_payment(db, fake.get_payment(pid))
    assert _status(oid) == "paid"
    assert number_statuses(campaign.id, [8, 9]) == {8: "paid", 9: "paid"}


def test_late_payment_conflict_goes_to_review(client, campaign):
    fake = FakeMercadoPago()
    set_provider(fake)
    first = place(client, [10, 11]).json()
    oid = first["order"]["id"]
    expire_checkout(oid)
    with new_session() as db:
        reconcile_once(db)
    second = place(client, [11]).json()  # outra pessoa compra o 11
    assert second["order"]["numbers"] == [11]

    pid = fake.by_key[oid]
    fake.set(pid, "approved", "accredited")
    from app.services.payments import apply_provider_payment

    with new_session() as db:
        apply_provider_payment(db, fake.get_payment(pid))
        o = db.get(Order, uuid.UUID(oid))
        assert o.status == "in_review"
        assert "estorno" in o.review_reason.lower()
    # nenhum número foi tomado do segundo comprador; o 10 não foi vendido em duplicidade
    st = number_statuses(campaign.id, [10, 11])
    assert st[11] == "reserved" and st[10] == "available"


def test_simulator_pix_expiry(client, campaign):
    created = place(client, [12]).json()
    oid = created["order"]["id"]
    expire_checkout(oid, also_pix=True)
    with new_session() as db:
        reconcile_once(db)
    assert _status(oid) == "expired"
    assert number_statuses(campaign.id, [12]) == {12: "available"}


def test_amount_mismatch_goes_to_review(client, campaign):
    fake = FakeMercadoPago()
    fake.amount_override = 1  # provedor reporta R$ 0,01
    set_provider(fake)
    created = place(client, [13]).json()
    pid = next(iter(fake.payments))
    fake.set(pid, "approved", "accredited")
    from app.services.payments import apply_provider_payment

    with new_session() as db:
        apply_provider_payment(db, fake.get_payment(pid))
    assert _status(created["order"]["id"]) == "in_review"
    assert number_statuses(campaign.id, [13]) == {13: "reserved"}


def test_charge_creation_failure_releases(client, campaign):
    from app.providers.base import ProviderError

    fake = FakeMercadoPago()
    fake.fail_create = ProviderError("dados inválidos", status_code=400, retriable=False)
    set_provider(fake)
    r = place(client, [14])
    assert r.status_code == 502
    assert number_statuses(campaign.id, [14]) == {14: "available"}


def test_lost_create_response_is_recovered(client, campaign):
    from app.providers.base import ProviderError

    fake = FakeMercadoPago()
    fake.fail_create = ProviderError("timeout")
    fake.create_but_lose_response = True
    set_provider(fake)
    r = place(client, [15])
    assert r.status_code == 201, r.text
    assert r.json()["order"]["pix"]["qr_code"].startswith("000201FAKE")
    assert fake.create_calls == 1  # nenhuma cobrança duplicada


def test_live_payment_blocked_in_test_mode(client, campaign):
    fake = FakeMercadoPago()
    fake.live_mode = True
    set_provider(fake)
    r = place(client, [16])
    assert r.status_code == 503
    assert fake.cancel_calls == 1
    assert number_statuses(campaign.id, [16]) == {16: "available"}
