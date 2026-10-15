from __future__ import annotations
import calendar
import secrets
from collections import defaultdict
from datetime import datetime, date, timedelta
from sqlalchemy import select, func, or_, and_, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
from src import models, schemas, exceptions, consultoria
from src.security import get_password_hash
import logging

logger = logging.getLogger(__name__)

# --- AUXILIARES ---

async def _preencher_status_aluno(db: AsyncSession, aluno: models.Aluno):
    """Calcula status financeiro e volumetria de sessões no mês atual."""
    hoje = consultoria.hoje()
    ref_mes = f"{hoje.month:02d}/{hoje.year}"
    inicio_mes = datetime(hoje.year, hoje.month, 1)

    # 1. Status Financeiro
    if aluno.modalidade == "consultoria":
        aluno.status_financeiro = "em_dia" if consultoria.consultoria_em_dia(aluno, hoje) else "atrasado"
    elif aluno.tipo_pagamento == "pacote":
        # Se for pacote, está em dia se tiver saldo de aulas
        aluno.status_financeiro = "em_dia" if aluno.saldo_aulas > 0 else "atrasado"
    else:
        # Se for mensal, verifica pagamento no mês de referência
        stmt_pag = select(models.Pagamento).where(
            models.Pagamento.aluno_id == aluno.id,
            models.Pagamento.referencia_mes == ref_mes
        )
        result_pag = await db.execute(stmt_pag)
        pagamento = result_pag.scalars().first() 
        aluno.status_financeiro = "em_dia" if pagamento else "atrasado"

    # 2. Contagem de Sessões Realizadas
    stmt_sessao = select(func.count(models.SessaoTreino.id)).where(
        models.SessaoTreino.aluno_id == aluno.id,
        models.SessaoTreino.data_hora >= inicio_mes,
        models.SessaoTreino.realizada
    )
    result_sessao = await db.execute(stmt_sessao)
    aluno.aulas_feitas_mes = result_sessao.scalar() or 0
    
    return aluno

# --- CONTROLLERS DE ALUNO ---

async def listar_alunos_ativos(db: AsyncSession, trainer_id: int | None = None):
    """Listagem leve: sem coleções pesadas e com status calculado em queries agregadas."""
    hoje = consultoria.hoje()
    ref_mes = f"{hoje.month:02d}/{hoje.year}"
    inicio_mes = datetime(hoje.year, hoje.month, 1)

    query = (
        select(models.Aluno)
        .options(selectinload(models.Aluno.usuario))
        .order_by(models.Aluno.nome)
    )
    if trainer_id is not None:
        query = query.where(models.Aluno.trainer_id == trainer_id)
    result = await db.execute(query)
    alunos = result.scalars().all()

    if not alunos:
        return alunos

    ids = [a.id for a in alunos]

    # Alunos mensais com pagamento no mês de referência
    pagos = await db.execute(
        select(models.Pagamento.aluno_id)
        .where(
            models.Pagamento.aluno_id.in_(ids),
            models.Pagamento.referencia_mes == ref_mes,
        )
        .distinct()
    )
    ids_pagos = {row[0] for row in pagos.all()}

    # Contagem de sessões realizadas no mês, por aluno
    sessoes = await db.execute(
        select(models.SessaoTreino.aluno_id, func.count(models.SessaoTreino.id))
        .where(
            models.SessaoTreino.aluno_id.in_(ids),
            models.SessaoTreino.data_hora >= inicio_mes,
            models.SessaoTreino.realizada,
        )
        .group_by(models.SessaoTreino.aluno_id)
    )
    sessoes_por_aluno = dict(sessoes.all())

    for aluno in alunos:
        if aluno.modalidade == "consultoria":
            aluno.status_financeiro = "em_dia" if consultoria.consultoria_em_dia(aluno, hoje) else "atrasado"
        elif aluno.tipo_pagamento == "pacote":
            aluno.status_financeiro = "em_dia" if aluno.saldo_aulas > 0 else "atrasado"
        else:
            aluno.status_financeiro = "em_dia" if aluno.id in ids_pagos else "atrasado"
        aluno.aulas_feitas_mes = sessoes_por_aluno.get(aluno.id, 0)

    return alunos

async def get_aluno(db: AsyncSession, aluno_id: int, trainer_id: int | None = None):
    query = (
        select(models.Aluno)
        .where(models.Aluno.id == aluno_id)
        .options(
            selectinload(models.Aluno.planos_treino)
                .selectinload(models.PlanoTreino.treinos)
                .selectinload(models.Treino.prescricoes)
                .selectinload(models.Prescricao.exercicio),
            selectinload(models.Aluno.sessoes_treino),
            selectinload(models.Aluno.pagamentos),
            selectinload(models.Aluno.usuario)
        )
    )
    if trainer_id is not None:
        query = query.where(models.Aluno.trainer_id == trainer_id)

    result = await db.execute(query)
    aluno = result.scalars().first()

    if not aluno:
        raise exceptions.ResourceNotFoundError(f"Aluno {aluno_id} não encontrado")

    await _preencher_status_aluno(db, aluno)
    consultoria.preencher_avisos(aluno, consultoria.hoje())

    return aluno



async def criar_aluno(db: AsyncSession, aluno_in: schemas.AlunoCreate, trainer_id: int):
    if aluno_in.cpf:
        stmt = select(models.Aluno).where(models.Aluno.cpf == aluno_in.cpf)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise exceptions.BusinessRuleError(f"CPF {aluno_in.cpf} já está cadastrado.")

    if aluno_in.email:
        if await db.scalar(select(models.Aluno).where(models.Aluno.email == aluno_in.email)):
            raise exceptions.BusinessRuleError(f"E-mail {aluno_in.email} já está cadastrado em outro aluno.")
        if await db.scalar(select(models.Usuario).where(models.Usuario.email == aluno_in.email)):
            raise exceptions.BusinessRuleError(f"E-mail {aluno_in.email} já está em uso por outro usuário.")

    auth_data = aluno_in.model_dump(include={"username", "password"})
    aluno_data = aluno_in.model_dump(exclude={"username", "password", "trainer_id"})

    novo_aluno = models.Aluno(**aluno_data, trainer_id=trainer_id)
    db.add(novo_aluno)
    
    try:
        await db.flush() # Garante o ID do aluno antes de criar o usuário
        
        # Criação de usuário (Geração automática se não fornecido)
        username = auth_data.get("username")
        senha = auth_data.get("password") or secrets.token_urlsafe(12)

        if not username:
            # Ex: joao.42 (primeiro nome + id do aluno)
            primeiro_nome = aluno_data["nome"].split()[0].lower().replace(" ", "")
            username = f"{primeiro_nome}.{novo_aluno.id}"

        # Verifica se username já existe (mesmo se gerado)
        stmt_user = select(models.Usuario).where(models.Usuario.username == username)
        res_user = await db.execute(stmt_user)
        if res_user.scalar_one_or_none():
            # Se o gerado colidir (raro com ID), adicionamos um sufixo extra ou lançamos erro se for manual
            if auth_data.get("username"):
                raise exceptions.BusinessRuleError(f"Username {username} já está em uso.")
            else:
                username = f"{username}.{datetime.now().second}"

        email_usuario = aluno_in.email or f"{username}@sistema.com"

        novo_usuario = models.Usuario(
            username=username,
            hashed_password=get_password_hash(senha),
            email=email_usuario,
            role="aluno",
            aluno_id=novo_aluno.id
        )
        db.add(novo_usuario)

        await db.commit()
        
        # Re-buscamos o aluno com selectinload
        stmt = (
            select(models.Aluno)
            .options(
                selectinload(models.Aluno.planos_treino),
                selectinload(models.Aluno.pagamentos),
                selectinload(models.Aluno.sessoes_treino),
                selectinload(models.Aluno.usuario)
            )
            .where(models.Aluno.id == novo_aluno.id)
        )
        result = await db.execute(stmt)
        aluno_final = result.scalar()
        
        # Atributos auxiliares para o schema
        await _preencher_status_aluno(db, aluno_final)
        consultoria.preencher_avisos(aluno_final, consultoria.hoje())
        
        # Garante que data_inicio exista
        if not aluno_final.data_inicio:
            aluno_final.data_inicio = date.today()
        
        return aluno_final
    except Exception as e:
        await db.rollback()
        raise e

