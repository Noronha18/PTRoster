import assert from 'node:assert/strict';
import { test } from 'node:test';
import { lerRota } from './rotas.js';

test('aceita links diretos do painel e da ficha', () => {
    assert.deepEqual(lerRota('#/aluno/42', 'trainer'), { aba: 'alunos', alunoId: 42 });
    assert.deepEqual(lerRota('#/treinos', 'trainer'), { aba: 'treinos', alunoId: null });
    assert.deepEqual(lerRota('#/financeiro', 'trainer'), { aba: 'financeiro', alunoId: null });
});

test('restringe Operações a admin e trata rotas inválidas', () => {
    assert.equal(lerRota('#/admin', 'admin').aba, 'admin');
    for (const rota of ['#/admin', '#/aluno/-2', '#/aluno/2147483648', '#/aluno/1/extra', '#/xyz']) {
        assert.deepEqual(lerRota(rota, 'trainer'), { aba: 'alunos', alunoId: null });
    }
});
