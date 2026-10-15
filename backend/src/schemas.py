from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional, List, Literal

StatusAluno = Literal["ativo", "suspenso", "cancelado"]
TipoPagamento = Literal["mensal", "pacote"]
Modalidade = Literal["presencial", "consultoria"]

# --- SCHEMAS DE AUTENTICAÇÃO ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- SCHEMAS DE EXERCÍCIO ---
class ExercicioBase(BaseModel):
    nome: str
    grupo_muscular: str
    video_url: Optional[str] = None

class ExercicioCreate(ExercicioBase):
    pass

class ExercicioPublic(ExercicioBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE PRESCRIÇÃO ---
class PrescricaoCargarUpdate(BaseModel):
    carga: Optional[str] = None

class PrescricaoCreate(BaseModel):
    exercicio_id: int
    series: int
    repeticoes: str
    carga: Optional[str] = None
    descanso: int = 60
    metodo: Optional[str] = "Convencional"
    observacoes: Optional[str] = None

class PrescricaoUpdate(BaseModel):
    id: Optional[int] = None # ID opcional: se vier, atualiza. Se não, cria nova.
    exercicio_id: int
    series: int
    repeticoes: str
    carga: Optional[str] = None
    descanso: int = 60
    metodo: Optional[str] = "Convencional"
    observacoes: Optional[str] = None

class PrescricaoPublic(PrescricaoCreate):
    id: int
    nome_exercicio: Optional[str] = None
    carga_kg: Optional[str] = Field(None, validation_alias="carga")
    tempo_descanso_segundos: int = Field(60, validation_alias="descanso")
    metodo: str = "Convencional"
    observacoes: Optional[str] = None
    exercicio: Optional[ExercicioPublic] = None
    
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE TREINO ---
class TreinoCreate(BaseModel):
    nome: str
    prescricoes: List[PrescricaoCreate]

class TreinoUpdate(BaseModel):
    id: Optional[int] = None
    nome: str
    prescricoes: List[PrescricaoUpdate]

class TreinoPublic(BaseModel):
    id: int
    nome: str
    prescricoes: List[PrescricaoPublic]
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE PLANO DE TREINO ---
class PlanoTreinoCreate(BaseModel):
    titulo: str
    objetivo_estrategico: Optional[str] = None
    detalhes: Optional[str] = None
    duracao_semanas: int = 4
    treinos: List[TreinoCreate]

class PlanoTreinoUpdate(BaseModel):
    titulo: Optional[str] = None
    objetivo_estrategico: Optional[str] = None
    detalhes: Optional[str] = None
    duracao_semanas: Optional[int] = None
    treinos: Optional[List[TreinoUpdate]] = None

class PlanoTreinoPublic(BaseModel):
    id: int
    titulo: str
    aluno_id: Optional[int] = None
    objetivo_estrategico: Optional[str] = None
    detalhes: Optional[str] = None
    duracao_semanas: Optional[int] = 4
    data_inicio: date
    esta_ativo: bool
    treinos: List[TreinoPublic]
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE PAGAMENTO ---
class PagamentoCreate(BaseModel):
    aluno_id: int
    valor: float
    referencia_mes: str # Ex: "02/2026"
    forma_pagamento: str # PIX, Dinheiro, etc
    quantidade_aulas: int = 0
    data_pagamento: Optional[date] = None
    observacao: Optional[str] = None
    novo_vencimento: Optional[date] = None  # obrigatório para aluno de consultoria

class PagamentoPublic(PagamentoCreate):
    id: int
    data_pagamento: date
    aluno_nome: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE ESTATÍSTICAS FINANCEIRAS ---
class ReceitaMensal(BaseModel):
    referencia_mes: str
    receita: float

class EstatisticasFinanceirasPublic(BaseModel):
    referencia_mes: str
    receita_total: float
    ticket_medio: float
    inadimplencia: float
    receita_mensal_12m: List[ReceitaMensal]
    total_alunos: int
    alunos_em_dia: int
    alunos_inadimplentes: int

# --- SCHEMAS DE SESSÃO DE TREINO ---
class SessaoTreinoCreate(BaseModel):
    aluno_id: int
    plano_treino_id: Optional[int] = None
    data_hora: datetime = Field(default_factory=datetime.now)
    realizada: bool = True
    precisa_reposicao: bool = False
    observacoes_performance: Optional[str] = None
    motivo_ausencia: Optional[str] = None
    tipo_atividade: Optional[str] = None

class SessaoTreinoPublic(SessaoTreinoCreate):
    id: int
    aviso: Optional[str] = None  # ex: pacote sem saldo no check-in
    model_config = ConfigDict(from_attributes=True)

class FrequenciaMensalPublic(BaseModel):
    aluno_id: int
    referencia_mes: str
    sessoes_previstas: int
    sessoes_realizadas: int
    taxa_adesao: float

# --- SCHEMAS DE ALUNO ---
class AlunoBase(BaseModel):
    nome: str
    email: Optional[str] = None
    cpf: Optional[str] = None
    dia_vencimento: int = 5
    tipo_pagamento: TipoPagamento = "mensal"
    saldo_aulas: int = 0
    frequencia_semanal_plano: int = 3
    valor_mensalidade: float = 0.0
    idade: int = 0
    objetivo: Optional[str] = None
    restricoes: Optional[str] = None
    status: StatusAluno = "ativo"
    modalidade: Modalidade = "presencial"
    data_vencimento_consultoria: Optional[date] = None
    bloquear_apos_vencimento: bool = False

class AlunoCreate(AlunoBase):
    username: Optional[str] = None
    password: Optional[str] = None
    trainer_id: Optional[int] = None  # preenchido pelo admin; trainers usam o próprio id

class UsuarioPublic(BaseModel):
    id: int
    username: str
    role: str
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE ADMIN ---
class TrainerCreate(BaseModel):
    username: str
    email: str
    password: str

class UsuarioAdminPublic(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    data_criacao: datetime
    aluno_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class VerificarSenhaRequest(BaseModel):
    senha: str

class VerificarSenhaResponse(BaseModel):
    valida: bool

class SenhaResetRequest(BaseModel):
    nova_senha: str = Field(min_length=6)

class AlunoUpdate(BaseModel):
    nome: Optional[str] = None
    cpf: Optional[str] = None
    dia_vencimento: Optional[int] = None
    tipo_pagamento: Optional[TipoPagamento] = None
    saldo_aulas: Optional[int] = None
    frequencia_semanal_plano: Optional[int] = None
    valor_mensalidade: Optional[float] = None
    idade: Optional[int] = None
    objetivo: Optional[str] = None
    restricoes: Optional[str] = None
    status: Optional[StatusAluno] = None
    modalidade: Optional[Modalidade] = None
    data_vencimento_consultoria: Optional[date] = None
    bloquear_apos_vencimento: Optional[bool] = None
    trainer_id: Optional[int] = None  # aplicado apenas quando o usuário é admin

class AlunoResumo(BaseModel):
    """Versão leve para listagens: sem planos, pagamentos e sessões."""
    id: int
    nome: str
    email: Optional[str] = None
    cpf: Optional[str] = None
    data_inicio: date
    dia_vencimento: int
    tipo_pagamento: str
    saldo_aulas: int
    frequencia_semanal_plano: int
    valor_mensalidade: float
    idade: int
    status: str = "ativo"
    modalidade: str = "presencial"
    data_vencimento_consultoria: Optional[date] = None
    bloquear_apos_vencimento: bool = False
    status_financeiro: str = "em_dia"
    aulas_feitas_mes: int = 0
    trainer_id: Optional[int] = None
    usuario: Optional[UsuarioPublic] = None

    model_config = ConfigDict(from_attributes=True)

class AlunoPublic(BaseModel):
    id: int
    nome: str
    email: Optional[str] = None
    cpf: Optional[str] = None
    data_inicio: date
    dia_vencimento: int
    tipo_pagamento: str
    saldo_aulas: int
    frequencia_semanal_plano: int
    valor_mensalidade: float
    idade: int
    objetivo: Optional[str] = None
    restricoes: Optional[str] = None
    status: str = "ativo"
    modalidade: str = "presencial"
    data_vencimento_consultoria: Optional[date] = None
    bloquear_apos_vencimento: bool = False
    acesso_bloqueado: bool = False
    dias_para_vencimento_consultoria: Optional[int] = None
    dias_para_fim_programa: Optional[int] = None
    status_financeiro: str = "em_dia"
    aulas_feitas_mes: int = 0
    trainer_id: Optional[int] = None
    planos_treino: List[PlanoTreinoPublic] = []
    pagamentos: List[PagamentoPublic] = []
    sessoes: List[SessaoTreinoPublic] = Field(default=[], validation_alias="sessoes_treino")
    usuario: Optional[UsuarioPublic] = None

    model_config = ConfigDict(from_attributes=True)
