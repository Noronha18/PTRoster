import { createElement, useCallback, useEffect, useMemo, useState } from 'react';
import {
    Activity, AlertTriangle, ChevronDown, ChevronRight, Clock,
    RefreshCw, Shield, UserCheck, UserPlus, Users, X, XCircle,
} from 'lucide-react';
import { operacoesService } from '../../services/api';
import { FormCadastrarTrainer } from './FormCadastrarTrainer';
import { DetalhePersonal } from './DetalhePersonal';
import { MENSALIDADE, alertasPersonal, formatarData, formatarQuando, semAtividade } from './formato';

const TOM_ALERTA = {
    danger: 'bg-danger/10 text-danger border-danger/20',
    warn: 'bg-warning/10 text-warning border-warning/20',
    muted: 'bg-overlay text-text-muted border-border',
};

function BadgeMensalidade({ situacao, diasAtraso = 0 }) {
    const dados = MENSALIDADE[situacao] ?? MENSALIDADE.sem_plano;
    return (
        <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border ${dados.classe}`}>
            {dados.rotulo}{situacao === 'atrasada' && diasAtraso > 0 ? ` · ${diasAtraso}d` : ''}
        </span>
    );
}

function BadgeAlertas({ personal }) {
    const alertas = alertasPersonal(personal);
    if (alertas.length === 0) {
        return <span className="text-xs text-text-muted">—</span>;
    }
    return (
        <div className="flex flex-wrap gap-1">
            {alertas.map((alerta) => (
                <span key={alerta.id} className={`px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wide border ${TOM_ALERTA[alerta.tom]}`}>
                    {alerta.texto}
                </span>
            ))}
        </div>
    );
}

function CelulaPersonal({ personal }) {
    return (
        <div className="flex items-center gap-3 min-w-0">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-black text-sm shrink-0 ${
                personal.is_active ? 'bg-brand text-brand-fg' : 'bg-overlay text-text-muted'
            }`}>
                {personal.username.slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                    <p className="text-sm font-bold text-text-primary truncate">{personal.username}</p>
                    {personal.role === 'admin' && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wide border bg-overlay text-text-muted border-border">
                            admin
                        </span>
                    )}
                </div>
                <p className="text-xs text-text-muted truncate">{personal.email}</p>
            </div>
        </div>
    );
}

