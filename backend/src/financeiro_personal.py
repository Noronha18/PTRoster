"""Mensalidade que cada personal paga à plataforma."""
from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src import consultoria, exceptions, models, schemas

JANELA_VENCE_EM_BREVE = 3


def referencia_mes(hoje: date | None = None) -> str:
    hoje = hoje or consultoria.hoje()
    return f"{hoje.month:02d}/{hoje.year}"


def _vencimento_no_mes(dia: int, ano: int, mes: int) -> date:
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia, ultimo))


def _meses_ate(inicio: date, hoje: date):
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (hoje.year, hoje.month):
        yield ano, mes
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1


def calcular_situacao(
    plano: models.PlanoPersonal | None,
    pagos: dict[str, date],
    hoje: date,
) -> tuple[str, int]:
    """Situação e dias de atraso, carregando meses anteriores em aberto.

    O primeiro mês sem pagamento desde o início do plano decide: se já venceu,
    fica atrasado mesmo que o mês corrente já tenha sido pago.
    """
    if plano is None or not plano.ativo:
        return "sem_plano", 0

    inicio = plano.inicio or hoje
    if inicio > hoje:
        inicio = hoje

    primeiro_em_aberto = None
    for ano, mes in _meses_ate(inicio, hoje):
        ref = f"{mes:02d}/{ano}"
        if ref not in pagos:
            primeiro_em_aberto = _vencimento_no_mes(plano.dia_vencimento, ano, mes)
            break

    if primeiro_em_aberto is None:
        return "em_dia", 0
    if hoje > primeiro_em_aberto:
        return "atrasada", (hoje - primeiro_em_aberto).days
    if (primeiro_em_aberto - hoje).days <= JANELA_VENCE_EM_BREVE:
        return "vence_em_breve", 0
    return "em_aberto", 0


async def _personal(db: AsyncSession, trainer_id: int) -> models.Usuario:
    usuario = await db.get(models.Usuario, trainer_id)
    if usuario is None or usuario.role != "trainer":
        raise exceptions.ResourceNotFoundError(f"Personal {trainer_id} não encontrado")
    return usuario


async def _pagamentos_por_mes(
    db: AsyncSession, trainer_ids: list[int]
) -> dict[int, dict[str, date]]:
    if not trainer_ids:
        return {}
    rows = (await db.execute(
        select(
            models.PagamentoPersonal.trainer_id,
            models.PagamentoPersonal.referencia_mes,
            models.PagamentoPersonal.data_pagamento,
        ).where(models.PagamentoPersonal.trainer_id.in_(trainer_ids))
    )).all()
    pagos: dict[int, dict[str, date]] = {}
    for trainer_id, ref, data in rows:
        if data is None:
            continue
        do_personal = pagos.setdefault(trainer_id, {})
        if ref not in do_personal or data > do_personal[ref]:
            do_personal[ref] = data
    return pagos


async def situacoes_do_mes(db: AsyncSession, hoje: date | None = None) -> list[schemas.SituacaoFinanceiraPersonal]:
    hoje = hoje or consultoria.hoje()
    ref = referencia_mes(hoje)
    personais = (await db.scalars(
        select(models.Usuario)
        .where(models.Usuario.role == "trainer")
        .order_by(models.Usuario.username)
    )).all()
    if not personais:
        return []

    planos = {
        plano.trainer_id: plano
        for plano in (await db.scalars(select(models.PlanoPersonal))).all()
    }
    pagos = await _pagamentos_por_mes(db, [p.id for p in personais])

    saida = []
    for personal in personais:
        plano = planos.get(personal.id)
        do_personal = pagos.get(personal.id, {})
        situacao, dias_atraso = calcular_situacao(plano, do_personal, hoje)
        saida.append(schemas.SituacaoFinanceiraPersonal(
            trainer_id=personal.id,
            username=personal.username,
            email=personal.email,
            valor_mensal=plano.valor_mensal if plano else None,
            dia_vencimento=plano.dia_vencimento if plano else None,
            ativo=bool(personal.is_active),
            situacao=situacao,
            dias_atraso=dias_atraso,
            pago_em=do_personal.get(ref),
        ))
    return saida


