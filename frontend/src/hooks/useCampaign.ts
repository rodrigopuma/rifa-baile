import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Campaign } from "../lib/types";

const POLL_MS = 20_000;

/**
 * Carrega a campanha e mantém a disponibilidade atualizada:
 * - Supabase Realtime (tabela pública number_availability), quando configurado;
 * - consulta periódica e ao voltar para a aba, como reserva.
 */
export function useCampaign() {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [unavailable, setUnavailable] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const [c, a] = await Promise.all([api.campaign(), api.availability()]);
      if (!mounted.current) return;
      setCampaign(c);
      setUnavailable(new Set(a.unavailable));
      setError(null);
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : "Erro ao carregar a campanha.");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    refresh();
    const timer = window.setInterval(refresh, POLL_MS);
    const onVisible = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);

  const campaignId = campaign?.id;
  useEffect(() => {
    if (!campaignId || !import.meta.env.VITE_SUPABASE_URL) return;
    let cleanup: (() => void) | undefined;
    let cancelled = false;
    // Carregado sob demanda: mantém o pacote inicial leve.
    import("../lib/supabase").then(({ supabase }) => {
      if (!supabase || cancelled) return;
      const channel = supabase
        .channel(`disponibilidade-${campaignId}`)
        .on(
          "postgres_changes",
          { event: "*", schema: "public", table: "number_availability", filter: `campaign_id=eq.${campaignId}` },
          (payload) => {
            const row = payload.new as { number?: number; available?: boolean } | undefined;
            if (!row || typeof row.number !== "number") return;
            const n = row.number;
            setUnavailable((prev) => {
              if (row.available === !prev.has(n)) return prev;
              const next = new Set(prev);
              if (row.available) next.delete(n);
              else next.add(n);
              return next;
            });
          },
        )
        .subscribe((status) => setLive(status === "SUBSCRIBED"));
      cleanup = () => void supabase.removeChannel(channel);
    });
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [campaignId]);

  const availableCount = campaign ? campaign.total_numbers - unavailable.size : 0;
  return { campaign, unavailable, availableCount, loading, error, refresh, live };
}
