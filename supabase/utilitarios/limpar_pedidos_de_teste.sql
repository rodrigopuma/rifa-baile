-- APAGA TODOS OS PEDIDOS, PAGAMENTOS E PARTICIPANTES e libera todos os números.
-- Use só antes de lançar a rifa de verdade (por exemplo, para poder mudar preço/pacote depois de testar).
-- Rode no Supabase → SQL Editor. NÃO use depois que houver vendas reais.
begin;
  update public.numbers set status = 'available', order_id = null where status <> 'available' or order_id is not null;
  delete from public.order_numbers;
  delete from public.payments;
  delete from public.orders;
  delete from public.participants;
  -- tabela só existe no modo simulador; ignora se não existir
  do $$ begin
    if to_regclass('public.dev_simulated_payments') is not null then delete from public.dev_simulated_payments; end if;
  end $$;
commit;
