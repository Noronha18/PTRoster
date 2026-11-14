import { useState, useEffect } from 'react';
import { Book, Search, Plus, X, Save } from 'lucide-react';
import { treinoService } from '../../services/api';
import { useToast } from '../../components/ToastProvider';
import { GRUPOS_MUSCULARES } from '../../constants/treino';

export const BibliotecaExercicios = ({ onSelectExercicio }) => {
    const toast = useToast();
    const [exercicios, setExercicios] = useState([]);
    const [grupoAtivo, setGrupoAtivo] = useState('Todos');
    const [busca, setBusca] = useState('');
    const [loading, setLoading] = useState(true);
    const [erro, setErro] = useState(null);
    
    // Estado do Modal de Cadastro
    const [showModal, setShowModal] = useState(false);
    const [novoExercicio, setNovoExercicio] = useState({
        nome: '',
        grupo_muscular: '',
        grupos_secundarios: [],
        video_url: ''
    });
    const [salvando, setSalvando] = useState(false);

    const carregar = async () => {
        try {
            setLoading(true);
            const data = await treinoService.listarExercicios();
            setExercicios(data || []);
            setErro(null);
        } catch (err) {
            console.error("Biblioteca: Erro ao carregar", err);
            setErro("Falha ao carregar biblioteca");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        carregar();
    }, []);

    const handleSalvar = async (e) => {
        e.preventDefault();
        if (!novoExercicio.nome || !novoExercicio.grupo_muscular) return;

        try {
            setSalvando(true);
            await treinoService.criarExercicio(novoExercicio);
            await carregar(); // Recarrega a lista
            setShowModal(false);
            setNovoExercicio({ nome: '', grupo_muscular: '', grupos_secundarios: [], video_url: '' });
        } catch (err) {
            toast({ tipo: 'erro', texto: err.message || "Erro ao salvar exercício" });
        } finally {
            setSalvando(false);
        }
    };

    // Um exercício pertence ao grupo principal e aos secundários (ex.: supino em Peito e em Tríceps).
    const trabalha = (ex, grupo) => ex.grupo_muscular === grupo || (ex.grupos_secundarios || []).includes(grupo);

    const grupos = [
        'Todos',
        ...GRUPOS_MUSCULARES.filter(grupo => exercicios.some(ex => trabalha(ex, grupo))),
    ];

    const alternarSecundario = (grupo) => {
        setNovoExercicio((atual) => {
            const lista = atual.grupos_secundarios;
            return {
                ...atual,
                grupos_secundarios: lista.includes(grupo) ? lista.filter(g => g !== grupo) : [...lista, grupo],
            };
        });
    };

    const exerciciosFiltrados = exercicios.filter(ex => {
        const matchesGrupo = grupoAtivo === 'Todos' || trabalha(ex, grupoAtivo);
        const matchesBusca = ex.nome.toLowerCase().includes(busca.toLowerCase());
        return matchesGrupo && matchesBusca;
    });

    return (
        <div className="bg-surface border border-border rounded-[2.5rem] p-8 shadow-sm h-full flex flex-col min-h-[400px] animate-in fade-in duration-700">
            <div className="mb-8 space-y-6">
                <div className="flex justify-between items-center">
                    <h3 className="text-xl font-black text-text-primary flex items-center gap-2 tracking-tight">
                        <Book className="text-brand" size={20} /> Biblioteca
                    </h3>
                    <button
                        onClick={() => setShowModal(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-overlay hover:bg-brand hover:text-brand-fg text-brand rounded-xl text-xs font-black uppercase tracking-widest transition-all"
                    >
                        <Plus size={14} /> Novo
                    </button>
                </div>
                
                <div className="relative group">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-brand transition-colors" size={16} />
                    <input
                        type="text"
                        placeholder="Buscar exercício..."
                        className="w-full bg-overlay border border-border rounded-2xl pl-12 pr-4 py-4 text-sm text-text-primary font-bold focus:ring-2 focus:ring-brand/10 outline-none transition-all placeholder:text-text-muted"
                        value={busca}
                        onChange={(e) => setBusca(e.target.value)}
                    />
                </div>

                <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                    {grupos.map(grupo => (
                        <button
                            key={grupo}
                            onClick={() => setGrupoAtivo(grupo)}
                            className={`px-5 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest whitespace-nowrap transition-all border
                ${grupoAtivo === grupo
                  ? 'bg-brand text-brand-fg border-brand shadow-lg shadow-brand/20'
                  : 'bg-overlay text-text-muted border-border hover:text-text-secondary hover:bg-overlay'}`}
                        >
                            {grupo}
                        </button>
                    ))}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-2 custom-scrollbar">
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-20 space-y-3">
                        <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin"></div>
                        <p className="text-xs font-black text-text-muted uppercase tracking-widest animate-pulse">Sincronizando...</p>
                    </div>
                ) : erro ? (
                    <div className="text-center py-10 text-red-500 text-xs font-bold uppercase">{erro}</div>
                ) : exerciciosFiltrados.length === 0 ? (
                    <div className="text-center py-20 text-text-muted text-xs font-black uppercase tracking-widest opacity-50 italic">
                        Nenhum resultado.
                    </div>
                ) : (
                    exerciciosFiltrados.map(ex => (
                        <div
                            key={ex.id}
                            onClick={() => onSelectExercicio(ex)}
                            className="p-5 bg-surface border border-border rounded-2xl hover:border-brand/30 hover:bg-overlay transition-all cursor-pointer group"
                        >
                            <div className="flex justify-between items-center">
                                <div>
                                    <p className="text-lg font-bold text-text-primary group-hover:text-brand transition-colors leading-tight">{ex.nome}</p>
                                    <p className="text-xs text-text-muted uppercase font-black tracking-widest mt-1 group-hover:text-text-secondary">
                                        {ex.grupo_muscular}
                                        {ex.grupos_secundarios?.length > 0 && (
                                            <span className="normal-case font-bold tracking-normal"> · também {ex.grupos_secundarios.join(', ')}</span>
                                        )}
                                    </p>
                                </div>
                                <div className="w-8 h-8 rounded-xl bg-overlay border border-border flex items-center justify-center text-text-muted group-hover:text-brand group-hover:border-brand/20 group-hover:bg-surface transition-all shadow-sm">
                                    <Plus size={16} />
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Modal de Cadastro */}
            {showModal && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
                    <div className="bg-surface border border-border w-full max-w-md rounded-[2.5rem] p-10 shadow-2xl animate-in zoom-in-95 duration-500">
                        <div className="flex justify-between items-center mb-8">
                            <h2 className="text-2xl font-black text-text-primary tracking-tight">Novo Exercício</h2>
                            <button onClick={() => setShowModal(false)} className="p-2 bg-overlay text-text-muted hover:text-text-secondary rounded-full transition-all">
                                <X size={20} />
                            </button>
                        </div>

                        <form onSubmit={handleSalvar} className="space-y-6">
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Nome do Exercício</label>
                                <input
                                    type="text"
                                    required
                                    className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold focus:ring-2 focus:ring-brand/20 outline-none transition-all placeholder:text-text-muted"
                                    value={novoExercicio.nome}
                                    onChange={(e) => setNovoExercicio({...novoExercicio, nome: e.target.value})}
                                    placeholder="Ex: Supino Reto"
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Grupo Muscular</label>
                                <select
                                    required
                                    className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold focus:ring-2 focus:ring-brand/20 outline-none transition-all cursor-pointer"
                                    value={novoExercicio.grupo_muscular}
                                    onChange={(e) => setNovoExercicio({
                                        ...novoExercicio,
                                        grupo_muscular: e.target.value,
                                        grupos_secundarios: novoExercicio.grupos_secundarios.filter(g => g !== e.target.value),
                                    })}
                                >
                                    <option value="" disabled>Selecione...</option>
                                    {GRUPOS_MUSCULARES.map((grupo) => (
                                        <option key={grupo} value={grupo}>{grupo}</option>
                                    ))}
                                </select>
                            </div>

                            <fieldset className="space-y-2">
                                <legend className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Também trabalha (opcional)</legend>
                                <p className="text-xs text-text-muted ml-1">Aparece no filtro desses grupos. Só o principal conta no volume semanal.</p>
                                <div className="flex flex-wrap gap-1.5">
                                    {GRUPOS_MUSCULARES.filter(g => g !== novoExercicio.grupo_muscular).map((grupo) => {
                                        const marcado = novoExercicio.grupos_secundarios.includes(grupo);
                                        return (
                                            <button
                                                key={grupo}
                                                type="button"
                                                aria-pressed={marcado}
                                                onClick={() => alternarSecundario(grupo)}
                                                className={`px-3 py-1.5 rounded-xl text-xs font-black uppercase tracking-widest border transition-all ${
                                                    marcado
                                                        ? 'bg-brand text-brand-fg border-brand'
                                                        : 'bg-overlay text-text-muted border-border hover:text-text-secondary'
                                                }`}
                                            >
                                                {grupo}
                                            </button>
                                        );
                                    })}
                                </div>
                            </fieldset>

                            <div className="space-y-2">
                                <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">URL do Vídeo (Opcional)</label>
                                <input
                                    type="url"
                                    className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold focus:ring-2 focus:ring-brand/20 outline-none transition-all placeholder:text-text-muted"
                                    value={novoExercicio.video_url}
                                    onChange={(e) => setNovoExercicio({...novoExercicio, video_url: e.target.value})}
                                    placeholder="https://youtube.com/..."
                                />
                            </div>

                            <div className="flex gap-3 pt-6">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="flex-1 px-6 py-4 bg-overlay hover:bg-overlay text-text-muted rounded-2xl text-xs font-black uppercase tracking-widest transition-all"
                                >
                                    Voltar
                                </button>
                                <button
                                    type="submit"
                                    disabled={salvando}
                                    className="flex-1 flex items-center justify-center gap-2 px-6 py-4 bg-brand hover:bg-brand-hover disabled:opacity-50 text-brand-fg rounded-2xl text-xs font-black uppercase tracking-widest transition-all shadow-lg shadow-brand/20"
                                >
                                    {salvando ? 'Salvando...' : <><Save size={16} /> Salvar</>}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};