async def atualizar_status_aluno(db: AsyncSession, aluno_id: int, novo_status: str, trainer_id: int | None = None):
    aluno = await get_aluno(db, aluno_id, trainer_id)
    aluno.status = novo_status
    await db.commit()
    await db.refresh(aluno)
    return aluno

async def atualizar_aluno(db: AsyncSession, aluno_id: int, aluno_up: schemas.AlunoUpdate, trainer_id: int | None = None, permitir_troca_trainer: bool = False):
    aluno = await get_aluno(db, aluno_id, trainer_id)

    if aluno_up.cpf and aluno_up.cpf != aluno.cpf:
        stmt = select(models.Aluno).where(models.Aluno.cpf == aluno_up.cpf)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise exceptions.BusinessRuleError(f"CPF {aluno_up.cpf} já está cadastrado em outro aluno.")

    dados = aluno_up.model_dump(exclude_unset=True)
    if not permitir_troca_trainer:
        dados.pop("trainer_id", None)

    for key, value in dados.items():
        setattr(aluno, key, value)
    
    try:
        await db.commit()
        await db.refresh(aluno)
        await _preencher_status_aluno(db, aluno)
        consultoria.preencher_avisos(aluno, consultoria.hoje())
        return aluno
    except Exception as e:
        await db.rollback()
        raise e

async def excluir_aluno(db: AsyncSession, aluno_id: int, trainer_id: int | None = None):
    aluno = await get_aluno(db, aluno_id, trainer_id)
    if aluno.usuario:
        await db.delete(aluno.usuario)
    await db.delete(aluno)
    await db.commit()
    return True

async def listar_avisos(db: AsyncSession, trainer_id: int | None = None) -> dict[str, list[dict]]:
    """Consultorias vencendo/vencidas e programas terminando/terminados na janela de aviso."""
    hoje = consultoria.hoje()
    limite = hoje + timedelta(days=consultoria.JANELA_AVISO_DIAS)
    filtro = [models.Aluno.status == "ativo"]
    if trainer_id is not None:
        filtro.append(models.Aluno.trainer_id == trainer_id)

    alunos = (await db.scalars(
        select(models.Aluno)
        .where(*filtro, models.Aluno.modalidade == "consultoria",
               models.Aluno.data_vencimento_consultoria <= limite)
        .order_by(models.Aluno.data_vencimento_consultoria)
    )).all()
    consultorias = [
        {"aluno_id": a.id, "aluno_nome": a.nome, "data_vencimento": a.data_vencimento_consultoria,
         "dias_restantes": (a.data_vencimento_consultoria - hoje).days}
        for a in alunos
    ]

    planos = (await db.scalars(
        select(models.PlanoTreino)
        .join(models.Aluno, models.PlanoTreino.aluno_id == models.Aluno.id)
        .options(selectinload(models.PlanoTreino.aluno))
        .where(*filtro, models.PlanoTreino.esta_ativo)
    )).all()
    por_aluno: dict[int, list[models.PlanoTreino]] = defaultdict(list)
    for plano in planos:
        por_aluno[plano.aluno_id].append(plano)

    programas = []
    for lista in por_aluno.values():
        plano = consultoria.plano_vigente(lista)
        fim = consultoria.fim_programa(plano)
        if fim <= limite:
            programas.append({
                "aluno_id": plano.aluno_id, "aluno_nome": plano.aluno.nome, "plano_id": plano.id,
                "plano_titulo": plano.titulo, "data_fim": fim, "dias_restantes": (fim - hoje).days,
            })
    programas.sort(key=lambda p: p["dias_restantes"])

    return {"consultorias": consultorias, "programas": programas}

# --- CONTROLLERS DE PLANO DE TREINO ---

async def listar_planos_detalhados_aluno(db: AsyncSession, aluno_id: int):

    query = (
        select(models.PlanoTreino)
        .where(models.PlanoTreino.aluno_id == aluno_id)
        .options(
            selectinload(models.PlanoTreino.treinos)      # Carrega Treinos A, B...
            .selectinload(models.Treino.prescricoes)     # Carrega Exercícios de cada Treino
            .selectinload(models.Prescricao.exercicio)
        )
        .order_by(models.PlanoTreino.data_inicio.desc())
    )
    
    result = await db.execute(query)
    return result.scalars().all()

async def listar_templates_globais(db: AsyncSession):
    """
    Retorna todos os planos que não possuem aluno_id vinculado (templates).
    """
    query = (
        select(models.PlanoTreino)
        .where(models.PlanoTreino.aluno_id == None)
        .options(
            selectinload(models.PlanoTreino.treinos)
            .selectinload(models.Treino.prescricoes)
            .selectinload(models.Prescricao.exercicio)
        )
        .order_by(models.PlanoTreino.titulo)
    )
    result = await db.execute(query)
    return result.scalars().all()



async def registrar_pagamento(db: AsyncSession, dados: schemas.PagamentoCreate, trainer_id: int | None = None) -> models.Pagamento:
    """
    Registra a entrada financeira de um aluno.
    """
    aluno = await get_aluno(db, dados.aluno_id, trainer_id)

    hoje = date.today()
    ref = dados.referencia_mes or f"{hoje.month:02d}/{hoje.year}"
    _parse_referencia_mes(ref)

    # Consultoria não usa saldo: o pagamento renova o vencimento do contrato
    quantidade_aulas = dados.quantidade_aulas
    if aluno.modalidade == "consultoria":
        if not dados.novo_vencimento:
            raise exceptions.BusinessRuleError("Informe o novo vencimento da consultoria.")
        aluno.data_vencimento_consultoria = dados.novo_vencimento
        quantidade_aulas = 0

    novo_pagamento = models.Pagamento(
        aluno_id=dados.aluno_id,
        valor=dados.valor,
        referencia_mes=ref,
        forma_pagamento=dados.forma_pagamento,
        observacao=dados.observacao,
        data_pagamento=dados.data_pagamento or hoje,
        quantidade_aulas=quantidade_aulas
    )

    # Se informou quantidade de aulas, soma ao saldo do aluno (recarga)
    if quantidade_aulas > 0:
        aluno.saldo_aulas += quantidade_aulas

    db.add(novo_pagamento)
    try:
        await db.commit()
        await db.refresh(novo_pagamento)
        return novo_pagamento
    except Exception as e:
        await db.rollback()
        raise e

