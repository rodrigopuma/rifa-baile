import { render, screen, fireEvent } from "@testing-library/react";
import { useReducer } from "react";
import { NumberGrid } from "../components/NumberGrid";
import { SelectionSummary } from "../components/SelectionSummary";
import { selectionReducer } from "../lib/selection";

function Harness({ unavailable }: { unavailable: number[] }) {
  const [selected, dispatch] = useReducer(selectionReducer, []);
  return (
    <>
      <NumberGrid total={30} unavailable={new Set(unavailable)} selected={selected}
        onToggle={(n) => dispatch({ type: "toggle", number: n, max: 10 })} />
      <SelectionSummary selected={selected} total={30} priceCents={1000}
        onClear={() => dispatch({ type: "clear" })} onContinue={() => {}} />
    </>
  );
}

describe("grade de números", () => {
  it("seleciona vários números por toque e atualiza o resumo", () => {
    render(<Harness unavailable={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "Número 03" }));
    fireEvent.click(screen.getByRole("button", { name: "Número 12" }));
    expect(screen.getByRole("button", { name: "Número 03" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("2 números escolhidos")).toBeInTheDocument();
    expect(screen.getByText(/R\$\s20,00/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continuar para pagamento" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Número 03" }));
    expect(screen.getByText("1 número escolhido")).toBeInTheDocument();
  });

  it("não permite escolher números indisponíveis", () => {
    render(<Harness unavailable={[5]} />);
    const taken = screen.getByRole("button", { name: "Número 05, indisponível" });
    expect(taken).toBeDisabled();
    fireEvent.click(taken);
    expect(screen.getByText("Nenhum número escolhido")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continuar para pagamento" })).toBeDisabled();
  });

  it("filtra somente livres", () => {
    render(<Harness unavailable={[1, 2]} />);
    fireEvent.click(screen.getByLabelText("Só livres"));
    expect(screen.queryByRole("button", { name: /Número 01/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Número 03" })).toBeInTheDocument();
  });
});
