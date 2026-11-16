import { request } from "../../lib/api";

export interface AdminOrder {
  id: string;
  code: string;
  status: string;
  numbers: number[];
  quantity: number;
  total_cents: number;
  created_at: string;
  paid_at: string | null;
  checkout_expires_at: string;
  cancel_requested_at: string | null;
  review_reason: string;
  participant: { id: string; full_name: string; email: string; phone: string; cpf_masked: string };
  payment: AdminPayment | null;
}

export interface AdminPayment {
  id: string;
  order_id: string;
  order_code?: string;
  provider: string;
  provider_payment_id: string;
  status: string;
  provider_status: string;
  status_detail: string;
  amount_cents: number;
  live_mode: boolean;
  created_at: string;
  approved_at: string | null;
  last_synced_at: string | null;
  expires_at: string | null;
}

export interface Overview {
  campaign: { id: string; name: string; status: string; total_numbers: number; price_cents: number };
  numbers: { available: number; reserved: number; paid: number };
  gross_cents: number;
  orders_by_status: Record<string, number>;
  pending_payments: number;
  payment_mode: string;
}

export interface AdminCampaign {
  id: string;
  name: string;
  subtitle: string;
  description: string;
  prize_title: string;
  price_cents: number;
  total_numbers: number;
  draw_date: string | null;
  organizer_name: string;
  organizer_contact: string;
  regulation_text: string;
  authorization_info: string;
  header_image_url: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AuditEntry {
  id: number;
  created_at: string;
  actor_type: string;
  actor_id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
}

export interface ParticipantRow {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  paid_numbers: number[];
  reserved_numbers: number[];
  orders: { code: string; status: string }[];
}

const qs = (o: Record<string, string | number | undefined>) =>
  new URLSearchParams(Object.entries(o).filter(([, v]) => v !== undefined && v !== "") as [string, string][]).toString();

export function adminApi(token: string) {
  const r = <T,>(path: string, init: RequestInit = {}) => request<T>(path, { ...init, token });
  return {
    me: () => r<{ id: string; email: string; name: string }>("/api/admin/me"),
    overview: () => r<Overview>("/api/admin/overview"),
    orders: (q: string, status?: string, page = 1) =>
      r<{ total: number; page: number; items: AdminOrder[] }>(`/api/admin/orders?${qs({ q, status, page })}`),
    participants: (q: string) => r<{ total: number; items: ParticipantRow[] }>(`/api/admin/participants?${qs({ q })}`),
    payments: (status?: string, page = 1) =>
      r<{ total: number; items: AdminPayment[] }>(`/api/admin/payments?${qs({ status, page })}`),
    syncPayment: (id: string) => r<AdminPayment>(`/api/admin/payments/${id}/sync`, { method: "POST" }),
    cancelOrder: (id: string) => r<AdminOrder>(`/api/admin/orders/${id}/cancel`, { method: "POST" }),
    audit: (page = 1) => r<{ items: AuditEntry[] }>(`/api/admin/audit-logs?${qs({ page })}`),
    campaigns: () => r<{ items: AdminCampaign[] }>("/api/admin/campaigns"),
    createCampaign: (body: unknown) => r<AdminCampaign>("/api/admin/campaigns", { method: "POST", body: JSON.stringify(body) }),
    updateCampaign: (id: string, body: unknown) =>
      r<AdminCampaign>(`/api/admin/campaigns/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    setStatus: (id: string, status: string) =>
      r<AdminCampaign>(`/api/admin/campaigns/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
    exportCsv: () => r<Blob>("/api/admin/export.csv"),
  };
}

export type AdminApi = ReturnType<typeof adminApi>;

export const ORDER_STATUS: Record<string, string> = {
  pending: "Pendente",
  paid: "Pago",
  cancelled: "Cancelado",
  expired: "Expirado",
  refunded: "Reembolsado",
  in_review: "Em análise",
};
export const PAYMENT_STATUS: Record<string, string> = {
  pending: "Pendente",
  approved: "Aprovado",
  cancelled: "Cancelado",
  expired: "Expirado",
  refunded: "Reembolsado",
  in_review: "Em análise",
  rejected: "Recusado",
};
export const STATUS_STYLE: Record<string, string> = {
  pending: "bg-[#FBF5E6] text-alerta border-[#ecdcb4]",
  paid: "bg-oliva-50 text-oliva border-oliva/25",
  approved: "bg-oliva-50 text-oliva border-oliva/25",
  cancelled: "bg-neutro text-tunica border-linha",
  expired: "bg-neutro text-tunica border-linha",
  rejected: "bg-neutro text-tunica border-linha",
  refunded: "bg-[#EEF0F4] text-[#46506a] border-[#d5dae5]",
  in_review: "bg-[#FBEFED] text-erro border-[#efcdc8]",
};
