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
