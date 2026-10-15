from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from src import consultoria, models

# Mesmos ids das constantes do conftest (tests/ não é pacote, então não dá para importar de lá)
TRAINER_A = models.Usuario(id=1, username="trainer_a", role="trainer")
TRAINER_B = models.Usuario(id=2, username="trainer_b", role="trainer")
HOJE = consultoria.hoje()  # mesma data que o servidor usa


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
        await ac.post("/sessoes/execucao", json={"treino_id": 1, "series": [{"exercicio_id": 1, "numero_serie": 1, "repeticoes": 10}]}),
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
    res = await ac.patch(f"/alunos/{suspenso}/status", params={"status": "suspenso"})
    assert res.status_code == 200, res.text

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


@pytest.mark.anyio
async def test_hoje_usa_horario_de_brasilia():
    """Servidor roda em UTC: 01:00 UTC do dia 21 ainda é dia 20 em Brasília."""
    from datetime import datetime, timezone
    assert consultoria.hoje(datetime(2026, 10, 21, 1, 0, tzinfo=timezone.utc)) == date(2026, 10, 20)
    assert consultoria.hoje(datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc)) == date(2026, 10, 21)
