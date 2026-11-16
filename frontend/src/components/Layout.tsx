import type { ReactNode } from "react";
import type { Campaign } from "../lib/types";
import { Footer } from "./Footer";
import { Header } from "./Header";
import { TestModeBanner } from "./TestModeBanner";

export function Layout({ campaign, children }: { campaign?: Campaign | null; children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <TestModeBanner mode={campaign?.payment_mode} />
      <Header eyebrow={campaign?.name} imageUrl={campaign?.header_image_url || undefined} />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 pt-5 sm:px-5 sm:pt-7">{children}</main>
      <Footer organizer={campaign?.organizer_name} contact={campaign?.organizer_contact} />
    </div>
  );
}
