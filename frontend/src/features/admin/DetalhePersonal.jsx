import { createElement, useCallback, useEffect, useState } from 'react';
import {
    ArrowLeft, Ban, CheckCircle2, ChevronDown, ChevronRight, CreditCard, Eye, EyeOff,
    KeyRound, Lock, Mail, RotateCcw, ShieldCheck, UserCheck, Users, XCircle,
} from 'lucide-react';
import { adminService, operacoesService } from '../../services/api';
import { useToast } from '../../components/ToastProvider';
import { MENSALIDADE, formatarData, formatarQuando } from './formato';

function BadgeStatus({ status }) {
    const ativo = status === 'ativo';
    return (
        <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border ${
            ativo ? 'bg-success/10 text-success border-success/20' : 'bg-overlay text-text-muted border-border'
        }`}>
            {status}
        </span>
    );
}

function LinhaAluno({ aluno, aberto, onToggle, sessoes, carregando, erro }) {
    return (
        <div className="border-b border-border/60 last:border-0">
            <button
                type="button"
                onClick={onToggle}
                aria-expanded={aberto}
                aria-controls={`sessoes-aluno-${aluno.id}`}
                className="w-full flex items-center gap-3 p-4 text-left hover:bg-overlay/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
            >
                <div className="w-9 h-9 rounded-lg bg-overlay flex items-center justify-center text-text-muted shrink-0">
                    <Users size={16} />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <p className="text-sm font-bold text-text-primary truncate">{aluno.nome}</p>
                        <BadgeStatus status={aluno.status} />
                        {aluno.tem_login && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-text-muted">
                                <Lock size={10} /> login
                            </span>
                        )}
                    </div>
                    <p className="text-xs text-text-muted mt-0.5">
                        {aluno.modalidade === 'consultoria' ? 'Consultoria' : 'Presencial'}
                        {' · '}último acesso {formatarQuando(aluno.ultimo_acesso)}
                        {' · '}treinos 7d: <span className="font-bold text-text-secondary">{aluno.treinos_7d}</span>
                    </p>
                </div>
                <div className="hidden sm:block text-right mr-2">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-text-muted">Último treino</p>
                    <p className="text-xs font-semibold text-text-secondary">{formatarData(aluno.ultimo_treino)}</p>
                </div>
                {aberto ? <ChevronDown size={16} className="text-text-muted shrink-0" /> : <ChevronRight size={16} className="text-text-muted shrink-0" />}
            </button>

            {aberto && (
                <div id={`sessoes-aluno-${aluno.id}`} className="px-4 pb-4 pl-16">
                    {carregando && (
                        <p className="text-xs text-text-muted font-bold py-3 animate-pulse">Carregando sessões...</p>
                    )}
                    {erro && (
                        <p className="text-xs text-danger font-bold py-3 flex items-center gap-2">
                            <XCircle size={13} /> {erro}
                        </p>
                    )}
                    {!carregando && !erro && sessoes?.length === 0 && (
                        <p className="text-xs text-text-muted italic py-3">Nenhuma sessão registrada.</p>
                    )}
                    {!carregando && !erro && sessoes?.length > 0 && (
                        <div className="space-y-2 pt-2">
                            <p className="text-[10px] font-black uppercase tracking-widest text-text-muted">Últimas {sessoes.length} sessões</p>
                            {sessoes.map((sessao) => (
                                <div key={sessao.id} className="flex items-start gap-3 bg-overlay/60 border border-border/60 rounded-lg px-3 py-2">
                                    <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${sessao.realizada ? 'bg-success' : 'bg-warning'}`} />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs font-bold text-text-primary">
                                            {sessao.treino_nome || sessao.tipo_atividade || 'Treino'}
                                            <span className="font-medium text-text-muted"> · {formatarData(sessao.data_hora)}</span>
                                        </p>
                                        <p className="text-[10px] text-text-muted mt-0.5">
                                            {sessao.realizada ? 'Realizada' : 'Ausência'}
                                            {sessao.registrado_por ? ` · registrada por ${sessao.registrado_por}` : ''}
                                            {sessao.motivo_ausencia ? ` · ${sessao.motivo_ausencia}` : ''}
                                        </p>
                                        {sessao.observacoes_performance && (
                                            <p className="text-[10px] text-text-secondary mt-1 italic">{sessao.observacoes_performance}</p>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export function DetalhePersonal({ personal, onClose, onAtualizado }) {
    const toast = useToast();
    const [alunos, setAlunos] = useState([]);
    const [loading, setLoading] = useState(true);
    const [erro, setErro] = useState(null);
    const [abertoId, setAbertoId] = useState(null);
    const [sessoes, setSessoes] = useState({});
    const [carregandoSessoes, setCarregandoSessoes] = useState({});
    const [erroSessoes, setErroSessoes] = useState({});
    const [ativo, setAtivo] = useState(personal.is_active);
    const [acaoLoading, setAcaoLoading] = useState(false);
    const [resetAberto, setResetAberto] = useState(false);
    const [novaSenha, setNovaSenha] = useState('');
    const [mostrarSenha, setMostrarSenha] = useState(false);

    const carregarAlunos = useCallback(async () => {
        setLoading(true);
        setErro(null);
        try {
            setAlunos(await operacoesService.alunosDoPersonal(personal.id));
        } catch (err) {
            setErro(err.message || 'Erro ao carregar alunos.');
        } finally {
            setLoading(false);
        }
    }, [personal.id]);

    useEffect(() => {
        carregarAlunos();
    }, [carregarAlunos]);

    useEffect(() => {
        const onKeyDown = (event) => {
            if (event.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [onClose]);

    const carregarSessoes = async (alunoId) => {
        if (sessoes[alunoId]) return;
        setCarregandoSessoes((atual) => ({ ...atual, [alunoId]: true }));
        setErroSessoes((atual) => ({ ...atual, [alunoId]: null }));
        try {
            const data = await operacoesService.sessoesDoAluno(alunoId);
            setSessoes((atual) => ({ ...atual, [alunoId]: data }));
        } catch (err) {
            setErroSessoes((atual) => ({ ...atual, [alunoId]: err.message || 'Erro ao carregar sessões.' }));
        } finally {
            setCarregandoSessoes((atual) => ({ ...atual, [alunoId]: false }));
        }
    };

    const alternarAluno = (alunoId) => {
        if (abertoId === alunoId) {
            setAbertoId(null);
            return;
        }
        setAbertoId(alunoId);
        carregarSessoes(alunoId);
    };

    const alternarAtivo = async () => {
        const acao = ativo ? 'desativar' : 'reativar';
        if (!confirm(`Tem certeza que deseja ${acao} o acesso de ${personal.username}?`)) return;
        setAcaoLoading(true);
        try {
            await operacoesService.definirAtivo(personal.id, !ativo);
            setAtivo((v) => !v);
            toast({ tipo: 'sucesso', texto: `Acesso ${ativo ? 'desativado' : 'reativado'}.` });
            onAtualizado();
        } catch (err) {
            toast({ tipo: 'erro', texto: err.message || 'Erro ao alterar o acesso.' });
        } finally {
            setAcaoLoading(false);
        }
    };

    const resetarSenha = async (event) => {
        event.preventDefault();
        setAcaoLoading(true);
        try {
            await adminService.resetarSenha(personal.id, novaSenha);
            setNovaSenha('');
            setResetAberto(false);
            toast({ tipo: 'sucesso', texto: 'Senha redefinida.' });
        } catch (err) {
            toast({ tipo: 'erro', texto: err.message || 'Erro ao redefinir a senha.' });
        } finally {
            setAcaoLoading(false);
        }
    };

    const mensalidade = MENSALIDADE[personal.situacao_mensalidade] ?? MENSALIDADE.sem_plano;

    return (
        <div className="fixed inset-0 z-[60] bg-canvas overflow-y-auto custom-scrollbar" role="dialog" aria-modal="true" aria-label={`Detalhes de ${personal.username}`}>
            <div className="max-w-5xl mx-auto p-4 md:p-8 lg:p-12">
                <button
                    onClick={onClose}
                    className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-text-muted hover:text-text-primary transition-colors mb-6"
                >
                    <ArrowLeft size={16} /> Voltar para Operações
                </button>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
                    <div className="flex items-center gap-4 min-w-0">
                        <div className="w-12 h-12 rounded-xl bg-brand text-brand-fg flex items-center justify-center font-black text-lg shrink-0">
                            {personal.username.slice(0, 1).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                                <h1 className="text-2xl font-black text-text-primary tracking-tight truncate">{personal.username}</h1>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border ${
                                    ativo ? 'bg-success/10 text-success border-success/20' : 'bg-danger/10 text-danger border-danger/20'
                                }`}>
                                    {ativo ? 'Ativo' : 'Fora do acompanhamento'}
                                </span>
                                {personal.role === 'admin' && (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border bg-overlay text-text-muted border-border">
                                        Admin
                                    </span>
                                )}
                            </div>
                            <p className="text-sm text-text-muted flex items-center gap-2 truncate"><Mail size={13} /> {personal.email}</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                        <button
                            type="button"
                            disabled
                            title="Entra com o financeiro dos personais (etapa 4)"
                            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-overlay text-text-muted text-xs font-black uppercase tracking-widest opacity-50 cursor-not-allowed"
                        >
                            <CreditCard size={14} /> Registrar pagamento
                        </button>
                        <button
                            onClick={() => setResetAberto((v) => !v)}
                            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-overlay hover:bg-border text-text-secondary text-xs font-black uppercase tracking-widest transition-all active:scale-95"
                        >
                            <KeyRound size={14} /> Redefinir senha
                        </button>
                        <button
                            onClick={alternarAtivo}
                            disabled={acaoLoading}
                            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all active:scale-95 disabled:opacity-50 ${
                                ativo
                                    ? 'bg-danger/10 text-danger hover:bg-danger hover:text-white'
                                    : 'bg-success/10 text-success hover:bg-success hover:text-white'
                            }`}
                        >
                            {ativo ? <Ban size={14} /> : <RotateCcw size={14} />}
                            {ativo ? 'Desativar acesso' : 'Reativar acesso'}
                        </button>
                    </div>
                </div>

                {resetAberto && (
                    <form onSubmit={resetarSenha} className="mb-8 flex flex-col sm:flex-row gap-3 p-4 bg-surface border border-border rounded-2xl">
                        <div className="relative flex-1">
                            <input
                                type={mostrarSenha ? 'text' : 'password'}
                                value={novaSenha}
                                onChange={(e) => setNovaSenha(e.target.value)}
                                required
                                minLength={6}
                                placeholder="Nova senha (mín. 6 caracteres)"
                                aria-label="Nova senha"
                                className="w-full bg-overlay border border-border rounded-xl px-4 py-3 pr-11 text-sm text-text-primary font-bold focus:outline-none focus:ring-4 focus:ring-brand/10"
                            />
                            <button
                                type="button"
                                onClick={() => setMostrarSenha((v) => !v)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
                                aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
                            >
                                {mostrarSenha ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                        <button
                            type="submit"
                            disabled={acaoLoading}
                            className="px-6 py-3 rounded-xl bg-brand hover:bg-brand-hover text-brand-fg text-xs font-black uppercase tracking-widest transition-all active:scale-95 disabled:opacity-50"
                        >
                            Salvar senha
                        </button>
                    </form>
                )}

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
                    {[
                        { rotulo: 'Alunos ativos', valor: `${personal.alunos_ativos}/${personal.alunos_total}`, icone: Users },
                        { rotulo: 'Treinos 7d', valor: personal.treinos_7d, icone: CheckCircle2 },
                        { rotulo: 'Último acesso', valor: formatarQuando(personal.ultimo_acesso), icone: ShieldCheck },
                        { rotulo: 'Último treino', valor: formatarQuando(personal.ultimo_treino), icone: UserCheck },
                    ].map(({ rotulo, valor, icone: Icone }) => (
                        <div key={rotulo} className="bg-surface border border-border rounded-2xl p-4">
                            <div className="flex items-center gap-2 text-text-muted mb-2">
                                {createElement(Icone, { size: 14 })}
                                <p className="text-[10px] font-black uppercase tracking-widest">{rotulo}</p>
                            </div>
                            <p className="text-sm font-black text-text-primary">{valor}</p>
                        </div>
                    ))}
                </div>

                <div className="flex flex-wrap items-center gap-3 mb-8 text-xs text-text-muted">
                    <span className={`px-2.5 py-1 rounded-lg border font-black uppercase tracking-widest text-[10px] ${mensalidade.classe}`}>
                        Mensalidade: {mensalidade.rotulo}
                    </span>
                    <span>Na plataforma desde {formatarQuando(personal.data_criacao)}</span>
                    <span className="text-[10px] font-bold uppercase tracking-widest text-text-muted/70">
                        Plano e pagamentos do personal entram na etapa 4
                    </span>
                </div>

                <section className="bg-surface border border-border rounded-2xl overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                        <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl bg-overlay flex items-center justify-center">
                                <Users size={17} className="text-text-secondary" />
                            </div>
                            <div>
                                <h2 className="text-sm font-black text-text-primary">Alunos</h2>
                                <p className="text-xs text-text-muted">{alunos.length} cadastrado{alunos.length !== 1 ? 's' : ''}; clique para ver as últimas sessões.</p>
                            </div>
                        </div>
                        <button
                            onClick={carregarAlunos}
                            disabled={loading}
                            className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-overlay transition-all disabled:opacity-50"
                            aria-label="Atualizar alunos"
                        >
                            <RotateCcw size={15} className={loading ? 'animate-spin' : ''} />
                        </button>
                    </div>

                    {loading ? (
                        <p className="px-5 py-10 text-center text-xs font-bold text-text-muted animate-pulse">Carregando alunos...</p>
                    ) : erro ? (
                        <p className="px-5 py-10 text-center text-xs font-bold text-danger flex items-center justify-center gap-2"><XCircle size={14} /> {erro}</p>
                    ) : alunos.length === 0 ? (
                        <p className="px-5 py-10 text-center text-xs text-text-muted italic">Este personal ainda não tem alunos.</p>
                    ) : (
                        <div>
                            {alunos.map((aluno) => (
                                <LinhaAluno
                                    key={aluno.id}
                                    aluno={aluno}
                                    aberto={abertoId === aluno.id}
                                    onToggle={() => alternarAluno(aluno.id)}
                                    sessoes={sessoes[aluno.id]}
                                    carregando={carregandoSessoes[aluno.id]}
                                    erro={erroSessoes[aluno.id]}
                                />
                            ))}
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
}
