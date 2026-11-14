"""grupos secundários em exercícios e exercícios de panturrilha no grupo Panturrilha

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-11-13 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a6b7c8d9e0f1'
down_revision: Union[str, None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Nomes que indicam exercício de panturrilha (comparados sem caixa).
PADROES_PANTURRILHA = ("%panturrilha%", "%gêmeo%", "%gemeo%", "%sóleo%", "%soleo%", "%calcanhar%")

NOVOS = ("Panturrilha em Pé (Máquina)", "Panturrilha Sentado", "Panturrilha no Leg Press")


def upgrade() -> None:
    op.add_column(
        'exercicios',
        sa.Column('grupos_secundarios', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    bind = op.get_bind()
    condicao = " OR ".join(f"lower(nome) LIKE :p{i}" for i in range(len(PADROES_PANTURRILHA)))
    bind.execute(
        sa.text(f"UPDATE exercicios SET grupo_muscular = 'Panturrilha' WHERE {condicao}"),
        {f"p{i}": padrao for i, padrao in enumerate(PADROES_PANTURRILHA)},
    )
    for nome in NOVOS:
        bind.execute(
            sa.text(
                "INSERT INTO exercicios (nome, grupo_muscular) SELECT :nome, 'Panturrilha' "
                "WHERE NOT EXISTS (SELECT 1 FROM exercicios WHERE lower(nome) = lower(:nome))"
            ),
            {"nome": nome},
        )


def downgrade() -> None:
    # Os exercícios movidos para Panturrilha não voltam ao grupo anterior (ele não foi guardado).
    op.drop_column('exercicios', 'grupos_secundarios')
