"""Vídeo próprio por personal: troca na RESPOSTA, nunca no objeto ORM.

Os schemas Pydantic são montados a partir do ORM (cópias); o video_url é trocado
só nelas, então o commit da sessão não persiste a troca no exercício original.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import exceptions, models, schemas


async def _overrides(db: AsyncSession, trainer_ids: set[int], exercicio_ids: set[int]) -> dict[tuple[int, int], str]:
    if not trainer_ids or not exercicio_ids:
        return {}
    rows = await db.execute(
        select(models.ExercicioVideoPersonal).where(
            models.ExercicioVideoPersonal.trainer_id.in_(trainer_ids),
            models.ExercicioVideoPersonal.exercicio_id.in_(exercicio_ids),
        )
    )
    return {(r.trainer_id, r.exercicio_id): r.video_url for r in rows.scalars()}


def _trocar(ex: schemas.ExercicioPublic, dono: int | None, overrides: dict) -> None:
    url = overrides.get((dono, ex.id))
    if url is not None:
        ex.video_url, ex.video_proprio = url, True
    elif dono is not None and ex.trainer_id == dono:
        ex.video_proprio = True


async def exercicios_efetivos(db: AsyncSession, exercicios: list, trainer_id: int | None) -> list[schemas.ExercicioPublic]:
    """Biblioteca vista por um personal (trainer_id) ou pelo admin (None = originais)."""
    saida = [schemas.ExercicioPublic.model_validate(e) for e in exercicios]
    ov = await _overrides(db, {trainer_id} if trainer_id else set(), {e.id for e in saida})
    for ex in saida:
        _trocar(ex, trainer_id, ov)
    return saida


async def planos_efetivos(db: AsyncSession, planos: list, solicitante_id: int | None) -> list[schemas.PlanoTreinoPublic]:
    """Planos com o vídeo do personal dono do aluno; modelo usa o dono do modelo ou quem pede."""
    saida = [schemas.PlanoTreinoPublic.model_validate(p) for p in planos]
    await aplicar_em_planos(db, saida, solicitante_id)
    return saida


async def aplicar_em_planos(db: AsyncSession, planos: list[schemas.PlanoTreinoPublic], solicitante_id: int | None) -> None:
    aluno_ids = {p.aluno_id for p in planos if p.aluno_id}
    dono_aluno = {}
    if aluno_ids:
        rows = await db.execute(select(models.Aluno.id, models.Aluno.trainer_id).where(models.Aluno.id.in_(aluno_ids)))
        dono_aluno = dict(rows.all())
    pares = []  # (dono, ExercicioPublic)
    for p in planos:
        dono = dono_aluno.get(p.aluno_id) if p.aluno_id else (p.trainer_id or solicitante_id)
        for t in p.treinos:
            for pr in t.prescricoes:
                if pr.exercicio is not None:
                    pares.append((dono, pr.exercicio))
    ov = await _overrides(db, {d for d, _ in pares if d}, {e.id for _, e in pares})
    for dono, ex in pares:
        _trocar(ex, dono, ov)


async def aluno_efetivo(db: AsyncSession, aluno) -> schemas.AlunoPublic:
    resp = schemas.AlunoPublic.model_validate(aluno)
    await aplicar_em_planos(db, resp.planos_treino, None)  # plano de aluno usa o trainer do aluno
    return resp


async def definir_video(
    db: AsyncSession, exercicio_id: int, video_url: str | None, trainer_id: int | None
) -> schemas.ExercicioPublic:
    ex = await db.get(models.Exercicio, exercicio_id)
    if ex is None or (trainer_id is not None and ex.trainer_id not in (None, trainer_id)):
        raise exceptions.ResourceNotFoundError(f"Exercício {exercicio_id} não encontrado")
    if trainer_id is None or ex.trainer_id == trainer_id:
        ex.video_url = video_url  # admin altera o original; personal altera o próprio
    else:
        linha = (await db.execute(select(models.ExercicioVideoPersonal).where(
            models.ExercicioVideoPersonal.trainer_id == trainer_id,
            models.ExercicioVideoPersonal.exercicio_id == exercicio_id,
        ))).scalars().first()
        if video_url is None:
            if linha:
                await db.delete(linha)
        elif linha:
            linha.video_url = video_url
        else:
            db.add(models.ExercicioVideoPersonal(trainer_id=trainer_id, exercicio_id=exercicio_id, video_url=video_url))
    await db.commit()
    return (await exercicios_efetivos(db, [ex], trainer_id))[0]
