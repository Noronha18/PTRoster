import pytest
from sqlalchemy import select

from src import models
from src.create_admin import definir_admin, gerar_senha
from src.security import verify_password

pytestmark = pytest.mark.anyio


async def _admins(db):
    return (await db.execute(select(models.Usuario).where(models.Usuario.role == "admin"))).scalars().all()


async def test_cria_admin_quando_nao_existe(db):
    assert await definir_admin(db, "senha-nova-12") == "admin"
    admins = await _admins(db)
    assert len(admins) == 1
    assert verify_password("senha-nova-12", admins[0].hashed_password)


async def test_troca_senha_do_admin_existente_sem_duplicar(db):
    await definir_admin(db, "admin123")
    await definir_admin(db, "senha-nova-12")
    admins = await _admins(db)
    assert len(admins) == 1
    assert verify_password("senha-nova-12", admins[0].hashed_password)
    assert not verify_password("admin123", admins[0].hashed_password)


async def test_senha_gerada_tem_4_palavras_e_numero():
    partes = gerar_senha().split("-")
    assert len(partes) == 5 and partes[-1].isdigit()
