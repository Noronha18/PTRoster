# Parte 3 — Planejamento semanal + volume por grupo muscular: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O trainer define quantas vezes por semana cada treino deve ser feito e em quais dias; o painel mostra aderência e volume planejado × realizado por grupo muscular; o portal do aluno ganha o card "Hoje" com o treino sugerido e o progresso semanal (`A 1/2 · B 0/1`).

**Architecture:** Duas colunas novas em `treinos` (`vezes_por_semana`, `dias_sugeridos`) e um módulo canônico de grupos musculares (`src/grupos_musculares.py`). Um endpoint de leitura (`GET /alunos/{id}/semana` e `GET /alunos/me/semana`) calcula, em uma única passada: aderência por treino na semana (segunda a domingo), volume planejado (prescrições × vezes/semana do plano ativo), volume realizado (séries registradas) e média das últimas 4 semanas. O painel consome o endpoint na aba "Semana" e calcula o volume planejado ao vivo no modal do plano. O portal consome a versão do aluno para o card "Hoje" e o progresso semanal.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, pytest + httpx (SQLite em memória); React 19 + Vite + Tailwind (painel e portal).

**Spec:** `docs/superpowers/specs/2026-10-15-acompanhamento-semanal-design.md` (seção "Parte 3 — Planejamento semanal + volume por grupo muscular")

## Global Constraints

- Rodar testes do backend: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`.
- Testes usam SQLite em memória com `Base.metadata.create_all`; migrações não rodam nos testes. Nada de SQL específico de PostgreSQL no código de produção.
- `backend/src/models.py` é CRLF. Editar preservando CRLF.
- Datas/horas são naive no horário de Brasília (`consultoria.hoje()` / `consultoria.agora()`).
- Semana = segunda a domingo; `dias_sugeridos` usa `0=segunda … 6=domingo` (Python `date.weekday()`).
- Grupos canônicos (ordem fixa): `Peito, Costas, Ombros, Bíceps, Tríceps, Quadríceps, Posterior, Glúteos, Panturrilha, Core, Cardio, Funcional, Outros`.
- Grupo muscular é validado no schema (case-insensitive); valor fora da lista retorna 422. Nome de exercício é único ignorando caixa (409).
- Planejado = `Prescricao.series × Treino.vezes_por_semana`, somado por grupo, do plano ativo.
- Realizado = quantidade de `RegistroSerie` na semana, por grupo do exercício.
- Média 4 semanas = média de séries realizadas por semana nas 4 semanas terminando na semana de referência (inclui a semana; semanas sem registro contam zero).
- Aderência = sessões realizadas (`SessaoTreino.realizada=True`) com `treino_id` do treino; check-ins sem treino não contam.
- Commits terminam com:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01ELN8nBWxTs2MvAF6GrjLq1
  ```
- Comentários e textos de UI em português, no estilo do código vizinho.

## Review Focus

1. **Semana errada por fuso:** uma sessão de domingo 23h precisa cair na semana que termina naquele domingo. Usar `consultoria.hoje()` e limites `[segunda 00:00, próxima segunda 00:00)`.
2. **Plano trocado no meio da semana:** o planejado usa o plano ativo atual; o realizado usa o histórico por exercício, então continua contando.
3. **Grupo legado "Pernas":** a migração de dados mapeia os 11 exercícios do seed por nome; o restante vira "Outros". O seed passa a gravar os grupos corretos.
4. **Duplicidade de exercício:** "Supino reto" e "Supino Reto" não podem coexistir; a checagem é `lower(nome)` e a migração aborta se já houver duplicidade.
5. **Aluno bloqueado:** `/alunos/me/semana` usa `exigir_acesso_treino` e retorna 403 `consultoria_vencida`.
6. **Portal sem endpoint:** se `/alunos/me/semana` falhar, o Dashboard continua funcionando com o plano atual (fallback silencioso).

---

