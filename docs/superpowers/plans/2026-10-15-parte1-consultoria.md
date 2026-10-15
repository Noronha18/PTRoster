# Parte 1 — Modalidade Consultoria: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alunos podem ser "presencial" (fluxo atual) ou "consultoria" (vencimento de contrato, trava de acesso opcional), e o trainer e o aluno recebem avisos de vencimento e de fim de programa.

**Architecture:** Três colunas novas em `alunos`. Um módulo novo `backend/src/consultoria.py` concentra as regras puras (vencimento, trava, fim de programa) e a dependência FastAPI que aplica a trava. Os controllers existentes ganham um ramo por modalidade no status financeiro e no pagamento. Um endpoint `GET /avisos/` alimenta o card "Atenção" do painel. O Portal do Aluno (repo separado) reage a `acesso_bloqueado` e aos campos `dias_para_*` de `GET /alunos/me`.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, pytest + httpx (SQLite em memória); React 19 + Vite + Tailwind (painel); React + axios + react-router (portal).

**Spec:** `docs/superpowers/specs/2026-10-15-acompanhamento-semanal-design.md` (seção "Parte 1 — Modalidade Consultoria")

## Global Constraints

- Rodar testes do backend: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q` (`uv` não está no PATH).
- Testes usam SQLite: nada de SQL específico de PostgreSQL nos controllers (aritmética de datas é feita em Python).
- Modalidades: `"presencial"` (default; todos os alunos atuais) e `"consultoria"`.
- Janela de aviso fixa: 7 dias (`JANELA_AVISO_DIAS = 7`). Dia 7 entra, dia 8 não.
- Fim do programa = `data_inicio + duracao_semanas * 7 dias`, do plano ativo mais recente do aluno.
- Trava: `modalidade == "consultoria"` e `bloquear_apos_vencimento` e `data_vencimento_consultoria < hoje`. Vencimento nulo não bloqueia.
- Status financeiro da consultoria: `em_dia` se `data_vencimento_consultoria >= hoje`, senão `atrasado` (nulo = `atrasado`).
- Código de erro da trava: 403 com `detail="consultoria_vencida"`. O handler global devolve isso como `{"message": "consultoria_vencida", "type": "HTTPError"}`.
- Registro feito pelo aluno não debita saldo (regra atual). Aluno de consultoria nunca tem débito nem recarga de saldo.
- Comentários e textos de UI em português, no estilo do código vizinho.
- Commits terminam com:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01ELN8nBWxTs2MvAF6GrjLq1
  ```

## Review Focus

1. **`/alunos/me` com trava não pode apagar planos.** `Aluno.planos_treino` tem `cascade="all, delete-orphan"`. Atribuir `[]` à relação ORM apagaria os planos no próximo flush. Esvaziar só o objeto de resposta (Task 4 testa que os planos continuam lá).
2. **Aluno que mudou de pacote para consultoria** mantém `tipo_pagamento="pacote"` e saldo. Não pode ter débito em check-in do trainer nem contar como "em dia" pelo saldo (Tasks 2 e 3 testam).
3. **Aluno de outro trainer** não aparece no `GET /avisos/` (Task 5 testa).
4. **Plano antigo ainda marcado ativo** (dado legado) não pode gerar aviso duplicado: só o plano vigente (maior `data_inicio`, depois maior `id`) conta (Task 2 testa `plano_vigente`).
5. **Trainer acessando endpoints de sessão** não pode ser barrado pela dependência da trava (Task 4 testa).

---

### Task 1: Campos de modalidade no aluno (migração, model, schemas)

**Files:**
- Create: `backend/alembic/versions/b1c2d3e4f5a6_add_consultoria_to_alunos.py`
- Modify: `backend/src/models.py` (classe `Aluno`, ~linhas 23-53)
- Modify: `backend/src/schemas.py` (`AlunoBase`, `AlunoUpdate`, `AlunoResumo`, `AlunoPublic`)
- Modify: `backend/tests/conftest.py` (fixtures compartilhadas)
- Test: `backend/tests/test_consultoria.py` (novo)

**Interfaces:**
- Produces: colunas `Aluno.modalidade: str`, `Aluno.data_vencimento_consultoria: date | None`, `Aluno.bloquear_apos_vencimento: bool`; atributos de instância (não mapeados) `Aluno.acesso_bloqueado = False`, `Aluno.dias_para_vencimento_consultoria = None`, `Aluno.dias_para_fim_programa = None`; `schemas.Modalidade = Literal["presencial", "consultoria"]`; fixtures `como_usuario` e `ac` em `conftest.py`.

- [ ] **Step 1: Mover fixtures para `conftest.py`**

Acrescentar ao final de `backend/tests/conftest.py` (os testes antigos definem fixtures com o mesmo nome localmente e continuam funcionando, pois a fixture local tem precedência):

```python
from httpx import AsyncClient, ASGITransport
from src.security import get_current_user

TRAINER_A = models.Usuario(id=1, username="trainer_a", role="trainer")
TRAINER_B = models.Usuario(id=2, username="trainer_b", role="trainer")


@pytest.fixture
def como_usuario():
    """Troca o usuário autenticado durante o teste e restaura ao final."""
    anterior = app.dependency_overrides.get(get_current_user)

    def _trocar(user):
        async def _override():
            return user
        app.dependency_overrides[get_current_user] = _override

    yield _trocar

    if anterior is not None:
        app.dependency_overrides[get_current_user] = anterior
    else:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ac(como_usuario):
    como_usuario(TRAINER_A)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
```

- [ ] **Step 2: Write the failing test**

Criar `backend/tests/test_consultoria.py`:

```python
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from src import models

# Mesmos ids das constantes do conftest (tests/ não é pacote, então não dá para importar de lá)
TRAINER_A = models.Usuario(id=1, username="trainer_a", role="trainer")
TRAINER_B = models.Usuario(id=2, username="trainer_b", role="trainer")
HOJE = date.today()


def _dia(delta: int) -> str:
    return (HOJE + timedelta(days=delta)).isoformat()


def _aluno_logado(aluno_id: int) -> models.Usuario:
    return models.Usuario(id=500 + aluno_id, username=f"aluno_{aluno_id}", role="aluno", aluno_id=aluno_id)


async def _criar_aluno(ac: AsyncClient, **extras) -> int:
    res = await ac.post("/alunos/", json={"nome": "Aluno Teste", **extras})
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _criar_plano(ac: AsyncClient, aluno_id: int, duracao_semanas: int = 4) -> dict:
    payload = {"titulo": "Plano", "duracao_semanas": duracao_semanas, "treinos": []}
    res = await ac.post(f"/alunos/{aluno_id}/planos", json=payload)
    assert res.status_code in (200, 201), res.text
    return res.json()


@pytest.mark.anyio
async def test_aluno_novo_e_presencial_por_padrao(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac)
    aluno = (await ac.get(f"/alunos/{aluno_id}")).json()
    assert aluno["modalidade"] == "presencial"
    assert aluno["data_vencimento_consultoria"] is None
    assert aluno["bloquear_apos_vencimento"] is False


@pytest.mark.anyio
async def test_cria_e_edita_aluno_de_consultoria(ac: AsyncClient):
    aluno_id = await _criar_aluno(
        ac, modalidade="consultoria", data_vencimento_consultoria=_dia(30), bloquear_apos_vencimento=True
    )
    aluno = (await ac.get(f"/alunos/{aluno_id}")).json()
    assert aluno["modalidade"] == "consultoria"
    assert aluno["data_vencimento_consultoria"] == _dia(30)
    assert aluno["bloquear_apos_vencimento"] is True

    res = await ac.patch(f"/alunos/{aluno_id}", json={"data_vencimento_consultoria": _dia(60)})
    assert res.status_code == 200, res.text
    assert res.json()["data_vencimento_consultoria"] == _dia(60)


@pytest.mark.anyio
async def test_modalidade_invalida_e_rejeitada(ac: AsyncClient):
    res = await ac.post("/alunos/", json={"nome": "X", "modalidade": "online"})
    assert res.status_code == 422
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_consultoria.py -q`
Expected: FAIL (`KeyError: 'modalidade'` e o 422 não acontece).

