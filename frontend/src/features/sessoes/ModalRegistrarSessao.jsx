import { useState, useEffect } from 'react';
import { X, Calendar, Dumbbell, CheckCircle2, Clock, AlertTriangle, MessageSquare } from 'lucide-react';
import { alunoService, sessaoService } from '../../services/api';
import { chaveSerie, seriesParaEnvio, valoresIniciais } from './series';

const hojeISO = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD no fuso do navegador

export default function ModalRegistrarSessao({ alunoId, planos, onClose, onSucesso }) {
  const treinos = planos?.find(p => p.esta_ativo)?.treinos ?? [];
  const [data, setData] = useState(hojeISO());
  const [treinoId, setTreinoId] = useState(treinos[0]?.id ?? '');
  const [valores, setValores] = useState({});
  const [status, setStatus] = useState('realizada');
  const [observacao, setObservacao] = useState('');
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState(null);

  const treino = treinos.find(t => t.id === Number(treinoId));

  useEffect(() => {
    if (!treino) return;
    let ativo = true;
    alunoService.ultimaExecucao(alunoId, treino.id)
      .catch(() => [])
      .then(ultimas => { if (ativo) setValores(valoresIniciais(treino.prescricoes, ultimas)); });
    return () => { ativo = false; };
  }, [alunoId, treino]);

  const mudarValor = (chave, campo, valor) =>
    setValores(prev => ({ ...prev, [chave]: { ...prev[chave], [campo]: valor } }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErro(null);

    try {
      const isRealizada = status === 'realizada';
      if (isRealizada) {
        if (!treino) throw new Error("Selecione qual treino foi realizado.");
        const series = seriesParaEnvio(treino.prescricoes, valores);
        if (series.length === 0) throw new Error("Preencha as repetições de pelo menos uma série.");
        await sessaoService.registrarExecucao({
          aluno_id: alunoId,
          treino_id: treino.id,
          // Hoje: o servidor usa a hora atual. Outro dia: meio-dia, para não virar a data por fuso.
          data_hora: data === hojeISO() ? undefined : `${data}T12:00:00`,
          observacoes_performance: observacao || null,
          series,
        });
      } else {
        if (!observacao) throw new Error("Informe o motivo da ausência.");
        await sessaoService.registrar({
          aluno_id: alunoId,
          plano_treino_id: null,
          data_hora: `${data}T12:00:00`,
          realizada: false,
          precisa_reposicao: status === 'falta_com_reposicao',
          motivo_ausencia: observacao,
        });
      }
      onSucesso();
      onClose();
    } catch (err) {
      setErro(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="bg-surface border border-border rounded-[2.5rem] w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl animate-in zoom-in-95 duration-500">

        {/* Header */}
        <div className="p-10 border-b border-border flex justify-between items-center bg-surface">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-brand text-brand-fg rounded-2xl flex items-center justify-center shadow-lg shadow-brand/20">
                <CheckCircle2 size={24} />
            </div>
            <div>
                <h2 className="text-2xl font-black text-text-primary tracking-tight">Registrar Treino</h2>
                <p className="text-text-secondary text-sm font-medium">Reps e carga de cada série.</p>
            </div>
          </div>
          <button onClick={onClose} aria-label="Fechar" className="p-3 bg-overlay text-text-muted hover:text-text-secondary rounded-full transition-all active:scale-90">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-10 space-y-8">
          {erro && (
            <div role="alert" className="p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-600 text-xs font-bold text-center">
              {erro}
            </div>
          )}

          <div className="grid grid-cols-1 gap-8">
            {/* Data */}
            <div className="space-y-2">
                <label htmlFor="data-sessao" className="text-xs font-black text-text-muted uppercase tracking-widest ml-1 flex items-center gap-2">
                    <Calendar size={14} className="text-brand" /> Data da Sessão
                </label>
                <input
                    id="data-sessao"
                    type="date"
                    value={data}
                    max={hojeISO()}
                    onChange={(e) => setData(e.target.value)}
                    className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold outline-none focus:ring-2 focus:ring-brand/10 transition-all"
                    required
                />
            </div>

            {/* Status Selector */}
            <div className="space-y-4">
                <span className="text-xs font-black text-text-muted uppercase tracking-widest ml-1">Status da Aula</span>
                <div className="grid grid-cols-3 gap-3">
                    {[
                        { id: 'realizada', label: 'Presente', icon: CheckCircle2, activeClass: 'bg-brand text-brand-fg border-brand shadow-lg' },
                        { id: 'falta_com_reposicao', label: 'Reposição', icon: Clock, activeClass: 'bg-warning text-brand-fg border-warning shadow-lg' },
                        { id: 'falta_sem_reposicao', label: 'Falta', icon: AlertTriangle, activeClass: 'bg-danger text-brand-fg border-danger shadow-lg' }
                    ].map(s => (
                        <button
                            key={s.id}
                            type="button"
                            aria-pressed={status === s.id}
                            onClick={() => setStatus(s.id)}
                            className={`flex flex-col items-center gap-2 p-4 rounded-2xl border transition-all
                                ${status === s.id
                                    ? s.activeClass
                                    : 'bg-overlay text-text-muted border-border hover:bg-overlay'}`}
                        >
                            <s.icon size={20} />
                            <span className="text-xs font-black uppercase tracking-tight">{s.label}</span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Treino e séries */}
            {status === 'realizada' && (
                <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    <label htmlFor="treino-sessao" className="text-xs font-black text-text-muted uppercase tracking-widest ml-1 flex items-center gap-2">
                        <Dumbbell size={14} className="text-brand" /> Treino Aplicado
                    </label>
                    {treinos.length === 0 ? (
                        <p className="text-xs text-text-muted italic">Aluno sem plano ativo com treinos.</p>
                    ) : (
                        <select
                            id="treino-sessao"
                            value={treinoId}
                            onChange={(e) => setTreinoId(e.target.value)}
                            className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold outline-none appearance-none cursor-pointer"
                        >
                            {treinos.map(t => <option key={t.id} value={t.id}>{t.nome}</option>)}
                        </select>
                    )}

                    {treino?.prescricoes.map(p => (
                        <fieldset key={p.id} className="border border-border rounded-2xl p-4 space-y-2">
                            <legend className="px-2 text-sm font-bold text-text-primary">
                                {p.nome_exercicio} <span className="text-text-muted font-medium">· {p.series}x {p.repeticoes}</span>
                            </legend>
                            {Array.from({ length: p.series || 0 }, (_, i) => i + 1).map(n => {
                                const chave = chaveSerie(p.id, n);
                                return (
                                    <div key={n} className="grid grid-cols-[2rem_1fr_1fr] items-center gap-3">
                                        <span className="text-xs font-bold text-text-muted">{n}</span>
                                        <input
                                            type="number" inputMode="numeric" min="0"
                                            aria-label={`${p.nome_exercicio}, série ${n}, repetições`}
                                            placeholder="reps"
                                            value={valores[chave]?.reps ?? ''}
                                            onChange={(e) => mudarValor(chave, 'reps', e.target.value)}
                                            className="bg-overlay border border-border rounded-xl px-3 py-2 text-text-primary font-bold outline-none focus:ring-2 focus:ring-brand/10"
                                        />
                                        <input
                                            type="number" inputMode="decimal" min="0" step="0.5"
                                            aria-label={`${p.nome_exercicio}, série ${n}, carga em kg`}
                                            placeholder="kg"
                                            value={valores[chave]?.kg ?? ''}
                                            onChange={(e) => mudarValor(chave, 'kg', e.target.value)}
                                            className="bg-overlay border border-border rounded-xl px-3 py-2 text-text-primary font-bold outline-none focus:ring-2 focus:ring-brand/10"
                                        />
                                    </div>
                                );
                            })}
                        </fieldset>
                    ))}
                </div>
            )}

            {/* Observação */}
            <div className="space-y-2">
                <label htmlFor="obs-sessao" className="text-xs font-black text-text-muted uppercase tracking-widest ml-1 flex items-center gap-2">
                    <MessageSquare size={14} className="text-brand" />
                    {status === 'realizada' ? 'Notas de Performance' : 'Motivo da Ausência'}
                </label>
                <textarea
                    id="obs-sessao"
                    value={observacao}
                    onChange={(e) => setObservacao(e.target.value)}
                    placeholder={status === 'realizada' ? "Ex: Evoluiu carga..." : "Ex: Problema de saúde..."}
                    className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-medium outline-none min-h-[100px] resize-none focus:ring-2 focus:ring-brand/10 transition-all placeholder:text-text-muted"
                />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`w-full py-5 rounded-[2rem] font-black text-xs uppercase tracking-widest transition-all shadow-xl active:scale-95 flex items-center justify-center gap-3
                ${loading ? 'bg-overlay text-text-muted' : 'bg-brand hover:bg-brand-hover text-brand-fg shadow-brand/20'}`}
          >
            {loading ? <div className="w-4 h-4 border-2 border-text-muted border-t-transparent rounded-full animate-spin" /> : <CheckCircle2 size={18} />}
            {loading ? 'Sincronizando...' : 'Salvar Registro'}
          </button>
        </form>
      </div>
    </div>
  );
}
