# Prompt para configurar e publicar a rifa

Abra este projeto no **Claude Code** (ou em outro assistente de código com acesso ao terminal), dentro da pasta do
repositório. Copie o bloco abaixo e cole como primeira mensagem. Antes, preencha os campos entre `<...>`. O que você
ainda não souber pode ficar como está: o assistente vai perguntar.

---

```text
Você vai me ajudar a configurar e publicar, de graça, o site da minha rifa. O projeto já está pronto nesta pasta
(frontend React/Vite, API FastAPI, banco Supabase, Pix pelo Mercado Pago). Leia o README.md antes de começar.

Meus dados:
- Nome que aparece no site: <Rodrigo>
- WhatsApp: <(81) 98630-2122>
- Instagram (opcional): <rodrigopumaa_>
- Usuário do GitHub: <rodrigopuma>
- Nome do repositório: <rifa-baile>
- Data do sorteio (concurso da Loteria Federal, quarta ou sábado): <2026-12-19>
- Prêmio: <R$ 150,00 no Pix>   Preço: <5,00>   Quantidade de números: <200>

Regras para você seguir:
1. Trabalhe em etapas, nesta ordem, e espere eu confirmar o fim de cada uma antes de seguir.
2. Tudo o que for clique em painel (GitHub, Supabase, Render, Mercado Pago) eu faço. Você me diz exatamente onde
   clicar e o que copiar, e eu te devolvo os valores.
3. Nunca coloque senhas, tokens ou a connection string do banco em arquivos versionados. Eles vão só nas variáveis
   de ambiente do Render ou num .env local (que está no .gitignore). A chave "anon" do Supabase é pública e pode ir
   nas Variables do GitHub.
4. Não mude PAYMENT_MODE para mercadopago_live nem preencha LIVE_PAYMENTS_ACKNOWLEDGEMENT. O site fica em modo de
   teste (simulador ou credenciais de teste do Mercado Pago).
5. Depois de cada etapa, teste e me mostre o resultado.

Etapas:
A) Configuração: preencha campanha.json com meus dados (incluindo site.endereco =
   https://<usuario>.github.io/<repositorio>/). Rode "python -m scripts.aplicar_campanha --ver" na pasta backend e
   me mostre o regulamento gerado para eu revisar.
B) Testes locais: instale as dependências (backend: requirements-dev.txt; frontend: npm ci), rode os testes do
   backend (pytest) e do frontend (npm test). Suba os dois servidores em modo simulador e me diga como abrir.
C) GitHub: inicialize o git (branch main), crie o repositório PÚBLICO <repositorio> com "gh repo create" (ou me
   guie pela interface) e faça o push. Me guie para ativar Settings → Pages → Source: GitHub Actions.
D) Supabase: me guie para criar o projeto (plano Free, região São Paulo). Aplique as migrations de
   supabase/migrations em ordem (pelo SQL Editor ou pela Supabase CLI). Peça e guarde:
   - a connection string do "Session pooler" (porta 5432; troque o prefixo para postgresql+psycopg://)
   - Project URL, chave anon e, se existir, o JWT Secret legado
   Me guie para criar meu usuário em Authentication → Users e para autorizá-lo como administrador com:
     insert into public.admin_users (id, email, name)
     select id, email, '<Rodrigo>' from auth.users where email = '<rodrigopumalimareserva@gmail.com>';
E) Render: me guie para criar o serviço pelo Blueprint (render.yaml) e preencher as variáveis de ambiente:
   DATABASE_URL, SUPABASE_URL, SUPABASE_JWT_SECRET, PUBLIC_BASE_URL (URL do Render),
   FRONTEND_URL (https://<usuario>.github.io/<repositorio>), CORS_ORIGINS (https://<usuario>.github.io).
   Depois do deploy, confira /api/health e /api/campaign.
F) GitHub Pages: me guie para criar em Settings → Secrets and variables → Actions → Variables:
   VITE_API_URL (URL do Render), VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY. Rode o workflow "Site (GitHub Pages)"
   e confira o site no ar: escolher números, gerar Pix no simulador, aprovar e ver o comprovante; depois entrar no
   /admin com meu usuário.
G) (Opcional) Mercado Pago em modo de TESTE: me guie para pegar as credenciais de teste e a assinatura secreta
   de webhooks (URL: <PUBLIC_BASE_URL>/api/webhooks/mercadopago, evento "Pagamentos"). Troque no Render:
   PAYMENT_MODE=mercadopago_test, ENVIRONMENT=production, MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET. Teste um pagamento
   com usuário de teste.
H) Me entregue um resumo final com: endereço do site, endereço do painel, onde editar a rifa (campanha.json)
   e o que fazer no dia do sorteio.
```

---

## Depois de configurado: como mudar algo

1. Edite `campanha.json` (ou `REGULAMENTO.md`) direto no GitHub. Clique no arquivo → ícone de lápis → *Commit changes*.
2. Em 2 a 5 minutos, o GitHub Pages republica o site e o Render reinicia a API, aplicando as mudanças no banco.
3. O preço não muda depois do primeiro pedido, e a quantidade só pode diminuir se os números removidos estiverem livres.
   Se o arquivo pedir algo impossível, a API continua no ar, mantém a configuração anterior e registra o erro no log
   do Render.