- [ ] **Step 4: Model**

Em `backend/src/models.py`, na classe `Aluno`, logo após `status = Column(...)`:

```python
    modalidade = Column(String, default="presencial", nullable=False)  # "presencial" ou "consultoria"
    data_vencimento_consultoria = Column(Date, nullable=True)
    bloquear_apos_vencimento = Column(Boolean, default=False, nullable=False)
```

E no bloco "Propriedades auxiliares para a View", após `status_financeiro = "em_dia"`:

```python
    acesso_bloqueado = False
    dias_para_vencimento_consultoria = None
    dias_para_fim_programa = None
```

- [ ] **Step 5: Migração**

Criar `backend/alembic/versions/b1c2d3e4f5a6_add_consultoria_to_alunos.py`:

```python
"""add modalidade consultoria to alunos

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('alunos', sa.Column('modalidade', sa.String(), nullable=False, server_default='presencial'))
    op.add_column('alunos', sa.Column('data_vencimento_consultoria', sa.Date(), nullable=True))
    op.add_column('alunos', sa.Column('bloquear_apos_vencimento', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('alunos', 'bloquear_apos_vencimento')
    op.drop_column('alunos', 'data_vencimento_consultoria')
    op.drop_column('alunos', 'modalidade')
```

Antes de criar, confirmar que `a9b8c7d6e5f4` é o head: `grep -l "down_revision.*a9b8c7d6e5f4" backend/alembic/versions/*.py` deve retornar vazio.

- [ ] **Step 6: Schemas**

Em `backend/src/schemas.py`, após `TipoPagamento = ...`:

```python
Modalidade = Literal["presencial", "consultoria"]
```

Em `AlunoBase`, após `status: StatusAluno = "ativo"`:

```python
    modalidade: Modalidade = "presencial"
    data_vencimento_consultoria: Optional[date] = None
    bloquear_apos_vencimento: bool = False
```

Em `AlunoUpdate`, após `status: Optional[StatusAluno] = None`:

```python
    modalidade: Optional[Modalidade] = None
    data_vencimento_consultoria: Optional[date] = None
    bloquear_apos_vencimento: Optional[bool] = None
```

Em `AlunoResumo`, após `status: str = "ativo"`:

```python
    modalidade: str = "presencial"
    data_vencimento_consultoria: Optional[date] = None
    bloquear_apos_vencimento: bool = False
```

Em `AlunoPublic`, após `status: str = "ativo"`:

```python
    modalidade: str = "presencial"
    data_vencimento_consultoria: Optional[date] = None
    bloquear_apos_vencimento: bool = False
    acesso_bloqueado: bool = False
    dias_para_vencimento_consultoria: Optional[int] = None
    dias_para_fim_programa: Optional[int] = None
```

- [ ] **Step 7: Run tests**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS (22 testes: 19 antigos + 3 novos).

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/b1c2d3e4f5a6_add_consultoria_to_alunos.py backend/src/models.py backend/src/schemas.py backend/tests/conftest.py backend/tests/test_consultoria.py
git commit -m "feat: campos de modalidade consultoria no aluno"
```

---

### Task 2: Regras de consultoria e status financeiro por modalidade

**Files:**
- Create: `backend/src/consultoria.py`
- Modify: `backend/src/controllers.py` (`_preencher_status_aluno` ~17-47, `listar_alunos_ativos` ~95-100, `get_aluno` ~126-130, `criar_aluno` ~200-202, `atualizar_aluno` ~236-238, `calcular_estatisticas_financeiras` ~681-700)
- Test: `backend/tests/test_consultoria.py`

**Interfaces:**
- Consumes: campos da Task 1.
- Produces, em `src/consultoria.py`:
  - `JANELA_AVISO_DIAS: int = 7`
  - `CODIGO_CONSULTORIA_VENCIDA: str = "consultoria_vencida"`
  - `fim_programa(plano: models.PlanoTreino) -> date`
  - `plano_vigente(planos: Iterable[models.PlanoTreino]) -> models.PlanoTreino | None`
  - `consultoria_em_dia(aluno: models.Aluno, hoje: date) -> bool`
  - `acesso_bloqueado(aluno: models.Aluno, hoje: date) -> bool`
  - `preencher_avisos(aluno: models.Aluno, hoje: date) -> None` (exige `aluno.planos_treino` já carregado)

- [ ] **Step 1: Write the failing tests**

Acrescentar a `backend/tests/test_consultoria.py`:

```python
from src import consultoria


def _plano(id: int, inicio: date, semanas: int, ativo: bool = True) -> models.PlanoTreino:
    return models.PlanoTreino(id=id, data_inicio=inicio, duracao_semanas=semanas, esta_ativo=ativo)


def test_fim_programa_soma_semanas():
    assert consultoria.fim_programa(_plano(1, date(2026, 10, 1), 2)) == date(2026, 10, 15)


def test_plano_vigente_ignora_inativo_e_pega_mais_recente():
    antigo = _plano(1, date(2026, 9, 1), 4)
    novo = _plano(2, date(2026, 10, 1), 4)
    inativo = _plano(3, date(2026, 11, 1), 4, ativo=False)
    assert consultoria.plano_vigente([antigo, inativo, novo]) is novo
    assert consultoria.plano_vigente([inativo]) is None


def test_acesso_bloqueado_regras():
    hoje = date(2026, 10, 15)
    def aluno(**kw):
        base = dict(modalidade="consultoria", bloquear_apos_vencimento=True,
                    data_vencimento_consultoria=date(2026, 10, 14))
        return models.Aluno(**{**base, **kw})
    assert consultoria.acesso_bloqueado(aluno(), hoje) is True
    assert consultoria.acesso_bloqueado(aluno(data_vencimento_consultoria=hoje), hoje) is False
    assert consultoria.acesso_bloqueado(aluno(bloquear_apos_vencimento=False), hoje) is False
    assert consultoria.acesso_bloqueado(aluno(data_vencimento_consultoria=None), hoje) is False
    assert consultoria.acesso_bloqueado(aluno(modalidade="presencial"), hoje) is False


@pytest.mark.anyio
async def test_status_financeiro_consultoria(ac: AsyncClient):
    em_dia = await _criar_aluno(ac, modalidade="consultoria", data_vencimento_consultoria=_dia(0))
    vencido = await _criar_aluno(ac, modalidade="consultoria", data_vencimento_consultoria=_dia(-1))
    sem_data = await _criar_aluno(ac, modalidade="consultoria")

    assert (await ac.get(f"/alunos/{em_dia}")).json()["status_financeiro"] == "em_dia"
    assert (await ac.get(f"/alunos/{vencido}")).json()["status_financeiro"] == "atrasado"
    assert (await ac.get(f"/alunos/{sem_data}")).json()["status_financeiro"] == "atrasado"

    lista = {a["id"]: a["status_financeiro"] for a in (await ac.get("/alunos/")).json()}
    assert lista == {em_dia: "em_dia", vencido: "atrasado", sem_data: "atrasado"}

    stats = (await ac.get("/pagamentos/estatisticas")).json()
    assert stats["total_alunos"] == 3
    assert stats["alunos_em_dia"] == 1


