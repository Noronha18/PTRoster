import pytest
from httpx import AsyncClient, ASGITransport

from src.api import app
from src.security import get_current_user
from src import models

TRAINER_A = models.Usuario(id=1, username="trainer_a", role="trainer")
TRAINER_B = models.Usuario(id=2, username="trainer_b", role="trainer")
ADMIN = models.Usuario(id=99, username="admin", role="admin")


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


async def _criar_aluno(ac: AsyncClient, **extras) -> int:
    payload = {"nome": "Aluno Teste", **extras}
    res = await ac.post("/alunos/", json=payload)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _registrar_pagamento(ac: AsyncClient, aluno_id: int, **extras) -> dict:
    payload = {
        "aluno_id": aluno_id,
        "valor": 100.0,
        "referencia_mes": "07/2026",
        "forma_pagamento": "PIX",
        **extras,
    }
    res = await ac.post("/pagamentos/", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.anyio
async def test_checkin_por_admin_debita_saldo_de_pacote(ac: AsyncClient, como_usuario):
    """Regressão: admin (tenant filter None) não debitava saldo no check-in."""
    aluno_id = await _criar_aluno(ac, tipo_pagamento="pacote", saldo_aulas=2)

    como_usuario(ADMIN)
    res = await ac.post("/sessoes/", json={"aluno_id": aluno_id, "realizada": True})
    assert res.status_code == 201, res.text

    res_aluno = await ac.get(f"/alunos/{aluno_id}")
    assert res_aluno.json()["saldo_aulas"] == 1


@pytest.mark.anyio
async def test_deletar_pagamento_estorna_aulas_do_pacote(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac, tipo_pagamento="pacote", saldo_aulas=0)
    pagamento = await _registrar_pagamento(ac, aluno_id, quantidade_aulas=10)

    res_aluno = await ac.get(f"/alunos/{aluno_id}")
    assert res_aluno.json()["saldo_aulas"] == 10

    res_del = await ac.delete(f"/pagamentos/{pagamento['id']}")
    assert res_del.status_code == 200, res_del.text

    res_aluno = await ac.get(f"/alunos/{aluno_id}")
    assert res_aluno.json()["saldo_aulas"] == 0


@pytest.mark.anyio
async def test_editar_pagamento_aplica_referencia_e_ajusta_saldo(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac, tipo_pagamento="pacote", saldo_aulas=0)
    pagamento = await _registrar_pagamento(ac, aluno_id, quantidade_aulas=4)

    res_put = await ac.put(
        f"/pagamentos/{pagamento['id']}",
        json={
            "aluno_id": aluno_id,
            "valor": 150.0,
            "referencia_mes": "08/2026",
            "forma_pagamento": "Dinheiro",
            "quantidade_aulas": 6,
        },
    )
    assert res_put.status_code == 200, res_put.text
    corpo = res_put.json()
    assert corpo["referencia_mes"] == "08/2026"
    assert corpo["quantidade_aulas"] == 6
    assert corpo["valor"] == 150.0

    res_aluno = await ac.get(f"/alunos/{aluno_id}")
    assert res_aluno.json()["saldo_aulas"] == 6


@pytest.mark.anyio
async def test_pagamento_com_referencia_invalida_rejeitado(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac)
    res = await ac.post(
        "/pagamentos/",
        json={
            "aluno_id": aluno_id,
            "valor": 100.0,
            "referencia_mes": "2026-07",
            "forma_pagamento": "PIX",
        },
    )
    assert res.status_code == 409, res.text


@pytest.mark.anyio
async def test_criar_aluno_com_email_duplicado_retorna_409(ac: AsyncClient):
    """Regressão: e-mail duplicado estourava IntegrityError (500)."""
    await _criar_aluno(ac, email="repetido@teste.com")
    res = await ac.post("/alunos/", json={"nome": "Outro", "email": "repetido@teste.com"})
    assert res.status_code == 409, res.text


@pytest.mark.anyio
async def test_frequencia_isolada_por_trainer(ac: AsyncClient, como_usuario):
    """Regressão: trainer B conseguia consultar frequência de aluno do trainer A."""
    aluno_id = await _criar_aluno(ac)

    como_usuario(TRAINER_B)
    res = await ac.get(f"/sessoes/frequencia/{aluno_id}")
    assert res.status_code == 404, res.text


@pytest.mark.anyio
async def test_reordenacao_de_treinos_e_prescricoes_persiste(ac: AsyncClient):
    aluno_id = await _criar_aluno(ac)

    # Cria exercícios na biblioteca
    ex_ids = []
    for nome in ("Supino", "Agachamento"):
        res_ex = await ac.post("/exercicios/", json={"nome": nome, "grupo_muscular": "Outros"})
        assert res_ex.status_code == 201, res_ex.text
        ex_ids.append(res_ex.json()["id"])

    plano_payload = {
        "titulo": "Plano Ordem",
        "treinos": [
            {"nome": "Treino A", "prescricoes": [
                {"exercicio_id": ex_ids[0], "series": 3, "repeticoes": "12"},
                {"exercicio_id": ex_ids[1], "series": 3, "repeticoes": "10"},
            ]},
            {"nome": "Treino B", "prescricoes": []},
        ],
    }
    res_plano = await ac.post(f"/alunos/{aluno_id}/planos", json=plano_payload)
    assert res_plano.status_code == 201, res_plano.text
    plano = res_plano.json()

    # Inverte a ordem dos treinos e das prescrições do Treino A
    treino_a, treino_b = plano["treinos"]
    novo_payload = {
        "treinos": [
            {"id": treino_b["id"], "nome": treino_b["nome"], "prescricoes": []},
            {"id": treino_a["id"], "nome": treino_a["nome"], "prescricoes": [
                {**treino_a["prescricoes"][1]},
                {**treino_a["prescricoes"][0]},
            ]},
        ]
    }
    res_patch = await ac.patch(f"/planos/{plano['id']}", json=novo_payload)
    assert res_patch.status_code == 200, res_patch.text

    # Re-busca o aluno e confere a ordem persistida
    res_aluno = await ac.get(f"/alunos/{aluno_id}")
    plano_final = res_aluno.json()["planos_treino"][0]
    assert [t["nome"] for t in plano_final["treinos"]] == ["Treino B", "Treino A"]
    prescricoes_a = plano_final["treinos"][1]["prescricoes"]
    assert [p["exercicio_id"] for p in prescricoes_a] == [ex_ids[1], ex_ids[0]]


@pytest.mark.anyio
async def test_inadimplencia_ignora_alunos_cancelados(ac: AsyncClient):
    aluno_ativo = await _criar_aluno(ac, nome="Ativo")
    aluno_cancelado = await _criar_aluno(ac, nome="Cancelado")
    await ac.patch(f"/alunos/{aluno_cancelado}/status", params={"status": "cancelado"})

    # Aluno ativo paga o mês atual
    from datetime import date
    hoje = date.today()
    await _registrar_pagamento(ac, aluno_ativo, referencia_mes=f"{hoje.month:02d}/{hoje.year}")

    res = await ac.get("/pagamentos/estatisticas")
    assert res.status_code == 200, res.text
    corpo = res.json()
    assert corpo["total_alunos"] == 1
    assert corpo["alunos_em_dia"] == 1
    assert corpo["alunos_inadimplentes"] == 0
    assert corpo["inadimplencia"] == 0.0
