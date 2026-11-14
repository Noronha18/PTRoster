import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, DollarSign, RefreshCw, Users, XCircle } from 'lucide-react';
import { financeiroPersonalService } from '../../services/api';
import { MENSALIDADE, formatarDia } from '../admin/formato';

const brl = (valor) => new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
}).format(Number(valor || 0));

function BadgeSituacao({ situacao, diasAtraso = 0 }) {
    const dados = MENSALIDADE[situacao] ?? MENSALIDADE.sem_plano;
    return (
        <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border ${dados.classe}`}>
            {dados.rotulo}{situacao === 'atrasada' && diasAtraso > 0 ? ` · ${diasAtraso}d` : ''}
        </span>
    );
}

function CelulaPersonal({ personal }) {
    return (
        <div className="flex items-center gap-3 min-w-0">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-black text-sm shrink-0 ${
                personal.ativo ? 'bg-brand text-brand-fg' : 'bg-overlay text-text-muted'
            }`}>
                {personal.username.slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0">
                <div className="flex items-center gap-2">
                    <p className="text-sm font-bold text-text-primary truncate">{personal.username}</p>
                    {!personal.ativo && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wide border bg-overlay text-text-muted border-border">
                            fora
                        </span>
                    )}
                </div>
                <p className="text-xs text-text-muted truncate">{personal.email}</p>
            </div>
        </div>
    );
}

