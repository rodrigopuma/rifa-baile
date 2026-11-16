import { memo, useMemo, useState } from "react";
import { padNumber } from "../lib/format";
import { ranges } from "../lib/selection";



interface Props {
  total: number;
  unavailable: Set<number>;
  selected: number[];
  onToggle: (n: number) => void;
  disabled?: boolean;
}

const Cell = memo(function Cell({
  n, label, state, onToggle, disabled,
}: { n: number; label: string; state: "free" | "selected" | "taken"; onToggle: (n: number) => void; disabled?: boolean }) {
  const base =
    "relative flex h-12 items-center justify-center rounded-md border font-numeral text-[17px] tracking-wide " +
    "transition-[background-color,border-color,color,transform] duration-150 select-none";
  const look =
    state === "selected"
      ? "border-oliva bg-oliva text-marfim shadow-[inset_0_0_0_1px_rgba(192,197,201,0.55)] active:scale-[0.97]"
      : state === "taken"
        ? "cursor-not-allowed border-transparent bg-neutro text-[#a4a69d]"
        : "border-linha bg-white text-grafite hover:border-oliva/70 hover:bg-oliva-50 active:scale-[0.97]";
  return (
    <button
      type="button"
      className={`${base} ${look}`}
      aria-pressed={state === "selected"}
      aria-disabled={state === "taken" || disabled}
      aria-label={state === "taken" ? `Número ${label}, indisponível` : `Número ${label}`}
      disabled={state === "taken" || disabled}
      onClick={() => onToggle(n)}
    >
      {label}
    </button>
  );
});

export function NumberGrid({ total, unavailable, selected, onToggle, disabled }: Props) {
  const blocks = useMemo(() => (total > 200 ? ranges(total) : [[1, total] as [number, number]]), [total]);
  const [block, setBlock] = useState(0);
  const [onlyFree, setOnlyFree] = useState(false);
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const [start, end] = blocks[Math.min(block, blocks.length - 1)];

  const cells = [];
  for (let n = start; n <= end; n++) {
    const state = selectedSet.has(n) ? "selected" : unavailable.has(n) ? "taken" : "free";
    if (onlyFree && state === "taken") continue;
    cells.push(<Cell key={n} n={n} label={padNumber(n, total)} state={state} onToggle={onToggle} disabled={disabled} />);
  }

  return (
    <div>
      {blocks.length > 1 ? (
        <div className="-mx-4 mb-3 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0" role="tablist">
          {blocks.map(([a, b], i) => {
            let free = 0;
            for (let n = a; n <= b; n++) if (!unavailable.has(n)) free++;
            const picked = selected.filter((n) => n >= a && n <= b).length;
            return (
              <button
                key={a}
                role="tab"
                aria-selected={i === block}
                onClick={() => setBlock(i)}
                className={`shrink-0 rounded-full border px-3.5 py-1.5 font-numeral text-sm tracking-wide transition ${
                  i === block ? "border-militar bg-militar text-marfim" : "border-linha bg-white text-grafite hover:border-oliva"
                }`}
              >
                {padNumber(a, total)}–{padNumber(b, total)}
                <span className={`ml-1.5 font-sans text-[11px] ${i === block ? "text-prata" : "text-tunica"}`}>
                  {picked ? `${picked} sel.` : `${free} livres`}
                </span>
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="mb-3 flex items-center justify-between gap-3 text-[13px] text-tunica">
        <div className="flex items-center gap-3.5">
          <Legend className="border-linha bg-white" label="Livre" />
          <Legend className="border-oliva bg-oliva" label="Escolhido" />
          <Legend className="border-transparent bg-neutro" label="Indisponível" />
        </div>
        <label className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap">
          <input
            type="checkbox"
            className="h-4 w-4 accent-oliva"
            checked={onlyFree}
            onChange={(e) => setOnlyFree(e.target.checked)}
          />
          Só livres
        </label>
      </div>

      <div className="grid grid-cols-5 gap-2 sm:grid-cols-8 md:grid-cols-10" aria-label="Números da rifa">
        {cells}
      </div>
    </div>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block h-3 w-3 rounded-[3px] border ${className}`} />
      <span className="hidden min-[400px]:inline">{label}</span>
    </span>
  );
}
