from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import date, datetime
from typing import Optional, List, Literal

from src.grupos_musculares import GRUPOS_MUSCULARES, normalizar_grupo

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
    # Secundários aparecem na biblioteca e no filtro, mas não contam no volume semanal.
    grupos_secundarios: List[str] = Field(default_factory=list)
    video_url: Optional[str] = None

class ExercicioCreate(ExercicioBase):
    @field_validator("nome")
    @classmethod
    def _nome_limpo(cls, nome: str) -> str:
        return nome.strip()

    @field_validator("grupo_muscular")
    @classmethod
    def _grupo_canonico(cls, grupo: str) -> str:
        canonico = normalizar_grupo(grupo)
        if canonico is None:
            raise ValueError(
                f"Grupo muscular inválido. Use um de: {', '.join(GRUPOS_MUSCULARES)}"
            )
        return canonico

    @field_validator("grupos_secundarios")
    @classmethod
    def _secundarios_canonicos(cls, grupos: List[str]) -> List[str]:
        canonicos = []
        for grupo in grupos:
            canonico = normalizar_grupo(grupo)
            if canonico is None:
                raise ValueError(
                    f"Grupo muscular inválido: '{grupo}'. Use um de: {', '.join(GRUPOS_MUSCULARES)}"
                )
            if canonico not in canonicos:
                canonicos.append(canonico)
        return canonicos

    @model_validator(mode="after")
    def _principal_fora_dos_secundarios(self):
        self.grupos_secundarios = [g for g in self.grupos_secundarios if g != self.grupo_muscular]
        return self

class ExercicioPublic(ExercicioBase):
    """Leitura permissiva: dados legados não podem quebrar a resposta da API."""
    id: int
    trainer_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE PRESCRIÇÃO ---
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
    vezes_por_semana: int = Field(1, ge=1, le=7)
    dias_sugeridos: List[int] = Field(default_factory=list)
    prescricoes: List[PrescricaoCreate]

    @field_validator("dias_sugeridos")
    @classmethod
    def _dias_validos(cls, dias: List[int]) -> List[int]:
        if any(d < 0 or d > 6 for d in dias):
            raise ValueError("dias_sugeridos deve conter valores entre 0 (segunda) e 6 (domingo)")
        return sorted(set(dias))

class TreinoUpdate(BaseModel):
    id: Optional[int] = None
    nome: str
    vezes_por_semana: Optional[int] = Field(None, ge=1, le=7)
    dias_sugeridos: Optional[List[int]] = None
    prescricoes: List[PrescricaoUpdate]

    @field_validator("dias_sugeridos")
    @classmethod
    def _dias_validos(cls, dias: Optional[List[int]]) -> Optional[List[int]]:
        if dias is None:
            return dias
        if any(d < 0 or d > 6 for d in dias):
            raise ValueError("dias_sugeridos deve conter valores entre 0 (segunda) e 6 (domingo)")
        return sorted(set(dias))

class TreinoPublic(BaseModel):
    id: int
    nome: str
    vezes_por_semana: int = 1
    dias_sugeridos: List[int] = Field(default_factory=list)
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
    trainer_id: Optional[int] = None
    objetivo_estrategico: Optional[str] = None
    detalhes: Optional[str] = None
    duracao_semanas: Optional[int] = 4
    data_inicio: date
    esta_ativo: bool
    treinos: List[TreinoPublic]
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE PLANEJAMENTO SEMANAL ---
class TreinoSemana(BaseModel):
    treino_id: int
    treino_nome: str
    vezes_por_semana: int
    dias_sugeridos: List[int] = Field(default_factory=list)
    feitas: int
    dias_feitos: List[int] = Field(default_factory=list)

class VolumeGrupo(BaseModel):
    grupo: str
    planejado: int
    realizado: int
    media_4_semanas: float

class SemanaPublic(BaseModel):
    semana_inicio: date
    semana_fim: date
    treinos: List[TreinoSemana]
    volumes: List[VolumeGrupo]

