import assert from 'node:assert/strict';
import { test } from 'node:test';
import { validarPlano } from './validarPlano.js';

const plano = {
    titulo: 'Força', duracao_semanas: 4,
    treinos: [{ nome: 'Treino A', vezes_por_semana: 2, prescricoes: [
        { exercicio_id: 1, nome_exercicio: 'Supino', series: 3, repeticoes: '8–12', descanso: 0 },
    ] }],
};

test('aceita faixa de repetições e descanso zero', () => {
    assert.equal(validarPlano(plano), null);
});

test('identifica a etapa, o treino e o exercício com dados inválidos', () => {
    const invalido = structuredClone(plano);
    invalido.titulo = ' ';
    assert.equal(validarPlano(invalido).campo, 'titulo');
    invalido.titulo = 'Força';
    invalido.treinos[0].vezes_por_semana = 8;
    assert.equal(validarPlano(invalido).campo, 'frequencia');
    invalido.treinos[0].vezes_por_semana = 2;
    invalido.treinos[0].prescricoes[0].series = -1;
    assert.equal(validarPlano(invalido).treinoIndex, 0);
    assert.match(validarPlano(invalido).mensagem, /Supino/);
});