### Task 1: Colunas de planejamento semanal em `treinos`

**Files:**
- Create: `backend/alembic/versions/d3e4f5a6b7c8_add_planejamento_semanal_treinos.py`
- Modify: `backend/src/models.py` (`Treino`)
- Modify: `backend/src/schemas.py` (`TreinoCreate`, `TreinoUpdate`, `TreinoPublic`)
- Modify: `backend/src/controllers.py` (`criar_plano_treino`, `clonar_plano_treino`, `atualizar_plano_treino`)
- Test: `backend/tests/test_semana.py` (novo; testes de payload)

**Interfaces:**
- Produces: `models.Treino.vezes_por_semana: int` (default 1) e `models.Treino.dias_sugeridos: list[int]` (default `[]`).
- Produces: schemas com `vezes_por_semana: int = Field(1, ge=1, le=7)` e `dias_sugeridos: list[int]` (validador 0..6, sem duplicatas).
- Produces: `TreinoPublic` expõe os dois campos (o portal e o painel dependem disso).

- [x] **Step 1: Escrever o teste que falha**

Em `backend/tests/test_semana.py`, criar helpers e o primeiro teste:

```python
import pytest
from httpx import AsyncClient

from src import consultoria, models

TRAINER_A = models.Usuario(id=1, username="trainer_a", role="trainer")
TRAINER_B = models.Usuario(id=2, username="trainer_b", role="trainer")


def _aluno_logado(aluno_id: int) -> models.Usuario:
    return models.Usuario(id=500 + aluno_id, username=f"aluno_{aluno_id}", role="aluno", aluno_id=aluno_id)


async def _criar_exercicio(ac: AsyncClient, nome: str, grupo: str) -> int:
    res = await ac.post("/exercicios/", json={"nome": nome, "grupo_muscular": grupo})
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _criar_aluno(ac: AsyncClient, **extras) -> int:
    res = await ac.post("/alunos/", json={"nome": "Aluno Semana", **extras})
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _criar_plano(ac: AsyncClient, aluno_id: int, treinos: list[dict]) -> dict:
    res = await ac.post(f"/alunos/{aluno_id}/planos", json={"titulo": "Plano Semana", "treinos": treinos})
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.anyio
async def test_treino_guarda_planejamento_semanal(ac: AsyncClient):
    ex = await _criar_exercicio(ac, "Supino Semana", "Peito")
    aluno_id = await _criar_aluno(ac)
    plano = await _criar_plano(ac, aluno_id, [{
        "nome": "Treino A",
        "vezes_por_semana": 2,
        "dias_sugeridos": [0, 3],
        "prescricoes": [{"exercicio_id": ex, "series": 4, "repeticoes": "10"}],
    }])

    treino = plano["treinos"][0]
    assert treino["vezes_por_semana"] == 2
    assert treino["dias_sugeridos"] == [0, 3]

    # clonar preserva
    clone = (await ac.post(f"/planos/{plano['id']}/clonar?aluno_id={aluno_id}")).json()
    assert clone["treinos"][0]["vezes_por_semana"] == 2
    assert clone["treinos"][0]["dias_sugeridos"] == [0, 3]
```

- [x] **Step 2: Rodar e ver falhar**

`... -m pytest tests/test_semana.py::test_treino_guarda_planejamento_semanal -q` → falha (campo inexistente/validação).

- [x] **Step 3: Implementar models + schemas + controllers + migração**

`models.py` (importar `JSON`):

```python
class Treino(Base):
    ...
    vezes_por_semana = Column(Integer, default=1, nullable=False)
    dias_sugeridos = Column(JSON, default=list, nullable=False)
```

`schemas.py`:

