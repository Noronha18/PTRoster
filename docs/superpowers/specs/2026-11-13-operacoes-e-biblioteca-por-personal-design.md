# Operações do admin e biblioteca por personal — desenho

Data: 2026-11-13. Pedido do Emmanuel (dono do produto), aprovado na conversa.

## Intenção

O PTRoster é vendido a personal trainers. Hoje:

- todos os personais veem, editam e apagam os modelos de treino uns dos outros
  (`_assert_owns_plano` libera planos sem aluno para qualquer um);
- a biblioteca de exercícios é uma só, e o vídeo de um exercício é o mesmo para
  todos os alunos;
- o admin não tem visão de quem usa a plataforma, e o financeiro dele soma o
  dinheiro dos alunos, não o que os personais pagam a ele.

O objetivo é isolar o trabalho de cada personal e dar ao admin uma tela de
Operações no estilo do módulo de Operações do Hub46, com o financeiro da
plataforma (mensalidade de cada personal).

## Objetivos

1. Cada personal tem os próprios modelos de treino e os próprios exercícios.
2. O personal pode trocar o vídeo de qualquer exercício; a troca vale só para
   os alunos dele.
3. O admin vê todos que têm acesso: personais e os alunos de cada personal, com
   sinais de uso e alertas.
4. O financeiro do admin mostra a mensalidade de cada personal (plano, pagamentos,
   em dia ou atrasado).

## Fora do escopo

- Cobrança automática (Pix, cartão, boleto) e e-mail de cobrança.
- Bloquear o personal com mensalidade atrasada. Decisão do Emmanuel: **só
  sinalizar por enquanto**.
- Abas "Funcionalidades" e "Erros" do Hub46: o PTRoster não coleta esses eventos.
- Editar exercício já cadastrado (fora o vídeo).

## Restrições

- Backend FastAPI + SQLAlchemy async + Alembic; Postgres no Supabase. Migrações
  rodam na subida do container no Render (`alembic upgrade head`).
- Painel do personal/admin: React + Tailwind (`frontend/`). Portal do aluno:
  repositório `ptroster-alunos`.
- `backend/src/models.py` usa CRLF; preservar.
- Testes do backend: `SECRET_KEY=... backend/.venv/bin/python -m pytest -q`
  (SQLite em memória, fixtures em `backend/tests/conftest.py`, marcar
  `@pytest.mark.anyio`).

## Abordagens consideradas

- **Endpoints novos no FastAPI e telas em React no painel atual** (escolhida).
  É a base que já existe.
- Copiar os componentes do Hub46: descartado. Lá é TypeScript, shadcn e RPCs do
  Supabase; aqui é outra base. Do Hub46 vem só o desenho da tela.

## Desenho

### Etapa 1 — modelos e exercícios por personal

**Dados**

- `planos_treino.trainer_id` (FK `usuarios.id`, `ON DELETE SET NULL`, nulo).
  Só faz sentido em modelo (plano sem aluno). Modelo com `trainer_id` nulo é
  **modelo da plataforma**.
- `exercicios.trainer_id` (FK `usuarios.id`, `ON DELETE SET NULL`, nulo).
  Nulo = **base da plataforma**.
- Unicidade do nome passa a ser por escopo: índice único em
  `(coalesce(trainer_id, 0), lower(nome))`. Saem o `ix_exercicios_nome` único
  (vira índice comum) e o `uq_exercicios_nome_lower`.

**Migração dos dados atuais** (decisão do Emmanuel: o que existe hoje vai para o
personal `emmanuel`)

- Procura o usuário com `lower(username) = 'emmanuel'` e papel `trainer` ou
  `admin`.
- Todos os modelos atuais (planos sem aluno) recebem esse `trainer_id`.
- Exercícios: os da lista padrão do seed (`exercicios_base`, comparando
  `lower(nome)`) continuam base (`trainer_id` nulo); os demais recebem o
  `trainer_id` do emmanuel. *Chamada minha:* sem isso a biblioteca dos outros
  personais ficaria vazia.
- Se o usuário não existir, a migração não falha: deixa tudo como base/plataforma
  e imprime um aviso. *Chamada minha:* não derrubar o deploy por isso.

**Regras de acesso** (admin continua vendo e editando tudo)

| Ação | Personal pode |
|---|---|
| Listar modelos | os próprios + os da plataforma |
| Criar modelo | sim; o modelo nasce com o `trainer_id` dele |
| Editar / apagar modelo | só os próprios |
| Copiar (clonar) | dos próprios, dos da plataforma e dos planos dos próprios alunos; o destino (aluno) precisa ser dele; cópia como modelo vira dele |
| Listar exercícios | base + os próprios |
| Criar exercício | sim; nasce dele. Recusa nome igual (sem caixa) a um da base ou a um dele |
| Prescrever exercício em plano/modelo | só base + os próprios (validar `exercicio_id` ao criar/editar plano) |
| Admin criar exercício | vira base |

