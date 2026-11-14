"""vídeo próprio do personal para exercícios da base

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-11-13 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'exercicio_videos_personal',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trainer_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('exercicio_id', sa.Integer(), sa.ForeignKey('exercicios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('video_url', sa.String(), nullable=False),
        sa.UniqueConstraint('trainer_id', 'exercicio_id', name='uq_video_personal_trainer_exercicio'),
    )
    op.create_index('ix_exercicio_videos_personal_trainer_id', 'exercicio_videos_personal', ['trainer_id'])


def downgrade() -> None:
    op.drop_index('ix_exercicio_videos_personal_trainer_id', table_name='exercicio_videos_personal')
    op.drop_table('exercicio_videos_personal')
