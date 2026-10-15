from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src import controllers, schemas, database
from src.schemas import StatusAluno
from src.models import Usuario
from src.security import get_current_trainer, resolve_tenant_filter

router = APIRouter(
    prefix="/alunos",
    tags=["Alunos"],
    dependencies=[Depends(get_current_trainer)]
)


@router.post("/", response_model=schemas.AlunoPublic, status_code=201)
async def criar_aluno(
    aluno: schemas.AlunoCreate,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    # Admin pode especificar trainer_id no payload; trainer usa o próprio id
    trainer_id = aluno.trainer_id if (current_user.role == "admin" and aluno.trainer_id) else current_user.id
    return await controllers.criar_aluno(db=db, aluno_in=aluno, trainer_id=trainer_id)


@router.get("/", response_model=list[schemas.AlunoResumo])
async def listar_alunos(
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    return await controllers.listar_alunos_ativos(db=db, trainer_id=resolve_tenant_filter(current_user))


@router.get("/{aluno_id}", response_model=schemas.AlunoPublic)
async def obter_aluno(
    aluno_id: int,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    return await controllers.get_aluno(db=db, aluno_id=aluno_id, trainer_id=resolve_tenant_filter(current_user))


@router.patch("/{aluno_id}", response_model=schemas.AlunoPublic)
async def atualizar_aluno(
    aluno_id: int,
    aluno: schemas.AlunoUpdate,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    return await controllers.atualizar_aluno(
        db=db, aluno_id=aluno_id, aluno_up=aluno,
        trainer_id=resolve_tenant_filter(current_user),
        permitir_troca_trainer=(current_user.role == "admin")
    )


@router.patch("/{aluno_id}/status", response_model=schemas.AlunoPublic)
async def atualizar_status_aluno(
    aluno_id: int,
    status: StatusAluno,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    return await controllers.atualizar_status_aluno(
        db=db, aluno_id=aluno_id, novo_status=status,
        trainer_id=resolve_tenant_filter(current_user)
    )


@router.delete("/{aluno_id}", status_code=204)
async def deletar_aluno(
    aluno_id: int,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    await controllers.excluir_aluno(db=db, aluno_id=aluno_id, trainer_id=resolve_tenant_filter(current_user))
    return None


@router.get("/{aluno_id}/ultima-execucao", response_model=list[schemas.UltimaExecucaoExercicio])
async def ultima_execucao(
    aluno_id: int,
    treino_id: int,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    return await controllers.ultima_execucao(
        db, aluno_id=aluno_id, treino_id=treino_id, trainer_id=resolve_tenant_filter(current_user)
    )
