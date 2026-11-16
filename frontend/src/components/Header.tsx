import { Link } from "react-router-dom";
import { BRAND, nb } from "../lib/brand";
import { Laurel } from "./Laurel";
import { SwordEmblem } from "./SwordEmblem";

export function Header({ eyebrow, imageUrl }: { eyebrow?: string; imageUrl?: string }) {
  return (
    <header className="relative overflow-hidden bg-militar text-marfim">
      {imageUrl ? (
        <img
          src={imageUrl}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 h-full w-full object-cover opacity-[0.12] mix-blend-luminosity"
        />
      ) : null}
      <div className="filete-prata opacity-60" />
      <div className="relative mx-auto max-w-3xl px-5 pb-4 pt-5 text-center sm:pt-6">
        <Link to="/" className="inline-block focus-visible:outline-prata">
          <div className="flex items-center justify-center gap-2.5 text-prata">
            <Laurel className="h-4 w-9" />
            <span className="font-cerimonial text-[12px] font-semibold uppercase tracking-[0.34em] sm:text-[13px]">
              {eyebrow || BRAND.eyebrow}
            </span>
            <Laurel className="h-4 w-9" mirrored />
          </div>
          <h1 className="mt-2 text-balance font-cerimonial text-[21px] font-semibold leading-tight text-marfim sm:text-[28px]">
            {nb(BRAND.title)}
          </h1>
          <p className="mt-1 text-balance text-[13px] tracking-wide text-prata sm:text-sm">{nb(BRAND.institution)}</p>
        </Link>
        <SwordEmblem className="mx-auto mt-3 h-auto w-[280px] sm:w-[340px]" />
        <p className="mt-1.5 text-[12.5px] italic text-prata/85">“{BRAND.motto}”</p>
      </div>
      <div className="filete-prata opacity-60" />
      <div className="mt-[3px] h-px bg-prata/15" />
    </header>
  );
}
