import assert from 'node:assert/strict';
import { test } from 'node:test';
import { filtrarAlunos } from './listaAlunos.js';

const alunos = [
    { id: 1, nome: 'Érica Souza', status: 'ativo' },
    { id: 2, nome: 'Ana Érica', status: 'suspenso' },
    { id: 3, nome: 'Álvaro Lima', status: 'ativo' },
];

test('busca ignora caixa e acento e respeita o status', () => {
    assert.deepEqual(filtrarAlunos(alunos, 'ativos', ' ERICA ').map(a => a.id), [1]);
    assert.deepEqual(filtrarAlunos(alunos, 'inativos', 'erica').map(a => a.id), [2]);
    assert.deepEqual(filtrarAlunos(alunos, 'ativos', 'joão'), []);
});

test('busca vazia mostra a categoria toda em ordem alfabética', () => {
    assert.deepEqual(filtrarAlunos(alunos, 'ativos', '').map(a => a.id), [3, 1]);
    assert.deepEqual(filtrarAlunos(alunos, 'ativos', '', 'desc').map(a => a.id), [1, 3]);
});
