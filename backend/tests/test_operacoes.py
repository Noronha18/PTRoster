from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from src import consultoria, models
from src.security import create_access_token, get_current_user, get_password_hash

ADMIN = models.Usuario(id=99, username="admin_teste", email="admin@teste", role="admin", is_active=True)
TRAINER_A = models.Usuario(id=1, username="trainer_a", email="a@teste", role="trainer", is_active=True)


async def _usuario(db, id, username, role="trainer", ativo=True, ultimo_acesso=None, senha=None):
    usuario = models.Usuario(
        id=id,
        username=username,
        email=f"{username}@teste",
        hashed_password=get_password_hash(senha or "segredo123"),
        role=role,
        is_active=ativo,
        ultimo_acesso=ultimo_acesso,
    )
    db.add(usuario)
    await db.commit()
    return usuario


async def _aluno(db, nome, trainer_id, status="ativo", modalidade="presencial", login=False, ultimo_acesso=None):
    aluno = models.Aluno(nome=nome, trainer_id=trainer_id, status=status, modalidade=modalidade)
    db.add(aluno)
    await db.flush()
    if login:
        db.add(models.Usuario(
            username=f"login_{aluno.id}",
            email=f"login_{aluno.id}@teste",
            hashed_password="x",
            role="aluno",
            is_active=True,
            aluno_id=aluno.id,
            ultimo_acesso=ultimo_acesso,
        ))
    await db.commit()
    return aluno


async def _treino(db, nome="Treino A"):
    treino = models.Treino(nome=nome)
    db.add(treino)
    await db.commit()
    return treino


async def _sessao(db, aluno_id, quando, realizada=True, treino_id=None, tipo_atividade=None):
    sessao = models.SessaoTreino(
        aluno_id=aluno_id,
        data_hora=quando,
        realizada=realizada,
        treino_id=treino_id,
        tipo_atividade=tipo_atividade,
    )
    db.add(sessao)
    await db.commit()
    return sessao


@pytest.mark.anyio
async def test_operacoes_exige_admin(ac, como_usuario):
    como_usuario(TRAINER_A)
    assert (await ac.get("/admin/operacoes/personais")).status_code == 403


@pytest.mark.anyio
async def test_personais_trazem_uso_dos_ultimos_7_dias(ac, como_usuario, db):
    agora = consultoria.agora()
    await _usuario(db, 1, "trainer_a", ultimo_acesso=agora - timedelta(hours=1))
    await _usuario(db, 2, "trainer_b", ultimo_acesso=agora - timedelta(days=10))
    await _usuario(db, 3, "trainer_c", ativo=False)
    await _usuario(db, 99, "admin_teste", role="admin")
    await _usuario(db, 100, "admin_sem_alunos", role="admin")

    aluno_a1 = await _aluno(db, "Aluno A1", 1)
    await _aluno(db, "Aluno A2", 1, status="suspenso")
    aluno_b1 = await _aluno(db, "Aluno B1", 2)
    await _aluno(db, "Aluno do admin", 99)

    await _sessao(db, aluno_a1.id, agora - timedelta(days=2))
    await _sessao(db, aluno_a1.id, agora - timedelta(days=10))
    await _sessao(db, aluno_a1.id, agora - timedelta(days=1), realizada=False)
    await _sessao(db, aluno_b1.id, agora - timedelta(days=3))

    como_usuario(ADMIN)
    res = await ac.get("/admin/operacoes/personais")
    assert res.status_code == 200, res.text
    por_id = {p["id"]: p for p in res.json()}

    a = por_id[1]
    assert a["alunos_total"] == 2 and a["alunos_ativos"] == 1
    assert a["treinos_7d"] == 1
    assert a["ultimo_treino"].startswith((agora - timedelta(days=2)).date().isoformat())
    assert a["ultimo_acesso"] is not None
    assert a["situacao_mensalidade"] == "sem_plano"

    b = por_id[2]
    assert b["alunos_total"] == 1 and b["alunos_ativos"] == 1
    assert b["treinos_7d"] == 1

    c = por_id[3]
    assert c["is_active"] is False and c["alunos_total"] == 0 and c["treinos_7d"] == 0

    # Admin com alunos próprios aparece; admin sem alunos não é personal e não entra.
    assert por_id[99]["role"] == "admin" and por_id[99]["alunos_total"] == 1
    assert 100 not in por_id


