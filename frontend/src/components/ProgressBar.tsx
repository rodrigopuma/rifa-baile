export function ProgressBar({ value, total }: { value: number; total: number }) {
  const pct = total ? Math.min(100, Math.round((value / total) * 100)) : 0;
  return (
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
  );
}