async def listar_pagamentos(db: AsyncSession, trainer_id: int | None = None) -> list[dict[str, Any]]:
    stmt = (
        select(
            models.Pagamento,
            models.Aluno.nome.label("aluno_nome")
        )
        .join(models.Aluno, models.Pagamento.aluno_id == models.Aluno.id)
        .order_by(models.Pagamento.data_pagamento.desc())
    )
    if trainer_id is not None:
        stmt = stmt.where(models.Aluno.trainer_id == trainer_id)
    result = await db.execute(stmt)
    
    pagamentos = []
    for row in result.all():
        pagamento = row.Pagamento
        # Converte o objeto do banco em um dicionário compatível com o schema
        pag_dict = {
            "id": pagamento.id,
            "aluno_id": pagamento.aluno_id,
            "aluno_nome": row.aluno_nome,
            "valor": pagamento.valor,
            "referencia_mes": pagamento.referencia_mes,
            "forma_pagamento": pagamento.forma_pagamento,
            "data_pagamento": pagamento.data_pagamento,
            "observacao": pagamento.observacao,
            "quantidade_aulas": pagamento.quantidade_aulas
        }
        pagamentos.append(pag_dict)
    
    return pagamentos

async def get_pagamento(db: AsyncSession, pagamento_id: int, trainer_id: int | None = None) -> models.Pagamento:
    stmt = (
        select(models.Pagamento)
        .join(models.Aluno, models.Pagamento.aluno_id == models.Aluno.id)
        .where(models.Pagamento.id == pagamento_id)
    )
    if trainer_id is not None:
        stmt = stmt.where(models.Aluno.trainer_id == trainer_id)
    result = await db.execute(stmt)
    pagamento = result.scalar_one_or_none()

    if not pagamento:
        raise exceptions.ResourceNotFoundError(f"Pagamento {pagamento_id} não encontrado")

    return pagamento

async def atualizar_pagamento(db: AsyncSession, pagamento_id: int, dados: schemas.PagamentoCreate, trainer_id: int | None = None) -> models.Pagamento:

    pagamento = await get_pagamento(db, pagamento_id, trainer_id)

    _parse_referencia_mes(dados.referencia_mes)

    # Ajusta o saldo de aulas do aluno pela diferença entre o valor antigo e o novo
    delta_aulas = dados.quantidade_aulas - (pagamento.quantidade_aulas or 0)
    if delta_aulas != 0:
        aluno = await db.get(models.Aluno, pagamento.aluno_id)
        if aluno:
            aluno.saldo_aulas = max((aluno.saldo_aulas or 0) + delta_aulas, 0)

    pagamento.valor = dados.valor
    pagamento.forma_pagamento = dados.forma_pagamento
    pagamento.observacao = dados.observacao
    pagamento.referencia_mes = dados.referencia_mes
    pagamento.quantidade_aulas = dados.quantidade_aulas
    if dados.data_pagamento:
        pagamento.data_pagamento = dados.data_pagamento

    try:
        await db.commit()
        await db.refresh(pagamento)
        return pagamento
    except Exception as e:
        await db.rollback()
        raise e

async def deletar_pagamento(db: AsyncSession, pagamento_id: int, trainer_id: int | None = None) -> dict:
    pagamento = await get_pagamento(db, pagamento_id, trainer_id)

    # Estorna aulas creditadas por este pagamento (recarga de pacote)
    if pagamento.quantidade_aulas and pagamento.quantidade_aulas > 0:
        aluno = await db.get(models.Aluno, pagamento.aluno_id)
        if aluno:
            aluno.saldo_aulas = max((aluno.saldo_aulas or 0) - pagamento.quantidade_aulas, 0)

    await db.delete(pagamento)
    await db.commit()
    return {"message": f"Pagamento {pagamento_id} deletado com sucesso"}

async def desativar_plano(db: AsyncSession, plano_id: int) -> models.PlanoTreino:
    plano = await db.scalar(
        select(models.PlanoTreino)
        .where(models.PlanoTreino.id == plano_id)
    )
    
    if not plano:
        raise exceptions.ResourceNotFoundError(f"Plano {plano_id} não encontrado")
    
    plano.esta_ativo = False
    await db.commit()
    await db.refresh(plano)
    return plano

async def deletar_prescricao(db: AsyncSession, prescricao_id: int) -> None:
    prescricao = await db.scalar(
        select(models.Prescricao).where(models.Prescricao.id == prescricao_id)
    )
    if not prescricao:
        raise exceptions.ResourceNotFoundError(f"Prescrição {prescricao_id} não encontrada")

    await db.delete(prescricao)
    await db.commit()


async def atualizar_prescricao(db: AsyncSession, prescricao_id: int, payload: schemas.PrescricaoUpdate) -> models.Prescricao:
    prescricao = await db.scalar(select(models.Prescricao).where(models.Prescricao.id == prescricao_id))
    if not prescricao:
        raise exceptions.ResourceNotFoundError(f"Prescrição {prescricao_id} não encontrada")
    
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(prescricao, key, value)
    
    await db.commit()
    await db.refresh(prescricao)
    return prescricao

# --- CONTROLLERS DE SESSAO DE TREINO ---

def _parse_referencia_mes(referencia_mes: str) -> tuple[int, int]:
    try:
        mm, yyyy = referencia_mes.split("/")
        mes = int(mm)
        ano = int(yyyy)
        if mes < 1 or mes > 12:
            raise ValueError
        return mes, ano
    except ValueError:
        raise exceptions.BusinessRuleError("referencia_mes inválida (use MM/YYYY)")


def _inicio_fim_mes(ano: int, mes: int) -> tuple[datetime, datetime]:
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    inicio = datetime(ano, mes, 1, 0, 0, 0)
    fim = datetime(ano, mes, ultimo_dia, 23, 59, 59)
    return inicio, fim


async def registrar_sessao(
    db: AsyncSession,
    payload: schemas.SessaoTreinoCreate,
    trainer_id: int | None = None,
    registrado_por_staff: bool = False,
) -> models.SessaoTreino:
    aluno = await get_aluno(db, payload.aluno_id, trainer_id)
    
    if payload.plano_treino_id is not None:
        plano = await db.scalar(
            select(models.PlanoTreino).where(
                models.PlanoTreino.id == payload.plano_treino_id,
                models.PlanoTreino.aluno_id == payload.aluno_id,
            )
        )
        if not plano:
            raise exceptions.BusinessRuleError("Plano de treino inválido para este aluno")
        

    data_final = _hora_brasilia(payload.data_hora)

    dados_sessao = payload.model_dump(exclude={"data_hora"}, exclude_unset=True)

    sessao = models.SessaoTreino(
        **dados_sessao,
        data_hora=data_final # ✅ Agora é naive (compatível com timestamp sem timezone)
    )
    
    # Só debita saldo quando o personal/admin registrou a sessão.
    # Sessões de treino independente registradas pelo próprio aluno não debitam
    aula_contabilizada = payload.realizada or (not payload.realizada and not payload.precisa_reposicao)

    sessao.registrado_por = "trainer" if registrado_por_staff else "aluno"
    aviso = await _debitar_aula(db, aluno) if registrado_por_staff and aula_contabilizada else None

    db.add(sessao)
    await db.commit()
    await db.refresh(sessao)
    sessao.aviso = aviso
    return sessao

