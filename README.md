# Rifa Solidária — Baile de Formatura de Aspirantes-a-Oficial (CPOR/R)

Site da rifa organizada por Rodrigo, Aspirante-a-Oficial formando do CPOR/R, para ajudar a custear a participação dele
no baile de formatura. O participante escolhe vários números na grade, informa os dados, paga por Pix e recebe um
comprovante. O organizador acompanha tudo em um painel administrativo.

**Para configurar a rifa, edite um único arquivo: [`campanha.json`](campanha.json).** O texto do regulamento fica em
[`REGULAMENTO.md`](REGULAMENTO.md). Para publicar de graça, veja [Publicar de graça](#publicar-de-graça) ou use o
[`PROMPT_CONFIGURACAO.md`](PROMPT_CONFIGURACAO.md) com o Claude Code.

> **O sistema começa em ambiente de testes.** Por padrão ele usa um **simulador local** de Pix. Também pode usar as
> **credenciais de teste do Mercado Pago**. Cobranças reais ficam **bloqueadas no código** até que você confirme
> duas coisas: a autorização legal da modalidade e a aceitação pelo Mercado Pago (ver [Produção](#produção)).

## Estrutura

```
backend/     FastAPI + SQLAlchemy (Python 3.11+)
  app/
    routers/     public.py · webhooks.py · admin.py · simulator.py
    services/    orders.py · reservations.py · payments.py · campaigns.py · audit.py
    providers/   mercadopago.py · simulator.py
    worker.py    conciliação periódica (também roda via cron: python -m app.worker --once)
  scripts/       aplicar_campanha.py · create_admin.py · dev_token.py
  tests/         testes da API (SQLite e PostgreSQL)
frontend/    React + Vite + Tailwind CSS v4 (TypeScript)
supabase/migrations/   esquema PostgreSQL, RLS, Realtime
campanha.json          ← configuração única da rifa
REGULAMENTO.md         ← texto do regulamento ({{variáveis}} preenchidas a partir do campanha.json)
render.yaml            API no Render (plano gratuito)
.github/workflows/     site no GitHub Pages + testes automáticos
```

## Arquivo único de configuração

| Seção do `campanha.json` | O que controla |
|---|---|
| `campanha` | nome, subtítulo, descrição, prêmio, preço, quantidade de números, data do sorteio, status |
| `organizador` | seu nome, apresentação, WhatsApp, Instagram, foto (`frontend/public/organizador.jpg`) e mensagem de agradecimento |
| `site` | textos do cabeçalho, lema, aviso de iniciativa pessoal e endereço do site |
| `regulamento` | arquivo do regulamento (`REGULAMENTO.md`) |

Como as mudanças são aplicadas:
- **Site:** o frontend lê os textos do arquivo na hora do build.
- **API:** quando a API inicia, ela aplica o arquivo ao banco, mas só se o conteúdo mudou desde a última vez. Ao fazer
  push no GitHub, o Render redeploya e a mudança já vale.
- **Na hora:** para aplicar sem esperar o deploy, rode `cd backend && python -m scripts.aplicar_campanha`.
- **Ver o regulamento gerado:** rode `python -m scripts.aplicar_campanha --ver`.
- **Regra do sorteio:** é gerada automaticamente a partir da quantidade de números. Usa a Loteria Federal, com a mesma
  chance para todos os números quando a quantidade divide 1000 (ex.: 100, 200, 250, 500).


## Execução local (simulador, sem Supabase)

Requisitos: Python 3.11+ e Node 20+.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
#   no .env, para testar rápido sem Supabase:
#   DATABASE_URL=sqlite:///./rifa_dev.db
#   SUPABASE_JWT_SECRET=uma-frase-longa-qualquer-com-mais-de-32-caracteres
python -m scripts.aplicar_campanha                     # cria a rifa a partir do campanha.json
uvicorn app.main:app --reload --port 8000               # docs em http://localhost:8000/api/docs

# Frontend (outro terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev                                             # http://localhost:5173
```

No checkout, o modo simulador mostra botões **Simular pagamento aprovado / Recusar / Expirar Pix**. Eles ficam em uma
caixa tracejada identificada como "Simulador local — sem valor real". O QR Code gerado pelo simulador **não** é um
Pix válido.

**Painel sem Supabase (só em desenvolvimento):** gere um token com `python -m scripts.dev_token`. Depois abra
`http://localhost:5173/admin` e cole o token.

## Configuração com Supabase

1. Crie um projeto no Supabase.
2. Aplique as migrations. Com a Supabase CLI, use `supabase link` e depois `supabase db push`. Outra opção é colar os
   arquivos de `supabase/migrations/` no SQL Editor, em ordem.
3. No `backend/.env`, preencha estas variáveis:
   - `DATABASE_URL`: connection string, trocando o prefixo para `postgresql+psycopg://`.
   - `SUPABASE_URL`.
   - `SUPABASE_JWT_SECRET`: só para projetos com JWT HS256. Projetos com chaves assimétricas validam pelo JWKS automaticamente.
4. No `frontend/.env.local`, preencha `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` (use **apenas** a chave anon).
   Também defina `VITE_ALLOW_DEV_TOKEN=false`.
5. A campanha é criada automaticamente a partir do `campanha.json` quando a API inicia.
6. Crie o seu usuário em **Authentication → Users** (e-mail e senha). Depois, no **SQL Editor**, autorize esse usuário a
   entrar no painel:
   ```sql
   insert into public.admin_users (id, email, name)
   select id, email, 'Rodrigo' from auth.users where email = 'seu-email@exemplo.com';
   ```

### Modelo de acesso aos dados

- O backend conecta ao banco com o papel `postgres` e faz todas as validações.
- As tabelas com dados pessoais (`participants`, `orders`, `payments` etc.) têm **RLS habilitado e nenhuma política**.
  Os papéis `anon` e `authenticated` não leem nada delas.
- A única tabela pública é `number_availability`, com as colunas `(campaign_id, number, available)`. Ela é mantida por
  trigger e é a única transmitida pelo **Supabase Realtime**. Reservado e pago aparecem igualmente como
  "indisponível", e nenhum dado pessoal é exposto. Sem Supabase, o site consulta a disponibilidade a cada 20 s e
  quando o usuário volta para a aba.
- O CPF é enviado ao Mercado Pago, mas só a versão mascarada é armazenada (`***.456.789-**`).
- O acesso a cada pedido exige um token aleatório, guardado no banco apenas como hash SHA-256. No link do comprovante,
  o token vai no fragmento (`#t=...`), então não chega a servidores nem a logs.

## Pagamentos Pix (Mercado Pago)

### Modo de teste do Mercado Pago

```env
PAYMENT_MODE=mercadopago_test
MP_ACCESS_TOKEN=<Access Token das credenciais de TESTE>
MP_WEBHOOK_SECRET=<assinatura secreta configurada em Webhooks>
PUBLIC_BASE_URL=https://<url pública HTTPS da API>     # ex.: túnel ngrok/cloudflared em desenvolvimento
```

No painel do Mercado Pago (Suas integrações → Webhooks), cadastre `https://<api>/api/webhooks/mercadopago` com o
evento **Pagamentos**.

Se o Mercado Pago devolver um pagamento com `live_mode=true` enquanto o sistema está em modo de teste, a cobrança é
cancelada na hora e o pedido é recusado.

### Fluxo e garantias

| Etapa | Implementação |
|---|---|
| Preço | Calculado só no backend, a partir do banco. Valores enviados pelo navegador são ignorados. |
| Reserva atômica | Transação com `SELECT … FOR UPDATE` em ordem crescente (evita deadlock), `UPDATE` condicional e um índice único parcial em `order_numbers (number_id) WHERE active`. Se algum número falhar, nada é reservado. |
| Cobrança | `POST /v1/payments` com `payment_method_id=pix`, `X-Idempotency-Key` = id do pedido e `external_reference` = id do pedido. Há uma cobrança por pedido (restrição `unique`). Se a resposta se perder (timeout), o sistema recupera a cobrança por `external_reference` sem criar outra. |
| Prazo | O contador visual é de **15 min**. O vencimento enviado ao Mercado Pago é de **30 min**, o mínimo documentado (`PIX_EXPIRATION_MINUTES`, que não aceita valor menor que 30). |
| Fim dos 15 min | O checkout é encerrado visualmente e o QR some. O sistema consulta o pagamento e pede `PUT /v1/payments/{id} {"status":"cancelled"}`. |
| Liberação | Os números **só** são liberados quando o provedor confirma um estado terminal: cancelado, expirado, rejeitado ou estornado. Se o cancelamento não for aceito, os números continuam reservados até o Pix vencer no Mercado Pago. |
| Pagamento tardio | Se a aprovação chegar depois dos 15 min (Pix ainda válido), o pedido é confirmado normalmente. Se os números já tiverem sido liberados e alguém os comprou, o pedido vai para **Em análise**, com instrução de estorno. Nada é vendido duas vezes. |
| Webhooks | A assinatura `x-signature` (HMAC-SHA256) é validada e o webhook é deduplicado por `x-request-id`. O status **sempre** vem de `GET /v1/payments/{id}`, nunca do corpo da notificação. As transições são idempotentes e não geram logs ou efeitos duplicados. |
| Conciliação | Roda a cada 30 s dentro da API. Encerra checkouts vencidos, consulta pagamentos pendentes e retenta cancelamentos. Se rodar com várias instâncias, use `RUN_BACKGROUND_RECONCILER=false` nelas e um único cron com `python -m app.worker --once`. |
| Valor divergente | Se o valor pago for diferente do pedido, ou se a referência ou o modo (teste/produção) não corresponderem, o pedido vai para análise. |
| Admin | Não existe aprovação manual. O painel só oferece "Consultar Mercado Pago" e "Cancelar cobrança". |

## Painel administrativo (`/admin`)

- **Visão geral e participantes:** números livres, reservados e pagos; arrecadação bruta; pagamentos pendentes.
  Busca por nome, e-mail, telefone, número ou código do pedido. Também mostra os números de cada participante e
  exporta CSV (separado por `;`, abre direto no Excel).
- **Pagamentos:** histórico com status (pendente, aprovado, cancelado, expirado, reembolsado, em análise, recusado),
  botão de atualização por consulta ao Mercado Pago e registro de ações (`audit_logs`).
- **Configurações:** nome, subtítulo, descrição, preço, quantidade de números, data do sorteio, organizador,
  regulamento, autorização, imagem de cabeçalho e status. Só uma campanha pode estar ativa (índice único no banco).
  O preço fica travado depois do primeiro pedido. A quantidade de números só pode ser reduzida se os números
  removidos estiverem livres.

## Identidade visual

- Cores e fontes estão em `frontend/src/index.css` (bloco `@theme`). As fontes Cinzel, Oswald e Inter são
  auto-hospedadas via `@fontsource`, sem chamadas ao Google.
- Os textos fixos do cabeçalho e o aviso institucional estão em `frontend/src/lib/brand.ts`.
- A espada está em `frontend/src/components/SwordEmblem.tsx`. É um vetor **estilizado** de espada de oficial em prata:
  pomo, empunhadura em fio, guarda com arco e lâmina esguia. **Recomendo substituí-la** por um vetor feito a partir
  da referência correta fornecida pelo organizador, mantendo o `viewBox` de 360×40.
- Não foram usados distintivos, brasões nem símbolos oficiais na interface. O rodapé informa que a rifa é uma
  iniciativa pessoal e não é organizada nem endossada pelo Exército Brasileiro, pelo CPOR/R ou pela comissão de
  formatura. O texto fica em `campanha.json` → `site.aviso`.
- A foto do organizador fica em `frontend/public/organizador.jpg`. Ela foi recortada em retrato 4:5 e salva sem
  metadados (sem EXIF/localização).
- A "imagem autorizada de cabeçalho" do painel aparece ao fundo do cabeçalho, com opacidade baixa.

## Publicar de graça

| Parte | Onde | Custo | Observação |
|---|---|---|---|
| Site (frontend) | **GitHub Pages** | grátis | repositório público; publicado pelo workflow `.github/workflows/site.yml` |
| API (FastAPI) | **Render** (plano Free) | grátis | dorme após 15 min sem acesso; o primeiro acesso depois disso leva cerca de 1 min |
| Banco + login + Realtime | **Supabase** (plano Free) | grátis | pausa após 7 dias sem atividade; com a rifa rodando, isso não acontece |

Passo a passo resumido (o [`PROMPT_CONFIGURACAO.md`](PROMPT_CONFIGURACAO.md) guia cada clique):

1. **GitHub:** crie um repositório **público** (ex.: `rifa-baile`) e faça push deste projeto. Em **Settings → Pages**,
   escolha *Source: GitHub Actions*.
2. **Supabase:** crie o projeto (região São Paulo) e rode as migrations de `supabase/migrations/` no SQL Editor, em
   ordem. Em **Connect**, copie a connection string do **Session pooler** (porta 5432). O Render só conecta por IPv4, e a
   conexão direta do Supabase é IPv6. Troque o prefixo para `postgresql+psycopg://`.
3. **Render:** *New → Blueprint* → escolha o repositório (usa o `render.yaml`). Preencha as variáveis:
   - `DATABASE_URL`, `SUPABASE_URL` e `SUPABASE_JWT_SECRET`.
   - `PUBLIC_BASE_URL`: a URL `.onrender.com`.
   - `FRONTEND_URL`: `https://<usuario>.github.io/<repo>`.
   - `CORS_ORIGINS`: `https://<usuario>.github.io`.
4. **GitHub → Settings → Secrets and variables → Actions → Variables:** crie `VITE_API_URL` (URL do Render),
   `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY`. Depois rode o workflow *Site (GitHub Pages)*.
5. Abra `https://<usuario>.github.io/<repo>/` e teste o fluxo com o simulador. Depois entre em `/admin`.
6. *(Opcional)* Para o Render não "dormir" com pedidos pendentes, cadastre no cron-job.org (grátis) um
   `POST https://<api>/api/cron/reconcile` a cada 10 min, com o cabeçalho `X-Cron-Secret` igual ao `CRON_SECRET`
   gerado pelo Render. Mesmo sem isso, tudo é conciliado no próximo acesso.

## Testes

```bash
cd backend && pytest                       # SQLite
TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/rifa_test pytest   # aplica as migrations reais
cd frontend && npm test
```

Cobertura: seleção múltipla, preço calculado no servidor, indisponibilidade, concorrência (16 e 12 threads disputando
os mesmos números), criação de cobrança, perda de resposta, aprovação, recusa, cancelamento, expiração, pagamento
tardio (aceito e em conflito), aprovação durante o cancelamento, valor divergente, estorno, webhooks duplicados e com
assinatura inválida, contrato HTTP com o Mercado Pago, proteção de **todas** as rotas `/api/admin`, ausência de
aprovação manual, campanha ativa única, travas de produção, RLS do papel `anon` e a tabela pública do Realtime.

## Produção

1. **Antes de qualquer cobrança real**, verifique dois pontos. Sorteios com venda de números dependem de autorização
   prévia do Ministério da Fazenda, que hoje não é concedida a pessoa física. Além disso, a lista de produtos
   proibidos do Mercado Pago inclui rifas. O código não substitui essa verificação.
2. Depois disso, configure:
   ```env
   ENVIRONMENT=production
   PAYMENT_MODE=mercadopago_live
   LIVE_PAYMENTS_ACKNOWLEDGEMENT=AUTORIZACAO_LEGAL_E_MERCADO_PAGO_VERIFICADAS
   PUBLIC_BASE_URL=https://api.seudominio.com.br
   ```
   Sem a frase de confirmação, ou sem HTTPS, a API não inicia. Ela também recusa pedidos se a campanha não tiver o
   campo **Autorização** preenchido. O simulador não funciona com `ENVIRONMENT=production`.
3. Sirva tudo por HTTPS. O frontend é estático (`npm run build` gera `dist/`) e pode ir para Vercel, Netlify ou
   Cloudflare Pages, com rewrite de todas as rotas para `index.html`. A API pode ir para Render, Railway, Fly.io ou uma
   VM com Nginx.
4. O limitador de tentativas é em memória, por processo. Com várias instâncias, complemente com limites no proxy ou CDN.
5. Remova a tabela `dev_simulated_payments` se quiser (migration `…_dev_simulator.sql`).