function TabelaPersonais({ personais, onSelect }) {
    return (
        <div className="hidden lg:block bg-surface border border-border rounded-2xl overflow-hidden">
            <table className="w-full text-left">
                <thead>
                    <tr className="border-b border-border text-[10px] font-black uppercase tracking-widest text-text-muted">
                        <th className="px-5 py-3 font-black">Personal</th>
                        <th className="px-5 py-3 font-black">Alunos ativos</th>
                        <th className="px-5 py-3 font-black">Último acesso</th>
                        <th className="px-5 py-3 font-black">Treinos 7d</th>
                        <th className="px-5 py-3 font-black">Mensalidade</th>
                        <th className="px-5 py-3 font-black">Alertas</th>
                        <th className="px-3 py-3" aria-hidden="true" />
                    </tr>
                </thead>
                <tbody>
                    {personais.map((personal) => (
                        <tr
                            key={personal.id}
                            tabIndex={0}
                            onClick={() => onSelect(personal)}
                            onKeyDown={(event) => {
                                if (event.key === 'Enter' || event.key === ' ') {
                                    event.preventDefault();
                                    onSelect(personal);
                                }
                            }}
                            aria-label={`Abrir operações de ${personal.username}`}
                            className="border-b border-border/60 last:border-0 hover:bg-overlay/50 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
                        >
                            <td className="px-5 py-3"><CelulaPersonal personal={personal} /></td>
                            <td className="px-5 py-3 text-sm font-bold text-text-secondary">{personal.alunos_ativos}/{personal.alunos_total}</td>
                            <td className="px-5 py-3 text-xs text-text-secondary whitespace-nowrap">{formatarQuando(personal.ultimo_acesso)}</td>
                            <td className="px-5 py-3 text-sm font-black text-text-primary">{personal.treinos_7d}</td>
                            <td className="px-5 py-3"><BadgeMensalidade situacao={personal.situacao_mensalidade} diasAtraso={personal.dias_atraso} /></td>
                            <td className="px-5 py-3"><BadgeAlertas personal={personal} /></td>
                            <td className="px-3 py-3 text-right">
                                <ChevronRight size={16} className="text-text-muted inline" />
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function CartoesPersonais({ personais, onSelect }) {
    return (
        <div className="lg:hidden space-y-3">
            {personais.map((personal) => (
                <button
                    key={personal.id}
                    type="button"
                    onClick={() => onSelect(personal)}
                    className="w-full text-left bg-surface border border-border rounded-2xl p-4 hover:bg-overlay/50 transition-colors active:scale-[0.995] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
                    aria-label={`Abrir operações de ${personal.username}`}
                >
                    <div className="flex items-start justify-between gap-3">
                        <CelulaPersonal personal={personal} />
                        <ChevronRight size={16} className="text-text-muted mt-2 shrink-0" />
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-4">
                        <div>
                            <p className="text-[9px] font-black uppercase tracking-widest text-text-muted">Alunos</p>
                            <p className="text-sm font-black text-text-primary">{personal.alunos_ativos}/{personal.alunos_total}</p>
                        </div>
                        <div>
                            <p className="text-[9px] font-black uppercase tracking-widest text-text-muted">Treinos 7d</p>
                            <p className="text-sm font-black text-text-primary">{personal.treinos_7d}</p>
                        </div>
                        <div>
                            <p className="text-[9px] font-black uppercase tracking-widest text-text-muted">Último acesso</p>
                            <p className="text-xs font-bold text-text-secondary">{formatarData(personal.ultimo_acesso)}</p>
                        </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 mt-3">
                        <BadgeMensalidade situacao={personal.situacao_mensalidade} diasAtraso={personal.dias_atraso} />
                        <BadgeAlertas personal={personal} />
                    </div>
                </button>
            ))}
        </div>
    );
}

function ListaPersonais({ personais, loading, erro, onSelect, onRetry }) {
    if (loading) {
        return (
            <div className="bg-surface border border-border rounded-2xl py-16 flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-brand/20 border-t-brand rounded-full animate-spin" />
                <p className="text-xs font-bold uppercase tracking-widest text-text-muted">Carregando operações...</p>
            </div>
        );
    }
    if (erro) {
        return (
            <div className="bg-surface border border-border rounded-2xl py-12 flex flex-col items-center gap-3">
                <p className="text-xs font-bold text-danger flex items-center gap-2"><XCircle size={14} /> {erro}</p>
                <button onClick={onRetry} className="px-4 py-2 rounded-xl bg-overlay hover:bg-border text-xs font-black uppercase tracking-widest text-text-secondary transition-all">
                    Tentar novamente
                </button>
            </div>
        );
    }
    if (personais.length === 0) {
        return (
            <div className="bg-surface border border-dashed border-border rounded-2xl py-16 text-center">
                <p className="text-sm text-text-muted italic">Nenhum personal nesta categoria.</p>
            </div>
        );
    }
    return (
        <>
            <TabelaPersonais personais={personais} onSelect={onSelect} />
            <CartoesPersonais personais={personais} onSelect={onSelect} />
        </>
    );
}

export function PainelAdmin() {
    const [personais, setPersonais] = useState([]);
    const [loading, setLoading] = useState(true);
    const [erro, setErro] = useState(null);
    const [filtro, setFiltro] = useState('ativos');
    const [selecionado, setSelecionado] = useState(null);
    const [cadastroAberto, setCadastroAberto] = useState(false);
    const [foraAberto, setForaAberto] = useState(false);

    const carregar = useCallback(async () => {
        setLoading(true);
        setErro(null);
        try {
            setPersonais(await operacoesService.listarPersonais());
        } catch (err) {
            setErro(err.message || 'Erro ao carregar operações.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        carregar();
    }, [carregar]);

    const ativos = useMemo(() => personais.filter((p) => p.is_active), [personais]);
    const fora = useMemo(() => personais.filter((p) => !p.is_active), [personais]);
    const semAtividadeAgora = useMemo(() => ativos.filter((p) => semAtividade(p)), [ativos]);
    const semAlunos = useMemo(() => ativos.filter((p) => p.alunos_ativos === 0), [ativos]);
    const atrasados = useMemo(() => ativos.filter((p) => p.situacao_mensalidade === 'atrasada'), [ativos]);
    const vencemEmBreve = useMemo(() => ativos.filter((p) => p.situacao_mensalidade === 'vence_em_breve'), [ativos]);

    const filtros = [
        { id: 'ativos', rotulo: 'Personais ativos', quantidade: ativos.length, icone: UserCheck },
        { id: 'sem_atividade', rotulo: 'Sem atividade há 7 dias', quantidade: semAtividadeAgora.length, icone: Activity },
        { id: 'sem_alunos', rotulo: 'Sem alunos', quantidade: semAlunos.length, icone: Users },
        { id: 'mensalidade_atrasada', rotulo: 'Mensalidade atrasada', quantidade: atrasados.length, icone: AlertTriangle },
        { id: 'vence_breve', rotulo: 'Vence em até 3 dias', quantidade: vencemEmBreve.length, icone: Clock },
    ];

    const filtrados = (() => {
        if (filtro === 'sem_atividade') return semAtividadeAgora;
        if (filtro === 'sem_alunos') return semAlunos;
        if (filtro === 'mensalidade_atrasada') return atrasados;
        if (filtro === 'vence_breve') return vencemEmBreve;
        return ativos;
    })();

    const filtroAtual = filtros.find((f) => f.id === filtro) ?? filtros[0];

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 px-2">
                <div className="flex items-center gap-3">
                    <Shield size={20} className="text-brand" />
                    <div>
                        <h1 className="text-xl font-black text-text-primary tracking-tight">Operações</h1>
                        <p className="text-xs text-text-muted">Personais, alunos e sinais de uso da plataforma.</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={carregar}
                        disabled={loading}
                        className="p-2.5 rounded-xl text-text-muted hover:text-text-primary hover:bg-overlay transition-all disabled:opacity-50"
                        aria-label="Atualizar operações"
                    >
                        <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    </button>
                    <button
                        onClick={() => setCadastroAberto(true)}
                        className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand hover:bg-brand-hover text-brand-fg text-xs font-black uppercase tracking-widest transition-all active:scale-95 shadow-sm"
                    >
                        <UserPlus size={15} /> Cadastrar personal
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 px-2">
                {filtros.map(({ id, rotulo, quantidade, icone: Icone, desabilitado }) => {
                    const ativo = filtro === id && !desabilitado;
                    return (
                        <button
                            key={id}
                            type="button"
                            onClick={() => !desabilitado && setFiltro(id)}
                            disabled={desabilitado}
                            aria-pressed={ativo}
                            title={desabilitado ? 'Disponível quando o financeiro dos personais entrar (etapa 4)' : undefined}
                            className={`text-left px-4 py-3 rounded-xl border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30 ${
                                ativo
                                    ? 'bg-brand text-brand-fg border-brand shadow-sm'
                                    : desabilitado
                                        ? 'bg-surface/60 text-text-muted border-border/60 cursor-not-allowed opacity-60'
                                        : 'bg-surface text-text-secondary border-border hover:bg-overlay'
                            }`}
                        >
                            <div className="flex items-center justify-between gap-2">
                                {createElement(Icone, { size: 14, className: 'shrink-0' })}
                                <span className="text-lg font-black leading-none">{quantidade}</span>
                            </div>
                            <p className="text-[10px] font-black uppercase tracking-widest mt-2 leading-tight">{rotulo}</p>
                        </button>
                    );
                })}
            </div>

            <div className="px-2">
                <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-bold text-text-muted">
                        {filtroAtual.rotulo} · {filtrados.length}
                    </p>
                    {filtro !== 'ativos' && filtrados.length === 0 && (
                        <button
                            onClick={() => setFiltro('ativos')}
                            className="text-[10px] font-black uppercase tracking-widest text-brand hover:underline"
                        >
                            Limpar filtro
                        </button>
                    )}
                </div>
                <ListaPersonais
                    personais={filtrados}
                    loading={loading}
                    erro={erro}
                    onSelect={setSelecionado}
                    onRetry={carregar}
                />
            </div>

            {fora.length > 0 && (
                <div className="px-2">
                    <button
                        onClick={() => setForaAberto((v) => !v)}
                        aria-expanded={foraAberto}
                        className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-text-muted hover:text-text-primary transition-colors"
                    >
                        {foraAberto ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        Fora do acompanhamento ({fora.length})
                    </button>
                    {foraAberto && (
                        <div className="mt-3 opacity-80">
                            <TabelaPersonais personais={fora} onSelect={setSelecionado} />
                            <CartoesPersonais personais={fora} onSelect={setSelecionado} />
                        </div>
                    )}
                </div>
            )}

            {cadastroAberto && (
                <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
                    <div className="w-full max-w-md bg-surface border border-border rounded-2xl p-6 shadow-2xl">
                        <div className="flex justify-end -mt-2 -mr-2">
                            <button
                                onClick={() => setCadastroAberto(false)}
                                className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-overlay transition-all"
                                aria-label="Fechar cadastro"
                            >
                                <X size={18} />
                            </button>
                        </div>
                        <FormCadastrarTrainer
                            onSuccess={() => {
                                setCadastroAberto(false);
                                carregar();
                            }}
                            onCancel={() => setCadastroAberto(false)}
                        />
                    </div>
                </div>
            )}

            {selecionado && (
                <DetalhePersonal
                    personal={selecionado}
                    onClose={() => setSelecionado(null)}
                    onAtualizado={carregar}
                />
            )}
        </div>
    );
}
