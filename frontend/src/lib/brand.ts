/** Textos fixos da identidade, lidos do arquivo único campanha.json (raiz do repositório). */
import config from "../../../campanha.json";

/** Hífen não separável: evita quebrar "Aspirantes-a-Oficial" no meio. */
export const nb = (s: string) => s.replace(/-/g, "\u2011");

export const BRAND = {
  eyebrow: config.site.chamada,
  title: config.site.titulo,
  institution: config.site.subtitulo,
  motto: config.site.lema,
  disclaimer: config.site.aviso,
};

export const ORGANIZER = {
  name: config.organizador.nome,
  intro: config.organizador.apresentacao,
  whatsapp: config.organizador.whatsapp,
  instagram: config.organizador.instagram.replace(/^@/, ""),
  photoUrl: config.organizador.foto ? `${import.meta.env.BASE_URL}${config.organizador.foto}` : "",
  thanks: config.organizador.agradecimento,
};

/** Chave Pix do organizador (modo manual), lida do campanha.json → "pagamento". */
export const PAYMENT = {
  pixKey: (config.pagamento?.pix_chave ?? "").trim(),
  pixType: (config.pagamento?.pix_tipo ?? "").trim(),
  holder: (config.pagamento?.pix_titular ?? "").trim(),
  city: (config.pagamento?.pix_cidade ?? "Recife").trim(),
};

/** Link de WhatsApp (wa.me) a partir do número configurado; vazio se ainda não preenchido.
 *  Com `text`, a conversa já abre com a mensagem pronta. */
export function whatsappLink(text?: string): string {
  const d = ORGANIZER.whatsapp.replace(/\D+/g, "");
  if (d.length !== 11) return "";
  return `https://wa.me/55${d}${text ? `?text=${encodeURIComponent(text)}` : ""}`;
}
