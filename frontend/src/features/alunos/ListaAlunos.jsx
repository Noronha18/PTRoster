import { useEffect, useState } from 'react';
import { ChevronRight, Plus, UserCircle2, CheckCircle2, ArrowDown, ArrowUp, Search } from 'lucide-react';
import { alunoService } from '../../services/api';
import { FormAlunoModal } from './FormAlunoModal';
import { filtrarAlunos } from './listaAlunos';
import { CardAvisos } from './CardAvisos';
import { AtividadeRecente } from '../sessoes/AtividadeRecente';
import { useToast } from '../../components/ToastProvider';

export const ListaAlunosFeature = ({ onSelectAluno }) => {
    const toast = useToast();
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [alunos, setAlunos] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [abaStatus, setAbaStatus] = useState('ativos');
    const [busca, setBusca] = useState('');
    const [ordem, setOrdem] = useState('asc');

    const carregarAlunos = async () => {
        try {
            setLoading(true);
            const data = await alunoService.listar();
            setAlunos(data);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleCheckIn = async (e, alunoId) => {
        e.stopPropagation();
        try {
            await alunoService.registrarPresenca(alunoId);
            carregarAlunos();
            toast({ tipo: 'sucesso', texto: 'Presença registrada com sucesso!' });
        } catch (err) {
            toast({ tipo: 'erro', texto: 'Erro ao registrar presença: ' + err.message });
        }
    };

    useEffect(() => {
        carregarAlunos();
    }, []);

    const alunosFiltrados = filtrarAlunos(alunos, abaStatus, busca, ordem);
    const temBusca = Boolean(busca.trim());
    const RotuloOrdem = ordem === 'asc' ? ArrowDown : ArrowUp;

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-32 space-y-4">
                <div className="w-10 h-10 border-2 border-brand/20 border-t-brand rounded-full animate-spin"></div>
                <p className="text-text-secondary text-xs font-bold uppercase tracking-widest animate-pulse">Sincronizando dados...</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 sm:space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="flex flex-wrap justify-between items-center gap-3 px-2">
                <div>
                    <h2 className="text-2xl sm:text-3xl font-bold text-text-primary tracking-tight">Alunos</h2>
                    <p className="text-text-secondary text-xs sm:text-sm font-medium">Gestão de performance e frequência.</p>
                </div>
                <button
                    onClick={() => setIsModalOpen(true)}
                    className="bg-brand hover:bg-brand-hover text-brand-fg p-3 rounded-xl font-bold transition-all shadow-sm active:scale-95 flex items-center gap-2"
                >
                    <Plus size={20} />
                    <span className="text-xs font-semibold">Novo aluno</span>
                </button>
            </div>

            <div role="search" aria-label="Buscar alunos" className="flex flex-wrap items-center gap-2 px-2">
                <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-border bg-surface px-3 focus-within:ring-2 focus-within:ring-brand/30">
                    <Search size={18} className="shrink-0 text-text-muted" aria-hidden="true" />
                    <span className="sr-only">Buscar aluno pelo nome</span>
                    <input
                        type="search"
                        value={busca}
                        onChange={(e) => setBusca(e.target.value)}
                        placeholder="Buscar aluno pelo nome"
                        className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none"
                    />
                </label>
                {busca && (
                    <button type="button" onClick={() => setBusca('')} className="min-h-11 px-3 text-sm font-semibold text-brand">
                        Limpar busca
                    </button>
                )}
            </div>

            <div
                role="tablist"
                aria-label="Filtrar alunos por status"
                className="flex p-1 bg-overlay rounded-xl border border-border mx-2 w-fit"
            >
                {[
                    { id: 'ativos', label: 'Ativos' },
                    { id: 'inativos', label: 'Inativos' }
                ].map((aba) => (
                    <button
                        key={aba.id}
                        role="tab"
                        aria-selected={abaStatus === aba.id}
                        onClick={() => setAbaStatus(aba.id)}
                        className={`px-5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 whitespace-nowrap ${
                            abaStatus === aba.id
                                ? 'bg-surface text-text-primary shadow-sm ring-1 ring-text-ink/5'
                                : 'text-text-secondary hover:text-text-primary'
                        }`}
                    >
                        {aba.label}
                    </button>
                ))}
            </div>

            {error && (
                <div className="p-4 bg-danger/10 border border-danger/20 text-danger text-xs font-bold uppercase tracking-wide rounded-xl mx-2">
                    Erro ao carregar: {error}
                </div>
            )}

            {!error && (
                <div className="flex items-center justify-between gap-2 px-2">
                    <p role="status" className="text-sm text-text-secondary">
                        {alunosFiltrados.length} {alunosFiltrados.length === 1 ? 'aluno' : 'alunos'}
                    </p>
                    {alunosFiltrados.length > 1 && (
                        <button
                            type="button"
                            onClick={() => setOrdem(ordem === 'asc' ? 'desc' : 'asc')}
                            aria-label={ordem === 'asc' ? 'Ordenar nomes de Z a A' : 'Ordenar nomes de A a Z'}
                            className="hidden min-h-11 items-center gap-1 px-2 text-sm font-semibold text-text-secondary sm:flex"
                        >
                            <RotuloOrdem size={16} aria-hidden="true" />
                            Nome ({ordem === 'asc' ? 'A–Z' : 'Z–A'})
                        </button>
                    )}
                </div>
            )}

            {alunosFiltrados.length === 0 ? !error && (
                <div className="py-20 sm:py-32 border border-dashed border-border rounded-xl text-center mx-2 bg-surface/50">
                    <p className="text-text-muted font-medium italic">{temBusca ? "Nenhum aluno corresponde à busca." : "Nenhum aluno nesta categoria."}</p>
                </div>
            ) : (
                <div className="mx-2 bg-surface border border-border rounded-xl overflow-hidden shadow-sm">
                    {alunosFiltrados.map((aluno, idx) => (
                        <div
                            key={aluno.id}
                            role="button"
                            tabIndex={0}
                            onClick={() => onSelectAluno(aluno.id)}
                            onKeyDown={(e) => {
                                if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
                                    e.preventDefault();
                                    onSelectAluno(aluno.id);
                                }
                            }}
                            aria-label={`Ver prontuário de ${aluno.nome}`}
                            className={`group flex items-center gap-3 sm:gap-4 p-4 transition-colors duration-150 cursor-pointer hover:bg-overlay active:bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30
                                ${idx !== alunosFiltrados.length - 1 ? 'border-b border-border/60' : ''}
                                ${aluno.status !== 'ativo' ? 'opacity-75' : ''}`}
                        >
                            <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-lg bg-overlay flex items-center justify-center text-text-muted group-hover:bg-brand/10 group-hover:text-brand transition-colors">
                                <UserCircle2 size={22} />
                            </div>

                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <h3 className="text-text-primary font-semibold text-sm sm:text-base truncate">{aluno.nome}</h3>
                                    {aluno.usuario && (
                                        <div className="p-1 bg-brand-subtle text-brand rounded-md" title={`Acesso liberado: ${aluno.usuario.username}`}>
                                            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                        </div>
                                    )}
                                </div>
                                <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 mt-0.5">
                                    <p className="text-text-secondary text-xs font-mono tracking-tight uppercase">{aluno.cpf || "Sem CPF"}</p>
                                    <span className="w-1 h-1 rounded-full bg-border hidden sm:inline" />
                                    <p className="text-xs text-text-secondary font-medium">
                                        {aluno.modalidade === 'consultoria'
                                            ? `Consultoria${aluno.data_vencimento_consultoria ? ` · vence ${new Date(aluno.data_vencimento_consultoria + 'T00:00').toLocaleDateString('pt-BR')}` : ''}`
                                            : aluno.tipo_pagamento === 'pacote'
                                                ? `${aluno.saldo_aulas} aulas restantes`
                                                : 'Presencial · mensal'}
                                    </p>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 sm:gap-4">
                                {aluno.status === 'ativo' && (
                                    <button
                                        onClick={(e) => handleCheckIn(e, aluno.id)}
                                        className="p-2 bg-brand/10 text-brand hover:bg-brand hover:text-brand-fg rounded-lg transition-all active:scale-95 flex items-center gap-2"
                                        title="Registrar Presença"
                                    >
                                        <CheckCircle2 size={16} />
                                        <span className="hidden lg:inline text-xs font-bold uppercase tracking-widest">Presença</span>
                                    </button>
                                )}
                                <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-widest border
                                    ${aluno.status_financeiro === 'atrasado'
                                        ? 'bg-danger/10 text-danger border-danger/20'
                                        : 'bg-brand/10 text-brand border-brand/20'
                                    }`}>
                                    {aluno.status_financeiro === 'atrasado' ? 'Pendência' : 'Em dia'}
                                </span>
                                <ChevronRight className="text-text-muted group-hover:text-text-secondary transition-colors shrink-0" size={16} />
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <CardAvisos onSelectAluno={onSelectAluno} />
            <AtividadeRecente onSelectAluno={onSelectAluno} />

            <FormAlunoModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onSuccess={carregarAlunos}
            />
        </div>
    );
};
