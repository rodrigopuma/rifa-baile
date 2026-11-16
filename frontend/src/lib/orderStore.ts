/** Guarda no navegador o token de acesso de cada pedido (necessário para consultar o pedido). */
const KEY = "rifa:pedidos";
const SELECTION_KEY = "rifa:selecao";

type Store = Record<string, { token: string; savedAt: number }>;

function read(): Store {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Store;
  } catch {
    return {};
  }
}

export function saveOrderToken(orderId: string, token: string) {
  try {
    const s = read();
    s[orderId] = { token, savedAt: Date.now() };
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* navegação privada: segue apenas com o link */
  }
}

export function getOrderToken(orderId: string): string | null {
  const fromHash = new URLSearchParams(window.location.hash.slice(1)).get("t");
  if (fromHash) {
    saveOrderToken(orderId, fromHash);
    return fromHash;
  }
  return read()[orderId]?.token ?? null;
}

export function receiptUrl(orderId: string, token: string) {
  // O token vai no fragmento (#): não é enviado a servidores nem aparece em logs.
  return `${window.location.origin}${import.meta.env.BASE_URL}comprovante/${orderId}#t=${encodeURIComponent(token)}`;
}

export function saveSelection(numbers: number[]) {
  try {
    sessionStorage.setItem(SELECTION_KEY, JSON.stringify(numbers));
  } catch {
    /* ignore */
  }
}

export function loadSelection(): number[] {
  try {
    const v = JSON.parse(sessionStorage.getItem(SELECTION_KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((n) => Number.isInteger(n)) : [];
  } catch {
    return [];
  }
}
