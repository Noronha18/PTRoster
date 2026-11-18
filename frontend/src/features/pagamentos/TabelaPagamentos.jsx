import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { pagamentoService } from '../../services/api';
import { useToast } from '../../components/ToastProvider';

export default function TabelaPagamentos({ pagamentos, onDelete }) {
    const toast = useToast();
    const [deletando, setDeletando] = useState(null);

    const handleDelete = async (pagamentoId) => {
        if (!confirm('Tem certeza que deseja cancelar este pagamento?')) {
            return;
        }

        setDeletando(pagamentoId);

        try {
            await pagamentoService.deletar(pagamentoId);
            if (onDelete) {
                onDelete(pagamentoId);
            }
        } catch (error) {
            toast({ tipo: 'erro', texto: 'Erro ao cancelar pagamento: ' + error.message });
        } finally {
            setDeletando(null);
        }
    };

    const formatarData = (dataStr) => {
        if (!dataStr) return '-';
        const data = new Date(dataStr + 'T00:00:00');
        return data.toLocaleDateString('pt-BR');
    };

    const formatarValor = (valor) => {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(valor);
    };

    if (!pagamentos || pagamentos.length === 0) {
        return (
            <div className="py-12 text-center border-t border-border">
                <p className="text-sm text-text-secondary">Nenhum recebimento registrado.</p>
            </div>
        );
    }

    return (
        <div className="overflow-x-auto custom-scrollbar">
            <table className="w-full min-w-[36rem]">
                <caption className="sr-only">Recebimentos registrados</caption>
                <thead>
                    <tr className="border-b border-border">
                        <th scope="col" className="text-left px-3 py-3 text-sm font-semibold text-text-secondary">
                            Data
                        </th>
                        <th scope="col" className="text-left px-3 py-3 text-sm font-semibold text-text-secondary">
                            Aluno
                        </th>
                        <th scope="col" className="text-left px-3 py-3 text-sm font-semibold text-text-secondary">
                            Mês de referência
                        </th>
                        <th scope="col" className="text-left px-3 py-3 text-sm font-semibold text-text-secondary">
                            Valor
                        </th>
                        <th scope="col" className="text-left px-3 py-3 text-sm font-semibold text-text-secondary">
                            Forma
                        </th>
                        <th scope="col" className="text-right px-3 py-3 text-sm font-semibold text-text-secondary">
                            Ações
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {pagamentos.map((pagamento) => (
                        <tr
                            key={pagamento.id}
                            className="border-b border-border hover:bg-overlay/50 transition-colors group"
                        >
                            <td className="px-3 py-3 text-xs font-bold text-text-secondary">
                                {formatarData(pagamento.data_pagamento)}
                            </td>
                            <td className="px-3 py-3">
                                <span className="text-sm font-semibold text-text-primary">{pagamento.aluno_nome}</span>
                            </td>
                            <td className="px-3 py-3 text-sm tabular-nums text-text-secondary">
                                {pagamento.referencia_mes}
                            </td>
                            <td className="px-3 py-3 text-sm font-semibold tabular-nums text-text-primary">
                                {formatarValor(pagamento.valor)}
                            </td>
                            <td className="px-3 py-3">
                                <span className="text-sm text-text-secondary">
                                    {pagamento.forma_pagamento}
                                </span>
                            </td>
                            <td className="px-3 py-3 text-right">
                                <button
                                    onClick={() => handleDelete(pagamento.id)}
                                    disabled={deletando === pagamento.id}
                                    className="p-2 text-text-muted hover:text-danger hover:bg-danger/10 rounded-xl transition-all disabled:opacity-50 active:scale-90"
                                    aria-label={`Cancelar lançamento de ${pagamento.aluno_nome}`}
                                    title="Cancelar lançamento"
                                >
                                    {deletando === pagamento.id ? (
                                        <div className="w-4 h-4 border-2 border-danger border-t-transparent rounded-full animate-spin" />
                                    ) : (
                                        <Trash2 size={18} />
                                    )}
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
