const rotaAlunos = { aba: 'alunos', alunoId: null };

export function lerRota(hash, papel) {
    const ficha = /^#\/aluno\/([1-9]\d*)$/.exec(hash);
    if (ficha) {
        const alunoId = Number(ficha[1]);
        return alunoId <= 2**31 - 1 ? { aba: 'alunos', alunoId } : rotaAlunos;
    }
    const aba = hash.slice(2);
    if (hash.startsWith('#/') && (aba === 'treinos' || aba === 'financeiro' || (aba === 'admin' && papel === 'admin'))) {
        return { aba, alunoId: null };
    }
    return rotaAlunos;
}
