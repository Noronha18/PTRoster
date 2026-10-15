import { useEffect, useState } from 'react';
import { Activity } from 'lucide-react';
import { atividadeService } from '../../services/api';

const POLLING_MS = 30000;
const MAX_EXERCICIOS = 3;

const kg = (v) => v.toLocaleString('pt-BR');

const textoExercicio = ({ nome, carga_max, delta_kg }) => {
    if (carga_max == null) return nome;
    const delta = delta_kg ? ` (${delta_kg > 0 ? '+' : ''}${kg(delta_kg)} kg)` : '';
    return `${nome} ${kg(carga_max)} kg${delta}`;
};

const horario = (iso) => {
    const d = new Date(iso);
    const hoje = new Date().toDateString() === d.toDateString();
    const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    return hoje ? hora : `${d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${hora}`;
};

export const AtividadeRecente = ({ onSelectAluno }) => {
    const [itens, setItens] = useState(null);

    useEffect(() => {
        // Só busca com a aba visível; ao voltar para a aba, atualiza na hora
        const carregar = () => {
            if (document.visibilityState !== 'visible') return;
            atividadeService.recente().then(setItens).catch(() => {});
        };
        carregar();
        const id = setInterval(carregar, POLLING_MS);
        document.addEventListener('visibilitychange', carregar);
        return () => {
            clearInterval(id);
            document.removeEventListener('visibilitychange', carregar);
        };
    }, []);

    if (!itens?.length) return null;

    return (
        <section aria-labelledby="atividade-titulo" className="bg-surface border border-border rounded-3xl p-5 sm:p-6 space-y-3">
            <h3 id="atividade-titulo" className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-text-muted">
                <Activity size={16} className="text-brand" /> Atividade recente
            </h3>
            <ul className="divide-y divide-border-faint">
                {itens.map(item => (
                    <li key={item.sessao_id}>
                        <button
                            type="button"
                            onClick={() => onSelectAluno(item.aluno_id)}
                            className="w-full text-left py-3 px-2 rounded-xl hover:bg-overlay transition-colors"
                        >
                            <span className="font-bold text-text-primary">{item.aluno_nome}</span>
                            <span className="text-text-muted"> · {item.treino_nome ?? 'Treino'} · {horario(item.data_hora)}</span>
                            <span className="block text-xs text-text-secondary mt-0.5">
                                {item.exercicios.slice(0, MAX_EXERCICIOS).map(textoExercicio).join(' · ')}
                                {item.exercicios.length > MAX_EXERCICIOS && ` · +${item.exercicios.length - MAX_EXERCICIOS}`}
                            </span>
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
};
