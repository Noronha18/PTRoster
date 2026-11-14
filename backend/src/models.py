from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Text, Float, ForeignKey, Index, JSON, UniqueConstraint, func
from sqlalchemy.orm import relationship
from src.database import Base
from datetime import date, datetime


class Usuario(Base):
    __tablename__ = 'usuarios'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="aluno")  # "trainer" ou "aluno"
    is_active = Column(Boolean, default=True)
    data_criacao = Column(DateTime, default=datetime.now)

    # Vínculo com o Aluno (opcional para trainers, obrigatório para alunos)
    aluno_id = Column(Integer, ForeignKey('alunos.id', ondelete='SET NULL'), nullable=True)

    aluno = relationship("Aluno", back_populates="usuario", foreign_keys=[aluno_id])

class Aluno(Base):
    __tablename__ = 'alunos'

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    email = Column(String, unique=True, index=True, nullable=True)
    cpf = Column(String, unique=True, index=True, nullable=True)
    data_inicio = Column(Date, default=date.today)
    dia_vencimento = Column(Integer, default=5)
    tipo_pagamento = Column(String, default="mensal") # "mensal" ou "pacote"
    saldo_aulas = Column(Integer, default=0)
    
    frequencia_semanal_plano = Column("frequencia_semanal", Integer, default=3)
    valor_mensalidade = Column(Float, default=0.0)
    idade = Column(Integer, default=0)
    objetivo = Column(Text, nullable=True)
    restricoes = Column(Text, nullable=True)
    status = Column(String, default="ativo") # "ativo", "suspenso", "cancelado"
    modalidade = Column(String, default="presencial", nullable=False)  # "presencial" ou "consultoria"
    data_vencimento_consultoria = Column(Date, nullable=True)
    bloquear_apos_vencimento = Column(Boolean, default=False, nullable=False)

    trainer_id = Column(Integer, ForeignKey('usuarios.id', ondelete='RESTRICT'), nullable=True, index=True)

    # Relacionamentos
    planos_treino = relationship("PlanoTreino", back_populates="aluno", cascade="all, delete-orphan")
    pagamentos = relationship("Pagamento", back_populates="aluno", cascade="all, delete-orphan")
    sessoes_treino = relationship("SessaoTreino", back_populates="aluno", cascade="all, delete-orphan")
    usuario = relationship("Usuario", back_populates="aluno", uselist=False, foreign_keys="Usuario.aluno_id")

    # Propriedades auxiliares para a View
    aulas_feitas_mes = 0
    status_financeiro = "em_dia"
    acesso_bloqueado = False
    dias_para_vencimento_consultoria = None
    dias_para_fim_programa = None


class Pagamento(Base):
    __tablename__ = 'pagamentos'

    id = Column(Integer, primary_key=True)
    aluno_id = Column(Integer, ForeignKey('alunos.id'))

    data_pagamento = Column(Date, default=date.today)
    valor = Column(Float)
    quantidade_aulas = Column(Integer, default=0)
    referencia_mes = Column(String(7))  # Ex: "01/2026"
    forma_pagamento = Column(String(50))  # PIX, Dinheiro, Cartão
    observacao = Column(Text, nullable=True)

    aluno = relationship("Aluno", back_populates="pagamentos")


class SessaoTreino(Base):
    __tablename__ = 'sessoes_treino'
    __table_args__ = (
        Index('ix_sessoes_treino_aluno_data_hora', 'aluno_id', 'data_hora'),
    )

    id = Column(Integer, primary_key=True)
    aluno_id = Column(Integer, ForeignKey('alunos.id', ondelete='CASCADE'))
    plano_treino_id = Column(Integer, ForeignKey('planos_treino.id', ondelete='SET NULL'), nullable=True)

    data_hora = Column(DateTime, default=datetime.now)
    realizada = Column(Boolean, default=True)
    precisa_reposicao = Column(Boolean, default=False)
    observacoes_performance = Column(Text, nullable=True)
    motivo_ausencia = Column(Text, nullable=True)
    tipo_atividade = Column(String, nullable=True)
    treino_id = Column(Integer, ForeignKey('treinos.id', ondelete='SET NULL'), nullable=True)
    registrado_por = Column(String, nullable=True)  # "aluno" ou "trainer"; nulo em sessões antigas
    
    # Relacionamentos
    aluno = relationship("Aluno", back_populates="sessoes_treino")
    plano_treino = relationship("PlanoTreino", back_populates="sessoes_executadas")
    treino = relationship("Treino")
    # passive_deletes: o banco apaga as séries (ON DELETE CASCADE) sem o ORM carregá-las
    series = relationship(
        "RegistroSerie", back_populates="sessao", cascade="all, delete-orphan",
        passive_deletes=True, order_by="RegistroSerie.id"
    )


