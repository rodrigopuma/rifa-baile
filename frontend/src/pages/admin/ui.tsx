import type { ReactNode } from "react";
import { STATUS_STYLE } from "./adminApi";

export function StatusBadge({ status, label }: { status: string; label: string }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[status] ?? "border-linha"}`}>
      {label}
    </span>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="cartao px-4 py-3.5">
      <p className="text-xs uppercase tracking-wider text-tunica">{label}</p>
      <p className="mt-0.5 font-numeral text-2xl text-militar">{value}</p>
      {hint ? <p className="text-xs text-tunica">{hint}</p> : null}
    </div>
  );
}