async def _debitar_aula(db: AsyncSession, aluno: models.Aluno) -> str | None:
    """Debita uma aula de aluno presencial de pacote. Devolve aviso quando não havia saldo."""
    if aluno.modalidade != "presencial" or aluno.tipo_pagamento != "pacote":
        return None
    # UPDATE condicional: atômico sob concorrência e nunca deixa o saldo negativo
    res_debito = await db.execute(
        update(models.Aluno)
        .where(models.Aluno.id == aluno.id, models.Aluno.saldo_aulas > 0)
        .values(saldo_aulas=models.Aluno.saldo_aulas - 1)
    )
    if res_debito.rowcount == 0:
        return "Aluno de pacote sem saldo de aulas: sessão registrada sem débito."
    return None


# --- EXECUÇÃO DE TREINO (registro por série) ---

def _hora_brasilia(dt: datetime | None) -> datetime:
    """Colunas DateTime são naive: grava sempre no horário de Brasília."""
    if dt is None:
        return consultoria.agora()
    return consultoria.agora(dt) if dt.tzinfo else dt


async def _aluno_do_tenant(db: AsyncSession, aluno_id: int, trainer_id: int | None) -> models.Aluno:
    stmt = select(models.Aluno).where(models.Aluno.id == aluno_id)
    if trainer_id is not None:
        stmt = stmt.where(models.Aluno.trainer_id == trainer_id)
    aluno = await db.scalar(stmt)
    if not aluno:
        raise exceptions.ResourceNotFoundError(f"Aluno {aluno_id} não encontrado")
    return aluno


async def _validar_series(db: AsyncSession, series: list[schemas.SerieIn], treino_id: int | None) -> None:
    ids_exercicio = {s.exercicio_id for s in series}
    existentes = set((await db.scalars(
        select(models.Exercicio.id).where(models.Exercicio.id.in_(ids_exercicio))
    )).all())
    if existentes != ids_exercicio:
        raise exceptions.BusinessRuleError("Exercício inexistente na série informada.")

    ids_prescricao = {s.prescricao_id for s in series if s.prescricao_id is not None}
    if ids_prescricao:
        stmt = select(models.Prescricao.id).where(models.Prescricao.id.in_(ids_prescricao))
        if treino_id is not None:
            stmt = stmt.where(models.Prescricao.treino_id == treino_id)
        if set((await db.scalars(stmt)).all()) != ids_prescricao:
            raise exceptions.BusinessRuleError("Prescrição não pertence a este treino.")


async def _carregar_execucao(db: AsyncSession, sessao_id: int) -> models.SessaoTreino:
    return await db.scalar(
        select(models.SessaoTreino)
        .options(selectinload(models.SessaoTreino.series))
        .where(models.SessaoTreino.id == sessao_id)
        .execution_options(populate_existing=True)
    )


async def registrar_execucao(
    db: AsyncSession,
    payload: schemas.ExecucaoCreate,
    aluno_id: int,
    registrado_por: str,
    trainer_id: int | None = None,
) -> models.SessaoTreino:
    aluno = await _aluno_do_tenant(db, aluno_id, trainer_id)
    treino = await db.scalar(
        select(models.Treino)
        .join(models.PlanoTreino, models.Treino.plano_id == models.PlanoTreino.id)
        .where(models.Treino.id == payload.treino_id, models.PlanoTreino.aluno_id == aluno.id)
    )
    if not treino:
        raise exceptions.BusinessRuleError("Treino inválido para este aluno.")
    # Valida tudo antes de gravar: série inválida não deixa sessão pela metade
    await _validar_series(db, payload.series, treino.id)

    data_hora = _hora_brasilia(payload.data_hora)
    inicio_dia = datetime.combine(data_hora.date(), datetime.min.time())
    # Check-in do mesmo dia sem séries vira esta execução: um treino conta uma sessão só
    sessao = await db.scalar(
        select(models.SessaoTreino)
        .options(selectinload(models.SessaoTreino.series))
        .where(
            models.SessaoTreino.aluno_id == aluno.id,
            models.SessaoTreino.realizada.is_(True),
            models.SessaoTreino.data_hora >= inicio_dia,
            models.SessaoTreino.data_hora < inicio_dia + timedelta(days=1),
            ~models.SessaoTreino.series.any(),
        )
        .order_by(models.SessaoTreino.data_hora.desc())
        .limit(1)
    )
    # Check-in do trainer já debitou a aula
    ja_debitada = sessao is not None and sessao.registrado_por == "trainer"
    if sessao is None:
        sessao = models.SessaoTreino(aluno_id=aluno.id, data_hora=data_hora, realizada=True)
        db.add(sessao)
    if not ja_debitada:
        sessao.registrado_por = registrado_por
    sessao.plano_treino_id = treino.plano_id
    sessao.treino_id = treino.id
    sessao.observacoes_performance = payload.observacoes_performance or sessao.observacoes_performance
    sessao.series = [models.RegistroSerie(**s.model_dump()) for s in payload.series]

    # Regra atual: só o registro feito pelo trainer debita saldo
    aviso = await _debitar_aula(db, aluno) if registrado_por == "trainer" and not ja_debitada else None
    await db.commit()

    sessao = await _carregar_execucao(db, sessao.id)
    sessao.aviso = aviso
    return sessao

