-- Tabela usada SOMENTE pelo simulador local de Pix (PAYMENT_MODE=simulator).
-- Pode ser removida em produção. Nenhum dado pessoal é armazenado aqui.
create table if not exists public.dev_simulated_payments (
  id                 varchar(64) primary key,
  external_reference varchar(64) not null,
  status             varchar(20) not null default 'pending',
  status_detail      varchar(64) not null default 'pending_waiting_transfer',
  amount_cents       integer not null,
  expires_at         timestamptz not null,
  created_at         timestamptz not null default now()
);
create index if not exists ix_dev_simulated_payments_external_reference
  on public.dev_simulated_payments (external_reference);
alter table public.dev_simulated_payments enable row level security;
revoke all on public.dev_simulated_payments from anon, authenticated;
