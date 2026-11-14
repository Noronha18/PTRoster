from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src import schemas, controllers, video_personal
from src.database import get_db
from src.models import Usuario
from src.security import get_current_trainer, resolve_tenant_filter

router = APIRouter(
    tags=["Planos de Treino"],
    dependencies=[Depends(get_current_trainer)]
)


@router.post("/alunos/{aluno_id}/planos", response_model=schemas.PlanoTreinoPublic, status_code=status.HTTP_201_CREATED)
async def criar_plano_para_aluno(
    aluno_id: int,
    plano_in: schemas.PlanoTreinoCreate,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db)
):
    plano = await controllers.criar_plano_treino(
        db=db, aluno_id=aluno_id, plano_in=plano_in,
        trainer_id=resolve_tenant_filter(current_user)
    )
    return (await video_personal.planos_efetivos(db, [plano], resolve_tenant_filter(current_user)))[0]


@router.get("/planos/templates", response_model=list[schemas.PlanoTreinoPublic])
async def listar_templates(
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db)
):
    trainer_id = resolve_tenant_filter(current_user)
    modelos = await controllers.listar_templates_globais(db=db, trainer_id=trainer_id)
    return await video_personal.planos_efetivos(db, modelos, trainer_id)


@router.post("/planos/templates", response_model=schemas.PlanoTreinoPublic, status_code=status.HTTP_201_CREATED)
async def criar_template_global(
    plano_in: schemas.PlanoTreinoCreate,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db)
):
    plano = await controllers.criar_plano_treino(
        db=db, aluno_id=None, plano_in=plano_in,
        trainer_id=resolve_tenant_filter(current_user)
    )
    return (await video_personal.planos_efetivos(db, [plano], resolve_tenant_filter(current_user)))[0]


@router.delete("/planos/{plano_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_plano(
    plano_id: int,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db)
):
    await controllers.deletar_plano_treino(
        db=db, plano_id=plano_id,
        trainer_id=resolve_tenant_filter(current_user)
    )


@router.post("/planos/{plano_id}/clonar", response_model=schemas.PlanoTreinoPublic)
async def clonar_plano(
    plano_id: int,
    aluno_id: int | None = None,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db)
):
    plano = await controllers.clonar_plano_treino(
        db=db, plano_origem_id=plano_id, novo_aluno_id=aluno_id,
        trainer_id=resolve_tenant_filter(current_user)
    )
    return (await video_personal.planos_efetivos(db, [plano], resolve_tenant_filter(current_user)))[0]


@router.patch("/planos/{plano_id}", response_model=schemas.PlanoTreinoPublic)
async def atualizar_plano(
    plano_id: int,
    plano_up: schemas.PlanoTreinoUpdate,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db)
):
    plano = await controllers.atualizar_plano_treino(
        db=db, plano_id=plano_id, payload=plano_up,
        trainer_id=resolve_tenant_filter(current_user)
    )
    return (await video_personal.planos_efetivos(db, [plano], resolve_tenant_filter(current_user)))[0]
