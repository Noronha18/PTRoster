# Acompanhamento Semanal — Design

Data: 2026-10-15
Status: aprovado em conversa, aguardando revisão da spec escrita

## Contexto e objetivo

Feedback de um personal trainer da cidade, que usa o MFIT (líder local), apontou três dores:

1. **Registro por série:** prescreve "4x 12–15" e quer que o aluno registre, série a série, repetições feitas e carga usada. No MFIT isso é feito com gambiarra no campo de intervalo.
2. **Histórico some:** ao trocar o treino por um novo, os registros se perdem. Ele copia tudo, aluno por aluno, para uma planilha.
3. **Volume por grupo muscular:** controla em planilha quantas séries semanais cada músculo recebe.

O PTRoster tem hoje o mesmo defeito do MFIT: `Prescricao.carga` é uma string única que o aluno sobrescreve (`PATCH /prescricoes/{id}/carga`), presa ao plano. Resolver as três dores é o diferencial de venda frente ao MFIT.

Além disso, o trainer atende em duas modalidades — presencial e consultoria online — e a consultoria não usa saldo de aulas, mas um vencimento de contrato.

### Critérios de sucesso

- O trainer vê a evolução de carga e repetições de qualquer exercício de um aluno, semana a semana, sem planilha, mesmo após trocar de plano.
- O trainer vê volume semanal planejado vs. realizado por grupo muscular.
- O trainer recebe no painel, em até ~30 s, o registro de um treino concluído pelo aluno.
- Alunos de consultoria têm vencimento próprio, com trava de acesso opcional e avisos antecipados.

## Decomposição e ordem de entrega

Três partes, cada uma entregável sozinha. Um plano de implementação por parte.

1. **Modalidade Consultoria** (independente)
2. **Registro por série + histórico** (independente)
3. **Planejamento semanal + volume** (o "realizado" depende da parte 2)

Repositórios afetados: este (backend + painel do trainer) e `~/Documentos/projetos/ptroster-alunos` (Portal do Aluno).

---

## Parte 1 — Modalidade Consultoria

### Dados

`Aluno` ganha:

| Campo | Tipo | Default | Observação |
|---|---|---|---|
| `modalidade` | String | `"presencial"` | `"presencial"` ou `"consultoria"`. Alunos existentes migram como presencial. |
| `data_vencimento_consultoria` | Date, nullable | `NULL` | Usado só na consultoria. |
| `bloquear_apos_vencimento` | Boolean | `False` | Usado só na consultoria. |

Presencial mantém `tipo_pagamento` (mensal/pacote), `saldo_aulas` e `dia_vencimento` como hoje. Consultoria ignora esses três campos.

### Cadastro do aluno (FormAlunoModal)

- Seletor "Modalidade": Presencial | Consultoria.
- Presencial: campos atuais.
- Consultoria: "Vencimento da consultoria" (date) e checkbox "Bloquear acesso aos treinos após o vencimento".

### Pagamento

Para aluno de consultoria, o modal de pagamento pede "Novo vencimento" (obrigatório). Salvar o pagamento atualiza `data_vencimento_consultoria`. Não mexe em saldo. Presencial continua igual.

### Status financeiro

- Consultoria: `em_dia` se `data_vencimento_consultoria >= hoje`, senão `atrasado`. Vencimento nulo = `atrasado`.
- Entra nos KPIs e no gráfico de inadimplência existentes.

### Trava de acesso

Condição: `modalidade == "consultoria"` e `bloquear_apos_vencimento` e `data_vencimento_consultoria < hoje`.

- O aluno continua fazendo login. `GET /alunos/me` retorna `acesso_bloqueado: true`.
- Os endpoints de treino do aluno (listar planos/treinos do próprio aluno, `POST /sessoes/execucao`, consultas de histórico do próprio aluno) retornam `403` com `detail` de código fixo `consultoria_vencida`.
- A checagem fica numa dependência FastAPI única, reutilizada por todos esses endpoints, no backend. O front apenas reage.
- Portal: ao receber `acesso_bloqueado` ou o 403, mostra a tela "Sua consultoria venceu. Fale com seu treinador."
- O trainer nunca é bloqueado.

### Avisos (janela fixa de 7 dias)

Calculados na consulta. Sem job agendado nem tabela de notificações.

- **Consultoria vencendo/vencida:** `data_vencimento_consultoria - hoje <= 7` (inclui vencidas).
- **Programa terminando:** plano ativo com `data_inicio + duracao_semanas*7 - hoje <= 7`. Vale para as duas modalidades.

Exibição:

- Dashboard do trainer: card "Atenção" com duas listas (consultorias, programas). Endpoint `GET /avisos`.
- Detalhe do aluno: badges com os mesmos avisos.
- Portal do Aluno: banner "Seu programa termina em X dias" / "Sua consultoria vence em X dias", a partir de campos calculados em `GET /alunos/me`.

### Testes (parte 1)

- Status financeiro por modalidade (em dia, vencida, vencimento nulo).
- 403 `consultoria_vencida` com trava ativa e vencida; acesso liberado sem trava; liberado antes do vencimento.
- Pagamento de consultoria renova o vencimento e não altera saldo.
- Avisos: limites de 7 dias (dia 7 entra, dia 8 não), plano inativo não gera aviso, isolamento por trainer.

---

## Parte 2 — Registro por série + histórico

### Dados

`SessaoTreino` ganha:

- `treino_id` → `treinos.id`, nullable, `ON DELETE SET NULL`.
- `registrado_por`: `"aluno"` ou `"trainer"`.

Nova tabela `registros_serie`:

| Campo | Tipo | Observação |
|---|---|---|
| `id` | Integer PK | |
| `sessao_id` | FK `sessoes_treino.id`, `ON DELETE CASCADE` | |
| `exercicio_id` | FK `exercicios.id` | Chave do histórico. |
| `prescricao_id` | FK `prescricoes.id`, nullable, `ON DELETE SET NULL` | Referência ao que foi prescrito. |
| `numero_serie` | Integer | 1..N |
| `repeticoes` | Integer | |
| `carga_kg` | Float, nullable | Nulo para peso corporal. |

Índice em `(exercicio_id, sessao_id)`. O histórico é consultado por aluno + exercício via join com a sessão. Apagar ou trocar o plano não apaga registros.

### API

- `POST /sessoes/execucao`: cria sessão + séries numa transação só. Body: `treino_id`, `data_hora` (opcional), `series: [{prescricao_id?, exercicio_id, numero_serie, repeticoes, carga_kg}]`, `observacoes_performance` (opcional).
  - Chamado pelo aluno: `aluno_id` vem do token, `registrado_por="aluno"`, `realizada=True`, sem débito de saldo (regra atual mantida). Sujeito à trava da parte 1.
  - Chamado pelo trainer: informa `aluno_id`, `registrado_por="trainer"`, aplica a regra de débito de pacote existente.
  - Valida que `treino_id` pertence a plano do aluno e que cada `exercicio_id` existe.
- `PUT /sessoes/{id}/series` substitui as séries de uma sessão. `DELETE /sessoes/{id}` já existe. Trainer edita/exclui qualquer sessão dos seus alunos. Aluno edita/exclui só as próprias.
- `GET /alunos/{id}/ultima-execucao?treino_id=` retorna, por exercício do treino, as séries da última execução. Usado para pré-preenchimento. Versão do aluno em `/alunos/me/...`.
- `GET /alunos/{id}/evolucao?exercicio_id=` retorna, por semana (segunda a domingo), as séries feitas, a carga máxima e o volume de carga (Σ reps × kg).
- `GET /atividade-recente?limit=20` (trainer) retorna as últimas sessões dos alunos do trainer, com nome do aluno, nome do treino, horário e, por exercício, carga máxima e delta vs. a sessão anterior do mesmo aluno no mesmo exercício.
- `PATCH /prescricoes/{id}/carga` é removido depois que o Portal do Aluno migrar para `POST /sessoes/execucao`. `Prescricao.carga` volta a ser apenas a carga prescrita pelo trainer.

### Portal do Aluno

- Nas linhas de série que já existem em `Treinos.jsx` (toggle + timer de descanso), cada série ganha os campos **reps** e **kg**.
- Pré-preenchimento: valores da última execução daquele exercício e série. Sem histórico, usa a carga prescrita e o limite inferior das repetições prescritas.
- Rascunho salvo em `localStorage` (chave por aluno + treino), envolvido em try/catch. É limpo ao concluir.
- Botão "Concluir treino" envia `POST /sessoes/execucao`. Em erro, o rascunho permanece e o toast oferece tentar de novo.

### Painel do trainer

- `ModalRegistrarSessao`: seleção do treino (A/B/C) e a mesma grade de séries, pré-preenchida.
- Detalhe do aluno, aba **Evolução**: seletor de exercício (só os que têm registros); tabela semana a semana (ex.: `12×40 · 12×40 · 11×42,5 · 10×42,5`); gráfico recharts de carga máxima e volume de carga por semana.
- Dashboard: feed **Atividade recente** com polling de 30 s apenas com a aba visível (`document.visibilityState`). Exemplo: "João · Treino A · 14:32 · Remada curvada 42,5 kg (+2,5 kg)". Clicar abre a sessão.

