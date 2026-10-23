"""adiciona índice de aluno e data em sessões

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-10-22 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_sessoes_treino_aluno_data_hora',
        'sessoes_treino',
        ['aluno_id', 'data_hora'],
    )


def downgrade() -> None:
    op.drop_index('ix_sessoes_treino_aluno_data_hora', table_name='sessoes_treino')
