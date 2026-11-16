import { useCallback, useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";

const DEV_KEY = "rifa:admin-dev-token";
export const devTokenAllowed = !supabase && import.meta.env.VITE_ALLOW_DEV_TOKEN === "true";

/** Sessão administrativa via Supabase Auth (ou token de desenvolvimento, quando permitido). */
export function useAdminAuth() {
  const [token, setToken] = useState<string | null>(() =>
    devTokenAllowed ? sessionStorage.getItem(DEV_KEY) : null,
  );
  const [ready, setReady] = useState(!supabase);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token ?? null);
      setReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) => setToken(session?.access_token ?? null));
    return () => sub.subscription.unsubscribe();
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabase) throw new Error("Supabase não configurado.");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error("E-mail ou senha incorretos.");
  }, []);

  const setDevToken = useCallback((t: string) => {
    sessionStorage.setItem(DEV_KEY, t.trim());
    setToken(t.trim());
  }, []);

  const signOut = useCallback(async () => {
    sessionStorage.removeItem(DEV_KEY);
    if (supabase) await supabase.auth.signOut();
    setToken(null);
  }, []);

  return { token, ready, signIn, signOut, setDevToken };
}
