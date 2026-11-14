import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, DollarSign, Pencil, Plus, Receipt, XCircle } from 'lucide-react';
import { financeiroPersonalService } from '../../services/api';
import { useToast } from '../../components/ToastProvider';
import { MENSALIDADE, formatarDia } from './formato';

const brl = (valor) => new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
}).format(Number(valor || 0));

function isoHoje() {
    const hoje = new Date();
    const mes = String(hoje.getMonth() + 1).padStart(2, '0');
    const dia = String(hoje.getDate()).padStart(2, '0');
    return `${hoje.getFullYear()}-${mes}-${dia}`;
}

function mesAtual() {
    const hoje = new Date();
    return `${String(hoje.getMonth() + 1).padStart(2, '0')}/${hoje.getFullYear()}`;
}

function BadgeSituacao({ situacao, diasAtraso = 0 }) {
    const dados = MENSALIDADE[situacao] ?? MENSALIDADE.sem_plano;
    return (
        <span className={`inline-flex px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-widest border ${dados.classe}`}>
            {dados.rotulo}{situacao === 'atrasada' && diasAtraso > 0 ? ` · ${diasAtraso}d` : ''}
        </span>
    );
}

const FORM_PLANO_VAZIO = {
    valor_mensal: '',
    dia_vencimento: 5,
    ativo: true,
    inicio: isoHoje(),
    observacao: '',
};

