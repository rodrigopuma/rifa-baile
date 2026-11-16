import type { Availability, Campaign, OrderView, Receipt } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function messageFrom(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // erros de validação do FastAPI
    const first = detail[0] as { msg?: string } | undefined;
    return first?.msg?.replace(/^Value error, /, "") ?? fallback;
  }
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: string }).message);
  return fallback;
}

export async function request<T>(path: string, init: RequestInit & { token?: string; orderToken?: string } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (init.token) headers.set("Authorization", `Bearer ${init.token}`);
  if (init.orderToken) headers.set("X-Order-Token", init.orderToken);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Sem conexão com o servidor. Verifique sua internet e tente novamente.", null);
  }
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* corpo vazio */
    }
    throw new ApiError(res.status, messageFrom(detail, `Erro ${res.status}`), detail);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.blob()) as Promise<T>;
}

export const api = {
  campaign: () => request<Campaign>("/api/campaign"),
  availability: () => request<Availability>("/api/campaign/availability"),
  createOrder: (body: unknown) =>
    request<{ order: OrderView; access_token: string }>("/api/orders", { method: "POST", body: JSON.stringify(body) }),
  order: (id: string, token: string) => request<OrderView>(`/api/orders/${id}`, { orderToken: token }),
  checkoutTimeout: (id: string, token: string) =>
    request<OrderView>(`/api/orders/${id}/checkout-timeout`, { method: "POST", orderToken: token }),
  receipt: (id: string, token: string) => request<Receipt>(`/api/receipts/${id}`, { orderToken: token }),
  simulate: (paymentId: string, action: "approve" | "reject" | "expire") =>
    request<unknown>(`/api/dev/simulator/payments/${paymentId}/${action}`, { method: "POST" }),
};
