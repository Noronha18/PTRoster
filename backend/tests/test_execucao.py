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
