import type { PaymentMode } from "../lib/types";

export function TestModeBanner({ mode }: { mode?: PaymentMode }) {
  if (!mode || mode === "live" || mode === "manual") return null;
  return (
    <div role="status" className="bg-[#F4ECD8] px-4 py-1.5 text-center text-[12.5px] font-medium text-alerta">
      {mode === "simulator"
        ? "Ambiente de testes com simulador local — nenhuma cobrança real é realizada."
        : "Ambiente de testes do Mercado Pago — nenhuma cobrança real é realizada."}
    </div>
  );
}
