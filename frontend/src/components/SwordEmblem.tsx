import { useId } from "react";

/**
 * Espada de oficial em prata, vista lateral, em vetor.
 * Desenho estilizado: pomo ovalado, punho com empunhadura em fio, guarda com arco (copo)
 * e lâmina esguia levemente curva com sulco central. Substitua por um vetor feito a partir
 * da referência correta fornecida pelo organizador, mantendo o mesmo viewBox.
 */
export function SwordEmblem({ className = "" }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  const metal = `metal-${id}`;
  const edge = `fio-${id}`;
  return (
    <svg viewBox="0 0 360 40" className={className} role="img" aria-label="Espada de oficial prateada">
      <defs>
        <linearGradient id={metal} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F4F6F7" />
          <stop offset="0.45" stopColor="#C0C5C9" />
          <stop offset="1" stopColor="#868B8F" />
        </linearGradient>
        <linearGradient id={edge} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#C0C5C9" stopOpacity="0.2" />
          <stop offset="0.5" stopColor="#FFFFFF" stopOpacity="0.85" />
          <stop offset="1" stopColor="#C0C5C9" stopOpacity="0.3" />
        </linearGradient>
      </defs>
      {/* lâmina */}
      <path d="M73 16.6 Q 215 14.9 356 19.2 Q 215 22.6 73 23.4 Z" fill={`url(#${metal})`} />
      <path d="M80 18.4 Q 200 17.1 300 18.7" stroke="#7E8387" strokeWidth="0.7" fill="none" opacity="0.7" />
      <path d="M78 16.9 Q 215 15.4 350 19.1" stroke={`url(#${edge})`} strokeWidth="0.6" fill="none" />
      {/* talão */}
      <path d="M68 15.2 C 72 15.2 75 16.5 75 20 C 75 23.5 72 24.8 68 24.8 Z" fill={`url(#${metal})`} />
      {/* guarda com quillon e arco */}
      <rect x="63" y="11" width="5.5" height="18" rx="2.2" fill={`url(#${metal})`} />
      <path d="M65.7 11.4 C 65.5 7.5 68.5 5.4 71 6.6" stroke={`url(#${metal})`} strokeWidth="2.2" fill="none" strokeLinecap="round" />
      <circle cx="71.4" cy="6.9" r="1.5" fill="#C0C5C9" />
      <path d="M65.6 28.6 C 54 37.5 28 37.5 15.5 25.2" stroke={`url(#${metal})`} strokeWidth="2" fill="none" strokeLinecap="round" />
      {/* punho com empunhadura em fio */}
      <path d="M19 16.8 L 62.5 15.6 L 62.5 24.4 L 19 23.2 Z" fill="#5F6468" />
      <g stroke="#C0C5C9" strokeWidth="0.8" opacity="0.85">
        {Array.from({ length: 11 }, (_, i) => {
          const x = 21 + i * 3.9;
          return <line key={i} x1={x} y1="23.3" x2={x + 3} y2="16.6" />;
        })}
      </g>
      <rect x="17.5" y="16" width="3" height="8" rx="1" fill={`url(#${metal})`} />
      <rect x="60.5" y="15" width="3" height="10" rx="1" fill={`url(#${metal})`} />
      {/* pomo */}
      <ellipse cx="11.5" cy="20" rx="6.3" ry="5.2" fill={`url(#${metal})`} />
      <circle cx="4.4" cy="20" r="1.7" fill="#C0C5C9" />
    </svg>
  );
}
