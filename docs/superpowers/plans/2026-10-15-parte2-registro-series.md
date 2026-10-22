# Parte 2 — Registro por série + histórico: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O aluno (portal) e o trainer (painel) registram reps e carga de cada série; o histórico fica preso ao exercício, não ao plano, e alimenta pré-preenchimento, evolução semanal e um feed de atividade recente com polling de 30 s.

**Architecture:** Nova tabela `registros_serie` (filha de `sessoes_treino`, chave de histórico = `exercicio_id`) e duas colunas em `sessoes_treino` (`treino_id`, `registrado_por`). Um endpoint transacional `POST /sessoes/execucao` cria sessão + séries. Três leituras derivam do histórico: `ultima-execucao` (pré-preenchimento), `evolucao` (semana a semana) e `/atividade-recente` (feed do trainer). O painel ganha modal de registro com grade de séries, seção Evolução no detalhe do aluno e feed na lista de alunos. O portal troca o campo "Minha Carga" por reps/kg em cada série, com rascunho em `localStorage`. Por último, `PATCH /prescricoes/{id}/carga` sai.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, pytest + httpx (SQLite em memória); React 19 + Vite + Tailwind + recharts (painel); React + axios + react-router (portal).

**Spec:** `docs/superpowers/specs/2026-10-15-acompanhamento-semanal-design.md` (seção "Parte 2 — Registro por série + histórico")

## Global Constraints

- Rodar testes do backend: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q` (`uv` não está no PATH).
- Testes usam SQLite sem `PRAGMA foreign_keys`: `ON DELETE` não roda nos testes. Nada de SQL específico de PostgreSQL; agrupamento por semana é feito em Python.
- `backend/src/models.py` é CRLF. Editar preservando CRLF (`open(..., newline='')` em script, ou Edit tool).
- Colunas `DateTime` são naive. Toda data/hora nova é gravada no horário de Brasília (`consultoria.FUSO_BRASILIA`, UTC-3 fixo).
- Semana = segunda a domingo (`dia - timedelta(days=dia.weekday())`).
- `registrado_por`: `"aluno"` ou `"trainer"` (admin conta como trainer). Sessões antigas ficam com nulo.
- Débito de saldo: só quando o trainer registra, aluno presencial de pacote, saldo > 0 (regra atual, reaproveitada).
- Aluno edita/exclui só sessões dele com `registrado_por == "aluno"`. Trainer edita/exclui qualquer sessão dos seus alunos.
- `POST /sessoes/execucao` do aluno está sujeito à trava da Parte 1 (router `/sessoes` já tem `exigir_acesso_treino`).
- Feed: polling de 30 s apenas com `document.visibilityState === 'visible'`.
- Rascunho do portal: chave `ptroster_rascunho_{alunoId}_{treinoId}`, todo acesso a `localStorage` dentro de try/catch.
- Fora do escopo: RPE/RIR, observação por série, recordes pessoais, push/WebSocket, UI de edição de séries (a API `PUT` existe; tela fica para depois).
- Comentários e textos de UI em português, no estilo do código vizinho.
- Commits terminam com:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01ELN8nBWxTs2MvAF6GrjLq1
  ```

## Review Focus

1. **Aluno apagando ou editando sessão registrada pelo trainer** (que debitou saldo) tem de receber 404, não sucesso (Task 3 testa).
2. **Excluir aluno com séries registradas** não pode dar 500: `SessaoTreino.series` usa `passive_deletes=True` e o banco faz o cascade (Task 2 testa).
3. **Execução sem `data_hora`** com servidor em UTC: precisa gravar o horário de Brasília, senão treino das 22h cai no dia seguinte (Task 2 testa).
4. **Troca de plano**: o pré-preenchimento casa por `exercicio_id`, não por `treino_id`; um plano novo com o mesmo exercício já vem preenchido (Task 4 testa).
5. **Série de peso corporal (`carga_kg` nulo)**: `carga_max` nulo, volume 0 e delta nulo, sem erro de soma com `None` (Tasks 5 e 6 testam).

---

### Task 1: Tabela `registros_serie` e colunas novas em `sessoes_treino`

**Files:**
- Create: `backend/alembic/versions/c2d3e4f5a6b7_add_registros_serie.py`
- Modify: `backend/src/models.py` (`SessaoTreino`, nova classe `RegistroSerie`, import de `Index`)
- Modify: `backend/src/schemas.py` (schemas de série, execução, evolução, atividade; `SessaoTreinoPublic`)
- Modify: `backend/src/consultoria.py` (função `agora()`)
- Test: `backend/tests/test_execucao.py` (novo)

**Interfaces:**
- Produces: `models.RegistroSerie(id, sessao_id, exercicio_id, prescricao_id, numero_serie, repeticoes, carga_kg, sessao, exercicio)`; `SessaoTreino.treino_id`, `SessaoTreino.registrado_por`, `SessaoTreino.treino`, `SessaoTreino.series`; `consultoria.agora() -> datetime` (naive, Brasília); schemas `SerieIn`, `SeriePublic`, `ExecucaoCreate`, `SeriesUpdate`, `SessaoExecucaoPublic`, `SerieResumo`, `UltimaExecucaoExercicio`, `ExercicioRegistrado`, `SemanaEvolucao`, `EvolucaoPublic`, `ExercicioAtividade`, `AtividadeRecente`.

- [x] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_execucao.py` (`tests/` não é pacote, então os helpers ficam no próprio arquivo):

```python
from datetime import timedelta

import pytest
from httpx import AsyncClient

from src import consultoria, models

# Mesmos ids das constantes do conftest (tests/ não é pacote, então não dá para importar de lá)
TRAINER_A = models.Usuario(id=1, username="trainer_a", role="trainer")
TRAINER_B = models.Usuario(id=2, username="trainer_b", role="trainer")


def _aluno_logado(aluno_id: int) -> models.Usuario:
    return models.Usuario(id=500 + aluno_id, username=f"aluno_{aluno_id}", role="aluno", aluno_id=aluno_id)


