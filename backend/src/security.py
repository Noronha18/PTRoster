import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Union
import jwt
from src.config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_db
from src.models import Usuario
from src.schemas import TokenData

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto puro corresponde ao hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), 
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Gera um hash bcrypt a partir de uma senha em texto puro."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception
    
    result = await db.execute(select(Usuario).where(Usuario.username == token_data.username))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception

    if not user.is_active:
        # 401 para o painel limpar o token e voltar ao login.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Conta desativada. Fale com o administrador.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

async def get_current_trainer(
    current_user: Usuario = Depends(get_current_user)
) -> Usuario:
    if current_user.role not in ("trainer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a Personal Trainers"
        )
    return current_user


async def get_current_admin(
    current_user: Usuario = Depends(get_current_user)
) -> Usuario:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores"
        )
    return current_user


def resolve_tenant_filter(current_user: Usuario) -> int | None:
    """Retorna None para admin (sem filtro) ou o id do trainer para escopo isolado."""
    if current_user.role == "admin":
        return None
    return current_user.id