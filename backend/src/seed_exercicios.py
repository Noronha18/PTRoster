import asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import SessionLocal
from src.models import Exercicio

exercicios_base = [
    # PEITO
    {"nome": "Supino Reto Barra", "grupo_muscular": "Peito", "video_url": "https://www.youtube.com/watch?v=vIGvt-vgrvY"},
    {"nome": "Supino Inclinado Halteres", "grupo_muscular": "Peito", "video_url": "https://www.youtube.com/watch?v=G-i3jMIbDmo"},
    {"nome": "Crucifixo Máquina (Peck Deck)", "grupo_muscular": "Peito", "video_url": "https://www.youtube.com/watch?v=zEcIgGm7fxU"},
    {"nome": "Crossover Polia Alta", "grupo_muscular": "Peito", "video_url": "https://www.youtube.com/watch?v=E3aha5zhlc0"},
    {"nome": "Supino Declinado Barra", "grupo_muscular": "Peito", "video_url": "https://www.youtube.com/watch?v=9XqGE8PNrws"},
    {"nome": "Flexão de Braços (Push up)", "grupo_muscular": "Peito", "video_url": "https://www.youtube.com/watch?v=UkDVBs9GEWo"},

    # COSTAS
    {"nome": "Puxada Aberta Pulley", "grupo_muscular": "Costas", "video_url": "https://www.youtube.com/watch?v=BOW9my4J_ek"},
    {"nome": "Remada Curvada Barra", "grupo_muscular": "Costas", "video_url": "https://www.youtube.com/watch?v=VJHBEy2duVc"},
    {"nome": "Remada Baixa Triângulo", "grupo_muscular": "Costas", "video_url": "https://www.youtube.com/watch?v=2YebbYuuBJQ"},
    {"nome": "Barra Fixa (Pull up)", "grupo_muscular": "Costas", "video_url": "https://www.youtube.com/watch?v=oH-NrOccUOg"},
    {"nome": "Levantamento Terra", "grupo_muscular": "Costas", "video_url": "https://www.youtube.com/watch?v=QiqUXcz2iyA"},
    {"nome": "Pullover Polia Alta", "grupo_muscular": "Costas", "video_url": "https://www.youtube.com/watch?v=F8SukAvJv-Q"},
    {"nome": "Remada Unilateral (Serrote)", "grupo_muscular": "Costas", "video_url": "https://www.youtube.com/watch?v=K25eTWoEOWU"},

    # PERNAS (QUADRÍCEPS)
    {"nome": "Agachamento Livre Barra", "grupo_muscular": "Quadríceps", "video_url": "https://www.youtube.com/watch?v=rM6SDUdl9fs"},
    {"nome": "Leg Press 45º", "grupo_muscular": "Quadríceps", "video_url": "https://www.youtube.com/watch?v=waAxlYvtCcI"},
    {"nome": "Cadeira Extensora", "grupo_muscular": "Quadríceps", "video_url": "https://www.youtube.com/watch?v=RHgqvYAed_8"},
    {"nome": "Afundo com Halteres", "grupo_muscular": "Quadríceps", "video_url": "https://www.youtube.com/watch?v=mPtTzNYAHi0"},
    {"nome": "Hack Squat", "grupo_muscular": "Quadríceps", "video_url": "https://www.youtube.com/watch?v=Whp712OHPl8"},

    # PERNAS (POSTERIOR/GLÚTEO)
    {"nome": "Stiff Barra", "grupo_muscular": "Posterior", "video_url": "https://www.youtube.com/watch?v=BHfY5-jGNDA"},
    {"nome": "Mesa Flexora", "grupo_muscular": "Posterior", "video_url": "https://www.youtube.com/watch?v=8Nat6GRiEoc"},
    {"nome": "Cadeira Flexora", "grupo_muscular": "Posterior", "video_url": "https://www.youtube.com/watch?v=e0_xHkXw350"},
    {"nome": "Elevação Pélvica", "grupo_muscular": "Glúteos", "video_url": "https://www.youtube.com/watch?v=kvmT_ZlgVI0"},

    # PANTURRILHA
    {"nome": "Panturrilha em Pé (Máquina)", "grupo_muscular": "Panturrilha", "video_url": None},
    {"nome": "Panturrilha Sentado", "grupo_muscular": "Panturrilha", "video_url": None},
    {"nome": "Panturrilha no Leg Press", "grupo_muscular": "Panturrilha", "video_url": None},
    {"nome": "Cadeira Abdutora", "grupo_muscular": "Glúteos", "video_url": "https://www.youtube.com/watch?v=50qHGus1TZk"},
    {"nome": "Cadeira Adutora", "grupo_muscular": "Glúteos", "video_url": "https://www.youtube.com/watch?v=goQVyEGMYMM"},

    # OMBROS (DELTOIDES)
    {"nome": "Desenvolvimento Halteres", "grupo_muscular": "Ombros", "video_url": "https://www.youtube.com/watch?v=eufDL9MmF8A"},
    {"nome": "Elevação Lateral Halteres", "grupo_muscular": "Ombros", "video_url": "https://www.youtube.com/watch?v=jannLx4RxKo"},
    {"nome": "Elevação Frontal Polia", "grupo_muscular": "Ombros", "video_url": "https://www.youtube.com/watch?v=Ed1jFL_2464"},
    {"nome": "Crucifixo Inverso Halteres", "grupo_muscular": "Ombros", "video_url": "https://www.youtube.com/watch?v=neiVTL2U5Qo"},
    {"nome": "Desenvolvimento Arnold", "grupo_muscular": "Ombros", "video_url": "https://www.youtube.com/watch?v=ijkw1TUmzJc"},

    # BRAÇOS (BÍCEPS)
    {"nome": "Rosca Direta Barra W", "grupo_muscular": "Bíceps", "video_url": "https://www.youtube.com/watch?v=017j7Gbxipo"},
    {"nome": "Rosca Alternada Halteres", "grupo_muscular": "Bíceps", "video_url": "https://www.youtube.com/watch?v=pdzDa9CwJ2Y"},
    {"nome": "Rosca Martelo", "grupo_muscular": "Bíceps", "video_url": "https://www.youtube.com/watch?v=1-xCKLVxqqg"},
    {"nome": "Rosca Concentrada", "grupo_muscular": "Bíceps", "video_url": "https://www.youtube.com/watch?v=nIUjhJMEmFk"},
    {"nome": "Rosca Scott Máquina", "grupo_muscular": "Bíceps", "video_url": "https://www.youtube.com/watch?v=90sG3CFTz4E"},

    # BRAÇOS (TRÍCEPS)
    {"nome": "Tríceps Pulley Corda", "grupo_muscular": "Tríceps", "video_url": "https://www.youtube.com/watch?v=7le1JRUUagM"},
    {"nome": "Tríceps Testa Barra", "grupo_muscular": "Tríceps", "video_url": "https://www.youtube.com/watch?v=gZ2gzw7lLQk"},
    {"nome": "Tríceps Francês Halter", "grupo_muscular": "Tríceps", "video_url": "https://www.youtube.com/watch?v=_WSadl0-dfU"},
    {"nome": "Tríceps Coice Polia", "grupo_muscular": "Tríceps", "video_url": "https://www.youtube.com/watch?v=xGjTMBMRzds"},
    {"nome": "Mergulho Paralelas", "grupo_muscular": "Tríceps", "video_url": "https://www.youtube.com/watch?v=OPyI6B68tHw"},

    # CORE / ABDÔMEN
    {"nome": "Abdominal Supra Solo", "grupo_muscular": "Core", "video_url": "https://www.youtube.com/watch?v=hZVIstfFsIc"},
    {"nome": "Prancha Isométrica", "grupo_muscular": "Core", "video_url": "https://www.youtube.com/watch?v=OnVIGDpnMow"},
    {"nome": "Elevação de Pernas Suspenso", "grupo_muscular": "Core", "video_url": "https://www.youtube.com/watch?v=Qg5KwPlB75E"},
    {"nome": "Abdominal Infra no Banco", "grupo_muscular": "Core", "video_url": "https://www.youtube.com/watch?v=fN1zziClTfE"},
    {"nome": "Russian Twist", "grupo_muscular": "Core", "video_url": "https://www.youtube.com/watch?v=4AFJrgd7HkU"},

    # CARDIO / OUTROS
    {"nome": "Corrida Esteira", "grupo_muscular": "Cardio", "video_url": "https://www.youtube.com/watch?v=9OCjXQNRXg4"},
    {"nome": "Bicicleta Ergométrica", "grupo_muscular": "Cardio", "video_url": "https://www.youtube.com/watch?v=DeiIL3Claw8"},
    {"nome": "Elíptico", "grupo_muscular": "Cardio", "video_url": "https://www.youtube.com/watch?v=Rltlu55sBLE"},
    {"nome": "Burpee", "grupo_muscular": "Funcional", "video_url": "https://www.youtube.com/watch?v=0pFAydNWsfM"},
    {"nome": "Kettlebell Swing", "grupo_muscular": "Funcional", "video_url": "https://www.youtube.com/watch?v=MB87gQFA_y0"},
]

