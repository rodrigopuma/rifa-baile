-- Pacote promocional (ex.: a cada 3 números do mesmo pedido, R$ 25,00 no conjunto).
-- Rode este arquivo no SQL Editor do Supabase ANTES de publicar a versão nova da API.
-- É seguro rodar mais de uma vez.

-- 1) Configuração do pacote na campanha. 0/0 = sem pacote.
alter table public.campaigns add column if not exists bundle_size integer not null default 0;
alter table public.campaigns add column if not exists bundle_price_cents integer not null default 0;
alter table public.campaigns drop constraint if exists ck_campaigns_bundle;
alter table public.campaigns add constraint ck_campaigns_bundle check (
  (bundle_size = 0 and bundle_price_cents = 0)
  or (bundle_size >= 2 and bundle_price_cents > 0 and bundle_price_cents < price_cents * bundle_size)
);

-- 2) O total do pedido deixa de ser sempre preço x quantidade (o pacote dá desconto):
--    agora ele só não pode ser zero nem maior que o preço cheio.
alter table public.orders drop constraint if exists ck_orders_total;
alter table public.orders add constraint ck_orders_total check (
  total_cents > 0 and total_cents <= unit_price_cents * quantity
);
