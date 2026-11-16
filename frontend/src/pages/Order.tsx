import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Divider } from "../components/Divider";
import { Laurel } from "../components/Laurel";
import { Layout } from "../components/Layout";
import { Notice } from "../components/Notice";
import { PageLoading, Spinner } from "../components/Spinner";
import { useCampaignContext } from "../hooks/CampaignContext";
import { useCountdown } from "../hooks/useCountdown";
import { ApiError, api } from "../lib/api";
import { dateTime, money, padNumber } from "../lib/format";
import { getOrderToken, receiptUrl } from "../lib/orderStore";
import { ORGANIZER } from "../lib/brand";
import type { OrderView } from "../lib/types";

const POLL_MS = 4000;

export default function Order() {
  const { id = "" } = useParams();
  const { campaign, refresh: refreshCampaign } = useCampaignContext();
  const [token] = useState(() => getOrderToken(id));
  const [order, setOrder] = useState<OrderView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timeoutSent = useRef(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setOrder(await api.order(id, token));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 404 ? "Pedido não encontrado neste dispositivo." : (e as Error).message);
    }
  }, [id, token]);

  useEffect(() => {
    load();
  }, [load]);

  const waiting = order?.status === "awaiting_payment" || order?.status === "awaiting_confirmation";
  useEffect(() => {
    if (!waiting) return;
    const t = window.setInterval(load, order?.status === "awaiting_payment" ? POLL_MS : POLL_MS * 3);
    return () => window.clearInterval(t);
  }, [waiting, order?.status, load]);

  useEffect(() => {
    if (order && !waiting) refreshCampaign();
  }, [order, waiting, refreshCampaign]);

  const countdown = useCountdown(order?.checkout_expires_at, order?.server_time);

  // Ao fim dos 15 minutos: encerra visualmente e pede o cancelamento da cobrança.
  useEffect(() => {
    if (!order || !token || timeoutSent.current) return;
    if (order.status === "awaiting_payment" && countdown.done) {
      timeoutSent.current = true;
      api.checkoutTimeout(id, token).then(setOrder).catch(() => load());
    }
  }, [countdown.done, order, token, id, load]);

  if (!token)
    return (
      <Layout campaign={campaign}>
        <Notice tone="warn">
          Não encontramos o acesso a este pedido neste dispositivo. Use o link seguro do comprovante ou fale com o organizador.
        </Notice>
      </Layout>
    );
  if (error && !order) return <Layout campaign={campaign}><Notice tone="error">{error}</Notice></Layout>;
  if (!order) return <Layout campaign={campaign}><PageLoading /></Layout>;

  const total = campaign?.total_numbers ?? 100;
  return (
    <Layout campaign={campaign}>
      {order.status === "paid" ? (
        <Confirmation order={order} total={total} token={token} />
      ) : order.status === "awaiting_payment" && !countdown.done && order.pix ? (
        <Checkout order={order} total={total} countdown={countdown} onSimulated={load} />
      ) : (
        <Closed order={order} total={total} />
      )}
    </Layout>
  );
}

function NumberChips({ numbers, total }: { numbers: number[]; total: number }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {numbers.map((n) => (
        <span key={n} className="rounded bg-oliva px-2 py-0.5 font-numeral text-sm tracking-wide text-marfim">
          {padNumber(n, total)}
        </span>
      ))}
    </div>
  );
}

