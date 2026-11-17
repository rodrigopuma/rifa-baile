"""Configuração via variáveis de ambiente (ver .env.example)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PaymentMode = Literal["simulator", "manual_pix", "mercadopago_test", "mercadopago_live"]

# Frase exigida para habilitar cobranças reais. Serve como trava consciente:
# só deve ser preenchida depois de verificada a autorização legal da modalidade
# e a aceitação pelo Mercado Pago.
LIVE_ACK_PHRASE = "AUTORIZACAO_LEGAL_E_MERCADO_PAGO_VERIFICADAS"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # Banco (Supabase PostgreSQL). Use a connection string do pooler em modo "session"
    # ou a conexão direta, com o driver psycopg: postgresql+psycopg://...
    database_url: str = "sqlite:///./rifa_dev.db"

    # URLs públicas
    public_base_url: str = "http://localhost:8000"   # base pública da API (webhooks)
    frontend_url: str = "http://localhost:5173"      # usada nos links de comprovante
    cors_origins: str = "http://localhost:5173"

    # Supabase Auth (painel administrativo)
    supabase_url: str = ""
    supabase_jwt_secret: str = ""          # projetos com chave HS256 (legado)
    supabase_jwt_audience: str = "authenticated"

    # Pagamentos
    payment_mode: PaymentMode = "simulator"
    mp_access_token: str = ""
    mp_webhook_secret: str = ""
    mp_api_base: str = "https://api.mercadopago.com"
    live_payments_acknowledgement: str = ""
    payer_cpf_required: bool = True        # Pix no Mercado Pago normalmente exige CPF do pagador

    # Prazos
    checkout_window_minutes: int = 15      # contador visual exibido ao participante
    pix_expiration_minutes: int = 30       # vencimento enviado ao Mercado Pago (mínimo 30)
    orphan_order_grace_seconds: int = 120
    # Modo manual (PAYMENT_MODE=manual_pix): por quanto tempo os números ficam reservados
    # esperando o participante pagar e o organizador confirmar.
    manual_hold_minutes: int = 1440
    # Aviso no celular a cada nova reserva (app ntfy). Vazio = desligado. O tópico funciona como senha: use algo longo e aleatório.
    ntfy_topic: str = ""
    ntfy_server: str = "https://ntfy.sh"

    # Limites
    max_numbers_per_order: int = 50
    max_pending_orders_per_contact: int = 2
    order_rate_limit_per_10min: int = 8

    # Arquivo único de configuração da campanha (campanha.json na raiz do repositório)
    campaign_config_path: str = ""
    auto_apply_campaign_config: bool = True

    # Segredo para o endpoint /api/cron/reconcile (agendador externo, opcional)
    cron_secret: str = ""

    # Conciliação em segundo plano
    reconcile_interval_seconds: int = 30
    run_background_reconciler: bool = True

    @field_validator("pix_expiration_minutes")
    @classmethod
    def _pix_min(cls, v: int) -> int:
        if v < 30:
            raise ValueError("PIX_EXPIRATION_MINUTES deve ser >= 30 (mínimo do Mercado Pago)")
        return v

    @model_validator(mode="after")
    def _guards(self) -> "Settings":
        if self.checkout_window_minutes > self.pix_expiration_minutes:
            raise ValueError("CHECKOUT_WINDOW_MINUTES não pode ser maior que PIX_EXPIRATION_MINUTES")
        if self.manual_hold_minutes < 15:
            raise ValueError("MANUAL_HOLD_MINUTES deve ser >= 15")
        if self.payment_mode in ("mercadopago_test", "mercadopago_live"):
            if not self.mp_access_token:
                raise ValueError("MP_ACCESS_TOKEN é obrigatório nos modos Mercado Pago")
            if not self.mp_webhook_secret:
                raise ValueError("MP_WEBHOOK_SECRET é obrigatório nos modos Mercado Pago")
        if self.payment_mode == "mercadopago_live":
            if self.live_payments_acknowledgement != LIVE_ACK_PHRASE:
                raise ValueError(
                    "Cobranças reais bloqueadas. Defina LIVE_PAYMENTS_ACKNOWLEDGEMENT somente após "
                    "verificar a autorização legal da modalidade e a aceitação pelo Mercado Pago."
                )
            if not self.public_base_url.startswith("https://"):
                raise ValueError("Em produção, PUBLIC_BASE_URL deve usar HTTPS")
        if self.environment == "production" and self.payment_mode == "simulator":
            raise ValueError("O simulador não pode ser usado com ENVIRONMENT=production")
        return self

    @property
    def resolved_campaign_config_path(self) -> "Path":
        if self.campaign_config_path:
            return Path(self.campaign_config_path).resolve()
        return Path(__file__).resolve().parents[2] / "campanha.json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_live(self) -> bool:
        return self.payment_mode == "mercadopago_live"

    @property
    def is_manual(self) -> bool:
        """Pix direto na chave do organizador; ele confirma cada pagamento no painel."""
        return self.payment_mode == "manual_pix"

    @property
    def public_payment_mode(self) -> str:
        return {"simulator": "simulator", "manual_pix": "manual", "mercadopago_test": "test",
                "mercadopago_live": "live"}[self.payment_mode]


@lru_cache
def get_settings() -> Settings:
    return Settings()
