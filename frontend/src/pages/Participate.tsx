import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Layout } from "../components/Layout";
import { Notice } from "../components/Notice";
import { PageLoading, Spinner } from "../components/Spinner";
import { useCampaignContext } from "../hooks/CampaignContext";
import { useSelection } from "../hooks/SelectionContext";
import { ApiError, api } from "../lib/api";
import { digits, isValidCpf, isValidEmail, isValidPhone, maskCpf, maskPhone, money, padNumber } from "../lib/format";
import { saveOrderToken } from "../lib/orderStore";

type Field = "full_name" | "phone" | "email" | "cpf" | "consent";

export default function Participate() {
  const { campaign, refresh } = useCampaignContext();
  const { selected, dispatch, setNotice } = useSelection();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", phone: "", email: "", cpf: "" });
  const [consent, setConsent] = useState(false);
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<string | null>(null);

  if (!campaign) return <Layout><PageLoading /></Layout>;
  if (createdId) return <Navigate to={`/pedido/${createdId}`} replace />;
  if (selected.length === 0) return <Navigate to="/" replace />;

  const errors: Partial<Record<Field, string>> = {};
  const name = form.full_name.trim().replace(/\s+/g, " ");
  if (name.length < 5 || name.split(" ").length < 2) errors.full_name = "Informe nome e sobrenome.";
  if (!isValidPhone(form.phone)) errors.phone = "Informe um celular com DDD, ex.: (81) 98888-7777.";
  if (!isValidEmail(form.email)) errors.email = "Informe um e-mail válido.";
  if (campaign.payer_cpf_required || digits(form.cpf)) {
    if (!isValidCpf(form.cpf)) errors.cpf = "CPF inválido.";
  }
  if (!consent) errors.consent = "É necessário concordar para participar.";
  const show = (f: Field) => (touched[f] ? errors[f] : undefined);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched({ full_name: true, phone: true, email: true, cpf: true, consent: true });
    if (Object.keys(errors).length || !campaign) return;
    setSubmitting(true);
    setServerError(null);
    try {
      const { order, access_token } = await api.createOrder({
        numbers: selected,
        full_name: name,
        email: form.email.trim(),
        phone: digits(form.phone),
        cpf: digits(form.cpf) || null,
        privacy_consent: consent,
      });
      saveOrderToken(order.id, access_token);
      setCreatedId(order.id);
      dispatch({ type: "clear" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const lost = (err.detail as { unavailable?: number[] } | null)?.unavailable ?? [];
        if (lost.length) {
          dispatch({ type: "remove", numbers: lost });
          setNotice(
            `${lost.length === 1 ? "O número" : "Os números"} ${lost.map((n) => padNumber(n, campaign.total_numbers)).join(", ")} ` +
              `acabou de ficar indisponível. Ajuste sua seleção e tente novamente.`,
          );
          refresh();
          navigate("/");
          return;
        }
      }
      setServerError(err instanceof Error ? err.message : "Não foi possível criar o pedido.");
    } finally {
      setSubmitting(false);
    }
  }

  const total = selected.length * campaign.price_cents;

  return (
    <Layout campaign={campaign}>
      <Link to="/" className="botao-discreto -ml-3 mb-2">← Alterar números</Link>
      <h2 className="titulo-cerimonial text-lg sm:text-xl">Seus dados</h2>
      <p className="mt-1 text-sm text-tunica">Sem cadastro e sem senha. Usaremos estes dados para identificar sua participação.</p>

      <section className="cartao mt-4 px-5 py-4">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-sm text-tunica">
            {selected.length} {selected.length === 1 ? "número" : "números"} × {money(campaign.price_cents)}
          </p>
          <p className="font-numeral text-2xl text-militar">{money(total)}</p>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {selected.map((n) => (
            <span key={n} className="rounded bg-oliva px-2 py-0.5 font-numeral text-sm tracking-wide text-marfim">
              {padNumber(n, campaign.total_numbers)}
            </span>
          ))}
        </div>
      </section>

      <form className="cartao mt-4 space-y-4 px-5 py-5" onSubmit={submit} noValidate>
        <div>
          <label htmlFor="nome" className="rotulo">Nome completo</label>
          <input
            id="nome" className={`campo ${show("full_name") ? "campo-erro" : ""}`} autoComplete="name"
            value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            onBlur={() => setTouched({ ...touched, full_name: true })} aria-invalid={!!show("full_name")}
            aria-describedby="nome-erro" maxLength={160}
          />
          <FieldError id="nome-erro" msg={show("full_name")} />
        </div>
        <div>
          <label htmlFor="whats" className="rotulo">WhatsApp</label>
          <input
            id="whats" className={`campo ${show("phone") ? "campo-erro" : ""}`} inputMode="tel" autoComplete="tel-national"
            placeholder="(81) 98888-7777" value={form.phone}
            onChange={(e) => setForm({ ...form, phone: maskPhone(e.target.value) })}
            onBlur={() => setTouched({ ...touched, phone: true })} aria-invalid={!!show("phone")} aria-describedby="whats-erro"
          />
          <FieldError id="whats-erro" msg={show("phone")} />
        </div>
        <div>
          <label htmlFor="email" className="rotulo">E-mail</label>
          <input
            id="email" type="email" className={`campo ${show("email") ? "campo-erro" : ""}`} inputMode="email"
            autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
            onBlur={() => setTouched({ ...touched, email: true })} aria-invalid={!!show("email")} aria-describedby="email-erro"
          />
          <FieldError id="email-erro" msg={show("email")} />
        </div>
        <div>
          <label htmlFor="cpf" className="rotulo">
            CPF {campaign.payer_cpf_required ? null : <span className="font-normal text-tunica">(opcional)</span>}
          </label>
          <input
            id="cpf" className={`campo ${show("cpf") ? "campo-erro" : ""}`} inputMode="numeric" placeholder="000.000.000-00"
            value={form.cpf} onChange={(e) => setForm({ ...form, cpf: maskCpf(e.target.value) })}
            onBlur={() => setTouched({ ...touched, cpf: true })} aria-invalid={!!show("cpf")} aria-describedby="cpf-ajuda cpf-erro"
          />
          <p id="cpf-ajuda" className="mt-1 text-xs text-tunica">
            Exigido pelo Mercado Pago para gerar o Pix. O CPF completo não fica armazenado no sistema da campanha.
          </p>
          <FieldError id="cpf-erro" msg={show("cpf")} />
        </div>

        <div className="rounded-md bg-oliva-50/70 px-4 py-3 text-[13px] leading-relaxed text-grafite/90">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 accent-oliva" checked={consent}
              onChange={(e) => { setConsent(e.target.checked); setTouched({ ...touched, consent: true }); }}
            />
            <span>
              Concordo com o tratamento dos meus dados (nome, WhatsApp, e-mail e CPF) exclusivamente para registrar
              minha participação, processar o pagamento via Pix e contatar-me em caso de premiação, conforme a{" "}
              <Link to="/privacidade" className="font-medium text-oliva underline">política de privacidade</Link> e o{" "}
              <Link to="/regulamento" className="font-medium text-oliva underline">regulamento</Link>.
            </span>
          </label>
          <FieldError id="consent-erro" msg={show("consent")} />
        </div>

        {serverError ? <Notice tone="error">{serverError}</Notice> : null}

        <button type="submit" className="botao w-full" disabled={submitting}>
          {submitting ? <><Spinner /> Gerando Pix…</> : `Gerar Pix de ${money(total)}`}
        </button>
        <p className="text-center text-xs text-tunica">
          Os números ficam reservados para você enquanto o Pix estiver válido.
        </p>
      </form>
    </Layout>
  );
}

function FieldError({ id, msg }: { id: string; msg?: string }) {
  return msg ? <p id={id} className="mt-1 text-[13px] text-erro">{msg}</p> : null;
}
