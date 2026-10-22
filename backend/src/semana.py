"""Cálculos puros do planejamento semanal (sem acesso ao banco)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from src import models
from src.grupos_musculares import normalizar_grupo


def inicio_semana(dia: date) -> date:
    """Segunda-feira da semana que contém `dia`."""
    return dia - timedelta(days=dia.weekday())


def volume_planejado(plano: models.PlanoTreino | None) -> dict[str, int]:
    """Séries planejadas por grupo na semana: prescrição × vezes/semana."""
    volumes: dict[str, int] = defaultdict(int)
    if plano is None:
        return dict(volumes)
    for treino in plano.treinos:
        vezes = treino.vezes_por_semana or 1
        for prescricao in treino.prescricoes:
            grupo = normalizar_grupo(prescricao.exercicio.grupo_muscular) if prescricao.exercicio else None
            volumes[grupo or "Outros"] += (prescricao.series or 0) * vezes
    return dict(volumes)


def treino_sugerido(
    plano: models.PlanoTreino | None,
    hoje: date,
    feitas: dict[int, int],
) -> tuple[models.Treino, str] | None:
    """Treino do dia; se não houver, o primeiro com menos sessões que o planejado."""
    if plano is None:
        return None
    for treino in plano.treinos:
        if hoje.weekday() in (treino.dias_sugeridos or []):
            return treino, "dia_sugerido"
    for treino in plano.treinos:
        if feitas.get(treino.id, 0) < (treino.vezes_por_semana or 1):
            return treino, "proximo_pendente"
    return None
