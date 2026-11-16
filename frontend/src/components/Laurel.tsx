/** Ramo de louros discreto, em prata. */
export function Laurel({ className = "", mirrored = false }: { className?: string; mirrored?: boolean }) {
  const leaves = Array.from({ length: 6 }, (_, i) => {
    const t = (i + 1) / 7;
    const x = 4 + t * 52;
    const y = 18 - Math.sin(t * Math.PI * 0.9) * 9;
    const angle = -18 - t * 25;
    return { x, y, angle };
  });
  return (
    <svg
      viewBox="0 0 64 28"
      className={className}
      aria-hidden="true"
      style={mirrored ? { transform: "scaleX(-1)" } : undefined}
    >
      <path d="M2 20 Q 30 4 60 9" stroke="currentColor" strokeWidth="1" fill="none" strokeLinecap="round" />
      {leaves.map((l, i) => (
        <g key={i} transform={`translate(${l.x} ${l.y})`}>
          <ellipse cx="0" cy="-4" rx="1.9" ry="4.4" transform={`rotate(${l.angle + 70})`} fill="currentColor" opacity="0.9" />
          <ellipse cx="0" cy="4" rx="1.9" ry="4.4" transform={`rotate(${l.angle + 110})`} fill="currentColor" opacity="0.75" />
        </g>
      ))}
    </svg>
  );
}
