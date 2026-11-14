import { useState, useEffect } from 'react';
import { Dumbbell, Plus, Book, CheckCircle2, AlertCircle, Trash2, Pencil } from 'lucide-react';
import { alunoService, treinoService } from '../../services/api';
import { ModalPlanoTreino } from '../alunos/ModalPlanoTreino';

export const ModuloTreinos = () => {
    const [alunos, setAlunos] = useState([]);
    const [loading, setLoading] = useState(false);
    const [mensagem, setMensagem] = useState({ tipo: '', texto: '' });
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [templateEdicao, setTemplateEdicao] = useState(null);
    const [templates, setTemplates] = useState([]);

    const carregarDados = async () => {
        try {
            const [listaAlunos, listaTemplates] = await Promise.all([
                alunoService.listar(),
                treinoService.listarTemplates()
            ]);
            setAlunos(listaAlunos);
            setTemplates(listaTemplates);
        } catch {
            // falha silenciosa — dados ficam em estado vazio
        }
    };

    useEffect(() => {
        carregarDados();
    }, []);

    const handleSavePlano = async (payload) => {
        setLoading(true);
        try {
            if (templateEdicao) {
                await treinoService.atualizarPlano(templateEdicao.id, payload);
                setMensagem({ tipo: 'sucesso', texto: 'Modelo atualizado com sucesso!' });
            } else if (payload.aluno_id) {
                await treinoService.criarPlano(payload.aluno_id, payload);
                setMensagem({ tipo: 'sucesso', texto: 'Plano vinculado ao aluno com sucesso!' });
            } else {
                await treinoService.criarTemplate(payload);
                setMensagem({ tipo: 'sucesso', texto: 'Modelo global salvo com sucesso!' });
            }
            setIsModalOpen(false);
            setTemplateEdicao(null);
            carregarDados();
            setTimeout(() => setMensagem({ tipo: '', texto: '' }), 3000);
        } catch (err) {
            setMensagem({ tipo: 'erro', texto: 'Erro ao salvar o plano: ' + err.message });
            return false;
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-700">
            {/* Header com Ações Principais */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-brand text-brand-fg rounded-xl flex items-center justify-center shadow-sm">
                        <Dumbbell size={24} />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold text-text-primary tracking-tight">Módulo de Treinos</h2>
                        <p className="text-text-secondary text-sm font-medium">Modelos e prescrições de alta performance.</p>
                    </div>
                </div>

                <div className="flex gap-3 w-full md:w-auto">
                    <button
                        onClick={() => setIsModalOpen(true)}
                        className="flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 bg-brand text-brand-fg rounded-xl text-xs font-bold uppercase tracking-widest hover:bg-brand-hover transition-all shadow-sm active:scale-95"
                    >
                        <Plus size={16} /> Novo Plano
                    </button>
                </div>
            </div>

            {mensagem.texto && (
                <div className={`p-4 rounded-xl flex items-center gap-3 animate-in slide-in-from-top-4 duration-300 border
                    ${mensagem.tipo === 'sucesso' ? 'bg-brand/10 text-brand border-brand/20' : 'bg-danger/10 text-danger border-danger/20'}`}>
                    {mensagem.tipo === 'sucesso' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                    <span className="text-xs font-bold uppercase tracking-widest">{mensagem.texto}</span>
                </div>
            )}

            {/* Grid de Conteúdo */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Templates Globais */}
                <div className="bg-surface border border-border rounded-xl p-6 shadow-sm">
                    <div className="flex items-center justify-between mb-6">
                        <h3 className="text-lg font-bold text-text-primary flex items-center gap-2">
                            <Book className="text-brand" size={18} /> Modelos Globais
                        </h3>
                        <span className="text-xs font-bold text-text-secondary bg-overlay px-2 py-1 rounded border border-border uppercase tracking-wide">{templates.length} salvos</span>
                    </div>

                    <div className="space-y-3">
                        {templates.map(template => (
                            <div key={template.id} className="p-4 bg-overlay border border-border/60 rounded-lg hover:border-accent/40 transition-all group">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <p className="font-bold text-base text-text-primary group-hover:text-accent transition-colors">{template.titulo}</p>
                                        <p className="text-xs text-text-secondary font-bold uppercase tracking-widest mt-1">
                                            {template.treinos?.length || 0} divisões · {template.duracao_semanas} semanas
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-1">
                                        <button
                                            onClick={() => { setTemplateEdicao(template); setIsModalOpen(true); }}
                                            className="p-2 text-text-muted hover:text-brand hover:bg-brand/10 rounded-md transition-colors"
                                            title="Editar modelo"
                                        >
                                            <Pencil size={14} />
                                        </button>
                                        <button
                                            onClick={async () => {
                                                if (confirm("Deseja apagar este modelo global?")) {
                                                    await treinoService.deletarPlano(template.id);
                                                    carregarDados();
                                                }
                                            }}
                                            className="p-2 text-text-muted hover:text-danger hover:bg-danger/10 rounded-md transition-colors"
                                            title="Apagar modelo"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                        {templates.length === 0 && (
                            <div className="text-center py-8 text-text-muted italic text-xs border border-dashed border-border rounded-lg bg-overlay/50">Nenhum modelo global criado.</div>
                        )}
                    </div>
                </div>

                {/* Info Card */}
                <div className="bg-text-primary rounded-xl p-8 text-brand-fg shadow-lg relative overflow-hidden flex flex-col justify-center border border-border-strong">
                    <div className="relative z-10 space-y-5">
                        <h3 className="text-xl font-bold tracking-tight leading-tight">Prescrição Inteligente</h3>
                        <p className="text-text-secondary text-xs font-medium leading-relaxed max-w-xs">
                            Maximize sua produtividade criando modelos de treino reutilizáveis e aplique-os com um clique.
                        </p>
                        <ul className="space-y-2">
                            {['Até 26 divisões (A-Z)', 'Base de dados customizável', 'Interface otimizada'].map(item => (
                                <li key={item} className="flex items-center gap-2 text-xs font-bold text-accent uppercase tracking-widest">
                                    <CheckCircle2 size={12} className="shrink-0" /> {item}
                                </li>
                            ))}
                        </ul>
                    </div>
                    <Dumbbell className="absolute -right-6 -bottom-6 text-brand-fg/5 w-40 h-40 -rotate-12" />
                </div>
            </div>

            {/* Modal Unificado */}
            <ModalPlanoTreino
                isOpen={isModalOpen}
                onClose={() => { setIsModalOpen(false); setTemplateEdicao(null); }}
                onSave={handleSavePlano}
                planoEdicao={templateEdicao}
                chaveRascunho="modelo"
            />
        </div>
    );
};
