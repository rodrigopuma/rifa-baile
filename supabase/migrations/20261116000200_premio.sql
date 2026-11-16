-- Descrição do prêmio exibida no site, no regulamento e no comprovante.
alter table public.campaigns add column if not exists prize_title varchar(200) not null default '';
