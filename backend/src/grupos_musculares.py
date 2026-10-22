"""Lista canônica de grupos musculares usada pela biblioteca e pelo volume semanal."""
from __future__ import annotations

import unicodedata

GRUPOS_MUSCULARES = (
    "Peito",
    "Costas",
    "Ombros",
    "Bíceps",
    "Tríceps",
    "Quadríceps",
    "Posterior",
    "Glúteos",
    "Panturrilha",
    "Core",
    "Cardio",
    "Funcional",
    "Outros",
)

ORDEM_GRUPO = {grupo: indice for indice, grupo in enumerate(GRUPOS_MUSCULARES)}


def _chave(valor: str) -> str:
    """Compara sem caixa e sem acento: 'Bíceps' e 'biceps' viram 'biceps'."""
    sem_acento = unicodedata.normalize("NFKD", valor or "").encode("ascii", "ignore").decode()
    return sem_acento.strip().lower()


_MAPA = {_chave(grupo): grupo for grupo in GRUPOS_MUSCULARES}


def normalizar_grupo(valor: str) -> str | None:
    """Devolve o grupo canônico ou None se não estiver na lista."""
    return _MAPA.get(_chave(valor))
