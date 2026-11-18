import { useState, useEffect, useId } from 'react';
import { Book, Search, Plus, X, Save, Video } from 'lucide-react';
import { treinoService, getUserRole } from '../../services/api';
import { useToast } from '../../components/ToastProvider';
import { GRUPOS_MUSCULARES } from '../../constants/treino';

const normalizar = (texto) => texto.trim().normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();

export const BibliotecaExercicios = ({ onSelectExercicio }) => {
    const toast = useToast();
    const campoId = useId();
    const [erroCadastro, setErroCadastro] = useState(null);
    const [exercicios, setExercicios] = useState([]);
    const [grupoAtivo, setGrupoAtivo] = useState('Todos');
    const [busca, setBusca] = useState('');
    // A lista do personal traz só a base (trainer_id nulo) e os dele: trainer_id preenchido = "Meu".
    const ehAdmin = getUserRole() === 'admin';
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

    // Modal "Trocar vídeo": exercício em edição e URL digitada.
    const [exVideo, setExVideo] = useState(null);
    const [urlVideo, setUrlVideo] = useState('');

    const abrirVideo = (e, ex) => {
        e.stopPropagation(); // não adiciona o exercício ao treino
        setExVideo(ex);
        setUrlVideo(ex.video_url || '');
    };

    const salvarVideo = async (url) => {
        try {
            setSalvando(true);
            await treinoService.definirVideoExercicio(exVideo.id, url);
            await carregar();
            setExVideo(null);
        } catch (err) {
            toast({ tipo: 'erro', texto: err.message || "Erro ao salvar vídeo" });
        } finally {
            setSalvando(false);
        }
    };

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
        if (salvando) return;
        const nome = novoExercicio.nome.trim();
        if (!nome) {
            setErroCadastro('Informe o nome do exercício.');
            return;
        }
        setErroCadastro(null);

        try {
            setSalvando(true);
            await treinoService.criarExercicio({ ...novoExercicio, nome });
            await carregar(); // Recarrega a lista
            setShowModal(false);
            setNovoExercicio({ nome: '', grupo_muscular: '', grupos_secundarios: [], video_url: '' });
        } catch (err) {
            setErroCadastro(err.message || "Não foi possível salvar o exercício.");
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

    const termo = normalizar(busca);
    const exerciciosFiltrados = exercicios.filter(ex => {
        const matchesGrupo = grupoAtivo === 'Todos' || trabalha(ex, grupoAtivo);
        const matchesBusca = normalizar(ex.nome).includes(termo);
        return matchesGrupo && matchesBusca;
    });

    return (
        <div className="bg-surface border border-border p-4 sm:p-5 h-full min-h-0 flex flex-col">
            <div className="mb-3 shrink-0 space-y-3">
                <div className="flex justify-between items-center">
                    <h3 className="text-xl font-black text-text-primary flex items-center gap-2 tracking-tight">
                        <Book className="text-brand" size={20} /> Biblioteca
                    </h3>
                    <button
                        onClick={() => { setErroCadastro(null); setShowModal(true); }}
                        className="flex items-center gap-2 px-4 py-2 bg-overlay hover:bg-brand hover:text-brand-fg text-brand rounded-xl text-xs font-black uppercase tracking-widest transition-all"
                    >
                        <Plus size={14} /> Novo exercício
                    </button>
                </div>
                
                <div className="relative group">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-brand transition-colors" size={16} />
                    <input
                        type="search"
                        aria-label="Buscar exercício pelo nome"
                        placeholder="Buscar exercício"
                        className="w-full bg-overlay border border-border rounded-xl pl-10 pr-4 py-3 text-sm text-text-primary font-bold focus:ring-2 focus:ring-brand/10 outline-none transition-all placeholder:text-text-muted"
                        value={busca}
                        onChange={(e) => setBusca(e.target.value)}
                    />
                </div>

                <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                    {grupos.map(grupo => (
                        <button
                            key={grupo}
                            onClick={() => setGrupoAtivo(grupo)}
                            aria-pressed={grupoAtivo === grupo}
                            className={`px-3 py-2 rounded-lg text-sm font-semibold whitespace-nowrap transition-all border
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
                    <div role="alert" className="py-6 text-center text-sm text-danger">
                        <p>{erro}</p>
                        <button type="button" onClick={carregar} className="min-h-11 underline">Tentar novamente</button>
                    </div>
                ) : exerciciosFiltrados.length === 0 ? (
                    <div className="py-8 text-center text-sm text-text-secondary">
                        <p>Nenhum exercício encontrado.</p>
                        {(termo || grupoAtivo !== 'Todos') && (
                            <button type="button" className="min-h-11 font-semibold underline"
                                onClick={() => { setBusca(''); setGrupoAtivo('Todos'); }}>
                                Limpar filtros
                            </button>
                        )}
                    </div>
                ) : (
                    exerciciosFiltrados.map(ex => (
                        <div
                            key={ex.id}
                            className="flex items-center gap-1 rounded-xl border border-border pr-2"
                        >
                            <button
                                type="button"
                                aria-label={`Adicionar ${ex.nome}`}
                                onClick={() => onSelectExercicio(ex)}
                                className="group flex min-h-11 min-w-0 flex-1 items-center justify-between gap-2 rounded-l-xl p-3 text-left hover:bg-overlay"
                            >
                                <span className="min-w-0 break-words">
                                    <span className="block text-sm font-semibold text-text-primary">{ex.nome}
                                        {!ehAdmin && ex.trainer_id != null && (
                                            <span className="ml-2 align-middle text-[10px] font-bold uppercase tracking-widest text-brand bg-brand/10 border border-brand/20 px-1.5 py-0.5 rounded">Meu</span>
                                        )}
                                    </span>
                                    <span className="mt-1 block text-xs text-text-secondary">
                                        {ex.grupo_muscular}
                                        {ex.grupos_secundarios?.length > 0 && (
                                            <span className="normal-case font-bold tracking-normal"> · também {ex.grupos_secundarios.join(', ')}</span>
                                        )}
                                    </span>
                                </span>
                                <Plus size={16} className="shrink-0 text-text-muted" aria-hidden="true" />
                            </button>
                                    <button
                                        type="button"
                                        title="Trocar vídeo"
                                        aria-label={`Trocar vídeo de ${ex.nome}`}
                                        onClick={(e) => abrirVideo(e, ex)}
                                        className={`h-11 w-11 shrink-0 rounded-xl bg-overlay border flex items-center justify-center hover:text-brand transition-all ${ex.video_proprio ? 'text-brand border-brand/30' : 'text-text-muted border-border'}`}
                                    >
                                        <Video size={14} />
                                    </button>
                        </div>
                    ))
                )}
            </div>

            {/* Modal de Troca de Vídeo */}
            {exVideo && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
                    <div className="bg-surface border border-border w-full max-w-md max-h-[90dvh] overflow-y-auto rounded-xl p-5 sm:p-8 shadow-2xl space-y-6">
                        <div className="flex justify-between items-center">
                            <h2 className="text-2xl font-black text-text-primary tracking-tight">Trocar vídeo</h2>
                            <button onClick={() => setExVideo(null)} disabled={salvando} aria-label="Fechar edição do vídeo" className="p-2 bg-overlay text-text-muted hover:text-text-secondary rounded-full transition-all">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="space-y-1">
                            <p className="text-sm font-bold text-text-primary">{exVideo.nome}</p>
                            <p className="text-xs text-text-muted break-all">Atual: {exVideo.video_url || 'sem vídeo'}</p>
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">URL do vídeo</label>
                            <input
                                type="url"
                                className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold focus:ring-2 focus:ring-brand/20 outline-none transition-all placeholder:text-text-muted"
                                value={urlVideo}
                                onChange={(e) => setUrlVideo(e.target.value)}
                                placeholder="https://youtube.com/..."
                            />
                            <p className="text-xs text-text-muted ml-1">
                                {ehAdmin ? 'Altera o vídeo original, visto por todos.' : 'O vídeo novo aparece só para os seus alunos.'}
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <button
                                type="button"
                                disabled={salvando}
                                onClick={() => setExVideo(null)}
                                className="flex-1 px-6 py-4 bg-overlay text-text-muted rounded-2xl text-xs font-black uppercase tracking-widest transition-all"
                            >
                                Voltar
                            </button>
                            <button
                                type="button"
                                disabled={salvando}
                                onClick={() => salvarVideo(urlVideo.trim())}
                                className="flex-1 flex items-center justify-center gap-2 px-6 py-4 bg-brand hover:bg-brand-hover disabled:opacity-50 text-brand-fg rounded-2xl text-xs font-black uppercase tracking-widest transition-all shadow-lg shadow-brand/20"
                            >
                                {salvando ? 'Salvando...' : <><Save size={16} /> Salvar</>}
                            </button>
                        </div>
                        {exVideo.video_proprio && exVideo.trainer_id == null && (
                            <button
                                type="button"
                                disabled={salvando}
                                onClick={() => salvarVideo(null)}
                                className="w-full px-6 py-3 text-text-muted hover:text-brand text-xs font-black uppercase tracking-widest transition-all"
                            >
                                Voltar ao original
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Modal de Cadastro */}
            {showModal && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
                    <div className="bg-surface border border-border w-full max-w-md max-h-[90dvh] overflow-y-auto rounded-xl p-5 sm:p-8 shadow-2xl animate-in zoom-in-95 duration-500">
                        <div className="flex justify-between items-center mb-8">
                            <h2 className="text-2xl font-black text-text-primary tracking-tight">Novo exercício</h2>
                            <button onClick={() => setShowModal(false)} disabled={salvando} aria-label="Fechar cadastro de exercício" className="p-2 bg-overlay text-text-muted hover:text-text-secondary rounded-full transition-all">
                                <X size={20} />
                            </button>
                        </div>

                        <form onSubmit={handleSalvar} className="space-y-6">
                            <div className="space-y-2">
                                <label htmlFor={`${campoId}-nome`} className="text-sm font-semibold text-text-secondary">Nome do exercício</label>
                                <input
                                    id={`${campoId}-nome`}
                                    type="text"
                                    aria-describedby={erroCadastro ? `${campoId}-erro` : undefined}
                                    required
                                    className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-bold focus:ring-2 focus:ring-brand/20 outline-none transition-all placeholder:text-text-muted"
                                    value={novoExercicio.nome}
                                    onChange={(e) => setNovoExercicio({...novoExercicio, nome: e.target.value})}
                                    placeholder="Ex: Supino Reto"
                                />
                            </div>

                            <div className="space-y-2">
                                <label htmlFor={`${campoId}-grupo`} className="text-sm font-semibold text-text-secondary">Grupo muscular principal</label>
                                <select
                                    id={`${campoId}-grupo`}
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

                            {erroCadastro && <p id={`${campoId}-erro`} role="alert" className="text-sm text-danger">{erroCadastro}</p>}

                            <div className="flex gap-3 pt-3">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    disabled={salvando}
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
