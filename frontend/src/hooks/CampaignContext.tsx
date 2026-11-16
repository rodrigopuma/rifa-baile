import { createContext, useContext, type ReactNode } from "react";
import { useCampaign } from "./useCampaign";

type Ctx = ReturnType<typeof useCampaign>;
const CampaignCtx = createContext<Ctx | null>(null);

export function CampaignProvider({ children }: { children: ReactNode }) {
  const value = useCampaign();
  return <CampaignCtx.Provider value={value}>{children}</CampaignCtx.Provider>;
}

export function useCampaignContext(): Ctx {
  const v = useContext(CampaignCtx);
  if (!v) throw new Error("CampaignProvider ausente");
  return v;
}
