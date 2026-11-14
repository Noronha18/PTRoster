from datetime import date

import pytest

from src import consultoria, financeiro_personal, models
from src.security import get_password_hash

ADMIN = models.Usuario(id=99, username="admin_teste", email="admin@teste", role="admin", is_active=True)
TRAINER_A = models.Usuario(id=1, username="trainer_a", email="a@teste", role="trainer", is_active=True)


async def _trainer(db, id, username):
    usuario = models.Usuario(
        id=id,
        username=username,
        email=f"{username}@teste",
        hashed_password=get_password_hash("segredo123"),
        role="trainer",
        is_active=True,
    )
    db.add(usuario)
    await db.commit()
    return usuario


async def _plano(db, trainer_id, valor=100.0, dia=10, ativo=True):
    plano = models.PlanoPersonal(
        trainer_id=trainer_id,
        valor_mensal=valor,
        dia_vencimento=dia,
        ativo=ativo,
        inicio=date(2026, 3, 1),
    )
    db.add(plano)
    await db.commit()
    return plano


async def _pagamento(db, trainer_id, referencia, valor=100.0, data=date(2026, 3, 5)):
    pagamento = models.PagamentoPersonal(
        trainer_id=trainer_id,
        referencia_mes=referencia,
        valor=valor,
        data_pagamento=data,
    )
    db.add(pagamento)
    await db.commit()
    return pagamento


@pytest.mark.anyio
async def test_calcular_situacao_cobre_janelas_e_fim_do_mes():
    plano = models.PlanoPersonal(
        trainer_id=1, valor_mensal=100, dia_vencimento=10, ativo=True, inicio=date(2026, 3, 1)
    )

    assert financeiro_personal.calcular_situacao(plano, {}, date(2026, 3, 1)) == ("em_aberto", 0)
    assert financeiro_personal.calcular_situacao(plano, {}, date(2026, 3, 7)) == ("vence_em_breve", 0)
    assert financeiro_personal.calcular_situacao(plano, {}, date(2026, 3, 10)) == ("vence_em_breve", 0)
    assert financeiro_personal.calcular_situacao(plano, {}, date(2026, 3, 11)) == ("atrasada", 1)
    assert financeiro_personal.calcular_situacao(plano, {"03/2026": date(2026, 3, 5)}, date(2026, 3, 11)) == ("em_dia", 0)
    assert financeiro_personal.calcular_situacao(None, {}, date(2026, 3, 11)) == ("sem_plano", 0)

    plano.ativo = False
    assert financeiro_personal.calcular_situacao(plano, {}, date(2026, 3, 11)) == ("sem_plano", 0)

    plano.ativo = True
    plano.dia_vencimento = 31
    plano.inicio = date(2026, 2, 1)
    assert financeiro_personal.calcular_situacao(plano, {}, date(2026, 2, 28)) == ("vence_em_breve", 0)
    assert financeiro_personal.calcular_situacao(plano, {"02/2026": date(2026, 2, 20)}, date(2026, 3, 31)) == ("vence_em_breve", 0)
    # Março em aberto continua atrasado em abril, mesmo com abril ainda no começo.
    assert financeiro_personal.calcular_situacao(plano, {"02/2026": date(2026, 2, 20)}, date(2026, 4, 2)) == ("atrasada", 2)


@pytest.mark.anyio
async def test_resumo_separa_pago_em_aberto_atrasado_e_sem_plano(db):
    await _trainer(db, 1, "trainer_pago")
    await _trainer(db, 2, "trainer_pendente")
    await _trainer(db, 3, "trainer_sem_plano")
    await _trainer(db, 4, "trainer_novo")
    await _plano(db, 1, valor=100, dia=10)
    await _plano(db, 2, valor=200, dia=12)
    await _plano(db, 4, valor=50, dia=25)
    await _pagamento(db, 1, "03/2026", valor=100, data=date(2026, 3, 5))

    resumo = await financeiro_personal.resumo(db, hoje=date(2026, 3, 9))
    por_id = {p.trainer_id: p for p in resumo.personais}

    assert resumo.referencia_mes == "03/2026"
    assert resumo.receita_prevista == 350
    assert resumo.recebido_mes == 100
    assert resumo.quantidade_em_dia == 1
    assert resumo.quantidade_vence_em_breve == 1  # dia 12, faltam 3
    assert resumo.quantidade_em_aberto == 1  # dia 25
    assert resumo.quantidade_sem_plano == 1
    assert por_id[1].situacao == "em_dia" and por_id[1].pago_em == date(2026, 3, 5)
    assert por_id[2].situacao == "vence_em_breve"
    assert por_id[3].situacao == "sem_plano"
    assert por_id[4].situacao == "em_aberto"


