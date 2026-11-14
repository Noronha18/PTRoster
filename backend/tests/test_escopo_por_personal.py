import pytest
from httpx import AsyncClient

from src import models

TRAINER_A = models.Usuario(id=1, username="trainer_a", role="trainer")
TRAINER_B = models.Usuario(id=2, username="trainer_b", role="trainer")
ADMIN = models.Usuario(id=99, username="admin_teste", role="admin")


def _plano(titulo="Modelo X", exercicio_id=None):
    treinos = []
    if exercicio_id is not None:
        treinos = [{
            "nome": "A",
            "prescricoes": [{"exercicio_id": exercicio_id, "series": 3, "repeticoes": "10"}],
        }]
    return {"titulo": titulo, "duracao_semanas": 4, "treinos": treinos}


async def _modelo(ac: AsyncClient, **kw) -> int:
    res = await ac.post("/planos/templates", json=_plano(**kw))
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _aluno(ac: AsyncClient) -> int:
    res = await ac.post("/alunos/", json={"nome": "Aluno"})
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _exercicio(ac: AsyncClient, nome: str) -> dict:
    res = await ac.post("/exercicios/", json={"nome": nome, "grupo_muscular": "Peito"})
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.anyio
async def test_modelo_de_outro_personal_e_invisivel_e_intocavel(ac: AsyncClient, como_usuario):
    plano_id = await _modelo(ac)
    como_usuario(TRAINER_B)

    lista = await ac.get("/planos/templates")
    assert plano_id not in [p["id"] for p in lista.json()]
    assert (await ac.patch(f"/planos/{plano_id}", json={"titulo": "Roubado"})).status_code == 404
    assert (await ac.delete(f"/planos/{plano_id}")).status_code == 404
    assert (await ac.post(f"/planos/{plano_id}/clonar")).status_code == 404


@pytest.mark.anyio
async def test_modelo_da_plataforma_so_le_e_clona(ac: AsyncClient, db):
    db.add(models.PlanoTreino(titulo="Da plataforma", aluno_id=None, trainer_id=None, esta_ativo=False))
    await db.commit()
    plataforma_id = (await db.get(models.PlanoTreino, 1)).id

    lista = (await ac.get("/planos/templates")).json()
    assert [p["id"] for p in lista] == [plataforma_id]
    assert lista[0]["trainer_id"] is None
    assert (await ac.patch(f"/planos/{plataforma_id}", json={"titulo": "X"})).status_code == 404
    assert (await ac.delete(f"/planos/{plataforma_id}")).status_code == 404

    aluno_id = await _aluno(ac)
    res = await ac.post(f"/planos/{plataforma_id}/clonar", params={"aluno_id": aluno_id})
    assert res.status_code == 200, res.text
    assert res.json()["aluno_id"] == aluno_id

    copia = await ac.post(f"/planos/{plataforma_id}/clonar")
    assert copia.status_code == 200, copia.text
    assert copia.json()["trainer_id"] == TRAINER_A.id


@pytest.mark.anyio
async def test_clonar_para_aluno_de_outro_personal_e_recusado(ac: AsyncClient, como_usuario):
    plano_id = await _modelo(ac)
    aluno_a = await _aluno(ac)
    como_usuario(TRAINER_B)
    aluno_b_id = await _aluno(ac)
    como_usuario(TRAINER_A)

    assert aluno_b_id != aluno_a
    res = await ac.post(f"/planos/{plano_id}/clonar", params={"aluno_id": aluno_b_id})
    assert res.status_code == 404, res.text


@pytest.mark.anyio
async def test_modelo_nasce_com_trainer_id_do_criador(ac: AsyncClient, como_usuario):
    res = await ac.post("/planos/templates", json=_plano())
    assert res.json()["trainer_id"] == TRAINER_A.id
    como_usuario(TRAINER_B)
    res = await ac.post("/planos/templates", json=_plano("Do B"))
    assert res.json()["trainer_id"] == TRAINER_B.id


@pytest.mark.anyio
async def test_exercicio_de_um_personal_nao_aparece_para_o_outro(ac: AsyncClient, como_usuario):
    criado = await _exercicio(ac, "Meu Exercício")
    assert criado["trainer_id"] == TRAINER_A.id
    assert "Meu Exercício" in [e["nome"] for e in (await ac.get("/exercicios/")).json()]

    como_usuario(TRAINER_B)
    assert "Meu Exercício" not in [e["nome"] for e in (await ac.get("/exercicios/")).json()]