@pytest.mark.anyio
async def test_consultoria_com_saldo_legado_nao_conta_como_em_dia(ac: AsyncClient):
    """Aluno que era de pacote e virou consultoria mantém saldo, mas o status segue o vencimento."""
    aluno_id = await _criar_aluno(
        ac, modalidade="consultoria", tipo_pagamento="pacote", saldo_aulas=5,
        data_vencimento_consultoria=_dia(-3),
    )
    assert (await ac.get(f"/alunos/{aluno_id}")).json()["status_financeiro"] == "atrasado"
    stats = (await ac.get("/pagamentos/estatisticas")).json()
    assert stats["alunos_em_dia"] == 0


@pytest.mark.anyio
async def test_aluno_publico_traz_dias_para_vencimento_e_fim_de_programa(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac, modalidade="consultoria", data_vencimento_consultoria=_dia(5))
    await _criar_plano(ac, aluno_id, duracao_semanas=1)
    aluno = (await ac.get(f"/alunos/{aluno_id}")).json()
    assert aluno["dias_para_vencimento_consultoria"] == 5
    assert aluno["dias_para_fim_programa"] == 7
    assert aluno["acesso_bloqueado"] is False


@pytest.mark.anyio
async def test_presencial_nao_tem_dias_para_vencimento(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac)
    aluno = (await ac.get(f"/alunos/{aluno_id}")).json()
    assert aluno["dias_para_vencimento_consultoria"] is None
    assert aluno["dias_para_fim_programa"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_consultoria.py -q`
Expected: FAIL (`ImportError: cannot import name 'consultoria'`).

- [ ] **Step 3: Criar `backend/src/consultoria.py`**

```python
"""Regras da modalidade consultoria: vencimento, trava de acesso e avisos."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from src import models

JANELA_AVISO_DIAS = 7
CODIGO_CONSULTORIA_VENCIDA = "consultoria_vencida"


def fim_programa(plano: models.PlanoTreino) -> date:
    return plano.data_inicio + timedelta(weeks=plano.duracao_semanas or 0)


def plano_vigente(planos: Iterable[models.PlanoTreino]) -> models.PlanoTreino | None:
    """Plano ativo mais recente. Defensivo contra dado legado com mais de um plano ativo."""
    ativos = [p for p in planos if p.esta_ativo]
    return max(ativos, key=lambda p: (p.data_inicio, p.id), default=None)


def consultoria_em_dia(aluno: models.Aluno, hoje: date) -> bool:
    return aluno.data_vencimento_consultoria is not None and aluno.data_vencimento_consultoria >= hoje


def acesso_bloqueado(aluno: models.Aluno, hoje: date) -> bool:
    vencimento = aluno.data_vencimento_consultoria
    return (
        aluno.modalidade == "consultoria"
        and bool(aluno.bloquear_apos_vencimento)
        and vencimento is not None
        and vencimento < hoje
    )


def preencher_avisos(aluno: models.Aluno, hoje: date) -> None:
    """Preenche os atributos auxiliares da view. Exige aluno.planos_treino carregado."""
    aluno.acesso_bloqueado = acesso_bloqueado(aluno, hoje)
    vencimento = aluno.data_vencimento_consultoria
    aluno.dias_para_vencimento_consultoria = (
        (vencimento - hoje).days if aluno.modalidade == "consultoria" and vencimento else None
    )
    plano = plano_vigente(aluno.planos_treino)
    aluno.dias_para_fim_programa = (fim_programa(plano) - hoje).days if plano else None
```

- [ ] **Step 4: Controllers**

Em `backend/src/controllers.py`:

1. Import: trocar `from src import models, schemas, exceptions` por `from src import models, schemas, exceptions, consultoria`.

2. Em `_preencher_status_aluno`, trocar o bloco `# 1. Status Financeiro` (`if aluno.tipo_pagamento == "pacote": ... else: ...`) por:

```python
    # 1. Status Financeiro
    if aluno.modalidade == "consultoria":
        aluno.status_financeiro = "em_dia" if consultoria.consultoria_em_dia(aluno, hoje) else "atrasado"
    elif aluno.tipo_pagamento == "pacote":
        # Se for pacote, está em dia se tiver saldo de aulas
        aluno.status_financeiro = "em_dia" if aluno.saldo_aulas > 0 else "atrasado"
    else:
        # Se for mensal, verifica pagamento no mês de referência
        stmt_pag = select(models.Pagamento).where(
            models.Pagamento.aluno_id == aluno.id,
            models.Pagamento.referencia_mes == ref_mes
        )
        result_pag = await db.execute(stmt_pag)
        pagamento = result_pag.scalars().first()
        aluno.status_financeiro = "em_dia" if pagamento else "atrasado"
```

3. Em `listar_alunos_ativos`, no loop final, trocar o `if aluno.tipo_pagamento == "pacote":` por:

```python
    for aluno in alunos:
        if aluno.modalidade == "consultoria":
            aluno.status_financeiro = "em_dia" if consultoria.consultoria_em_dia(aluno, hoje) else "atrasado"
        elif aluno.tipo_pagamento == "pacote":
            aluno.status_financeiro = "em_dia" if aluno.saldo_aulas > 0 else "atrasado"
        else:
            aluno.status_financeiro = "em_dia" if aluno.id in ids_pagos else "atrasado"
        aluno.aulas_feitas_mes = sessoes_por_aluno.get(aluno.id, 0)
```

4. Em `get_aluno`, trocar `await _preencher_status_aluno(db, aluno)` por:

```python
    await _preencher_status_aluno(db, aluno)
    consultoria.preencher_avisos(aluno, date.today())
```

5. Em `criar_aluno`, trocar:

```python
        # Atributos auxiliares para o schema
        aluno_final.status_financeiro = "em_dia"
        aluno_final.aulas_feitas_mes = 0
```

por:

```python
        # Atributos auxiliares para o schema
        await _preencher_status_aluno(db, aluno_final)
        consultoria.preencher_avisos(aluno_final, date.today())
```

6. Em `atualizar_aluno`, trocar `await _preencher_status_aluno(db, aluno)` por:

```python
        await _preencher_status_aluno(db, aluno)
        consultoria.preencher_avisos(aluno, date.today())
```

7. Em `calcular_estatisticas_financeiras`, trocar o `or_(...)` dentro de `alunos_em_dia_sq` por:

```python
            or_(
                and_(
                    models.Aluno.modalidade == "presencial",
                    models.Aluno.tipo_pagamento == "mensal",
                    models.Aluno.id.in_(
                        select(models.Pagamento.aluno_id).where(models.Pagamento.referencia_mes == ref_mes)
                    )
                ),
                and_(
                    models.Aluno.modalidade == "presencial",
                    models.Aluno.tipo_pagamento == "pacote",
                    models.Aluno.saldo_aulas > 0
                ),
                and_(
                    models.Aluno.modalidade == "consultoria",
                    models.Aluno.data_vencimento_consultoria >= hoje
                ),
            )
```

- [ ] **Step 5: Run tests**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS (todos).

- [ ] **Step 6: Commit**

```bash
git add backend/src/consultoria.py backend/src/controllers.py backend/tests/test_consultoria.py
git commit -m "feat: status financeiro e avisos por modalidade consultoria"
```

---

### Task 3: Pagamento de consultoria renova vencimento; consultoria nunca mexe em saldo

**Files:**
- Modify: `backend/src/schemas.py` (`PagamentoCreate`)
- Modify: `backend/src/controllers.py` (`registrar_pagamento` ~290-321, `registrar_sessao` ~527-540)
- Test: `backend/tests/test_consultoria.py`

**Interfaces:**
- Produces: `PagamentoCreate.novo_vencimento: Optional[date] = None`. Para aluno de consultoria é obrigatório (409 `BusinessRuleViolation` sem ele).

- [ ] **Step 1: Write the failing tests**

Acrescentar a `backend/tests/test_consultoria.py`:

```python
def _pagamento(aluno_id: int, **extras) -> dict:
    return {"aluno_id": aluno_id, "valor": 300.0, "referencia_mes": f"{HOJE.month:02d}/{HOJE.year}",
            "forma_pagamento": "PIX", **extras}


@pytest.mark.anyio
async def test_pagamento_de_consultoria_renova_vencimento_e_ignora_aulas(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac, modalidade="consultoria", data_vencimento_consultoria=_dia(-2))
    res = await ac.post("/pagamentos/", json=_pagamento(aluno_id, novo_vencimento=_dia(90), quantidade_aulas=10))
    assert res.status_code == 201, res.text

    aluno = (await ac.get(f"/alunos/{aluno_id}")).json()
    assert aluno["data_vencimento_consultoria"] == _dia(90)
    assert aluno["saldo_aulas"] == 0
    assert aluno["status_financeiro"] == "em_dia"


@pytest.mark.anyio
async def test_pagamento_de_consultoria_exige_novo_vencimento(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac, modalidade="consultoria", data_vencimento_consultoria=_dia(-2))
    res = await ac.post("/pagamentos/", json=_pagamento(aluno_id))
    assert res.status_code == 409
    assert "vencimento" in res.json()["message"].lower()


@pytest.mark.anyio
async def test_pagamento_presencial_ignora_novo_vencimento(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac, tipo_pagamento="pacote")
    res = await ac.post("/pagamentos/", json=_pagamento(aluno_id, quantidade_aulas=8, novo_vencimento=_dia(30)))
    assert res.status_code == 201, res.text
    aluno = (await ac.get(f"/alunos/{aluno_id}")).json()
    assert aluno["saldo_aulas"] == 8
    assert aluno["data_vencimento_consultoria"] is None


@pytest.mark.anyio
async def test_checkin_do_trainer_nao_debita_consultoria_com_saldo_legado(ac: AsyncClient):
    aluno_id = await _criar_aluno(
        ac, modalidade="consultoria", tipo_pagamento="pacote", saldo_aulas=5,
        data_vencimento_consultoria=_dia(30),
    )
    res = await ac.post("/sessoes/", json={"aluno_id": aluno_id})
    assert res.status_code == 201, res.text
    assert (await ac.get(f"/alunos/{aluno_id}")).json()["saldo_aulas"] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_consultoria.py -q`
Expected: FAIL nos 3 testes de consultoria (vencimento não muda; saldo vira 10; sem 409; débito de 5 para 4).

- [ ] **Step 3: Schema**

Em `PagamentoCreate`, após `observacao: Optional[str] = None`:

```python
    novo_vencimento: Optional[date] = None  # obrigatório para aluno de consultoria
```

- [ ] **Step 4: `registrar_pagamento`**

Trocar o corpo entre `_parse_referencia_mes(ref)` e `db.add(novo_pagamento)` por:

```python
    _parse_referencia_mes(ref)

    # Consultoria não usa saldo: o pagamento renova o vencimento do contrato
    quantidade_aulas = dados.quantidade_aulas
    if aluno.modalidade == "consultoria":
        if not dados.novo_vencimento:
            raise exceptions.BusinessRuleError("Informe o novo vencimento da consultoria.")
        aluno.data_vencimento_consultoria = dados.novo_vencimento
        quantidade_aulas = 0

    novo_pagamento = models.Pagamento(
        aluno_id=dados.aluno_id,
        valor=dados.valor,
        referencia_mes=ref,
        forma_pagamento=dados.forma_pagamento,
        observacao=dados.observacao,
        data_pagamento=dados.data_pagamento or hoje,
        quantidade_aulas=quantidade_aulas
    )

    # Se informou quantidade de aulas, soma ao saldo do aluno (recarga)
    if quantidade_aulas > 0:
        aluno.saldo_aulas += quantidade_aulas
```

- [ ] **Step 5: `registrar_sessao`**

Trocar `if registrado_por_staff and aula_contabilizada and aluno.tipo_pagamento == "pacote":` por:

```python
    if (registrado_por_staff and aula_contabilizada
            and aluno.modalidade == "presencial" and aluno.tipo_pagamento == "pacote"):
```

- [ ] **Step 6: Run tests**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS (todos).

- [ ] **Step 7: Commit**

```bash
git add backend/src/schemas.py backend/src/controllers.py backend/tests/test_consultoria.py
git commit -m "feat: pagamento de consultoria renova vencimento sem mexer em saldo"
```

---

### Task 4: Trava de acesso do aluno com consultoria vencida

**Files:**
- Modify: `backend/src/consultoria.py` (dependência `exigir_acesso_treino`)
- Modify: `backend/src/routes/sessoes.py` (router-level dependency)
- Modify: `backend/src/routes/prescricoes.py` (router-level dependency)
- Modify: `backend/src/routes/meu_perfil.py` (resposta esvaziada)
- Test: `backend/tests/test_consultoria.py`

**Interfaces:**
- Consumes: `consultoria.acesso_bloqueado`, `CODIGO_CONSULTORIA_VENCIDA` (Task 2).
- Produces: `async def exigir_acesso_treino(current_user: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None`. Levanta `HTTPException(403, detail="consultoria_vencida")` para usuário aluno bloqueado; não faz nada para trainer/admin. As partes 2 e 3 vão reutilizar esta dependência nos endpoints novos do aluno.

- [ ] **Step 1: Write the failing tests**

Acrescentar a `backend/tests/test_consultoria.py`:

```python
async def _aluno_bloqueado(ac: AsyncClient) -> int:
    aluno_id = await _criar_aluno(
        ac, modalidade="consultoria", data_vencimento_consultoria=_dia(-1), bloquear_apos_vencimento=True
    )
    await _criar_plano(ac, aluno_id)
    return aluno_id


@pytest.mark.anyio
async def test_aluno_bloqueado_recebe_403_nos_endpoints_de_treino(ac: AsyncClient, como_usuario):
    aluno_id = await _aluno_bloqueado(ac)
    como_usuario(_aluno_logado(aluno_id))

    for res in (
        await ac.post("/sessoes/", json={"aluno_id": aluno_id, "tipo_atividade": "Corrida"}),
        await ac.get("/sessoes/"),
        await ac.patch("/prescricoes/1/carga", json={"carga": "20"}),
    ):
        assert res.status_code == 403, res.text
        assert res.json()["message"] == "consultoria_vencida"


@pytest.mark.anyio
async def test_alunos_me_bloqueado_esconde_treinos_sem_apagar_planos(ac: AsyncClient, como_usuario):
    aluno_id = await _aluno_bloqueado(ac)

    como_usuario(_aluno_logado(aluno_id))
    me = await ac.get("/alunos/me")
    assert me.status_code == 200, me.text
    assert me.json()["acesso_bloqueado"] is True
    assert me.json()["planos_treino"] == []
    assert me.json()["sessoes"] == []

    # Regressão: planos_treino tem delete-orphan; o plano tem que continuar existindo
    como_usuario(TRAINER_A)
    assert len((await ac.get(f"/alunos/{aluno_id}")).json()["planos_treino"]) == 1


@pytest.mark.anyio
async def test_sem_trava_ou_antes_do_vencimento_acesso_liberado(ac: AsyncClient, como_usuario):
    sem_trava = await _criar_aluno(ac, modalidade="consultoria", data_vencimento_consultoria=_dia(-1))
    em_dia = await _criar_aluno(
        ac, modalidade="consultoria", data_vencimento_consultoria=_dia(0), bloquear_apos_vencimento=True
    )
    for aluno_id in (sem_trava, em_dia):
        como_usuario(_aluno_logado(aluno_id))
        assert (await ac.get("/sessoes/")).status_code == 200
        assert (await ac.get("/alunos/me")).json()["acesso_bloqueado"] is False


@pytest.mark.anyio
async def test_trainer_nunca_e_bloqueado(ac: AsyncClient):
    aluno_id = await _aluno_bloqueado(ac)
    assert (await ac.get("/sessoes/", params={"aluno_id": aluno_id})).status_code == 200
    assert (await ac.post("/sessoes/", json={"aluno_id": aluno_id})).status_code == 201
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_consultoria.py -q`
Expected: FAIL (200/201 onde se espera 403; `planos_treino` não vazio).

- [ ] **Step 3: Dependência em `consultoria.py`**

Acrescentar ao topo de `backend/src/consultoria.py` (imports):

```python
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.security import get_current_user
```

E ao final do arquivo:

```python
async def exigir_acesso_treino(
    current_user: models.Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Barra o aluno com consultoria vencida e trava ativa. Trainer/admin passam direto."""
    if current_user.role in ("trainer", "admin") or not current_user.aluno_id:
        return
    aluno = await db.get(models.Aluno, current_user.aluno_id)
    if aluno and acesso_bloqueado(aluno, date.today()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=CODIGO_CONSULTORIA_VENCIDA)
```

- [ ] **Step 4: Aplicar nos routers**

Em `backend/src/routes/sessoes.py`:

```python
from src.consultoria import exigir_acesso_treino
...
router = APIRouter(prefix="/sessoes", tags=["Sessoes"], dependencies=[Depends(exigir_acesso_treino)])
```

Em `backend/src/routes/prescricoes.py`:

```python
from src.consultoria import exigir_acesso_treino
...
router = APIRouter(tags=["Prescrições"], dependencies=[Depends(exigir_acesso_treino)])
```

- [ ] **Step 5: `/alunos/me`**

Em `backend/src/routes/meu_perfil.py`, trocar o `return await controllers.get_aluno(db, current_user.aluno_id)` por:

```python
    aluno = await controllers.get_aluno(db, current_user.aluno_id)
    if aluno.acesso_bloqueado:
        # Esvazia só a resposta: atribuir [] à relação ORM apagaria os planos (delete-orphan)
        return schemas.AlunoPublic.model_validate(aluno).model_copy(
            update={"planos_treino": [], "sessoes": []}
        )
    return aluno
```

- [ ] **Step 6: Run tests**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS (todos).

- [ ] **Step 7: Commit**

```bash
git add backend/src/consultoria.py backend/src/routes/sessoes.py backend/src/routes/prescricoes.py backend/src/routes/meu_perfil.py backend/tests/test_consultoria.py
git commit -m "feat: trava de acesso do aluno com consultoria vencida"
```

---

### Task 5: Endpoint `GET /avisos/` para o trainer

**Files:**
- Create: `backend/src/routes/avisos.py`
- Modify: `backend/src/controllers.py` (nova função `listar_avisos`, no fim da seção de alunos)
- Modify: `backend/src/schemas.py` (`AvisoConsultoria`, `AvisoPrograma`, `AvisosPublic`)
- Modify: `backend/src/api.py` (registrar router)
- Test: `backend/tests/test_consultoria.py`

**Interfaces:**
- Consumes: `consultoria.JANELA_AVISO_DIAS`, `fim_programa`, `plano_vigente`.
- Produces: `GET /avisos/` (trainer) que retorna:
  ```json
  {"consultorias": [{"aluno_id": 1, "aluno_nome": "Ana", "data_vencimento": "2026-10-20", "dias_restantes": 5}],
   "programas":    [{"aluno_id": 1, "aluno_nome": "Ana", "plano_id": 3, "plano_titulo": "Hipertrofia",
                     "data_fim": "2026-10-22", "dias_restantes": 7}]}
  ```
  Ambas as listas vêm ordenadas por `dias_restantes` crescente e incluem valores negativos (já vencido/terminado). Só alunos com `status == "ativo"`.

- [ ] **Step 1: Write the failing tests**

Acrescentar a `backend/tests/test_consultoria.py`:

```python
@pytest.mark.anyio
async def test_avisos_janela_de_7_dias(ac: AsyncClient):
    dentro = await _criar_aluno(ac, nome="Dentro", modalidade="consultoria", data_vencimento_consultoria=_dia(7))
    await _criar_aluno(ac, nome="Fora", modalidade="consultoria", data_vencimento_consultoria=_dia(8))
    vencido = await _criar_aluno(ac, nome="Vencido", modalidade="consultoria", data_vencimento_consultoria=_dia(-3))

    curto = await _criar_aluno(ac, nome="Curto")
    await _criar_plano(ac, curto, duracao_semanas=1)   # termina em 7 dias
    longo = await _criar_aluno(ac, nome="Longo")
    await _criar_plano(ac, longo, duracao_semanas=2)   # termina em 14 dias

    avisos = (await ac.get("/avisos/")).json()
    assert [a["aluno_id"] for a in avisos["consultorias"]] == [vencido, dentro]
    assert [a["dias_restantes"] for a in avisos["consultorias"]] == [-3, 7]
    assert [a["aluno_id"] for a in avisos["programas"]] == [curto]
    assert avisos["programas"][0]["dias_restantes"] == 7


@pytest.mark.anyio
async def test_avisos_ignoram_aluno_inativo_e_plano_substituido(ac: AsyncClient):
    suspenso = await _criar_aluno(ac, modalidade="consultoria", data_vencimento_consultoria=_dia(1))
    await ac.patch(f"/alunos/{suspenso}/status", params={"status": "suspenso"})

    trocou = await _criar_aluno(ac)
    await _criar_plano(ac, trocou, duracao_semanas=1)
    await _criar_plano(ac, trocou, duracao_semanas=8)  # desativa o anterior

    avisos = (await ac.get("/avisos/")).json()
    assert avisos == {"consultorias": [], "programas": []}


@pytest.mark.anyio
async def test_avisos_isolados_por_trainer(ac: AsyncClient, como_usuario):
    await _criar_aluno(ac, modalidade="consultoria", data_vencimento_consultoria=_dia(1))
    como_usuario(TRAINER_B)
    assert (await ac.get("/avisos/")).json() == {"consultorias": [], "programas": []}


@pytest.mark.anyio
async def test_avisos_negado_para_aluno(ac: AsyncClient, como_usuario):
    aluno_id = await _criar_aluno(ac)
    como_usuario(_aluno_logado(aluno_id))
    assert (await ac.get("/avisos/")).status_code == 403
```

Antes de rodar, conferir a assinatura de `PATCH /alunos/{id}/status` em `backend/src/routes/alunos.py`: `status: StatusAluno` sem `Body` é query param, então `params={"status": "suspenso"}` está correto.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest tests/test_consultoria.py -q`
Expected: FAIL (404 em `/avisos/`).

- [ ] **Step 3: Schemas**

Em `backend/src/schemas.py`, ao final:

```python
# --- SCHEMAS DE AVISOS ---
class AvisoConsultoria(BaseModel):
    aluno_id: int
    aluno_nome: str
    data_vencimento: date
    dias_restantes: int

class AvisoPrograma(BaseModel):
    aluno_id: int
    aluno_nome: str
    plano_id: int
    plano_titulo: str
    data_fim: date
    dias_restantes: int

class AvisosPublic(BaseModel):
    consultorias: List[AvisoConsultoria]
    programas: List[AvisoPrograma]
```

- [ ] **Step 4: Controller**

Em `backend/src/controllers.py`, trocar `from datetime import datetime, date` por `from datetime import datetime, date, timedelta`, acrescentar `from collections import defaultdict` e, após `excluir_aluno`:

```python
async def listar_avisos(db: AsyncSession, trainer_id: int | None = None) -> dict[str, list[dict]]:
    """Consultorias vencendo/vencidas e programas terminando/terminados na janela de aviso."""
    hoje = date.today()
    limite = hoje + timedelta(days=consultoria.JANELA_AVISO_DIAS)
    filtro = [models.Aluno.status == "ativo"]
    if trainer_id is not None:
        filtro.append(models.Aluno.trainer_id == trainer_id)

    alunos = (await db.scalars(
        select(models.Aluno)
        .where(*filtro, models.Aluno.modalidade == "consultoria",
               models.Aluno.data_vencimento_consultoria <= limite)
        .order_by(models.Aluno.data_vencimento_consultoria)
    )).all()
    consultorias = [
        {"aluno_id": a.id, "aluno_nome": a.nome, "data_vencimento": a.data_vencimento_consultoria,
         "dias_restantes": (a.data_vencimento_consultoria - hoje).days}
        for a in alunos
    ]

    planos = (await db.scalars(
        select(models.PlanoTreino)
        .join(models.Aluno, models.PlanoTreino.aluno_id == models.Aluno.id)
        .options(selectinload(models.PlanoTreino.aluno))
        .where(*filtro, models.PlanoTreino.esta_ativo)
    )).all()
    por_aluno: dict[int, list[models.PlanoTreino]] = defaultdict(list)
    for plano in planos:
        por_aluno[plano.aluno_id].append(plano)

    programas = []
    for lista in por_aluno.values():
        plano = consultoria.plano_vigente(lista)
        fim = consultoria.fim_programa(plano)
        if fim <= limite:
            programas.append({
                "aluno_id": plano.aluno_id, "aluno_nome": plano.aluno.nome, "plano_id": plano.id,
                "plano_titulo": plano.titulo, "data_fim": fim, "dias_restantes": (fim - hoje).days,
            })
    programas.sort(key=lambda p: p["dias_restantes"])

    return {"consultorias": consultorias, "programas": programas}
```

- [ ] **Step 5: Router**

Criar `backend/src/routes/avisos.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src import controllers, schemas
from src.database import get_db
from src.models import Usuario
from src.security import get_current_trainer, resolve_tenant_filter

router = APIRouter(prefix="/avisos", tags=["Avisos"], dependencies=[Depends(get_current_trainer)])


@router.get("/", response_model=schemas.AvisosPublic)
async def listar_avisos(
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.listar_avisos(db, trainer_id=resolve_tenant_filter(current_user))
```

Em `backend/src/api.py`, acrescentar `avisos` ao final da linha `from src.routes import alunos, planos, pagamentos, sessoes, auth, exercicios, ...` e, após `app.include_router(sessoes.router)`:

```python
app.include_router(avisos.router)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && SECRET_KEY="test-secret-key-for-local-pytest-0123456789" .venv/bin/python -m pytest -q`
Expected: PASS (todos).

- [ ] **Step 7: Commit**

```bash
git add backend/src/routes/avisos.py backend/src/controllers.py backend/src/schemas.py backend/src/api.py backend/tests/test_consultoria.py
git commit -m "feat: endpoint de avisos de consultoria e fim de programa"
```

---

### Task 6: Painel do trainer — cadastro, pagamento, avisos e badges

**Files:**
- Modify: `frontend/src/services/api.js` (novo `avisoService`)
- Modify: `frontend/src/features/alunos/FormAlunoModal.jsx`
- Modify: `frontend/src/features/pagamentos/ModalPagamento.jsx`
- Create: `frontend/src/features/alunos/CardAvisos.jsx`
- Modify: `frontend/src/features/alunos/ListaAlunos.jsx`
- Modify: `frontend/src/features/alunos/DetalheAluno.jsx` (~linhas 245-305)

**Interfaces:**
- Consumes: `GET /avisos/` (Task 5); campos `modalidade`, `data_vencimento_consultoria`, `bloquear_apos_vencimento`, `dias_para_vencimento_consultoria`, `dias_para_fim_programa` (Tasks 1-2); `novo_vencimento` no pagamento (Task 3).
- Produces: `avisoService.listar(): Promise<{consultorias, programas}>`.

Não há testes de frontend neste repo. A verificação é lint + build + checagem manual (Step 7).

- [ ] **Step 1: `api.js`**

Após `financeiroService`:

```js
export const avisoService = {
    listar: () => apiFetch('/avisos/'),
};
```

- [ ] **Step 2: `FormAlunoModal.jsx`**

1. Nos três objetos de estado do formulário (o `useState` inicial e os dois `setFormData` do `useEffect`), acrescentar:
   - estado inicial e reset: `modalidade: 'presencial', data_vencimento_consultoria: '', bloquear_apos_vencimento: false,`
   - edição: `modalidade: alunoEdicao.modalidade || 'presencial', data_vencimento_consultoria: alunoEdicao.data_vencimento_consultoria || '', bloquear_apos_vencimento: !!alunoEdicao.bloquear_apos_vencimento,`

2. Em `handleSubmit`, no `cleanData`, acrescentar:

```js
            data_vencimento_consultoria: formData.modalidade === 'consultoria'
                ? (formData.data_vencimento_consultoria || null)
                : null,
            bloquear_apos_vencimento: formData.modalidade === 'consultoria' && formData.bloquear_apos_vencimento,
```

3. Imediatamente antes do bloco `{/* Modalidade de Pagamento */}` (o `<div className="space-y-4">` com label "Modalidade de Pagamento"), inserir o seletor de atendimento:

```jsx
                    <div className="space-y-4">
                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Tipo de Atendimento</label>
                        <div className="flex gap-4">
                            {[
                                { id: 'presencial', label: 'Presencial' },
                                { id: 'consultoria', label: 'Consultoria' }
                            ].map(m => (
                                <button
                                    key={m.id}
                                    type="button"
                                    aria-pressed={formData.modalidade === m.id}
                                    onClick={() => setFormData({...formData, modalidade: m.id})}
                                    className={`flex-1 py-4 rounded-2xl text-xs font-black uppercase tracking-widest transition-all border
                                        ${formData.modalidade === m.id
                                            ? 'bg-brand text-brand-fg border-brand shadow-lg shadow-brand/20'
                                            : 'bg-overlay text-text-muted border-border hover:bg-overlay'}`}
                                >
                                    {m.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {formData.modalidade === 'consultoria' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-end animate-in fade-in duration-300">
                            <div className="space-y-2">
                                <label htmlFor="venc-consultoria" className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Vencimento da Consultoria</label>
                                <input
                                    id="venc-consultoria"
                                    required
                                    type="date"
                                    className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold outline-none focus:ring-2 focus:ring-brand/20"
                                    value={formData.data_vencimento_consultoria}
                                    onChange={(e) => setFormData({...formData, data_vencimento_consultoria: e.target.value})}
                                />
                            </div>
                            <label className="flex items-center gap-3 px-1 py-4 cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="w-5 h-5 accent-[var(--color-brand)]"
                                    checked={formData.bloquear_apos_vencimento}
                                    onChange={(e) => setFormData({...formData, bloquear_apos_vencimento: e.target.checked})}
                                />
                                <span className="text-sm font-semibold text-text-primary">Bloquear acesso aos treinos após o vencimento</span>
                            </label>
                        </div>
                    )}
```

Se `accent-[var(--color-brand)]` não existir no tema, usar `accent-current text-brand` (conferir o nome da variável em `frontend/src/index.css`).

4. Envolver o bloco "Modalidade de Pagamento" inteiro (o `<div className="space-y-4">` com Mensalidade/Pacote) em `{formData.modalidade === 'presencial' && ( ... )}`. Envolver também o campo "Vencimento" (dia do mês, já condicionado a `tipo_pagamento === 'mensal'`), trocando a condição por `formData.modalidade === 'presencial' && formData.tipo_pagamento === 'mensal'`. Trocar o label do valor:

```jsx
                                {formData.modalidade === 'consultoria'
                                    ? 'Valor da Consultoria'
                                    : formData.tipo_pagamento === 'mensal' ? 'Mensalidade' : 'Valor do Pacote'}
```

- [ ] **Step 3: `ModalPagamento.jsx`**

1. Estado inicial: acrescentar `novo_vencimento: ''` ao `formData`.
2. No `useEffect` que acha `alunoSelecionado`, preencher o valor também para consultoria: trocar `aluno.tipo_pagamento === 'pacote'` por `(aluno.tipo_pagamento === 'pacote' || aluno.modalidade === 'consultoria')`.
3. Em `handleSubmit`, no objeto enviado, acrescentar `novo_vencimento: formData.novo_vencimento || null,`.
4. Envolver o bloco do campo "Qtd. de Aulas" (o `<div>` que contém `formData.quantidade_aulas`) em `{alunoSelecionado?.modalidade !== 'consultoria' && ( ... )}` e, logo após, inserir:

```jsx
                    {alunoSelecionado?.modalidade === 'consultoria' && (
                        <div className="space-y-2">
                            <label htmlFor="novo-vencimento" className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1 flex items-center gap-2">
                                <Calendar size={14} className="text-brand" /> Novo Vencimento
                            </label>
                            <input
                                id="novo-vencimento"
                                required
                                type="date"
                                className="w-full bg-overlay border border-brand/30 ring-2 ring-brand/5 rounded-2xl px-5 py-4 text-text-primary font-bold outline-none focus:ring-2 focus:ring-brand/10 transition-all"
                                value={formData.novo_vencimento}
                                onChange={(e) => setFormData({...formData, novo_vencimento: e.target.value})}
                            />
                            {alunoSelecionado.data_vencimento_consultoria && (
                                <p className="text-xs text-text-muted ml-1">
                                    Vencimento atual: {new Date(alunoSelecionado.data_vencimento_consultoria + 'T00:00').toLocaleDateString('pt-BR')}
                                </p>
                            )}
                        </div>
                    )}
```

(`Calendar` já é importado de `lucide-react` neste arquivo.)

- [ ] **Step 4: `CardAvisos.jsx`**

Criar `frontend/src/features/alunos/CardAvisos.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { avisoService } from '../../services/api';

const textoDias = (dias, futuro, passado) => {
    if (dias < 0) return `${passado} há ${-dias} dia${dias === -1 ? '' : 's'}`;
    if (dias === 0) return `${futuro} hoje`;
    return `${futuro} em ${dias} dia${dias === 1 ? '' : 's'}`;
};

export const CardAvisos = ({ onSelectAluno }) => {
    const [avisos, setAvisos] = useState(null);

    useEffect(() => {
        avisoService.listar().then(setAvisos).catch(() => setAvisos(null));
    }, []);

    if (!avisos || (avisos.consultorias.length === 0 && avisos.programas.length === 0)) return null;

    const itens = [
        ...avisos.consultorias.map(a => ({
            chave: `c-${a.aluno_id}`, aluno_id: a.aluno_id, nome: a.aluno_nome, dias: a.dias_restantes,
            texto: textoDias(a.dias_restantes, 'Consultoria vence', 'Consultoria venceu'),
        })),
        ...avisos.programas.map(p => ({
            chave: `p-${p.plano_id}`, aluno_id: p.aluno_id, nome: p.aluno_nome, dias: p.dias_restantes,
            texto: `${p.plano_titulo}: ${textoDias(p.dias_restantes, 'termina', 'terminou')}`,
        })),
    ];

    return (
        <section aria-labelledby="avisos-titulo" className="bg-warning/5 border border-warning/20 rounded-3xl p-5 sm:p-6 space-y-3">
            <h3 id="avisos-titulo" className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-warning">
                <AlertTriangle size={16} /> Atenção
            </h3>
            <ul className="divide-y divide-border">
                {itens.map(item => (
                    <li key={item.chave}>
                        <button
                            type="button"
                            onClick={() => onSelectAluno(item.aluno_id)}
                            className="w-full flex justify-between items-center gap-4 py-3 text-left hover:bg-overlay rounded-xl px-2 transition-colors"
                        >
                            <span className="font-bold text-text-primary">{item.nome}</span>
                            <span className={`text-xs font-semibold ${item.dias < 0 ? 'text-danger' : 'text-text-secondary'}`}>{item.texto}</span>
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
};
```

Antes de usar `bg-warning`/`text-warning`, conferir se o token existe: `grep -n "warning" frontend/src/index.css frontend/tailwind.config.* 2>/dev/null`. Se não existir, usar os tokens de `danger` com opacidade (`bg-danger/5 border-danger/20 text-danger`).

- [ ] **Step 5: `ListaAlunos.jsx`**

1. Import: `import { CardAvisos } from './CardAvisos';`
2. Logo após o `<div className="flex justify-between items-center px-2">...</div>` do cabeçalho "Alunos", inserir `<CardAvisos onSelectAluno={onSelectAluno} />`.
3. No texto do card do aluno, trocar:

```jsx
                                        {aluno.tipo_pagamento === 'pacote'
                                            ? `${aluno.saldo_aulas} aulas restantes`
                                            : 'Plano Mensal'}
```

por:

```jsx
                                        {aluno.modalidade === 'consultoria'
                                            ? `Consultoria${aluno.data_vencimento_consultoria ? ` · vence ${new Date(aluno.data_vencimento_consultoria + 'T00:00').toLocaleDateString('pt-BR')}` : ''}`
                                            : aluno.tipo_pagamento === 'pacote'
                                                ? `${aluno.saldo_aulas} aulas restantes`
                                                : 'Plano Mensal'}
```

- [ ] **Step 6: `DetalheAluno.jsx`**

1. No bloco "Créditos / Vencimento" (~linha 295), trocar `{aluno.tipo_pagamento === 'pacote' ? (` pelo ramo de consultoria primeiro:

```jsx
                                    {aluno.modalidade === 'consultoria' ? (
                                        <>
                                            <p className="text-2xs font-bold text-text-muted uppercase tracking-widest mb-1">Consultoria até</p>
                                            <p className={`text-xs font-bold font-mono ${aluno.dias_para_vencimento_consultoria < 0 ? 'text-danger' : 'text-text-primary'}`}>
                                                {aluno.data_vencimento_consultoria
                                                    ? new Date(aluno.data_vencimento_consultoria + 'T00:00').toLocaleDateString('pt-BR')
                                                    : 'SEM DATA'}
                                            </p>
                                        </>
                                    ) : aluno.tipo_pagamento === 'pacote' ? (
```

(o restante do ternário existente fica igual).

2. Logo abaixo do badge de status financeiro (~linha 250-255, o elemento com `'Pendência Financeira'`), inserir os badges de aviso:

```jsx
                            {aluno.dias_para_vencimento_consultoria !== null && aluno.dias_para_vencimento_consultoria <= 7 && (
                                <span className="px-3 py-1 rounded-full text-2xs font-bold uppercase tracking-widest bg-danger/10 text-danger">
                                    {aluno.dias_para_vencimento_consultoria < 0
                                        ? 'Consultoria vencida'
                                        : `Consultoria vence em ${aluno.dias_para_vencimento_consultoria}d`}
                                </span>
                            )}
                            {aluno.dias_para_fim_programa !== null && aluno.dias_para_fim_programa <= 7 && (
                                <span className="px-3 py-1 rounded-full text-2xs font-bold uppercase tracking-widest bg-brand/10 text-brand">
                                    {aluno.dias_para_fim_programa < 0
                                        ? 'Programa encerrado'
                                        : `Programa termina em ${aluno.dias_para_fim_programa}d`}
                                </span>
                            )}
```

Ajustar o wrapper se o badge existente não estiver num container flex: envolver badge existente + novos em `<div className="flex flex-wrap gap-2">`.

- [ ] **Step 7: Verificar**

Run: `cd frontend && npx eslint src/ && npm run build`
Expected: sem erros de lint; build ok.

Checagem manual (backend local com SQLite não existe nesta máquina; usar `npm run dev` apontando para um backend local com Postgres via `docker compose up -d` + `alembic upgrade head`, ou pular e validar no deploy de preview). Roteiro:
1. Criar aluno "Consultoria", vencimento daqui a 3 dias, trava marcada. Card "Atenção" mostra "Consultoria vence em 3 dias".
2. Abrir o aluno: badge "Consultoria vence em 3d", bloco "Consultoria até".
3. Registrar pagamento para ele: campo "Novo Vencimento" aparece, "Qtd. de Aulas" some. Salvar com +90 dias: aviso some.
4. Editar um aluno presencial: campos de pacote/mensal iguais a antes.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/services/api.js frontend/src/features/alunos/FormAlunoModal.jsx frontend/src/features/pagamentos/ModalPagamento.jsx frontend/src/features/alunos/CardAvisos.jsx frontend/src/features/alunos/ListaAlunos.jsx frontend/src/features/alunos/DetalheAluno.jsx
git commit -m "feat: painel com modalidade consultoria, avisos e renovação no pagamento"
```

---

### Task 7: Portal do Aluno — tela de bloqueio e banner de aviso

**Repo:** `~/Documentos/projetos/ptroster-alunos` (separado).

**Files:**
- Create: `src/components/BloqueioConsultoria.jsx`
- Create: `src/components/BannerAvisos.jsx`
- Modify: `src/App.jsx` (`ProtectedLayout`)
- Modify: `src/services/api.js` (interceptor do 403)
- Modify: `src/pages/Dashboard.jsx`

**Interfaces:**
- Consumes: `GET /alunos/me` com `acesso_bloqueado`, `modalidade`, `dias_para_vencimento_consultoria`, `dias_para_fim_programa` (Tasks 2 e 4); 403 com `message == "consultoria_vencida"` (Task 4).

- [ ] **Step 1: Checar o estado do repo — PARAR se sujo**

Run: `cd ~/Documentos/projetos/ptroster-alunos && git status --short`

Em 2026-10-15 havia mudanças não commitadas na `main` (`PRODUCT.md`, `package.json`, `package-lock.json`, `src/index.css`, `src/pages/Treinos.jsx`, `AUDITORIA-UX.md`, `src/pages/Treinos.test.jsx`). **Se ainda houver, parar e perguntar ao usuário** o que fazer com elas antes de criar branch. Não fazer stash, commit ou descarte por conta própria.

Com o repo limpo: `git checkout -b feat/consultoria`.

- [ ] **Step 2: Interceptor do 403**

Em `src/services/api.js`, dentro do interceptor de resposta, antes do `return Promise.reject(error);`:

```js
    if (error.response?.status === 403 && error.response?.data?.message === 'consultoria_vencida') {
      // AuthContext ouve e recarrega /alunos/me, que traz acesso_bloqueado
      window.dispatchEvent(new Event('consultoria:vencida'));
    }
```

- [ ] **Step 3: `AuthContext` ouve o evento**

Em `src/contexts/AuthContext.jsx`, acrescentar um `useEffect` após o `useEffect` de inicialização:

```jsx
  useEffect(() => {
    const recarregar = () => {
      const alunoId = getAlunoId();
      if (alunoId) loadAluno(alunoId);
    };
    window.addEventListener('consultoria:vencida', recarregar);
    return () => window.removeEventListener('consultoria:vencida', recarregar);
  }, [loadAluno]);
```

- [ ] **Step 4: Tela de bloqueio**

Criar `src/components/BloqueioConsultoria.jsx`:

```jsx
import { useAuth } from '../contexts/AuthContext';

export function BloqueioConsultoria() {
  const { logout } = useAuth();
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-6 text-center bg-ios-background">
      <h1 className="text-2xl font-bold">Sua consultoria venceu</h1>
      <p className="text-base opacity-80 max-w-sm">
        Fale com seu treinador para renovar e voltar a acessar seus treinos.
      </p>
      {logout && (
        <button type="button" onClick={logout} className="mt-4 underline opacity-80">
          Sair
        </button>
      )}
    </div>
  );
}
```

Conferir o nome da função de logout exposta por `useAuth()` (`grep -n "logout\|signOut" src/contexts/AuthContext.jsx`) e ajustar.

Em `src/App.jsx`, dentro de `ProtectedLayout`, pegar `aluno` do `useAuth()` e, após `if (!user) return <Navigate ... />;`:

```jsx
  if (aluno?.acesso_bloqueado) return <BloqueioConsultoria />;