async def _criar_exercicio(ac: AsyncClient, nome: str = "Supino reto") -> int:
    res = await ac.post("/exercicios/", json={"nome": nome, "grupo_muscular": "Peito"})
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _criar_aluno(ac: AsyncClient, **extras) -> int:
    res = await ac.post("/alunos/", json={"nome": "Aluno Teste", **extras})
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _criar_plano(ac: AsyncClient, aluno_id: int, exercicio_ids: list[int]) -> dict:
    payload = {
        "titulo": "Plano",
        "treinos": [{
            "nome": "Treino A",
            "prescricoes": [
                {"exercicio_id": e, "series": 3, "repeticoes": "10-12", "carga": "40"} for e in exercicio_ids
            ],
        }],
    }
    res = await ac.post(f"/alunos/{aluno_id}/planos", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def _series(prescricao: dict, cargas: list[float | None], reps: int = 10) -> list[dict]:
    return [
        {"exercicio_id": prescricao["exercicio_id"], "prescricao_id": prescricao["id"],
         "numero_serie": i + 1, "repeticoes": reps, "carga_kg": c}
        for i, c in enumerate(cargas)
    ]


async def _cenario(ac: AsyncClient, **extras_aluno) -> tuple[int, dict]:
    """Aluno do trainer A com um plano de um exercício. Devolve (aluno_id, treino)."""
    ex = await _criar_exercicio(ac)
    aluno_id = await _criar_aluno(ac, **extras_aluno)
    plano = await _criar_plano(ac, aluno_id, [ex])
    return aluno_id, plano["treinos"][0]


@pytest.mark.anyio
async def test_agora_usa_horario_de_brasilia():
    from datetime import datetime, timezone
    utc = datetime(2026, 10, 16, 1, 30, tzinfo=timezone.utc)  # 22h30 do dia 15 em Brasília
    assert consultoria.agora(utc) == datetime(2026, 10, 15, 22, 30)
```

- [x] **Step 2: Rodar e ver falhar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_execucao.py -q`
Expected: FAIL com `AttributeError: module 'src.consultoria' has no attribute 'agora'`

- [x] **Step 3: Implementar `agora`, models, migração e schemas**

Em `backend/src/consultoria.py`, logo depois de `def hoje(...)`:

```python
def agora(instante: datetime | None = None) -> datetime:
    """Data e hora de Brasília sem fuso: as colunas DateTime do banco são naive."""
    return (instante or datetime.now(timezone.utc)).astimezone(FUSO_BRASILIA).replace(tzinfo=None)
```

Em `backend/src/models.py` (CRLF): trocar a primeira linha por

```python
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Text, Float, ForeignKey, Index
```

Em `SessaoTreino`, depois de `tipo_atividade`:

```python
    treino_id = Column(Integer, ForeignKey('treinos.id', ondelete='SET NULL'), nullable=True)
    registrado_por = Column(String, nullable=True)  # "aluno" ou "trainer"; nulo em sessões antigas
```

e depois de `plano_treino = relationship(...)`:

```python
    treino = relationship("Treino")
    # passive_deletes: o banco apaga as séries (ON DELETE CASCADE) sem o ORM carregá-las
    series = relationship(
        "RegistroSerie", back_populates="sessao", cascade="all, delete-orphan",
        passive_deletes=True, order_by="RegistroSerie.id"
    )
```

No fim do arquivo:

```python


class RegistroSerie(Base):
    """Uma série executada. O histórico é por exercício e sobrevive à troca ou exclusão do plano."""
    __tablename__ = 'registros_serie'
    __table_args__ = (Index('ix_registros_serie_exercicio_sessao', 'exercicio_id', 'sessao_id'),)

    id = Column(Integer, primary_key=True)
    sessao_id = Column(Integer, ForeignKey('sessoes_treino.id', ondelete='CASCADE'), nullable=False, index=True)
    exercicio_id = Column(Integer, ForeignKey('exercicios.id'), nullable=False)
    prescricao_id = Column(Integer, ForeignKey('prescricoes.id', ondelete='SET NULL'), nullable=True)
    numero_serie = Column(Integer, nullable=False)
    repeticoes = Column(Integer, nullable=False)
    carga_kg = Column(Float, nullable=True)  # nulo = peso corporal

    sessao = relationship("SessaoTreino", back_populates="series")
    exercicio = relationship("Exercicio")
```

Criar `backend/alembic/versions/c2d3e4f5a6b7_add_registros_serie.py`:

```python
"""add registros_serie, treino_id e registrado_por em sessoes_treino

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessoes_treino', sa.Column('treino_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_sessoes_treino_treino_id', 'sessoes_treino', 'treinos', ['treino_id'], ['id'], ondelete='SET NULL'
    )
    op.add_column('sessoes_treino', sa.Column('registrado_por', sa.String(), nullable=True))
    op.create_table(
        'registros_serie',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sessao_id', sa.Integer(), sa.ForeignKey('sessoes_treino.id', ondelete='CASCADE'), nullable=False),
        sa.Column('exercicio_id', sa.Integer(), sa.ForeignKey('exercicios.id'), nullable=False),
        sa.Column('prescricao_id', sa.Integer(), sa.ForeignKey('prescricoes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('numero_serie', sa.Integer(), nullable=False),
        sa.Column('repeticoes', sa.Integer(), nullable=False),
        sa.Column('carga_kg', sa.Float(), nullable=True),
    )
    op.create_index('ix_registros_serie_sessao_id', 'registros_serie', ['sessao_id'])
    op.create_index('ix_registros_serie_exercicio_sessao', 'registros_serie', ['exercicio_id', 'sessao_id'])


def downgrade() -> None:
    op.drop_index('ix_registros_serie_exercicio_sessao', table_name='registros_serie')
    op.drop_index('ix_registros_serie_sessao_id', table_name='registros_serie')
    op.drop_table('registros_serie')
    op.drop_column('sessoes_treino', 'registrado_por')
    op.drop_constraint('fk_sessoes_treino_treino_id', 'sessoes_treino', type_='foreignkey')
    op.drop_column('sessoes_treino', 'treino_id')
```

Em `backend/src/schemas.py`, em `SessaoTreinoPublic` acrescentar:

```python
    treino_id: Optional[int] = None
    registrado_por: Optional[str] = None
```

e logo depois de `FrequenciaMensalPublic`:

```python
# --- SCHEMAS DE EXECUÇÃO (registro por série) ---
class SerieIn(BaseModel):
    exercicio_id: int
    prescricao_id: Optional[int] = None
    numero_serie: int = Field(ge=1)
    repeticoes: int = Field(ge=0)
    carga_kg: Optional[float] = Field(default=None, ge=0)  # nulo = peso corporal

class SeriePublic(SerieIn):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ExecucaoCreate(BaseModel):
    treino_id: int
    aluno_id: Optional[int] = None  # obrigatório quando o trainer registra; ignorado para o aluno
    data_hora: Optional[datetime] = None
    observacoes_performance: Optional[str] = None
    series: List[SerieIn] = Field(min_length=1)

class SeriesUpdate(BaseModel):
    series: List[SerieIn] = Field(min_length=1)

class SessaoExecucaoPublic(BaseModel):
    id: int
    aluno_id: int
    treino_id: Optional[int] = None
    plano_treino_id: Optional[int] = None
    data_hora: datetime
    registrado_por: Optional[str] = None
    observacoes_performance: Optional[str] = None
    aviso: Optional[str] = None
    series: List[SeriePublic]
    model_config = ConfigDict(from_attributes=True)

class SerieResumo(BaseModel):
    numero_serie: int
    repeticoes: int
    carga_kg: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class UltimaExecucaoExercicio(BaseModel):
    exercicio_id: int
    sessao_id: int
    data_hora: datetime
    series: List[SerieResumo]

class ExercicioRegistrado(BaseModel):
    id: int
    nome: str

class SemanaEvolucao(BaseModel):
    semana_inicio: date  # segunda-feira
    series: List[SerieResumo]
    carga_max: Optional[float] = None
    volume_carga: float  # Σ reps × kg

class EvolucaoPublic(BaseModel):
    exercicios: List[ExercicioRegistrado]
    semanas: List[SemanaEvolucao]

class ExercicioAtividade(BaseModel):
    exercicio_id: int
    nome: str
    carga_max: Optional[float] = None
    delta_kg: Optional[float] = None  # vs. a sessão anterior do mesmo aluno no mesmo exercício

class AtividadeRecente(BaseModel):
    sessao_id: int
    aluno_id: int
    aluno_nome: str
    treino_nome: Optional[str] = None
    data_hora: datetime
    registrado_por: Optional[str] = None
    exercicios: List[ExercicioAtividade]
```

- [x] **Step 4: Rodar e ver passar (arquivo novo + suíte inteira)**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS, 43 passed (42 antigos + 1 novo)

- [x] **Step 5: Conferir CRLF e commitar**

Run: `cd backend && git diff --stat src/models.py` — Expected: só as linhas novas (~20), não o arquivo inteiro.

```bash
git add backend/alembic/versions/c2d3e4f5a6b7_add_registros_serie.py backend/src/models.py backend/src/schemas.py backend/src/consultoria.py backend/tests/test_execucao.py
git commit -m "feat: tabela registros_serie e vínculo da sessão com o treino"
```

---

### Task 2: `POST /sessoes/execucao` (sessão + séries numa transação)

**Files:**
- Modify: `backend/src/controllers.py` (helpers `_hora_brasilia`, `_debitar_aula`, `_aluno_do_tenant`, `_validar_series`, `_carregar_execucao`; `registrar_execucao`; `registrar_sessao` passa a usar `_debitar_aula` e gravar `registrado_por`)
- Modify: `backend/src/routes/sessoes.py` (rota `POST /execucao`)
- Test: `backend/tests/test_execucao.py`

**Interfaces:**
- Consumes: Task 1 (models e schemas).
- Produces: `controllers.registrar_execucao(db, payload: schemas.ExecucaoCreate, aluno_id: int, registrado_por: str, trainer_id: int | None = None) -> models.SessaoTreino`; `controllers._aluno_do_tenant(db, aluno_id, trainer_id) -> models.Aluno`; `controllers._validar_series(db, series, treino_id: int | None) -> None`; `controllers._carregar_execucao(db, sessao_id) -> models.SessaoTreino` (com `series` carregadas).

- [x] **Step 1: Escrever os testes que falham**

Acrescentar a `backend/tests/test_execucao.py`:

```python
@pytest.mark.anyio
async def test_aluno_registra_execucao_com_series(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    presc = treino["prescricoes"][0]
    como_usuario(_aluno_logado(aluno_id))

    res = await ac.post("/sessoes/execucao", json={"treino_id": treino["id"], "series": _series(presc, [40, 40, 42.5])})

    assert res.status_code == 201, res.text
    sessao = res.json()
    assert sessao["registrado_por"] == "aluno"
    assert sessao["treino_id"] == treino["id"]
    assert sessao["aluno_id"] == aluno_id
    assert [s["carga_kg"] for s in sessao["series"]] == [40, 40, 42.5]


@pytest.mark.anyio
async def test_execucao_sem_data_grava_horario_de_brasilia(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    como_usuario(_aluno_logado(aluno_id))
    res = await ac.post("/sessoes/execucao", json={"treino_id": treino["id"], "series": _series(treino["prescricoes"][0], [40])})
    assert res.status_code == 201, res.text
    assert res.json()["data_hora"][:10] == consultoria.hoje().isoformat()


@pytest.mark.anyio
async def test_debito_so_quando_trainer_registra_aluno_de_pacote(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac, tipo_pagamento="pacote", saldo_aulas=5)
    series = _series(treino["prescricoes"][0], [40])

    res = await ac.post("/sessoes/execucao", json={"aluno_id": aluno_id, "treino_id": treino["id"], "series": series})
    assert res.status_code == 201, res.text
    assert res.json()["registrado_por"] == "trainer"

    como_usuario(_aluno_logado(aluno_id))
    assert (await ac.post("/sessoes/execucao", json={"treino_id": treino["id"], "series": series})).status_code == 201

    como_usuario(TRAINER_A)
    assert (await ac.get(f"/alunos/{aluno_id}")).json()["saldo_aulas"] == 4


@pytest.mark.anyio
async def test_trainer_precisa_informar_aluno(ac: AsyncClient):
    _, treino = await _cenario(ac)
    res = await ac.post("/sessoes/execucao", json={"treino_id": treino["id"], "series": _series(treino["prescricoes"][0], [40])})
    assert res.status_code == 422


@pytest.mark.anyio
async def test_serie_invalida_nao_grava_nada(ac: AsyncClient):
    aluno_id, treino = await _cenario(ac)
    series = _series(treino["prescricoes"][0], [40]) + [
        {"exercicio_id": 9999, "numero_serie": 1, "repeticoes": 10, "carga_kg": 10}
    ]
    res = await ac.post("/sessoes/execucao", json={"aluno_id": aluno_id, "treino_id": treino["id"], "series": series})
    assert res.status_code == 409
    assert (await ac.get("/sessoes/", params={"aluno_id": aluno_id})).json() == []


@pytest.mark.anyio
async def test_treino_de_outro_aluno_e_rejeitado(ac: AsyncClient, como_usuario):
    _, treino_do_outro = await _cenario(ac)
    aluno_id = await _criar_aluno(ac)
    como_usuario(_aluno_logado(aluno_id))
    res = await ac.post("/sessoes/execucao", json={
        "treino_id": treino_do_outro["id"], "series": _series(treino_do_outro["prescricoes"][0], [40]),
    })
    assert res.status_code == 409


@pytest.mark.anyio
async def test_trainer_de_outro_tenant_nao_registra(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    como_usuario(TRAINER_B)
    res = await ac.post("/sessoes/execucao", json={
        "aluno_id": aluno_id, "treino_id": treino["id"], "series": _series(treino["prescricoes"][0], [40]),
    })
    assert res.status_code == 404


@pytest.mark.anyio
async def test_trava_de_consultoria_bloqueia_execucao_do_aluno(ac: AsyncClient, como_usuario):
    vencido = (consultoria.hoje() - timedelta(days=1)).isoformat()
    aluno_id, treino = await _cenario(
        ac, modalidade="consultoria", data_vencimento_consultoria=vencido, bloquear_apos_vencimento=True
    )
    como_usuario(_aluno_logado(aluno_id))
    res = await ac.post("/sessoes/execucao", json={"treino_id": treino["id"], "series": _series(treino["prescricoes"][0], [40])})
    assert res.status_code == 403
    assert res.json()["message"] == "consultoria_vencida"


@pytest.mark.anyio
async def test_excluir_aluno_com_series_registradas(ac: AsyncClient):
    aluno_id, treino = await _cenario(ac)
    await ac.post("/sessoes/execucao", json={"aluno_id": aluno_id, "treino_id": treino["id"], "series": _series(treino["prescricoes"][0], [40])})
    assert (await ac.delete(f"/alunos/{aluno_id}")).status_code == 204
```

- [x] **Step 2: Rodar e ver falhar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_execucao.py -q`
Expected: FAIL nos testes novos com 404/405 em `POST /sessoes/execucao` (rota inexistente). `test_excluir_aluno_com_series_registradas` pode passar já, porque o `POST` falha antes de gravar; ele fica valendo depois do Step 3.

- [x] **Step 3: Implementar**

Em `backend/src/controllers.py`, substituir o bloco de débito de `registrar_sessao` e gravar `registrado_por`. O trecho atual:

```python
    aviso = None
    if (registrado_por_staff and aula_contabilizada
            and aluno.modalidade == "presencial" and aluno.tipo_pagamento == "pacote"):
        # UPDATE condicional: atômico sob concorrência e nunca deixa o saldo negativo
        res_debito = await db.execute(
            update(models.Aluno)
            .where(models.Aluno.id == aluno.id, models.Aluno.saldo_aulas > 0)
            .values(saldo_aulas=models.Aluno.saldo_aulas - 1)
        )
        if res_debito.rowcount == 0:
            aviso = "Aluno de pacote sem saldo de aulas: sessão registrada sem débito."
```

vira:

```python
    sessao.registrado_por = "trainer" if registrado_por_staff else "aluno"
    aviso = await _debitar_aula(db, aluno) if registrado_por_staff and aula_contabilizada else None
```

Logo depois de `registrar_sessao` (antes de `listar_sessoes`), acrescentar:

```python
async def _debitar_aula(db: AsyncSession, aluno: models.Aluno) -> str | None:
    """Debita uma aula de aluno presencial de pacote. Devolve aviso quando não havia saldo."""
    if aluno.modalidade != "presencial" or aluno.tipo_pagamento != "pacote":
        return None
    # UPDATE condicional: atômico sob concorrência e nunca deixa o saldo negativo
    res_debito = await db.execute(
        update(models.Aluno)
        .where(models.Aluno.id == aluno.id, models.Aluno.saldo_aulas > 0)
        .values(saldo_aulas=models.Aluno.saldo_aulas - 1)
    )
    if res_debito.rowcount == 0:
        return "Aluno de pacote sem saldo de aulas: sessão registrada sem débito."
    return None


# --- EXECUÇÃO DE TREINO (registro por série) ---

def _hora_brasilia(dt: datetime | None) -> datetime:
    """Colunas DateTime são naive: grava sempre no horário de Brasília."""
    if dt is None:
        return consultoria.agora()
    return consultoria.agora(dt) if dt.tzinfo else dt


async def _aluno_do_tenant(db: AsyncSession, aluno_id: int, trainer_id: int | None) -> models.Aluno:
    stmt = select(models.Aluno).where(models.Aluno.id == aluno_id)
    if trainer_id is not None:
        stmt = stmt.where(models.Aluno.trainer_id == trainer_id)
    aluno = await db.scalar(stmt)
    if not aluno:
        raise exceptions.ResourceNotFoundError(f"Aluno {aluno_id} não encontrado")
    return aluno


async def _validar_series(db: AsyncSession, series: list[schemas.SerieIn], treino_id: int | None) -> None:
    ids_exercicio = {s.exercicio_id for s in series}
    existentes = set((await db.scalars(
        select(models.Exercicio.id).where(models.Exercicio.id.in_(ids_exercicio))
    )).all())
    if existentes != ids_exercicio:
        raise exceptions.BusinessRuleError("Exercício inexistente na série informada.")

    ids_prescricao = {s.prescricao_id for s in series if s.prescricao_id is not None}
    if ids_prescricao:
        stmt = select(models.Prescricao.id).where(models.Prescricao.id.in_(ids_prescricao))
        if treino_id is not None:
            stmt = stmt.where(models.Prescricao.treino_id == treino_id)
        if set((await db.scalars(stmt)).all()) != ids_prescricao:
            raise exceptions.BusinessRuleError("Prescrição não pertence a este treino.")


async def _carregar_execucao(db: AsyncSession, sessao_id: int) -> models.SessaoTreino:
    return await db.scalar(
        select(models.SessaoTreino)
        .options(selectinload(models.SessaoTreino.series))
        .where(models.SessaoTreino.id == sessao_id)
        .execution_options(populate_existing=True)
    )


async def registrar_execucao(
    db: AsyncSession,
    payload: schemas.ExecucaoCreate,
    aluno_id: int,
    registrado_por: str,
    trainer_id: int | None = None,
) -> models.SessaoTreino:
    aluno = await _aluno_do_tenant(db, aluno_id, trainer_id)
    treino = await db.scalar(
        select(models.Treino)
        .join(models.PlanoTreino, models.Treino.plano_id == models.PlanoTreino.id)
        .where(models.Treino.id == payload.treino_id, models.PlanoTreino.aluno_id == aluno.id)
    )
    if not treino:
        raise exceptions.BusinessRuleError("Treino inválido para este aluno.")
    # Valida tudo antes de gravar: série inválida não deixa sessão pela metade
    await _validar_series(db, payload.series, treino.id)

    sessao = models.SessaoTreino(
        aluno_id=aluno.id,
        plano_treino_id=treino.plano_id,
        treino_id=treino.id,
        data_hora=_hora_brasilia(payload.data_hora),
        realizada=True,
        observacoes_performance=payload.observacoes_performance,
        registrado_por=registrado_por,
        series=[models.RegistroSerie(**s.model_dump()) for s in payload.series],
    )
    # Regra atual: só o registro feito pelo trainer debita saldo
    aviso = await _debitar_aula(db, aluno) if registrado_por == "trainer" else None
    db.add(sessao)
    await db.commit()

    sessao = await _carregar_execucao(db, sessao.id)
    sessao.aviso = aviso
    return sessao
```

Em `backend/src/routes/sessoes.py`, antes de `@router.get("/", ...)`:

```python
@router.post("/execucao", response_model=schemas.SessaoExecucaoPublic, status_code=201)
async def registrar_execucao(
    payload: schemas.ExecucaoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role in ("trainer", "admin"):
        if payload.aluno_id is None:
            raise HTTPException(status_code=422, detail="Informe o aluno.")
        return await controllers.registrar_execucao(
            db, payload, aluno_id=payload.aluno_id, registrado_por="trainer",
            trainer_id=resolve_tenant_filter(current_user),
        )
    if not current_user.aluno_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não vinculado a um aluno.")
    # aluno_id do payload é ignorado: o aluno só registra para si mesmo
    return await controllers.registrar_execucao(db, payload, aluno_id=current_user.aluno_id, registrado_por="aluno")
```

- [x] **Step 4: Rodar e ver passar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS, 52 passed

- [x] **Step 5: Commit**

```bash
git add backend/src/controllers.py backend/src/routes/sessoes.py backend/tests/test_execucao.py
git commit -m "feat: registro de execução com séries numa transação"
```

---

### Task 3: Editar séries e excluir sessão (trainer e aluno)

**Files:**
- Modify: `backend/src/controllers.py` (`_escopo_sessao`, `get_sessao`, `deletar_sessao`, nova `substituir_series`)
- Modify: `backend/src/routes/sessoes.py` (`_escopo`, `PUT /{sessao_id}/series`, `DELETE /{sessao_id}` aberto ao aluno)
- Test: `backend/tests/test_execucao.py`

**Interfaces:**
- Consumes: `_validar_series`, `_carregar_execucao` (Task 2).
- Produces: `controllers.substituir_series(db, sessao_id, series, trainer_id=None, aluno_id=None) -> models.SessaoTreino`; `controllers.get_sessao(db, sessao_id, trainer_id=None, aluno_id=None)`; `controllers.deletar_sessao(db, sessao_id, trainer_id=None, aluno_id=None)`.

- [x] **Step 1: Escrever os testes que falham**

```python
async def _execucao(ac: AsyncClient, treino: dict, cargas: list[float | None], **extras) -> dict:
    res = await ac.post("/sessoes/execucao", json={
        "treino_id": treino["id"], "series": _series(treino["prescricoes"][0], cargas), **extras,
    })
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.anyio
async def test_aluno_edita_series_da_propria_sessao(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    como_usuario(_aluno_logado(aluno_id))
    sessao = await _execucao(ac, treino, [40, 40])

    res = await ac.put(f"/sessoes/{sessao['id']}/series", json={"series": _series(treino["prescricoes"][0], [45])})

    assert res.status_code == 200, res.text
    assert [s["carga_kg"] for s in res.json()["series"]] == [45]


@pytest.mark.anyio
async def test_aluno_nao_edita_nem_exclui_sessao_de_outro_aluno(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    outro_id = await _criar_aluno(ac)
    como_usuario(_aluno_logado(aluno_id))
    sessao = await _execucao(ac, treino, [40])

    como_usuario(_aluno_logado(outro_id))
    assert (await ac.put(f"/sessoes/{sessao['id']}/series", json={"series": _series(treino["prescricoes"][0], [1])})).status_code == 404
    assert (await ac.delete(f"/sessoes/{sessao['id']}")).status_code == 404


@pytest.mark.anyio
async def test_aluno_nao_mexe_em_sessao_registrada_pelo_trainer(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    sessao = await _execucao(ac, treino, [40], aluno_id=aluno_id)  # trainer registrou

    como_usuario(_aluno_logado(aluno_id))
    assert (await ac.put(f"/sessoes/{sessao['id']}/series", json={"series": _series(treino["prescricoes"][0], [1])})).status_code == 404
    assert (await ac.delete(f"/sessoes/{sessao['id']}")).status_code == 404


@pytest.mark.anyio
async def test_aluno_exclui_propria_sessao_e_trainer_edita_qualquer(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    como_usuario(_aluno_logado(aluno_id))
    s1 = await _execucao(ac, treino, [40])
    s2 = await _execucao(ac, treino, [40])
    assert (await ac.delete(f"/sessoes/{s1['id']}")).status_code == 204

    como_usuario(TRAINER_A)
    res = await ac.put(f"/sessoes/{s2['id']}/series", json={"series": _series(treino["prescricoes"][0], [50])})
    assert res.status_code == 200, res.text

    como_usuario(TRAINER_B)
    assert (await ac.put(f"/sessoes/{s2['id']}/series", json={"series": _series(treino["prescricoes"][0], [1])})).status_code == 404
```

- [x] **Step 2: Rodar e ver falhar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_execucao.py -q`
Expected: FAIL com 405 no `PUT` e 403 no `DELETE` do aluno (rota restrita a trainer).

- [x] **Step 3: Implementar**

Em `backend/src/controllers.py`, substituir `get_sessao` e `deletar_sessao` por:

```python
def _escopo_sessao(stmt, trainer_id: int | None, aluno_id: int | None):
    """Trainer: sessões dos seus alunos. Aluno: só as que ele mesmo registrou."""
    if trainer_id is not None:
        stmt = stmt.join(models.Aluno, models.SessaoTreino.aluno_id == models.Aluno.id).where(
            models.Aluno.trainer_id == trainer_id
        )
    if aluno_id is not None:
        stmt = stmt.where(models.SessaoTreino.aluno_id == aluno_id, models.SessaoTreino.registrado_por == "aluno")
    return stmt


async def get_sessao(
    db: AsyncSession, sessao_id: int, trainer_id: int | None = None, aluno_id: int | None = None
) -> models.SessaoTreino:
    stmt = select(models.SessaoTreino).where(models.SessaoTreino.id == sessao_id)
    sessao = await db.scalar(_escopo_sessao(stmt, trainer_id, aluno_id))
    if not sessao:
        raise exceptions.ResourceNotFoundError(f"Sessão {sessao_id} não encontrada")
    return sessao

async def deletar_sessao(
    db: AsyncSession, sessao_id: int, trainer_id: int | None = None, aluno_id: int | None = None
) -> None:
    sessao = await get_sessao(db, sessao_id, trainer_id, aluno_id)
    await db.delete(sessao)
    await db.commit()


async def substituir_series(
    db: AsyncSession,
    sessao_id: int,
    series: list[schemas.SerieIn],
    trainer_id: int | None = None,
    aluno_id: int | None = None,
) -> models.SessaoTreino:
    stmt = (
        select(models.SessaoTreino)
        .options(selectinload(models.SessaoTreino.series))
        .where(models.SessaoTreino.id == sessao_id)
    )
    sessao = await db.scalar(_escopo_sessao(stmt, trainer_id, aluno_id))
    if not sessao:
        raise exceptions.ResourceNotFoundError(f"Sessão {sessao_id} não encontrada")
    await _validar_series(db, series, sessao.treino_id)

    sessao.series = [models.RegistroSerie(**s.model_dump()) for s in series]  # delete-orphan apaga as antigas
    await db.commit()
    return await _carregar_execucao(db, sessao.id)
```

Em `backend/src/routes/sessoes.py`, depois de `_validar_acesso_aluno`:

```python
def _escopo(current_user: Usuario) -> dict:
    """Filtro de dono para editar/excluir sessão: trainer pelo tenant, aluno pelo próprio id."""
    if current_user.role in ("trainer", "admin"):
        return {"trainer_id": resolve_tenant_filter(current_user)}
    if not current_user.aluno_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não vinculado a um aluno.")
    return {"aluno_id": current_user.aluno_id}
```

Substituir a rota `DELETE /{sessao_id}` por:

```python
@router.put("/{sessao_id}/series", response_model=schemas.SessaoExecucaoPublic)
async def substituir_series(
    sessao_id: int,
    payload: schemas.SeriesUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.substituir_series(db, sessao_id, payload.series, **_escopo(current_user))


@router.delete("/{sessao_id}", status_code=204)
async def deletar_sessao(
    sessao_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await controllers.deletar_sessao(db, sessao_id, **_escopo(current_user))
    return Response(status_code=204)
```

- [x] **Step 4: Rodar e ver passar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS, 56 passed

- [x] **Step 5: Commit**

```bash
git add backend/src/controllers.py backend/src/routes/sessoes.py backend/tests/test_execucao.py
git commit -m "feat: editar séries e excluir sessão com escopo de trainer e aluno"
```

---

### Task 4: `GET .../ultima-execucao` (pré-preenchimento)

**Files:**
- Modify: `backend/src/controllers.py` (`ultima_execucao`)
- Modify: `backend/src/routes/alunos.py` (trainer)
- Modify: `backend/src/routes/meu_perfil.py` (aluno, com trava)
- Test: `backend/tests/test_execucao.py`

**Interfaces:**
- Consumes: `_aluno_do_tenant` (Task 2).
- Produces: `controllers.ultima_execucao(db, aluno_id, treino_id, trainer_id=None) -> list[dict]` com chaves `exercicio_id, sessao_id, data_hora, series` (lista de `RegistroSerie`). Rotas `GET /alunos/{aluno_id}/ultima-execucao?treino_id=` e `GET /alunos/me/ultima-execucao?treino_id=`.

- [x] **Step 1: Escrever os testes que falham**

```python
@pytest.mark.anyio
async def test_ultima_execucao_retorna_a_sessao_mais_recente(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    await _execucao(ac, treino, [40, 40], aluno_id=aluno_id, data_hora="2026-10-05T10:00:00")
    await _execucao(ac, treino, [45, 42.5, 42.5], aluno_id=aluno_id, data_hora="2026-10-12T10:00:00")

    res = await ac.get(f"/alunos/{aluno_id}/ultima-execucao", params={"treino_id": treino["id"]})

    assert res.status_code == 200, res.text
    [ultima] = res.json()
    assert ultima["exercicio_id"] == treino["prescricoes"][0]["exercicio_id"]
    assert [s["carga_kg"] for s in ultima["series"]] == [45, 42.5, 42.5]

    como_usuario(_aluno_logado(aluno_id))
    res_me = await ac.get("/alunos/me/ultima-execucao", params={"treino_id": treino["id"]})
    assert res_me.status_code == 200, res_me.text
    assert res_me.json() == res.json()


@pytest.mark.anyio
async def test_ultima_execucao_sobrevive_a_troca_de_plano(ac: AsyncClient):
    aluno_id, treino_antigo = await _cenario(ac)
    await _execucao(ac, treino_antigo, [40], aluno_id=aluno_id)

    exercicio_id = treino_antigo["prescricoes"][0]["exercicio_id"]
    treino_novo = (await _criar_plano(ac, aluno_id, [exercicio_id]))["treinos"][0]

    res = await ac.get(f"/alunos/{aluno_id}/ultima-execucao", params={"treino_id": treino_novo["id"]})
    assert [s["carga_kg"] for s in res.json()[0]["series"]] == [40]


@pytest.mark.anyio
async def test_ultima_execucao_isolada_por_trainer(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    como_usuario(TRAINER_B)
    res = await ac.get(f"/alunos/{aluno_id}/ultima-execucao", params={"treino_id": treino["id"]})
    assert res.status_code == 404
```

- [x] **Step 2: Rodar e ver falhar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_execucao.py -q`
Expected: FAIL com 404/405 nas rotas novas.

- [x] **Step 3: Implementar**

Em `backend/src/controllers.py`, depois de `substituir_series`:

```python
async def _series_do_aluno(db: AsyncSession, aluno_id: int, exercicio_ids, cronologico: bool):
    """Séries do aluno nos exercícios dados, com a data da sessão."""
    ordem = (models.SessaoTreino.data_hora, models.SessaoTreino.id) if cronologico else (
        models.SessaoTreino.data_hora.desc(), models.SessaoTreino.id.desc())
    return (await db.execute(
        select(models.RegistroSerie, models.SessaoTreino.data_hora)
        .join(models.SessaoTreino, models.RegistroSerie.sessao_id == models.SessaoTreino.id)
        .where(models.SessaoTreino.aluno_id == aluno_id, models.RegistroSerie.exercicio_id.in_(exercicio_ids))
        .order_by(*ordem, models.RegistroSerie.numero_serie)
    )).all()


async def ultima_execucao(
    db: AsyncSession, aluno_id: int, treino_id: int, trainer_id: int | None = None
) -> list[dict]:
    """Por exercício do treino, as séries da última sessão em que o aluno o fez (em qualquer plano)."""
    await _aluno_do_tenant(db, aluno_id, trainer_id)
    exercicio_ids = set((await db.scalars(
        select(models.Prescricao.exercicio_id)
        .join(models.Treino, models.Prescricao.treino_id == models.Treino.id)
        .join(models.PlanoTreino, models.Treino.plano_id == models.PlanoTreino.id)
        .where(models.Treino.id == treino_id, models.PlanoTreino.aluno_id == aluno_id)
    )).all())
    if not exercicio_ids:
        return []

    # ponytail: lê o histórico inteiro desses exercícios; limitar por data se ficar lento
    ultima: dict[int, dict] = {}
    for registro, data_hora in await _series_do_aluno(db, aluno_id, exercicio_ids, cronologico=False):
        atual = ultima.setdefault(registro.exercicio_id, {
            "exercicio_id": registro.exercicio_id, "sessao_id": registro.sessao_id,
            "data_hora": data_hora, "series": [],
        })
        if atual["sessao_id"] == registro.sessao_id:
            atual["series"].append(registro)
    return list(ultima.values())
```

Em `backend/src/routes/alunos.py`, no fim:

```python
@router.get("/{aluno_id}/ultima-execucao", response_model=list[schemas.UltimaExecucaoExercicio])
async def ultima_execucao(
    aluno_id: int,
    treino_id: int,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    return await controllers.ultima_execucao(
        db, aluno_id=aluno_id, treino_id=treino_id, trainer_id=resolve_tenant_filter(current_user)
    )
```

Em `backend/src/routes/meu_perfil.py`, acrescentar o import `from src.consultoria import exigir_acesso_treino` e, no fim:

```python
@router.get(
    "/alunos/me/ultima-execucao",
    response_model=list[schemas.UltimaExecucaoExercicio],
    dependencies=[Depends(exigir_acesso_treino)],
)
async def minha_ultima_execucao(
    treino_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db),
):
    if not current_user.aluno_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não vinculado a um aluno.")
    return await controllers.ultima_execucao(db, aluno_id=current_user.aluno_id, treino_id=treino_id)
```

- [x] **Step 4: Rodar e ver passar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS, 59 passed

- [x] **Step 5: Commit**

```bash
git add backend/src/controllers.py backend/src/routes/alunos.py backend/src/routes/meu_perfil.py backend/tests/test_execucao.py
git commit -m "feat: última execução por exercício para pré-preenchimento"
```

---

### Task 5: `GET /alunos/{id}/evolucao` (semana a semana)

**Files:**
- Modify: `backend/src/controllers.py` (`evolucao_exercicio`)
- Modify: `backend/src/routes/alunos.py`
- Test: `backend/tests/test_execucao.py`

**Interfaces:**
- Consumes: `_aluno_do_tenant`, `_series_do_aluno` (Tasks 2 e 4).
- Produces: `controllers.evolucao_exercicio(db, aluno_id, exercicio_id=None, trainer_id=None) -> dict` com `exercicios: [{id, nome}]` (só os que têm registro, por nome) e `semanas: [{semana_inicio, series, carga_max, volume_carga}]` em ordem cronológica (vazia quando `exercicio_id` não vem). Rota `GET /alunos/{aluno_id}/evolucao?exercicio_id=`.

- [x] **Step 1: Escrever os testes que falham**

```python
@pytest.mark.anyio
async def test_evolucao_agrupa_por_semana(ac: AsyncClient):
    aluno_id, treino = await _cenario(ac)
    exercicio_id = treino["prescricoes"][0]["exercicio_id"]
    await _execucao(ac, treino, [40, 40], aluno_id=aluno_id, data_hora="2026-10-05T10:00:00")  # segunda
    await _execucao(ac, treino, [42.5], aluno_id=aluno_id, data_hora="2026-10-11T10:00:00")    # domingo, mesma semana
    await _execucao(ac, treino, [45, None], aluno_id=aluno_id, data_hora="2026-10-12T10:00:00")  # semana seguinte

    res = await ac.get(f"/alunos/{aluno_id}/evolucao", params={"exercicio_id": exercicio_id})

    assert res.status_code == 200, res.text
    corpo = res.json()
    assert corpo["exercicios"] == [{"id": exercicio_id, "nome": "Supino reto"}]
    s1, s2 = corpo["semanas"]
    assert s1["semana_inicio"] == "2026-10-05"
    assert [s["carga_kg"] for s in s1["series"]] == [40, 40, 42.5]
    assert s1["carga_max"] == 42.5
    assert s1["volume_carga"] == 10 * 40 + 10 * 40 + 10 * 42.5
    assert s2["semana_inicio"] == "2026-10-12"
    assert s2["carga_max"] == 45
    assert s2["volume_carga"] == 450  # peso corporal entra com 0


@pytest.mark.anyio
async def test_evolucao_so_peso_corporal(ac: AsyncClient):
    aluno_id, treino = await _cenario(ac)
    await _execucao(ac, treino, [None], aluno_id=aluno_id)
    exercicio_id = treino["prescricoes"][0]["exercicio_id"]
    [semana] = (await ac.get(f"/alunos/{aluno_id}/evolucao", params={"exercicio_id": exercicio_id})).json()["semanas"]
    assert semana["carga_max"] is None
    assert semana["volume_carga"] == 0


@pytest.mark.anyio
async def test_historico_permanece_apos_excluir_o_plano(ac: AsyncClient):
    aluno_id, treino = await _cenario(ac)
    await _execucao(ac, treino, [40], aluno_id=aluno_id)
    plano_id = (await ac.get(f"/alunos/{aluno_id}")).json()["planos_treino"][0]["id"]
    assert (await ac.delete(f"/planos/{plano_id}")).status_code == 204

    exercicio_id = treino["prescricoes"][0]["exercicio_id"]
    corpo = (await ac.get(f"/alunos/{aluno_id}/evolucao", params={"exercicio_id": exercicio_id})).json()
    assert len(corpo["semanas"]) == 1


@pytest.mark.anyio
async def test_evolucao_isolada_por_trainer(ac: AsyncClient, como_usuario):
    aluno_id, _ = await _cenario(ac)
    como_usuario(TRAINER_B)
    assert (await ac.get(f"/alunos/{aluno_id}/evolucao")).status_code == 404
```

- [x] **Step 2: Rodar e ver falhar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_execucao.py -q`
Expected: FAIL com 404 em `/alunos/{id}/evolucao` (rota inexistente; o 404 do isolamento passa por acaso).

- [x] **Step 3: Implementar**

Em `backend/src/controllers.py`, depois de `ultima_execucao`:

```python
async def evolucao_exercicio(
    db: AsyncSession, aluno_id: int, exercicio_id: int | None = None, trainer_id: int | None = None
) -> dict:
    """Exercícios com registro e, para o escolhido, as séries agrupadas por semana (segunda a domingo)."""
    await _aluno_do_tenant(db, aluno_id, trainer_id)
    exercicios = (await db.execute(
        select(models.Exercicio.id, models.Exercicio.nome).distinct()
        .join(models.RegistroSerie, models.RegistroSerie.exercicio_id == models.Exercicio.id)
        .join(models.SessaoTreino, models.RegistroSerie.sessao_id == models.SessaoTreino.id)
        .where(models.SessaoTreino.aluno_id == aluno_id)
        .order_by(models.Exercicio.nome)
    )).all()

    semanas = []
    if exercicio_id is not None:
        por_semana: dict[date, list] = defaultdict(list)  # dict mantém a ordem cronológica de inserção
        for registro, data_hora in await _series_do_aluno(db, aluno_id, {exercicio_id}, cronologico=True):
            dia = data_hora.date()
            por_semana[dia - timedelta(days=dia.weekday())].append(registro)
        semanas = [
            {
                "semana_inicio": inicio,
                "series": registros,
                "carga_max": max((r.carga_kg for r in registros if r.carga_kg is not None), default=None),
                "volume_carga": sum(r.repeticoes * (r.carga_kg or 0) for r in registros),
            }
            for inicio, registros in por_semana.items()
        ]
    return {"exercicios": [{"id": i, "nome": n} for i, n in exercicios], "semanas": semanas}
```

Em `backend/src/routes/alunos.py`, no fim:

```python
@router.get("/{aluno_id}/evolucao", response_model=schemas.EvolucaoPublic)
async def evolucao(
    aluno_id: int,
    exercicio_id: int | None = None,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    return await controllers.evolucao_exercicio(
        db, aluno_id=aluno_id, exercicio_id=exercicio_id, trainer_id=resolve_tenant_filter(current_user)
    )
```

- [x] **Step 4: Rodar e ver passar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS, 63 passed

- [x] **Step 5: Commit**

```bash
git add backend/src/controllers.py backend/src/routes/alunos.py backend/tests/test_execucao.py
git commit -m "feat: evolução semanal de carga e volume por exercício"
```

---

### Task 6: `GET /atividade-recente` (feed do trainer)

**Files:**
- Modify: `backend/src/controllers.py` (`atividade_recente`)
- Create: `backend/src/routes/atividade.py`
- Modify: `backend/src/api.py` (import e `include_router`)
- Test: `backend/tests/test_execucao.py`

**Interfaces:**
- Produces: `controllers.atividade_recente(db, trainer_id=None, limit=20) -> list[dict]` no formato de `schemas.AtividadeRecente`. Rota `GET /atividade-recente?limit=` (só trainer/admin).

- [x] **Step 1: Escrever os testes que falham**

```python
@pytest.mark.anyio
async def test_feed_mostra_delta_vs_sessao_anterior(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    como_usuario(_aluno_logado(aluno_id))
    await _execucao(ac, treino, [40, 40], data_hora="2026-10-05T10:00:00")
    await _execucao(ac, treino, [42.5, 40], data_hora="2026-10-07T10:00:00")

    como_usuario(TRAINER_A)
    res = await ac.get("/atividade-recente")

    assert res.status_code == 200, res.text
    recente, primeira = res.json()
    assert recente["aluno_nome"] == "Aluno Teste"
    assert recente["treino_nome"] == "Treino A"
    assert recente["registrado_por"] == "aluno"
    assert recente["exercicios"] == [{
        "exercicio_id": treino["prescricoes"][0]["exercicio_id"], "nome": "Supino reto",
        "carga_max": 42.5, "delta_kg": 2.5,
    }]
    assert primeira["exercicios"][0]["delta_kg"] is None


@pytest.mark.anyio
async def test_feed_peso_corporal_sem_delta(ac: AsyncClient):
    aluno_id, treino = await _cenario(ac)
    await _execucao(ac, treino, [None], aluno_id=aluno_id, data_hora="2026-10-05T10:00:00")
    await _execucao(ac, treino, [None], aluno_id=aluno_id, data_hora="2026-10-07T10:00:00")
    [recente, _] = (await ac.get("/atividade-recente")).json()
    assert recente["exercicios"][0]["carga_max"] is None
    assert recente["exercicios"][0]["delta_kg"] is None


@pytest.mark.anyio
async def test_feed_isolado_por_trainer_e_fechado_ao_aluno(ac: AsyncClient, como_usuario):
    aluno_id, treino = await _cenario(ac)
    await _execucao(ac, treino, [40], aluno_id=aluno_id)
    await ac.post("/sessoes/", json={"aluno_id": aluno_id, "realizada": True})  # check-in sem séries não entra

    assert len((await ac.get("/atividade-recente")).json()) == 1

    como_usuario(TRAINER_B)
    assert (await ac.get("/atividade-recente")).json() == []

    como_usuario(_aluno_logado(aluno_id))
    assert (await ac.get("/atividade-recente")).status_code == 403
```

- [x] **Step 2: Rodar e ver falhar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_execucao.py -q`
Expected: FAIL com 404 em `/atividade-recente`.

- [x] **Step 3: Implementar**

Em `backend/src/controllers.py`, depois de `evolucao_exercicio`:

```python
async def atividade_recente(db: AsyncSession, trainer_id: int | None = None, limit: int = 20) -> list[dict]:
    """Últimas execuções com séries, com carga máxima por exercício e delta vs. a sessão anterior."""
    stmt = (
        select(models.SessaoTreino)
        .options(
            selectinload(models.SessaoTreino.aluno),
            selectinload(models.SessaoTreino.treino),
            selectinload(models.SessaoTreino.series).selectinload(models.RegistroSerie.exercicio),
        )
        .where(models.SessaoTreino.series.any())
        .order_by(models.SessaoTreino.data_hora.desc(), models.SessaoTreino.id.desc())
        .limit(limit)
    )
    if trainer_id is not None:
        stmt = stmt.join(models.Aluno, models.SessaoTreino.aluno_id == models.Aluno.id).where(
            models.Aluno.trainer_id == trainer_id
        )
    sessoes = list((await db.scalars(stmt)).all())
    if not sessoes:
        return []

    # ponytail: lê o histórico inteiro dos alunos do feed; restringir por data se ficar lento
    linhas = (await db.execute(
        select(models.SessaoTreino.aluno_id, models.RegistroSerie.exercicio_id,
               models.SessaoTreino.id, func.max(models.RegistroSerie.carga_kg))
        .join(models.RegistroSerie, models.RegistroSerie.sessao_id == models.SessaoTreino.id)
        .where(models.SessaoTreino.aluno_id.in_({s.aluno_id for s in sessoes}))
        .group_by(models.SessaoTreino.aluno_id, models.RegistroSerie.exercicio_id,
                  models.SessaoTreino.id, models.SessaoTreino.data_hora)
        .order_by(models.SessaoTreino.data_hora, models.SessaoTreino.id)
    )).all()
    historico: dict[tuple[int, int], list[tuple[int, float | None]]] = defaultdict(list)
    for aluno_id, exercicio_id, sessao_id, carga_max in linhas:
        historico[(aluno_id, exercicio_id)].append((sessao_id, carga_max))

    feed = []
    for sessao in sessoes:
        nomes = {}
        for registro in sessao.series:
            nomes.setdefault(registro.exercicio_id, registro.exercicio.nome)
        exercicios = []
        for exercicio_id, nome in nomes.items():
            linha_tempo = historico[(sessao.aluno_id, exercicio_id)]
            pos = next(i for i, (sid, _) in enumerate(linha_tempo) if sid == sessao.id)
            carga = linha_tempo[pos][1]
            anterior = linha_tempo[pos - 1][1] if pos > 0 else None
            delta = round(carga - anterior, 2) if carga is not None and anterior is not None else None
            exercicios.append({"exercicio_id": exercicio_id, "nome": nome, "carga_max": carga, "delta_kg": delta})
        feed.append({
            "sessao_id": sessao.id,
            "aluno_id": sessao.aluno_id,
            "aluno_nome": sessao.aluno.nome,
            "treino_nome": sessao.treino.nome if sessao.treino else None,
            "data_hora": sessao.data_hora,
            "registrado_por": sessao.registrado_por,
            "exercicios": exercicios,
        })
    return feed
```

Criar `backend/src/routes/atividade.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src import controllers, schemas
from src.database import get_db
from src.models import Usuario
from src.security import get_current_trainer, resolve_tenant_filter

router = APIRouter(tags=["Atividade"], dependencies=[Depends(get_current_trainer)])


@router.get("/atividade-recente", response_model=list[schemas.AtividadeRecente])
async def atividade_recente(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.atividade_recente(db, trainer_id=resolve_tenant_filter(current_user), limit=limit)
```

Em `backend/src/api.py`: acrescentar `atividade` ao import de `src.routes` e `app.include_router(atividade.router)` depois de `avisos.router`.

- [x] **Step 4: Rodar e ver passar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS, 66 passed

- [x] **Step 5: Commit**

```bash
git add backend/src/controllers.py backend/src/routes/atividade.py backend/src/api.py backend/tests/test_execucao.py
git commit -m "feat: feed de atividade recente com delta de carga"
```

---

### Task 7: Painel — registrar treino com grade de séries

**Files:**
- Create: `frontend/src/features/sessoes/series.js`
- Modify: `frontend/src/services/api.js` (`alunoService.ultimaExecucao`, `alunoService.evolucao`, `sessaoService.registrarExecucao`, novo `atividadeService`)
- Modify: `frontend/src/features/sessoes/ModalRegistrarSessao.jsx`
- Modify: `frontend/src/features/alunos/DetalheAluno.jsx` (botão "Registrar Treino" e o modal)

**Interfaces:**
- Consumes: rotas das Tasks 2, 4, 5, 6.
- Produces: `series.js` exporta `valoresIniciais(prescricoes, ultimas) -> {[chave]: {reps, kg}}` e `seriesParaEnvio(prescricoes, valores, incluir?) -> SerieIn[]`, com `chave = \`p${prescricao.id}_s${n}\``. O mesmo arquivo é copiado para o portal na Task 10.

- [x] **Step 1: Criar `frontend/src/features/sessoes/series.js`**

```js
// Grade de séries: valores iniciais e conversão para o POST /sessoes/execucao.
// Cópia idêntica em ptroster-alunos/src/utils/series.js: mudou aqui, mude lá.

export const chaveSerie = (prescricaoId, n) => `p${prescricaoId}_s${n}`;

const numero = (valor, parse) => {
    const n = parse(String(valor ?? '').replace(',', '.'));
    return Number.isNaN(n) ? null : n;
};

// "12-15" → 12, "60kg" → 60, "até a falha" → ''
const inicialPrescrito = (valor, parse) => {
    const n = numero(valor, parse);
    return n === null ? '' : String(n);
};

// Sem histórico do exercício, parte do prescrito; com histórico, repete a última execução.
export function valoresIniciais(prescricoes, ultimas) {
    const porExercicio = Object.fromEntries((ultimas ?? []).map(u => [u.exercicio_id, u.series]));
    const valores = {};
    for (const p of prescricoes ?? []) {
        const anteriores = porExercicio[p.exercicio_id] ?? [];
        for (let n = 1; n <= (p.series || 0); n++) {
            const anterior = anteriores.find(s => s.numero_serie === n) ?? anteriores[anteriores.length - 1];
            valores[chaveSerie(p.id, n)] = anterior
                ? { reps: String(anterior.repeticoes), kg: anterior.carga_kg == null ? '' : String(anterior.carga_kg) }
                : { reps: inicialPrescrito(p.repeticoes, parseInt), kg: inicialPrescrito(p.carga_kg ?? p.carga, parseFloat) };
        }
    }
    return valores;
}

// Séries sem reps válidas ficam de fora; kg vazio vira peso corporal (null).
export function seriesParaEnvio(prescricoes, valores, incluir = () => true) {
    const series = [];
    for (const p of prescricoes ?? []) {
        for (let n = 1; n <= (p.series || 0); n++) {
            const chave = chaveSerie(p.id, n);
            const reps = numero(valores[chave]?.reps, parseInt);
            if (!incluir(chave) || reps === null) continue;
            series.push({
                exercicio_id: p.exercicio_id,
                prescricao_id: p.id,
                numero_serie: n,
                repeticoes: reps,
                carga_kg: numero(valores[chave]?.kg, parseFloat),
            });
        }
    }
    return series;
}
```

- [x] **Step 2: Conferir a lógica com um assert rápido**

Run (na raiz do repo):

```bash
node --input-type=module -e "
import { valoresIniciais, seriesParaEnvio } from './frontend/src/features/sessoes/series.js';
import assert from 'node:assert/strict';
const p = [{ id: 7, exercicio_id: 3, series: 2, repeticoes: '12-15', carga: '60kg' }];
assert.deepEqual(valoresIniciais(p, []), { p7_s1: { reps: '12', kg: '60' }, p7_s2: { reps: '12', kg: '60' } });
const ult = [{ exercicio_id: 3, series: [{ numero_serie: 1, repeticoes: 10, carga_kg: 62.5 }] }];
assert.deepEqual(valoresIniciais(p, ult).p7_s2, { reps: '10', kg: '62.5' });
assert.deepEqual(seriesParaEnvio(p, { p7_s1: { reps: '10', kg: '42,5' }, p7_s2: { reps: '', kg: '40' } }),
  [{ exercicio_id: 3, prescricao_id: 7, numero_serie: 1, repeticoes: 10, carga_kg: 42.5 }]);
assert.equal(seriesParaEnvio(p, { p7_s1: { reps: '8', kg: '' } })[0].carga_kg, null);
console.log('ok');
"
```

Expected: `ok`

- [x] **Step 3: Serviços em `frontend/src/services/api.js`**

Em `alunoService`, depois de `obterPorId`:

```js
    ultimaExecucao: (id, treinoId) => apiFetch(`/alunos/${id}/ultima-execucao?treino_id=${treinoId}`),
    evolucao: (id, exercicioId) =>
        apiFetch(`/alunos/${id}/evolucao${exercicioId ? `?exercicio_id=${exercicioId}` : ''}`),
```

Em `sessaoService`, depois de `registrar`:

```js
    registrarExecucao: (dados) => apiFetch('/sessoes/execucao', {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
```

Depois de `avisoService`:

```js
export const atividadeService = {
    recente: () => apiFetch('/atividade-recente'),
};
```

- [x] **Step 4: Reescrever o bloco "realizada" do `ModalRegistrarSessao.jsx`**

O modal hoje escolhe só o plano. Passa a escolher o treino do plano ativo e mostra a grade. Faltas continuam no `POST /sessoes/` antigo.

Trocar imports e estado do topo por:

```jsx
import { useState, useEffect } from 'react';
import { X, Calendar, Dumbbell, CheckCircle2, Clock, AlertTriangle, MessageSquare } from 'lucide-react';
import { alunoService, sessaoService } from '../../services/api';
import { chaveSerie, seriesParaEnvio, valoresIniciais } from './series';

const hojeISO = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD no fuso do navegador

export default function ModalRegistrarSessao({ alunoId, planos, onClose, onSucesso }) {
  const treinos = planos?.find(p => p.esta_ativo)?.treinos ?? [];
  const [data, setData] = useState(hojeISO());
  const [treinoId, setTreinoId] = useState(treinos[0]?.id ?? '');
  const [valores, setValores] = useState({});
  const [status, setStatus] = useState('realizada');
  const [observacao, setObservacao] = useState('');
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState(null);

  const treino = treinos.find(t => t.id === Number(treinoId));

  useEffect(() => {
    if (!treino) return;
    let ativo = true;
    alunoService.ultimaExecucao(alunoId, treino.id)
      .catch(() => [])
      .then(ultimas => { if (ativo) setValores(valoresIniciais(treino.prescricoes, ultimas)); });
    return () => { ativo = false; };
  }, [alunoId, treino]);

  const mudarValor = (chave, campo, valor) =>
    setValores(prev => ({ ...prev, [chave]: { ...prev[chave], [campo]: valor } }));
```

Trocar `handleSubmit` por:

```jsx
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErro(null);

    try {
      const isRealizada = status === 'realizada';
      if (isRealizada) {
        if (!treino) throw new Error("Selecione qual treino foi realizado.");
        const series = seriesParaEnvio(treino.prescricoes, valores);
        if (series.length === 0) throw new Error("Preencha as repetições de pelo menos uma série.");
        await sessaoService.registrarExecucao({
          aluno_id: alunoId,
          treino_id: treino.id,
          // Hoje: o servidor usa a hora atual. Outro dia: meio-dia, para não virar a data por fuso.
          data_hora: data === hojeISO() ? undefined : `${data}T12:00:00`,
          observacoes_performance: observacao || null,
          series,
        });
      } else {
        if (!observacao) throw new Error("Informe o motivo da ausência.");
        await sessaoService.registrar({
          aluno_id: alunoId,
          plano_treino_id: null,
          data_hora: `${data}T12:00:00`,
          realizada: false,
          precisa_reposicao: status === 'falta_com_reposicao',
          motivo_ausencia: observacao,
        });
      }
      onSucesso();
      onClose();
    } catch (err) {
      setErro(err.message);
    } finally {
      setLoading(false);
    }
  };
```

No JSX: trocar `max={new Date().toISOString().split('T')[0]}` por `max={hojeISO()}`; trocar a largura do card `max-w-lg` por `max-w-2xl max-h-[90vh] overflow-y-auto`; e substituir o bloco `{/* Plano Selector */}` inteiro por:

```jsx
            {/* Treino e séries */}
            {status === 'realizada' && (
                <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    <label htmlFor="treino-sessao" className="text-xs font-black text-text-muted uppercase tracking-widest ml-1 flex items-center gap-2">
                        <Dumbbell size={14} className="text-brand" /> Treino Aplicado
                    </label>
                    {treinos.length === 0 ? (
                        <p className="text-xs text-text-muted italic">Aluno sem plano ativo com treinos.</p>
                    ) : (
                        <select
                            id="treino-sessao"
                            value={treinoId}
                            onChange={(e) => setTreinoId(e.target.value)}
                            className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold outline-none appearance-none cursor-pointer"
                        >
                            {treinos.map(t => <option key={t.id} value={t.id}>{t.nome}</option>)}
                        </select>
                    )}

                    {treino?.prescricoes.map(p => (
                        <fieldset key={p.id} className="border border-border rounded-2xl p-4 space-y-2">
                            <legend className="px-2 text-sm font-bold text-text-primary">
                                {p.nome_exercicio} <span className="text-text-muted font-medium">· {p.series}x {p.repeticoes}</span>
                            </legend>
                            {Array.from({ length: p.series || 0 }, (_, i) => i + 1).map(n => {
                                const chave = chaveSerie(p.id, n);
                                return (
                                    <div key={n} className="grid grid-cols-[2rem_1fr_1fr] items-center gap-3">
                                        <span className="text-xs font-bold text-text-muted">{n}</span>
                                        <input
                                            type="number" inputMode="numeric" min="0"
                                            aria-label={`${p.nome_exercicio}, série ${n}, repetições`}
                                            placeholder="reps"
                                            value={valores[chave]?.reps ?? ''}
                                            onChange={(e) => mudarValor(chave, 'reps', e.target.value)}
                                            className="bg-overlay border border-border rounded-xl px-3 py-2 text-text-primary font-bold outline-none focus:ring-2 focus:ring-brand/10"
                                        />
                                        <input
                                            type="number" inputMode="decimal" min="0" step="0.5"
                                            aria-label={`${p.nome_exercicio}, série ${n}, carga em kg`}
                                            placeholder="kg"
                                            value={valores[chave]?.kg ?? ''}
                                            onChange={(e) => mudarValor(chave, 'kg', e.target.value)}
                                            className="bg-overlay border border-border rounded-xl px-3 py-2 text-text-primary font-bold outline-none focus:ring-2 focus:ring-brand/10"
                                        />
                                    </div>
                                );
                            })}
                        </fieldset>
                    ))}
                </div>
            )}
```

Remover os imports não usados que sobrarem (`AlertCircle`, se o lint apontar).

- [x] **Step 5: Abrir o modal pelo `DetalheAluno.jsx`**

Import: `import ModalRegistrarSessao from '../sessoes/ModalRegistrarSessao';`. Estado: `const [isModalSessaoOpen, setIsModalSessaoOpen] = useState(false);`. Depois do botão de Check-in (dentro do mesmo `aluno.status === 'ativo' &&`, envolvendo os dois botões num fragmento):

```jsx
                        <button
                            onClick={() => setIsModalSessaoOpen(true)}
                            className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-surface hover:bg-overlay text-text-primary border border-border px-4 py-2 rounded-lg transition-all active:scale-95"
                        >
                            <Dumbbell size={16} />
                            <span className="text-xs font-bold uppercase tracking-widest">Registrar Treino</span>
                        </button>
```

E em `{/* Modais */}`:

```jsx
            {isModalSessaoOpen && (
                <ModalRegistrarSessao
                    alunoId={alunoId}
                    planos={aluno.planos_treino}
                    onClose={() => setIsModalSessaoOpen(false)}
                    onSucesso={() => { toast({ tipo: 'sucesso', texto: 'Treino registrado!' }); carregar(); }}
                />
            )}
```

- [x] **Step 6: Build e lint**

Run: `cd frontend && npm run build && npx eslint src -f json -o /tmp/claude-1000/-home-emmanuel-Documentos-projetos-Personal-System1-0-master/b90446f6-8761-45a6-b15c-416253f94b39/scratchpad/lint-t7.json; node -e "const r=require('/tmp/claude-1000/-home-emmanuel-Documentos-projetos-Personal-System1-0-master/b90446f6-8761-45a6-b15c-416253f94b39/scratchpad/lint-t7.json');console.log(r.reduce((a,f)=>a+f.errorCount+f.warningCount,0))"`
Expected: build OK; contagem de lint = 9 (os mesmos pré-existentes). Se subir, corrigir os novos.

- [x] **Step 7: Commit**

```bash
git add frontend/src/features/sessoes/series.js frontend/src/services/api.js frontend/src/features/sessoes/ModalRegistrarSessao.jsx frontend/src/features/alunos/DetalheAluno.jsx
git commit -m "feat: painel registra treino com reps e carga por série"
```

---

### Task 8: Painel — seção Evolução no detalhe do aluno

**Files:**
- Create: `frontend/src/features/alunos/EvolucaoExercicio.jsx`
- Modify: `frontend/src/features/alunos/DetalheAluno.jsx`

**Interfaces:**
- Consumes: `alunoService.evolucao(id, exercicioId?)` (Task 7).

- [x] **Step 1: Criar `frontend/src/features/alunos/EvolucaoExercicio.jsx`**

```jsx
import { useEffect, useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { alunoService } from '../../services/api';

// Mesmos tokens do GraficoReceita (light-only por design)
const CHART = {
    carga: 'oklch(62% 0.14 48)',   // --color-accent
    volume: 'oklch(60% 0.012 82)', // --color-text-muted
    grid: 'oklch(92% 0.006 82)',
    axis: 'oklch(60% 0.012 82)',
};

const kg = (v) => (v == null ? 'PC' : v.toLocaleString('pt-BR'));  // PC = peso corporal
const dataCurta = (iso) => new Date(`${iso}T00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });

export const EvolucaoExercicio = ({ alunoId }) => {
    const [exercicios, setExercicios] = useState([]);
    const [exercicioId, setExercicioId] = useState('');
    const [semanas, setSemanas] = useState([]);

    useEffect(() => {
        alunoService.evolucao(alunoId)
            .then(d => { setExercicios(d.exercicios); setExercicioId(d.exercicios[0]?.id ?? ''); })
            .catch(() => setExercicios([]));
    }, [alunoId]);

    useEffect(() => {
        if (!exercicioId) return;
        alunoService.evolucao(alunoId, exercicioId).then(d => setSemanas(d.semanas)).catch(() => setSemanas([]));
    }, [alunoId, exercicioId]);

    if (exercicios.length === 0) return null;

    const dados = semanas.map(s => ({
        semana: dataCurta(s.semana_inicio),
        carga_max: s.carga_max,
        volume: Math.round(s.volume_carga),
    }));

    return (
        <section aria-labelledby="evolucao-titulo" className="bg-surface border border-border rounded-xl p-6 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <h3 id="evolucao-titulo" className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <TrendingUp size={14} className="text-brand" /> Evolução
                </h3>
                <select
                    value={exercicioId}
                    onChange={(e) => setExercicioId(Number(e.target.value))}
                    aria-label="Exercício"
                    className="bg-overlay border border-border rounded-lg px-3 py-2 text-sm font-bold text-text-primary outline-none cursor-pointer"
                >
                    {exercicios.map(ex => <option key={ex.id} value={ex.id}>{ex.nome}</option>)}
                </select>
            </div>

            {dados.length > 1 && (
                <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={dados} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                            <XAxis dataKey="semana" axisLine={false} tickLine={false} tick={{ fill: CHART.axis, fontSize: 10 }} />
                            <YAxis yAxisId="carga" axisLine={false} tickLine={false} tick={{ fill: CHART.axis, fontSize: 10 }} />
                            <YAxis yAxisId="volume" orientation="right" axisLine={false} tickLine={false} tick={{ fill: CHART.axis, fontSize: 10 }} />
                            <Tooltip />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Line yAxisId="carga" dataKey="carga_max" name="Carga máx. (kg)" stroke={CHART.carga} strokeWidth={2} connectNulls />
                            <Line yAxisId="volume" dataKey="volume" name="Volume (reps × kg)" stroke={CHART.volume} strokeDasharray="4 4" />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}

            <div className="overflow-x-auto">
                <table className="w-full text-xs">
                    <thead>
                        <tr className="text-text-muted uppercase tracking-widest text-left">
                            <th className="py-2 pr-4 font-bold">Semana</th>
                            <th className="py-2 pr-4 font-bold">Séries (reps×kg)</th>
                            <th className="py-2 pr-4 font-bold text-right">Máx.</th>
                            <th className="py-2 font-bold text-right">Volume</th>
                        </tr>
                    </thead>
                    <tbody>
                        {[...semanas].reverse().map(s => (
                            <tr key={s.semana_inicio} className="border-t border-border-faint">
                                <td className="py-2 pr-4 font-mono text-text-secondary">{dataCurta(s.semana_inicio)}</td>
                                <td className="py-2 pr-4 text-text-primary">
                                    {s.series.map(r => `${r.repeticoes}×${kg(r.carga_kg)}`).join(' · ')}
                                </td>
                                <td className="py-2 pr-4 text-right font-bold tabular-nums">{kg(s.carga_max)}</td>
                                <td className="py-2 text-right tabular-nums">{Math.round(s.volume_carga).toLocaleString('pt-BR')}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
};
```

- [x] **Step 2: Montar no `DetalheAluno.jsx`**

Import: `import { EvolucaoExercicio } from './EvolucaoExercicio';`. Logo antes de `{/* Histórico */}`:

```jsx
                    <EvolucaoExercicio alunoId={alunoId} />
```

- [x] **Step 3: Build e lint**

Run: o mesmo comando do Step 6 da Task 7 (arquivo `lint-t8.json`).
Expected: build OK; lint = 9.

- [x] **Step 4: Commit**

```bash
git add frontend/src/features/alunos/EvolucaoExercicio.jsx frontend/src/features/alunos/DetalheAluno.jsx
git commit -m "feat: evolução semanal por exercício no detalhe do aluno"
```

---

### Task 9: Painel — feed "Atividade recente" com polling

**Files:**
- Create: `frontend/src/features/sessoes/AtividadeRecente.jsx`
- Modify: `frontend/src/features/alunos/ListaAlunos.jsx` (logo abaixo de `<CardAvisos ... />`)

**Interfaces:**
- Consumes: `atividadeService.recente()` (Task 7).

- [x] **Step 1: Criar `frontend/src/features/sessoes/AtividadeRecente.jsx`**

```jsx
import { useEffect, useState } from 'react';
import { Activity } from 'lucide-react';
import { atividadeService } from '../../services/api';

const POLLING_MS = 30000;
const MAX_EXERCICIOS = 3;

const kg = (v) => v.toLocaleString('pt-BR');

const textoExercicio = ({ nome, carga_max, delta_kg }) => {
    if (carga_max == null) return nome;
    const delta = delta_kg ? ` (${delta_kg > 0 ? '+' : ''}${kg(delta_kg)} kg)` : '';
    return `${nome} ${kg(carga_max)} kg${delta}`;
};

const horario = (iso) => {
    const d = new Date(iso);
    const hoje = new Date().toDateString() === d.toDateString();
    const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    return hoje ? hora : `${d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${hora}`;
};

export const AtividadeRecente = ({ onSelectAluno }) => {
    const [itens, setItens] = useState(null);

    useEffect(() => {
        // Só busca com a aba visível; ao voltar para a aba, atualiza na hora
        const carregar = () => {
            if (document.visibilityState !== 'visible') return;
            atividadeService.recente().then(setItens).catch(() => {});
        };
        carregar();
        const id = setInterval(carregar, POLLING_MS);
        document.addEventListener('visibilitychange', carregar);
        return () => {
            clearInterval(id);
            document.removeEventListener('visibilitychange', carregar);
        };
    }, []);

    if (!itens?.length) return null;

    return (
        <section aria-labelledby="atividade-titulo" className="bg-surface border border-border rounded-3xl p-5 sm:p-6 space-y-3">
            <h3 id="atividade-titulo" className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-text-muted">
                <Activity size={16} className="text-brand" /> Atividade recente
            </h3>
            <ul className="divide-y divide-border-faint" aria-live="polite">
                {itens.map(item => (
                    <li key={item.sessao_id}>
                        <button
                            type="button"
                            onClick={() => onSelectAluno(item.aluno_id)}
                            className="w-full text-left py-3 px-2 rounded-xl hover:bg-overlay transition-colors"
                        >
                            <span className="font-bold text-text-primary">{item.aluno_nome}</span>
                            <span className="text-text-muted"> · {item.treino_nome ?? 'Treino'} · {horario(item.data_hora)}</span>
                            <span className="block text-xs text-text-secondary mt-0.5">
                                {item.exercicios.slice(0, MAX_EXERCICIOS).map(textoExercicio).join(' · ')}
                                {item.exercicios.length > MAX_EXERCICIOS && ` · +${item.exercicios.length - MAX_EXERCICIOS}`}
                            </span>
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
};
```

- [x] **Step 2: Montar no `ListaAlunos.jsx`**

Import: `import { AtividadeRecente } from '../sessoes/AtividadeRecente';`. Logo depois de `<CardAvisos onSelectAluno={onSelectAluno} />`:

```jsx
            <AtividadeRecente onSelectAluno={onSelectAluno} />
```

- [x] **Step 3: Build e lint**

Run: o mesmo comando do Step 6 da Task 7 (arquivo `lint-t9.json`).
Expected: build OK; lint = 9.

- [x] **Step 4: Commit**

```bash
git add frontend/src/features/sessoes/AtividadeRecente.jsx frontend/src/features/alunos/ListaAlunos.jsx
git commit -m "feat: feed de atividade recente no painel com polling de 30s"
```

---

### Task 10: Portal do Aluno — reps e kg por série, rascunho e "Salvar treino"

> **Pré-condição:** decisão do usuário sobre o WIP não commitado em `ptroster-alunos` (`src/pages/Treinos.jsx` com salvamento de carga com debounce, `src/pages/Treinos.test.jsx`, `package.json` com vitest). Esta task substitui exatamente o campo "Minha Carga" que o WIP melhora. Seguir a escolha registrada no ledger.

**Repo:** `~/Documentos/projetos/ptroster-alunos`, branch `feat/registro-series` criada a partir de `feat/consultoria`.

**Files:**
- Create: `src/utils/series.js` (cópia idêntica de `frontend/src/features/sessoes/series.js`, com o comentário apontando para o painel)
- Modify: `src/pages/Treinos.jsx` (`ExercicioAccordion`, `CompletionModal`, `Treinos`)
- Modify: `src/hooks/useAluno.js` (remove `atualizarCarga`)

**Interfaces:**
- Consumes: `GET /alunos/me/ultima-execucao?treino_id=`, `POST /sessoes/execucao` (Tasks 2 e 4); `valoresIniciais`, `seriesParaEnvio`, `chaveSerie`.

- [x] **Step 1: Criar a branch e copiar `series.js`**

```bash
cd ~/Documentos/projetos/ptroster-alunos && git switch -c feat/registro-series
cp ~/Documentos/projetos/Personal_System1.0-master/frontend/src/features/sessoes/series.js src/utils/series.js
sed -i 's#// Cópia idêntica em ptroster-alunos/src/utils/series.js: mudou aqui, mude lá.#// Cópia idêntica de Personal_System1.0/frontend/src/features/sessoes/series.js: mudou aqui, mude lá.#' src/utils/series.js
```

- [x] **Step 2: `ExercicioAccordion` com reps e kg editáveis**

Nova assinatura (sem carga, sem debounce):

```jsx
function ExercicioAccordion({ prescricao, numero, groupPosition, doneSets, onToggle, isOpen, onOpen, valores, onValor }) {
  const sets    = useMemo(() => Array.from({ length: prescricao.series || 0 }, (_, i) => i + 1), [prescricao.series]);
  const doneCnt = sets.filter(n => doneSets[chaveSerie(prescricao.id, n)]).length;
  const allDone = doneCnt === sets.length && sets.length > 0;
```

Apagar: os estados `cargaInput/salvando/salvo`, os refs `cargaSalvaRef/inputRef/debounceCargaRef/salvamentoAtualRef`, o efeito de ressincronização, `salvarCarga`, o efeito de debounce, `handleSalvarCarga` e o bloco JSX `{/* Input de carga */}`. Onde o cabeçalho do acordeão mostrava a carga (`cargaInput`), mostrar a carga prescrita: `prescricao.carga_kg || prescricao.carga`.

Cabeçalho das séries: `['#', 'Reps', 'Kg', '✓']`. Em cada linha, trocar os dois `<span>` de reps e carga por:

```jsx
                <input
                  type="number" inputMode="numeric" min="0"
                  aria-label={`Série ${n}, repetições`}
                  placeholder={prescricao.repeticoes || '—'}
                  value={valores[key]?.reps ?? ''}
                  onChange={e => onValor(key, 'reps', e.target.value)}
                  className="input-dark mx-2 px-2 py-2 text-[15px] font-bold text-center rounded-xl"
                  style={{ background: '#222', border: '1.5px solid #333', color: done ? '#00FF7F' : '#fff', outline: 'none' }}
                />
                <input
                  type="number" inputMode="decimal" min="0" step="0.5"
                  aria-label={`Série ${n}, carga em kg`}
                  placeholder="kg"
                  value={valores[key]?.kg ?? ''}
                  onChange={e => onValor(key, 'kg', e.target.value)}
                  className="input-dark mx-2 px-2 py-2 text-[15px] font-bold text-center rounded-xl"
                  style={{ background: '#222', border: '1.5px solid #333', color: done ? '#00FF7F' : '#fff', outline: 'none' }}
                />
```

`const key = chaveSerie(prescricao.id, n);` no lugar do template literal.

- [x] **Step 3: `CompletionModal` salva o treino**

Props: `({ onSalvar, salvando, onClose, totalSets, treinoNome })`. Trocar o botão "Fazer Check-in ✓" por:

```jsx
        <button
          onClick={onSalvar}
          disabled={salvando}
          className="w-full py-3.5 bg-primary text-black font-black rounded-2xl text-sm mb-2 disabled:opacity-60"
        >
          {salvando ? 'Salvando…' : 'Salvar treino ✓'}
        </button>
```

- [x] **Step 4: Estado, pré-preenchimento, rascunho e envio em `Treinos`**

Imports novos: `import api from '../services/api';`, `import { getAlunoId } from '../utils/auth';`, `import { chaveSerie, seriesParaEnvio, valoresIniciais } from '../utils/series';`. `useAluno()` passa a devolver só `{ planoAtivo, loading, error }`.

Antes do componente:

```jsx
const chaveRascunho = (treinoId) => `ptroster_rascunho_${getAlunoId()}_${treinoId}`;

function lerRascunho(treinoId) {
  try {
    return JSON.parse(localStorage.getItem(chaveRascunho(treinoId)));
  } catch {
    return null;
  }
}

function gravarRascunho(treinoId, rascunho) {
  try {
    if (rascunho) localStorage.setItem(chaveRascunho(treinoId), JSON.stringify(rascunho));
    else localStorage.removeItem(chaveRascunho(treinoId));
  } catch {
    // modo privado ou storage cheio: segue sem rascunho
  }
}
```

No componente, novo estado `const [valores, setValores] = useState({});` e `const [salvando, setSalvando] = useState(false);`. Substituir o efeito que reage a `selectedIdx` por:

```jsx
  useEffect(() => {
    setOpenPrescId(selectedTreino?.prescricoes?.[0]?.id ?? null);
    setRestSecs(null);
    clearTimeout(timerRef.current);
    if (!selectedTreino) return;

    const rascunho = lerRascunho(selectedTreino.id);
    setDoneSets(rascunho?.doneSets ?? {});
    if (rascunho?.valores) {
      setValores(rascunho.valores);
      return;
    }
    setValores(valoresIniciais(selectedTreino.prescricoes, []));
    let ativo = true;
    api.get('/alunos/me/ultima-execucao', { params: { treino_id: selectedTreino.id } })
      .then(({ data }) => { if (ativo) setValores(valoresIniciais(selectedTreino.prescricoes, data)); })
      .catch(() => {});  // sem histórico: fica o prescrito
    return () => { ativo = false; };
  }, [selectedTreino?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Rascunho só depois que o aluno mexeu em algo
  useEffect(() => {
    if (selectedTreino && Object.keys(doneSets).length > 0) {
      gravarRascunho(selectedTreino.id, { doneSets, valores });
    }
  }, [doneSets, valores]); // eslint-disable-line react-hooks/exhaustive-deps

  function mudarValor(chave, campo, valor) {
    setValores(prev => ({ ...prev, [chave]: { ...prev[chave], [campo]: valor } }));
  }

  async function salvarTreino() {
    const series = seriesParaEnvio(selectedTreino.prescricoes, valores, chave => doneSets[chave]);
    if (series.length === 0) {
      show('Marque ao menos uma série com repetições.', 'error');
      return;
    }
    setSalvando(true);
    try {
      await api.post('/sessoes/execucao', { treino_id: selectedTreino.id, series });
      gravarRascunho(selectedTreino.id, null);
      setShowModal(false);
      setDoneSets({});
      show('Treino salvo!');
      navigate('/historico');
    } catch {
      // Rascunho continua salvo; o botão do modal é o "tentar de novo"
      show('Não foi possível salvar. Toque em "Salvar treino" para tentar de novo.', 'error');
    } finally {
      setSalvando(false);
    }
  }
```

No JSX: `CompletionModal` recebe `onSalvar={salvarTreino}` e `salvando={salvando}` no lugar de `onCheckin`. `ExercicioAccordion` recebe `valores={valores}` e `onValor={mudarValor}` no lugar de `onSalvarCarga`/`onErroCarga`. Em `toggleSet`, trocar o template da chave por `chaveSerie(prescId, setNum)`.

Em `src/hooks/useAluno.js`: apagar `atualizarCarga` e o import de `api` e `useCallback` se ficarem sem uso. Retorno: `{ aluno, setAluno, planoAtivo, loading, error }`.

- [x] **Step 5: Teste da conversão de séries**

Se o vitest estiver disponível (depende da decisão sobre o WIP), criar `src/utils/series.test.js` com os mesmos asserts do Step 2 da Task 7 em `describe/it/expect` e rodar `npm test`. Sem vitest, rodar o mesmo `node --input-type=module` do Step 2 da Task 7 apontando para `src/utils/series.js`.
Expected: pass / `ok`.

- [x] **Step 6: Build e lint**

Run: `npm run build && npx eslint src -f json -o <scratchpad>/lint-t10.json` e contar problemas.
Expected: build OK; lint ≤ 3 (os pré-existentes) — os erros que somem junto com o código de carga contam como ganho.

- [x] **Step 7: Commit**

```bash
git add src/utils/series.js src/pages/Treinos.jsx src/hooks/useAluno.js
git commit -m "feat: aluno registra reps e carga por série e salva o treino"
```

---

### Task 11: Remover `PATCH /prescricoes/{id}/carga`

> **Deploy:** só publicar este commit depois que o portal da Task 10 estiver no ar. Portal antigo + backend novo = aluno sem conseguir salvar carga.

**Files:**
- Delete: `backend/src/routes/prescricoes.py`
- Modify: `backend/src/api.py` (tira `prescricoes` do import e do `include_router`)
- Modify: `backend/src/controllers.py` (apaga `atualizar_carga_prescricao`)
- Modify: `backend/src/schemas.py` (apaga `PrescricaoCargarUpdate`)
- Modify: `backend/tests/test_consultoria.py` (~linha 210: a checagem de trava usava `PATCH /prescricoes/1/carga`)

- [x] **Step 1: Ajustar o teste primeiro**

Em `test_consultoria.py`, no teste que lista endpoints bloqueados pela trava, trocar
`await ac.patch("/prescricoes/1/carga", json={"carga": "20"}),`
por
`await ac.post("/sessoes/execucao", json={"treino_id": 1, "series": [{"exercicio_id": 1, "numero_serie": 1, "repeticoes": 10}]}),`
e acrescentar a `test_execucao.py`:

```python
@pytest.mark.anyio
async def test_patch_de_carga_foi_removido(ac: AsyncClient):
    assert (await ac.patch("/prescricoes/1/carga", json={"carga": "20"})).status_code in (404, 405)
```

- [x] **Step 2: Rodar e ver falhar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: FAIL só em `test_patch_de_carga_foi_removido` (rota ainda responde 403/404 de prescrição). Se responder 404 já hoje (prescrição 1 inexistente) o teste passa por acaso: nesse caso criar antes um cenário com `_cenario` e usar o id real da prescrição, logado como o aluno.

- [x] **Step 3: Remover rota, controller e schema**

```bash
git rm backend/src/routes/prescricoes.py
```

Editar `api.py`, `controllers.py`, `schemas.py` como listado em **Files**.

- [x] **Step 4: Rodar e ver passar**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS, 67 passed

- [x] **Step 5: Commit**

```bash
git add -A backend/src backend/tests
git commit -m "refactor: remove PATCH de carga da prescrição, substituído pelo registro por série"
```
