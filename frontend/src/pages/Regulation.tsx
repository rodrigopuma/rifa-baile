import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { PageLoading } from "../components/Spinner";
import { useCampaignContext } from "../hooks/CampaignContext";
import { BRAND } from "../lib/brand";
import { dateLong, money } from "../lib/format";

export default function Regulation() {
  const { campaign } = useCampaignContext();
  if (!campaign) return <Layout><PageLoading /></Layout>;
  return (
    <Layout campaign={campaign}>
      <Link to="/" className="botao-discreto -ml-3 mb-2">← Voltar aos números</Link>
      <h2 className="titulo-cerimonial text-lg sm:text-xl">Regulamento e informações</h2>
      <section className="cartao mt-4 space-y-4 px-5 py-5 text-[15px] leading-relaxed">
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <Item label="Campanha" value={`${campaign.name} — ${campaign.subtitle}`} />
          <Item label="Valor por número" value={money(campaign.price_cents)} />
          {campaign.bundle_size >= 2 ? (
            <Item label="Pacote" value={`${campaign.bundle_size} por ${money(campaign.bundle_price_cents)}`} />
          ) : null}
          {campaign.prize_title ? <Item label="Prêmio" value={campaign.prize_title} /> : null}
          <Item label="Quantidade de números" value={String(campaign.total_numbers)} />
          <Item label="Sorteio previsto" value={campaign.draw_date ? dateLong(campaign.draw_date) : "A definir"} />
          <Item label="Organizador" value={campaign.organizer_name || "—"} />
          <Item label="Contato" value={campaign.organizer_contact || "—"} />
        </dl>
        {campaign.authorization_info ? (
          <div className="rounded-md bg-oliva-50 px-4 py-3 text-sm">
            <p className="font-semibold text-oliva">Autorização</p>
            <p className="whitespace-pre-line">{campaign.authorization_info}</p>
          </div>
        ) : null}
        <div className="whitespace-pre-line">{campaign.regulation_text || "Regulamento ainda não publicado."}</div>
        <p className="text-[13px] text-tunica">{BRAND.disclaimer}</p>
      </section>
    </Layout>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-tunica">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
