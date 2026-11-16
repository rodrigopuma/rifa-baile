import { Link, useNavigate } from "react-router-dom";
import { Laurel } from "../components/Laurel";
import { Layout } from "../components/Layout";
import { Notice } from "../components/Notice";
import { NumberGrid } from "../components/NumberGrid";
import { ProgressBar } from "../components/ProgressBar";
import { SelectionSummary } from "../components/SelectionSummary";
import { PageLoading } from "../components/Spinner";
import { useCampaignContext } from "../hooks/CampaignContext";
import { useSelection } from "../hooks/SelectionContext";
import { dateLong, money } from "../lib/format";
import { ORGANIZER, nb, whatsappLink } from "../lib/brand";

export default function Home() {
  const { campaign, unavailable, availableCount, loading, error, refresh } = useCampaignContext();
  const { selected, dispatch, notice, clearNotice } = useSelection();
  const navigate = useNavigate();

  if (loading && !campaign) return <Layout><PageLoading /></Layout>;
  if (!campaign)
    return (
      <Layout>
        <Notice tone="error">
          {error ?? "Nenhuma campanha publicada no momento."}{" "}
          <button className="font-semibold underline" onClick={refresh}>Tentar novamente</button>
        </Notice>
      </Layout>
    );

  const active = campaign.status === "active";
  const taken = campaign.total_numbers - availableCount;

  return (
    <Layout campaign={campaign}>
      <section className="cartao animar-surgir overflow-hidden">
        <div className="flex gap-4 px-4 pt-4 sm:gap-5 sm:px-6 sm:pt-6">
          {ORGANIZER.photoUrl ? (
            <img
              src={ORGANIZER.photoUrl}
              alt={`Foto de ${ORGANIZER.name}`}
              width={640}
              height={800}
              className="aspect-[4/5] w-28 shrink-0 rounded-md object-cover object-top ring-1 ring-prata sm:w-36"
            />
          ) : null}
          <div className="min-w-0 self-center">
            <p className="text-[11px] uppercase tracking-[0.18em] text-tunica">Quem organiza</p>
            <p className="font-cerimonial text-xl font-semibold leading-tight text-militar sm:text-2xl">{ORGANIZER.name}</p>
            <p className="mt-0.5 text-[13px] leading-snug text-tunica">{nb(ORGANIZER.intro)}</p>
            {whatsappLink() ? (
              <a href={whatsappLink()} target="_blank" rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1.5 text-[13px] font-medium text-oliva underline-offset-4 hover:underline">
                Falar no WhatsApp →
              </a>
            ) : null}
          </div>
        </div>
        {campaign.description ? (
          <p className="px-4 pt-4 text-[15px] leading-relaxed text-grafite/90 sm:px-6">{nb(campaign.description)}</p>
        ) : null}

        {campaign.prize_title ? (
          <div className="mx-4 mt-4 rounded-md bg-militar px-4 py-4 text-center text-marfim sm:mx-6">
            <div className="flex items-center justify-center gap-2.5 text-prata">
              <Laurel className="h-4 w-9" />
              <span className="font-numeral text-xs uppercase tracking-[0.3em]">Prêmio</span>
              <Laurel className="h-4 w-9" mirrored />
            </div>
            <p className="mt-1 font-cerimonial text-2xl font-semibold sm:text-3xl">{campaign.prize_title}</p>
            {campaign.draw_date ? (
              <p className="mt-1 text-[13px] text-prata">
                Sorteio pela Loteria Federal · {dateLong(campaign.draw_date)}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="px-4 pb-5 pt-4 sm:px-6">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4">
            <div>
              <dt className="text-xs uppercase tracking-wider text-tunica">Valor por número</dt>
              <dd className="font-numeral text-2xl text-militar">{money(campaign.price_cents)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wider text-tunica">Números livres</dt>
              <dd className="font-numeral text-2xl text-militar">
                {availableCount}
                <span className="ml-1 text-base text-tunica">de {campaign.total_numbers}</span>
              </dd>
            </div>
          </dl>
          <div className="mt-4">
            <ProgressBar value={taken} total={campaign.total_numbers} />
          </div>
          <p className="mt-3 text-[13px]">
            <Link to="/regulamento" className="font-medium text-oliva underline-offset-4 hover:underline">
              Regulamento e informações da rifa →
            </Link>
          </p>
        </div>
      </section>

      {!active ? (
        <div className="mt-4">
          <Notice tone="warn">
            {campaign.status === "paused"
              ? "A campanha está temporariamente pausada. Volte em breve."
              : campaign.status === "closed"
                ? "A campanha foi encerrada. Obrigado a todos que participaram!"
                : "A campanha ainda não foi aberta."}
          </Notice>
        </div>
      ) : null}

      <section className="mt-7" aria-labelledby="escolha">
        <h2 id="escolha" className="titulo-cerimonial text-lg sm:text-xl">Escolha seus números</h2>
        <p className="mb-4 mt-1 text-sm text-tunica">Toque nos números para selecionar. Você pode escolher vários.</p>
        {notice ? (
          <div className="mb-3">
            <Notice tone="warn" onClose={clearNotice}>{notice}</Notice>
          </div>
        ) : null}
        <NumberGrid
          total={campaign.total_numbers}
          unavailable={unavailable}
          selected={selected}
          disabled={!active}
          onToggle={(n) => dispatch({ type: "toggle", number: n, max: campaign.max_numbers_per_order })}
        />
        {selected.length >= campaign.max_numbers_per_order ? (
          <p className="mt-3 text-[13px] text-alerta">Limite de {campaign.max_numbers_per_order} números por pedido.</p>
        ) : null}
        <SelectionSummary
          selected={selected}
          total={campaign.total_numbers}
          priceCents={campaign.price_cents}
          disabled={!active}
          onClear={() => dispatch({ type: "clear" })}
          onContinue={() => navigate("/participar")}
        />
      </section>
    </Layout>
  );
}
