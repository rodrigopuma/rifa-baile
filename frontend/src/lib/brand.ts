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

/** Link de WhatsApp (wa.me) a partir do número configurado; vazio se ainda não preenchido. */
export function whatsappLink(): string {
  const d = ORGANIZER.whatsapp.replace(/\D+/g, "");
  return d.length === 11 ? `https://wa.me/55${d}` : "";
}
