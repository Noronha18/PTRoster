from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src import controllers, schemas
from src.database import get_db
from src.models import Usuario
from src.security import get_current_trainer, resolve_tenant_filter

router = APIRouter(tags=["Atividade"], dependencies=[Depends(get_current_trainer)])


@router.get("/atividade-recente", response_model=list[schemas.AtividadeRecente])
async def atividade_recente(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.atividade_recente(db, trainer_id=resolve_tenant_filter(current_user), limit=limit)
