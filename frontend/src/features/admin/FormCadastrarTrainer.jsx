import { useState } from 'react';
import { UserPlus, Eye, EyeOff, XCircle } from 'lucide-react';
import { adminService } from '../../services/api';

export function FormCadastrarTrainer({ onSuccess, onCancel }) {
    const [form, setForm] = useState({
        username: '',
        email: '',
        password: '',
        valor_mensal: '',
        dia_vencimento: '',
    });
    const [loading, setLoading] = useState(false);
    const [erro, setErro] = useState('');
    const [mostrarSenha, setMostrarSenha] = useState(false);

    const handleChange = (e) => setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

    const handleSubmit = async (e) => {
        e.preventDefault();
        setErro('');
        setLoading(true);
        try {
            await adminService.criarTrainer({
                ...form,
                valor_mensal: form.valor_mensal === '' ? null : Number(form.valor_mensal),
                dia_vencimento: form.dia_vencimento === '' ? null : Number(form.dia_vencimento),
            });
            setForm({
                username: '',
                email: '',
                password: '',
                valor_mensal: '',
                dia_vencimento: '',
            });
            onSuccess();
        } catch (err) {
            setErro(err.message || 'Erro ao cadastrar trainer.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center gap-3 mb-6">
                <div className="w-9 h-9 rounded-xl bg-brand/10 flex items-center justify-center">
                    <UserPlus size={18} className="text-brand" />
                </div>
                <div>
                    <h2 className="text-sm font-black text-text-primary">Cadastrar Personal</h2>
                    <p className="text-xs text-text-muted">Cria uma nova conta com acesso de treinador</p>
                </div>
            </div>

            {erro && (
                <div className="p-3 bg-danger/10 border border-danger/20 text-danger text-xs font-bold rounded-xl flex items-center gap-2">
                    <XCircle size={14} /> {erro}
                </div>
            )}

            <div className="space-y-1.5">
                <label htmlFor="novo-personal-usuario" className="text-[10px] font-black uppercase tracking-widest text-text-muted">Usuário</label>
                <input
                    id="novo-personal-usuario"
                    name="username"
                    value={form.username}
                    onChange={handleChange}
                    required
                    placeholder="ex: joao.silva"
                    className="w-full bg-overlay border border-border rounded-xl px-4 py-3 text-sm text-text-primary font-bold focus:outline-none focus:ring-4 focus:ring-brand/10 transition-all placeholder:text-text-muted"
                />
            </div>

            <div className="space-y-1.5">
                <label htmlFor="novo-personal-email" className="text-[10px] font-black uppercase tracking-widest text-text-muted">E-mail</label>
                <input
                    id="novo-personal-email"
                    name="email"
                    type="email"
                    value={form.email}
                    onChange={handleChange}
                    required
                    placeholder="trainer@academia.com"
                    className="w-full bg-overlay border border-border rounded-xl px-4 py-3 text-sm text-text-primary font-bold focus:outline-none focus:ring-4 focus:ring-brand/10 transition-all placeholder:text-text-muted"
                />
            </div>

            <div className="space-y-1.5">
                <label htmlFor="novo-personal-senha" className="text-[10px] font-black uppercase tracking-widest text-text-muted">Senha</label>
                <div className="relative">
                    <input
                        id="novo-personal-senha"
                        name="password"
                        type={mostrarSenha ? 'text' : 'password'}
                        value={form.password}
                        onChange={handleChange}
                        required
                        minLength={6}
                        placeholder="Mínimo 6 caracteres"
                        className="w-full bg-overlay border border-border rounded-xl px-4 py-3 pr-12 text-sm text-text-primary font-bold focus:outline-none focus:ring-4 focus:ring-brand/10 transition-all placeholder:text-text-muted"
                    />
                    <button
                        type="button"
                        onClick={() => setMostrarSenha((v) => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
                        aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
                    >
                        {mostrarSenha ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                    <label htmlFor="novo-personal-valor" className="text-[10px] font-black uppercase tracking-widest text-text-muted">Mensalidade (opcional)</label>
                    <input
                        id="novo-personal-valor"
                        name="valor_mensal"
                        type="number"
                        min="0"
                        step="0.01"
                        value={form.valor_mensal}
                        onChange={handleChange}
                        placeholder="0,00"
                        className="w-full bg-overlay border border-border rounded-xl px-4 py-3 text-sm text-text-primary font-bold focus:outline-none focus:ring-4 focus:ring-brand/10 transition-all placeholder:text-text-muted"
                    />
                </div>
                <div className="space-y-1.5">
                    <label htmlFor="novo-personal-vencimento" className="text-[10px] font-black uppercase tracking-widest text-text-muted">Vencimento</label>
                    <input
                        id="novo-personal-vencimento"
                        name="dia_vencimento"
                        type="number"
                        min="1"
                        max="31"
                        value={form.dia_vencimento}
                        onChange={handleChange}
                        placeholder="dia 5"
                        className="w-full bg-overlay border border-border rounded-xl px-4 py-3 text-sm text-text-primary font-bold focus:outline-none focus:ring-4 focus:ring-brand/10 transition-all placeholder:text-text-muted"
                    />
                </div>
            </div>
            <p className="text-[10px] text-text-muted">Pode definir ou alterar o plano depois em Operações.</p>

            <div className="flex gap-3 pt-2">
                {onCancel && (
                    <button
                        type="button"
                        onClick={onCancel}
                        className="flex-1 py-3 rounded-xl font-black text-xs uppercase tracking-widest text-text-muted bg-overlay hover:bg-border transition-all active:scale-95"
                    >
                        Cancelar
                    </button>
                )}
                <button
                    type="submit"
                    disabled={loading}
                    className="flex-1 py-3 rounded-xl font-black text-xs uppercase tracking-widest transition-all active:scale-95 bg-brand hover:bg-brand-hover text-brand-fg shadow-lg shadow-brand/20 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {loading ? 'Cadastrando...' : 'Cadastrar Personal'}
                </button>
            </div>
        </form>
    );
}
