import type { ReactNode } from "react";

export function Notice({
  tone = "info", children, onClose,
}: { tone?: "info" | "warn" | "error" | "ok"; children: ReactNode; onClose?: () => void }) {
  const styles = {
    info: "border-prata bg-white text-grafite",
    warn: "border-[#e2cf9f] bg-[#FBF5E6] text-alerta",
    error: "border-[#e5b8b3] bg-[#FBEFED] text-erro",
    ok: "border-oliva/30 bg-oliva-50 text-oliva",
  }[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`animar-surgir flex items-start gap-3 rounded-md border px-4 py-3 text-sm ${styles}`}>
      <div className="flex-1 leading-relaxed">{children}</div>
      {onClose ? (
        <button onClick={onClose} className="-my-1 -mr-1 rounded px-2 py-1 text-base leading-none opacity-70 hover:opacity-100" aria-label="Fechar aviso">
          ×
        </button>
      ) : null}
    </div>
  );
}
