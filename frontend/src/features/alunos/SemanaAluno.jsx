import { useCallback, useEffect, useState } from 'react';
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react';
import { alunoService } from '../../services/api';
import { DIAS_SEMANA } from '../../constants/treino';

const hojeLocal = () => {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

const somarDias = (iso, dias) => {
    const d = new Date(`${iso}T12:00:00`);
    d.setDate(d.getDate() + dias);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

const formatarDia = (iso) => {
    if (!iso) return '—';
    const [, mes, dia] = iso.split('-');
    return `${dia}/${mes}`;
};

const rotuloDias = (dias = []) =>
    dias.map((dia) => DIAS_SEMANA[dia]?.curto ?? dia).join(', ') || '—';

export function SemanaAluno({ alunoId }) {
    const [ref, setRef] = useState(hojeLocal);
    const [dados, setDados] = useState(null);
    const [loading, setLoading] = useState(true);
    const [erro, setErro] = useState(null);

    const carregar = useCallback(async () => {
        try {
            setLoading(true);
            setErro(null);
            const data = await alunoService.semana(alunoId, ref);
            setDados(data);
        } catch (err) {
            setErro(err.message || 'Falha ao carregar a semana');
            setDados(null);
        } finally {
            setLoading(false);
        }
    }, [alunoId, ref]);

    useEffect(() => { carregar(); }, [carregar]);

    const totalPlanejado = dados?.volumes?.reduce((soma, v) => soma + v.planejado, 0) ?? 0;
    const totalRealizado = dados?.volumes?.reduce((soma, v) => soma + v.realizado, 0) ?? 0;
    const aderencia = totalPlanejado > 0 ? Math.round((totalRealizado / totalPlanejado) * 100) : 0;

    return (
        <div className="bg-surface border border-border rounded-xl p-6 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <h3 className="text-lg font-bold text-text-primary tracking-tight flex items-center gap-3">
                    <CalendarDays className="text-brand" size={18} /> Semana
                </h3>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setRef((atual) => somarDias(atual, -7))}
                        className="p-2 bg-overlay text-text-muted hover:text-brand rounded-lg transition-all"
                        aria-label="Semana anterior"
                    >
                        <ChevronLeft size={16} />
                    </button>
                    <button
                        onClick={() => setRef(hojeLocal())}
                        className="px-3 py-2 bg-overlay text-text-secondary hover:text-brand rounded-lg text-xs font-black uppercase tracking-widest transition-all"
                    >
                        Hoje
                    </button>
                    <button
                        onClick={() => setRef((atual) => somarDias(atual, 7))}
                        className="p-2 bg-overlay text-text-muted hover:text-brand rounded-lg transition-all"
                        aria-label="Próxima semana"
                    >
                        <ChevronRight size={16} />
                    </button>
                </div>
            </div>

            {dados && (
                <p className="text-xs font-bold text-text-muted uppercase tracking-widest font-mono">
                    {formatarDia(dados.semana_inicio)} — {formatarDia(dados.semana_fim)}
                </p>
            )}

            {loading ? (
                <div className="py-12 text-center text-xs font-black text-text-muted uppercase tracking-widest animate-pulse">
                    Calculando semana...
                </div>
            ) : erro ? (
                <div className="py-8 text-center text-danger text-xs font-bold uppercase tracking-widest">
                    {erro}
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-3 gap-3">
                        <div className="bg-overlay border border-border rounded-xl p-4">
                            <p className="text-2xs font-black text-text-muted uppercase tracking-widest">Planejado</p>
                            <p className="text-2xl font-black text-text-primary mt-1 tabular-nums">{totalPlanejado}</p>
                            <p className="text-2xs text-text-muted font-bold uppercase tracking-widest">séries</p>
                        </div>
                        <div className="bg-overlay border border-border rounded-xl p-4">
                            <p className="text-2xs font-black text-text-muted uppercase tracking-widest">Realizado</p>
                            <p className="text-2xl font-black text-brand mt-1 tabular-nums">{totalRealizado}</p>
                            <p className="text-2xs text-text-muted font-bold uppercase tracking-widest">séries</p>
                        </div>
                        <div className="bg-overlay border border-border rounded-xl p-4">
                            <p className="text-2xs font-black text-text-muted uppercase tracking-widest">Aderência</p>
                            <p className="text-2xl font-black text-accent mt-1 tabular-nums">{aderencia}%</p>
                            <p className="text-2xs text-text-muted font-bold uppercase tracking-widest">do volume</p>
                        </div>
                    </div>

                    <div>
                        <h4 className="text-xs font-black text-text-muted uppercase tracking-widest mb-3">Treinos</h4>
                        {dados.treinos.length === 0 ? (
                            <p className="text-xs text-text-muted italic py-4">Nenhum plano ativo.</p>
                        ) : (
                            <div className="space-y-2">
                                {dados.treinos.map((treino) => {
                                    const completo = treino.feitas >= treino.vezes_por_semana;
                                    return (
                                        <div key={treino.treino_id} className="flex items-center justify-between gap-3 bg-overlay rounded-xl px-4 py-3 border border-border">
                                            <div className="min-w-0">
                                                <p className="text-sm font-bold text-text-primary truncate">{treino.treino_nome}</p>
                                                <p className="text-2xs text-text-muted font-bold uppercase tracking-widest mt-0.5">
                                                    Feito: {rotuloDias(treino.dias_feitos)}
                                                </p>
                                            </div>
                                            <span className={`text-sm font-black tabular-nums shrink-0 ${completo ? 'text-brand' : 'text-text-secondary'}`}>
                                                {treino.feitas}/{treino.vezes_por_semana}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    <div>
                        <h4 className="text-xs font-black text-text-muted uppercase tracking-widest mb-3">Volume por grupo</h4>
                        {dados.volumes.length === 0 ? (
                            <p className="text-xs text-text-muted italic py-4">Sem volume planejado ou registrado.</p>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-xs">
                                    <thead>
                                        <tr className="text-2xs font-black text-text-muted uppercase tracking-widest border-b border-border">
                                            <th className="py-2 pr-3">Grupo</th>
                                            <th className="py-2 px-3 text-right">Planejado</th>
                                            <th className="py-2 px-3 text-right">Realizado</th>
                                            <th className="py-2 pl-3 text-right">Média 4 sem.</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {dados.volumes.map((volume) => (
                                            <tr key={volume.grupo} className="border-b border-border-faint last:border-0">
                                                <td className="py-2.5 pr-3 font-bold text-text-primary">{volume.grupo}</td>
                                                <td className="py-2.5 px-3 text-right font-black text-text-secondary tabular-nums">{volume.planejado}</td>
                                                <td className="py-2.5 px-3 text-right font-black text-brand tabular-nums">{volume.realizado}</td>
                                                <td className="py-2.5 pl-3 text-right font-bold text-text-muted tabular-nums">{volume.media_4_semanas}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
