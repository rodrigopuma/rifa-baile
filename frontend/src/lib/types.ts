export type PaymentMode = "simulator" | "manual" | "test" | "live";

export interface Campaign {
  id: string;
  name: string;
  subtitle: string;
  description: string;
  prize_title: string;
  price_cents: number;
  /** Pacote: a cada `bundle_size` números o grupo custa `bundle_price_cents` (0 = sem pacote). */
  bundle_size: number;
  bundle_price_cents: number;
  total_numbers: number;
  available_count: number;
  draw_date: string | null;
  organizer_name: string;
  organizer_contact: string;
  regulation_text: string;
  authorization_info: string;
  header_image_url: string;
  status: "draft" | "active" | "paused" | "closed";
  payment_mode: PaymentMode;
  checkout_window_minutes: number;
  max_numbers_per_order: number;
  payer_cpf_required: boolean;
  /** Só no modo manual: por quanto tempo os números ficam reservados. */
  reservation_hold_minutes: number | null;
}

export interface Availability {
  campaign_id: string;
  total_numbers: number;
  unavailable: number[];
  available_count: number;
}

export type OrderDisplayStatus =
  | "awaiting_payment"
  | "awaiting_confirmation"
  | "paid"
  | "cancelled"
  | "expired"
  | "refunded"
  | "in_review";

export interface OrderView {
  id: string;
  code: string;
  status: OrderDisplayStatus;
  numbers: number[];
  quantity: number;
  unit_price_cents: number;
  total_cents: number;
  discount_cents?: number;
  created_at: string;
  checkout_expires_at: string;
  server_time: string;
  participant_first_name: string;
  payment_mode: PaymentMode;
  pix: { qr_code: string; qr_code_base64: string; ticket_url: string } | null;
  simulator_payment_id?: string;
  paid_at?: string | null;
  participant_name?: string;
  paid_cents?: number;
}

export interface Receipt {
  order_id: string;
  code: string;
  status: string;
  participant_name: string;
  numbers: number[];
  total_cents: number;
  paid_at: string | null;
  campaign_name: string;
  total_numbers: number;
  campaign_subtitle: string;
  prize_title: string;
  draw_date: string | null;
  organizer_name: string;
  provider_payment_id: string | null;
  payment_mode: PaymentMode;
}
