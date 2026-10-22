"""add planejamento semanal to treinos

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-10-22 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'treinos',
        sa.Column('vezes_por_semana', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column(
        'treinos',
        sa.Column('dias_sugeridos', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column('treinos', 'dias_sugeridos')
    op.drop_column('treinos', 'vezes_por_semana')