```python
from pydantic import field_validator

class TreinoCreate(BaseModel):
    nome: str
    vezes_por_semana: int = Field(1, ge=1, le=7)
    dias_sugeridos: List[int] = Field(default_factory=list)
    prescricoes: List[PrescricaoCreate]

    @field_validator("dias_sugeridos")
    @classmethod
    def _dias_validos(cls, dias: List[int]) -> List[int]:
        if any(d < 0 or d > 6 for d in dias):
            raise ValueError("dias_sugeridos deve conter valores entre 0 (segunda) e 6 (domingo)")
        return sorted(set(dias))

class TreinoUpdate(BaseModel):
    id: Optional[int] = None
    nome: str
    vezes_por_semana: Optional[int] = Field(None, ge=1, le=7)
    dias_sugeridos: Optional[List[int]] = None
    prescricoes: List[PrescricaoUpdate]

class TreinoPublic(BaseModel):
    id: int
    nome: str
    vezes_por_semana: int = 1
    dias_sugeridos: List[int] = Field(default_factory=list)
    prescricoes: List[PrescricaoPublic]
    model_config = ConfigDict(from_attributes=True)
```

Controllers: em `criar_plano_treino` incluir `vezes_por_semana=treino_data.vezes_por_semana, dias_sugeridos=treino_data.dias_sugeridos`; em `clonar` copiar os dois; em `atualizar`, no treino existente atualizar apenas se não nulo:

```python
if t_data.vezes_por_semana is not None:
    treino.vezes_por_semana = t_data.vezes_por_semana
if t_data.dias_sugeridos is not None:
    treino.dias_sugeridos = t_data.dias_sugeridos
```

Migração `d3e4f5a6b7c8` (`down_revision = "c2d3e4f5a6b7"`):

```python
op.add_column('treinos', sa.Column('vezes_por_semana', sa.Integer(), nullable=False, server_default='1'))
op.add_column('treinos', sa.Column('dias_sugeridos', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
# downgrade: drop_column
```

- [x] **Step 4: Rodar e ver passar**

- [x] **Step 5: Commit**

`feat: planejamento semanal por treino (vezes e dias sugeridos)`

---

### Task 2: Grupos musculares canônicos + nome de exercício único sem caixa

**Files:**
- Create: `backend/src/grupos_musculares.py`
- Create: `backend/alembic/versions/e4f5a6b7c8d9_normaliza_grupos_e_nome_exercicio.py`
- Modify: `backend/src/schemas.py` (`ExercicioBase`)
- Modify: `backend/src/controllers.py` (`criar_exercicio`)
- Modify: `backend/src/models.py` (`Exercicio.__table_args__` com índice funcional)
- Modify: `backend/src/seed_exercicios.py` (11 exercícios "Pernas")
- Test: `backend/tests/test_semana.py`, `test_alunos.py`, `test_planos_treino.py`, `test_correcoes_auditoria.py`

**Interfaces:**
- Produces: `grupos_musculares.GRUPOS_MUSCULARES` (tupla na ordem canônica), `normalizar_grupo(valor) -> str | None`.
- Produces: `ExercicioBase.grupo_muscular` normalizado; inválido → 422.
- Produces: `criar_exercicio` rejeita nome duplicado ignorando caixa com 409.

- [x] **Step 1: Escrever testes que falham**

```python
@pytest.mark.anyio
async def test_grupo_muscular_e_normalizado_e_validado(ac: AsyncClient):
    ok = await ac.post("/exercicios/", json={"nome": "Remada Caixa", "grupo_muscular": "costas"})
    assert ok.status_code == 201
    assert ok.json()["grupo_muscular"] == "Costas"

    invalido = await ac.post("/exercicios/", json={"nome": "Exercicio Invalido", "grupo_muscular": "Pernas"})
    assert invalido.status_code == 422


@pytest.mark.anyio
async def test_nome_de_exercicio_unico_ignorando_caixa(ac: AsyncClient):
    assert (await ac.post("/exercicios/", json={"nome": "Supino Case", "grupo_muscular": "Peito"})).status_code == 201
    dup = await ac.post("/exercicios/", json={"nome": "supino case", "grupo_muscular": "Peito"})
    assert dup.status_code == 409
```

