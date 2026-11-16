import { selectionReducer, ranges } from "../lib/selection";
import { isValidCpf, maskCpf, maskPhone, money, padNumber, isValidPhone } from "../lib/format";

describe("seleção múltipla", () => {
  it("alterna, ordena e respeita o limite", () => {
    let s: number[] = [];
    s = selectionReducer(s, { type: "toggle", number: 7, max: 3 });
    s = selectionReducer(s, { type: "toggle", number: 2, max: 3 });
    s = selectionReducer(s, { type: "toggle", number: 5, max: 3 });
    expect(s).toEqual([2, 5, 7]);
    expect(selectionReducer(s, { type: "toggle", number: 9, max: 3 })).toBe(s);
    expect(selectionReducer(s, { type: "toggle", number: 5, max: 3 })).toEqual([2, 7]);
  });
  it("remove números que ficaram indisponíveis", () => {
    expect(selectionReducer([1, 2, 3], { type: "remove", numbers: [2, 9] })).toEqual([1, 3]);
    const same = [1];
    expect(selectionReducer(same, { type: "remove", numbers: [5] })).toBe(same);
  });
  it("divide campanhas grandes em faixas", () => {
    expect(ranges(250)).toEqual([[1, 100], [101, 200], [201, 250]]);
  });
});

describe("formatação e validação", () => {
  it("formata valores e números", () => {
    expect(money(3000).replace(/\s/g, " ")).toBe("R$ 30,00");
    expect(padNumber(7, 300)).toBe("007");
    expect(padNumber(7, 50)).toBe("07");
  });
  it("aplica máscaras", () => {
    expect(maskPhone("81988887777")).toBe("(81) 98888-7777");
    expect(maskCpf("52998224725")).toBe("529.982.247-25");
  });
  it("valida CPF e celular", () => {
    expect(isValidCpf("529.982.247-25")).toBe(true);
    expect(isValidCpf("111.111.111-11")).toBe(false);
    expect(isValidCpf("123.456.789-00")).toBe(false);
    expect(isValidPhone("(81) 98888-7777")).toBe(true);
    expect(isValidPhone("(81) 3333-4444")).toBe(false);
  });
});
