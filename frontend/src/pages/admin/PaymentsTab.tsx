import { useCallback, useEffect, useState } from "react";
import { Notice } from "../../components/Notice";
import { dateTime, money } from "../../lib/format";
import { PAYMENT_STATUS, type AdminApi, type AdminPayment, type AuditEntry } from "./adminApi";
import { StatusBadge } from "./ui";

export default function PaymentsTab({ api }: { api: AdminApi }) {
  const [status, setStatus] = useState("");
  const [items, setItems] = useState<AdminPayment[]>([]);
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, a] = await Promise.all([api.payments(status || undefined), api.audit()]);
      setItems(p.items);
      setLogs(a.items);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [api, status]);
  useEffect(() => { load(); }, [load]);

  async function sync(id: string) {
    setBusyId(id);
    try { await api.syncPayment(id); await load(); } catch (e) { setError((e as Error).message); } finally { setBusyId(null); }
  }

  return (
    <div className="space-y-6">
      <Notice tone="info">
        Modo Mercado Pago: pagamentos são confirmados só pelo Mercado Pago (webhook ou consulta), sem aprovação manual.
        Modo manual (Pix direto): você confirma cada pagamento na aba Visão geral, conferindo o Pix no app do seu banco.
      </Notice>
      <div className="flex items-center justify-between gap-3">
        <h2 className="titulo-cerimonial text-lg">Transações</h2>
        <select className="campo mt-0 w-48" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filtrar status">
          <option value="">Todos os status</option>
          {Object.entries(PAYMENT_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <div className="cartao overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-linha text-xs uppercase tracking-wider text-tunica">
            <tr>
              <th className="px-4 py-2.5 font-medium">Pedido</th>
              <th className="px-4 py-2.5 font-medium">ID provedor</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Valor</th>
              <th className="px-4 py-2.5 font-medium">Criado</th>
              <th className="px-4 py-2.5 font-medium">Aprovado</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-linha">
            {items.map((p) => (
              <tr key={p.id}>
                <td className="px-4 py-2.5 font-numeral tracking-wide">{p.order_code}</td>
                <td className="px-4 py-2.5 text-[13px]">
                  {p.provider_payment_id}
                  {p.live_mode ? <span className="ml-1 rounded bg-erro px-1 text-[10px] text-white">LIVE</span> : null}
                </td>
                <td className="px-4 py-2.5">
                  <StatusBadge status={p.status} label={PAYMENT_STATUS[p.status] ?? p.status} />
                  {p.status_detail ? <span className="ml-1.5 text-xs text-tunica">{p.status_detail}</span> : null}
                </td>
                <td className="px-4 py-2.5 font-numeral">{money(p.amount_cents)}</td>
                <td className="px-4 py-2.5 text-[13px]">{dateTime(p.created_at)}</td>
                <td className="px-4 py-2.5 text-[13px]">{p.approved_at ? dateTime(p.approved_at) : "—"}</td>
                <td className="px-4 py-2.5 text-right">
                  {p.provider === "manual" ? null : (
                    <button className="botao-discreto text-oliva" disabled={busyId === p.id} onClick={() => sync(p.id)}>
                      {busyId === p.id ? "Consultando…" : "Atualizar"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-tunica">Nenhuma transação.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div>
        <h2 className="titulo-cerimonial mb-2 text-lg">Registro de ações</h2>
        <div className="cartao max-h-[480px] divide-y divide-linha overflow-y-auto text-[13px]">
          {logs.map((l) => (
            <div key={l.id} className="flex flex-wrap gap-x-3 px-4 py-2">
              <span className="text-tunica">{dateTime(l.created_at)}</span>
              <span className="font-medium">{l.action}</span>
              <span className="text-tunica">{l.actor_type}</span>
              <span className="min-w-0 flex-1 truncate text-tunica" title={JSON.stringify(l.details)}>
                {l.entity_type} {l.entity_id} {Object.keys(l.details).length ? JSON.stringify(l.details) : ""}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
