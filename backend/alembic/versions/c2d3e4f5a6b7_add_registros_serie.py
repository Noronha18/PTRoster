"""add registros_serie, treino_id e registrado_por em sessoes_treino

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessoes_treino', sa.Column('treino_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_sessoes_treino_treino_id', 'sessoes_treino', 'treinos', ['treino_id'], ['id'], ondelete='SET NULL'
    )
    op.add_column('sessoes_treino', sa.Column('registrado_por', sa.String(), nullable=True))
    op.create_table(
        'registros_serie',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sessao_id', sa.Integer(), sa.ForeignKey('sessoes_treino.id', ondelete='CASCADE'), nullable=False),
        sa.Column('exercicio_id', sa.Integer(), sa.ForeignKey('exercicios.id'), nullable=False),
        sa.Column('prescricao_id', sa.Integer(), sa.ForeignKey('prescricoes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('numero_serie', sa.Integer(), nullable=False),
        sa.Column('repeticoes', sa.Integer(), nullable=False),
        sa.Column('carga_kg', sa.Float(), nullable=True),
    )
    op.create_index('ix_registros_serie_sessao_id', 'registros_serie', ['sessao_id'])
    op.create_index('ix_registros_serie_exercicio_sessao', 'registros_serie', ['exercicio_id', 'sessao_id'])


def downgrade() -> None:
    op.drop_index('ix_registros_serie_exercicio_sessao', table_name='registros_serie')
    op.drop_index('ix_registros_serie_sessao_id', table_name='registros_serie')
    op.drop_table('registros_serie')
    op.drop_column('sessoes_treino', 'registrado_por')
    op.drop_constraint('fk_sessoes_treino_treino_id', 'sessoes_treino', type_='foreignkey')
    op.drop_column('sessoes_treino', 'treino_id')
