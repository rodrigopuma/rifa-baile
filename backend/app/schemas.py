from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from .config import get_settings
from .validators import is_valid_cpf, normalize_br_phone, only_digits


class OrderCreate(BaseModel):
    numbers: list[int] = Field(min_length=1, max_length=500)
    full_name: str = Field(min_length=5, max_length=160)
    email: EmailStr | None = None  # obrigatório, exceto no modo manual
    phone: str
    cpf: str | None = None
    privacy_consent: bool

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v.split()) < 2:
            raise ValueError("Informe nome e sobrenome")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v else None

    @model_validator(mode="after")
    def _contact_rules(self) -> "OrderCreate":
        manual = get_settings().is_manual
        if not self.email and not manual:
            raise ValueError("E-mail é obrigatório")
        if manual:
            self.cpf = None  # no modo manual não pedimos nem guardamos CPF
        return self

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        p = normalize_br_phone(v)
        if not p:
            raise ValueError("WhatsApp inválido: informe DDD + número de celular")
        return p

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            if get_settings().payer_cpf_required and not get_settings().is_manual:
                raise ValueError("CPF é obrigatório para gerar o Pix")
            return None
        if get_settings().is_manual:
            return None
        if not is_valid_cpf(v):
            raise ValueError("CPF inválido")
        return only_digits(v)

    @field_validator("privacy_consent")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("É necessário concordar com o tratamento dos dados para participar")
        return v


class CampaignSettingsIn(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    subtitle: str = Field(default="", max_length=240)
    description: str = Field(default="", max_length=4000)
    prize_title: str = Field(default="", max_length=200)
    price_cents: int = Field(gt=0, le=10_000_000)
    bundle_size: int = Field(default=0, ge=0, le=100)
    bundle_price_cents: int = Field(default=0, ge=0, le=10_000_000)
    total_numbers: int = Field(gt=0, le=100_000)
    draw_date: date | None = None
    organizer_name: str = Field(default="", max_length=200)
    organizer_contact: str = Field(default="", max_length=200)
    regulation_text: str = Field(default="", max_length=50_000)
    authorization_info: str = Field(default="", max_length=4000)
    header_image_url: str = Field(default="", max_length=500)

    @field_validator("header_image_url")
    @classmethod
    def _img(cls, v: str) -> str:
        v = v.strip()
        if v and not v.startswith("https://"):
            raise ValueError("A imagem deve ser servida por HTTPS")
        return v

    @model_validator(mode="after")
    def _bundle(self) -> "CampaignSettingsIn":
        if self.bundle_size == 0 and self.bundle_price_cents == 0:
            return self
        if self.bundle_size < 2 or self.bundle_price_cents <= 0:
            raise ValueError("Pacote inválido: informe a quantidade (2 ou mais) e o preço do pacote.")
        if self.bundle_price_cents >= self.price_cents * self.bundle_size:
            raise ValueError("O preço do pacote precisa ser menor que a soma dos números avulsos.")
        return self


class CampaignStatusIn(BaseModel):
    status: str = Field(pattern="^(draft|active|paused|closed)$")
