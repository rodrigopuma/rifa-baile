import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Notice } from "../../components/Notice";
import { Spinner } from "../../components/Spinner";
import { SwordEmblem } from "../../components/SwordEmblem";
import { ApiError } from "../../lib/api";
import { adminApi } from "./adminApi";
import OverviewTab from "./OverviewTab";
import PaymentsTab from "./PaymentsTab";
import SettingsTab from "./SettingsTab";
import { devTokenAllowed, useAdminAuth } from "./useAdminAuth";

const TABS = [
  { id: "overview", label: "Visão geral e participantes" },
  { id: "payments", label: "Pagamentos" },
  { id: "settings", label: "Configurações" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export default function AdminApp() {
  const auth = useAdminAuth();
  const [me, setMe] = useState<{ email: string } | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("overview");
  const api = useMemo(() => (auth.token ? adminApi(auth.token) : null), [auth.token]);

  useEffect(() => {
    if (!api) { setMe(null); return; }
    api.me().then(setMe).catch((e) => {
      setAuthError(e instanceof ApiError && e.status === 403 ? "Este usuário não tem permissão administrativa." : "Sessão inválida ou expirada.");
      auth.signOut();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api]);

  return (
    <div className="min-h-dvh">
      <header className="bg-militar text-marfim">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <Link to="/" className="flex items-center gap-3">
            <SwordEmblem className="hidden w-28 sm:block" />
            <div>
              <p className="font-cerimonial text-sm tracking-[0.2em] text-prata">PAINEL</p>
              <p className="text-[13px] text-prata/80">Rifa Solidária · CPOR/R</p>
            </div>
          </Link>
          {me ? (
            <div className="flex items-center gap-3 text-[13px] text-prata">
              <span className="hidden sm:inline">{me.email}</span>
              <button className="rounded border border-prata/30 px-3 py-1.5 hover:bg-white/5" onClick={auth.signOut}>Sair</button>
            </div>
          ) : null}
        </div>
        <div className="filete-prata opacity-50" />
      </header>

      {!auth.ready ? (
        <div className="flex justify-center py-20"><Spinner /></div>
      ) : !api || !me ? (
        auth.token && !authError ? (
          <div className="flex justify-center py-20"><Spinner /></div>
        ) : (
          <Login auth={auth} error={authError} onAttempt={() => setAuthError(null)} />
        )
      ) : (
        <div className="mx-auto max-w-6xl px-4 py-5">
          <nav className="mb-5 flex gap-1 overflow-x-auto border-b border-linha" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={`-mb-px shrink-0 border-b-2 px-3.5 py-2.5 text-sm font-medium transition ${
                  tab === t.id ? "border-oliva text-oliva" : "border-transparent text-tunica hover:text-grafite"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
          {tab === "overview" ? <OverviewTab api={api} /> : tab === "payments" ? <PaymentsTab api={api} /> : <SettingsTab api={api} />}
        </div>
      )}
    </div>
  );
}

function Login({ auth, error, onAttempt }: { auth: ReturnType<typeof useAdminAuth>; error: string | null; onAttempt: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [devToken, setDevToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    onAttempt();
    setBusy(true);
    setMsg(null);
    try {
      await auth.signIn(email, password);
    } catch (err) {
      setMsg((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm px-4 py-12">
      <h1 className="titulo-cerimonial text-center text-xl">Acesso restrito</h1>
      <p className="mt-1 text-center text-sm text-tunica">Somente organizadores autorizados.</p>
      {error || msg ? <div className="mt-4"><Notice tone="error">{error ?? msg}</Notice></div> : null}
      {devTokenAllowed ? (
        <form
          className="cartao mt-5 space-y-3 px-5 py-5"
          onSubmit={(e) => { e.preventDefault(); onAttempt(); auth.setDevToken(devToken); }}
        >
          <Notice tone="warn">
            Supabase não configurado. Modo de desenvolvimento: cole o token gerado por{" "}
            <code className="text-xs">python -m scripts.dev_token</code>.
          </Notice>
          <textarea className="campo font-mono text-xs" rows={4} value={devToken} onChange={(e) => setDevToken(e.target.value)} />
          <button className="botao w-full" disabled={!devToken.trim()}>Entrar</button>
        </form>
      ) : (
        <form className="cartao mt-5 space-y-4 px-5 py-5" onSubmit={submit}>
          <div>
            <label className="rotulo" htmlFor="adm-email">E-mail</label>
            <input id="adm-email" type="email" className="campo" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="rotulo" htmlFor="adm-senha">Senha</label>
            <input id="adm-senha" type="password" className="campo" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <button className="botao w-full" disabled={busy}>{busy ? <Spinner /> : null} Entrar</button>
        </form>
      )}
    </div>
  );
}
