"""Define o login único de admin: cria o usuário se não existir, ou troca a senha do atual.

Rodar à mão, uma vez, apontando para o banco desejado:
    DATABASE_URL_DIRECT=... SECRET_KEY=... python -m src.create_admin

A senha é gerada aqui (palavras fáceis de lembrar) e aparece só no terminal.
Rode num terminal comum, fora de chats e de logs de deploy, e guarde a senha
num gerenciador de senhas. Nada disso roda na subida do container.
"""
import asyncio
import secrets

from sqlalchemy import select

from src.models import Usuario
from src.security import get_password_hash

USERNAME = "admin"
EMAIL = "admin@personal.com"

# Palavras curtas, sem acento, fáceis de digitar no celular.
PALAVRAS = (
    "treino supino remada agacha prancha barra halter polia corda banco "
    "anilha serie carga ritmo foco forca suor folego pulso salto "
    "corrida trilha praia sol lua mar rio pedra ferro bronze "
    "prata ouro tigre lobo urso aguia falcao touro leao zebra "
    "manga caju coco uva limao pera kiwi amora goiaba acai "
    "verde azul roxo laranja branco preto cinza rosa vinho ambar"
).split()


def gerar_senha() -> str:
    # ponytail: 4 de 60 palavras + 2 dígitos ≈ 1,2 bilhão de combinações; aumente
    # para 5 palavras se o login passar a aceitar muitas tentativas por segundo.
    palavras = [secrets.choice(PALAVRAS) for _ in range(4)]
    return "-".join(palavras) + f"-{secrets.randbelow(90) + 10}"


async def definir_admin(db, senha: str) -> str:
    """Grava a senha no admin existente ou cria o admin. Devolve o username usado."""
    result = await db.execute(
        select(Usuario).where((Usuario.role == "admin") | (Usuario.username == USERNAME))
    )
    admin = result.scalars().first()
    if admin is None:
        admin = Usuario(username=USERNAME, email=EMAIL, role="admin", is_active=True)
        db.add(admin)
    admin.role = "admin"
    admin.is_active = True
    admin.hashed_password = get_password_hash(senha)
    await db.commit()
    return admin.username


async def main():
    from src.database import SessionLocal

    senha = gerar_senha()
    async with SessionLocal() as db:
        username = await definir_admin(db, senha)
    print(f"Login: {username}")
    print(f"Senha: {senha}")
    print("Guarde a senha agora; ela não fica salva em lugar nenhum.")


if __name__ == "__main__":
    asyncio.run(main())
