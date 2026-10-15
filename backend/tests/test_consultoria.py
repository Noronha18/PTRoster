from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from src import consultoria, models

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



def _plano(id: int, inicio: date, semanas: int, ativo: bool = True) -> models.PlanoTreino:
    return models.PlanoTreino(id=id, data_inicio=inicio, duracao_semanas=semanas, esta_ativo=ativo)


@pytest.mark.anyio  # fixture autouse _banco_limpo é assíncrona
async def test_fim_programa_soma_semanas():
    assert consultoria.fim_programa(_plano(1, date(2026, 10, 1), 2)) == date(2026, 10, 15)


@pytest.mark.anyio  # fixture autouse _banco_limpo é assíncrona
async def test_plano_vigente_ignora_inativo_e_pega_mais_recente():
    antigo = _plano(1, date(2026, 9, 1), 4)
    novo = _plano(2, date(2026, 10, 1), 4)
    inativo = _plano(3, date(2026, 11, 1), 4, ativo=False)
    assert consultoria.plano_vigente([antigo, inativo, novo]) is novo
    assert consultoria.plano_vigente([inativo]) is None


@pytest.mark.anyio  # fixture autouse _banco_limpo é assíncrona
async def test_acesso_bloqueado_regras():
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