@pytest.mark.anyio
async def test_alunos_do_personal_trazem_login_e_ultimo_treino(ac, como_usuario, db):
    agora = consultoria.agora()
    await _usuario(db, 1, "trainer_a")
    aluno = await _aluno(
        db, "Aluno com login", 1, login=True, ultimo_acesso=agora - timedelta(days=1)
    )
    await _sessao(db, aluno.id, agora - timedelta(days=2))

    como_usuario(ADMIN)
    res = await ac.get("/admin/operacoes/personais/1/alunos")
    assert res.status_code == 200, res.text
    linha = res.json()[0]
    assert linha["nome"] == "Aluno com login"
    assert linha["tem_login"] is True
    assert linha["ultimo_acesso"] is not None
    assert linha["treinos_7d"] == 1
    assert linha["ultimo_treino"] is not None
    assert linha["modalidade"] == "presencial"

    assert (await ac.get("/admin/operacoes/personais/999/alunos")).status_code == 404


@pytest.mark.anyio
async def test_sessoes_do_aluno_respeitam_limite_e_ordem(ac, como_usuario, db):
    agora = consultoria.agora()
    await _usuario(db, 1, "trainer_a")
    aluno = await _aluno(db, "Aluno", 1)
    treino = await _treino(db, "Superiores")
    await _sessao(db, aluno.id, agora - timedelta(days=3), treino_id=treino.id)
    await _sessao(db, aluno.id, agora - timedelta(days=1), tipo_atividade="corrida")
    await _sessao(db, aluno.id, agora - timedelta(days=2))

    como_usuario(ADMIN)
    res = await ac.get(f"/admin/operacoes/alunos/{aluno.id}/sessoes?limite=2")
    assert res.status_code == 200, res.text
    sessoes = res.json()
    assert len(sessoes) == 2
    assert sessoes[0]["tipo_atividade"] == "corrida"
    assert sessoes[1]["treino_nome"] is None

    assert (await ac.get(f"/admin/operacoes/alunos/{aluno.id}/sessoes?limite=0")).status_code == 422
    assert (await ac.get("/admin/operacoes/alunos/999/sessoes")).status_code == 404


@pytest.mark.anyio
async def test_desativar_bloqueia_login_e_token_existente(ac, como_usuario, db):
    usuario = await _usuario(db, 10, "trainer_novo", senha="senha-boa")
    token = create_access_token({"sub": usuario.username, "role": usuario.role})

    como_usuario(ADMIN)
    res = await ac.patch("/admin/usuarios/10/ativo", json={"ativo": False})
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False

    login = await ac.post("/auth/token", data={"username": "trainer_novo", "password": "senha-boa"})
    assert login.status_code == 403
    assert "desativada" in login.json()["message"].lower()

    db.expire_all()  # a sessão de teste tem o usuário em cache antes do PATCH
    with pytest.raises(HTTPException) as erro:
        await get_current_user(db=db, token=token)
    assert erro.value.status_code == 401

    # Reativar devolve o acesso e registra o último acesso no login.
    assert (await ac.patch("/admin/usuarios/10/ativo", json={"ativo": True})).status_code == 200
    login = await ac.post("/auth/token", data={"username": "trainer_novo", "password": "senha-boa"})
    assert login.status_code == 200
    db.expire_all()
    atualizado = await db.scalar(select(models.Usuario).where(models.Usuario.id == 10))
    assert atualizado.ultimo_acesso is not None


@pytest.mark.anyio
async def test_admin_nao_desativa_a_propria_conta(ac, como_usuario, db):
    await _usuario(db, 99, "admin_teste", role="admin")
    como_usuario(ADMIN)
    res = await ac.patch("/admin/usuarios/99/ativo", json={"ativo": False})
    assert res.status_code == 409
    assert "própria" in res.json()["message"]