export function FinanceiroPersonal({ personal, onAtualizado }) {
    const toast = useToast();
    const [plano, setPlano] = useState(null);
    const [pagamentos, setPagamentos] = useState([]);
    const [loading, setLoading] = useState(true);
    const [erro, setErro] = useState(null);
    const [situacao, setSituacao] = useState({
        valor: personal.situacao_mensalidade ?? 'sem_plano',
        dias: personal.dias_atraso ?? 0,
    });
    const [editandoPlano, setEditandoPlano] = useState(false);
    const [formPlano, setFormPlano] = useState(FORM_PLANO_VAZIO);
    const [pagamentoAberto, setPagamentoAberto] = useState(false);
    const [formPagamento, setFormPagamento] = useState({
        referencia_mes: mesAtual(),
        valor: '',
        data_pagamento: isoHoje(),
        forma_pagamento: 'PIX',
        observacao: '',
    });
    const [salvando, setSalvando] = useState(false);

    const atualizarSituacao = useCallback(async () => {
        try {
            const resumo = await financeiroPersonalService.resumo();
            const linha = resumo.personais.find((p) => p.trainer_id === personal.id);
            if (linha) setSituacao({ valor: linha.situacao, dias: linha.dias_atraso });
        } catch {
            // A lista principal também é recarregada pelo pai; a falha aqui é só do selo.
        }
    }, [personal.id]);

    const carregar = useCallback(async () => {
        setLoading(true);
        setErro(null);
        try {
            const [planoAtual, pagamentosAtuais] = await Promise.all([
                financeiroPersonalService.obterPlano(personal.id),
                financeiroPersonalService.listarPagamentos(personal.id),
            ]);
            setPlano(planoAtual);
            setPagamentos(pagamentosAtuais || []);
            setFormPlano(planoAtual ? {
                valor_mensal: planoAtual.valor_mensal,
                dia_vencimento: planoAtual.dia_vencimento,
                ativo: planoAtual.ativo,
                inicio: String(planoAtual.inicio).slice(0, 10),
                observacao: planoAtual.observacao || '',
            } : FORM_PLANO_VAZIO);
        } catch (err) {
            setErro(err.message || 'Erro ao carregar o financeiro do personal.');
        } finally {
            setLoading(false);
        }
    }, [personal.id]);

    useEffect(() => {
        carregar();
    }, [carregar]);

    const abrirPlano = () => {
        setFormPlano(plano ? {
            valor_mensal: plano.valor_mensal,
            dia_vencimento: plano.dia_vencimento,
            ativo: plano.ativo,
            inicio: String(plano.inicio).slice(0, 10),
            observacao: plano.observacao || '',
        } : FORM_PLANO_VAZIO);
        setEditandoPlano(true);
    };

    const salvarPlano = async (event) => {
        event.preventDefault();
        setSalvando(true);
        try {
            const salvo = await financeiroPersonalService.salvarPlano(personal.id, {
                valor_mensal: Number(formPlano.valor_mensal),
                dia_vencimento: Number(formPlano.dia_vencimento),
                ativo: formPlano.ativo,
                inicio: formPlano.inicio || null,
                observacao: formPlano.observacao || null,
            });
            setPlano(salvo);
            setEditandoPlano(false);
            toast({ tipo: 'sucesso', texto: 'Plano do personal salvo.' });
            await atualizarSituacao();
            onAtualizado?.();
        } catch (err) {
            toast({ tipo: 'erro', texto: err.message || 'Erro ao salvar o plano.' });
        } finally {
            setSalvando(false);
        }
    };

    const abrirPagamento = () => {
        setFormPagamento({
            referencia_mes: mesAtual(),
            valor: plano?.valor_mensal ?? '',
            data_pagamento: isoHoje(),
            forma_pagamento: 'PIX',
            observacao: '',
        });
        setPagamentoAberto(true);
    };

    const registrarPagamento = async (event) => {
        event.preventDefault();
        setSalvando(true);
        try {
            const novo = await financeiroPersonalService.registrarPagamento(personal.id, {
                referencia_mes: formPagamento.referencia_mes,
                valor: Number(formPagamento.valor),
                data_pagamento: formPagamento.data_pagamento || null,
                forma_pagamento: formPagamento.forma_pagamento || null,
                observacao: formPagamento.observacao || null,
            });
            setPagamentos((atuais) => [novo, ...atuais]);
            setPagamentoAberto(false);
            toast({ tipo: 'sucesso', texto: 'Pagamento registrado.' });
            await atualizarSituacao();
            onAtualizado?.();
        } catch (err) {
            toast({ tipo: 'erro', texto: err.message || 'Erro ao registrar o pagamento.' });
        } finally {
            setSalvando(false);
        }
    };

    return (
        <section className="bg-surface border border-border rounded-2xl overflow-hidden mb-8">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-5 py-4 border-b border-border">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-overlay flex items-center justify-center">
                        <DollarSign size={17} className="text-text-secondary" />
                    </div>
                    <div>
                        <h2 className="text-sm font-black text-text-primary">Mensalidade</h2>
                        <p className="text-xs text-text-muted">Plano e pagamentos deste personal.</p>
                    </div>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    <BadgeSituacao situacao={situacao.valor} diasAtraso={situacao.dias} />
                    <button
                        type="button"
                        onClick={abrirPlano}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-overlay hover:bg-border text-text-secondary text-[10px] font-black uppercase tracking-widest transition-all"
                    >
                        <Pencil size={12} /> {plano ? 'Editar plano' : 'Definir plano'}
                    </button>
                </div>
            </div>

            <div className="p-5 space-y-5">
                {loading ? (
                    <p className="text-xs font-bold text-text-muted animate-pulse">Carregando financeiro...</p>
                ) : erro ? (
                    <div className="flex items-center justify-between gap-3">
                        <p className="text-xs font-bold text-danger flex items-center gap-2"><XCircle size={14} /> {erro}</p>
                        <button onClick={carregar} className="text-[10px] font-black uppercase tracking-widest text-brand hover:underline">Tentar novamente</button>
                    </div>
                ) : plano ? (
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-text-secondary">
                        <span className="text-base font-black font-mono text-text-primary tabular-nums">{brl(plano.valor_mensal)}<span className="text-xs font-medium text-text-muted">/mês</span></span>
                        <span>Vence dia <strong className="text-text-primary">{plano.dia_vencimento}</strong></span>
                        <span>Desde {formatarDia(plano.inicio)}</span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border ${
                            plano.ativo ? 'bg-success/10 text-success border-success/20' : 'bg-overlay text-text-muted border-border'
                        }`}>{plano.ativo ? 'Ativo' : 'Inativo'}</span>
                        {plano.observacao && <span className="text-text-muted italic">{plano.observacao}</span>}
                    </div>
                ) : (
                    <p className="text-xs text-text-muted italic">Nenhum plano definido. A mensalidade fica “sem plano” até você definir um valor e vencimento.</p>
                )}

                {editandoPlano && (
                    <form onSubmit={salvarPlano} className="border border-border rounded-xl p-4 bg-overlay/40 space-y-3">
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                            <label className="space-y-1">
                                <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Valor mensal (R$)</span>
                                <input
                                    required type="number" min="0" step="0.01"
                                    value={formPlano.valor_mensal}
                                    onChange={(e) => setFormPlano((f) => ({ ...f, valor_mensal: e.target.value }))}
                                    className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-bold text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/20"
                                />
                            </label>
                            <label className="space-y-1">
                                <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Dia do vencimento</span>
                                <input
                                    required type="number" min="1" max="31"
                                    value={formPlano.dia_vencimento}
                                    onChange={(e) => setFormPlano((f) => ({ ...f, dia_vencimento: e.target.value }))}
                                    className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-bold text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/20"
                                />
                            </label>
                            <label className="space-y-1">
                                <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Início</span>
                                <input
                                    type="date"
                                    value={formPlano.inicio}
                                    onChange={(e) => setFormPlano((f) => ({ ...f, inicio: e.target.value }))}
                                    className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-bold text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/20"
                                />
                            </label>
                            <label className="flex items-center gap-2 mt-5">
                                <input
                                    type="checkbox"
                                    checked={formPlano.ativo}
                                    onChange={(e) => setFormPlano((f) => ({ ...f, ativo: e.target.checked }))}
                                    className="w-4 h-4 accent-[var(--color-brand)]"
                                />
                                <span className="text-xs font-bold text-text-secondary">Cobrança ativa</span>
                            </label>
                        </div>
                        <label className="block space-y-1">
                            <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Observação</span>
                            <input
                                type="text"
                                value={formPlano.observacao}
                                onChange={(e) => setFormPlano((f) => ({ ...f, observacao: e.target.value }))}
                                placeholder="Opcional"
                                className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/20"
                            />
                        </label>
                        <div className="flex gap-2 justify-end">
                            <button type="button" onClick={() => setEditandoPlano(false)} className="px-3 py-2 rounded-lg bg-surface border border-border text-[10px] font-black uppercase tracking-widest text-text-muted hover:bg-overlay transition-all">Cancelar</button>
                            <button type="submit" disabled={salvando} className="px-3 py-2 rounded-lg bg-brand hover:bg-brand-hover text-brand-fg text-[10px] font-black uppercase tracking-widest transition-all disabled:opacity-50">Salvar plano</button>
                        </div>
                    </form>
                )}

                <div className="border-t border-border/60 pt-4">
                    <div className="flex items-center justify-between mb-3">
                        <p className="text-[10px] font-black uppercase tracking-widest text-text-muted flex items-center gap-2">
                            <Receipt size={13} /> Pagamentos recentes
                        </p>
                        <button
                            type="button"
                            onClick={abrirPagamento}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand hover:bg-brand-hover text-brand-fg text-[10px] font-black uppercase tracking-widest transition-all active:scale-95"
                        >
                            <Plus size={12} /> Registrar pagamento
                        </button>
                    </div>

                    {pagamentos.length === 0 ? (
                        <p className="text-xs text-text-muted italic">Nenhum pagamento registrado.</p>
                    ) : (
                        <div className="divide-y divide-border/60 border border-border/60 rounded-xl overflow-hidden">
                            {pagamentos.map((pagamento) => (
                                <div key={pagamento.id} className="flex items-center gap-3 px-4 py-2.5 bg-overlay/30">
                                    <CheckCircle2 size={14} className="text-success shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs font-bold text-text-primary">
                                            {brl(pagamento.valor)}
                                            <span className="font-medium text-text-muted"> · ref. {pagamento.referencia_mes}</span>
                                        </p>
                                        <p className="text-[10px] text-text-muted">
                                            Pago em {formatarDia(pagamento.data_pagamento)}
                                            {pagamento.forma_pagamento ? ` · ${pagamento.forma_pagamento}` : ''}
                                            {pagamento.observacao ? ` · ${pagamento.observacao}` : ''}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {pagamentoAberto && (
                        <form onSubmit={registrarPagamento} className="mt-3 border border-border rounded-xl p-4 bg-overlay/40 space-y-3">
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                                <label className="space-y-1">
                                    <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Mês de referência</span>
                                    <input
                                        required type="text" placeholder="MM/AAAA" pattern="(0[1-9]|1[0-2])/[0-9]{4}"
                                        value={formPagamento.referencia_mes}
                                        onChange={(e) => setFormPagamento((f) => ({ ...f, referencia_mes: e.target.value }))}
                                        className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-bold text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/20"
                                    />
                                </label>
                                <label className="space-y-1">
                                    <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Valor (R$)</span>
                                    <input
                                        required type="number" min="0" step="0.01"
                                        value={formPagamento.valor}
                                        onChange={(e) => setFormPagamento((f) => ({ ...f, valor: e.target.value }))}
                                        className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-bold text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/20"
                                    />
                                </label>
                                <label className="space-y-1">
                                    <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Pago em</span>
                                    <input
                                        type="date"
                                        value={formPagamento.data_pagamento}
                                        onChange={(e) => setFormPagamento((f) => ({ ...f, data_pagamento: e.target.value }))}
                                        className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-bold text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/20"
                                    />
                                </label>
                                <label className="space-y-1">
                                    <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Forma</span>
                                    <select
                                        value={formPagamento.forma_pagamento}
                                        onChange={(e) => setFormPagamento((f) => ({ ...f, forma_pagamento: e.target.value }))}
                                        className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-bold text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/20"
                                    >
                                        <option>PIX</option>
                                        <option>Dinheiro</option>
                                        <option>Cartão</option>
                                        <option>Transferência</option>
                                    </select>
                                </label>
                            </div>
                            <label className="block space-y-1">
                                <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Observação</span>
                                <input
                                    type="text"
                                    value={formPagamento.observacao}
                                    onChange={(e) => setFormPagamento((f) => ({ ...f, observacao: e.target.value }))}
                                    placeholder="Opcional"
                                    className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand/20"
                                />
                            </label>
                            <div className="flex gap-2 justify-end">
                                <button type="button" onClick={() => setPagamentoAberto(false)} className="px-3 py-2 rounded-lg bg-surface border border-border text-[10px] font-black uppercase tracking-widest text-text-muted hover:bg-overlay transition-all">Cancelar</button>
                                <button type="submit" disabled={salvando} className="px-3 py-2 rounded-lg bg-brand hover:bg-brand-hover text-brand-fg text-[10px] font-black uppercase tracking-widest transition-all disabled:opacity-50">Salvar pagamento</button>
                            </div>
                        </form>
                    )}
                </div>
            </div>
        </section>
    );
}
