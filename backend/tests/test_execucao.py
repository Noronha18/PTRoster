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
