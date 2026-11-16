import { money, padNumber } from "../lib/format";

interface Props {
  selected: number[];
  total: number;
  priceCents: number;
  onClear: () => void;
  onContinue: () => void;
  disabled?: boolean;
}

/** Barra fixa com o resumo da seleção e o botão de continuar. */
export function SelectionSummary({ selected, total, priceCents, onClear, onContinue, disabled }: Props) {
  const count = selected.length;
  return (
    <div className="nao-imprimir sticky bottom-0 z-20 -mx-4 mt-6 border-t border-linha bg-marfim/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur sm:mx-0 sm:rounded-t-lg sm:border-x">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="min-w-0" aria-live="polite">
          <p className="text-[13px] text-tunica">
            {count === 0 ? "Nenhum número escolhido" : count === 1 ? "1 número escolhido" : `${count} números escolhidos`}
          </p>
          <p className="font-numeral text-2xl leading-tight text-militar">{money(count * priceCents)}</p>
        </div>
        <button className="botao w-full min-[460px]:w-auto" onClick={onContinue} disabled={disabled || count === 0}>
          Continuar para pagamento
        </button>
      </div>
      {count > 0 ? (
        <div className="mt-2 flex items-start gap-2">
          <div className="flex max-h-16 flex-1 flex-wrap gap-1.5 overflow-y-auto">
            {selected.map((n) => (
              <span key={n} className="rounded border border-oliva/30 bg-oliva-50 px-1.5 py-0.5 font-numeral text-[13px] text-oliva">
                {padNumber(n, total)}
              </span>
            ))}
          </div>
          <button className="botao-discreto -mr-2 -mt-1 shrink-0" onClick={onClear}>
            Limpar
          </button>
        </div>
      ) : null}
    </div>
  );
}