- [x] **Step 2: Rodar e ver falhar**

- [x] **Step 3: Implementar**

`grupos_musculares.py`:

```python
import unicodedata

GRUPOS_MUSCULARES = (
    "Peito", "Costas", "Ombros", "Bíceps", "Tríceps", "Quadríceps",
    "Posterior", "Glúteos", "Panturrilha", "Core", "Cardio", "Funcional", "Outros",
)

def _chave(valor: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
    return sem_acento.strip().lower()

_MAPA = {_chave(g): g for g in GRUPOS_MUSCULARES}

def normalizar_grupo(valor: str) -> str | None:
    return _MAPA.get(_chave(valor or ""))
```

`ExercicioBase`:

```python
@field_validator("grupo_muscular")
@classmethod
def _grupo_canonico(cls, valor: str) -> str:
    from src.grupos_musculares import GRUPOS_MUSCULARES, normalizar_grupo
    canonico = normalizar_grupo(valor)
    if canonico is None:
        raise ValueError(f"Grupo muscular inválido. Use um de: {', '.join(GRUPOS_MUSCULARES)}")
    return canonico
```

`criar_exercicio`: trocar a checagem por `func.lower(models.Exercicio.nome) == exercicio_in.nome.strip().lower()` e capturar `IntegrityError` → `BusinessRuleError`. Normalizar `nome` com `.strip()`.

`models.Exercicio`:

```python
__table_args__ = (Index('uq_exercicios_nome_lower', func.lower(nome), unique=True),)
```

(importar `func`.)

Migração `e4f5a6b7c8d9`:
- Ler todas as linhas de `exercicios` com Python (`op.get_bind().execute(sa.text(...))`).
- Normalizar grupos com a mesma lógica (lista duplicada na migração).
- Mapa explícito de "Pernas" por nome:
  - Quadríceps: Agachamento Livre Barra, Leg Press 45º, Cadeira Extensora, Afundo com Halteres, Hack Squat.
  - Posterior: Stiff Barra, Mesa Flexora, Cadeira Flexora.
  - Glúteos: Elevação Pélvica, Cadeira Abdutora, Cadeira Adutora.
- Grupo não reconhecido → "Outros".
- Antes do índice, verificar duplicatas `lower(nome)` e `raise RuntimeError` listando os nomes.
- `op.execute("CREATE UNIQUE INDEX uq_exercicios_nome_lower ON exercicios (lower(nome))")`; downgrade `DROP INDEX`.
- `down_revision = "d3e4f5a6b7c8"`.

Seed: trocar os 11 `"Pernas"` pelos grupos acima. Atualizar também o grupo de exercícios existentes no `_run_seed` (`elif existente.grupo_muscular != ex_data["grupo_muscular"]: existente.grupo_muscular = ...`).

Testes existentes: `Peitoral` → `Peito`; `Braços` → `Bíceps`; `Pernas` → `Quadríceps`; `Teste` → `Outros`.

- [x] **Step 4: Rodar e ver passar**

- [x] **Step 5: Commit**

`feat: padroniza grupos musculares e nome único de exercício`

---

### Task 3: API semanal (trainer + aluno)

**Files:**
- Create: `backend/src/semana.py`
- Modify: `backend/src/schemas.py` (schemas de semana)
- Modify: `backend/src/controllers.py` (`resumo_semana`)
- Modify: `backend/src/routes/alunos.py` e `backend/src/routes/meu_perfil.py`
- Test: `backend/tests/test_semana.py`

**Interfaces:**
- Produces: `semana.inicio_semana(dia: date) -> date`, `semana.volume_planejado(plano) -> dict[str, int]`, `semana.treino_sugerido(plano, hoje, feitas) -> models.Treino | None`.
- Produces: `controllers.resumo_semana(db, aluno_id, ref=None, trainer_id=None, incluir_sugestao=False) -> dict`.
- Produces: `GET /alunos/{aluno_id}/semana?ref=YYYY-MM-DD` → `SemanaPublic`; `GET /alunos/me/semana?ref=` → `SemanaAlunoPublic`.

