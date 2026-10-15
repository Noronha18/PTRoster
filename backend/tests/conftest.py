import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from src.api import app
from src.database import Base, get_db
from src import models  # noqa: F401 — registra os models no metadata

# Banco de teste isolado: SQLite em memória compartilhado entre conexões
engine_teste = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SessionTeste = async_sessionmaker(bind=engine_teste, class_=AsyncSession, expire_on_commit=False)


async def _get_db_teste():
    async with SessionTeste() as session:
        yield session


app.dependency_overrides[get_db] = _get_db_teste


@pytest.fixture(autouse=True)
async def _banco_limpo():
    """Cria o schema antes de cada teste e derruba depois — testes independentes."""
    async with engine_teste.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_teste.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


from httpx import AsyncClient, ASGITransport  # noqa: E402
from src.security import get_current_user  # noqa: E402

TRAINER_A = models.Usuario(id=1, username="trainer_a", role="trainer")
TRAINER_B = models.Usuario(id=2, username="trainer_b", role="trainer")


@pytest.fixture
def como_usuario():
    """Troca o usuário autenticado durante o teste e restaura ao final."""
    anterior = app.dependency_overrides.get(get_current_user)

    def _trocar(user):
        async def _override():
            return user
        app.dependency_overrides[get_current_user] = _override

    yield _trocar

    if anterior is not None:
        app.dependency_overrides[get_current_user] = anterior
    else:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ac(como_usuario):
    como_usuario(TRAINER_A)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
