const BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? '' : 'http://127.0.0.1:8000');

/**
 * Utilitário base para chamadas API
 */
async function apiFetch(endpoint, options = {}) {
    const token = localStorage.getItem('token');
    
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}${endpoint}`, {
        ...options,
        headers,
    });

    if (response.status === 401) {
        localStorage.removeItem('token');
        // App.jsx ouve este evento e volta para a tela de login
        window.dispatchEvent(new Event('auth:expired'));
        throw new Error('Sessão expirada. Por favor, faça login novamente.');
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || 'Erro na comunicação com o servidor');
    }

    if (response.status === 204) return null;
    
    return response.json();
}

export const alunoService = {
    listar: () => apiFetch('/alunos/'),
    obterPorId: (id) => apiFetch(`/alunos/${id}`),
    ultimaExecucao: (id, treinoId) => apiFetch(`/alunos/${id}/ultima-execucao?treino_id=${treinoId}`),
    evolucao: (id, exercicioId) =>
        apiFetch(`/alunos/${id}/evolucao${exercicioId ? `?exercicio_id=${exercicioId}` : ''}`),
    semana: (id, ref) =>
        apiFetch(`/alunos/${id}/semana${ref ? `?ref=${ref}` : ''}`),
    criar: (dados) => apiFetch('/alunos/', {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
    atualizar: (id, dados) => apiFetch(`/alunos/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(dados),
    }),
    atualizarStatus: (id, status) => apiFetch(`/alunos/${id}/status?status=${status}`, {
        method: 'PATCH',
    }),
    registrarPresenca: (alunoId) => apiFetch('/sessoes/', {
        method: 'POST',
        body: JSON.stringify({
            aluno_id: alunoId,
            realizada: true
        }),
    }),
    deletar: (id) => apiFetch(`/alunos/${id}`, {
        method: 'DELETE',
    }),
};

export const treinoService = {
    listarExercicios: () => apiFetch('/exercicios/'),
    criarExercicio: (dados) => apiFetch('/exercicios/', {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
    // video_url nulo/vazio = voltar ao original (troca do personal na base) ou remover.
    definirVideoExercicio: (id, videoUrl) => apiFetch(`/exercicios/${id}/video`, {
        method: 'PUT',
        body: JSON.stringify({ video_url: videoUrl || null }),
    }),
    
    // Gestão de Planos
    criarPlano: (alunoId, dados) => apiFetch(`/alunos/${alunoId}/planos`, {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
    atualizarPlano: (planoId, dados) => apiFetch(`/planos/${planoId}`, {
        method: 'PATCH',
        body: JSON.stringify(dados),
    }),
    deletarPlano: (id) => apiFetch(`/planos/${id}`, {
        method: 'DELETE',
    }),
    clonarPlano: (planoId, alunoId = null) => {
        const url = alunoId ? `/planos/${planoId}/clonar?aluno_id=${alunoId}` : `/planos/${planoId}/clonar`;
        return apiFetch(url, { method: 'POST' });
    },

    // Templates Globais
    listarTemplates: () => apiFetch('/planos/templates'),
    criarTemplate: (dados) => apiFetch('/planos/templates', {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
};

export const financeiroService = {
    obterEstatisticas: () => apiFetch('/pagamentos/estatisticas'),
};

export const avisoService = {
    listar: () => apiFetch('/avisos/'),
};

export const atividadeService = {
    recente: () => apiFetch('/atividade-recente'),
};

export const pagamentoService = {
    listar: () => apiFetch('/pagamentos/'),
    registrar: (dados) => apiFetch('/pagamentos/', {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
    atualizar: (id, dados) => apiFetch(`/pagamentos/${id}`, {
        method: 'PUT',
        body: JSON.stringify(dados),
    }),
    deletar: (id) => apiFetch(`/pagamentos/${id}`, {
        method: 'DELETE',
    }),
};

export const sessaoService = {
    listar: (params) => {
        const query = new URLSearchParams(params).toString();
        return apiFetch(`/sessoes/?${query}`);
    },
    frequencia: (alunoId, referenciaMes) =>
        apiFetch(`/sessoes/frequencia/${alunoId}?referencia_mes=${encodeURIComponent(referenciaMes)}`),
    registrar: (dados) => apiFetch('/sessoes/', {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
    registrarExecucao: (dados) => apiFetch('/sessoes/execucao', {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
    deletar: (id) => apiFetch(`/sessoes/${id}`, {
        method: 'DELETE',
    }),
};

export const authService = {
    login: async (username, password) => {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${BASE_URL}/auth/token`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const erro = await response.json().catch(() => ({}));
            throw new Error(erro.message || 'Usuário ou senha inválidos');
        }

        const data = await response.json();
        localStorage.setItem('token', data.access_token);
        return data;
    },
    logout: () => {
        localStorage.removeItem('token');
    }
};

export function getUserRole() {
    const token = localStorage.getItem('token');
    if (!token) return null;
    try {
        const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
        return payload.role ?? null;
    } catch {
        return null;
    }
}

export const financeiroPersonalService = {
    resumo: () => apiFetch('/admin/financeiro/personais'),
    obterPlano: (personalId) => apiFetch(`/admin/financeiro/personais/${personalId}/plano`),
    salvarPlano: (personalId, dados) => apiFetch(`/admin/financeiro/personais/${personalId}/plano`, {
        method: 'PUT',
        body: JSON.stringify(dados),
    }),
    listarPagamentos: (personalId, limite = 24) =>
        apiFetch(`/admin/financeiro/personais/${personalId}/pagamentos?limite=${limite}`),
    registrarPagamento: (personalId, dados) => apiFetch(`/admin/financeiro/personais/${personalId}/pagamentos`, {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
};

export const operacoesService = {
    listarPersonais: () => apiFetch('/admin/operacoes/personais'),
    alunosDoPersonal: (personalId) => apiFetch(`/admin/operacoes/personais/${personalId}/alunos`),
    sessoesDoAluno: (alunoId, limite = 20) =>
        apiFetch(`/admin/operacoes/alunos/${alunoId}/sessoes?limite=${limite}`),
    definirAtivo: (usuarioId, ativo) => apiFetch(`/admin/usuarios/${usuarioId}/ativo`, {
        method: 'PATCH',
        body: JSON.stringify({ ativo }),
    }),
};

export const adminService = {
    listarUsuarios: () => apiFetch('/admin/usuarios'),
    listarTrainers: async () => {
        const usuarios = await apiFetch('/admin/usuarios');
        return usuarios.filter((u) => u.role === 'trainer');
    },
    criarTrainer: (dados) => apiFetch('/admin/trainers', {
        method: 'POST',
        body: JSON.stringify(dados),
    }),
    verificarSenha: (usuarioId, senha) => apiFetch(`/admin/usuarios/${usuarioId}/verificar-senha`, {
        method: 'POST',
        body: JSON.stringify({ senha }),
    }),
    resetarSenha: (usuarioId, novaSenha) => apiFetch(`/admin/usuarios/${usuarioId}/senha`, {
        method: 'PATCH',
        body: JSON.stringify({ nova_senha: novaSenha }),
    }),
};
