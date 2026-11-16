"""Integração com a API de Pagamentos do Mercado Pago (Pix).

Referências (documentação oficial do Mercado Pago):
- POST /v1/payments com payment_method_id="pix" e cabeçalho X-Idempotency-Key
- GET  /v1/payments/{id}
- PUT  /v1/payments/{id} {"status": "cancelled"} para cancelar cobranças pendentes
- GET  /v1/payments/search?external_reference=...
- Webhooks assinados com o cabeçalho x-signature (HMAC-SHA256)
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from .base import CreatePixRequest, ProviderError, ProviderPayment


def _to_cents(value: Any) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def format_mp_datetime(dt: datetime) -> str:
    """Formato aceito pelo MP: yyyy-MM-dd'T'HH:mm:ss.SSS±HH:MM"""
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}+00:00"


def parse_payment(data: dict[str, Any]) -> ProviderPayment:
    tx = ((data.get("point_of_interaction") or {}).get("transaction_data")) or {}
    return ProviderPayment(
        id=str(data["id"]),
        status=str(data.get("status", "")),
        status_detail=str(data.get("status_detail") or ""),
        amount_cents=_to_cents(data.get("transaction_amount", 0)),
        external_reference=str(data.get("external_reference") or ""),
        live_mode=bool(data.get("live_mode", False)),
        qr_code=tx.get("qr_code") or "",
        qr_code_base64=tx.get("qr_code_base64") or "",
        ticket_url=tx.get("ticket_url") or "",
        expires_at=_parse_dt(data.get("date_of_expiration")),
        raw={
            k: data.get(k)
            for k in (
                "id", "status", "status_detail", "transaction_amount", "external_reference",
                "live_mode", "date_created", "date_approved", "date_last_updated",
                "date_of_expiration", "payment_method_id",
            )
        },
    )


def split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


class MercadoPagoProvider:
    name = "mercadopago"

    def __init__(self, access_token: str, api_base: str = "https://api.mercadopago.com",
                 client: httpx.Client | None = None, timeout: float = 15.0):
        self._token = access_token
        self._client = client or httpx.Client(base_url=api_base, timeout=timeout)

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        if idempotency_key:
            h["X-Idempotency-Key"] = idempotency_key
        return h

    def _request(self, method: str, path: str, **kw) -> dict[str, Any]:
        try:
            resp = self._client.request(method, path, **kw)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Falha de comunicação com o Mercado Pago: {exc}") from exc
        if resp.status_code >= 400:
            retriable = resp.status_code >= 500 or resp.status_code == 429
            raise ProviderError(
                f"Mercado Pago respondeu {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
                retriable=retriable,
            )
        return resp.json()

    def create_pix(self, req: CreatePixRequest) -> ProviderPayment:
        first, last = split_name(req.payer.full_name)
        payer: dict[str, Any] = {"email": req.payer.email, "first_name": first, "last_name": last}
        if req.payer.cpf:
            payer["identification"] = {"type": "CPF", "number": req.payer.cpf}
        body: dict[str, Any] = {
            "transaction_amount": float(Decimal(req.amount_cents) / 100),
            "description": req.description[:250],
            "payment_method_id": "pix",
            "external_reference": req.external_reference,
            "date_of_expiration": format_mp_datetime(req.expires_at),
            "payer": payer,
        }
        if req.notification_url:
            body["notification_url"] = req.notification_url
        data = self._request("POST", "/v1/payments", json=body, headers=self._headers(req.idempotency_key))
        return parse_payment(data)

    def get_payment(self, payment_id: str) -> ProviderPayment:
        return parse_payment(self._request("GET", f"/v1/payments/{payment_id}", headers=self._headers()))

    def cancel_payment(self, payment_id: str) -> ProviderPayment:
        data = self._request(
            "PUT", f"/v1/payments/{payment_id}", json={"status": "cancelled"}, headers=self._headers()
        )
        return parse_payment(data)

    def find_by_reference(self, external_reference: str) -> ProviderPayment | None:
        data = self._request(
            "GET",
            "/v1/payments/search",
            params={"external_reference": external_reference, "sort": "date_created", "criteria": "desc"},
            headers=self._headers(),
        )
        results = data.get("results") or []
        return parse_payment(results[0]) if results else None


# ---- Assinatura de webhooks ----------------------------------------------

def build_signature_manifest(data_id: str | None, request_id: str | None, ts: str | None) -> str:
    parts = []
    if data_id:
        did = data_id.lower() if data_id.isalnum() else data_id
        parts.append(f"id:{did};")
    if request_id:
        parts.append(f"request-id:{request_id};")
    if ts:
        parts.append(f"ts:{ts};")
    return "".join(parts)


def parse_signature_header(header: str | None) -> tuple[str | None, str | None]:
    ts = v1 = None
    for part in (header or "").split(","):
        key, _, value = part.strip().partition("=")
        if key == "ts":
            ts = value
        elif key == "v1":
            v1 = value
    return ts, v1


def verify_webhook_signature(secret: str, signature_header: str | None, request_id: str | None,
                             data_id: str | None) -> bool:
    ts, v1 = parse_signature_header(signature_header)
    if not secret or not ts or not v1:
        return False
    manifest = build_signature_manifest(data_id, request_id, ts)
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def sign_for_tests(secret: str, data_id: str, request_id: str, ts: str) -> str:
    manifest = build_signature_manifest(data_id, request_id, ts)
    v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"