async def situacoes_por_trainer(db: AsyncSession, hoje: date | None = None) -> dict[int, schemas.SituacaoFinanceiraPersonal]:
    return {situacao.trainer_id: situacao for situacao in await situacoes_do_mes(db, hoje)}


async def resumo(db: AsyncSession, hoje: date | None = None) -> schemas.ResumoFinanceiroPersonais:
    hoje = hoje or consultoria.hoje()
    ref = referencia_mes(hoje)
    lista = await situacoes_do_mes(db, hoje)

    recebido = await db.scalar(
        select(func.coalesce(func.sum(models.PagamentoPersonal.valor), 0))
        .where(models.PagamentoPersonal.referencia_mes == ref)
    )
    receita_prevista = sum(s.valor_mensal or 0 for s in lista if s.situacao != "sem_plano")
    atrasados = [s for s in lista if s.situacao == "atrasada"]

    return schemas.ResumoFinanceiroPersonais(
        referencia_mes=ref,
        receita_prevista=receita_prevista,
        recebido_mes=float(recebido or 0),
        valor_em_atraso=sum(s.valor_mensal or 0 for s in atrasados),
        total_personais=len(lista),
        quantidade_em_dia=sum(1 for s in lista if s.situacao == "em_dia"),
        quantidade_vence_em_breve=sum(1 for s in lista if s.situacao == "vence_em_breve"),
        quantidade_em_atraso=len(atrasados),
        quantidade_em_aberto=sum(1 for s in lista if s.situacao == "em_aberto"),
        quantidade_sem_plano=sum(1 for s in lista if s.situacao == "sem_plano"),
        personais=lista,
    )


async def obter_plano(db: AsyncSession, trainer_id: int) -> schemas.PlanoPersonalPublic | None:
    await _personal(db, trainer_id)
    plano = await db.get(models.PlanoPersonal, trainer_id)
    return schemas.PlanoPersonalPublic.model_validate(plano) if plano else None


async def salvar_plano(
    db: AsyncSession, trainer_id: int, dados: schemas.PlanoPersonalUpsert
) -> schemas.PlanoPersonalPublic:
    await _personal(db, trainer_id)
    plano = await db.get(models.PlanoPersonal, trainer_id)
    if plano is None:
        plano = models.PlanoPersonal(
            trainer_id=trainer_id,
            valor_mensal=dados.valor_mensal,
            dia_vencimento=dados.dia_vencimento,
            ativo=dados.ativo,
            inicio=dados.inicio or consultoria.hoje(),
            observacao=dados.observacao,
        )
        db.add(plano)
    else:
        plano.valor_mensal = dados.valor_mensal
        plano.dia_vencimento = dados.dia_vencimento
        plano.ativo = dados.ativo
        plano.inicio = dados.inicio or plano.inicio
        plano.observacao = dados.observacao
    try:
        await db.commit()
        await db.refresh(plano)
        return schemas.PlanoPersonalPublic.model_validate(plano)
    except Exception:
        await db.rollback()
        raise


async def listar_pagamentos(
    db: AsyncSession, trainer_id: int, limite: int = 24
) -> list[schemas.PagamentoPersonalPublic]:
    await _personal(db, trainer_id)
    pagamentos = (await db.scalars(
        select(models.PagamentoPersonal)
        .where(models.PagamentoPersonal.trainer_id == trainer_id)
        .order_by(models.PagamentoPersonal.data_pagamento.desc(), models.PagamentoPersonal.id.desc())
        .limit(limite)
    )).all()
    return [schemas.PagamentoPersonalPublic.model_validate(p) for p in pagamentos]


async def registrar_pagamento(
    db: AsyncSession, trainer_id: int, dados: schemas.PagamentoPersonalCreate
) -> schemas.PagamentoPersonalPublic:
    await _personal(db, trainer_id)
    pagamento = models.PagamentoPersonal(
        trainer_id=trainer_id,
        referencia_mes=dados.referencia_mes,
        valor=dados.valor,
        data_pagamento=dados.data_pagamento or consultoria.hoje(),
        forma_pagamento=dados.forma_pagamento,
        observacao=dados.observacao,
    )
    db.add(pagamento)
    try:
        await db.commit()
        await db.refresh(pagamento)
        return schemas.PagamentoPersonalPublic.model_validate(pagamento)
    except Exception:
        await db.rollback()
        raise
