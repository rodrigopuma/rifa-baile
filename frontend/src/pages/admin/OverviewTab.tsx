import { useCallback, useEffect, useState } from "react";
import { ORGANIZER } from "../../lib/brand";
import { Notice } from "../../components/Notice";
import { Spinner } from "../../components/Spinner";
import { ago, dateTime, digits, money, padNumber } from "../../lib/format";
import { ORDER_STATUS, PAYMENT_STATUS, type AdminApi, type AdminOrder, type Overview, type ParticipantRow } from "./adminApi";
import { Stat, StatusBadge } from "./ui";

export default function OverviewTab({ api }: { api: AdminApi }) {
  const [ov, setOv] = useState<Overview | null>(null);
  const [view, setView] = useState<"orders" | "participants">("orders");
  const initialQ = new URLSearchParams(window.location.search).get("q") ?? "";   // link da notificação: /admin?q=<código>
  const [q, setQ] = useState(initialQ);
  const [query, setQuery] = useState(initialQ);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [orders, setOrders] = useState<{ total: number; items: AdminOrder[] } | null>(null);
  const [people, setPeople] = useState<ParticipantRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [o, list] = await Promise.all([
        api.overview(),
        view === "orders" ? api.orders(query, status || undefined, page) : api.participants(query),
      ]);
      setOv(o);
      if (view === "orders") setOrders(list as { total: number; items: AdminOrder[] });
      else setPeople((list as { items: ParticipantRow[] }).items);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [api, view, query, status, page]);

  useEffect(() => { load(); }, [load]);

  async function exportCsv() {
    try {
      const blob = await api.exportCsv();
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: "participantes.csv" });
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const total = ov?.campaign.total_numbers ?? 100;
  const manual = ov?.payment_mode === "manual";
  return (
    <div className="space-y-5">
      {ov ? (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="titulo-cerimonial text-lg">{ov.campaign.name}</h2>
            <span className="text-xs text-tunica">
              Campanha {ov.campaign.status === "active" ? "ativa" : ov.campaign.status} · pagamentos em modo{" "}
              <b>{{ live: "PRODUÇÃO", test: "teste (Mercado Pago)", manual: "manual (Pix direto, você confirma)" }[ov.payment_mode] ?? "simulador"}</b>
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="Livres" value={ov.numbers.available} hint={`de ${ov.campaign.total_numbers}`} />
            <Stat label="Reservados" value={ov.numbers.reserved} hint={manual ? "aguardando sua confirmação" : "aguardando Pix"} />
            <Stat label="Pagos" value={ov.numbers.paid} />
            <Stat label="Arrecadação bruta" value={money(ov.gross_cents)} />
            <Stat label="Pagamentos pendentes" value={ov.pending_payments} hint={ov.orders_by_status.in_review ? `${ov.orders_by_status.in_review} em análise` : undefined} />
          </div>
        </>
      ) : null}

      <div className="cartao space-y-3 px-4 py-4">
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); setPage(1); setQuery(q); }}>
          <input
            className="campo mt-0 flex-1" placeholder="Buscar por nome, e-mail, telefone, número ou pedido"
            value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar"
          />
          {view === "orders" ? (
            <select className="campo mt-0 sm:w-44" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Status">
              <option value="">Todos os status</option>
              {Object.entries(ORDER_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          ) : null}
          <button className="botao">Buscar</button>
        </form>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex rounded-md border border-linha p-0.5 text-sm">
            {(["orders", "participants"] as const).map((v) => (
              <button key={v} onClick={() => setView(v)}
                className={`rounded px-3 py-1.5 ${view === v ? "bg-militar text-marfim" : "text-tunica hover:text-grafite"}`}>
                {v === "orders" ? "Pedidos" : "Participantes"}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            {busy ? <Spinner className="h-4 w-4 text-oliva" /> : null}
            <button className="botao-secundario" onClick={exportCsv}>Exportar CSV</button>
          </div>
        </div>
      </div>

      {error ? <Notice tone="error">{error}</Notice> : null}

      {view === "orders" && orders ? (
        <div className="space-y-2">
          <p className="text-sm text-tunica">{orders.total} pedido(s)</p>
          {orders.items.map((o) => <OrderCard key={o.id} o={o} total={total} api={api} manual={manual} onChange={load} />)}
          {orders.total > 25 ? (
            <div className="flex justify-center gap-2 pt-2">
              <button className="botao-secundario" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button>
              <span className="self-center text-sm text-tunica">Página {page}</span>
              <button className="botao-secundario" disabled={page * 25 >= orders.total} onClick={() => setPage(page + 1)}>Próxima</button>
            </div>
          ) : null}
        </div>
      ) : null}

      {view === "participants" && people ? (
        <div className="cartao divide-y divide-linha">
          {people.length === 0 ? <p className="px-4 py-6 text-center text-sm text-tunica">Nenhum participante encontrado.</p> : null}
          {people.map((p) => (
            <div key={p.id} className="px-4 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-medium">{p.full_name}</p>
                <p className="text-[13px] text-tunica">{p.phone} · {p.email}</p>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {p.paid_numbers.map((n) => <span key={n} className="rounded bg-oliva px-1.5 font-numeral text-[13px] text-marfim">{padNumber(n, total)}</span>)}
                {p.reserved_numbers.map((n) => <span key={n} className="rounded border border-dashed border-alerta/50 px-1.5 font-numeral text-[13px] text-alerta" title="Reservado">{padNumber(n, total)}</span>)}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function OrderCard({ o, total, api, manual, onChange }: { o: AdminOrder; total: number; api: AdminApi; manual: boolean; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setMsg(null);
    try { await action(); onChange(); } catch (e) { setMsg((e as Error).message); } finally { setBusy(false); }
  }
  const nums = o.numbers.map((n) => padNumber(n, total)).join(", ");

  function cancel() {
    const text = manual
      ? `Cancelar a reserva do pedido ${o.code}? Os números ${nums} voltam para a venda agora.`
      : `Solicitar o cancelamento da cobrança do pedido ${o.code}? Os números serão liberados somente após a confirmação do provedor.`;
    if (window.confirm(text)) run(() => api.cancelOrder(o.id));
  }
  function confirmPayment() {
    const late = o.status !== "pending" ? "\n\nA reserva já tinha vencido: só funciona se os números ainda estiverem livres." : "";
    if (window.confirm(`Confirmar que o Pix de ${money(o.total_cents)} de ${o.participant.full_name} caiu na sua conta?\nNúmeros: ${nums}.${late}`))
      run(() => api.confirmOrder(o.id));
  }
  function refund() {
    if (window.confirm(`Estornar o pedido ${o.code}? Os números ${nums} voltam para a venda e o comprovante deixa de valer.`))
      run(() => api.refundOrder(o.id));
  }
  function sync() {
    if (o.payment) run(() => api.syncPayment(o.payment!.id));
  }

  const canConfirm = manual && (o.status === "pending" || o.status === "expired" || o.status === "cancelled");
  const first = o.participant.full_name.split(" ")[0];
  const until = o.status === "pending" ? ` Ela vale até ${dateTime(o.checkout_expires_at)}; depois disso os números voltam para a venda.` : "";
  const chase =
    `Oi, ${first}! Aqui é o ${ORGANIZER.name}, da rifa do baile. Vi sua reserva ${o.code} (números ${nums}, ${money(o.total_cents)}).` +
    `${until} Quando fizer o Pix, me manda o comprovante por aqui que eu confirmo. Qualquer dúvida é só falar!`;
  const wa = `https://wa.me/55${digits(o.participant.phone)}?text=${encodeURIComponent(chase)}`;

  return (
    <div className="cartao">
      <div className="flex items-center">
        <button className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
          <span className="font-numeral text-[15px] tracking-wide text-militar">{o.code}</span>
          <StatusBadge status={o.status} label={ORDER_STATUS[o.status] ?? o.status} />
          <span className="min-w-0 basis-full text-sm sm:flex-1 sm:basis-auto sm:truncate">{o.participant.full_name}</span>
          <span className="font-numeral text-[15px]">{money(o.total_cents)}</span>
          <span className="w-full text-[13px] text-tunica sm:w-auto">{nums.replaceAll(", ", " · ")}</span>
          {manual && o.status === "pending" ? <span className="text-[13px] text-tunica">reservado {ago(o.created_at)}</span> : null}
        </button>
        {manual && o.status === "pending" ? (
          <a className="botao-secundario mr-2 shrink-0 px-3 py-1.5 text-sm" href={wa} target="_blank" rel="noreferrer">Chamar</a>
        ) : null}
        {manual && o.status === "pending" ? (
          <button className="botao mr-3 shrink-0 px-3 py-1.5 text-sm" disabled={busy} onClick={confirmPayment}>Confirmar</button>
        ) : null}
      </div>
      {open ? (
        <div className="space-y-3 border-t border-linha px-4 py-3 text-sm">
          <dl className="grid gap-2 sm:grid-cols-3">
            <D label="WhatsApp" v={o.participant.phone} />
            {manual ? null : <D label="E-mail" v={o.participant.email} />}
            {manual ? null : <D label="CPF" v={o.participant.cpf_masked || "—"} />}
            <D label="Criado em" v={dateTime(o.created_at)} />
            {manual && o.status === "pending" ? <D label="Reserva vale até" v={dateTime(o.checkout_expires_at)} /> : null}
            <D label="Pago em" v={o.paid_at ? dateTime(o.paid_at) : "—"} />
            <D label="ID do pedido" v={o.id} />
            {o.payment && !manual ? (
              <>
                <D label="Pagamento" v={`${PAYMENT_STATUS[o.payment.status] ?? o.payment.status} (${o.payment.provider_status || "—"})`} />
                <D label="ID no provedor" v={`${o.payment.provider} · ${o.payment.provider_payment_id}`} />
                <D label="Última consulta" v={o.payment.last_synced_at ? dateTime(o.payment.last_synced_at) : "—"} />
              </>
            ) : null}
          </dl>
          {o.review_reason ? <Notice tone="error">{o.review_reason}</Notice> : null}
          {msg ? <Notice tone="error">{msg}</Notice> : null}
          <div className="flex flex-wrap gap-2">
            {canConfirm ? (
              <button className="botao" disabled={busy} onClick={confirmPayment}>
                {o.status === "pending" ? "Confirmar pagamento" : "Confirmar pagamento tardio"}
              </button>
            ) : null}
            {manual ? <a className="botao-secundario" href={wa} target="_blank" rel="noreferrer">Chamar no WhatsApp</a> : null}
            {!manual && o.payment ? <button className="botao-secundario" disabled={busy} onClick={sync}>Consultar Mercado Pago</button> : null}
            {o.status === "pending" ? <button className="botao-secundario" disabled={busy} onClick={cancel}>{manual ? "Cancelar reserva" : "Cancelar cobrança"}</button> : null}
            {manual && o.status === "paid" ? <button className="botao-secundario" disabled={busy} onClick={refund}>Estornar (liberar números)</button> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function D({ label, v }: { label: string; v: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-tunica">{label}</dt>
      <dd className="break-all">{v}</dd>
    </div>
  );
}