async def seed(db: AsyncSession = None):
    if db is None:
        async with SessionLocal() as session:
            return await _run_seed(session)
    else:
        return await _run_seed(db)

async def _run_seed(db: AsyncSession):
    print(f"🌱 Iniciando atualização da biblioteca com {len(exercicios_base)} exercícios...")
    novos = 0
    videos_atualizados = 0
    for ex_data in exercicios_base:
        # O índice único é lower(nome); a busca também precisa ignorar caixa.
        stmt = select(Exercicio).where(
            func.lower(Exercicio.nome) == ex_data["nome"].strip().lower()
        )
        result = await db.execute(stmt)
        existente = result.scalar_one_or_none()
        if existente is None:
            db.add(Exercicio(**ex_data))
            novos += 1
        else:
            # Canoniza a caixa do nome para a grafia oficial da biblioteca.
            if existente.nome != ex_data["nome"]:
                existente.nome = ex_data["nome"]
            if not existente.video_url and ex_data.get("video_url"):
                # Preenche vídeo em exercícios já cadastrados que ainda não têm
                existente.video_url = ex_data["video_url"]
                videos_atualizados += 1
            # Corrige grupos legados (ex: "Pernas") para a lista canônica
            if existente.grupo_muscular != ex_data["grupo_muscular"]:
                existente.grupo_muscular = ex_data["grupo_muscular"]

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise RuntimeError(
            "Não foi possível atualizar a biblioteca: há nomes de exercícios duplicados."
        ) from exc
    print(f"✅ Sucesso! {novos} novos exercícios adicionados, {videos_atualizados} vídeos preenchidos.")
    return novos + videos_atualizados

if __name__ == "__main__":
    asyncio.run(seed())
