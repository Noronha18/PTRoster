from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src import controllers, schemas, database, video_personal
from src.seed_exercicios import seed
from src.models import Usuario
from src.security import get_current_trainer, resolve_tenant_filter

router = APIRouter(
    prefix="/exercicios",
    tags=["Biblioteca de Exercícios"],
    dependencies=[Depends(get_current_trainer)]
)

@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed_exercicios(db: AsyncSession = Depends(database.get_db)):
    """
    Popula a biblioteca de exercícios com a lista base.
    Utilize este endpoint se não tiver acesso ao terminal do servidor.
    """
    count = await seed(db)
    return {"message": f"Biblioteca atualizada com sucesso! {count} exercícios adicionados ou com vídeo preenchido."}

@router.get("/", response_model=list[schemas.ExercicioPublic])
async def listar_exercicios(
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    trainer_id = resolve_tenant_filter(current_user)
    exercicios = await controllers.listar_exercicios(db=db, trainer_id=trainer_id)
    return await video_personal.exercicios_efetivos(db, exercicios, trainer_id)

@router.post("/", response_model=schemas.ExercicioPublic, status_code=status.HTTP_201_CREATED)
async def criar_exercicio(
    exercicio: schemas.ExercicioCreate,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    return await controllers.criar_exercicio(
        db=db, exercicio_in=exercicio, trainer_id=resolve_tenant_filter(current_user)
    )


@router.put("/{exercicio_id}/video", response_model=schemas.ExercicioPublic)
async def definir_video_exercicio(
    exercicio_id: int,
    corpo: schemas.VideoUpdate,
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(database.get_db)
):
    return await video_personal.definir_video(
        db, exercicio_id, corpo.video_url, resolve_tenant_filter(current_user)
    )
