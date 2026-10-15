from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src import controllers, schemas
from src.database import get_db
from src.models import Usuario
from src.security import get_current_trainer, get_current_user, resolve_tenant_filter
from src.consultoria import exigir_acesso_treino

router = APIRouter(prefix="/sessoes", tags=["Sessoes"], dependencies=[Depends(exigir_acesso_treino)])


def _validar_acesso_aluno(current_user: Usuario, aluno_id: int) -> None:
    """Alunos só podem acessar dados do seu próprio aluno_id."""
    if current_user.role not in ("trainer", "admin") and current_user.aluno_id != aluno_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: você só pode acessar suas próprias sessões.",
        )


@router.post("/", response_model=schemas.SessaoTreinoPublic, status_code=201)
async def criar_sessao(
    payload: schemas.SessaoTreinoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validar_acesso_aluno(current_user, payload.aluno_id)
    is_staff = current_user.role in ("trainer", "admin")
    trainer_id = resolve_tenant_filter(current_user) if is_staff else None
    return await controllers.registrar_sessao(db, payload, trainer_id=trainer_id, registrado_por_staff=is_staff)


@router.post("/execucao", response_model=schemas.SessaoExecucaoPublic, status_code=201)
async def registrar_execucao(
    payload: schemas.ExecucaoCreate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role in ("trainer", "admin"):
        if payload.aluno_id is None:
            raise HTTPException(status_code=422, detail="Informe o aluno.")
        return await controllers.registrar_execucao(
            db, payload, aluno_id=payload.aluno_id, registrado_por="trainer",
            trainer_id=resolve_tenant_filter(current_user),
        )
    if not current_user.aluno_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não vinculado a um aluno.")
    # aluno_id do payload é ignorado: o aluno só registra para si mesmo
    return await controllers.registrar_execucao(db, payload, aluno_id=current_user.aluno_id, registrado_por="aluno")


@router.get("/", response_model=list[schemas.SessaoTreinoPublic])
async def listar_sessoes(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
    aluno_id: int | None = None,
    de: date | None = None,
    ate: date | None = None,
    realizada: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    # Alunos só veem suas próprias sessões
    if current_user.role not in ("trainer", "admin"):
        if not current_user.aluno_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não vinculado a um aluno.")
        if aluno_id is not None and aluno_id != current_user.aluno_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")
        aluno_id = current_user.aluno_id

    trainer_id = resolve_tenant_filter(current_user) if current_user.role in ("trainer", "admin") else None
    return await controllers.listar_sessoes(
        db=db,
        aluno_id=aluno_id,
        trainer_id=trainer_id,
        de=de,
        ate=ate,
        realizada=realizada,
        limit=limit,
        offset=offset,
    )


@router.get("/frequencia/{aluno_id}", response_model=schemas.FrequenciaMensalPublic)
async def frequencia_mensal(
    aluno_id: int,
    referencia_mes: str | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validar_acesso_aluno(current_user, aluno_id)
    if referencia_mes is None:
        agora = datetime.now()
        referencia_mes = f"{agora.month:02d}/{agora.year}"
    trainer_id = resolve_tenant_filter(current_user) if current_user.role in ("trainer", "admin") else None
    return await controllers.calcular_frequencia_mensal(
        db, aluno_id=aluno_id, referencia_mes=referencia_mes, trainer_id=trainer_id
    )


@router.get("/{sessao_id}", response_model=schemas.SessaoTreinoPublic)
async def buscar_sessao(
    sessao_id: int,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_sessao(db, sessao_id, trainer_id=resolve_tenant_filter(current_user))


@router.delete("/{sessao_id}", status_code=204)
async def deletar_sessao(
    sessao_id: int,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    await controllers.deletar_sessao(db, sessao_id, trainer_id=resolve_tenant_filter(current_user))
    return Response(status_code=204)