Response:

```json
{
  "semana_inicio": "2026-10-19",
  "semana_fim": "2026-10-25",
  "treinos": [
    {"treino_id": 1, "treino_nome": "Treino A", "vezes_por_semana": 2,
     "dias_sugeridos": [0, 3], "feitas": 1, "dias_feitos": [0]}
  ],
  "volumes": [
    {"grupo": "Peito", "planejado": 8, "realizado": 6, "media_4_semanas": 5.5}
  ],
  "treino_sugerido_hoje": {"treino_id": 1, "treino_nome": "Treino A", "motivo": "dia_sugerido"}
}
```

Regras:
- `ref` default `consultoria.hoje()`; semana de segunda a domingo.
- Sessões da semana: `realizada=True`, `treino_id` não nulo, `data_hora` em `[inicio 00:00, inicio+7 00:00)`.
- `feitas` = contagem; `dias_feitos` = weekdays únicos ordenados.
- Planejado: plano ativo mais recente; por treino `series × vezes_por_semana`, normalizando o grupo do exercício.
- Realizado: `count(RegistroSerie.id)` por grupo na semana.
- `media_4_semanas`: contagem no intervalo `[inicio-3 semanas, inicio+1 semana)` dividida por 4, arredondada a 1 casa.
- `volumes` = união dos grupos com planejado/realizado/média > 0, na ordem canônica.
- Sugestão: `hoje.weekday() in dias_sugeridos` → `motivo="dia_sugerido"`; senão primeiro treino com `feitas < vezes_por_semana` → `"proximo_pendente"`; senão `None`.
- Trainer: `get_aluno(..., trainer_id=resolve_tenant_filter)` garante 404 para outro tenant.
- Aluno: `current_user.aluno_id`; `dependencies=[Depends(exigir_acesso_treino)]`.

- [x] **Step 1: Escrever testes que falham**

Cobrir:
1. Planejado com `vezes_por_semana=2` e 2 exercícios de 3 séries → 12 séries do grupo.
2. Realizado e aderência: duas sessões do Treino A na semana, uma na semana anterior; `feitas=2`, `dias_feitos` corretos, `media_4_semanas = (2+1)/4 = 0.8` (ajustar conforme séries).
3. Limite de semana: sessão domingo 23:59 conta; segunda seguinte 00:00 não.
4. `treino_sugerido_hoje` por dia e fallback.
5. Isolamento de trainer B → 404; aluno vê o próprio; bloqueado → 403.
6. Semana sem plano ativo → listas vazias, sem erro.

Usar `POST /sessoes/execucao` com `data_hora` explícito (o schema aceita) e `_series` por prescrição.

- [x] **Step 2: Rodar e ver falhar**

- [x] **Step 3: Implementar `semana.py`, schemas, controller e rotas**

Schemas:

```python
class TreinoSemana(BaseModel):
    treino_id: int
    treino_nome: str
    vezes_por_semana: int
    dias_sugeridos: List[int] = []
    feitas: int
    dias_feitos: List[int] = []

class VolumeGrupo(BaseModel):
    grupo: str
    planejado: int
    realizado: int
    media_4_semanas: float

class SemanaPublic(BaseModel):
    semana_inicio: date
    semana_fim: date
    treinos: List[TreinoSemana]
    volumes: List[VolumeGrupo]

class TreinoSugerido(BaseModel):
    treino_id: int
    treino_nome: str
    motivo: Literal["dia_sugerido", "proximo_pendente"]

class SemanaAlunoPublic(SemanaPublic):
    treino_sugerido_hoje: Optional[TreinoSugerido] = None
```

