import { Link } from "react-router-dom";
import { BRAND, ORGANIZER, whatsappLink } from "../lib/brand";

export function Footer({ organizer, contact }: { organizer?: string; contact?: string }) {
  return (
    <footer className="mt-14 bg-militar text-prata">
      <div className="filete-prata opacity-50" />
      <div className="mx-auto max-w-3xl space-y-3 px-5 py-7 text-[13px] leading-relaxed">
        <p className="font-cerimonial text-sm tracking-wide text-marfim">{BRAND.institution}</p>
        {organizer || ORGANIZER.name ? (
          <p>
            Organizador: <span className="text-marfim">{organizer || ORGANIZER.name}</span>
            {contact ? <> · {contact}</> : null}
          </p>
        ) : null}
        {whatsappLink() ? (
          <a href={whatsappLink()} target="_blank" rel="noreferrer" className="inline-block text-marfim underline-offset-4 hover:underline">
            Falar comigo no WhatsApp →
          </a>
        ) : null}
        <p className="text-prata/80">{BRAND.disclaimer}</p>
        <nav className="flex gap-4 pt-1">
          <Link to="/regulamento" className="underline-offset-4 hover:text-marfim hover:underline">
            Regulamento e informações
          </Link>
          <Link to="/privacidade" className="underline-offset-4 hover:text-marfim hover:underline">
            Privacidade
          </Link>
        </nav>
      </div>
    </footer>
  );
}
