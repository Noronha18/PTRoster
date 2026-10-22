from datetime import datetime, time, timedelta

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
    res = await ac.post(
        f"/alunos/{aluno_id}/planos",
        json={"titulo": "Plano Semana", "treinos": treinos},
    )
    assert res.status_code == 201, res.text
    return res.json()


def _series(prescricao: dict, quantidade: int = 3, data_hora: str | None = None,
            aluno_id: int | None = None) -> dict:
    payload = {
        "treino_id": prescricao["treino_id"],
        "data_hora": data_hora,
        "series": [
            {
                "exercicio_id": prescricao["exercicio_id"],
                "prescricao_id": prescricao["id"],
                "numero_serie": i + 1,
                "repeticoes": 10,
                "carga_kg": 20,
            }
            for i in range(quantidade)
        ],
    }
    if aluno_id is not None:
        payload["aluno_id"] = aluno_id
    return payload


async def _executar(ac: AsyncClient, aluno_id: int, prescricoes: list[dict],
                    data_hora: datetime, quantidade: int = 3) -> None:
    series = []
    for prescricao in prescricoes:
        series.extend(_series(prescricao, quantidade, data_hora.isoformat(), aluno_id)["series"])
    res = await ac.post("/sessoes/execucao", json={
        "aluno_id": aluno_id,
        "treino_id": prescricoes[0]["treino_id"],
        "data_hora": data_hora.isoformat(),
        "series": series,
    })
    assert res.status_code == 201, res.text


def _prescricoes(plano: dict) -> list[dict]:
    return [
        {**p, "treino_id": t["id"]}
        for t in plano["treinos"]
        for p in t["prescricoes"]
    ]


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

    clone = (await ac.post(f"/planos/{plano['id']}/clonar?aluno_id={aluno_id}")).json()
    assert clone["treinos"][0]["vezes_por_semana"] == 2
    assert clone["treinos"][0]["dias_sugeridos"] == [0, 3]


@pytest.mark.anyio
async def test_grupo_muscular_e_normalizado_e_validado(ac: AsyncClient):
    ok = await ac.post("/exercicios/", json={"nome": "Remada Caixa", "grupo_muscular": "costas"})
    assert ok.status_code == 201, ok.text
    assert ok.json()["grupo_muscular"] == "Costas"

    invalido = await ac.post(
        "/exercicios/", json={"nome": "Exercicio Invalido", "grupo_muscular": "Pernas"}
    )
    assert invalido.status_code == 422, invalido.text


@pytest.mark.anyio
async def test_nome_de_exercicio_unico_ignorando_caixa(ac: AsyncClient):
    primeiro = await ac.post(
        "/exercicios/", json={"nome": "Supino Case", "grupo_muscular": "Peito"}
    )
    assert primeiro.status_code == 201, primeiro.text

    duplicado = await ac.post(
        "/exercicios/", json={"nome": "supino case", "grupo_muscular": "Peito"}
    )
    assert duplicado.status_code == 409, duplicado.text


@pytest.mark.anyio
async def test_dias_sugeridos_invalidos_retornam_422(ac: AsyncClient):
    ex = await _criar_exercicio(ac, "Supino Dias", "Peito")
    aluno_id = await _criar_aluno(ac)
    res = await ac.post(f"/alunos/{aluno_id}/planos", json={
        "titulo": "Plano Inválido",
        "treinos": [{
            "nome": "Treino A",
            "dias_sugeridos": [7],
            "prescricoes": [{"exercicio_id": ex, "series": 3, "repeticoes": "10"}],
        }],
    })
    assert res.status_code == 422


@pytest.mark.anyio
async def test_semana_planejado_realizado_e_media(ac: AsyncClient, como_usuario):
    hoje = consultoria.hoje()
    inicio = hoje - timedelta(days=hoje.weekday())
    ex1 = await _criar_exercicio(ac, "Supino Semana 1", "Peito")
    ex2 = await _criar_exercicio(ac, "Supino Semana 2", "Peito")
    aluno_id = await _criar_aluno(ac)
    plano = await _criar_plano(ac, aluno_id, [{
        "nome": "Treino A",
        "vezes_por_semana": 2,
        "dias_sugeridos": [hoje.weekday()],
        "prescricoes": [
            {"exercicio_id": ex1, "series": 3, "repeticoes": "10"},
            {"exercicio_id": ex2, "series": 3, "repeticoes": "10"},
        ],
    }])
    prescricoes = _prescricoes(plano)

    # Duas sessões nesta semana (segunda e quarta) e uma na semana anterior.
    await _executar(ac, aluno_id, prescricoes, datetime.combine(inicio, time(10, 0)))
    await _executar(ac, aluno_id, prescricoes, datetime.combine(inicio + timedelta(days=2), time(10, 0)))
    await _executar(ac, aluno_id, prescricoes, datetime.combine(inicio - timedelta(days=5), time(10, 0)))

    res = await ac.get(f"/alunos/{aluno_id}/semana", params={"ref": hoje.isoformat()})
    assert res.status_code == 200, res.text
    corpo = res.json()

    assert corpo["semana_inicio"] == inicio.isoformat()
    assert corpo["semana_fim"] == (inicio + timedelta(days=6)).isoformat()
    treino = corpo["treinos"][0]
    assert treino["feitas"] == 2
    assert treino["dias_feitos"] == [0, 2]
    assert treino["vezes_por_semana"] == 2

    peito = next(v for v in corpo["volumes"] if v["grupo"] == "Peito")
    assert peito["planejado"] == 12  # 2 exercícios × 3 séries × 2 vezes
    assert peito["realizado"] == 12
    assert peito["media_4_semanas"] == 4.5  # (12 desta semana + 6 da anterior) / 4