class PlanoTreino(Base):
    __tablename__ = 'planos_treino'

    id = Column(Integer, primary_key=True, index=True)
    aluno_id = Column(Integer, ForeignKey('alunos.id', ondelete='CASCADE'), nullable=True)
    # Só em modelo (aluno_id nulo): dono do modelo; nulo = modelo da plataforma.
    trainer_id = Column(Integer, ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True, index=True)

    titulo = Column(String, index=True)
    objetivo_estrategico = Column(Text, nullable=True) 
    detalhes = Column(Text, nullable=True)
    duracao_semanas = Column(Integer, default=4)
    data_inicio = Column(Date, default=date.today)
    esta_ativo = Column(Boolean, default=True)

    # Relacionamentos
    aluno = relationship("Aluno", back_populates="planos_treino")
    treinos = relationship(
        "Treino", back_populates="plano", cascade="all, delete-orphan",
        order_by="Treino.ordem, Treino.id"
    )
    sessoes_executadas = relationship("SessaoTreino", back_populates="plano_treino")

class Treino(Base):
    """Um grupo de exercícios, ex: 'Treino A - Superiores'"""
    __tablename__ = 'treinos'
    id = Column(Integer, primary_key=True)
    plano_id = Column(Integer, ForeignKey('planos_treino.id', ondelete='CASCADE'))
    nome = Column(String) 
    ordem = Column(Integer, default=0)
    vezes_por_semana = Column(Integer, default=1, nullable=False)
    # 0=segunda ... 6=domingo; lista vazia = sem dia sugerido
    dias_sugeridos = Column(JSON, default=list, nullable=False)

    plano = relationship("PlanoTreino", back_populates="treinos")
    prescricoes = relationship(
        "Prescricao", back_populates="treino", cascade="all, delete-orphan",
        order_by="Prescricao.ordem, Prescricao.id"
    )

class Exercicio(Base):
    """A Biblioteca Global de Exercícios"""
    __tablename__ = 'exercicios'

    id = Column(Integer, primary_key=True)
    nome = Column(String, index=True)
    # Nulo = base da plataforma; preenchido = exercício do personal.
    trainer_id = Column(Integer, ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True, index=True)
    grupo_muscular = Column(String, index=True)  # principal: o único que conta no volume semanal
    grupos_secundarios = Column(JSON, nullable=False, default=list, server_default='[]')
    video_url = Column(String, nullable=True)

    __table_args__ = (Index('uq_exercicios_escopo_nome', func.coalesce(trainer_id, 0), func.lower(nome), unique=True),)

class ExercicioVideoPersonal(Base):
    """Vídeo próprio do personal para um exercício da base (só os alunos dele veem)."""
    __tablename__ = 'exercicio_videos_personal'
    id = Column(Integer, primary_key=True)
    trainer_id = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    exercicio_id = Column(Integer, ForeignKey('exercicios.id', ondelete='CASCADE'), nullable=False)
    video_url = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint('trainer_id', 'exercicio_id', name='uq_video_personal_trainer_exercicio'),)

class Prescricao(Base):
    """A ligação entre um Treino e um Exercício com as cargas/séries"""
    __tablename__ = 'prescricoes'
    id = Column(Integer, primary_key=True)
    treino_id = Column(Integer, ForeignKey('treinos.id', ondelete='CASCADE'))
    exercicio_id = Column(Integer, ForeignKey('exercicios.id'))
    
    ordem = Column(Integer, default=0)
    series = Column(Integer, default=3)
    repeticoes = Column(String)
    descanso = Column(Integer) # Em segundos
    carga = Column(String, nullable=True)
    metodo = Column(String, default="Convencional")
    observacoes = Column(Text, nullable=True)

    treino = relationship("Treino", back_populates="prescricoes")
    exercicio = relationship("Exercicio")

    @property
    def nome_exercicio(self):
        return self.exercicio.nome if self.exercicio else "Exercício Removido"


class RegistroSerie(Base):
    """Uma série executada. O histórico é por exercício e sobrevive à troca ou exclusão do plano."""
    __tablename__ = 'registros_serie'
    __table_args__ = (Index('ix_registros_serie_exercicio_sessao', 'exercicio_id', 'sessao_id'),)

    id = Column(Integer, primary_key=True)
    sessao_id = Column(Integer, ForeignKey('sessoes_treino.id', ondelete='CASCADE'), nullable=False, index=True)
    exercicio_id = Column(Integer, ForeignKey('exercicios.id'), nullable=False)
    prescricao_id = Column(Integer, ForeignKey('prescricoes.id', ondelete='SET NULL'), nullable=True)
    numero_serie = Column(Integer, nullable=False)
    repeticoes = Column(Integer, nullable=False)
    carga_kg = Column(Float, nullable=True)  # nulo = peso corporal

    sessao = relationship("SessaoTreino", back_populates="series")
    exercicio = relationship("Exercicio")
