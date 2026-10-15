import { useState, useEffect } from 'react';
import { alunoService, adminService, getUserRole } from '../../services/api';

export const FormAlunoModal = ({ isOpen, onClose, onSuccess, alunoEdicao = null }) => {
    const isAdmin = getUserRole() === 'admin';
    const [loading, setLoading] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);
    const [error, setError] = useState('');
    const [trainers, setTrainers] = useState([]);
    const [formData, setFormData] = useState({
        nome: '',
        email: '',
        cpf: '',
        dia_vencimento: 5,
        tipo_pagamento: 'mensal',
        frequencia_semanal_plano: 3,
        valor_mensalidade: 0,
        idade: '',
        objetivo: '',
        restricoes: '',
        username: '',
        password: '',
        trainer_id: null,
        modalidade: 'presencial',
        data_vencimento_consultoria: '',
        bloquear_apos_vencimento: false,
    });

    useEffect(() => {
        if (isOpen && isAdmin) {
            adminService.listarTrainers().then(setTrainers).catch(() => {});
        }
    }, [isOpen, isAdmin]);

    useEffect(() => {
        if (isOpen && alunoEdicao) {
            setFormData({
                nome: alunoEdicao.nome || '',
                email: alunoEdicao.email || '',
                cpf: alunoEdicao.cpf || '',
                dia_vencimento: alunoEdicao.dia_vencimento || 5,
                tipo_pagamento: alunoEdicao.tipo_pagamento || 'mensal',
                frequencia_semanal_plano: alunoEdicao.frequencia_semanal_plano || 3,
                valor_mensalidade: alunoEdicao.valor_mensalidade || 0,
                idade: alunoEdicao.idade ?? '',
                objetivo: alunoEdicao.objetivo || '',
                restricoes: alunoEdicao.restricoes || '',
                username: alunoEdicao.usuario?.username || '',
                password: '',
                trainer_id: alunoEdicao.trainer_id ?? null,
                modalidade: alunoEdicao.modalidade || 'presencial',
                data_vencimento_consultoria: alunoEdicao.data_vencimento_consultoria || '',
                bloquear_apos_vencimento: !!alunoEdicao.bloquear_apos_vencimento,
            });
        } else if (isOpen) {
            setFormData({
                nome: '',
                email: '',
                cpf: '',
                dia_vencimento: 5,
                tipo_pagamento: 'mensal',
                frequencia_semanal_plano: 3,
                valor_mensalidade: 0,
                idade: '',
                objetivo: '',
                restricoes: '',
                username: '',
                password: '',
                trainer_id: null,
                modalidade: 'presencial',
                data_vencimento_consultoria: '',
                bloquear_apos_vencimento: false,
            });
        }
    }, [isOpen, alunoEdicao]);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        // Limpeza de dados para evitar strings vazias em campos opcionais
        const cleanData = {
            ...formData,
            cpf: formData.cpf?.trim() || null,
            email: formData.email?.trim() || null,
            idade: formData.idade === '' ? 0 : parseInt(formData.idade),
            objetivo: formData.objetivo?.trim() || null,
            restricoes: formData.restricoes?.trim() || null,
            username: formData.username?.trim() || null,
            password: formData.password?.trim() || null,
            trainer_id: formData.trainer_id ? parseInt(formData.trainer_id) : null,
            data_vencimento_consultoria: formData.modalidade === 'consultoria'
                ? (formData.data_vencimento_consultoria || null)
                : null,
            bloquear_apos_vencimento: formData.modalidade === 'consultoria' && formData.bloquear_apos_vencimento,
        };

        try {
            if (alunoEdicao) {
                await alunoService.atualizar(alunoEdicao.id, cleanData);
            } else {
                await alunoService.criar(cleanData);
            }
            
            setIsSuccess(true);
            
            // Aguarda um pouco para mostrar a mensagem de sucesso antes de fechar
            setTimeout(() => {
                onSuccess();
                onClose();
                // Reseta o estado para o próximo uso
                setIsSuccess(false);
            }, 2000);

        } catch (err) {
            setError(err.message || 'Erro ao processar solicitação');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="form-aluno-titulo"
                className="bg-surface border border-border w-full max-w-2xl rounded-[2.5rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-500"
            >
                <div className="p-10 border-b border-border flex justify-between items-center bg-surface">
                    <div>
                        <h2 id="form-aluno-titulo" className="text-3xl font-black text-text-primary tracking-tight">
                            {isSuccess ? 'Sucesso!' : alunoEdicao ? 'Editar Aluno' : 'Novo Aluno'}
                        </h2>
                        <p className="text-text-secondary text-sm font-medium">
                            {isSuccess 
                                ? `O aluno foi ${alunoEdicao ? 'atualizado' : 'cadastrado'} com sucesso.` 
                                : alunoEdicao 
                                    ? 'Atualize os dados cadastrais e financeiros do aluno.' 
                                    : 'Preencha os dados básicos para iniciar o acompanhamento.'}
                        </p>
                    </div>
                    {!isSuccess && (
                        <button onClick={onClose} aria-label="Fechar formulário" className="p-3 bg-overlay text-text-muted hover:text-text-secondary rounded-full transition-all active:scale-90">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="rotate-45"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                        </button>
                    )}
                </div>

                {isSuccess ? (
                    <div className="p-20 flex flex-col items-center justify-center space-y-6 animate-in zoom-in duration-500">
                        <div className="w-20 h-20 bg-brand rounded-full flex items-center justify-center text-brand-fg shadow-xl shadow-brand/20">
                            <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        </div>
                        <p className="text-text-primary font-bold text-lg text-center">{alunoEdicao ? 'Atualização finalizada!' : 'Cadastro finalizado!'}</p>
                        <p className="text-text-muted text-sm font-medium">Sincronizando com a base de dados...</p>
                    </div>
                ) : (
                    <>
                        <form id="form-aluno" onSubmit={handleSubmit} className="p-10 space-y-8 max-h-[70vh] overflow-y-auto custom-scrollbar">
                            {error && (
                                <div className="p-4 bg-danger/10 border border-danger/20 text-danger text-sm font-bold rounded-2xl text-center">
                                    {error}
                                </div>
                            )}

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Nome Completo</label>
                                    <input 
                                        required
                                        type="text"
                                        className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold focus:ring-2 focus:ring-brand/20 outline-none transition-all placeholder:text-text-muted"
                                        value={formData.nome}
                                        onChange={(e) => setFormData({...formData, nome: e.target.value})}
                                        placeholder="Ex: João Silva"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">E-mail (Opcional)</label>
                                    <input 
                                        type="email"
                                        className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold focus:ring-2 focus:ring-brand/20 outline-none transition-all placeholder:text-text-muted"
                                        value={formData.email}
                                        onChange={(e) => setFormData({...formData, email: e.target.value})}
                                        placeholder="joao@email.com"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">CPF (Opcional)</label>
                                    <input 
                                        type="text"
                                        className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold focus:ring-2 focus:ring-brand/20 outline-none transition-all placeholder:text-text-muted"
                                        value={formData.cpf}
                                        onChange={(e) => setFormData({...formData, cpf: e.target.value})}
                                        placeholder="000.000.000-00"
                                    />
                                </div>
                                    {isAdmin && (
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Trainer Responsável</label>
                                        <select
                                            className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold outline-none focus:ring-2 focus:ring-brand/20"
                                            value={formData.trainer_id ?? ''}
                                            onChange={(e) => setFormData({ ...formData, trainer_id: e.target.value || null })}
                                        >
                                            <option value="">— Sem trainer —</option>
                                            {trainers.map((t) => (
                                                <option key={t.id} value={t.id}>{t.username}</option>
                                            ))}
                                        </select>
                                    </div>
                                )}
                            </div>

                            {!alunoEdicao && (
                                <div className="p-8 bg-brand/5 rounded-[2rem] border border-brand/10 space-y-6 animate-in slide-in-from-top-4 duration-500">
                                    <div className="flex items-center gap-3">
                                        <div className="w-8 h-8 bg-brand rounded-full flex items-center justify-center text-brand-fg shadow-lg shadow-brand/20">
                                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                        </div>
                                        <h3 className="text-xs font-black text-brand uppercase tracking-widest">Credenciais de Acesso</h3>
                                    </div>
                                    
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-2">
                                            <label className="text-xs font-bold text-brand/80 uppercase tracking-wide ml-1">Usuário (Login)</label>
                                            <input 
                                                type="text"
                                                className="w-full bg-surface border border-brand/20 rounded-2xl px-5 py-4 text-text-primary font-semibold outline-none focus:ring-2 focus:ring-brand/20 transition-all"
                                                placeholder="Ex: joaosilva"
                                                value={formData.username}
                                                onChange={(e) => setFormData({...formData, username: e.target.value})}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-xs font-bold text-brand/80 uppercase tracking-wide ml-1">Senha Temporária</label>
                                            <input 
                                                type="text"
                                                className="w-full bg-surface border border-brand/20 rounded-2xl px-5 py-4 text-text-primary font-semibold outline-none focus:ring-2 focus:ring-brand/20 transition-all"
                                                placeholder="Ex: aluno123"
                                                value={formData.password}
                                                onChange={(e) => setFormData({...formData, password: e.target.value})}
                                            />
                                        </div>
                                    </div>
                                </div>
                            )}

                    <div className="space-y-4">
                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Tipo de Atendimento</label>
                        <div className="flex gap-4">
                            {[
                                { id: 'presencial', label: 'Presencial' },
                                { id: 'consultoria', label: 'Consultoria' }
                            ].map(m => (
                                <button
                                    key={m.id}
                                    type="button"
                                    aria-pressed={formData.modalidade === m.id}
                                    onClick={() => setFormData({...formData, modalidade: m.id})}
                                    className={`flex-1 py-4 rounded-2xl text-xs font-black uppercase tracking-widest transition-all border
                                        ${formData.modalidade === m.id
                                            ? 'bg-brand text-brand-fg border-brand shadow-lg shadow-brand/20'
                                            : 'bg-overlay text-text-muted border-border hover:bg-overlay'}`}
                                >
                                    {m.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {formData.modalidade === 'consultoria' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-end animate-in fade-in duration-300">
                            <div className="space-y-2">
                                <label htmlFor="venc-consultoria" className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Vencimento da Consultoria</label>
                                <input
                                    id="venc-consultoria"
                                    required
                                    type="date"
                                    className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold outline-none focus:ring-2 focus:ring-brand/20"
                                    value={formData.data_vencimento_consultoria}
                                    onChange={(e) => setFormData({...formData, data_vencimento_consultoria: e.target.value})}
                                />
                            </div>
                            <label className="flex items-center gap-3 px-1 py-4 cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="w-5 h-5 accent-[var(--color-brand)]"
                                    checked={formData.bloquear_apos_vencimento}
                                    onChange={(e) => setFormData({...formData, bloquear_apos_vencimento: e.target.checked})}
                                />
                                <span className="text-sm font-semibold text-text-primary">Bloquear acesso aos treinos após o vencimento</span>
                            </label>
                        </div>
                    )}

                    {formData.modalidade === 'presencial' && (
                    <div className="space-y-4">
                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Modalidade de Pagamento</label>
                        <div className="flex gap-4">
                            {[
                                { id: 'mensal', label: 'Mensalidade' },
                                { id: 'pacote', label: 'Pacote de Aulas' }
                            ].map(tipo => (
                                <button
                                    key={tipo.id}
                                    type="button"
                                    onClick={() => setFormData({...formData, tipo_pagamento: tipo.id})}
                                    className={`flex-1 py-4 rounded-2xl text-xs font-black uppercase tracking-widest transition-all border
                                        ${formData.tipo_pagamento === tipo.id 
                                            ? 'bg-brand text-brand-fg border-brand shadow-lg shadow-brand/20'
                                            : 'bg-overlay text-text-muted border-border hover:bg-overlay'}`}
                                >
                                    {tipo.label}
                                </button>
                            ))}
                        </div>
                    </div>
                    )}

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Frequência</label>
                            <select 
                                className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold outline-none"
                                value={formData.frequencia_semanal_plano}
                                onChange={(e) => setFormData({...formData, frequencia_semanal_plano: parseInt(e.target.value)})}
                            >
                                <option value={1}>1x na semana</option>
                                <option value={2}>2x na semana</option>
                                <option value={3}>3x na semana</option>
                                <option value={4}>4x na semana</option>
                                <option value={5}>5x na semana</option>
                                <option value={6}>6x na semana</option>
                                <option value={7}>Livre / Diário</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">
                                {formData.modalidade === 'consultoria'
                                    ? 'Valor da Consultoria'
                                    : formData.tipo_pagamento === 'mensal' ? 'Mensalidade' : 'Valor do Pacote'}
                            </label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none">
                                    <span className="text-text-muted font-bold text-sm">R$</span>
                                </div>
                                <input 
                                    type="text"
                                    className="w-full bg-overlay border border-border rounded-2xl pl-12 pr-5 py-4 text-text-primary font-semibold outline-none focus:ring-2 focus:ring-brand/20 transition-all"
                                    value={new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2 }).format(formData.valor_mensalidade || 0)}
                                    onChange={(e) => {
                                        // Remove tudo que não for dígito
                                        const value = e.target.value.replace(/\D/g, "");
                                        // Converte para float (ex: 1250 vira 12.50)
                                        const floatValue = parseFloat(value) / 100;
                                        setFormData({...formData, valor_mensalidade: floatValue || 0});
                                    }}
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Idade</label>
                            <input 
                                type="number"
                                className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold"
                                value={formData.idade}
                                onChange={(e) => setFormData({...formData, idade: e.target.value})}
                            />
                        </div>
                        {formData.modalidade === 'presencial' && formData.tipo_pagamento === 'mensal' && (
                            <div className="space-y-2 animate-in fade-in slide-in-from-right-4 duration-500">
                                <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Vencimento</label>
                                <input 
                                    type="number"
                                    min="1"
                                max="31"
                                    className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold focus:ring-2 focus:ring-brand/20 outline-none"
                                    value={formData.dia_vencimento}
                                    onChange={(e) => setFormData({...formData, dia_vencimento: parseInt(e.target.value) || 0})}
                                />
                            </div>
                        )}
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Objetivo Estratégico</label>
                        <textarea 
                            rows="2"
                            className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold outline-none focus:ring-2 focus:ring-brand/20 transition-all placeholder:text-text-muted"
                            placeholder="Ex: Hipertrofia focada em membros inferiores..."
                            value={formData.objetivo}
                            onChange={(e) => setFormData({...formData, objetivo: e.target.value})}
                        ></textarea>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Restrições / Patologias</label>
                        <textarea 
                            rows="2"
                            className="w-full bg-overlay border border-border rounded-2xl px-5 py-4 text-text-primary font-semibold outline-none focus:ring-2 focus:ring-brand/20 transition-all placeholder:text-text-muted"
                            placeholder="Ex: Condromalácia patelar grau 2..."
                            value={formData.restricoes}
                            onChange={(e) => setFormData({...formData, restricoes: e.target.value})}
                        ></textarea>
                    </div>
                </form>

                <div className="p-10 border-t border-border bg-surface flex flex-col md:flex-row justify-end gap-4">
                    <button
                        type="button"
                        onClick={onClose}
                        className="px-8 py-4 rounded-2xl font-black text-text-muted hover:text-text-secondary hover:bg-overlay transition-all uppercase text-xs tracking-widest"
                    >
                        Cancelar
                    </button>
                    <button 
                        form="form-aluno"
                        type="submit"
                        disabled={loading}
                        className="bg-brand hover:bg-brand-hover text-brand-fg px-12 py-4 rounded-2xl font-black transition-all shadow-lg shadow-brand/20 disabled:opacity-50 active:scale-95 uppercase text-xs tracking-widest"
                    >
                        {loading ? 'Sincronizando...' : alunoEdicao ? 'Salvar Alterações' : 'Finalizar Cadastro'}
                    </button>
                </div>
                </>
                )}
            </div>
        </div>
    );
};