@pytest.mark.anyio
async def test_semana_respeita_limite_de_domingo_e_segunda(ac: AsyncClient):
    hoje = consultoria.hoje()
    inicio = hoje - timedelta(days=hoje.weekday())
    ex = await _criar_exercicio(ac, "Agachamento Limite", "Quadríceps")
    aluno_id = await _criar_aluno(ac)
    plano = await _criar_plano(ac, aluno_id, [{
        "nome": "Treino A",
        "prescricoes": [{"exercicio_id": ex, "series": 3, "repeticoes": "10"}],
    }])
    prescricoes = _prescricoes(plano)

    domingo = datetime.combine(inicio + timedelta(days=6), time(23, 59))
    segunda_seguinte = datetime.combine(inicio + timedelta(days=7), time(0, 0))
    await _executar(ac, aluno_id, prescricoes, domingo)
    await _executar(ac, aluno_id, prescricoes, segunda_seguinte)

    atual = (await ac.get(f"/alunos/{aluno_id}/semana", params={"ref": hoje.isoformat()})).json()
    assert atual["treinos"][0]["feitas"] == 1
    assert atual["treinos"][0]["dias_feitos"] == [6]

    proxima = (await ac.get(
        f"/alunos/{aluno_id}/semana", params={"ref": (hoje + timedelta(days=7)).isoformat()}
    )).json()
    assert proxima["treinos"][0]["feitas"] == 1
    assert proxima["treinos"][0]["dias_feitos"] == [0]


@pytest.mark.anyio
async def test_semana_sugere_treino_do_dia(ac: AsyncClient, como_usuario):
    hoje = consultoria.hoje()
    ex = await _criar_exercicio(ac, "Supino Sugestao", "Peito")
    aluno_id = await _criar_aluno(ac)
    plano = await _criar_plano(ac, aluno_id, [
        {"nome": "Treino A", "dias_sugeridos": [hoje.weekday()],
         "prescricoes": [{"exercicio_id": ex, "series": 3, "repeticoes": "10"}]},
        {"nome": "Treino B",
         "prescricoes": [{"exercicio_id": ex, "series": 3, "repeticoes": "10"}]},
    ])

    como_usuario(_aluno_logado(aluno_id))
    res = await ac.get("/alunos/me/semana")
    assert res.status_code == 200, res.text
    sugestao = res.json()["treino_sugerido_hoje"]
    assert sugestao["treino_id"] == plano["treinos"][0]["id"]
    assert sugestao["treino_nome"] == "Treino A"
    assert sugestao["motivo"] == "dia_sugerido"


@pytest.mark.anyio
async def test_semana_sugere_proximo_pendente(ac: AsyncClient, como_usuario):
    hoje = consultoria.hoje()
    inicio = hoje - timedelta(days=hoje.weekday())
    ex = await _criar_exercicio(ac, "Supino Pendente", "Peito")
    aluno_id = await _criar_aluno(ac)
    plano = await _criar_plano(ac, aluno_id, [
        {"nome": "Treino A",
         "prescricoes": [{"exercicio_id": ex, "series": 3, "repeticoes": "10"}]},
        {"nome": "Treino B",
         "prescricoes": [{"exercicio_id": ex, "series": 3, "repeticoes": "10"}]},
    ])
    treino_a = next(t for t in plano["treinos"] if t["nome"] == "Treino A")
    prescricoes_a = [p for p in _prescricoes(plano) if p["treino_id"] == treino_a["id"]]
    await _executar(ac, aluno_id, prescricoes_a, datetime.combine(inicio, time(10, 0)))

    como_usuario(_aluno_logado(aluno_id))
    res = await ac.get("/alunos/me/semana")
    assert res.status_code == 200, res.text
    sugestao = res.json()["treino_sugerido_hoje"]
    assert sugestao["treino_nome"] == "Treino B"
    assert sugestao["motivo"] == "proximo_pendente"


@pytest.mark.anyio
async def test_semana_isolada_por_trainer_e_aluno(ac: AsyncClient, como_usuario):
    ex = await _criar_exercicio(ac, "Supino Tenant", "Peito")
    aluno_id = await _criar_aluno(ac)
    await _criar_plano(ac, aluno_id, [{
        "nome": "Treino A",
        "prescricoes": [{"exercicio_id": ex, "series": 3, "repeticoes": "10"}],
    }])

    como_usuario(TRAINER_B)
    assert (await ac.get(f"/alunos/{aluno_id}/semana")).status_code == 404

    como_usuario(_aluno_logado(aluno_id))
    assert (await ac.get("/alunos/me/semana")).status_code == 200


@pytest.mark.anyio
async def test_semana_bloqueada_para_consultoria_vencida(ac: AsyncClient, como_usuario):
    aluno_id = await _criar_aluno(ac)
    vencimento = consultoria.hoje() - timedelta(days=1)
    res = await ac.patch(f"/alunos/{aluno_id}", json={
        "modalidade": "consultoria",
        "data_vencimento_consultoria": vencimento.isoformat(),
        "bloquear_apos_vencimento": True,
    })
    assert res.status_code == 200, res.text

    como_usuario(_aluno_logado(aluno_id))
    res = await ac.get("/alunos/me/semana")
    assert res.status_code == 403


@pytest.mark.anyio
async def test_semana_sem_plano_ativo(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac)
    res = await ac.get(f"/alunos/{aluno_id}/semana")
    assert res.status_code == 200, res.text
    assert res.json()["treinos"] == []
    assert res.json()["volumes"] == []
