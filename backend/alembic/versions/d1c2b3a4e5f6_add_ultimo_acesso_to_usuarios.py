"""último acesso do usuário

Revision ID: d1c2b3a4e5f6
Revises: c8d9e0f1a2b3
Create Date: 2026-11-13 23:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd1c2b3a4e5f6'
down_revision: Union[str, None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('usuarios', sa.Column('ultimo_acesso', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('usuarios', 'ultimo_acesso')
