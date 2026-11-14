"""financeiro dos personais

Revision ID: e2f3a4b5c6d7
Revises: d1c2b3a4e5f6
Create Date: 2026-11-13 23:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1c2b3a4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'planos_personal',
        sa.Column('trainer_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('valor_mensal', sa.Float(), nullable=False, server_default='0'),
        sa.Column('dia_vencimento', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('inicio', sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column('observacao', sa.Text(), nullable=True),
    )
    op.create_table(
        'pagamentos_personal',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trainer_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('referencia_mes', sa.String(length=7), nullable=False),
        sa.Column('valor', sa.Float(), nullable=False),
        sa.Column('data_pagamento', sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column('forma_pagamento', sa.String(length=50), nullable=True),
        sa.Column('observacao', sa.Text(), nullable=True),
    )
    op.create_index(
        'ix_pagamentos_personal_trainer_referencia',
        'pagamentos_personal',
        ['trainer_id', 'referencia_mes'],
    )


def downgrade() -> None:
    op.drop_index('ix_pagamentos_personal_trainer_referencia', table_name='pagamentos_personal')
    op.drop_table('pagamentos_personal')
    op.drop_table('planos_personal')
