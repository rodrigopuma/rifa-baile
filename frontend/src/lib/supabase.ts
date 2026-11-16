import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

/** Cliente Supabase com a chave pública (anon). Null quando não configurado. */
export const supabase: SupabaseClient | null = url && anonKey ? createClient(url, anonKey) : null;
