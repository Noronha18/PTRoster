import { useState, useEffect } from 'react';
import { X, DollarSign, UserCircle2, Calendar, Hash } from 'lucide-react';
import { alunoService, pagamentoService } from '../../services/api';
import { useToast } from '../../components/ToastProvider';

export const ModalPagamento = ({ isOpen, onClose, onSuccess }) => {
    const toast = useToast();
    const [alunos, setAlunos] = useState([]);
    const [loading, setLoading] = useState(false);
    const [alunoSelecionado, setAlunoSelecionado] = useState(null);
    const [formData, setFormData] = useState({
        aluno_id: '',
        valor: '',
        referencia_mes: new Date().toLocaleDateString('pt-BR', { month: '2-digit', year: 'numeric' }),
        forma_pagamento: 'PIX',
        quantidade_aulas: 0,
        observacao: '',
        novo_vencimento: ''
    });

    useEffect(() => {
        if (isOpen) {
            alunoService.listar().then(setAlunos).catch(console.error);
        }
    }, [isOpen]);

    useEffect(() => {
        // Vencimento é por contrato: nunca herdar o de outro aluno nem de uma abertura anterior
        setFormData(prev => ({ ...prev, novo_vencimento: '' }));
        if (formData.aluno_id) {
            const aluno = alunos.find(a => a.id === parseInt(formData.aluno_id));
            setAlunoSelecionado(aluno);
            if (aluno && (aluno.tipo_pagamento === 'pacote' || aluno.modalidade === 'consultoria') && !formData.valor) {
                setFormData(prev => ({ ...prev, valor: aluno.valor_mensalidade }));
            }
        } else {
            setAlunoSelecionado(null);
        }
    }, [formData.aluno_id, alunos]);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await pagamentoService.registrar({
                ...formData,
                aluno_id: parseInt(formData.aluno_id),
                valor: parseFloat(formData.valor),
                quantidade_aulas: parseInt(formData.quantidade_aulas) || 0,
                novo_vencimento: formData.novo_vencimento || null
            });
            if (onSuccess) onSuccess();
            onClose();
        } catch (err) {
            console.error(err);
            toast({ tipo: 'erro', texto: err.message || "Erro ao registrar pagamento" });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="bg-surface border border-border w-full max-w-lg rounded-[2.5rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-500">
                <div className="p-10 border-b border-border flex justify-between items-center bg-surface">
                    <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-brand/10 text-brand rounded-2xl flex items-center justify-center">
                            <DollarSign size={24} />
                        </div>
                        <div>
                            <h2 className="text-2xl font-black text-text-primary tracking-tight">Novo Recebimento</h2>
                            <p className="text-text-secondary text-sm font-medium">Registre a entrada no fluxo.</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-3 bg-overlay text-text-muted hover:text-text-secondary rounded-full transition-all active:scale-90">
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-10 space-y-8">
                    <div className="space-y-2">
                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1 flex items-center gap-2">
                            <UserCircle2 size={14} className="text-brand" /> Aluno Pagador
                        </label>
                        <select
                            required
                            className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold outline-none focus:ring-2 focus:ring-brand/10 transition-all appearance-none cursor-pointer"
                            value={formData.aluno_id}
                            onChange={(e) => setFormData({...formData, aluno_id: e.target.value})}
                        >
                            <option value="">Selecione o atleta...</option>
                            {alunos.map(aluno => (
                                <option key={aluno.id} value={aluno.id}>{aluno.nome} ({aluno.tipo_pagamento})</option>
                            ))}
                        </select>
                    </div>

                    <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Valor (R$)</label>
                            <input
                                required
                                type="number"
                                className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-black outline-none focus:ring-2 focus:ring-brand/10 transition-all"
                                value={formData.valor}
                                onChange={(e) => setFormData({...formData, valor: e.target.value})}
                                placeholder="0,00"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1 flex items-center gap-2">
                                <Calendar size={14} className="text-brand" /> Mês de Ref.
                            </label>
                            <input
                                required
                                type="text"
                                placeholder="MM/AAAA"
                                className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold outline-none focus:ring-2 focus:ring-brand/10 transition-all"
                                value={formData.referencia_mes}
                                onChange={(e) => setFormData({...formData, referencia_mes: e.target.value})}
                            />
                        </div>
                    </div>

                    {alunoSelecionado?.modalidade !== 'consultoria' && (
                    <div className="space-y-2">
                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1 flex items-center gap-2">
                            <Hash size={14} className="text-brand" />
                            {alunoSelecionado?.tipo_pagamento === 'pacote' ? 'Qtd. de Aulas (Recarga)' : 'Aulas Extras (Opcional)'}
                        </label>
                        <input
                            type="number"
                            className={`w-full bg-overlay border rounded-2xl px-5 py-4 text-text-primary font-black outline-none transition-all
                                ${alunoSelecionado?.tipo_pagamento === 'pacote' ? 'border-brand/30 ring-2 ring-brand/5' : 'border-border'}`}
                            value={formData.quantidade_aulas}
                            onChange={(e) => setFormData({...formData, quantidade_aulas: e.target.value})}
                            placeholder="Ex: 10"
                        />
                        {alunoSelecionado?.tipo_pagamento === 'pacote' && (
                            <p className="text-2xs text-brand font-bold uppercase tracking-tight ml-1 animate-pulse">
                                As aulas serão somadas ao saldo atual do aluno.
                            </p>
                        )}
                    </div>
                    )}

                    {alunoSelecionado?.modalidade === 'consultoria' && (
                        <div className="space-y-2">
                            <label htmlFor="novo-vencimento" className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1 flex items-center gap-2">
                                <Calendar size={14} className="text-brand" /> Novo Vencimento
                            </label>
                            <input
                                id="novo-vencimento"
                                required
                                type="date"
                                className="w-full bg-overlay border border-brand/30 ring-2 ring-brand/5 rounded-2xl px-5 py-4 text-text-primary font-bold outline-none focus:ring-2 focus:ring-brand/10 transition-all"
                                value={formData.novo_vencimento}
                                onChange={(e) => setFormData({...formData, novo_vencimento: e.target.value})}
                            />
                            {alunoSelecionado.data_vencimento_consultoria && (
                                <p className="text-xs text-text-muted ml-1">
                                    Vencimento atual: {new Date(alunoSelecionado.data_vencimento_consultoria + 'T00:00').toLocaleDateString('pt-BR')}
                                </p>
                            )}
                        </div>
                    )}

                    <div className="space-y-4">
                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Forma de Pagamento</label>
                        <div className="flex gap-3">
                            {['PIX', 'Dinheiro', 'Cartão'].map(forma => (
                                <button
                                    key={forma}
                                    type="button"
                                    onClick={() => setFormData({...formData, forma_pagamento: forma})}
                                    className={`flex-1 py-4 rounded-2xl text-xs font-black transition-all uppercase tracking-widest border
                                        ${formData.forma_pagamento === forma
                                            ? 'bg-brand text-brand-fg border-brand shadow-lg shadow-brand/20'
                                            : 'bg-overlay text-text-muted border-border hover:bg-overlay'}`}
                                >
                                    {forma}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Observação Interna</label>
                        <textarea
                            className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-medium outline-none focus:ring-2 focus:ring-brand/10 transition-all placeholder:text-text-muted"
                            rows="2"
                            value={formData.observacao}
                            onChange={(e) => setFormData({...formData, observacao: e.target.value})}
                            placeholder="Ex: Pago via transferência direta..."
                        ></textarea>
                    </div>

                    <button
                        disabled={loading}
                        className="w-full bg-brand hover:bg-brand-hover text-brand-fg py-5 rounded-[2rem] font-black text-xs uppercase tracking-[0.2em] mt-4 transition-all shadow-xl shadow-brand/20 active:scale-95 disabled:opacity-50"
                    >
                        {loading ? 'Processando...' : 'Confirmar Recebimento'}
                    </button>
                </form>
            </div>
        </div>
    );
};