```

com `import { BloqueioConsultoria } from './components/BloqueioConsultoria';` e `const { user, loading, aluno } = useAuth();`.

- [ ] **Step 5: Banner**

Criar `src/components/BannerAvisos.jsx`:

```jsx
const JANELA = 7;

const emDias = (d) => (d === 0 ? 'hoje' : `em ${d} dia${d === 1 ? '' : 's'}`);

export function BannerAvisos({ aluno }) {
  if (!aluno) return null;
  const avisos = [];
  const venc = aluno.dias_para_vencimento_consultoria;
  const fim = aluno.dias_para_fim_programa;
  if (venc !== null && venc !== undefined && venc >= 0 && venc <= JANELA) {
    avisos.push(`Sua consultoria vence ${emDias(venc)}.`);
  }
  if (fim !== null && fim !== undefined && fim <= JANELA) {
    avisos.push(fim < 0 ? 'Seu programa de treino terminou. Fale com seu treinador.' : `Seu programa termina ${emDias(fim)}.`);
  }
  if (avisos.length === 0) return null;
  return (
    <div role="status" className="mx-5 mt-4 rounded-2xl px-4 py-3 bg-amber-500/15 text-amber-200 text-sm font-medium space-y-1">
      {avisos.map((t) => <p key={t}>{t}</p>)}
    </div>
  );
}
```

Ajustar as cores aos tokens do portal (tema escuro; conferir `src/index.css`).

Em `src/pages/Dashboard.jsx`, importar `BannerAvisos` e renderizar `<BannerAvisos aluno={aluno} />` logo após o cabeçalho, usando o `aluno` que a página já obtém via `useAluno()`/`useAuth()` (conferir o nome da variável na página).

- [ ] **Step 6: Verificar**

Run: `cd ~/Documentos/projetos/ptroster-alunos && npm run lint && npm test && npm run build`
Expected: lint sem erros, testes do vitest passando, build ok.

Checagem manual com backend da branch: aluno com consultoria vencida + trava vê a tela de bloqueio após login; com vencimento em 3 dias vê o banner; aluno presencial sem plano terminando não vê banner.

- [ ] **Step 7: Commit**

```bash
git add src/components/BloqueioConsultoria.jsx src/components/BannerAvisos.jsx src/App.jsx src/services/api.js src/contexts/AuthContext.jsx src/pages/Dashboard.jsx
git commit -m "feat: tela de bloqueio de consultoria e banner de avisos"
```

---

## Ordem de deploy

1. Backend (Tasks 1-5) primeiro. A migração roda sozinha no start do container (`alembic upgrade head` no `Dockerfile`). Os campos novos são aditivos, então o portal e o painel atuais continuam funcionando.
2. Painel (Task 6). Vai junto com o backend: o build do frontend sai do mesmo repo/deploy.
3. Portal (Task 7) por último.

## Fora deste plano

- Editar pagamento (`PUT /pagamentos/{id}`) não altera o vencimento da consultoria. Se o trainer errar a data, corrige no cadastro do aluno. Adicionar quando pedirem.
- Janela de aviso configurável por trainer.