Rotas (adicionar antes de `/{aluno_id}`? não é necessário, o path tem sufixo `/semana`):

```python
@router.get("/{aluno_id}/semana", response_model=schemas.SemanaPublic)
async def semana_do_aluno(
    aluno_id: int,
    ref: date | None = None,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db),
):
    return await controllers.resumo_semana(
        db, aluno_id, ref=ref, trainer_id=resolve_tenant_filter(current_user)
    )
```

`meu_perfil.py`:

```python
@router.get("/alunos/me/semana", response_model=schemas.SemanaAlunoPublic,
            dependencies=[Depends(exigir_acesso_treino)])
async def minha_semana(
    ref: date | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db),
):
    if not current_user.aluno_id:
        raise HTTPException(status_code=403, detail="Usuário não vinculado a um aluno.")
    return await controllers.resumo_semana(
        db, current_user.aluno_id, ref=ref, incluir_sugestao=True
    )
```

- [x] **Step 4: Rodar e ver passar**

- [x] **Step 5: Commit**

`feat: API de planejamento semanal com volume por grupo muscular`

---

### Task 4: Painel — modal do plano e aba Semana

**Files:**
- Create: `frontend/src/constants/grupos.js`
- Create: `frontend/src/features/alunos/SemanaAluno.jsx`
- Modify: `frontend/src/services/api.js` (`alunoService.semana`)
- Modify: `frontend/src/features/treinos/BibliotecaExercicios.jsx` (select de grupo)
- Modify: `frontend/src/features/alunos/ModalPlanoTreino.jsx` (vezes/dias + volume ao vivo)
- Modify: `frontend/src/features/alunos/DetalheAluno.jsx` (aba Semana + campos no editar)

**Interfaces:**
- Produces: `GRUPOS_MUSCULARES` no frontend (mesma ordem do backend).
- Produces: `alunoService.semana(id, ref?)`.
- Produces: `SemanaAluno({ alunoId })` com navegação de semana, tabela de aderência e tabela de volume.
- Produces: modal envia `vezes_por_semana`/`dias_sugeridos` e mostra "Volume semanal planejado".

- [x] **Step 1: Constante + service**

`grupos.js` com a lista canônica. `api.js`:

```js
semana: (id, ref) =>
    apiFetch(`/alunos/${id}/semana${ref ? `?ref=${ref}` : ''}`),
```

- [x] **Step 2: Biblioteca com select**

Substituir o `<input>` de grupo por `<select required>` com `GRUPOS_MUSCULARES`; placeholder "Selecione..."; estado inicial `''`.

- [x] **Step 3: Modal do plano**

- Estado inicial de treino: `{ nome: 'Treino A', vezes_por_semana: 1, dias_sugeridos: [], prescricoes: [] }`; o mesmo em `handleAddTreino`.
- Ao adicionar da biblioteca, guardar `grupo_muscular: ex.grupo_muscular` na prescrição.
- `handleImportTemplate` e `handleEditPlano` (DetalheAluno) copiam os campos novos e `grupo_muscular`.
- Bloco após a identificação do treino:
  - input numérico "Vezes / semana" (1..7);
  - chips `Seg Ter Qua Qui Sex Sáb Dom` (valores 0..6) com toggle;
  - painel "Volume semanal planejado" agregando todos os treinos: `séries × vezes_por_semana`, por grupo; total de séries.
- Não alterar o payload de prescrição além do necessário; `...t` já envia os campos novos.

- [x] **Step 4: `SemanaAluno` + aba no detalhe**

`SemanaAluno`:
- `ref` inicial = hoje local (`YYYY-MM-DD`).
- Botões `‹`, `Hoje`, `›` (semana ±7 dias), título com `dd/mm` a `dd/mm`.
- Cards de resumo: planejado, realizado, aderência (`realizado/planejado`).
- Tabela "Treinos": nome, `feitas/vezes`, dias feitos (Seg..Dom).
- Tabela "Volume por grupo": grupo, planejado, realizado, média 4 semanas.
- Estados de loading/erro/vazio.

