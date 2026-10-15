from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src import controllers, schemas
from src.database import get_db
from src.models import Usuario
from src.security import get_current_trainer, resolve_tenant_filter

router = APIRouter(prefix="/avisos", tags=["Avisos"], dependencies=[Depends(get_current_trainer)])


@router.get("/", response_model=schemas.AvisosPublic)
async def listar_avisos(
    current_user: Usuario = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.listar_avisos(db, trainer_id=resolve_tenant_filter(current_user))
