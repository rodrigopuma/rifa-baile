/** Linha cerimonial fina em prata com losango central. */
export function Divider({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-3 ${className}`} aria-hidden="true">
      <div className="filete-prata flex-1" />
      <div className="h-1.5 w-1.5 rotate-45 border border-prata bg-marfim" />
      <div className="filete-prata flex-1" />
    </div>
  );
}
