"""Aplica o arquivo único de configuração (campanha.json + REGULAMENTO.md) ao banco.

- É idempotente: guarda o hash do conteúdo aplicado no audit_log e só reaplica quando o
  arquivo muda (ou quando chamado com force=True). Assim, ajustes feitos no painel valem
  até a próxima alteração do arquivo.
- Atualiza a campanha ativa (ou a mais recente não encerrada); se não houver, cria uma.
- Respeita as travas do sistema: preço não muda depois do primeiro pedido e a quantidade
  só diminui se os números removidos estiverem livres.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AuditLog, Campaign, Order
from ..schemas import CampaignSettingsIn
from . import audit
from .campaigns import create_numbers, resize_numbers

log = logging.getLogger("rifa.config")


class CampaignConfigError(Exception):
    pass


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]
EXTENSO = {1: "último algarismo", 2: "dois últimos algarismos", 3: "três últimos algarismos",
           4: "quatro últimos algarismos", 5: "cinco últimos algarismos"}


def brl(cents: int) -> str:
    inteiro, centavos = divmod(cents, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{centavos:02d}"


def data_extenso(d: date | None) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}" if d else "a definir"


def draw_rule(total: int) -> tuple[str, str]:
    """Regra verificável a partir do 1º prêmio da Loteria Federal (5 algarismos)."""
    k = max(1, len(str(total - 1)) if total > 1 else 1)
    while 10 ** k < total:
        k += 1
    width = len(str(total))
    pad = lambda n: str(n).zfill(max(2, width))  # noqa: E731
    exemplo_premio = 45637
    final = exemplo_premio % (10 ** k)
    if (10 ** k) % total == 0:
        regra = (f"Toma-se o número formado pelos {EXTENSO[k]} do 1º prêmio e calcula-se o resto da "
                 f"divisão desse número por {total}. Se o resto for zero, o número ganhador é o {pad(total)}; "
                 f"caso contrário, o número ganhador é o próprio resto. Como {10 ** k} é múltiplo de {total}, "
                 f"todos os números têm exatamente a mesma chance.")
        r = final % total
        ganhador = total if r == 0 else r
        exemplo = (f"se o 1º prêmio for 45.637, os {EXTENSO[k]} formam {str(final).zfill(k)}; "
                   f"{final} dividido por {total} deixa resto {r}; o número ganhador é o {pad(ganhador)}.")
    else:
        regra = (f"O número ganhador é o formado pelos {EXTENSO[k]} do 1º prêmio. Se esse número for "
                 f"zero ou maior que {total}, aplica-se o item 5.4 como se o número não tivesse sido vendido.")
        exemplo = (f"se o 1º prêmio for 45.637, o número formado é {str(final).zfill(k)}"
                   + (f", que corresponde ao número {pad(final)}." if 0 < final <= total
                      else f", fora do intervalo; passa-se ao 2º prêmio."))
    return regra, exemplo


def load(path: Path | None = None) -> tuple[dict[str, Any], str, str]:
    """Lê campanha.json e o regulamento. Retorna (config, regulamento_renderizado, hash)."""
    path = path or get_settings().resolved_campaign_config_path
    if not path.exists():
        raise CampaignConfigError(f"Arquivo de configuração não encontrado: {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CampaignConfigError(f"campanha.json inválido (linha {exc.lineno}): {exc.msg}") from exc
    reg_name = cfg.get("regulamento") or "REGULAMENTO.md"
    reg_path = (path.parent / reg_name)
    reg_raw = reg_path.read_text(encoding="utf-8") if reg_path.exists() else ""
    digest = hashlib.sha256((raw + "\n--\n" + reg_raw).encode()).hexdigest()
    return cfg, render_regulation(cfg, reg_raw), digest


def _campaign_fields(cfg: dict[str, Any], regulation: str) -> dict[str, Any]:
    c, o = cfg.get("campanha", {}), cfg.get("organizador", {})
    contato = []
    if o.get("whatsapp"):
        contato.append(f"WhatsApp {o['whatsapp']}")
    if o.get("instagram"):
        contato.append(f"Instagram @{str(o['instagram']).lstrip('@')}")
    try:
        price_cents = round(float(c.get("preco_reais", 0)) * 100)
        total = int(c.get("quantidade_numeros", 0))
    except (TypeError, ValueError) as exc:
        raise CampaignConfigError("preco_reais e quantidade_numeros devem ser números") from exc
    draw = c.get("data_sorteio") or None
    try:
        settings_in = CampaignSettingsIn(
            name=c.get("nome", "Rifa Solidária"),
            subtitle=c.get("subtitulo", ""),
            description=c.get("descricao", ""),
            prize_title=c.get("premio", ""),
            price_cents=price_cents,
            total_numbers=total,
            draw_date=draw,
            organizer_name=o.get("nome", ""),
            organizer_contact=" · ".join(contato),
            regulation_text=regulation,
            authorization_info=c.get("autorizacao", ""),
            header_image_url=c.get("imagem_cabecalho_url", ""),
        )
    except ValidationError as exc:
        erros = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise CampaignConfigError(f"Valores inválidos em campanha.json: {erros}") from exc
    status = c.get("status", "active")
    if status not in ("draft", "active", "paused", "closed"):
        raise CampaignConfigError("status deve ser active, paused, closed ou draft")
    return {**settings_in.model_dump(), "status": status}


def render_regulation(cfg: dict[str, Any], template: str) -> str:
    s = get_settings()
    c, o, site = cfg.get("campanha", {}), cfg.get("organizador", {}), cfg.get("site", {})
    total = int(c.get("quantidade_numeros") or 1)
    width = max(2, len(str(total)))
    try:
        d = date.fromisoformat(c["data_sorteio"]) if c.get("data_sorteio") else None
    except ValueError:
        d = None
    regra, exemplo = draw_rule(total)
    contato = [f"WhatsApp {o['whatsapp']}"] if o.get("whatsapp") else []
    if o.get("instagram"):
        contato.append(f"Instagram @{str(o['instagram']).lstrip('@')}")
    values = {
        "nome": c.get("nome", ""),
        "subtitulo": c.get("subtitulo", ""),
        "organizador": o.get("nome", ""),
        "apresentacao": o.get("apresentacao", ""),
        "quantidade": str(total),
        "primeiro_numero": "1".zfill(width),
        "ultimo_numero": str(total).zfill(width),
        "preco": brl(round(float(c.get("preco_reais", 0)) * 100)),
        "premio": c.get("premio", ""),
        "data_sorteio": data_extenso(d),
        "regra_sorteio": regra,
        "exemplo_sorteio": exemplo,
        "limite_por_pedido": str(s.max_numbers_per_order),
        "prazo_checkout": str(s.checkout_window_minutes),
        "prazo_pix": str(s.pix_expiration_minutes),
        "site": site.get("endereco", ""),
        "contato": " · ".join(contato) or "pelos canais do organizador",
    }
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    return out.strip()


def last_applied_hash(db: Session) -> str | None:
    row = db.execute(
        select(AuditLog).where(AuditLog.action == "campaign_config_applied").order_by(AuditLog.id.desc()).limit(1)
    ).scalar_one_or_none()
    return (row.details or {}).get("hash") if row else None


def apply(db: Session, cfg: dict[str, Any], regulation: str, digest: str, *, force: bool = False,
          actor_type: str = "system") -> dict[str, Any]:
    if not force and last_applied_hash(db) == digest:
        return {"applied": False, "reason": "sem alterações"}
    fields = _campaign_fields(cfg, regulation)
    status = fields.pop("status")
    total = fields.pop("total_numbers")

    campaign = db.execute(select(Campaign).where(Campaign.status == "active")).scalar_one_or_none()
    if campaign is None:
        campaign = db.execute(
            select(Campaign).where(Campaign.status.in_(("draft", "paused"))).order_by(Campaign.updated_at.desc())
        ).scalars().first()

    created = False
    if campaign is None:
        campaign = Campaign(status="draft", total_numbers=total, **fields)
        db.add(campaign)
        db.flush()
        create_numbers(db, campaign.id, 1, total)
        created = True
    else:
        has_orders = db.execute(
            select(func.count()).select_from(Order).where(Order.campaign_id == campaign.id)
        ).scalar_one()
        if has_orders and fields["price_cents"] != campaign.price_cents:
            db.rollback()
            raise CampaignConfigError(
                f"O preço não pode mudar depois do primeiro pedido (atual: {brl(campaign.price_cents)}). "
                "Volte o valor de preco_reais no campanha.json."
            )
        try:
            resize_numbers(db, campaign, total)
        except HTTPException as exc:
            db.rollback()
            raise CampaignConfigError(str(exc.detail)) from exc
        for k, v in fields.items():
            setattr(campaign, k, v)

    campaign.status = status
    audit.log(db, "campaign_config_applied", actor_type=actor_type, entity_type="campaign",
              entity_id=campaign.id, details={"hash": digest, "created": created, "status": status,
                                              "total_numbers": total, "price_cents": fields["price_cents"]})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CampaignConfigError("Já existe outra campanha ativa. Encerre-a no painel antes.") from exc
    return {"applied": True, "created": created, "campaign_id": str(campaign.id), "status": status,
            "total_numbers": total, "price_cents": fields["price_cents"]}


def apply_from_file(db: Session, *, force: bool = False, path: Path | None = None) -> dict[str, Any]:
    cfg, regulation, digest = load(path)
    return apply(db, cfg, regulation, digest, force=force)
