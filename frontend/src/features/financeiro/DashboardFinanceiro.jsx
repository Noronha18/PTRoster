import { useState, useEffect } from 'react';
import { Plus, AlertCircle, DollarSign } from 'lucide-react';
import CardsKPI from './CardsKPI';
import GraficoReceita from './GraficoReceita';
import GraficoInadimplencia from './GraficoInadimplencia';
import TabelaPagamentos from '../pagamentos/TabelaPagamentos';
import { ModalPagamento } from '../pagamentos/ModalPagamento';
import { financeiroService, pagamentoService } from '../../services/api';

const DADOS_DEFAULT = {
    receita_total: 0,
    ticket_medio: 0,
    inadimplencia: 0,
    total_alunos: 0,
    alunos_em_dia: 0,
    alunos_inadimplentes: 0,
    receita_mensal_12m: []
};

const DashboardFinanceiro = () => {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [financeiroData, setFinanceiroData] = useState(DADOS_DEFAULT);
    const [ultimosPagamentos, setUltimosPagamentos] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const carregarDados = async () => {
        try {
            setLoading(true);
            const [stats, pagamentos] = await Promise.all([
                financeiroService.obterEstatisticas(),
                pagamentoService.listar()
            ]);
            setFinanceiroData(stats);
            setUltimosPagamentos(pagamentos || []);
            setError(null);
        } catch {
            setError('Não foi possível carregar os dados financeiros.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        carregarDados();
    }, []);

    const handlePagamentoRegistrado = () => {
        setIsModalOpen(false);
        carregarDados();
    };

    if (loading && !financeiroData.receita_total) {
        return (
            <div className="flex flex-col items-center justify-center py-40 space-y-4">
                <div className="w-10 h-10 border-2 border-brand/20 border-t-brand rounded-full animate-spin"></div>
                <p className="text-text-secondary font-bold uppercase text-xs tracking-widest animate-pulse">Sincronizando Fluxo de Caixa...</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6 px-2">
                <div>
                    <h2 className="text-2xl sm:text-3xl font-bold text-text-primary tracking-tight">Financeiro</h2>
                    <p className="text-text-secondary text-xs sm:text-sm font-medium">Saúde financeira e previsibilidade operacional.</p>
                </div>
                <button 
                    onClick={() => setIsModalOpen(true)}
                    className="w-full sm:w-auto bg-brand hover:bg-brand-hover text-brand-fg px-6 py-3 rounded-xl font-bold transition-all shadow-sm flex items-center justify-center gap-2 active:scale-95 uppercase text-xs tracking-widest"
                >
                    <Plus size={16} /> Registrar recebimento
                </button>
            </div>

            {error && (
                <div className="bg-danger/10 border border-danger/20 text-danger p-4 rounded-xl text-xs font-bold uppercase tracking-widest flex items-center gap-3 mx-2">
                    <AlertCircle size={16} /> {error}
                    <button type="button" onClick={carregarDados} className="ml-auto min-h-11 px-2 underline">
                        Tentar novamente
                    </button>
                </div>
            )}

            {!error && <>
            <CardsKPI dados={financeiroData} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch mx-2">
                <GraficoReceita dados={financeiroData.receita_mensal_12m} />
                <GraficoInadimplencia dados={financeiroData} />
            </div>

            <div className="bg-surface border border-border rounded-xl p-6 sm:p-8 shadow-sm mx-2">
                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-overlay text-brand rounded-lg flex items-center justify-center border border-border">
                            <DollarSign size={18} />
                        </div>
                        <h3 className="text-lg font-bold text-text-primary tracking-tight">Recebimentos recentes</h3>
                    </div>
                </div>
                <TabelaPagamentos pagamentos={ultimosPagamentos} onDelete={carregarDados} />
            </div>

            </>}

            <ModalPagamento 
                isOpen={isModalOpen} 
                onClose={() => setIsModalOpen(false)}
                onSuccess={handlePagamentoRegistrado}
            />
        </div>
    );
};

export default DashboardFinanceiro;
