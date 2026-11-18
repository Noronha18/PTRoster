const inteiro = (valor, min, max = 2**31 - 1) =>
    String(valor ?? '').trim() !== '' && Number.isInteger(Number(valor))
    && Number(valor) >= min && Number(valor) <= max;

export function validarPlano(plano, somenteInformacoes = false) {
    if (!plano.titulo.trim()) return { campo: 'titulo', mensagem: 'Informe o título do plano.' };
    if (!inteiro(plano.duracao_semanas, 1)) {
        return { campo: 'duracao', mensagem: 'Informe uma duração em semanas maior que zero.' };
    }
    if (somenteInformacoes) return null;
    if (!plano.treinos.some(treino => treino.prescricoes.length)) {
        return { treinoIndex: 0, mensagem: 'Adicione pelo menos um exercício ao plano.' };
    }
    for (const [treinoIndex, treino] of plano.treinos.entries()) {
        if (!treino.nome.trim()) return { treinoIndex, campo: 'nome', mensagem: 'Informe o nome do treino.' };
        if (!inteiro(treino.vezes_por_semana ?? 1, 1, 7)) {
            return { treinoIndex, campo: 'frequencia', mensagem: 'Informe de 1 a 7 sessões por semana.' };
        }
        for (const prescricao of treino.prescricoes) {
            const nome = prescricao.nome_exercicio || 'Exercício';
            if (!inteiro(prescricao.series, 1)) return { treinoIndex, mensagem: `${nome}: informe uma quantidade inteira de séries maior que zero.` };
            if (!prescricao.repeticoes?.trim()) return { treinoIndex, mensagem: `${nome}: informe as repetições.` };
            if (!inteiro(prescricao.descanso, 0)) return { treinoIndex, mensagem: `${nome}: informe o descanso em segundos, de zero em diante.` };
        }
    }
    return null;
}
