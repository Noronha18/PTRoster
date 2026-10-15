import { useState, useEffect } from 'react';
import {
    User, Target, AlertTriangle,
    Dumbbell, DollarSign, Clock, ArrowLeft,
    CheckCircle2, Trash2, Plus, Eye, ChevronDown, ChevronUp, Copy, Edit,
    ShieldCheck, Zap, BookMarked
} from 'lucide-react';
import { alunoService, treinoService } from '../../services/api';
import { ModalPlanoTreino } from './ModalPlanoTreino';
import { FormAlunoModal } from './FormAlunoModal';
import { useToast } from '../../components/ToastProvider';

const METODOS_AGRUPADORES = ["Bi-set", "Tri-set", "Giant-set", "Super-set"];

const METHOD_BG = {
    'Bi-set':    'bg-method-bi/8',
    'Tri-set':   'bg-method-tri/8',
    'Giant-set': 'bg-method-giant/8',
    'Super-set': 'bg-method-super/8',
};

const METHOD_BADGE = {
    'Bi-set':    'bg-method-bi/10 text-method-bi border-method-bi/20',
    'Tri-set':   'bg-method-tri/10 text-method-tri border-method-tri/20',
    'Giant-set': 'bg-method-giant/10 text-method-giant border-method-giant/20',
    'Super-set': 'bg-method-super/10 text-method-super border-method-super/20',
};

