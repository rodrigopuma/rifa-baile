import { useEffect, useState, type FormEvent } from "react";
import { Notice } from "../../components/Notice";
import { Spinner } from "../../components/Spinner";
import type { AdminApi, AdminCampaign } from "./adminApi";
import { StatusBadge } from "./ui";

type FormState = {
  name: string; subtitle: string; description: string; prize_title: string; price: string; total_numbers: string; draw_date: string;
  organizer_name: string; organizer_contact: string; regulation_text: string; authorization_info: string; header_image_url: string;
};

const EMPTY: FormState = {
  name: "Rifa Solidária", subtitle: "Baile de Formatura de Aspirantes-a-Oficial", description: "", prize_title: "", price: "10,00", total_numbers: "300",
  draw_date: "", organizer_name: "", organizer_contact: "", regulation_text: "", authorization_info: "", header_image_url: "",
};

const STATUS_LABEL: Record<string, string> = { draft: "Rascunho", active: "Ativa", paused: "Pausada", closed: "Encerrada" };

function toForm(c: AdminCampaign): FormState {
  return {
    name: c.name, subtitle: c.subtitle, description: c.description, prize_title: c.prize_title,
    price: (c.price_cents / 100).toFixed(2).replace(".", ","), total_numbers: String(c.total_numbers),
    draw_date: c.draw_date ?? "", organizer_name: c.organizer_name, organizer_contact: c.organizer_contact,
    regulation_text: c.regulation_text, authorization_info: c.authorization_info, header_image_url: c.header_image_url,
  };
}