async def listar_sessoes(
    db: AsyncSession,
    aluno_id: int | None = None,
    trainer_id: int | None = None,
    de: date | None = None,
    ate: date | None = None,
    realizada: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[models.SessaoTreino]:
    stmt = select(models.SessaoTreino)

    if trainer_id is not None:
        stmt = stmt.join(models.Aluno, models.SessaoTreino.aluno_id == models.Aluno.id).where(
            models.Aluno.trainer_id == trainer_id
        )

    if aluno_id is not None:
        stmt = stmt.where(models.SessaoTreino.aluno_id == aluno_id)
    if realizada is not None:
        stmt = stmt.where(models.SessaoTreino.realizada == realizada)
    if de is not None:
        stmt = stmt.where(models.SessaoTreino.data_hora >= datetime.combine(de, datetime.min.time()))
    if ate is not None:
        stmt = stmt.where(models.SessaoTreino.data_hora <= datetime.combine(ate, datetime.max.time()))

    stmt = stmt.order_by(models.SessaoTreino.data_hora.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def calcular_frequencia_mensal(
    db: AsyncSession,
    aluno_id: int,
    referencia_mes: str,
    trainer_id: int | None = None,
) -> schemas.FrequenciaMensalPublic:
    mes, ano = _parse_referencia_mes(referencia_mes)
    inicio, fim = _inicio_fim_mes(ano, mes)

    aluno = await db.scalar(select(models.Aluno).where(models.Aluno.id == aluno_id))
    if not aluno or (trainer_id is not None and aluno.trainer_id != trainer_id):
        raise exceptions.ResourceNotFoundError(f"Aluno {aluno_id} não encontrado")

    # Protótipo local: semanas ≈ ceil(dias/7)
    dias_no_mes = calendar.monthrange(ano, mes)[1]
    semanas_no_mes = (dias_no_mes + 6) // 7
    meta_base = int(aluno.frequencia_semanal_plano) * semanas_no_mes

    aulas_extras = await db.scalar(
        select(func.sum(models.Pagamento.quantidade_aulas))
        .where(
            models.Pagamento.aluno_id == aluno_id,
            models.Pagamento.referencia_mes == referencia_mes
        )
    )
    aulas_extras = int(aulas_extras or 0)

    sessoes_previstas = meta_base + aulas_extras

    sessoes_realizadas = await db.scalar(
        select(func.count(models.SessaoTreino.id)).where(
            models.SessaoTreino.aluno_id == aluno_id,
            models.SessaoTreino.data_hora >= inicio,
            models.SessaoTreino.data_hora <= fim,
            or_(
                models.SessaoTreino.realizada.is_(True),
                and_(
                    models.SessaoTreino.realizada.is_(False),
                    models.SessaoTreino.precisa_reposicao.is_(False)
                )
            )
        )
    )

    sessoes_realizadas = int(sessoes_realizadas or 0)
    taxa_adesao = (sessoes_realizadas / sessoes_previstas) if sessoes_previstas > 0 else 0.0

    return schemas.FrequenciaMensalPublic(
        aluno_id=aluno_id,
        referencia_mes=referencia_mes,
        sessoes_previstas=sessoes_previstas,
        sessoes_realizadas=sessoes_realizadas,
        taxa_adesao=round(taxa_adesao, 4),
    )

def _escopo_sessao(stmt, trainer_id: int | None, aluno_id: int | None):
    """Trainer: sessões dos seus alunos. Aluno: só as que ele mesmo registrou."""
    if trainer_id is not None:
        stmt = stmt.join(models.Aluno, models.SessaoTreino.aluno_id == models.Aluno.id).where(
            models.Aluno.trainer_id == trainer_id
        )
    if aluno_id is not None:
        stmt = stmt.where(models.SessaoTreino.aluno_id == aluno_id, models.SessaoTreino.registrado_por == "aluno")
    return stmt


async def get_sessao(
    db: AsyncSession, sessao_id: int, trainer_id: int | None = None, aluno_id: int | None = None
) -> models.SessaoTreino:
    stmt = select(models.SessaoTreino).where(models.SessaoTreino.id == sessao_id)
    sessao = await db.scalar(_escopo_sessao(stmt, trainer_id, aluno_id))
    if not sessao:
        raise exceptions.ResourceNotFoundError(f"Sessão {sessao_id} não encontrada")
    return sessao

async def deletar_sessao(
    db: AsyncSession, sessao_id: int, trainer_id: int | None = None, aluno_id: int | None = None
) -> None:
    sessao = await get_sessao(db, sessao_id, trainer_id, aluno_id)
    await db.delete(sessao)
    await db.commit()


async def substituir_series(
    db: AsyncSession,
    sessao_id: int,
    series: list[schemas.SerieIn],
    trainer_id: int | None = None,
    aluno_id: int | None = None,
) -> models.SessaoTreino:
    stmt = (
        select(models.SessaoTreino)
        .options(selectinload(models.SessaoTreino.series))
        .where(models.SessaoTreino.id == sessao_id)
    )
    sessao = await db.scalar(_escopo_sessao(stmt, trainer_id, aluno_id))
    if not sessao:
        raise exceptions.ResourceNotFoundError(f"Sessão {sessao_id} não encontrada")
    await _validar_series(db, series, sessao.treino_id)

    sessao.series = [models.RegistroSerie(**s.model_dump()) for s in series]  # delete-orphan apaga as antigas
    await db.commit()
    return await _carregar_execucao(db, sessao.id)

async def _series_do_aluno(db: AsyncSession, aluno_id: int, exercicio_ids, cronologico: bool):
    """Séries do aluno nos exercícios dados, com a data da sessão."""
    ordem = (models.SessaoTreino.data_hora, models.SessaoTreino.id) if cronologico else (
        models.SessaoTreino.data_hora.desc(), models.SessaoTreino.id.desc())
    return (await db.execute(
        select(models.RegistroSerie, models.SessaoTreino.data_hora)
        .join(models.SessaoTreino, models.RegistroSerie.sessao_id == models.SessaoTreino.id)
        .where(models.SessaoTreino.aluno_id == aluno_id, models.RegistroSerie.exercicio_id.in_(exercicio_ids))
        .order_by(*ordem, models.RegistroSerie.numero_serie)
    )).all()


async def ultima_execucao(
    db: AsyncSession, aluno_id: int, treino_id: int, trainer_id: int | None = None
) -> list[dict]:
    """Por exercício do treino, as séries da última sessão em que o aluno o fez (em qualquer plano)."""
    await _aluno_do_tenant(db, aluno_id, trainer_id)
    exercicio_ids = set((await db.scalars(
        select(models.Prescricao.exercicio_id)
        .join(models.Treino, models.Prescricao.treino_id == models.Treino.id)
        .join(models.PlanoTreino, models.Treino.plano_id == models.PlanoTreino.id)
        .where(models.Treino.id == treino_id, models.PlanoTreino.aluno_id == aluno_id)
    )).all())
    if not exercicio_ids:
        return []

    # ponytail: lê o histórico inteiro desses exercícios; limitar por data se ficar lento
    ultima: dict[int, dict] = {}
    for registro, data_hora in await _series_do_aluno(db, aluno_id, exercicio_ids, cronologico=False):
        atual = ultima.setdefault(registro.exercicio_id, {
            "exercicio_id": registro.exercicio_id, "sessao_id": registro.sessao_id,
            "data_hora": data_hora, "series": [],
        })
        if atual["sessao_id"] == registro.sessao_id:
            atual["series"].append(registro)
    return list(ultima.values())

async def evolucao_exercicio(
    db: AsyncSession, aluno_id: int, exercicio_id: int | None = None, trainer_id: int | None = None
) -> dict:
    """Exercícios com registro e, para o escolhido, as séries agrupadas por semana (segunda a domingo)."""
    await _aluno_do_tenant(db, aluno_id, trainer_id)
    exercicios = (await db.execute(
        select(models.Exercicio.id, models.Exercicio.nome).distinct()
        .join(models.RegistroSerie, models.RegistroSerie.exercicio_id == models.Exercicio.id)
        .join(models.SessaoTreino, models.RegistroSerie.sessao_id == models.SessaoTreino.id)
        .where(models.SessaoTreino.aluno_id == aluno_id)
        .order_by(models.Exercicio.nome)
    )).all()

    semanas = []
    if exercicio_id is not None:
        por_semana: dict[date, list] = defaultdict(list)  # dict mantém a ordem cronológica de inserção
        for registro, data_hora in await _series_do_aluno(db, aluno_id, {exercicio_id}, cronologico=True):
            dia = data_hora.date()
            por_semana[dia - timedelta(days=dia.weekday())].append(registro)
        semanas = [
            {
                "semana_inicio": inicio,
                "series": registros,
                "carga_max": max((r.carga_kg for r in registros if r.carga_kg is not None), default=None),
                "volume_carga": sum(r.repeticoes * (r.carga_kg or 0) for r in registros),
            }
            for inicio, registros in por_semana.items()
        ]
    return {"exercicios": [{"id": i, "nome": n} for i, n in exercicios], "semanas": semanas}

async def atividade_recente(db: AsyncSession, trainer_id: int | None = None, limit: int = 20) -> list[dict]:
    """Últimas execuções com séries, com carga máxima por exercício e delta vs. a sessão anterior."""
    stmt = (
        select(models.SessaoTreino)
        .options(
            selectinload(models.SessaoTreino.aluno),
            selectinload(models.SessaoTreino.treino),
            selectinload(models.SessaoTreino.series).selectinload(models.RegistroSerie.exercicio),
        )
        .where(models.SessaoTreino.series.any())
        .order_by(models.SessaoTreino.data_hora.desc(), models.SessaoTreino.id.desc())
        .limit(limit)
    )
    if trainer_id is not None:
        stmt = stmt.join(models.Aluno, models.SessaoTreino.aluno_id == models.Aluno.id).where(
            models.Aluno.trainer_id == trainer_id
        )
    sessoes = list((await db.scalars(stmt)).all())
    if not sessoes:
        return []

    # ponytail: lê o histórico inteiro dos alunos do feed; restringir por data se ficar lento
    linhas = (await db.execute(
        select(models.SessaoTreino.aluno_id, models.RegistroSerie.exercicio_id,
               models.SessaoTreino.id, func.max(models.RegistroSerie.carga_kg))
        .join(models.RegistroSerie, models.RegistroSerie.sessao_id == models.SessaoTreino.id)
        .where(models.SessaoTreino.aluno_id.in_({s.aluno_id for s in sessoes}))
        .group_by(models.SessaoTreino.aluno_id, models.RegistroSerie.exercicio_id,
                  models.SessaoTreino.id, models.SessaoTreino.data_hora)
        .order_by(models.SessaoTreino.data_hora, models.SessaoTreino.id)
    )).all()
    historico: dict[tuple[int, int], list[tuple[int, float | None]]] = defaultdict(list)
    for aluno_id, exercicio_id, sessao_id, carga_max in linhas:
        historico[(aluno_id, exercicio_id)].append((sessao_id, carga_max))

    feed = []
    for sessao in sessoes:
        nomes = {}
        for registro in sessao.series:
            nomes.setdefault(registro.exercicio_id, registro.exercicio.nome)
        exercicios = []
        for exercicio_id, nome in nomes.items():
            linha_tempo = historico[(sessao.aluno_id, exercicio_id)]
            pos = next(i for i, (sid, _) in enumerate(linha_tempo) if sid == sessao.id)
            carga = linha_tempo[pos][1]
            anterior = linha_tempo[pos - 1][1] if pos > 0 else None
            delta = round(carga - anterior, 2) if carga is not None and anterior is not None else None
            exercicios.append({"exercicio_id": exercicio_id, "nome": nome, "carga_max": carga, "delta_kg": delta})
        feed.append({
            "sessao_id": sessao.id,
            "aluno_id": sessao.aluno_id,
            "aluno_nome": sessao.aluno.nome,
            "treino_nome": sessao.treino.nome if sessao.treino else None,
            "data_hora": sessao.data_hora,
            "registrado_por": sessao.registrado_por,
            "exercicios": exercicios,
        })
    return feed

def _month_starts(ate_mes_atual: date, n: int = 12) -> list[date]:
    """Retorna lista (ordem crescente) com o 1º dia de cada mês, dos últimos n meses."""
    y, m = ate_mes_atual.year, ate_mes_atual.month
    out: list[date] = []
    for i in range(n - 1, -1, -1):
        mm = m - i
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        out.append(date(yy, mm, 1))
    return out


async def calcular_estatisticas_financeiras(db: AsyncSession, trainer_id: int | None = None) -> dict[str, Any]:
    hoje = consultoria.hoje()
    ref_mes = f"{hoje.month:02d}/{hoje.year}"
    mes_atual_inicio = date(hoje.year, hoje.month, 1)

    # Filtro de alunos do trainer (ou todos para admin)
    aluno_trainer_filter = (models.Aluno.trainer_id == trainer_id) if trainer_id is not None else True

    # === QUERY 1: KPIs do mês atual ===
    receita_mes_sq = (
        select(func.coalesce(func.sum(models.Pagamento.valor), 0))
        .join(models.Aluno, models.Pagamento.aluno_id == models.Aluno.id)
        .where(models.Pagamento.referencia_mes == ref_mes)
        .where(aluno_trainer_filter)
        .scalar_subquery()
    )

    alunos_em_dia_sq = (
        select(func.count(models.Aluno.id))
        .where(aluno_trainer_filter)
        .where(models.Aluno.status == "ativo")
        .where(
            or_(
                and_(
                    models.Aluno.modalidade == "presencial",
                    models.Aluno.tipo_pagamento == "mensal",
                    models.Aluno.id.in_(
                        select(models.Pagamento.aluno_id).where(models.Pagamento.referencia_mes == ref_mes)
                    )
                ),
                and_(
                    models.Aluno.modalidade == "presencial",
                    models.Aluno.tipo_pagamento == "pacote",
                    models.Aluno.saldo_aulas > 0
                ),
                and_(
                    models.Aluno.modalidade == "consultoria",
                    models.Aluno.data_vencimento_consultoria >= hoje
                ),
            )
        )
        .scalar_subquery()
    )

    # Apenas alunos ativos entram no cálculo de inadimplência
    total_alunos_sq = (
        select(func.count(models.Aluno.id))
        .where(aluno_trainer_filter)
        .where(models.Aluno.status == "ativo")
        .scalar_subquery()
    )

    kpi_stmt = select(
        receita_mes_sq.label("receita_total_mes"),
        alunos_em_dia_sq.label("alunos_em_dia"),
        total_alunos_sq.label("total_alunos"),
    )

    kpi_row = (await db.execute(kpi_stmt)).one()
    receita_total_mes = float(kpi_row.receita_total_mes or 0)
    alunos_em_dia = int(kpi_row.alunos_em_dia or 0)
    total_alunos = int(kpi_row.total_alunos or 0)

    alunos_inadimplentes = max(total_alunos - alunos_em_dia, 0)
    inadimplencia = (alunos_inadimplentes / total_alunos) if total_alunos > 0 else 0.0

    alunos_que_pagaram_stmt = (
        select(func.count(func.distinct(models.Pagamento.aluno_id)))
        .join(models.Aluno, models.Pagamento.aluno_id == models.Aluno.id)
        .where(models.Pagamento.referencia_mes == ref_mes)
        .where(aluno_trainer_filter)
    )
    alunos_que_pagaram_este_mes = await db.scalar(alunos_que_pagaram_stmt)
    ticket_medio = (receita_total_mes / alunos_que_pagaram_este_mes) if alunos_que_pagaram_este_mes and alunos_que_pagaram_este_mes > 0 else 0.0

    # === QUERY 2: Série histórica 12 meses ===
    meses = _month_starts(mes_atual_inicio, n=12)
    inicio_janela = meses[0]

    # extract() é portável (PostgreSQL e SQLite), ao contrário de date_trunc
    ano_col = func.extract("year", models.Pagamento.data_pagamento).label("ano")
    mes_col = func.extract("month", models.Pagamento.data_pagamento).label("mes")
    serie_stmt = (
        select(
            ano_col,
            mes_col,
            func.coalesce(func.sum(models.Pagamento.valor), 0).label("receita"),
        )
        .join(models.Aluno, models.Pagamento.aluno_id == models.Aluno.id)
        .where(models.Pagamento.data_pagamento >= inicio_janela)
        .where(aluno_trainer_filter)
        .group_by(ano_col, mes_col)
        .order_by(ano_col, mes_col)
    )

    serie_rows = (await db.execute(serie_stmt)).all()

    # Preenche meses sem receita com 0
    receita_por_mes: dict[date, float] = {}
    for ano, mes, receita in serie_rows:
        receita_por_mes[date(int(ano), int(mes), 1)] = float(receita or 0)

    receita_mensal_12m = [
        {"referencia_mes": f"{m.month:02d}/{m.year}", "receita": receita_por_mes.get(m, 0.0)}
        for m in meses
    ]

    resultado = {
        "referencia_mes": ref_mes,
        "receita_total": receita_total_mes,
        "ticket_medio": round(ticket_medio, 2),
        "inadimplencia": round(inadimplencia, 4),
        "receita_mensal_12m": receita_mensal_12m,
        "total_alunos": total_alunos,
        "alunos_em_dia": alunos_em_dia,
        "alunos_inadimplentes": alunos_inadimplentes,
    }

    return resultado

async def _assert_owns_plano(db: AsyncSession, plano_id: int, trainer_id: int | None) -> models.PlanoTreino:
    """Busca plano e verifica ownership. Templates (aluno_id=None) são acessíveis a todos."""
    plano = await db.scalar(select(models.PlanoTreino).where(models.PlanoTreino.id == plano_id))
    if not plano:
        raise exceptions.ResourceNotFoundError(f"Plano de treino {plano_id} não encontrado")
    if trainer_id is not None and plano.aluno_id is not None:
        aluno_trainer = await db.scalar(
            select(models.Aluno.trainer_id).where(models.Aluno.id == plano.aluno_id)
        )
        if aluno_trainer != trainer_id:
            raise exceptions.ResourceNotFoundError(f"Plano de treino {plano_id} não encontrado")
    return plano


async def criar_plano_treino(db: AsyncSession, aluno_id: int | None, plano_in: schemas.PlanoTreinoCreate, trainer_id: int | None = None):
    if aluno_id is not None and trainer_id is not None:
        await get_aluno(db, aluno_id, trainer_id)  # valida ownership

    # 1. Se for para um aluno específico, desativa os planos anteriores
    if aluno_id is not None:
        stmt_desativa = (
            update(models.PlanoTreino)
            .where(models.PlanoTreino.aluno_id == aluno_id, models.PlanoTreino.esta_ativo)
            .values(esta_ativo=False)
        )
        await db.execute(stmt_desativa)

    # 2. Cria o Plano
    novo_plano = models.PlanoTreino(
        aluno_id=aluno_id,
        titulo=plano_in.titulo,
        objetivo_estrategico=plano_in.objetivo_estrategico,
        detalhes=plano_in.detalhes,
        duracao_semanas=plano_in.duracao_semanas,
        esta_ativo=True if aluno_id is not None else False  # Templates não ficam ativos por padrão
    )
    db.add(novo_plano)
    await db.flush() # Garante que temos o ID do plano

    # 2. Cria os Treinos (A, B, C...) preservando a ordem do payload
    for t_idx, treino_data in enumerate(plano_in.treinos):
        novo_treino = models.Treino(
            plano_id=novo_plano.id,
            nome=treino_data.nome,
            ordem=t_idx
        )
        db.add(novo_treino)
        await db.flush()

        # 3. Cria as Prescrições para cada treino
        for p_idx, pres_data in enumerate(treino_data.prescricoes):
            nova_pres = models.Prescricao(
                treino_id=novo_treino.id,
                ordem=p_idx,
                **pres_data.model_dump()
            )
            db.add(nova_pres)

    try:
        await db.commit()
        
        # Re-busca com selectinload para evitar erro de lazy loading no schema
        stmt = (
            select(models.PlanoTreino)
            .options(
                selectinload(models.PlanoTreino.treinos)
                .selectinload(models.Treino.prescricoes)
                .selectinload(models.Prescricao.exercicio)
            )
            .where(models.PlanoTreino.id == novo_plano.id)
        )
        res = await db.execute(stmt)
        return res.scalar()
    except Exception as e:
        await db.rollback()
        raise e

async def deletar_plano_treino(db: AsyncSession, plano_id: int, trainer_id: int | None = None) -> None:
    plano = await _assert_owns_plano(db, plano_id, trainer_id)
    await db.delete(plano)
    await db.commit()

async def clonar_plano_treino(db: AsyncSession, plano_origem_id: int, novo_aluno_id: int | None, trainer_id: int | None = None) -> models.PlanoTreino:
    """
    Clona um plano existente para um novo aluno (ou como template se novo_aluno_id for None).
    """
    # 1. Valida ownership e carrega o plano original
    await _assert_owns_plano(db, plano_origem_id, trainer_id)
    stmt = (
        select(models.PlanoTreino)
        .options(
            selectinload(models.PlanoTreino.treinos)
            .selectinload(models.Treino.prescricoes)
        )
        .where(models.PlanoTreino.id == plano_origem_id)
    )
    result = await db.execute(stmt)
    plano_origem = result.scalar_one_or_none()

    if not plano_origem:
        raise exceptions.ResourceNotFoundError(f"Plano de origem {plano_origem_id} não encontrado")

    # 2. Se for para um aluno, desativa os planos atuais dele
    if novo_aluno_id:
        await db.execute(
            update(models.PlanoTreino)
            .where(models.PlanoTreino.aluno_id == novo_aluno_id, models.PlanoTreino.esta_ativo)
            .values(esta_ativo=False)
        )

    # 3. Cria o novo plano (Cópia profunda)
    # Templates mantêm o título original; cópias para aluno ganham sufixo
    novo_plano = models.PlanoTreino(
        aluno_id=novo_aluno_id,
        titulo=f"{plano_origem.titulo} (Cópia)" if novo_aluno_id else plano_origem.titulo,
        objetivo_estrategico=plano_origem.objetivo_estrategico,
        detalhes=plano_origem.detalhes,
        duracao_semanas=plano_origem.duracao_semanas,
        esta_ativo=True if novo_aluno_id else False # Templates começam inativos ou neutros
    )
    db.add(novo_plano)
    await db.flush()

    for treino_origem in plano_origem.treinos:
        novo_treino = models.Treino(
            plano_id=novo_plano.id,
            nome=treino_origem.nome,
            ordem=treino_origem.ordem
        )
        db.add(novo_treino)
        await db.flush()

        for pres_origem in treino_origem.prescricoes:
            nova_pres = models.Prescricao(
                treino_id=novo_treino.id,
                ordem=pres_origem.ordem,
                exercicio_id=pres_origem.exercicio_id,
                series=pres_origem.series,
                repeticoes=pres_origem.repeticoes,
                descanso=pres_origem.descanso,
                carga=pres_origem.carga,
                metodo=pres_origem.metodo,
                observacoes=pres_origem.observacoes
            )
            db.add(nova_pres)

    await db.commit()
    
    # Retorna o plano clonado com os dados carregados
    stmt_final = (
        select(models.PlanoTreino)
        .options(
            selectinload(models.PlanoTreino.treinos)
            .selectinload(models.Treino.prescricoes)
            .selectinload(models.Prescricao.exercicio)
        )
        .where(models.PlanoTreino.id == novo_plano.id)
    )
    res_final = await db.execute(stmt_final)
    return res_final.scalar()

async def atualizar_plano_treino(db: AsyncSession, plano_id: int, payload: schemas.PlanoTreinoUpdate, trainer_id: int | None = None) -> models.PlanoTreino:
    """
    Atualiza um plano de treino e toda sua hierarquia (treinos e prescrições).
    Implementa lógica de sincronização: o que não vier no payload é removido.
    """
    await _assert_owns_plano(db, plano_id, trainer_id)

    stmt = (
        select(models.PlanoTreino)
        .options(
            selectinload(models.PlanoTreino.treinos)
            .selectinload(models.Treino.prescricoes)
        )
        .where(models.PlanoTreino.id == plano_id)
    )
    result = await db.execute(stmt)
    plano = result.scalar_one_or_none()

    if not plano:
        raise exceptions.ResourceNotFoundError(f"Plano {plano_id} não encontrado")

    # 2. Atualiza campos básicos do plano
    dados_plano = payload.model_dump(exclude={"treinos"}, exclude_unset=True)
    for key, value in dados_plano.items():
        setattr(plano, key, value)

    # 3. Sincroniza Treinos se fornecido
    if payload.treinos is not None:
        # Forçamos o carregamento/acesso para garantir que o SQLAlchemy não se perca
        treinos_atuais_map = {t.id: t for t in plano.treinos}
        ids_no_payload = {t.id for t in payload.treinos if t.id is not None}

        # 3a. Remover treinos que não estão no payload
        # Usamos uma lista auxiliar para iterar e deletar com segurança
        for t_id, t_obj in list(treinos_atuais_map.items()):
            if t_id not in ids_no_payload:
                # Remove da coleção da relação também
                plano.treinos.remove(t_obj)
                await db.delete(t_obj)

        # 3b. Atualizar ou Criar
        for i, t_data in enumerate(payload.treinos):
            if t_data.id and t_data.id in treinos_atuais_map:
                # Atualizar existente
                treino = treinos_atuais_map[t_data.id]
                treino.nome = t_data.nome
                treino.ordem = i

                # Sincronizar Prescrições
                pres_atuais_map = {p.id: p for p in treino.prescricoes}
                p_ids_no_payload = {p.id for p in t_data.prescricoes if p.id is not None}

                for p_id, p_obj in list(pres_atuais_map.items()):
                    if p_id not in p_ids_no_payload:
                        treino.prescricoes.remove(p_obj)
                        await db.delete(p_obj)

                for p_idx, p_data in enumerate(t_data.prescricoes):
                    if p_data.id and p_data.id in pres_atuais_map:
                        pres = pres_atuais_map[p_data.id]
                        for k, v in p_data.model_dump(exclude={"id"}).items():
                            setattr(pres, k, v)
                        pres.ordem = p_idx
                    else:
                        nova_p = models.Prescricao(treino_id=treino.id, ordem=p_idx, **p_data.model_dump(exclude={"id"}))
                        db.add(nova_p)
            else:
                # Criar novo treino
                novo_treino = models.Treino(plano_id=plano.id, nome=t_data.nome, ordem=i)
                plano.treinos.append(novo_treino)
                db.add(novo_treino)
                await db.flush() # Para ganhar o ID do novo treino
                for p_idx, p_data in enumerate(t_data.prescricoes):
                    nova_p = models.Prescricao(treino_id=novo_treino.id, ordem=p_idx, **p_data.model_dump(exclude={"id"}))
                    db.add(nova_p)

    await db.commit()

    # Retorna o plano atualizado com relações novas
    stmt_final = (
        select(models.PlanoTreino)
        .options(
            selectinload(models.PlanoTreino.treinos)
            .selectinload(models.Treino.prescricoes)
            .selectinload(models.Prescricao.exercicio)
        )
        .where(models.PlanoTreino.id == plano.id)
    )
    res_final = await db.execute(stmt_final)
    return res_final.scalar()

# --- CONTROLLERS DE ADMIN ---

async def criar_trainer(db: AsyncSession, trainer_in: schemas.TrainerCreate) -> models.Usuario:
    stmt = select(models.Usuario).where(models.Usuario.username == trainer_in.username)
    if await db.scalar(stmt):
        raise exceptions.BusinessRuleError(f"Username '{trainer_in.username}' já está em uso.")

    stmt_email = select(models.Usuario).where(models.Usuario.email == trainer_in.email)
    if await db.scalar(stmt_email):
        raise exceptions.BusinessRuleError(f"E-mail '{trainer_in.email}' já está em uso.")

    novo_trainer = models.Usuario(
        username=trainer_in.username,
        email=trainer_in.email,
        hashed_password=get_password_hash(trainer_in.password),
        role="trainer",
        is_active=True,
    )
    db.add(novo_trainer)
    try:
        await db.commit()
        await db.refresh(novo_trainer)
        return novo_trainer
    except Exception as e:
        await db.rollback()
        raise e


async def listar_todos_usuarios(db: AsyncSession) -> list[models.Usuario]:
    result = await db.execute(
        select(models.Usuario).order_by(models.Usuario.role, models.Usuario.username)
    )
    return list(result.scalars().all())


async def verificar_senha_usuario(db: AsyncSession, usuario_id: int, senha: str) -> bool:
    usuario = await db.scalar(select(models.Usuario).where(models.Usuario.id == usuario_id))
    if not usuario:
        raise exceptions.ResourceNotFoundError(f"Usuário {usuario_id} não encontrado")
    from src.security import verify_password
    return verify_password(senha, usuario.hashed_password)


async def resetar_senha_usuario(db: AsyncSession, usuario_id: int, nova_senha: str) -> models.Usuario:
    usuario = await db.scalar(select(models.Usuario).where(models.Usuario.id == usuario_id))
    if not usuario:
        raise exceptions.ResourceNotFoundError(f"Usuário {usuario_id} não encontrado")
    usuario.hashed_password = get_password_hash(nova_senha)
    try:
        await db.commit()
        await db.refresh(usuario)
        return usuario
    except Exception as e:
        await db.rollback()
        raise e


async def listar_exercicios(db: AsyncSession):
    result = await db.execute(select(models.Exercicio).order_by(models.Exercicio.grupo_muscular))
    return result.scalars().all()

async def criar_exercicio(db: AsyncSession, exercicio_in: schemas.ExercicioCreate):
    stmt = select(models.Exercicio).where(models.Exercicio.nome == exercicio_in.nome)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise exceptions.BusinessRuleError(f"Exercício '{exercicio_in.nome}' já cadastrado.")
    
    novo_exercicio = models.Exercicio(**exercicio_in.model_dump())
    db.add(novo_exercicio)
    try:
        await db.commit()
        await db.refresh(novo_exercicio)
        return novo_exercicio
    except Exception as e:
        await db.rollback()
        raise e
