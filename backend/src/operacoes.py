"""Consultas da tela Operações do admin: uso dos personais e dos alunos deles."""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src import consultoria, exceptions, financeiro_personal, models, schemas


def _dict(rows) -> dict:
    return {chave: valor for chave, valor in rows}


def _corte_7_dias(agora: datetime | None = None) -> datetime:
    return consultoria.agora(agora) - timedelta(days=7)


async def listar_personais(db: AsyncSession) -> list[schemas.PersonalOperacoes]:
    """Personais e admins, com alunos e treinos dos últimos 7 dias."""
    usuarios = (await db.scalars(
        select(models.Usuario)
        .where(models.Usuario.role.in_(("trainer", "admin")))
        .order_by(models.Usuario.username)
    )).all()
    ids = [u.id for u in usuarios]
    if not ids:
        return []

    totais = _dict((await db.execute(
        select(models.Aluno.trainer_id, func.count(models.Aluno.id))
        .where(models.Aluno.trainer_id.in_(ids))
        .group_by(models.Aluno.trainer_id)
    )).all())

    # O admin só entra se tiver alunos próprios; contas de admin sem alunos não são personais.
    usuarios = [u for u in usuarios if u.role != "admin" or totais.get(u.id, 0) > 0]
    ids = [u.id for u in usuarios]
    if not ids:
        return []

    ativos = _dict((await db.execute(
        select(models.Aluno.trainer_id, func.count(models.Aluno.id))
        .where(models.Aluno.trainer_id.in_(ids), models.Aluno.status == "ativo")
        .group_by(models.Aluno.trainer_id)
    )).all())

    corte = _corte_7_dias()
    treinos_7d = _dict((await db.execute(
        select(models.Aluno.trainer_id, func.count(models.SessaoTreino.id))
        .join(models.SessaoTreino, models.SessaoTreino.aluno_id == models.Aluno.id)
        .where(
            models.Aluno.trainer_id.in_(ids),
            models.SessaoTreino.realizada.is_(True),
            models.SessaoTreino.data_hora >= corte,
        )
        .group_by(models.Aluno.trainer_id)
    )).all())
    ultimo_treino = _dict((await db.execute(
        select(models.Aluno.trainer_id, func.max(models.SessaoTreino.data_hora))
        .join(models.SessaoTreino, models.SessaoTreino.aluno_id == models.Aluno.id)
        .where(models.Aluno.trainer_id.in_(ids), models.SessaoTreino.realizada.is_(True))
        .group_by(models.Aluno.trainer_id)
    )).all())
    financeiro = await financeiro_personal.situacoes_por_trainer(db)

    return [
        schemas.PersonalOperacoes(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role,
            is_active=bool(u.is_active),
            data_criacao=u.data_criacao,
            ultimo_acesso=u.ultimo_acesso,
            alunos_ativos=ativos.get(u.id, 0),
            alunos_total=totais.get(u.id, 0),
            treinos_7d=treinos_7d.get(u.id, 0),
            ultimo_treino=ultimo_treino.get(u.id),
            situacao_mensalidade=financeiro[u.id].situacao if u.id in financeiro else "sem_plano",
            dias_atraso=financeiro[u.id].dias_atraso if u.id in financeiro else 0,
            valor_mensal=financeiro[u.id].valor_mensal if u.id in financeiro else None,
            dia_vencimento=financeiro[u.id].dia_vencimento if u.id in financeiro else None,
        )
        for u in usuarios
    ]


async def alunos_do_personal(db: AsyncSession, personal_id: int) -> list[schemas.AlunoOperacoes]:
    if await db.get(models.Usuario, personal_id) is None:
        raise exceptions.ResourceNotFoundError(f"Personal {personal_id} não encontrado")

    alunos = (await db.scalars(
        select(models.Aluno)
        .where(models.Aluno.trainer_id == personal_id)
        .options(selectinload(models.Aluno.usuario))
        .order_by(models.Aluno.nome)
    )).all()
    ids = [a.id for a in alunos]
    if not ids:
        return []

    corte = _corte_7_dias()
    treinos_7d = _dict((await db.execute(
        select(models.SessaoTreino.aluno_id, func.count(models.SessaoTreino.id))
        .where(
            models.SessaoTreino.aluno_id.in_(ids),
            models.SessaoTreino.realizada.is_(True),
            models.SessaoTreino.data_hora >= corte,
        )
        .group_by(models.SessaoTreino.aluno_id)
    )).all())
    ultimo_treino = _dict((await db.execute(
        select(models.SessaoTreino.aluno_id, func.max(models.SessaoTreino.data_hora))
        .where(models.SessaoTreino.aluno_id.in_(ids), models.SessaoTreino.realizada.is_(True))
        .group_by(models.SessaoTreino.aluno_id)
    )).all())

    return [
        schemas.AlunoOperacoes(
            id=a.id,
            nome=a.nome,
            status=a.status or "ativo",
            modalidade=a.modalidade or "presencial",
            tem_login=a.usuario is not None,
            ultimo_acesso=a.usuario.ultimo_acesso if a.usuario else None,
            ultimo_treino=ultimo_treino.get(a.id),
            treinos_7d=treinos_7d.get(a.id, 0),
        )
        for a in alunos
    ]


async def ultimas_sessoes(
    db: AsyncSession, aluno_id: int, limite: int = 20
) -> list[schemas.SessaoOperacoes]:
    if await db.get(models.Aluno, aluno_id) is None:
        raise exceptions.ResourceNotFoundError(f"Aluno {aluno_id} não encontrado")

    rows = (await db.execute(
        select(models.SessaoTreino, models.Treino.nome)
        .outerjoin(models.Treino, models.SessaoTreino.treino_id == models.Treino.id)
        .where(models.SessaoTreino.aluno_id == aluno_id)
        .order_by(models.SessaoTreino.data_hora.desc(), models.SessaoTreino.id.desc())
        .limit(limite)
    )).all()

    return [
        schemas.SessaoOperacoes(
            id=sessao.id,
            data_hora=sessao.data_hora,
            treino_id=sessao.treino_id,
            treino_nome=treino_nome,
            realizada=bool(sessao.realizada),
            tipo_atividade=sessao.tipo_atividade,
            registrado_por=sessao.registrado_por,
            observacoes_performance=sessao.observacoes_performance,
            motivo_ausencia=sessao.motivo_ausencia,
        )
        for sessao, treino_nome in rows
    ]


async def definir_ativo(
    db: AsyncSession, usuario_id: int, ativo: bool, solicitante_id: int
) -> models.Usuario:
    usuario = await db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise exceptions.ResourceNotFoundError(f"Usuário {usuario_id} não encontrado")

    if usuario.id == solicitante_id and not ativo:
        raise exceptions.BusinessRuleError("Você não pode desativar a própria conta.")

    if not ativo and usuario.role == "admin":
        outros_admins = await db.scalar(
            select(func.count(models.Usuario.id)).where(
                models.Usuario.role == "admin",
                models.Usuario.is_active.is_(True),
                models.Usuario.id != usuario.id,
            )
        )
        if not outros_admins:
            raise exceptions.BusinessRuleError("O sistema precisa de ao menos um admin ativo.")

    usuario.is_active = ativo
    try:
        await db.commit()
        await db.refresh(usuario)
        return usuario
    except Exception:
        await db.rollback()
        raise