class TreinoSugerido(BaseModel):
    treino_id: int
    treino_nome: str
    motivo: Literal["dia_sugerido", "proximo_pendente"]

class SemanaAlunoPublic(SemanaPublic):
    treino_sugerido_hoje: Optional[TreinoSugerido] = None

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
    data_hora: Optional[datetime] = None  # sem data: agora, no horário de Brasília
    realizada: bool = True
    precisa_reposicao: bool = False
    observacoes_performance: Optional[str] = None
    motivo_ausencia: Optional[str] = None
    tipo_atividade: Optional[str] = None

class SessaoTreinoPublic(SessaoTreinoCreate):
    id: int
    treino_id: Optional[int] = None
    registrado_por: Optional[str] = None
    aviso: Optional[str] = None  # ex: pacote sem saldo no check-in
    model_config = ConfigDict(from_attributes=True)

class FrequenciaMensalPublic(BaseModel):
    aluno_id: int
    referencia_mes: str
    sessoes_previstas: int
    sessoes_realizadas: int
    taxa_adesao: float

# --- SCHEMAS DE EXECUÇÃO (registro por série) ---
class SerieIn(BaseModel):
    exercicio_id: int
    prescricao_id: Optional[int] = None
    numero_serie: int = Field(ge=1)
    repeticoes: int = Field(ge=0)
    carga_kg: Optional[float] = Field(default=None, ge=0)  # nulo = peso corporal

class SeriePublic(SerieIn):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ExecucaoCreate(BaseModel):
    treino_id: int
    aluno_id: Optional[int] = None  # obrigatório quando o trainer registra; ignorado para o aluno
    data_hora: Optional[datetime] = None
    observacoes_performance: Optional[str] = None
    series: List[SerieIn] = Field(min_length=1)

class SeriesUpdate(BaseModel):
    series: List[SerieIn] = Field(min_length=1)

class SessaoExecucaoPublic(BaseModel):
    id: int
    aluno_id: int
    treino_id: Optional[int] = None
    plano_treino_id: Optional[int] = None
    data_hora: datetime
    registrado_por: Optional[str] = None
    observacoes_performance: Optional[str] = None
    aviso: Optional[str] = None
    series: List[SeriePublic]
    model_config = ConfigDict(from_attributes=True)

class SerieResumo(BaseModel):
    numero_serie: int
    repeticoes: int
    carga_kg: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class UltimaExecucaoExercicio(BaseModel):
    exercicio_id: int
    sessao_id: int
    data_hora: datetime
    series: List[SerieResumo]

class ExercicioRegistrado(BaseModel):
    id: int
    nome: str

class SemanaEvolucao(BaseModel):
    semana_inicio: date  # segunda-feira
    series: List[SerieResumo]
    carga_max: Optional[float] = None
    volume_carga: float  # soma de reps × kg

class EvolucaoPublic(BaseModel):
    exercicios: List[ExercicioRegistrado]
    semanas: List[SemanaEvolucao]

class ExercicioAtividade(BaseModel):
    exercicio_id: int
    nome: str
    carga_max: Optional[float] = None
    delta_kg: Optional[float] = None  # vs. a sessão anterior do mesmo aluno no mesmo exercício

class AtividadeRecente(BaseModel):
    sessao_id: int
    aluno_id: int
    aluno_nome: str
    treino_nome: Optional[str] = None
    data_hora: datetime
    registrado_por: Optional[str] = None
    exercicios: List[ExercicioAtividade]

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

# --- SCHEMAS DE AVISOS ---
class AvisoConsultoria(BaseModel):
    aluno_id: int
    aluno_nome: str
    data_vencimento: date
    dias_restantes: int

class AvisoPrograma(BaseModel):
    aluno_id: int
    aluno_nome: str
    plano_id: int
    plano_titulo: str
    data_fim: date
    dias_restantes: int

class AvisosPublic(BaseModel):
    consultorias: List[AvisoConsultoria]
    programas: List[AvisoPrograma]
