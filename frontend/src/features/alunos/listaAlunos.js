const normalizar = (texto) => texto.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
const compararNomes = new Intl.Collator('pt-BR', { sensitivity: 'base' }).compare;

export function filtrarAlunos(alunos, categoria, busca, ordem = 'asc') {
    const termo = normalizar(busca.trim());
    return alunos.filter(({ nome, status }) => {
        const pertence = categoria === 'ativos'
            ? status === 'ativo'
            : status === 'suspenso' || status === 'cancelado';
        return pertence && normalizar(nome).includes(termo);
    }).sort((a, b) => ordem === 'asc' ? compararNomes(a.nome, b.nome) : compararNomes(b.nome, a.nome));
}
