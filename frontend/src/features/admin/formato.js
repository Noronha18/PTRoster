const SETE_DIAS_MS = 7 * 24 * 60 * 60 * 1000;

export const MENSALIDADE = {
    sem_plano: { rotulo: 'Sem plano', classe: 'bg-overlay text-text-muted border-border' },
    em_dia: { rotulo: 'Em dia', classe: 'bg-success/10 text-success border-success/20' },
    vence_em_breve: { rotulo: 'Vence em breve', classe: 'bg-warning/10 text-warning border-warning/20' },
    atrasada: { rotulo: 'Atrasada', classe: 'bg-danger/10 text-danger border-danger/20' },
};

export function formatarQuando(valor) {
    if (!valor) return 'Nunca';
    const data = new Date(valor);
    if (Number.isNaN(data.getTime())) return '—';
    return data.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

export function formatarData(valor) {
    if (!valor) return 'Nunca';
    const data = new Date(valor);
    if (Number.isNaN(data.getTime())) return '—';
    return data.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

export function ultimaAtividade(linha) {
    const instantes = [linha.ultimo_acesso, linha.ultimo_treino]
        .filter(Boolean)
        .map((valor) => new Date(valor).getTime())
        .filter((valor) => !Number.isNaN(valor));
    return instantes.length ? new Date(Math.max(...instantes)) : null;
}

export function semAtividade(linha, agora = Date.now()) {
    const ultima = ultimaAtividade(linha);
    return !ultima || agora - ultima.getTime() > SETE_DIAS_MS;
}

export function alertasPersonal(personal) {
    const alertas = [];
    if (personal.is_active && semAtividade(personal)) {
        alertas.push({ id: 'sem-atividade', texto: 'Sem atividade 7d', tom: 'muted' });
    }
    if (personal.is_active && personal.alunos_ativos === 0) {
        alertas.push({ id: 'sem-alunos', texto: 'Sem alunos', tom: 'warn' });
    }
    if (personal.situacao_mensalidade === 'atrasada') {
        alertas.push({ id: 'mensalidade-atrasada', texto: 'Mensalidade atrasada', tom: 'danger' });
    }
    return alertas;
}
