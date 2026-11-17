const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
export const money = (cents: number) => brl.format(cents / 100);

/** Preenche com zeros conforme o total de números (ex.: 007 para 300 números). */
export const padNumber = (n: number, total: number) => String(n).padStart(Math.max(2, String(total).length), "0");

const TZ = "America/Recife";
export const dateTime = (iso: string) =>
  new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: TZ }).format(new Date(iso));
export const dateLong = (iso: string) =>
  new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "long", year: "numeric", timeZone: "UTC" }).format(
    new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso),
  );

export const digits = (v: string) => v.replace(/\D+/g, "");

export function maskPhone(v: string): string {
  const d = digits(v).slice(0, 11);
  if (d.length <= 2) return d.length ? `(${d}` : "";
  if (d.length <= 7) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

export function maskCpf(v: string): string {
  const d = digits(v).slice(0, 11);
  return d
    .replace(/^(\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
}

export function isValidCpf(v: string): boolean {
  const cpf = digits(v);
  if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;
  for (const size of [9, 10]) {
    let total = 0;
    for (let i = 0; i < size; i++) total += Number(cpf[i]) * (size + 1 - i);
    if (((total * 10) % 11) % 10 !== Number(cpf[size])) return false;
  }
  return true;
}

export const isValidPhone = (v: string) => {
  const d = digits(v);
  return d.length === 11 && d[2] === "9" && d[0] !== "0";
};

export const isValidEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());

/** "24 h", "90 min"… para prazos em minutos. */
export function durationLabel(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = minutes / 60;
  return Number.isInteger(h) ? `${h} h` : `${Math.round(h * 10) / 10} h`.replace(".", ",");
}

/** "há 3 h", "há 25 min", "há 2 dias" a partir de um instante ISO. */
export function ago(iso: string, now = Date.now()): string {
  const min = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.floor(min / 60);
  return h < 48 ? `há ${h} h` : `há ${Math.floor(h / 24)} dias`;
}

/** Total do pedido com pacote (espelha services/pricing.py): a cada `bundleSize` números, o grupo custa `bundlePrice`. */
export function orderTotal(unit: number, bundleSize: number, bundlePrice: number, qty: number): number {
  if (bundleSize >= 2 && bundlePrice > 0) {
    return Math.floor(qty / bundleSize) * bundlePrice + (qty % bundleSize) * unit;
  }
  return qty * unit;
}
