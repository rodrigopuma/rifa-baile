/** Estado puro da seleção de números (testável sem DOM). */
export type SelectionAction =
  | { type: "toggle"; number: number; max: number }
  | { type: "remove"; numbers: number[] }
  | { type: "clear" };

export function selectionReducer(state: number[], action: SelectionAction): number[] {
  switch (action.type) {
    case "toggle": {
      if (state.includes(action.number)) return state.filter((n) => n !== action.number);
      if (state.length >= action.max) return state;
      return [...state, action.number].sort((a, b) => a - b);
    }
    case "remove": {
      const drop = new Set(action.numbers);
      const next = state.filter((n) => !drop.has(n));
      return next.length === state.length ? state : next;
    }
    case "clear":
      return state.length ? [] : state;
  }
}

/** Faixas de 100 números para campanhas grandes. */
export function ranges(total: number, size = 100): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  for (let start = 1; start <= total; start += size) out.push([start, Math.min(total, start + size - 1)]);
  return out;
}
