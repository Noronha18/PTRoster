from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src import controllers, schemas, database
from src.models import Usuario
from src.security import get_current_user
from src.consultoria import exigir_acesso_treino

router = APIRouter(tags=["Meu Perfil"])


@router.get("/alunos/me", response_model=schemas.AlunoPublic)
async def meu_perfil(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db),
):
    if not current_user.aluno_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário não vinculado a um aluno.",
        )
    aluno = await controllers.get_aluno(db, current_user.aluno_id)
    if aluno.acesso_bloqueado:
        # Esvazia só a resposta: atribuir [] à relação ORM apagaria os planos (delete-orphan)
        return schemas.AlunoPublic.model_validate(aluno).model_copy(
            update={"planos_treino": [], "sessoes": []}
        )
    return aluno


@router.get(
    "/alunos/me/ultima-execucao",
    response_model=list[schemas.UltimaExecucaoExercicio],
    dependencies=[Depends(exigir_acesso_treino)],
)
async def minha_ultima_execucao(
    treino_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db),
):
    if not current_user.aluno_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não vinculado a um aluno.")
    return await controllers.ultima_execucao(db, aluno_id=current_user.aluno_id, treino_id=treino_id)


@router.get(
    "/alunos/me/semana",
    response_model=schemas.SemanaAlunoPublic,
    dependencies=[Depends(exigir_acesso_treino)],
)
async def minha_semana(
    ref: date | None = None,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db),
):
    if not current_user.aluno_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não vinculado a um aluno.")
    return await controllers.resumo_semana(
        db, current_user.aluno_id, ref=ref, incluir_sugestao=True
    )
