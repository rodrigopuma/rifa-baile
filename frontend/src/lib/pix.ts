/** Pix "copia e cola" estático (BR Code, EMV) com o valor já preenchido. Sem servidor: tudo calculado no navegador. */

function tlv(id: string, value: string): string {
  return id + String(value.length).padStart(2, "0") + value;
}

function crc16(s: string): string {
  let crc = 0xffff;
  for (let i = 0; i < s.length; i++) {
    crc ^= s.charCodeAt(i) << 8;
    for (let b = 0; b < 8; b++) crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
  }
  return crc.toString(16).toUpperCase().padStart(4, "0");
}

const ascii = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9 .\-]/g, "").trim();

/** Chave no formato aceito pelos bancos: celular com +55, CPF só dígitos, e-mail/aleatória como estão. */
export function normalizePixKey(key: string, type = ""): string {
  const k = key.trim();
  const digits = k.replace(/\D+/g, "");
  const t = type.toLowerCase();
  if (t.startsWith("cel") || t.startsWith("tel")) return `+55${digits}`;
  if (t.startsWith("cpf") || t.startsWith("cnpj")) return digits;
  return k;
}

export function pixBrCode(opts: { key: string; type?: string; name: string; city: string; amountCents: number; txid?: string }): string {
  const key = normalizePixKey(opts.key, opts.type);
  const txid = (opts.txid ?? "").replace(/[^A-Za-z0-9]/g, "").slice(0, 25) || "***";
  const account = tlv("00", "br.gov.bcb.pix") + tlv("01", key);
  const body =
    tlv("00", "01") +
    tlv("26", account) +
    tlv("52", "0000") +
    tlv("53", "986") +
    (opts.amountCents > 0 ? tlv("54", (opts.amountCents / 100).toFixed(2)) : "") +
    tlv("58", "BR") +
    tlv("59", ascii(opts.name).slice(0, 25) || "RIFA") +
    tlv("60", ascii(opts.city).slice(0, 15) || "BRASIL") +
    tlv("62", tlv("05", txid)) +
    "6304";
  return body + crc16(body);
}
