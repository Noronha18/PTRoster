import pytest
from httpx import AsyncClient

from src import models


@pytest.mark.anyio
async def test_leitura_de_exercicio_com_grupo_legado_nao_quebra(ac: AsyncClient, db):
    db.add(models.Exercicio(nome="Legado Pernas", grupo_muscular="Pernas"))
    await db.commit()

    res = await ac.get("/exercicios/")

    assert res.status_code == 200, res.text
    assert any(exercicio["nome"] == "Legado Pernas" for exercicio in res.json())


@pytest.mark.anyio
async def test_seed_encontra_nome_ignorando_caixa(ac: AsyncClient):
    criado = await ac.post(
        "/exercicios/",
        json={"nome": "leg press 45º", "grupo_muscular": "Quadríceps"},
    )
    assert criado.status_code == 201, criado.text

    res = await ac.post("/exercicios/seed")

    assert res.status_code == 201, res.text
    lista = (await ac.get("/exercicios/")).json()
    exercicio = next(
        item for item in lista
        if item["nome"].lower() == "leg press 45º"
    )
    assert exercicio["nome"] == "Leg Press 45º"
    assert exercicio["grupo_muscular"] == "Quadríceps"