- O seed (`seed_exercicios.py` e `POST /exercicios/seed`) só lê e grava a base
  (`trainer_id` nulo).
- `ExercicioPublic` ganha `trainer_id` (para a tela marcar "meu").
- `PlanoTreinoPublic` ganha `trainer_id` (para a tela marcar "da plataforma",
  sem botões de editar/apagar).

**Painel**

- Módulo Treinos: "Modelos Globais" vira "Meus modelos"; os da plataforma
  aparecem com selo "PTRoster", só com a ação de usar/copiar.
- Biblioteca: exercícios do personal com selo "Meu".

### Etapa 2 — vídeo próprio por personal

- Tabela `exercicio_videos_personal (id, trainer_id, exercicio_id, video_url)`,
  único `(trainer_id, exercicio_id)`, `ON DELETE CASCADE` nos dois.
- Exercício próprio: o personal edita o `video_url` do próprio exercício.
  Exercício da base: grava/atualiza a linha em `exercicio_videos_personal`.
  Vídeo vazio remove a troca (volta ao original).
- Rota: `PUT /exercicios/{id}/video` (`{video_url: str | null}`), escopo do
  personal logado. Admin editando base altera o original.
- Leitura: a biblioteca do personal devolve o vídeo efetivo dele. Tudo que o
  aluno lê (plano com prescrições em `/alunos/me`) devolve o vídeo efetivo do
  personal do aluno.
- Painel: na biblioteca, ação "Trocar vídeo" por exercício, com o vídeo atual e
  "Voltar ao original".

### Etapa 3 — Operações (admin)

Aba "Admin" do painel vira "Operações".

- Endpoint `GET /admin/operacoes/personais`: por personal — id, nome de usuário,
  e-mail, ativo, criado em, último acesso, alunos ativos/total, treinos
  registrados nos últimos 7 dias, último treino registrado, situação da
  mensalidade (etapa 4; até lá, "sem plano").
- Endpoint `GET /admin/operacoes/personais/{id}/alunos`: nome, situação,
  modalidade, tem login, último acesso do login, último treino, treinos em 7
  dias.
- Endpoint `GET /admin/operacoes/alunos/{id}/sessoes?limite=20`: últimas sessões.
- Endpoint `PATCH /admin/usuarios/{id}/ativo` (`{ativo: bool}`): desativar ou
  reativar acesso de um personal.
- `usuarios.ultimo_acesso` (DateTime nulo), gravado a cada login bem-sucedido
  em `/auth/token`.
- Tela:
  - Cartões-filtro (clicar filtra, clicar de novo desliga): Personais ativos ·
    Sem atividade há 7 dias · Sem alunos · Mensalidade atrasada · Vence em até
    3 dias.
  - Tabela no desktop, cartões no celular: Personal · Alunos ativos/total ·
    Último acesso · Treinos 7d · Mensalidade · Alertas.
  - Clicar no personal abre o detalhe: dados, plano e pagamentos (etapa 4),
    lista de alunos; clicar no aluno expande as últimas sessões. Ações:
    registrar pagamento, redefinir senha (já existe), desativar acesso.
  - Personais desativados numa seção recolhida "Fora do acompanhamento", fora
    dos números de cima.
  - "Cadastrar personal" vira botão no topo.
- Regras de alerta: sem atividade = nenhum treino registrado pelos alunos dele
  nem login dele há 7 dias; sem alunos = 0 alunos ativos.

### Etapa 4 — financeiro dos personais

- Tabela `planos_personal (trainer_id PK/FK, valor_mensal, dia_vencimento,
  ativo, inicio, observacao)`.
- Tabela `pagamentos_personal (id, trainer_id, referencia_mes 'MM/AAAA', valor,
  data_pagamento, forma_pagamento, observacao)`.
- Situação no mês (datas em `consultoria.hoje()`, UTC-3): **em dia** (pagamento
  da referência do mês), **vence em breve** (até 3 dias do vencimento, sem
  pagamento), **atrasada** (passou o dia de vencimento sem pagamento, com dias de
  atraso), **sem plano**.
- Endpoints admin: criar/editar plano do personal; registrar pagamento; listar
  pagamentos de um personal; resumo do mês (receita prevista = soma dos planos
  ativos, recebido no mês, valor e quantidade em atraso, lista por personal).
- Cadastro de personal ganha o campo de valor e dia de vencimento do plano.
- Para o papel `admin`, a aba "Financeiro" mostra esse resumo em vez do
  financeiro dos alunos. O personal continua vendo o financeiro dos alunos dele.

## Ordem e entrega

Uma etapa por vez, nesta ordem (1 fecha o vazamento entre personais). Cada etapa:
testes do backend, build do painel, conferência no navegador com ambiente local,
revisão, e push só com o ok do Emmanuel.

## Deixado para quem implementa

Nomes internos de funções e componentes; layout fino das telas seguindo o padrão
visual do painel atual; paginação (volumes pequenos hoje, sem paginar).