export const DetalheAluno = ({ alunoId, onBack }) => {
    const toast = useToast();
    const [aluno, setAluno] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isModalPlanoOpen, setIsModalPlanoOpen] = useState(false);
    const [isModalEditOpen, setIsModalEditOpen] = useState(false);
    const [planoSelecionado, setPlanoSelecionado] = useState(null);
    const [planoEdicao, setPlanoEdicao] = useState(null);
    const [expandirSessoes, setExpandirSessoes] = useState(false);
    const [expandirPagamentos, setExpandirPagamentos] = useState(false);

    const carregar = async () => {
        try {
            setLoading(true);
            const data = await alunoService.obterPorId(alunoId);
            setAluno(data);
        } catch {
            setError("Falha ao carregar prontuário");
        } finally {
            setLoading(false);
        }
    };

    const handleStatusUpdate = async (novoStatus) => {
        try {
            await alunoService.atualizarStatus(alunoId, novoStatus);
            toast({ tipo: 'sucesso', texto: `Status atualizado para ${novoStatus}.` });
            carregar();
        } catch (err) {
            toast({ tipo: 'erro', texto: 'Erro ao atualizar status: ' + err.message });
        }
    };

    const handleCheckIn = async () => {
        try {
            await alunoService.registrarPresenca(alunoId);
            toast({ tipo: 'sucesso', texto: 'Presença registrada com sucesso!' });
            carregar();
        } catch (err) {
            toast({ tipo: 'erro', texto: 'Erro ao registrar presença: ' + err.message });
        }
    };

    useEffect(() => { carregar(); }, [alunoId]);

    const handleDeleteAluno = async () => {
        if (confirm(`Tem certeza que deseja EXCLUIR permanentemente o cadastro de ${aluno.nome}? Todos os treinos e históricos serão perdidos.`)) {
            try {
                await alunoService.deletar(alunoId);
                toast({ tipo: 'sucesso', texto: 'Aluno excluído com sucesso.' });
                onBack();
            } catch (err) {
                toast({ tipo: 'erro', texto: 'Erro ao excluir aluno: ' + err.message });
            }
        }
    };

    const handleSavePlano = async (novoPlano) => {
        try {
            if (planoEdicao) {
                await treinoService.atualizarPlano(planoEdicao.id, novoPlano);
                toast({ tipo: 'sucesso', texto: 'Plano de treino atualizado com sucesso!' });
            } else {
                await treinoService.criarPlano(alunoId, novoPlano);
                toast({ tipo: 'sucesso', texto: 'Plano de treino criado com sucesso!' });
            }
            carregar();
            setIsModalPlanoOpen(false);
            setPlanoEdicao(null);
        } catch (err) {
            toast({ tipo: 'erro', texto: 'Erro ao salvar plano: ' + err.message });
        }
    };

    const handleClonarPlano = async (planoId) => {
        try {
            await treinoService.clonarPlano(planoId, alunoId);
            toast({ tipo: 'sucesso', texto: 'Plano clonado e ativado para este aluno!' });
            carregar();
        } catch (err) {
            toast({ tipo: 'erro', texto: 'Erro ao clonar plano: ' + err.message });
        }
    };

    const handleSalvarComoTemplate = async (planoId) => {
        try {
            await treinoService.clonarPlano(planoId, null);
            toast({ tipo: 'sucesso', texto: 'Plano salvo nos modelos globais!' });
        } catch (err) {
            toast({ tipo: 'erro', texto: 'Erro ao salvar modelo: ' + err.message });
        }
    };

    const handleEditPlano = (plano) => {
        setPlanoEdicao({
            id: plano.id,
            titulo: plano.titulo,
            objetivo_estrategico: plano.objetivo_estrategico,
            detalhes: plano.detalhes,
            duracao_semanas: plano.duracao_semanas,
            treinos: plano.treinos.map(t => ({
                id: t.id,
                nome: t.nome,
                prescricoes: t.prescricoes.map(p => ({
                    id: p.id,
                    exercicio_id: p.exercicio_id,
                    nome_exercicio: p.nome_exercicio || p.exercicio?.nome || 'Exercício',
                    series: p.series,
                    repeticoes: p.repeticoes,
                    carga: p.carga_kg,
                    descanso: p.tempo_descanso_segundos,
                    metodo: p.metodo,
                    observacoes: p.observacoes
                }))
            }))
        });
        setPlanoSelecionado(null);
        setIsModalPlanoOpen(true);
    };

    const handleDeletePlano = async (planoId) => {
        if (confirm("Deseja excluir este plano de treino permanentemente?")) {
            try {
                await treinoService.deletarPlano(planoId);
                toast({ tipo: 'sucesso', texto: 'Plano excluído com sucesso!' });
                setPlanoSelecionado(null);
                carregar();
            } catch (err) {
                toast({ tipo: 'erro', texto: 'Erro ao excluir plano: ' + err.message });
            }
        }
    };

    if (loading) return (
        <div className="flex flex-col items-center justify-center p-20 space-y-4">
            <div className="w-9 h-9 border-2 border-brand/20 border-t-brand rounded-full animate-spin"></div>
            <p className="text-xs font-bold text-text-secondary uppercase tracking-widest animate-pulse">Acessando Prontuário...</p>
        </div>
    );

    if (error || !aluno) return (
        <div className="p-10 text-center text-danger bg-danger/5 rounded-xl border border-danger/20">
            <p className="font-bold text-sm uppercase tracking-wide">{error || "Aluno não encontrado"}</p>
            <button onClick={onBack} className="mt-4 text-xs font-bold text-text-secondary hover:text-text-primary underline uppercase tracking-widest">Voltar para lista</button>
        </div>
    );

    const sessoesExibidas = expandirSessoes ? aluno.sessoes : aluno.sessoes?.slice(0, 3);
    const pagamentosExibidos = expandirPagamentos ? aluno.pagamentos : aluno.pagamentos?.slice(0, 3);

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700 pb-20">
            {/* Cabeçalho de Ação */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 px-2">
                <button
                    onClick={onBack}
                    className="flex items-center gap-1.5 text-text-secondary hover:text-text-primary transition-colors font-bold text-xs uppercase tracking-widest active:scale-95"
                >
                    <ArrowLeft size={14} /> Voltar para lista
                </button>

                <div className="flex flex-wrap items-center gap-2 sm:gap-3 w-full sm:w-auto">
                    {aluno.status === 'ativo' && (
                        <button
                            onClick={handleCheckIn}
                            className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-brand hover:bg-brand-hover text-brand-fg px-4 py-2 rounded-lg transition-all active:scale-95 shadow-sm"
                        >
                            <CheckCircle2 size={16} />
                            <span className="text-xs font-bold uppercase tracking-widest">Check-in</span>
                        </button>
                    )}

                    <select
                        value={aluno.status}
                        onChange={(e) => handleStatusUpdate(e.target.value)}
                        aria-label="Status do aluno"
                        className={`flex-1 sm:flex-none px-3 py-2 rounded-lg text-xs font-bold uppercase tracking-widest border border-border focus:ring-2 focus:ring-brand/10 cursor-pointer outline-none transition-all
                            ${aluno.status === 'ativo' ? 'bg-brand/10 text-brand' :
                              aluno.status === 'suspenso' ? 'bg-warning/10 text-warning' :
                              'bg-danger/10 text-danger'}`}
                    >
                        <option value="ativo">Status: Ativo</option>
                        <option value="suspenso">Status: Suspenso</option>
                        <option value="cancelado">Status: Cancelado</option>
                    </select>

                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => setIsModalEditOpen(true)}
                            className="min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted hover:text-brand hover:bg-brand/10 rounded-lg transition-colors border border-border"
                            title="Editar Cadastro"
                            aria-label="Editar cadastro do aluno"
                        >
                            <Edit size={16} />
                        </button>
                        <button
                            onClick={handleDeleteAluno}
                            className="min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors border border-border"
                            title="Excluir Aluno"
                            aria-label="Excluir aluno permanentemente"
                        >
                            <Trash2 size={16} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Grid Principal */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 sm:gap-8">

                {/* Coluna 1: Perfil e Anamnese */}
                <div className="lg:col-span-4 space-y-6">
                    <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
                        <div className="flex flex-col items-center text-center mb-8">
                            <div className="w-20 h-20 rounded-xl bg-surface-raised border border-border flex items-center justify-center mb-4">
                                <User size={32} className="text-text-muted" />
                            </div>
                            <h2 className="text-2xl font-bold text-text-primary tracking-tight">{aluno.nome}</h2>
                            <p className="text-text-secondary text-xs font-mono font-bold uppercase tracking-widest mt-1">{aluno.cpf || "CPF não informado"}</p>

                            <span className={`mt-3 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-widest border
                                ${aluno.status_financeiro === 'atrasado'
                                    ? 'bg-danger/10 text-danger border-danger/20'
                                    : 'bg-brand/10 text-brand border-brand/20'}`}>
                                {aluno.status_financeiro === 'atrasado' ? 'Pendência Financeira' : 'Situação Regular'}
                            </span>

                            {aluno.dias_para_vencimento_consultoria != null && aluno.dias_para_vencimento_consultoria <= 7 && (
                                <span className="mt-2 px-3 py-1 rounded-full text-2xs font-bold uppercase tracking-widest bg-danger/10 text-danger">
                                    {aluno.dias_para_vencimento_consultoria < 0
                                        ? 'Consultoria vencida'
                                        : `Consultoria vence em ${aluno.dias_para_vencimento_consultoria}d`}
                                </span>
                            )}
                            {aluno.dias_para_fim_programa != null && aluno.dias_para_fim_programa <= 7 && (
                                <span className="mt-2 px-3 py-1 rounded-full text-2xs font-bold uppercase tracking-widest bg-warning-subtle text-warning-text">
                                    {aluno.dias_para_fim_programa < 0
                                        ? 'Programa encerrado'
                                        : `Programa termina em ${aluno.dias_para_fim_programa}d`}
                                </span>
                            )}
                        </div>

                        <div className="space-y-4">
                            <div className="space-y-1.5">
                                <p className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                                    <Target size={12} className="text-brand" /> Objetivo Estratégico
                                </p>
                                <div className="bg-overlay p-3 rounded-lg border border-border/60">
                                    <p className="text-xs text-text-primary font-medium leading-relaxed">{aluno.objetivo || "Foco não definido"}</p>
                                </div>
                            </div>

                            <div className="space-y-1.5">
                                <p className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                                    <AlertTriangle size={12} className="text-warning" /> Observações Clínicas
                                </p>
                                <div className="bg-overlay p-3 rounded-lg border border-border/60">
                                    <p className="text-xs text-text-primary font-medium leading-relaxed">{aluno.restricoes || "Nenhuma restrição registrada"}</p>
                                </div>
                            </div>

                            {aluno.usuario && (
                                <div className="bg-brand/5 p-4 rounded-xl border border-brand/20">
                                    <p className="text-2xs font-bold text-brand uppercase tracking-widest mb-2 flex items-center gap-1.5">
                                        <ShieldCheck size={12} /> Acesso Digital
                                    </p>
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-text-primary font-bold font-mono">{aluno.usuario.username}</span>
                                        <span className="bg-brand text-brand-fg text-2xs font-bold px-2 py-0.5 rounded uppercase tracking-widest">Ativo</span>
                                    </div>
                                </div>
                            )}

                            <div className="pt-4 border-t border-border grid grid-cols-2 gap-4">
                                <div className="text-center">
                                    <p className="text-2xs font-bold text-text-muted uppercase tracking-widest mb-1">Membro desde</p>
                                    <p className="text-xs text-text-primary font-bold font-mono">{new Date(aluno.data_inicio).toLocaleDateString('pt-BR')}</p>
                                </div>
                                <div className="text-center">
                                    {aluno.modalidade === 'consultoria' ? (
                                        <>
                                            <p className="text-2xs font-bold text-text-muted uppercase tracking-widest mb-1">Consultoria até</p>
                                            <p className={`text-xs font-bold font-mono ${aluno.dias_para_vencimento_consultoria < 0 ? 'text-danger' : 'text-text-primary'}`}>
                                                {aluno.data_vencimento_consultoria
                                                    ? new Date(aluno.data_vencimento_consultoria + 'T00:00').toLocaleDateString('pt-BR')
                                                    : 'SEM DATA'}
                                            </p>
                                        </>
                                    ) : aluno.tipo_pagamento === 'pacote' ? (
                                        <>
                                            <p className="text-2xs font-bold text-text-muted uppercase tracking-widest mb-1">Créditos</p>
                                            <p className={`text-xs font-bold font-mono ${aluno.saldo_aulas > 0 ? 'text-brand' : 'text-danger'}`}>
                                                {aluno.saldo_aulas} AULAS
                                            </p>
                                        </>
                                    ) : (
                                        <>
                                            <p className="text-2xs font-bold text-text-muted uppercase tracking-widest mb-1">Vencimento</p>
                                            <p className="text-xs text-text-primary font-bold font-mono">DIA {aluno.dia_vencimento}</p>
                                        </>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Coluna 2 e 3: Treinos e Histórico */}
                <div className="lg:col-span-8 space-y-6">

                    {/* Planos de Treino */}
                    <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-lg font-bold text-text-primary tracking-tight flex items-center gap-3">
                                <Dumbbell className="text-brand" size={18} /> Planos de Treino
                            </h3>
                            <button
                                onClick={() => setIsModalPlanoOpen(true)}
                                className="bg-brand hover:bg-brand-hover text-brand-fg p-2 rounded-lg transition-all shadow-sm active:scale-95"
                            >
                                <Plus size={16} />
                            </button>
                        </div>

                        {aluno.planos_treino?.length > 0 ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {aluno.planos_treino.map(plano => (
                                    <div key={plano.id} className={`p-5 border rounded-xl flex flex-col justify-between transition-all ${plano.esta_ativo ? 'bg-brand/5 border-brand/20 ring-1 ring-brand/5' : 'bg-overlay border-border opacity-75'}`}>
                                        <div className="mb-4">
                                            <div className="flex justify-between items-start gap-2">
                                                <p className="font-bold text-text-primary text-base tracking-tight leading-tight">{plano.titulo}</p>
                                                {plano.esta_ativo && <span className="bg-brand text-brand-fg text-2xs font-bold px-2 py-0.5 rounded uppercase tracking-widest">Ativo</span>}
                                            </div>
                                            <p className="text-xs text-text-secondary font-bold uppercase tracking-widest mt-1.5 font-mono">
                                                {plano.duracao_semanas} SEMANAS · {new Date(plano.data_inicio).toLocaleDateString('pt-BR')}
                                            </p>
                                        </div>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setPlanoSelecionado(plano)}
                                                className="flex-1 flex items-center justify-center gap-2 py-2 bg-surface border border-border hover:bg-overlay text-text-primary rounded-lg text-xs font-bold uppercase tracking-widest transition-all shadow-sm"
                                            >
                                                <Eye size={14} /> Detalhes
                                            </button>
                                            <button
                                                onClick={() => handleSalvarComoTemplate(plano.id)}
                                                className="p-2 bg-surface border border-border hover:border-brand/40 hover:bg-brand/5 text-text-muted hover:text-brand rounded-lg transition-all"
                                                title="Salvar como modelo global"
                                            >
                                                <BookMarked size={14} />
                                            </button>
                                            {!plano.esta_ativo && (
                                                <button
                                                    onClick={() => handleClonarPlano(plano.id)}
                                                    className="p-2 bg-surface border border-border hover:border-brand/40 hover:bg-brand/5 text-brand rounded-lg transition-all"
                                                    title="Reativar Plano"
                                                >
                                                    <Copy size={14} />
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-10 border border-dashed border-border rounded-xl text-text-muted italic text-xs bg-overlay/50">
                                Nenhum plano de treinamento registrado.
                            </div>
                        )}
                    </div>

                    {/* Histórico */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
                        <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
                            <h3 className="text-xs font-bold text-text-muted uppercase tracking-widest mb-4 flex items-center gap-2">
                                <Clock size={14} className="text-brand" /> Registro de Frequência
                            </h3>
                            <div className="space-y-0.5">
                                {sessoesExibidas?.map(sessao => (
                                    <div key={sessao.id} className="flex items-center justify-between py-2 border-b border-border-faint last:border-0">
                                        <span className="text-xs text-text-secondary font-bold font-mono uppercase">{new Date(sessao.data_hora).toLocaleDateString('pt-BR')}</span>
                                        <span className={`text-xs font-bold uppercase tracking-widest px-2 py-0.5 rounded ${sessao.realizada ? "bg-brand/10 text-brand" : "bg-danger/10 text-danger"}`}>
                                            {sessao.realizada ? "Presença" : "Falta"}
                                        </span>
                                    </div>
                                )) || (
                                    <p className="text-xs text-text-muted italic py-4">Sem histórico registrado.</p>
                                )}
                                {aluno.sessoes?.length > 3 && (
                                    <button
                                        onClick={() => setExpandirSessoes(!expandirSessoes)}
                                        className="w-full text-center pt-3 text-xs font-bold text-brand hover:text-brand-hover uppercase tracking-widest flex items-center justify-center gap-1 transition-colors"
                                    >
                                        {expandirSessoes ? <><ChevronUp size={12} /> Recolher</> : <><ChevronDown size={12} /> Ver Histórico Completo ({aluno.sessoes.length})</>}
                                    </button>
                                )}
                            </div>
                        </div>

                        <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
                            <h3 className="text-xs font-bold text-text-muted uppercase tracking-widest mb-4 flex items-center gap-2">
                                <DollarSign size={14} className="text-brand" /> Histórico Financeiro
                            </h3>
                            <div className="space-y-0.5">
                                {pagamentosExibidos?.map(pag => (
                                    <div key={pag.id} className="flex items-center justify-between py-2 border-b border-border-faint last:border-0">
                                        <span className="text-xs text-text-secondary font-bold uppercase tracking-widest">Ref: {pag.referencia_mes}</span>
                                        <span className="text-xs text-text-primary font-bold font-mono tabular-nums">{new Intl.NumberFormat('pt-BR', {style: 'currency', currency:'BRL'}).format(pag.valor)}</span>
                                    </div>
                                )) || (
                                    <p className="text-xs text-text-muted italic py-4">Sem registros financeiros.</p>
                                )}
                                {aluno.pagamentos?.length > 3 && (
                                    <button
                                        onClick={() => setExpandirPagamentos(!expandirPagamentos)}
                                        className="w-full text-center pt-3 text-xs font-bold text-brand hover:text-brand-hover uppercase tracking-widest flex items-center justify-center gap-1 transition-colors"
                                    >
                                        {expandirPagamentos ? <><ChevronUp size={12} /> Recolher</> : <><ChevronDown size={12} /> Ver Todos ({aluno.pagamentos.length})</>}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>

                </div>
            </div>

            {/* Modais */}
            <ModalPlanoTreino
                isOpen={isModalPlanoOpen}
                onClose={() => { setIsModalPlanoOpen(false); setPlanoEdicao(null); }}
                onSave={handleSavePlano}
                planoEdicao={planoEdicao}
            />

            <FormAlunoModal
                isOpen={isModalEditOpen}
                onClose={() => setIsModalEditOpen(false)}
                onSuccess={carregar}
                alunoEdicao={aluno}
            />

            {/* Modal de Visualização de Plano */}
            {planoSelecionado && (
                <div className="fixed inset-0 z-[60] flex items-end md:items-center justify-center p-0 md:p-4 bg-text-ink/40 backdrop-blur-sm animate-in fade-in duration-300">
                    <div
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="plano-modal-titulo"
                        className="bg-canvas w-full max-w-5xl h-[92vh] md:h-[85vh] overflow-hidden rounded-t-xl md:rounded-xl shadow-2xl flex flex-col animate-in slide-in-from-bottom-8 duration-500 border border-border"
                    >
                        <div className="p-6 sm:p-8 border-b border-border flex justify-between items-start bg-surface">
                            <div>
                                <h2 id="plano-modal-titulo" className="text-2xl font-bold text-text-primary tracking-tight">{planoSelecionado.titulo}</h2>
                                <div className="flex flex-col gap-1.5 mt-2">
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs font-bold text-text-muted uppercase tracking-widest">Foco do Plano:</span>
                                        <span className="text-xs text-text-primary font-semibold">{planoSelecionado.objetivo_estrategico || "Técnico"}</span>
                                    </div>
                                    {planoSelecionado.detalhes && (
                                        <p className="text-xs text-text-secondary leading-relaxed max-w-2xl bg-overlay p-3 rounded-lg border border-border mt-1 italic">
                                            "{planoSelecionado.detalhes}"
                                        </p>
                                    )}
                                </div>
                            </div>
                            <button
                                onClick={() => setPlanoSelecionado(null)}
                                className="min-w-[44px] min-h-[44px] flex items-center justify-center bg-overlay text-text-muted hover:text-text-primary hover:bg-border rounded-lg transition-all"
                                aria-label="Fechar plano"
                            >
                                <Plus size={20} className="rotate-45" aria-hidden="true" />
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-10 bg-canvas">
                            {planoSelecionado.treinos?.map(treino => (
                                <div key={treino.id} className="space-y-4">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 bg-brand text-brand-fg rounded-lg flex items-center justify-center font-bold text-lg shadow-sm">
                                            {treino.nome}
                                        </div>
                                        <div>
                                            <h4 className="text-lg font-bold text-text-primary tracking-tight">{treino.descricao || `Divisão ${treino.nome}`}</h4>
                                            <p className="text-xs text-text-muted font-bold uppercase tracking-widest mt-0.5">{treino.prescricoes?.length || 0} exercícios prescritos</p>
                                        </div>
                                    </div>
                                    <div className="flex flex-col gap-1.5">
                                        {treino.prescricoes?.map((presc, idx) => {
                                            const prescricoes = treino.prescricoes;
                                            const isGrouping = METODOS_AGRUPADORES.includes(presc.metodo);
                                            const prevIsSame = idx > 0 && prescricoes[idx - 1].metodo === presc.metodo && isGrouping;
                                            const nextIsSame = idx < prescricoes.length - 1 && prescricoes[idx + 1].metodo === presc.metodo && isGrouping;

                                            const groupClasses = [
                                                prevIsSame ? 'mt-0 border-t-0 rounded-t-none' : 'rounded-t-lg mt-1.5 shadow-sm',
                                                nextIsSame ? 'mb-0 rounded-b-none' : 'rounded-b-lg mb-1.5 shadow-sm',
                                            ].join(' ');

                                            const methodBg = isGrouping ? (METHOD_BG[presc.metodo] ?? '') : '';

                                            return (
                                                <div
                                                    key={presc.id || idx}
                                                    className={`p-4 bg-surface border border-border flex justify-between items-center transition-all ${groupClasses} ${methodBg}`}
                                                >
                                                    <div className="space-y-2.5 flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            <p className="font-bold text-text-primary text-sm leading-tight">{presc.nome_exercicio}</p>
                                                            {presc.metodo && presc.metodo !== 'Convencional' && (
                                                                <span className={`text-2xs font-bold px-1.5 py-0.5 rounded border uppercase tracking-widest ${METHOD_BADGE[presc.metodo] ?? 'bg-overlay text-text-secondary border-border'}`}>
                                                                    {presc.metodo}
                                                                </span>
                                                            )}
                                                            {presc.exercicio?.video_url && (
                                                                <a
                                                                    href={presc.exercicio.video_url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="p-1 text-accent hover:text-accent-hover transition-colors shrink-0"
                                                                    title="Ver Demonstração"
                                                                    onClick={(e) => e.stopPropagation()}
                                                                >
                                                                    <Zap size={14} />
                                                                </a>
                                                            )}
                                                        </div>
                                                        <div className="flex flex-wrap gap-2">
                                                            <span className="text-xs font-bold font-mono text-text-secondary bg-overlay px-2 py-0.5 rounded border border-border uppercase tracking-tight">{presc.series} séries</span>
                                                            <span className="text-xs font-bold font-mono text-text-secondary bg-overlay px-2 py-0.5 rounded border border-border uppercase tracking-tight">{presc.repeticoes} reps</span>
                                                            {presc.observacoes && (
                                                                <span className="w-full text-xs text-accent-text font-bold uppercase tracking-widest mt-0.5 block leading-relaxed">
                                                                    Nota: {presc.observacoes}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <div className="text-right shrink-0 ml-4">
                                                        <p className="text-xl font-bold font-mono text-accent tabular-nums tracking-tighter">{presc.carga_kg}KG</p>
                                                        {(!nextIsSame || !isGrouping) && (
                                                            <p className="text-xs text-text-muted font-bold uppercase tracking-widest mt-0.5 font-mono">{presc.tempo_descanso_segundos}S OFF</p>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="p-6 sm:p-8 bg-surface flex flex-col md:flex-row justify-end gap-3 border-t border-border">
                            <button
                                onClick={() => handleEditPlano(planoSelecionado)}
                                className="px-6 py-2.5 bg-overlay hover:bg-border text-text-primary rounded-lg text-xs font-bold uppercase tracking-widest transition-all border border-border"
                            >
                                Editar Plano
                            </button>
                            <button
                                onClick={() => handleDeletePlano(planoSelecionado.id)}
                                className="px-6 py-2.5 bg-danger/5 text-danger hover:bg-danger hover:text-brand-fg border border-danger/20 rounded-lg text-xs font-bold uppercase tracking-widest transition-all"
                            >
                                Excluir Plano
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
