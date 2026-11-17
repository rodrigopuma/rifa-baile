import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Divider } from "../components/Divider";
import { Laurel } from "../components/Laurel";
import { Notice } from "../components/Notice";
import { PageLoading } from "../components/Spinner";
import { SwordEmblem } from "../components/SwordEmblem";
import { api } from "../lib/api";
import { BRAND, nb } from "../lib/brand";
import { dateLong, dateTime, money, padNumber } from "../lib/format";
import { getOrderToken } from "../lib/orderStore";
import type { Receipt as R } from "../lib/types";

export default function Receipt() {
  const { id = "" } = useParams();
  const [data, setData] = useState<R | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getOrderToken(id);
    if (!token) {
      setError("Link de comprovante incompleto ou inválido.");
      return;
    }
    api.receipt(id, token).then(setData).catch((e) => setError(e.message));
  }, [id]);

  return (
    <div className="min-h-dvh px-4 py-6 sm:py-10">
      <div className="mx-auto max-w-xl">
        {error ? <Notice tone="error">{error}</Notice> : !data ? <PageLoading /> : <Certificate r={data} />}
        <div className="nao-imprimir mt-5 flex flex-col justify-center gap-3 sm:flex-row">
          {data ? <button className="botao" onClick={() => window.print()}>Imprimir ou salvar PDF</button> : null}
          <Link to="/" className="botao-secundario">Página inicial</Link>
        </div>
      </div>
    </div>
  );
}

function Certificate({ r }: { r: R }) {
  const total = r.total_numbers;
  return (
    <article className="relative border border-prata bg-white p-1.5 shadow-cartao">
      <div className="border border-prata/60 px-5 py-7 sm:px-8">
        <header className="text-center">
          <div className="flex items-center justify-center gap-2.5 text-tunica">
            <Laurel className="hidden h-4 w-9 shrink-0 sm:block" />
            <span className="font-cerimonial text-xs font-semibold uppercase tracking-[0.18em] sm:tracking-[0.3em]">Comprovante de participação</span>
            <Laurel className="hidden h-4 w-9 shrink-0 sm:block" mirrored />
          </div>
          <h1 className="mt-3 font-cerimonial text-xl text-militar sm:text-2xl">{r.campaign_name}</h1>
          <p className="mt-1 text-sm text-tunica">{nb(r.campaign_subtitle || BRAND.title)}</p>
          <SwordEmblem className="mx-auto mt-3 w-52 opacity-80" />
        </header>
        <Divider className="my-5" />
        <p className="text-center text-sm text-tunica">Certificamos a participação de</p>
        <p className="mt-1 text-center font-cerimonial text-lg text-militar">{r.participant_name}</p>
        <div className="mt-4 flex flex-wrap justify-center gap-1.5">
          {r.numbers.map((n) => (
            <span key={n} className="rounded border border-oliva bg-oliva px-2.5 py-1 font-numeral text-base tracking-wide text-marfim">
              {padNumber(n, total)}
            </span>
          ))}
        </div>
        <dl className="mt-6 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <Row label="Valor pago" value={money(r.total_cents)} />
          <Row label="Pedido" value={r.code} />
          <Row label="Confirmado em" value={r.paid_at ? dateTime(r.paid_at) : "—"} />
          <Row label="Sorteio previsto" value={r.draw_date ? dateLong(r.draw_date) : "A definir"} />
          {r.payment_mode === "manual" ? null : <Row label="ID do pagamento" value={r.provider_payment_id ?? "—"} />}
          <Row label="Organizador" value={r.organizer_name || "—"} />
          {r.prize_title ? <Row label="Prêmio" value={r.prize_title} /> : null}
        </dl>
        {r.payment_mode !== "live" && r.payment_mode !== "manual" ? (
          <p className="mt-6 rounded bg-[#FBF5E6] px-3 py-2 text-center text-xs font-medium text-alerta">
            Emitido em ambiente de testes — documento sem valor.
          </p>
        ) : null}
        <p className="mt-5 text-center text-[11px] leading-relaxed text-tunica">{BRAND.disclaimer}</p>
      </div>
    </article>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-tunica">{label}</dt>
      <dd className="mt-0.5 break-words font-medium">{value}</dd>
    </div>
  );
}
