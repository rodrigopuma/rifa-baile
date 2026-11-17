import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { useCampaignContext } from "../hooks/CampaignContext";

export default function Privacy() {
  const { campaign } = useCampaignContext();
  const manual = campaign?.payment_mode === "manual";
  return (
    <Layout campaign={campaign}>
      <Link to="/" className="botao-discreto -ml-3 mb-2">← Voltar</Link>
      <h2 className="titulo-cerimonial text-lg sm:text-xl">Privacidade e dados pessoais</h2>
      <section className="cartao mt-4 space-y-3 px-5 py-5 text-[15px] leading-relaxed">
        <p><b>Quais dados coletamos:</b> {manual ? "nome completo e WhatsApp." : "nome completo, WhatsApp, e-mail e CPF."}</p>
        <p>
          <b>Para quê:</b> {manual
            ? "registrar sua reserva, conferir o pagamento feito por Pix, emitir o comprovante"
            : "registrar sua participação, processar o pagamento via Pix junto ao Mercado Pago, emitir o comprovante"}{" "}
          e contatar você em caso de premiação (base legal: execução do contrato de participação — LGPD, art. 7º, V).
        </p>
        {manual ? (
          <p>
            <b>CPF e e-mail:</b> não são solicitados. O pagamento é feito por Pix direto ao organizador; o comprovante do
            seu banco fica com você e com ele.
          </p>
        ) : (
          <p>
            <b>CPF:</b> é enviado ao Mercado Pago apenas para gerar a cobrança. A campanha guarda somente uma versão
            mascarada (ex.: ***.456.789-**).
          </p>
        )}
        <p>
          <b>Quem acessa:</b> apenas o organizador da rifa, por meio de painel protegido por senha. Os números
          comprados são exibidos publicamente apenas como "indisponíveis", sem nomes.
        </p>
        <p>
          <b>Por quanto tempo:</b> até a conclusão do sorteio e da prestação de contas da campanha. Você pode solicitar
          acesso, correção ou exclusão dos seus dados pelo contato do organizador
          {campaign?.organizer_contact ? <>: <b>{campaign.organizer_contact}</b></> : "."}
        </p>
      </section>
    </Layout>
  );
}
