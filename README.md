# PTRoster
 
> Plataforma web para personal trainers gerenciarem alunos, prescreverem treinos e acompanharem frequência e receita.
 
O **PTRoster** é um sistema full-stack multi-tenant: cada personal trainer acessa apenas os próprios alunos, planos e pagamentos. A prescrição técnica (planos, treinos, exercícios) fica separada da execução (sessões e cargas registradas), o que permite acompanhar a evolução de cada aluno e a saúde financeira do negócio.
 
O ecossistema tem duas interfaces:
 
| App | Público | Repositório |
|---|---|---|
| **Painel do Personal** (este repo) | Personal trainers e admin | `Personal_System1.0` |
| **Portal do Aluno** (PWA mobile) | Alunos, durante o treino | [`ptroster-alunos`](https://github.com/Noronha18/ptroster-alunos) |
 
---
 
## Funcionalidades
 
### Acesso e multi-tenancy
- Autenticação **JWT** (PyJWT + bcrypt) com três papéis: `admin`, `trainer` e `aluno`.
- Isolamento por personal: os dados de cada trainer ficam filtrados por `trainer_id` em todas as rotas.
- **Painel admin:** criação de trainers, atribuição ou troca do trainer de um aluno e redefinição de senha por usuário.
### Gestão de alunos
- Cadastro com dados pessoais, objetivo, restrições e frequência semanal planejada.
- Modalidades de cobrança: **mensalidade** (com dia de vencimento) ou **pacote de aulas** (com saldo).
- Status **ativo**, **suspenso** ou **cancelado**.
- Credenciais de acesso ao Portal do Aluno geradas pelo personal. A conta do usuário é removida junto com o aluno.
### Prescrição de treinos
- **Biblioteca de exercícios** com 48 exercícios base por grupo muscular, cada um com vídeo demonstrativo do YouTube.
- **Planos de treino** organizados em blocos (Treino A, B, C…), com séries, repetições, carga, descanso, observações e **método** (convencional, bi-set, tri-set, circuito…).
- Reordenação de treinos e exercícios.
- **Templates** de plano reutilizáveis e clonagem de plano para outro aluno.
### Frequência e check-in
- Registro de sessões realizadas, faltas e reposições, com check-in rápido.
- Check-in pelo plano prescrito ou como **atividade livre** (corrida, funcional etc.).
- Indicador de frequência mensal (realizado × planejado).
- **Débito automático de saldo** para alunos de pacote quando o personal registra a sessão. Os check-ins feitos pelo próprio aluno não debitam, e o débito é atômico, de modo que o saldo nunca fica negativo.
### Financeiro
- Registro de pagamentos (PIX, dinheiro, cartão) com mês de referência. Para alunos de pacote, a compra soma aulas ao saldo.
- **Dashboard financeiro** com KPIs (receita mensal, ticket médio, inadimplência) e gráficos (Recharts).
- Status financeiro por aluno: em dia ou atrasado.
### API para o Portal do Aluno
- `GET /alunos/me` devolve perfil, planos, treinos e prescrições do aluno logado.
- `PATCH /prescricoes/{id}/carga`: o aluno registra a própria carga por exercício.
- `POST /sessoes/`: check-in feito pelo aluno.
---
 
## Stack
 
| Camada | Tecnologia |
|---|---|
| Backend | FastAPI · Python 3.12 · SQLAlchemy 2.x (async, `asyncpg`) · Pydantic v2 · `pydantic-settings` |
| Banco | PostgreSQL 15 (Docker) · migrações com Alembic |
| Auth | PyJWT (HS256) · bcrypt |
| Frontend | React 19 · Vite 7 · Tailwind CSS 4 · Recharts · lucide-react |
| Testes | pytest · httpx · anyio · aiosqlite (banco em memória) |
| Infra | Docker multi-stage · Render · `uv` |
 
**Visual do painel:** tema claro em tons de cinza quente (zinc), com acento cobre/âmbar e tipografia Inter + Geist Mono.
 
---
 
## Estrutura
 
```
.
├── backend/
│   ├── src/
│   │   ├── api.py              # App FastAPI, middlewares, handlers de erro, routers
│   │   ├── config.py           # Settings (.env)
│   │   ├── database.py         # Engine async + sessão
│   │   ├── models.py           # Usuario, Aluno, Pagamento, SessaoTreino, PlanoTreino, Treino, Exercicio, Prescricao
│   │   ├── schemas.py          # Schemas Pydantic
│   │   ├── controllers.py      # Regras de negócio
│   │   ├── security.py         # Hash de senha, JWT, dependências de papel
│   │   ├── create_admin.py     # Cria o usuário admin inicial
│   │   ├── seed_exercicios.py  # Biblioteca base de exercícios
│   │   └── routes/             # auth, admin, alunos, meu_perfil, planos, prescricoes, exercicios, pagamentos, sessoes
│   ├── alembic/                # Migrações
│   ├── tests/                  # Testes de integração da API
│   └── .env.example
├── frontend/
│   └── src/
│       ├── features/           # admin, auth, alunos, treinos, sessoes, pagamentos, financeiro
│       ├── components/
│       └── services/api.js     # Cliente HTTP
├── docker-compose.yml          # PostgreSQL local
├── Dockerfile                  # Build do frontend + imagem do backend
└── render.yaml
```
 
---
 
## Como executar localmente
 
### Requisitos
- Docker e Docker Compose
- [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+
### 1. Banco de dados
```bash
docker compose up -d
```
 
### 2. Backend
```bash
cd backend
cp .env.example .env              # defina SECRET_KEY (mín. 32 caracteres): openssl rand -hex 32
uv sync                           # instala as dependências
uv run alembic upgrade head       # aplica as migrações
uv run python -m src.create_admin # cria o usuário admin inicial
uv run uvicorn src.api:app --reload --port 8000
```
 
> O usuário inicial é **`admin` / `admin123`**. Troque a senha no primeiro acesso.
>
> Para popular a biblioteca de exercícios, faça login como trainer ou admin e chame `POST /exercicios/seed`.
 
A documentação interativa da API fica em `http://localhost:8000/docs`.
 
### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
 
O painel abre em `http://localhost:5173` e, em desenvolvimento, aponta para a API em `http://127.0.0.1:8000`. Para mudar o endereço, use `VITE_API_URL`.
 
### Variáveis de ambiente (backend)
 
| Variável | Descrição |
|---|---|
| `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`, `DB_NAME` | Conexão com o PostgreSQL (o padrão casa com o `docker-compose.yml`) |
| `DATABASE_URL_DIRECT` | URL completa (Render, Neon, Supabase). Tem prioridade sobre os campos acima |
| `SECRET_KEY` | **Obrigatória.** Chave de assinatura do JWT (mín. 32 caracteres) |
 
---
 
## Testes
 
Os testes usam SQLite em memória (`aiosqlite`), então não precisam de PostgreSQL. A suíte cobre o cadastro de alunos, os planos de treino, as regras críticas de saldo e frequência e as correções de auditoria, como o isolamento multi-tenant.
 
```bash
cd backend
uv run pytest
```
 
---
 
## Deploy
 
O deploy roda no **Render** como serviço Docker ([`render.yaml`](./render.yaml)). O `Dockerfile` é multi-stage:
 
1. Compila o frontend com Node 20.
2. Monta a imagem Python 3.12 com as dependências via `uv`, roda tudo com usuário não-root e o FastAPI serve o build do frontend como arquivos estáticos.
3. Ao iniciar, executa `alembic upgrade head`, depois `python -m src.create_admin` e sobe o `uvicorn`.
Frontend e API ficam no mesmo domínio (`ptroster-app.onrender.com`). O Portal do Aluno fica em um domínio próprio, já liberado no CORS.
 
---
 
## Roadmap
 
- [x] Autenticação com papéis e isolamento multi-tenant
- [x] Biblioteca de exercícios com vídeos demonstrativos
- [x] App do aluno (PWA) → [`ptroster-alunos`](https://github.com/Noronha18/ptroster-alunos)
- [ ] Gráficos de evolução de carga (kg × tempo) por exercício
- [ ] Notificações de vencimento e renovação de pacote (WhatsApp/e-mail)
- [ ] Validação de CPF no cadastro de alunos
---
 
## Autor
 
Desenvolvido por **Emmanuel Noronha**, desenvolvedor Full-Stack e ex-supervisor e instrutor de musculação.
