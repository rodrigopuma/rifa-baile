"""Aviso no celular (ntfy): desligado sem tópico, payload sem dados pessoais, falhas não quebram a reserva."""
from __future__ import annotations

import threading

import httpx
import pytest

from app.config import get_settings
from app.providers import set_provider

from .conftest import place


@pytest.fixture
def manual_mode():
    s = get_settings()
    old = (s.payment_mode, s.ntfy_topic, s.ntfy_server, s.frontend_url)
    s.payment_mode, s.frontend_url = "manual_pix", "https://site.exemplo/rifa-baile"
    set_provider(None)
    yield s
    s.payment_mode, s.ntfy_topic, s.ntfy_server, s.frontend_url = old
    set_provider(None)


@pytest.fixture
def sent(monkeypatch):
    calls, done = [], threading.Event()

    def fake_post(url, json=None, timeout=None, **_):
        calls.append((url, json))
        done.set()
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    return calls, done


def test_disabled_without_topic(client, manual_mode, sent):
    calls, done = sent
    manual_mode.ntfy_topic = ""
    assert place(client, [1, 2, 3], i=11).status_code == 201
    assert not done.wait(0.3) and calls == []


def test_notifies_on_new_reservation(client, manual_mode, sent):
    calls, done = sent
    manual_mode.ntfy_topic = "segredo-longo-123"
    r = place(client, [4, 5, 6], i=12)
    assert r.status_code == 201
    assert done.wait(2)
    url, body = calls[0]
    code = r.json()["order"]["code"]
    assert url == "https://ntfy.sh/"
    assert body["topic"] == "segredo-longo-123"
    assert body["click"] == f"https://site.exemplo/rifa-baile/admin?q={code}"
    assert code in body["message"] and "3 números" in body["message"]
    assert "R$" in body["title"]


def test_payload_has_no_phone(client, manual_mode, sent):
    calls, done = sent
    manual_mode.ntfy_topic = "t-abc"
    r = client.post("/api/orders", json={"numbers": [9], "full_name": "Maria da Silva", "phone": "(81) 98765-4321",
                                         "privacy_consent": True})
    assert r.status_code == 201 and done.wait(2)
    assert "98765" not in str(calls[0][1]) and "Maria da Silva" in calls[0][1]["message"]


def test_failure_never_breaks_the_reservation(client, manual_mode, monkeypatch):
    manual_mode.ntfy_topic = "t-abc"
    done = threading.Event()

    def boom(*a, **k):
        done.set()
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "post", boom)
    assert place(client, [20], i=13).status_code == 201
    assert done.wait(2)


def test_not_sent_in_simulator_mode(client, sent):
    calls, done = sent
    s = get_settings()
    s.ntfy_topic = "t-abc"
    try:
        assert place(client, [30], i=14).status_code == 201
        assert not done.wait(0.3)
    finally:
        s.ntfy_topic = ""
