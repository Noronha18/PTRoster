"""modelos e exercícios por personal (trainer_id) e unicidade de nome por escopo

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-11-13 12:00:00.000000
"""
from typing import Sequence, Union

import unicodedata

import sqlalchemy as sa
from alembic import op

revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'a6b7c8d9e0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DONO_ATUAL = "emmanuel"

# Cópia dos nomes de exercicios_base (seed_exercicios.py) na data desta migração:
# esses continuam como base da plataforma (trainer_id nulo).
NOMES_BASE = [
    "Supino Reto Barra",
    "Supino Inclinado Halteres",
    "Crucifixo Máquina (Peck Deck)",
    "Crossover Polia Alta",
    "Supino Declinado Barra",
    "Flexão de Braços (Push up)",
    "Puxada Aberta Pulley",
    "Remada Curvada Barra",
    "Remada Baixa Triângulo",
    "Barra Fixa (Pull up)",
    "Levantamento Terra",
    "Pullover Polia Alta",
    "Remada Unilateral (Serrote)",
    "Agachamento Livre Barra",
    "Leg Press 45º",
    "Cadeira Extensora",
    "Afundo com Halteres",
    "Hack Squat",
    "Stiff Barra",
    "Mesa Flexora",
    "Cadeira Flexora",
    "Elevação Pélvica",
    "Panturrilha em Pé (Máquina)",
    "Panturrilha Sentado",
    "Panturrilha no Leg Press",
    "Cadeira Abdutora",
    "Cadeira Adutora",
    "Desenvolvimento Halteres",
    "Elevação Lateral Halteres",
    "Elevação Frontal Polia",
    "Crucifixo Inverso Halteres",
    "Desenvolvimento Arnold",
    "Rosca Direta Barra W",
    "Rosca Alternada Halteres",
    "Rosca Martelo",
    "Rosca Concentrada",
    "Rosca Scott Máquina",
    "Tríceps Pulley Corda",
    "Tríceps Testa Barra",
    "Tríceps Francês Halter",
    "Tríceps Coice Polia",
    "Mergulho Paralelas",
    "Abdominal Supra Solo",
    "Prancha Isométrica",
    "Elevação de Pernas Suspenso",
    "Abdominal Infra no Banco",
    "Russian Twist",
    "Corrida Esteira",
    "Bicicleta Ergométrica",
    "Elíptico",
    "Burpee",
    "Kettlebell Swing",
]


def upgrade() -> None:
    op.add_column('planos_treino', sa.Column('trainer_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_planos_treino_trainer_id', 'planos_treino', 'usuarios', ['trainer_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_planos_treino_trainer_id', 'planos_treino', ['trainer_id'])
    op.add_column('exercicios', sa.Column('trainer_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_exercicios_trainer_id', 'exercicios', 'usuarios', ['trainer_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_exercicios_trainer_id', 'exercicios', ['trainer_id'])

    # Unicidade do nome passa a ser por escopo (base ou personal).
    op.drop_index('ix_exercicios_nome', table_name='exercicios')
    op.create_index('ix_exercicios_nome', 'exercicios', ['nome'])
    op.drop_index('uq_exercicios_nome_lower', table_name='exercicios')
    op.create_index(
        'uq_exercicios_escopo_nome', 'exercicios',
        [sa.text('coalesce(trainer_id, 0)'), sa.text('lower(nome)')], unique=True,
    )

    # Dados atuais vão para o personal "emmanuel"; sem ele, tudo fica como plataforma.
    bind = op.get_bind()
    dono = bind.execute(
        sa.text("SELECT id FROM usuarios WHERE lower(username) = :u AND role IN ('trainer', 'admin') ORDER BY id LIMIT 1"),
        {"u": DONO_ATUAL},
    ).scalar()
    if dono is None:
        print(f"AVISO: usuário '{DONO_ATUAL}' não encontrado; modelos e exercícios ficam como da plataforma.")
        return
    bind.execute(sa.text("UPDATE planos_treino SET trainer_id = :d WHERE aluno_id IS NULL"), {"d": dono})
    # Comparação em Python: lower() do banco depende do locale e erra acentos.
    norm = lambda n: unicodedata.normalize("NFC", n).lower()
    base = {norm(n) for n in NOMES_BASE}
    for ex_id, nome in bind.execute(sa.text("SELECT id, nome FROM exercicios")).all():
        if norm(nome or "") not in base:
            bind.execute(sa.text("UPDATE exercicios SET trainer_id = :d WHERE id = :i"), {"d": dono, "i": ex_id})


def downgrade() -> None:
    # Atenção: recriar o índice único global de lower(nome) falha se houver nomes
    # repetidos entre personais/base. Resolva os duplicados antes de reverter.
    op.drop_index('uq_exercicios_escopo_nome', table_name='exercicios')
    op.create_index('uq_exercicios_nome_lower', 'exercicios', [sa.text('lower(nome)')], unique=True)
    op.drop_index('ix_exercicios_nome', table_name='exercicios')
    op.create_index('ix_exercicios_nome', 'exercicios', ['nome'], unique=True)
    op.drop_index('ix_exercicios_trainer_id', table_name='exercicios')
    op.drop_constraint('fk_exercicios_trainer_id', 'exercicios', type_='foreignkey')
    op.drop_column('exercicios', 'trainer_id')
    op.drop_index('ix_planos_treino_trainer_id', table_name='planos_treino')
    op.drop_constraint('fk_planos_treino_trainer_id', 'planos_treino', type_='foreignkey')
    op.drop_column('planos_treino', 'trainer_id')
