from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src import schemas, controllers
from src.database import get_db
from src.models import Usuario
from src.security import get_current_user
from src.consultoria import exigir_acesso_treino

router = APIRouter(tags=["Prescrições"], dependencies=[Depends(exigir_acesso_treino)])


@router.patch("/prescricoes/{prescricao_id}/carga", response_model=schemas.PrescricaoPublic)
async def atualizar_carga(
    prescricao_id: int,
    carga_in: schemas.PrescricaoCargarUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.aluno_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas alunos vinculados podem atualizar a carga.",
        )
    return await controllers.atualizar_carga_prescricao(
        db=db,
        prescricao_id=prescricao_id,
        nova_carga=carga_in.carga or None,
        aluno_id=current_user.aluno_id,
    )
