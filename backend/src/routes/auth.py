from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_db
from src.models import Usuario
from src.security import verify_password, create_access_token
from src import schemas, consultoria

router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    # Busca usuário no banco
    result = await db.execute(select(Usuario).where(Usuario.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada. Fale com o administrador.",
        )

    # Registra o acesso antes de emitir o token; a tela Operações usa esse instante.
    user.ultimo_acesso = consultoria.agora()
    await db.commit()

    token_data = {"sub": user.username, "role": user.role}
    if user.aluno_id:
        token_data["aluno_id"] = user.aluno_id

    access_token = create_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}