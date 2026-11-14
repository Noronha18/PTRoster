import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src import models

TRAINER_A = models.Usuario(id=1, username="trainer_a", role="trainer")
TRAINER_B = models.Usuario(id=2, username="trainer_b", role="trainer")
ADMIN = models.Usuario(id=99, username="admin_teste", role="admin")

ORIGINAL = "https://youtu.be/original"
NOVO = "https://youtu.be/do-personal"


def _aluno_logado(aluno_id: int) -> models.Usuario:
    return models.Usuario(id=500 + aluno_id, username=f"aluno{aluno_id}", role="aluno", aluno_id=aluno_id)


async def _base(db) -> int:
    ex = models.Exercicio(nome="Supino Base", grupo_muscular="Peito", video_url=ORIGINAL, trainer_id=None)
    db.add(ex)
    await db.commit()
    return ex.id


async def _aluno_com_plano(ac: AsyncClient, ex_id: int) -> int:
    aluno_id = (await ac.post("/alunos/", json={"nome": "Aluno"})).json()["id"]
    plano = {"titulo": "P", "duracao_semanas": 4, "treinos": [
        {"nome": "A", "prescricoes": [{"exercicio_id": ex_id, "series": 3, "repeticoes": "10"}]}]}
    res = await ac.post(f"/alunos/{aluno_id}/planos", json=plano)
    assert res.status_code == 201, res.text
    return aluno_id


async def _video_na_lista(ac, ex_id):
    return next(e for e in (await ac.get("/exercicios/")).json() if e["id"] == ex_id)


async def _put(ac, ex_id, url):
    return await ac.put(f"/exercicios/{ex_id}/video", json={"video_url": url})


@pytest.mark.anyio
async def test_troca_na_base_vale_so_para_quem_trocou(ac: AsyncClient, como_usuario, db):
    ex_id = await _base(db)
    res = await _put(ac, ex_id, NOVO)
    assert res.status_code == 200, res.text
    assert res.json()["video_url"] == NOVO and res.json()["video_proprio"] is True
    assert (await _video_na_lista(ac, ex_id))["video_url"] == NOVO
    como_usuario(TRAINER_B)
    b = await _video_na_lista(ac, ex_id)
    assert b["video_url"] == ORIGINAL and b["video_proprio"] is False


@pytest.mark.anyio
async def test_aluno_ve_video_do_personal_dono(ac: AsyncClient, como_usuario, db):
    ex_id = await _base(db)
    aluno_a = await _aluno_com_plano(ac, ex_id)
    como_usuario(TRAINER_B)
    aluno_b = await _aluno_com_plano(ac, ex_id)
    como_usuario(TRAINER_A)
    await _put(ac, ex_id, NOVO)

    def video(r):
        return r.json()["planos_treino"][0]["treinos"][0]["prescricoes"][0]["exercicio"]["video_url"]

    como_usuario(_aluno_logado(aluno_a))
    assert video(await ac.get("/alunos/me")) == NOVO
    como_usuario(_aluno_logado(aluno_b))
    assert video(await ac.get("/alunos/me")) == ORIGINAL
    como_usuario(TRAINER_A)
    assert video(await ac.get(f"/alunos/{aluno_a}")) == NOVO


@pytest.mark.anyio
async def test_voltar_ao_original_remove_troca(ac: AsyncClient, db):
    ex_id = await _base(db)
    await _put(ac, ex_id, NOVO)
    res = await _put(ac, ex_id, None)
    assert res.json()["video_url"] == ORIGINAL and res.json()["video_proprio"] is False
    assert (await _video_na_lista(ac, ex_id))["video_url"] == ORIGINAL
    assert (await db.execute(select(models.ExercicioVideoPersonal))).scalars().all() == []


@pytest.mark.anyio
async def test_personal_altera_video_do_proprio_exercicio(ac: AsyncClient, db):
    ex = (await ac.post("/exercicios/", json={"nome": "Meu", "grupo_muscular": "Peito", "video_url": ORIGINAL})).json()
    res = await _put(ac, ex["id"], NOVO)
    assert res.json()["video_url"] == NOVO and res.json()["video_proprio"] is True
    await db.rollback()
    assert (await db.get(models.Exercicio, ex["id"])).video_url == NOVO


@pytest.mark.anyio
async def test_exercicio_de_outro_personal_da_404(ac: AsyncClient, como_usuario):
    ex = (await ac.post("/exercicios/", json={"nome": "Do A", "grupo_muscular": "Peito"})).json()
    como_usuario(TRAINER_B)
    assert (await _put(ac, ex["id"], NOVO)).status_code == 404


@pytest.mark.anyio
async def test_admin_altera_original_para_todos(ac: AsyncClient, como_usuario, db):
    ex_id = await _base(db)
    como_usuario(ADMIN)
    res = await _put(ac, ex_id, NOVO)
    assert res.status_code == 200, res.text
    como_usuario(TRAINER_B)
    assert (await _video_na_lista(ac, ex_id))["video_url"] == NOVO


@pytest.mark.anyio
async def test_leitura_com_troca_nao_persiste_no_original(ac: AsyncClient, db):
    ex_id = await _base(db)
    aluno = await _aluno_com_plano(ac, ex_id)
    await _put(ac, ex_id, NOVO)
    await ac.get("/exercicios/")
    await ac.get(f"/alunos/{aluno}")
    await ac.get("/planos/templates")
    await ac.patch(f"/alunos/{aluno}/status", params={"status": "ativo"})  # commit depois de ler
    await db.rollback()
    assert (await db.get(models.Exercicio, ex_id)).video_url == ORIGINAL


@pytest.mark.anyio
@pytest.mark.parametrize("url", ["javascript:alert(1)", "youtube.com/x", "ftp://x.com/v", "https://x.com/" + "a" * 500])
async def test_url_invalida_da_422(ac: AsyncClient, db, url):
    ex_id = await _base(db)
    assert (await _put(ac, ex_id, url)).status_code == 422
