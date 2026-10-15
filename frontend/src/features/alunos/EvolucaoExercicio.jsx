import { useEffect, useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { alunoService } from '../../services/api';

// Mesmos tokens do GraficoReceita (light-only por design)
const CHART = {
    carga: 'oklch(62% 0.14 48)',   // --color-accent
    volume: 'oklch(60% 0.012 82)', // --color-text-muted
    grid: 'oklch(92% 0.006 82)',
    axis: 'oklch(60% 0.012 82)',
};

const kg = (v) => (v == null ? 'PC' : v.toLocaleString('pt-BR'));  // PC = peso corporal
const dataCurta = (iso) => new Date(`${iso}T00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });

export const EvolucaoExercicio = ({ alunoId }) => {
    const [exercicios, setExercicios] = useState([]);
    const [exercicioId, setExercicioId] = useState('');
    const [semanas, setSemanas] = useState([]);

    useEffect(() => {
        alunoService.evolucao(alunoId)
            .then(d => { setExercicios(d.exercicios); setExercicioId(d.exercicios[0]?.id ?? ''); })
            .catch(() => setExercicios([]));
    }, [alunoId]);

    useEffect(() => {
        if (!exercicioId) return;
        alunoService.evolucao(alunoId, exercicioId).then(d => setSemanas(d.semanas)).catch(() => setSemanas([]));
    }, [alunoId, exercicioId]);

    if (exercicios.length === 0) return null;

    const dados = semanas.map(s => ({
        semana: dataCurta(s.semana_inicio),
        carga_max: s.carga_max,
        volume: Math.round(s.volume_carga),
    }));

    return (
        <section aria-labelledby="evolucao-titulo" className="bg-surface border border-border rounded-xl p-6 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <h3 id="evolucao-titulo" className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                    <TrendingUp size={14} className="text-brand" /> Evolução
                </h3>
                <select
                    value={exercicioId}
                    onChange={(e) => setExercicioId(Number(e.target.value))}
                    aria-label="Exercício"
                    className="bg-overlay border border-border rounded-lg px-3 py-2 text-sm font-bold text-text-primary outline-none cursor-pointer"
                >
                    {exercicios.map(ex => <option key={ex.id} value={ex.id}>{ex.nome}</option>)}
                </select>
            </div>

            {dados.length > 1 && (
                <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={dados} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                            <XAxis dataKey="semana" axisLine={false} tickLine={false} tick={{ fill: CHART.axis, fontSize: 10 }} />
                            <YAxis yAxisId="carga" axisLine={false} tickLine={false} tick={{ fill: CHART.axis, fontSize: 10 }} />
                            <YAxis yAxisId="volume" orientation="right" axisLine={false} tickLine={false} tick={{ fill: CHART.axis, fontSize: 10 }} />
                            <Tooltip />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Line yAxisId="carga" dataKey="carga_max" name="Carga máx. (kg)" stroke={CHART.carga} strokeWidth={2} connectNulls />
                            <Line yAxisId="volume" dataKey="volume" name="Volume (reps × kg)" stroke={CHART.volume} strokeDasharray="4 4" />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}

            <div className="overflow-x-auto">
                <table className="w-full text-xs">
                    <thead>
                        <tr className="text-text-muted uppercase tracking-widest text-left">
                            <th className="py-2 pr-4 font-bold">Semana</th>
                            <th className="py-2 pr-4 font-bold">Séries (reps×kg)</th>
                            <th className="py-2 pr-4 font-bold text-right">Máx.</th>
                            <th className="py-2 font-bold text-right">Volume</th>
                        </tr>
                    </thead>
                    <tbody>
                        {[...semanas].reverse().map(s => (
                            <tr key={s.semana_inicio} className="border-t border-border-faint">
                                <td className="py-2 pr-4 font-mono text-text-secondary">{dataCurta(s.semana_inicio)}</td>
                                <td className="py-2 pr-4 text-text-primary">
                                    {s.series.map(r => `${r.repeticoes}×${kg(r.carga_kg)}`).join(' · ')}
                                </td>
                                <td className="py-2 pr-4 text-right font-bold tabular-nums">{kg(s.carga_max)}</td>
                                <td className="py-2 text-right tabular-nums">{Math.round(s.volume_carga).toLocaleString('pt-BR')}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
};
