"""normaliza grupos musculares e nome de exercicio sem caixa

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-10-22 00:00:00.000000
"""
from typing import Sequence, Union
import unicodedata

import sqlalchemy as sa
from alembic import op

revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GRUPOS = (
    "Peito", "Costas", "Ombros", "Bíceps", "Tríceps", "Quadríceps",
    "Posterior", "Glúteos", "Panturrilha", "Core", "Cardio", "Funcional", "Outros",
)


def _chave(valor: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", valor or "").encode("ascii", "ignore").decode()
    return sem_acento.strip().lower()


MAPA = {_chave(grupo): grupo for grupo in GRUPOS}
# Sinônimos legados óbvios; o resto cai em "Outros".
ALIASES = {"peitoral": "Peito", "abdomen": "Core", "abdomem": "Core", "bracos": "Outros"}

PERNAS_POR_NOME = {
    "Agachamento Livre Barra": "Quadríceps",
    "Leg Press 45º": "Quadríceps",
    "Cadeira Extensora": "Quadríceps",
    "Afundo com Halteres": "Quadríceps",
    "Hack Squat": "Quadríceps",
    "Stiff Barra": "Posterior",
    "Mesa Flexora": "Posterior",
    "Cadeira Flexora": "Posterior",
    "Elevação Pélvica": "Glúteos",
    "Cadeira Abdutora": "Glúteos",
    "Cadeira Adutora": "Glúteos",
}


def _grupo_canonico(nome: str, grupo: str) -> str:
    canonico = MAPA.get(_chave(grupo))
    if canonico:
        return canonico
    if _chave(grupo) == "pernas":
        return PERNAS_POR_NOME.get(nome, "Outros")
    return ALIASES.get(_chave(grupo), "Outros")


def upgrade() -> None:
    bind = op.get_bind()
    linhas = bind.execute(sa.text("SELECT id, nome, grupo_muscular FROM exercicios")).fetchall()

    for exercicio_id, nome, grupo in linhas:
        canonico = _grupo_canonico(nome or "", grupo or "")
        if canonico != grupo:
            bind.execute(
                sa.text("UPDATE exercicios SET grupo_muscular = :grupo WHERE id = :id"),
                {"grupo": canonico, "id": exercicio_id},
            )

    duplicados = bind.execute(sa.text(
        "SELECT lower(nome), count(*) FROM exercicios "
        "GROUP BY lower(nome) HAVING count(*) > 1"
    )).fetchall()
    if duplicados:
        lista = ", ".join(f"'{nome}' ({quantidade}x)" for nome, quantidade in duplicados)
        raise RuntimeError(
            "Não é possível criar o índice único ignorando caixa: "
            f"há exercícios duplicados ({lista}). Resolva os nomes antes de migrar."
        )

    op.execute("CREATE UNIQUE INDEX uq_exercicios_nome_lower ON exercicios (lower(nome))")


def downgrade() -> None:
    op.execute("DROP INDEX uq_exercicios_nome_lower")
