import { describe, expect, it } from "vitest";
import { durationLabel } from "../lib/format";
import { whatsappLink } from "../lib/brand";

describe("modo manual", () => {
  it("formata o prazo da reserva", () => {
    expect(durationLabel(1440)).toBe("24 h");
    expect(durationLabel(90)).toBe("1,5 h");
    expect(durationLabel(45)).toBe("45 min");
  });

  it("monta o link do WhatsApp com a mensagem pronta e acentos codificados", () => {
    const link = whatsappLink("Olá! Pedido RF-1, números 007");
    expect(link.startsWith("https://wa.me/55")).toBe(true);
    expect(link).toContain("?text=");
    expect(decodeURIComponent(link.split("?text=")[1])).toBe("Olá! Pedido RF-1, números 007");
    expect(whatsappLink()).not.toContain("?text=");
  });
});

import { ago, orderTotal } from "../lib/format";

describe("pacote e tempo", () => {
  it("orderTotal aplica o pacote a cada grupo de 3", () => {
    const t = (q: number) => orderTotal(1000, 3, 2500, q);
    expect([0, 1, 2, 3, 4, 5, 6, 7].map(t)).toEqual([0, 1000, 2000, 2500, 3500, 4500, 5000, 6000]);
    expect(orderTotal(1000, 0, 0, 4)).toBe(4000);
  });
  it("ago descreve o tempo decorrido", () => {
    const now = Date.parse("2026-12-01T12:00:00Z");
    expect(ago("2026-12-01T11:58:00Z", now)).toBe("há 2 min");
    expect(ago("2026-12-01T09:00:00Z", now)).toBe("há 3 h");
    expect(ago("2026-11-28T12:00:00Z", now)).toBe("há 3 dias");
  });
});

import { normalizePixKey, pixBrCode } from "../lib/pix";

describe("pix copia e cola", () => {
  it("normaliza a chave", () => {
    expect(normalizePixKey("81986302122", "Celular")).toBe("+5581986302122");
    expect(normalizePixKey("529.982.247-25", "CPF")).toBe("52998224725");
    expect(normalizePixKey("a@b.com", "E-mail")).toBe("a@b.com");
  });
  it("gera BR Code válido (estrutura e CRC)", () => {
    const code = pixBrCode({ key: "81986302122", type: "Celular", name: "Luiz Rodrigo Puma Lima", city: "Recife", amountCents: 2500, txid: "AB12CD" });
    expect(code.startsWith("000201")).toBe(true);
    expect(code).toContain("0014br.gov.bcb.pix0114+5581986302122");
    expect(code).toContain("540525.00");
    expect(code).toContain("5922Luiz Rodrigo Puma Lima");
    expect(code).toContain("6006Recife");
    // CRC16-CCITT dos dados + "6304" bate com os 4 últimos caracteres
    const body = code.slice(0, -4);
    let crc = 0xffff;
    for (const ch of body) { crc ^= ch.charCodeAt(0) << 8; for (let i = 0; i < 8; i++) crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff; }
    expect(code.slice(-4)).toBe(crc.toString(16).toUpperCase().padStart(4, "0"));
  });
});