@pytest.mark.anyio
async def test_endpoints_de_plano_e_pagamento_do_personal(ac, como_usuario, db):
    await _trainer(db, 1, "trainer_a")
    como_usuario(ADMIN)
    inicio_mes = consultoria.hoje().replace(day=1).isoformat()

    resumo_inicial = await ac.get("/admin/financeiro/personais")
    assert resumo_inicial.status_code == 200, resumo_inicial.text
    assert resumo_inicial.json()["personais"][0]["situacao"] == "sem_plano"

    plano = await ac.put("/admin/financeiro/personais/1/plano", json={
        "valor_mensal": 149.9,
        "dia_vencimento": 10,
        "ativo": True,
        "inicio": inicio_mes,
        "observacao": "Plano inicial",
    })
    assert plano.status_code == 200, plano.text
    assert plano.json()["valor_mensal"] == 149.9

    lido = await ac.get("/admin/financeiro/personais/1/plano")
    assert lido.json()["dia_vencimento"] == 10

    ref = financeiro_personal.referencia_mes()
    pagamento = await ac.post("/admin/financeiro/personais/1/pagamentos", json={
        "referencia_mes": ref,
        "valor": 149.9,
        "forma_pagamento": "PIX",
    })
    assert pagamento.status_code == 201, pagamento.text
    assert pagamento.json()["trainer_id"] == 1

    pagamentos = await ac.get("/admin/financeiro/personais/1/pagamentos")
    assert pagamentos.status_code == 200
    assert len(pagamentos.json()) == 1

    resumo = await ac.get("/admin/financeiro/personais")
    dados = resumo.json()
    assert dados["recebido_mes"] == 149.9
    assert dados["quantidade_em_dia"] == 1
    assert dados["personais"][0]["situacao"] == "em_dia"

    operacoes = await ac.get("/admin/operacoes/personais")
    linha = next(p for p in operacoes.json() if p["id"] == 1)
    assert linha["situacao_mensalidade"] == "em_dia"
    assert linha["valor_mensal"] == 149.9


@pytest.mark.anyio
async def test_cadastro_de_personal_ja_cria_o_plano(ac, como_usuario, db):
    como_usuario(ADMIN)
    res = await ac.post("/admin/trainers", json={
        "username": "novo_personal",
        "email": "novo@teste",
        "password": "segredo123",
        "valor_mensal": 199.9,
        "dia_vencimento": 15,
    })
    assert res.status_code == 201, res.text

    plano = await ac.get(f"/admin/financeiro/personais/{res.json()['id']}/plano")
    assert plano.status_code == 200, plano.text
    assert plano.json()["valor_mensal"] == 199.9
    assert plano.json()["dia_vencimento"] == 15


@pytest.mark.anyio
async def test_endpoints_financeiros_exigem_admin_e_validam_entrada(ac, como_usuario, db):
    await _trainer(db, 1, "trainer_a")
    como_usuario(TRAINER_A)
    assert (await ac.get("/admin/financeiro/personais")).status_code == 403

    como_usuario(ADMIN)
    assert (await ac.get("/admin/financeiro/personais/999/plano")).status_code == 404
    assert (await ac.put("/admin/financeiro/personais/999/plano", json={
        "valor_mensal": 100, "dia_vencimento": 10,
    })).status_code == 404

    assert (await ac.put("/admin/financeiro/personais/1/plano", json={
        "valor_mensal": 100, "dia_vencimento": 32,
    })).status_code == 422
    assert (await ac.post("/admin/financeiro/personais/1/pagamentos", json={
        "referencia_mes": "13/2026", "valor": 100,
    })).status_code == 422
