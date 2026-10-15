// Grade de séries: valores iniciais e conversão para o POST /sessoes/execucao.
// Cópia idêntica em ptroster-alunos/src/utils/series.js: mudou aqui, mude lá.

export const chaveSerie = (prescricaoId, n) => `p${prescricaoId}_s${n}`;

const numero = (valor, parse) => {
    const n = parse(String(valor ?? '').replace(',', '.'));
    return Number.isNaN(n) ? null : n;
};

// "12-15" → 12, "60kg" → 60, "até a falha" → ''
const inicialPrescrito = (valor, parse) => {
    const n = numero(valor, parse);
    return n === null ? '' : String(n);
};

// Sem histórico do exercício, parte do prescrito; com histórico, repete a última execução.
export function valoresIniciais(prescricoes, ultimas) {
    const porExercicio = Object.fromEntries((ultimas ?? []).map(u => [u.exercicio_id, u.series]));
    const valores = {};
    for (const p of prescricoes ?? []) {
        const anteriores = porExercicio[p.exercicio_id] ?? [];
        for (let n = 1; n <= (p.series || 0); n++) {
            const anterior = anteriores.find(s => s.numero_serie === n) ?? anteriores[anteriores.length - 1];
            valores[chaveSerie(p.id, n)] = anterior
                ? { reps: String(anterior.repeticoes), kg: anterior.carga_kg == null ? '' : String(anterior.carga_kg) }
                : { reps: inicialPrescrito(p.repeticoes, parseInt), kg: inicialPrescrito(p.carga_kg ?? p.carga, parseFloat) };
        }
    }
    return valores;
}

// Séries sem reps válidas ficam de fora; kg vazio vira peso corporal (null).
export function seriesParaEnvio(prescricoes, valores, incluir = () => true) {
    const series = [];
    for (const p of prescricoes ?? []) {
        for (let n = 1; n <= (p.series || 0); n++) {
            const chave = chaveSerie(p.id, n);
            const reps = numero(valores[chave]?.reps, parseInt);
            if (!incluir(chave) || reps === null) continue;
            series.push({
                exercicio_id: p.exercicio_id,
                prescricao_id: p.id,
                numero_serie: n,
                repeticoes: reps,
                carga_kg: numero(valores[chave]?.kg, parseFloat),
            });
        }
    }
    return series;
}
