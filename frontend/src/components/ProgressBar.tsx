interface Goal {
  numbers: number;
  label: string;
}

/** Barra de progresso. Com `goal`, marca a meta (ex.: prêmio maior acima de 100 números) na posição certa. */
export function ProgressBar({ value, total, goal }: { value: number; total: number; goal?: Goal }) {
  const pct = total ? Math.min(100, Math.round((value / total) * 100)) : 0;
  const goalPct = goal && total ? Math.min(100, (goal.numbers / total) * 100) : null;
  return (
    <div className="relative">
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-prata-claro"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label="Números já escolhidos"
      >
        <div className="h-full rounded-full bg-oliva transition-[width] duration-700" style={{ width: `${pct}%` }} />
      </div>
      {goal && goalPct !== null ? (
        <>
          <span
            className="absolute -top-1 h-3.5 w-0.5 -translate-x-1/2 rounded bg-militar"
            style={{ left: `${goalPct}%` }}
            aria-hidden="true"
          />
          <p
            className="mt-1.5 -translate-x-1/2 whitespace-nowrap text-center text-[12px] font-medium text-militar"
            style={{ marginLeft: `${goalPct}%`, width: "max-content" }}
          >
            Meta: {goal.numbers} números · {goal.label}
          </p>
        </>
      ) : null}
    </div>
  );
}