@pytest.mark.anyio
async def test_nome_de_exercicio_por_escopo(ac: AsyncClient, como_usuario, db):
    db.add(models.Exercicio(nome="Supino Base", grupo_muscular="Peito", trainer_id=None))
    await db.commit()

    await _exercicio(ac, "Rosca Minha")
    como_usuario(TRAINER_B)
    await _exercicio(ac, "Rosca Minha")  # mesmo nome em outro personal: ok

    como_usuario(TRAINER_A)
    res = await ac.post("/exercicios/", json={"nome": "supino base", "grupo_muscular": "Peito"})
    assert res.status_code == 409, res.text
    dup = await ac.post("/exercicios/", json={"nome": "ROSCA MINHA", "grupo_muscular": "Peito"})
    assert dup.status_code == 409, dup.text


@pytest.mark.anyio
async def test_prescrever_exercicio_de_outro_personal_e_recusado(ac: AsyncClient, como_usuario):
    ex = await _exercicio(ac, "Exercício do A")
    como_usuario(TRAINER_B)
    aluno_id = await _aluno(ac)

    para_aluno = await ac.post(f"/alunos/{aluno_id}/planos", json=_plano(exercicio_id=ex["id"]))
    assert para_aluno.status_code == 409, para_aluno.text
    modelo = await ac.post("/planos/templates", json=_plano(exercicio_id=ex["id"]))
    assert modelo.status_code == 409, modelo.text

    # edição também valida
    ok = await _modelo(ac)
    edit = await ac.patch(f"/planos/{ok}", json={"treinos": _plano(exercicio_id=ex["id"])["treinos"]})
    assert edit.status_code == 409, edit.text


@pytest.mark.anyio
async def test_seed_nao_mexe_em_exercicio_de_personal(ac: AsyncClient, db):
    db.add(models.Exercicio(nome="leg press 45º", grupo_muscular="Pernas", trainer_id=TRAINER_A.id))
    await db.commit()

    assert (await ac.post("/exercicios/seed")).status_code == 201

    lista = (await ac.get("/exercicios/")).json()
    proprio = [e for e in lista if e["trainer_id"] == TRAINER_A.id]
    assert [(e["nome"], e["grupo_muscular"]) for e in proprio] == [("leg press 45º", "Pernas")]
    base = [e for e in lista if e["nome"] == "Leg Press 45º"]
    assert len(base) == 1 and base[0]["trainer_id"] is None


@pytest.mark.anyio
async def test_patch_reenviando_exercicio_que_ja_estava_no_plano(ac: AsyncClient, como_usuario, db):
    ex_a = models.Exercicio(nome="Do A", grupo_muscular="Peito", trainer_id=TRAINER_A.id)
    ex_a2 = models.Exercicio(nome="Do A 2", grupo_muscular="Peito", trainer_id=TRAINER_A.id)
    aluno = models.Aluno(nome="Aluno B", trainer_id=TRAINER_B.id)
    db.add_all([ex_a, ex_a2, aluno])
    await db.flush()
    plano = models.PlanoTreino(aluno_id=aluno.id, titulo="Antigo", duracao_semanas=4)
    plano.treinos = [models.Treino(nome="A", prescricoes=[models.Prescricao(exercicio_id=ex_a.id, series=3, repeticoes="10")])]
    db.add(plano)
    await db.commit()

    como_usuario(TRAINER_B)
    treinos = _plano(exercicio_id=ex_a.id)["treinos"]
    ok = await ac.patch(f"/planos/{plano.id}", json={"titulo": "Novo", "treinos": treinos})
    assert ok.status_code == 200, ok.text

    treinos[0]["prescricoes"].append({"exercicio_id": ex_a2.id, "series": 3, "repeticoes": "10"})
    nok = await ac.patch(f"/planos/{plano.id}", json={"treinos": treinos})
    assert nok.status_code == 409, nok.text


@pytest.mark.anyio
async def test_clonar_plano_de_aluno_de_outro_personal_e_404(ac: AsyncClient, como_usuario, db):
    aluno = models.Aluno(nome="Aluno A", trainer_id=TRAINER_A.id)
    db.add(aluno)
    await db.flush()
    plano = models.PlanoTreino(aluno_id=aluno.id, titulo="Do aluno A", duracao_semanas=4)
    db.add(plano)
    await db.commit()

    como_usuario(TRAINER_B)
    res = await ac.post(f"/planos/{plano.id}/clonar")
    assert res.status_code == 404, res.text


@pytest.mark.anyio
async def test_modelo_da_plataforma_so_aceita_exercicio_da_base(ac: AsyncClient, como_usuario, db):
    de_personal = models.Exercicio(nome="Do A", grupo_muscular="Peito", trainer_id=TRAINER_A.id)
    da_base = models.Exercicio(nome="Da base", grupo_muscular="Peito", trainer_id=None)
    db.add_all([de_personal, da_base])
    await db.commit()

    como_usuario(ADMIN)
    nok = await ac.post("/planos/templates", json=_plano(exercicio_id=de_personal.id))
    assert nok.status_code == 409, nok.text
    ok = await ac.post("/planos/templates", json=_plano(exercicio_id=da_base.id))
    assert ok.status_code == 201, ok.text