export default function DashboardFinanceiroPersonais() {
    const [dados, setDados] = useState(null);
    const [loading, setLoading] = useState(true);
    const [erro, setErro] = useState(null);

    const carregar = async () => {
        setLoading(true);
        setErro(null);
        try {
            setDados(await financeiroPersonalService.resumo());
        } catch (err) {
            setErro(err.message || 'Não foi possível carregar o financeiro dos personais.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        carregar();
    }, []);

    if (loading && !dados) {
        return (
            <div className="flex flex-col items-center justify-center py-40 space-y-4">
                <div className="w-10 h-10 border-2 border-brand/20 border-t-brand rounded-full animate-spin" />
                <p className="text-text-secondary font-bold uppercase text-xs tracking-widest animate-pulse">Sincronizando mensalidades...</p>
            </div>
        );
    }

    if (erro && !dados) {
        return (
            <div className="bg-danger/10 border border-danger/20 text-danger p-6 rounded-2xl mx-2 flex flex-col items-center gap-3">
                <p className="text-xs font-bold uppercase tracking-widest flex items-center gap-2"><AlertCircle size={15} /> {erro}</p>
                <button onClick={carregar} className="px-4 py-2 rounded-xl bg-surface border border-border text-xs font-black uppercase tracking-widest text-text-secondary hover:bg-overlay transition-all">
                    Tentar novamente
                </button>
            </div>
        );
    }

    const resumo = dados ?? {
        referencia_mes: '—',
        receita_prevista: 0,
        recebido_mes: 0,
        valor_em_atraso: 0,
        total_personais: 0,
        quantidade_em_dia: 0,
        quantidade_vence_em_breve: 0,
        quantidade_em_atraso: 0,
        quantidade_em_aberto: 0,
        quantidade_sem_plano: 0,
        personais: [],
    };

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 px-2">
                <div>
                    <h2 className="text-2xl sm:text-3xl font-bold text-text-primary tracking-tight">Financeiro dos Personais</h2>
                    <p className="text-text-secondary text-xs sm:text-sm font-medium">
                        Mensalidades de quem usa a plataforma · referência {resumo.referencia_mes}.
                    </p>
                </div>
                <button
                    onClick={carregar}
                    disabled={loading}
                    className="p-2.5 rounded-xl text-text-muted hover:text-text-primary hover:bg-overlay transition-all disabled:opacity-50"
                    aria-label="Atualizar financeiro dos personais"
                >
                    <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {erro && dados && (
                <div className="bg-danger/10 border border-danger/20 text-danger p-3 rounded-xl text-xs font-bold flex items-center gap-2 mx-2">
                    <AlertCircle size={14} /> {erro}
                </div>
            )}

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mx-2">
                <div className="bg-surface border border-border rounded-2xl p-5">
                    <div className="flex items-center gap-2 text-text-muted mb-2">
                        <DollarSign size={14} />
                        <p className="text-[10px] font-black uppercase tracking-widest">Receita prevista</p>
                    </div>
                    <p className="text-2xl font-black font-mono tabular-nums text-text-primary tracking-tighter">{brl(resumo.receita_prevista)}</p>
                    <p className="text-[10px] text-text-muted mt-1">planos ativos no mês</p>
                </div>
                <div className="bg-surface border border-border rounded-2xl p-5">
                    <div className="flex items-center gap-2 text-text-muted mb-2">
                        <CheckCircle2 size={14} className="text-success" />
                        <p className="text-[10px] font-black uppercase tracking-widest">Recebido</p>
                    </div>
                    <p className="text-2xl font-black font-mono tabular-nums text-success-text tracking-tighter">{brl(resumo.recebido_mes)}</p>
                    <p className="text-[10px] text-text-muted mt-1">{resumo.quantidade_em_dia} em dia</p>
                </div>
                <div className="bg-surface border border-border rounded-2xl p-5">
                    <div className="flex items-center gap-2 text-text-muted mb-2">
                        <XCircle size={14} className="text-danger" />
                        <p className="text-[10px] font-black uppercase tracking-widest">Em atraso</p>
                    </div>
                    <p className="text-2xl font-black font-mono tabular-nums text-danger tracking-tighter">{brl(resumo.valor_em_atraso)}</p>
                    <p className="text-[10px] text-text-muted mt-1">{resumo.quantidade_em_atraso} {resumo.quantidade_em_atraso === 1 ? 'personal' : 'personais'}</p>
                </div>
                <div className="bg-surface border border-border rounded-2xl p-5">
                    <div className="flex items-center gap-2 text-text-muted mb-2">
                        <Users size={14} />
                        <p className="text-[10px] font-black uppercase tracking-widest">Personais</p>
                    </div>
                    <p className="text-2xl font-black font-mono tabular-nums text-text-primary tracking-tighter">{resumo.total_personais}</p>
                    <p className="text-[10px] text-text-muted mt-1">
                        {resumo.quantidade_vence_em_breve} vencem · {resumo.quantidade_sem_plano} sem plano
                    </p>
                </div>
            </div>

            <div className="mx-2 bg-surface border border-border rounded-2xl overflow-hidden">
                <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
                    <div className="w-9 h-9 rounded-xl bg-overlay flex items-center justify-center">
                        <Users size={17} className="text-text-secondary" />
                    </div>
                    <div>
                        <h3 className="text-sm font-black text-text-primary">Mensalidades por personal</h3>
                        <p className="text-xs text-text-muted">{resumo.total_personais} cadastrado{resumo.total_personais !== 1 ? 's' : ''}; {resumo.quantidade_em_aberto} em aberto e {resumo.quantidade_sem_plano} sem plano.</p>
                    </div>
                </div>

                {resumo.personais.length === 0 ? (
                    <p className="px-5 py-12 text-center text-xs text-text-muted italic">Nenhum personal cadastrado ainda.</p>
                ) : (
                    <>
                        <div className="hidden md:block overflow-x-auto">
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="border-b border-border text-[10px] font-black uppercase tracking-widest text-text-muted">
                                        <th className="px-5 py-3">Personal</th>
                                        <th className="px-5 py-3">Mensalidade</th>
                                        <th className="px-5 py-3">Vencimento</th>
                                        <th className="px-5 py-3">Situação</th>
                                        <th className="px-5 py-3">Pago em</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {resumo.personais.map((personal) => (
                                        <tr key={personal.trainer_id} className="border-b border-border/60 last:border-0">
                                            <td className="px-5 py-3"><CelulaPersonal personal={personal} /></td>
                                            <td className="px-5 py-3 text-sm font-bold font-mono tabular-nums text-text-primary">
                                                {personal.valor_mensal == null ? '—' : brl(personal.valor_mensal)}
                                            </td>
                                            <td className="px-5 py-3 text-xs text-text-secondary">
                                                {personal.dia_vencimento ? `dia ${personal.dia_vencimento}` : '—'}
                                            </td>
                                            <td className="px-5 py-3"><BadgeSituacao situacao={personal.situacao} diasAtraso={personal.dias_atraso} /></td>
                                            <td className="px-5 py-3 text-xs text-text-secondary">{formatarDia(personal.pago_em)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <div className="md:hidden divide-y divide-border/60">
                            {resumo.personais.map((personal) => (
                                <div key={personal.trainer_id} className="p-4 space-y-2">
                                    <div className="flex items-start justify-between gap-3">
                                        <CelulaPersonal personal={personal} />
                                        <BadgeSituacao situacao={personal.situacao} diasAtraso={personal.dias_atraso} />
                                    </div>
                                    <div className="flex items-center justify-between text-xs text-text-secondary">
                                        <span className="font-mono font-bold text-text-primary">
                                            {personal.valor_mensal == null ? 'sem valor' : brl(personal.valor_mensal)}
                                        </span>
                                        <span>{personal.dia_vencimento ? `vence dia ${personal.dia_vencimento}` : 'sem plano'}</span>
                                        <span>pago {formatarDia(personal.pago_em)}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