export default function SettingsTab({ api }: { api: AdminApi }) {
  const [list, setList] = useState<AdminCampaign[]>([]);
  const [current, setCurrent] = useState<AdminCampaign | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  async function load(selectId?: string) {
    const { items } = await api.campaigns();
    setList(items);
    const pick = items.find((c) => c.id === selectId) ?? items.find((c) => c.status === "active") ?? items[0] ?? null;
    setCurrent(pick);
    setCreating(!pick);
    setForm(pick ? toForm(pick) : EMPTY);
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load().catch((e) => setMsg({ tone: "error", text: e.message })); }, []);

  const set = (k: keyof FormState) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  async function save(e: FormEvent) {
    e.preventDefault();
    const price_cents = Math.round(Number(form.price.replace(/\./g, "").replace(",", ".")) * 100);
    const body = {
      ...form, price_cents, total_numbers: Number(form.total_numbers), draw_date: form.draw_date || null,
    } as Record<string, unknown>;
    delete body.price;
    setBusy(true);
    setMsg(null);
    try {
      const saved = creating || !current ? await api.createCampaign(body) : await api.updateCampaign(current.id, body);
      await load(saved.id);
      setMsg({ tone: "ok", text: "Configurações salvas." });
    } catch (err) {
      setMsg({ tone: "error", text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(status: string) {
    if (!current) return;
    if (status === "closed" && !window.confirm("Encerrar a campanha? Novos pedidos serão bloqueados.")) return;
    setBusy(true);
    try {
      await api.setStatus(current.id, status);
      await load(current.id);
      setMsg({ tone: "ok", text: `Status alterado para ${STATUS_LABEL[status]}.` });
    } catch (err) {
      setMsg({ tone: "error", text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
      <form className="cartao space-y-4 px-5 py-5" onSubmit={save}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="titulo-cerimonial text-lg">{creating ? "Nova campanha" : "Configurações da campanha"}</h2>
          {current && !creating ? <StatusBadge status={current.status === "active" ? "paid" : "cancelled"} label={STATUS_LABEL[current.status]} /> : null}
        </div>
        <p className="text-xs text-tunica">
          A configuração oficial fica no arquivo <code>campanha.json</code>. Alterações feitas aqui valem até a próxima
          mudança nesse arquivo.
        </p>
        {msg ? <Notice tone={msg.tone}>{msg.text}</Notice> : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <F label="Nome" id="c-nome"><input id="c-nome" className="campo" value={form.name} onChange={set("name")} required /></F>
          <F label="Subtítulo" id="c-sub"><input id="c-sub" className="campo" value={form.subtitle} onChange={set("subtitle")} /></F>
        </div>
        <F label="Descrição (finalidade solidária)" id="c-desc">
          <textarea id="c-desc" className="campo" rows={3} value={form.description} onChange={set("description")} />
        </F>
        <F label="Prêmio" id="c-premio"><input id="c-premio" className="campo" placeholder="Ex.: R$ 100,00 no Pix" value={form.prize_title} onChange={set("prize_title")} /></F>
        <div className="grid gap-4 sm:grid-cols-3">
          <F label="Preço por número (R$)" id="c-preco" hint="Não pode ser alterado após o primeiro pedido.">
            <input id="c-preco" className="campo" inputMode="decimal" value={form.price} onChange={set("price")} required />
          </F>
          <F label="Quantidade de números" id="c-qtd" hint="Redução só é possível se os números removidos estiverem livres.">
            <input id="c-qtd" className="campo" type="number" min={1} max={100000} value={form.total_numbers} onChange={set("total_numbers")} required />
          </F>
          <F label="Data prevista do sorteio" id="c-data">
            <input id="c-data" className="campo" type="date" value={form.draw_date} onChange={set("draw_date")} />
          </F>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <F label="Organizador (identificação)" id="c-org"><input id="c-org" className="campo" value={form.organizer_name} onChange={set("organizer_name")} /></F>
          <F label="Contato do organizador" id="c-cont"><input id="c-cont" className="campo" value={form.organizer_contact} onChange={set("organizer_contact")} /></F>
        </div>
        <F label="Autorização (número, órgão, data)" id="c-aut" hint="Obrigatório para habilitar cobranças reais.">
          <textarea id="c-aut" className="campo" rows={2} value={form.authorization_info} onChange={set("authorization_info")} />
        </F>
        <F label="Regulamento" id="c-reg">
          <textarea id="c-reg" className="campo font-mono text-[13px]" rows={10} value={form.regulation_text} onChange={set("regulation_text")} />
        </F>
        <F label="Imagem autorizada de cabeçalho (URL HTTPS)" id="c-img" hint="Use somente imagens com autorização de uso. Aparece de forma discreta ao fundo do cabeçalho.">
          <input id="c-img" className="campo" type="url" placeholder="https://…" value={form.header_image_url} onChange={set("header_image_url")} />
        </F>
        <div className="flex flex-wrap gap-2">
          <button className="botao" disabled={busy}>{busy ? <Spinner /> : null} {creating ? "Criar campanha (rascunho)" : "Salvar alterações"}</button>
          {creating && current ? (
            <button type="button" className="botao-secundario" onClick={() => { setCreating(false); setForm(toForm(current)); }}>Cancelar</button>
          ) : null}
        </div>
      </form>

      <aside className="space-y-4">
        {current && !creating ? (
          <div className="cartao space-y-2 px-4 py-4">
            <p className="text-sm font-medium">Status da campanha</p>
            <p className="text-xs text-tunica">Apenas uma campanha pode estar ativa por vez.</p>
            <div className="grid grid-cols-2 gap-2 pt-1">
              {(["active", "paused", "closed", "draft"] as const).map((s) => (
                <button key={s} type="button" disabled={busy || current.status === s} onClick={() => changeStatus(s)}
                  className={`rounded-md border px-3 py-2 text-sm ${current.status === s ? "border-oliva bg-oliva text-marfim" : "border-linha hover:border-oliva"}`}>
                  {STATUS_LABEL[s]}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        <div className="cartao px-4 py-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-medium">Campanhas</p>
            <button type="button" className="botao-discreto text-oliva" onClick={() => { setCreating(true); setForm(EMPTY); setMsg(null); }}>+ Nova</button>
          </div>
          <ul className="space-y-1 text-sm">
            {list.map((c) => (
              <li key={c.id}>
                <button type="button" onClick={() => { setCurrent(c); setCreating(false); setForm(toForm(c)); setMsg(null); }}
                  className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left ${current?.id === c.id && !creating ? "bg-oliva-50" : "hover:bg-neutro"}`}>
                  <span className="truncate">{c.name}</span>
                  <span className="text-xs text-tunica">{STATUS_LABEL[c.status]}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

function F({ label, id, hint, children }: { label: string; id: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="rotulo">{label}</label>
      {children}
      {hint ? <p className="mt-1 text-xs text-tunica">{hint}</p> : null}
    </div>
  );
}
