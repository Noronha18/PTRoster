"""add modalidade consultoria to alunos

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('alunos', sa.Column('modalidade', sa.String(), nullable=False, server_default='presencial'))
    op.add_column('alunos', sa.Column('data_vencimento_consultoria', sa.Date(), nullable=True))
    op.add_column('alunos', sa.Column('bloquear_apos_vencimento', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('alunos', 'bloquear_apos_vencimento')
    op.drop_column('alunos', 'data_vencimento_consultoria')
    op.drop_column('alunos', 'modalidade')
