import { createContext, useContext, useEffect, useReducer, useRef, useState, type ReactNode } from "react";
import { loadSelection, saveSelection } from "../lib/orderStore";
import { selectionReducer, type SelectionAction } from "../lib/selection";
import { useCampaignContext } from "./CampaignContext";

interface Ctx {
  selected: number[];
  dispatch: (a: SelectionAction) => void;
  notice: string | null;
  clearNotice: () => void;
  setNotice: (n: string | null) => void;
  /** Enquanto o pedido está sendo criado, os próprios números ficam indisponíveis (Realtime)
   *  antes de a resposta chegar. Durante esse intervalo, não tratá-los como "perdidos". */
  setSubmitting: (v: boolean) => void;
}
const SelectionCtx = createContext<Ctx | null>(null);

export function SelectionProvider({ children }: { children: ReactNode }) {
  const { unavailable, campaign } = useCampaignContext();
  const [selected, dispatch] = useReducer(selectionReducer, undefined, loadSelection);
  const [notice, setNotice] = useState<string | null>(null);
  const first = useRef(true);
  const submitting = useRef(false);

  useEffect(() => saveSelection(selected), [selected]);

  // Se algum número escolhido ficar indisponível (outra pessoa reservou), remove e avisa.
  useEffect(() => {
    if (submitting.current) return;
    const lost = selected.filter((n) => unavailable.has(n) || (campaign && n > campaign.total_numbers));
    if (lost.length) {
      dispatch({ type: "remove", numbers: lost });
      if (!first.current) {
        setNotice(
          lost.length === 1
            ? `O número ${lost[0]} acabou de ser escolhido por outra pessoa e foi removido da sua seleção.`
            : `Os números ${lost.join(", ")} acabaram de ser escolhidos por outras pessoas e foram removidos.`,
        );
      }
    }
    if (campaign) first.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unavailable, campaign]);

  return (
    <SelectionCtx.Provider value={{
      selected, dispatch, notice, setNotice, clearNotice: () => setNotice(null),
      setSubmitting: (v: boolean) => { submitting.current = v; },
    }}>
      {children}
    </SelectionCtx.Provider>
  );
}

export function useSelection(): Ctx {
  const v = useContext(SelectionCtx);
  if (!v) throw new Error("SelectionProvider ausente");
  return v;
}