### Fora do escopo

RPE/RIR, observação por série, recordes pessoais, push/WebSocket.

### Testes (parte 2)

- Sessão + séries numa transação: série inválida não grava nada.
- Isolamento multi-tenant: aluno e trainer de outro tenant não leem nem gravam.
- Aluno não edita sessão de outro aluno.
- Histórico permanece após excluir o plano.
- `ultima-execucao` retorna a sessão mais recente.
- Delta do feed vs. sessão anterior; primeira sessão sem delta.
- Débito de saldo só quando registrado pelo trainer em aluno de pacote.
- Trava de consultoria bloqueia `POST /sessoes/execucao` do aluno.

---

## Parte 3 — Planejamento semanal + volume por grupo muscular

### Dados

`Treino` ganha:

- `vezes_por_semana`: Integer, default 1, entre 1 e 7.
- `dias_sugeridos`: coluna `JSON` com lista de inteiros (0 = segunda … 6 = domingo). Lista vazia = sem sugestão. `JSON` funciona em Postgres e no SQLite dos testes.

### Grupos musculares padronizados

Lista fixa: Peito, Costas, Ombros, Bíceps, Tríceps, Quadríceps, Posterior, Glúteos, Panturrilha, Core, Cardio, Funcional, Outros.

- Backend: validação no schema de exercício. A entrada é comparada sem diferenciar maiúsculas/minúsculas e gravada na forma canônica (`costas` → `Costas`). Valor fora da lista = 422.
- Frontend (BibliotecaExercicios): o campo de texto livre vira select com a lista.
- Nome de exercício: a unicidade passa a ignorar maiúsculas/minúsculas (índice único em `lower(nome)`). O cadastro de duplicata retorna erro claro ("Exercício já existe"). A migração aborta e lista os conflitos se já houver duplicatas que diferem só na caixa.
- Migração de dados:
  - Os 11 exercícios "Pernas" do seed recebem o grupo correto por nome (mapa explícito).
  - O seed é atualizado com os novos grupos.
  - Grupos existentes que casam sem diferenciar caixa são normalizados.
  - O que não casar (incluindo "Pernas" de exercícios personalizados) vira "Outros" para o trainer revisar.

### Prescrição (ModalPlanoTreino)

- Cada treino ganha "Vezes/semana" (1–7) e chips de dias (S T Q Q S S D).
- Painel "Volume semanal planejado", calculado ao vivo no front: `Σ séries × vezes_por_semana` por grupo muscular.

### API

- `GET /alunos/{id}/semana?ref=YYYY-MM-DD` (trainer) retorna, para a semana (segunda a domingo) que contém `ref`:
  - aderência por treino: `{treino, vezes_por_semana, feitas, dias_feitos}`;
  - volume por grupo: `{grupo, planejado, realizado, media_4_semanas}`, onde realizado = número de séries registradas em `registros_serie` agrupadas pelo `grupo_muscular` do exercício.
- O planejado usa o plano ativo do aluno. O cálculo do planejado vive numa função única no backend.
- Versão do aluno (`/alunos/me/semana`) com treino sugerido para hoje e progresso. Sujeita à trava.

### Detalhe do aluno, aba Semana

Aderência (`Treino A 1/2 · Treino B 1/1`, com dias feitos), tabela de volume planejado | realizado | média 4 semanas, e navegação entre semanas.

### Portal do Aluno

- Card "Hoje": treino sugerido pelo dia. Sem sugestão, mostra o próximo treino ainda não concluído na semana.
- Progresso da semana: `A 1/2 · B 0/1`.

### Testes (parte 3)

- Planejado com `vezes_por_semana > 1`.
- Realizado conta só séries da semana de referência (limites segunda 00:00 e domingo 23:59).
- Grupo normalizado sem diferenciar caixa; grupo fora da lista rejeitado.
- Nome de exercício duplicado com caixa diferente rejeitado.
- Isolamento multi-tenant no endpoint da semana.

---

## Decisões registradas

- Registro em tabela normalizada (`registros_serie`), não JSON na sessão nem snapshot da prescrição. Motivo: consultas de evolução e volume viram SQL simples, e o histórico fica independente do plano.
- "Tempo real" = polling de 30 s com aba visível. SSE/WebSocket e push ficam de fora (plano free do Render e complexidade).
- Cada exercício conta para um único grupo muscular.
- Janela de aviso fixa em 7 dias.
- Vencimento da consultoria fica no aluno (contrato). O fim do programa vem do plano (`data_inicio + duracao_semanas`).