function Checkout({
  order, total, countdown, onSimulated,
}: { order: OrderView; total: number; countdown: ReturnType<typeof useCountdown>; onSimulated: () => void }) {
  const [copied, setCopied] = useState(false);
  const [simBusy, setSimBusy] = useState(false);
  const pix = order.pix!;
  const urgent = countdown.seconds < 120;

  async function copy() {
    try {
      await navigator.clipboard.writeText(pix.qr_code);
    } catch {
      const el = document.getElementById("pix-code") as HTMLTextAreaElement | null;
      el?.select();
      document.execCommand?.("copy");
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2500);
  }

  async function simulate(action: "approve" | "reject" | "expire") {
    if (!order.simulator_payment_id) return;
    setSimBusy(true);
    try {
      await api.simulate(order.simulator_payment_id, action);
    } finally {
      setSimBusy(false);
      onSimulated();
    }
  }

  return (
    <div className="animar-surgir space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="titulo-cerimonial text-lg sm:text-xl">Pagamento via Pix</h2>
          <p className="mt-0.5 text-sm text-tunica">Pedido {order.code}</p>
        </div>
        <div className="text-right" aria-live="off">
          <p className="text-[11px] uppercase tracking-wider text-tunica">Tempo restante</p>
          <p className={`font-numeral text-3xl leading-none ${urgent ? "text-erro" : "text-militar"}`} role="timer">
            {countdown.label}
          </p>
        </div>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-prata-claro" aria-hidden="true">
        <div
          className={`h-full transition-[width] duration-500 ${urgent ? "bg-erro" : "bg-oliva"}`}
          style={{ width: `${Math.min(100, (countdown.seconds / (15 * 60)) * 100)}%` }}
        />
      </div>

      <section className="cartao px-5 py-5 text-center">
        <p className="text-sm text-tunica">Valor a pagar</p>
        <p className="font-numeral text-4xl text-militar">{money(order.total_cents)}</p>
        <div className="mx-auto mt-4 w-fit rounded-lg border border-linha bg-white p-3">
          <img
            src={`data:image/png;base64,${pix.qr_code_base64}`}
            alt="QR Code Pix para pagamento"
            className="h-56 w-56 [image-rendering:pixelated] sm:h-60 sm:w-60"
          />
        </div>
        <p className="mt-3 text-sm text-tunica">Abra o app do seu banco, escolha <b>Pix</b> e leia o QR Code.</p>

        <Divider className="my-5" />

        <label htmlFor="pix-code" className="rotulo text-left">Pix copia e cola</label>
        <textarea
          id="pix-code" readOnly value={pix.qr_code} rows={3}
          className="campo resize-none break-all font-mono text-xs leading-relaxed text-grafite/80"
          onFocus={(e) => e.currentTarget.select()}
        />
        <button className="botao mt-3 w-full" onClick={copy}>
          {copied ? "Código copiado ✓" : "Copiar código Pix"}
        </button>
        {pix.ticket_url ? (
          <a href={pix.ticket_url} target="_blank" rel="noreferrer" className="botao-discreto mt-2">
            Abrir instruções do Mercado Pago ↗
          </a>
        ) : null}
      </section>

      <section className="cartao px-5 py-4">
        <p className="mb-2 text-sm text-tunica">Números reservados para você</p>
        <NumberChips numbers={order.numbers} total={total} />
        <p className="mt-3 flex items-center gap-2 text-[13px] text-tunica">
          <Spinner className="h-4 w-4 text-oliva" /> Aguardando a confirmação do pagamento — esta página atualiza sozinha.
        </p>
      </section>

      {order.payment_mode === "simulator" && order.simulator_payment_id ? (
        <section className="rounded-md border-2 border-dashed border-alerta/40 bg-[#FBF5E6] px-5 py-4">
          <p className="text-sm font-semibold text-alerta">Simulador local — sem valor real</p>
          <p className="mt-0.5 text-[13px] text-alerta/90">Use para testar o fluxo. Não aparece em produção.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="botao-secundario" disabled={simBusy} onClick={() => simulate("approve")}>Simular pagamento aprovado</button>
            <button className="botao-secundario" disabled={simBusy} onClick={() => simulate("reject")}>Recusar</button>
            <button className="botao-secundario" disabled={simBusy} onClick={() => simulate("expire")}>Expirar Pix</button>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function Confirmation({ order, total, token }: { order: OrderView; total: number; token: string }) {
  const [copied, setCopied] = useState(false);
  const link = receiptUrl(order.id, token);
  return (
    <section className="cartao animar-surgir overflow-hidden">
      <div className="bg-militar px-5 pb-5 pt-6 text-center text-marfim">
        <div className="flex items-center justify-center gap-3 text-prata">
          <Laurel className="h-5 w-11" />
          <span className="font-numeral text-sm uppercase tracking-[0.3em]">Confirmado</span>
          <Laurel className="h-5 w-11" mirrored />
        </div>
        <h2 className="mt-3 font-cerimonial text-xl sm:text-2xl">Muito obrigado, {order.participant_first_name}!</h2>
        <p className="mt-1 text-sm text-prata">{ORGANIZER.thanks}</p>
      </div>
      <div className="filete-prata" />
      <div className="space-y-5 px-5 py-5">
        <div>
          <p className="mb-2 text-xs uppercase tracking-wider text-tunica">Seus números</p>
          <NumberChips numbers={order.numbers} total={total} />
        </div>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <Info label="Participante" value={order.participant_name ?? ""} wide />
          <Info label="Valor pago" value={money(order.paid_cents ?? order.total_cents)} />
          <Info label="Pedido" value={order.code} />
          <Info label="Confirmado em" value={order.paid_at ? dateTime(order.paid_at) : "—"} wide />
        </dl>
        <Divider />
        <div>
          <p className="text-sm font-medium">Link seguro do comprovante</p>
          <p className="mt-0.5 text-[13px] text-tunica">Guarde este link: ele dá acesso ao seu comprovante. Não o compartilhe publicamente.</p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <Link to={`/comprovante/${order.id}#t=${encodeURIComponent(token)}`} className="botao flex-1">
              Ver comprovante
            </Link>
            <button
              className="botao-secundario flex-1"
              onClick={async () => {
                try { await navigator.clipboard.writeText(link); } catch { /* ignore */ }
                setCopied(true);
              }}
            >
              {copied ? "Link copiado ✓" : "Copiar link"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function Info({ label, value, wide }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "col-span-2" : ""}>
      <dt className="text-xs uppercase tracking-wider text-tunica">{label}</dt>
      <dd className="mt-0.5 font-medium text-grafite">{value}</dd>
    </div>
  );
}

function Closed({ order, total }: { order: OrderView; total: number }) {
  const texts: Record<string, { title: string; body: string; tone: "warn" | "info" | "error" }> = {
    awaiting_payment: {
      title: "Tempo esgotado",
      body: "O prazo de pagamento terminou. Estamos confirmando o encerramento da cobrança com o Mercado Pago.",
      tone: "warn",
    },
    awaiting_confirmation: {
      title: "Prazo de pagamento encerrado",
      body:
        "Se você já pagou, não se preocupe: a confirmação será feita automaticamente assim que o Mercado Pago informar. " +
        "Caso contrário, os números serão liberados após o vencimento da cobrança.",
      tone: "warn",
    },
    expired: { title: "Pix expirado", body: "O pagamento não foi realizado a tempo e os números foram liberados.", tone: "info" },
    cancelled: { title: "Pedido cancelado", body: "A cobrança foi cancelada e os números foram liberados.", tone: "info" },
    refunded: { title: "Pagamento estornado", body: "Este pagamento foi estornado e os números foram liberados.", tone: "info" },
    in_review: {
      title: "Pagamento em análise",
      body: "Recebemos uma informação que precisa ser conferida pelo organizador. Entrarei em contato pelo WhatsApp.",
      tone: "warn",
    },
  };
  const t = texts[order.status] ?? texts.cancelled;
  return (
    <div className="animar-surgir space-y-4">
      <h2 className="titulo-cerimonial text-lg sm:text-xl">{t.title}</h2>
      <Notice tone={t.tone}>{t.body}</Notice>
      <section className="cartao px-5 py-4">
        <p className="mb-2 text-sm text-tunica">Pedido {order.code} · {money(order.total_cents)}</p>
        <NumberChips numbers={order.numbers} total={total} />
      </section>
      {order.status !== "awaiting_confirmation" && order.status !== "in_review" ? (
        <Link to="/" className="botao w-full">Escolher números novamente</Link>
      ) : null}
    </div>
  );
}
