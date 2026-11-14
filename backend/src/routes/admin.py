from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src import controllers, schemas, database, operacoes
from src.security import get_current_admin

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("/usuarios", response_model=list[schemas.UsuarioAdminPublic])
async def listar_usuarios(db: AsyncSession = Depends(database.get_db)):
    return await controllers.listar_todos_usuarios(db)


@router.get("/operacoes/personais", response_model=list[schemas.PersonalOperacoes])
async def listar_personais_operacoes(db: AsyncSession = Depends(database.get_db)):
    return await operacoes.listar_personais(db)


@router.get("/operacoes/personais/{personal_id}/alunos", response_model=list[schemas.AlunoOperacoes])
async def listar_alunos_do_personal(
    personal_id: int,
    db: AsyncSession = Depends(database.get_db),
):
    return await operacoes.alunos_do_personal(db, personal_id)


@router.get("/operacoes/alunos/{aluno_id}/sessoes", response_model=list[schemas.SessaoOperacoes])
async def listar_sessoes_do_aluno(
    aluno_id: int,
    limite: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(database.get_db),
):
    return await operacoes.ultimas_sessoes(db, aluno_id, limite)


@router.patch("/usuarios/{usuario_id}/ativo", response_model=schemas.UsuarioAdminPublic)
async def definir_ativo_usuario(
    usuario_id: int,
    payload: schemas.UsuarioAtivoUpdate,
    db: AsyncSession = Depends(database.get_db),
    current_user=Depends(get_current_admin),
):
    return await operacoes.definir_ativo(db, usuario_id, payload.ativo, current_user.id)


@router.post("/trainers", response_model=schemas.UsuarioAdminPublic, status_code=201)
async def criar_trainer(
    trainer: schemas.TrainerCreate,
    db: AsyncSession = Depends(database.get_db),
):
    return await controllers.criar_trainer(db, trainer)


@router.post("/usuarios/{usuario_id}/verificar-senha", response_model=schemas.VerificarSenhaResponse)
async def verificar_senha(
    usuario_id: int,
    payload: schemas.VerificarSenhaRequest,
    db: AsyncSession = Depends(database.get_db),
):
    valida = await controllers.verificar_senha_usuario(db, usuario_id, payload.senha)
    return schemas.VerificarSenhaResponse(valida=valida)


@router.patch("/usuarios/{usuario_id}/senha", response_model=schemas.UsuarioAdminPublic)
async def resetar_senha(
    usuario_id: int,
    payload: schemas.SenhaResetRequest,
    db: AsyncSession = Depends(database.get_db),
):
    return await controllers.resetar_senha_usuario(db, usuario_id, payload.nova_senha)
