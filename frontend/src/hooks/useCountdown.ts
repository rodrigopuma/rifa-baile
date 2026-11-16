import { useEffect, useMemo, useState } from "react";

/** Contagem regressiva sincronizada com o relógio do servidor. */
export function useCountdown(expiresAtIso: string | undefined, serverTimeIso: string | undefined) {
  const offset = useMemo(
    () => (serverTimeIso ? new Date(serverTimeIso).getTime() - Date.now() : 0),
    [serverTimeIso],
  );
  const target = expiresAtIso ? new Date(expiresAtIso).getTime() : 0;
  const calc = () => Math.max(0, Math.floor((target - (Date.now() + offset)) / 1000));
  const [seconds, setSeconds] = useState(calc);

  useEffect(() => {
    setSeconds(calc());
    if (!target) return;
    const t = window.setInterval(() => setSeconds(calc()), 500);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, offset]);

  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return { seconds, label: `${mm}:${ss}`, done: !!target && seconds === 0 };
}
