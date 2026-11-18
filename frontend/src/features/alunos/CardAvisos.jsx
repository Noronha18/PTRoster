import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { avisoService } from '../../services/api';

const textoDias = (dias, futuro, passado) => {
    if (dias < 0) return `${passado} há ${-dias} dia${dias === -1 ? '' : 's'}`;
    if (dias === 0) return `${futuro} hoje`;
    return `${futuro} em ${dias} dia${dias === 1 ? '' : 's'}`;
};

export const CardAvisos = ({ onSelectAluno }) => {
    const [avisos, setAvisos] = useState(null);

    useEffect(() => {
        avisoService.listar().then(setAvisos).catch(() => setAvisos(null));
    }, []);

    if (!avisos || (avisos.consultorias.length === 0 && avisos.programas.length === 0)) return null;

    const itens = [
        ...avisos.consultorias.map(a => ({
            chave: `c-${a.aluno_id}`, aluno_id: a.aluno_id, nome: a.aluno_nome, dias: a.dias_restantes,
            texto: textoDias(a.dias_restantes, 'Consultoria vence', 'Consultoria venceu'),
        })),
        ...avisos.programas.map(p => ({
            chave: `p-${p.plano_id}`, aluno_id: p.aluno_id, nome: p.aluno_nome, dias: p.dias_restantes,
            texto: `${p.plano_titulo}: ${textoDias(p.dias_restantes, 'termina', 'terminou')}`,
        })),
    ];

    return (
        <section aria-labelledby="avisos-titulo" className="bg-warning-subtle border border-warning/30 rounded-xl p-4 space-y-2">
            <h3 id="avisos-titulo" className="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-warning-text">
                <AlertTriangle size={16} /> Atenção
            </h3>
            <ul className="divide-y divide-warning/20">
                {itens.map(item => (
                    <li key={item.chave}>
                        <button
                            type="button"
                            onClick={() => onSelectAluno(item.aluno_id)}
                            className="w-full flex justify-between items-center gap-3 py-2 text-left hover:bg-warning/10 rounded-xl px-2 transition-colors"
                        >
                            <span className="font-bold text-text-primary">{item.nome}</span>
                            <span className={`text-xs font-semibold ${item.dias < 0 ? 'text-danger' : 'text-warning-text'}`}>{item.texto}</span>
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
};