`DetalheAluno`:
- `const [aba, setAba] = useState('treinos')`.
- Segmented control "Treinos" / "Semana" no topo da coluna direita.
- `aba === 'semana'` → `<SemanaAluno alunoId={alunoId} />`; senão, o conteúdo atual (planos + evolução + histórico).
- `handleEditPlano` inclui `vezes_por_semana: t.vezes_por_semana ?? 1`, `dias_sugeridos: t.dias_sugeridos ?? []` e `grupo_muscular: p.exercicio?.grupo_muscular`.

- [x] **Step 5: Lint/build**

`cd frontend && npm run lint && npm run build`.

- [x] **Step 6: Commit**

`feat: painel com planejamento semanal e volume por grupo`

---

### Task 5: Portal — card "Hoje" e progresso semanal

**Files:**
- Create: `src/hooks/useSemana.js`
- Modify: `src/pages/Dashboard.jsx`
- Modify: `src/pages/Treinos.jsx` (preseleção por `?treino=`)
- Test: `src/pages/Treinos.test.jsx` se necessário (não quebrar os existentes)

**Interfaces:**
- Produces: `useSemana() -> { semana, loadingSemana, buscarSemana }` chamando `GET /alunos/me/semana`.
- Produces: Dashboard usa `semana.treino_sugerido_hoje` e `semana.treinos`.
- Produces: `Treinos` lê `useSearchParams().get('treino')` e seleciona o índice.

- [x] **Step 1: Hook**

```js
import { useCallback, useState } from 'react';
import api from '../services/api';

export function useSemana() {
  const [semana, setSemana] = useState(null);
  const [loadingSemana, setLoadingSemana] = useState(false);

  const buscarSemana = useCallback(async () => {
    setLoadingSemana(true);
    try {
      const { data } = await api.get('/alunos/me/semana');
      setSemana(data);
    } catch {
      setSemana(null); // fallback silencioso
    } finally {
      setLoadingSemana(false);
    }
  }, []);

  return { semana, loadingSemana, buscarSemana };
}
```

- [x] **Step 2: Dashboard**

- Chamar `buscarSemana()` no `useEffect` inicial.
- Badge: `sessaoHoje` → "Presença Confirmada"; senão `treinoSugerido` → "Treino de Hoje"; senão "Sem Plano".
- Título: `treinoSugerido?.treino_nome ?? planoAtivo?.titulo ?? 'Nenhum plano ativo'`.
- CTA: `sessaoHoje` → "Ver Treino de Hoje"; senão `treinoSugerido` → "Começar Treino"; senão "Fazer Check-in".
- Links: treino → `/treinos?treino=${id}`; check-in → `/checkin`.
- Abaixo de "Esta Semana", linha de progresso por treino: `A 1/2 · B 0/1`, verde quando `feitas >= vezes_por_semana`; se `semana` nulo, não renderiza.

- [x] **Step 3: Treinos com query param**

```js
import { useSearchParams } from 'react-router-dom';
const [searchParams] = useSearchParams();

useEffect(() => {
  const id = Number(searchParams.get('treino'));
  if (!id || !planoAtivo?.treinos) return;
  const idx = planoAtivo.treinos.findIndex(t => t.id === id);
  if (idx >= 0) setSelectedIdx(idx);
}, [searchParams, planoAtivo]);
```

- [x] **Step 4: Testes/build**

`npm test` e `npm run build`.

- [x] **Step 5: Commit**

`feat: portal com treino sugerido e progresso semanal`

---

### Task 6: Verificação final

- [x] Rodar a suíte completa do backend.
- [x] Rodar lint/build do painel.
- [x] Rodar testes/build do portal.
- [x] Revisar `git diff` (sem arquivos temporários, sem `__pycache__`).
- [x] Commits separados por task, com o trailer combinado.
