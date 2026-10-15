"""Regras da modalidade consultoria: vencimento, trava de acesso e avisos."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.database import get_db
from src.security import get_current_user

JANELA_AVISO_DIAS = 7
CODIGO_CONSULTORIA_VENCIDA = "consultoria_vencida"
# ponytail: offset fixo UTC-3 (Brasil sem horário de verão desde 2019); ZoneInfo se voltar a ter
FUSO_BRASILIA = timezone(timedelta(hours=-3))


def hoje(agora: datetime | None = None) -> date:
    """Data atual em Brasília. O servidor roda em UTC, e date.today() vira o dia às 21h."""
    return (agora or datetime.now(timezone.utc)).astimezone(FUSO_BRASILIA).date()


def agora(instante: datetime | None = None) -> datetime:
    """Data e hora de Brasília sem fuso: as colunas DateTime do banco são naive."""
    return (instante or datetime.now(timezone.utc)).astimezone(FUSO_BRASILIA).replace(tzinfo=None)


def fim_programa(plano: models.PlanoTreino) -> date:
    return plano.data_inicio + timedelta(weeks=plano.duracao_semanas or 0)


def plano_vigente(planos: Iterable[models.PlanoTreino]) -> models.PlanoTreino | None:
    """Plano ativo mais recente. Defensivo contra dado legado com mais de um plano ativo."""
    ativos = [p for p in planos if p.esta_ativo]
    return max(ativos, key=lambda p: (p.data_inicio, p.id), default=None)


def consultoria_em_dia(aluno: models.Aluno, hoje: date) -> bool:
    return aluno.data_vencimento_consultoria is not None and aluno.data_vencimento_consultoria >= hoje


def acesso_bloqueado(aluno: models.Aluno, hoje: date) -> bool:
    vencimento = aluno.data_vencimento_consultoria
    return (
        aluno.modalidade == "consultoria"
        and bool(aluno.bloquear_apos_vencimento)
        and vencimento is not None
        and vencimento < hoje
    )


def preencher_avisos(aluno: models.Aluno, hoje: date) -> None:
    """Preenche os atributos auxiliares da view. Exige aluno.planos_treino carregado."""
    aluno.acesso_bloqueado = acesso_bloqueado(aluno, hoje)
    vencimento = aluno.data_vencimento_consultoria
    aluno.dias_para_vencimento_consultoria = (
        (vencimento - hoje).days if aluno.modalidade == "consultoria" and vencimento else None
    )
    plano = plano_vigente(aluno.planos_treino)
    aluno.dias_para_fim_programa = (fim_programa(plano) - hoje).days if plano else None


async def exigir_acesso_treino(
    current_user: models.Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Barra o aluno com consultoria vencida e trava ativa. Trainer/admin passam direto."""
    if current_user.role in ("trainer", "admin") or not current_user.aluno_id:
        return
    aluno = await db.get(models.Aluno, current_user.aluno_id)
    if aluno and acesso_bloqueado(aluno, hoje()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=CODIGO_CONSULTORIA_VENCIDA)
