import React, { useState, useEffect, useRef } from 'react';
import { X, Dumbbell, Trash2, Plus, Save, Book, ChevronRight, ChevronLeft, ChevronUp, ChevronDown, CheckCircle2 } from 'lucide-react';
import { treinoService } from '../../services/api';
import { BibliotecaExercicios } from '../treinos/BibliotecaExercicios';
import { useToast } from '../../components/ToastProvider';
import { GRUPOS_MUSCULARES, DIAS_SEMANA } from '../../constants/treino';

const METODOS_TREINO = [
  "Convencional", "Drop-set", "Rest-pause", "Bi-set", "Tri-set",
  "Giant-set", "Super-set", "Piramidal Crescente", "Piramidal Decrescente",
  "Cluster-set", "GVT", "FST-7", "SST", "MTUT", "Isometria",
  "Excêntrico", "Pré-Exaustão", "Pós-Exaustão", "AMRAP", "Myo-reps", "21s"
];

const METODOS_AGRUPADORES = ["Bi-set", "Tri-set", "Giant-set", "Super-set"];

const METHOD_BG = {
  'Bi-set':    'bg-method-bi/8',
  'Tri-set':   'bg-method-tri/8',
  'Giant-set': 'bg-method-giant/8',
  'Super-set': 'bg-method-super/8',
};

export function ModalPlanoTreino({ isOpen, onClose, onSave, planoEdicao = null }) {
  const toast = useToast();
  const [step, setStep] = useState(1);
  const [activeTreinoIndex, setActiveTreinoIndex] = useState(0);
  const [mobileLibOpen, setMobileLibOpen] = useState(false);
  const [lastAddedIdx, setLastAddedIdx] = useState(null);
  const editorScrollRef = useRef(null);

  const [novoPlano, setNovoPlano] = useState({
    titulo: '',
    objetivo_estrategico: '',
    detalhes: '',
    duracao_semanas: 4,
    treinos: [{ nome: 'Treino A', vezes_por_semana: 1, dias_sugeridos: [], prescricoes: [] }]
  });

  const [templates, setTemplates] = useState([]);
  const [showTemplates, setShowTemplates] = useState(false);

  const carregarTemplates = async () => {
    try {
      const tmpls = await treinoService.listarTemplates();
      setTemplates(tmpls);
    } catch (err) {
      console.error("Erro ao carregar templates:", err);
    }
  };

  useEffect(() => {
    if (isOpen) {
      carregarTemplates();
      if (planoEdicao) {
        setNovoPlano({ ...planoEdicao, detalhes: planoEdicao.detalhes || '' });
        setStep(2);
      } else {
        setNovoPlano({
          titulo: '', objetivo_estrategico: '', detalhes: '',
          duracao_semanas: 4,
          treinos: [{ nome: 'Treino A', vezes_por_semana: 1, dias_sugeridos: [], prescricoes: [] }]
        });
        setStep(1);
        setActiveTreinoIndex(0);
      }
      setMobileLibOpen(false);
    }
  }, [isOpen, planoEdicao]);

  if (!isOpen) return null;

  const handleAddTreino = () => {
    const letras = 'BCDEFGHIJKLMNOPQRSTUVWXYZ';
    const letra = letras[novoPlano.treinos.length - 1] || 'Extra';
    const novosTreinos = [
      ...novoPlano.treinos,
      { nome: `Treino ${letra}`, vezes_por_semana: 1, dias_sugeridos: [], prescricoes: [] },
    ];
    setNovoPlano({ ...novoPlano, treinos: novosTreinos });
    setActiveTreinoIndex(novosTreinos.length - 1);
  };

  const handleRemoveTreino = (tIndex) => {
    if (novoPlano.treinos.length > 1) {
      const updated = novoPlano.treinos.filter((_, i) => i !== tIndex);
      setNovoPlano({ ...novoPlano, treinos: updated });
      setActiveTreinoIndex(Math.max(0, tIndex - 1));
    }
  };

  const handleAddFromLibrary = (ex) => {
    const updated = [...novoPlano.treinos];
    updated[activeTreinoIndex].prescricoes.push({
      exercicio_id: ex.id,
      nome_exercicio: ex.nome,
      grupo_muscular: ex.grupo_muscular,
      series: 3, repeticoes: '12', carga: '',
      descanso: 60, metodo: 'Convencional', observacoes: ''
    });
    setNovoPlano({ ...novoPlano, treinos: updated });

    const newIdx = updated[activeTreinoIndex].prescricoes.length - 1;
    setLastAddedIdx(newIdx);
    setTimeout(() => setLastAddedIdx(null), 700);
  };

  const handleRemoveExercicio = (tIndex, exIndex) => {
    const updated = [...novoPlano.treinos];
    updated[tIndex].prescricoes = updated[tIndex].prescricoes.filter((_, i) => i !== exIndex);
    setNovoPlano({ ...novoPlano, treinos: updated });
  };

  const handleTreinoChange = (tIndex, campo, valor) => {
    const updated = [...novoPlano.treinos];
    updated[tIndex][campo] = valor;
    setNovoPlano({ ...novoPlano, treinos: updated });
  };

  const handleExercicioChange = (tIndex, exIndex, campo, valor) => {
    const updated = [...novoPlano.treinos];
    updated[tIndex].prescricoes[exIndex][campo] = valor;
    setNovoPlano({ ...novoPlano, treinos: updated });
  };

  const toggleDia = (dia) => {
    const atuais = novoPlano.treinos[activeTreinoIndex].dias_sugeridos || [];
    const novos = atuais.includes(dia)
      ? atuais.filter((d) => d !== dia)
      : [...atuais, dia].sort((a, b) => a - b);
    handleTreinoChange(activeTreinoIndex, 'dias_sugeridos', novos);
  };

  const moveTreino = (idx, dir) => {
    const alvo = idx + dir;
    if (alvo < 0 || alvo >= novoPlano.treinos.length) return;
    const updated = [...novoPlano.treinos];
    [updated[idx], updated[alvo]] = [updated[alvo], updated[idx]];
    setNovoPlano({ ...novoPlano, treinos: updated });
    setActiveTreinoIndex(alvo);
  };

  const moveExercicio = (tIndex, exIndex, dir) => {
    const alvo = exIndex + dir;
    const updated = [...novoPlano.treinos];
    const lista = [...updated[tIndex].prescricoes];
    if (alvo < 0 || alvo >= lista.length) return;
    [lista[exIndex], lista[alvo]] = [lista[alvo], lista[exIndex]];
    updated[tIndex] = { ...updated[tIndex], prescricoes: lista };
    setNovoPlano({ ...novoPlano, treinos: updated });
  };

  const handleImportTemplate = (template) => {
    setNovoPlano({
      ...novoPlano,
      titulo: template.titulo,
      objetivo_estrategico: template.objetivo_estrategico,
      detalhes: template.detalhes || '',
      duracao_semanas: template.duracao_semanas,
      treinos: template.treinos.map(t => ({
        nome: t.nome,
        vezes_por_semana: t.vezes_por_semana ?? 1,
        dias_sugeridos: t.dias_sugeridos ?? [],
        prescricoes: t.prescricoes.map(p => ({
          exercicio_id: p.exercicio_id,
          nome_exercicio: p.nome_exercicio || (p.exercicio ? p.exercicio.nome : 'Exercício'),
          grupo_muscular: p.exercicio?.grupo_muscular || 'Outros',
          series: p.series, repeticoes: p.repeticoes,
          carga: p.carga_kg, descanso: p.tempo_descanso_segundos,
          metodo: p.metodo || 'Convencional', observacoes: p.observacoes || ''
        }))
      }))
    });
    setShowTemplates(false);
    setStep(2);
  };

  const handleFormSubmit = () => {
    const payload = {
      ...novoPlano,
      treinos: novoPlano.treinos.map(t => ({
        ...t,
        prescricoes: t.prescricoes.map(p => ({
          id: p.id || null,
          exercicio_id: parseInt(p.exercicio_id),
          series: parseInt(p.series) || 1,
          repeticoes: p.repeticoes,
          carga: p.carga || null,
          descanso: parseInt(p.descanso) || 0,
          metodo: p.metodo,
          observacoes: p.observacoes || null
        }))
      }))
    };
    onSave(payload);
  };

  const prescricoes = novoPlano.treinos[activeTreinoIndex]?.prescricoes ?? [];
  const treinoAtivo = novoPlano.treinos[activeTreinoIndex];

  const volumePorGrupo = {};
  novoPlano.treinos.forEach((t) => {
    const vezes = Number(t.vezes_por_semana) || 0;
    (t.prescricoes || []).forEach((p) => {
      const grupo = p.grupo_muscular || 'Outros';
      volumePorGrupo[grupo] = (volumePorGrupo[grupo] || 0) + (Number(p.series) || 0) * vezes;
    });
  });
  const volumePlanejado = GRUPOS_MUSCULARES
    .filter((grupo) => (volumePorGrupo[grupo] || 0) > 0)
    .map((grupo) => [grupo, volumePorGrupo[grupo]]);
  const totalVolume = volumePlanejado.reduce((soma, [, series]) => soma + series, 0);

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-0 md:p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">

      <div className="bg-canvas w-full max-w-7xl h-[95dvh] md:h-[90vh] overflow-hidden rounded-t-[2.5rem] md:rounded-[3rem] shadow-2xl flex flex-col animate-in slide-in-from-bottom duration-500" style={{ transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)' }}>

        {/* Header */}
        <div className="px-5 py-4 md:p-8 border-b border-border flex justify-between items-center bg-surface z-10 flex-shrink-0">
          <div className="flex items-center gap-3 md:gap-4">
            <div className="w-10 h-10 md:w-12 md:h-12 bg-brand text-brand-fg rounded-xl md:rounded-2xl flex items-center justify-center shadow-lg shadow-brand/20 flex-shrink-0">
              <Dumbbell size={20} />
            </div>
            <div>
              <h2 className="text-xl md:text-3xl font-black text-text-primary tracking-tight leading-none">
                {planoEdicao ? 'Editar Plano' : 'Prescrever Plano'}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs font-black uppercase tracking-widest px-2 py-0.5 rounded-full ${step === 1 ? 'bg-brand text-brand-fg' : 'bg-overlay text-text-muted'}`}>1. Info</span>
                <div className="w-4 h-px bg-border" />
                <span className={`text-xs font-black uppercase tracking-widest px-2 py-0.5 rounded-full ${step === 2 ? 'bg-brand text-brand-fg' : 'bg-overlay text-text-muted'}`}>2. Treinos</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 md:gap-3">
            {step === 1 && !planoEdicao && (
              <button
                onClick={() => setShowTemplates(!showTemplates)}
                className="flex items-center gap-1.5 px-3 py-2 md:px-4 bg-blue-50 text-blue-600 rounded-xl text-xs font-black uppercase tracking-widest hover:bg-blue-100 transition-all"
              >
                <Book size={14} /> <span className="hidden sm:inline">Templates</span>
              </button>
            )}
            <button onClick={onClose} className="p-2.5 md:p-3 bg-overlay text-text-muted hover:text-text-secondary rounded-full transition-all active:scale-90">
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Templates Dropdown */}
        {showTemplates && step === 1 && (
          <div className="absolute top-24 right-4 md:top-28 md:right-8 w-72 md:w-80 bg-surface border border-border shadow-2xl rounded-3xl z-50 p-4 animate-in zoom-in-95 duration-200">
            <h4 className="text-xs font-black text-text-muted uppercase tracking-widest mb-4 px-2">Modelos Disponíveis</h4>
            <div className="space-y-2 max-h-60 overflow-y-auto custom-scrollbar">
              {templates.map(t => (
                <button key={t.id} onClick={() => handleImportTemplate(t)}
                  className="w-full text-left p-3 hover:bg-overlay rounded-2xl border border-transparent hover:border-border transition-all group"
                >
                  <p className="font-bold text-text-primary text-sm group-hover:text-brand">{t.titulo}</p>
                  <p className="text-xs text-text-muted font-medium">{t.treinos?.length} treinos · {t.duracao_semanas} semanas</p>
                </button>
              ))}
              {templates.length === 0 && <p className="text-xs text-text-muted p-4 text-center italic">Nenhum modelo global criado.</p>}
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">

          {step === 1 ? (
            /* PASSO 1: INFO */
            <div className="flex-1 overflow-y-auto px-5 py-8 md:p-10 flex flex-col items-center justify-center bg-surface">
              <div className="w-full max-w-2xl space-y-8 md:space-y-12 animate-in fade-in zoom-in-95 duration-500">
                <div className="text-center space-y-2">
                  <h3 className="text-2xl md:text-4xl font-black text-text-primary tracking-tight">Sobre o que é este plano?</h3>
                  <p className="text-text-secondary font-medium text-sm md:text-base">Defina o título, objetivo estratégico e o tempo de ciclo.</p>
                </div>

                <div className="space-y-5 md:space-y-6">
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Título do Plano *</label>
                    <input
                      type="text" placeholder="Ex: Protocolo de Verão - Cutting"
                      className="w-full bg-overlay border border-border rounded-2xl md:rounded-3xl px-5 md:px-8 py-4 md:py-6 text-lg md:text-xl text-text-primary font-black focus:ring-4 focus:ring-brand/10 outline-none transition-all placeholder:text-text-muted"
                      value={novoPlano.titulo}
                      onChange={e => setNovoPlano({ ...novoPlano, titulo: e.target.value })}
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Objetivo Estratégico</label>
                      <input
                        type="text" placeholder="Ex: Perda de Gordura"
                        className="w-full bg-overlay border border-border rounded-2xl md:rounded-3xl px-5 md:px-6 py-4 md:py-5 text-text-primary font-bold focus:ring-4 focus:ring-brand/10 outline-none transition-all"
                        value={novoPlano.objetivo_estrategico}
                        onChange={e => setNovoPlano({ ...novoPlano, objetivo_estrategico: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Duração (Semanas)</label>
                      <input
                        type="number"
                        className="w-full bg-overlay border border-border rounded-2xl md:rounded-3xl px-5 md:px-6 py-4 md:py-5 text-text-primary font-bold focus:ring-4 focus:ring-brand/10 outline-none transition-all"
                        value={novoPlano.duracao_semanas}
                        onChange={e => setNovoPlano({ ...novoPlano, duracao_semanas: parseInt(e.target.value) || 0 })}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-text-secondary uppercase tracking-wide ml-1">Observações Gerais (Opcional)</label>
                    <textarea
                      placeholder="Descreva detalhes importantes sobre o plano, restrições ou dicas de execução geral."
                      className="w-full bg-overlay border border-border rounded-2xl md:rounded-3xl px-5 md:px-6 py-4 md:py-5 text-text-primary font-medium focus:ring-4 focus:ring-brand/10 outline-none transition-all min-h-[100px] md:min-h-[120px] resize-none"
                      value={novoPlano.detalhes}
                      onChange={e => setNovoPlano({ ...novoPlano, detalhes: e.target.value })}
                    />
                  </div>
                </div>

                <div className="pt-4 md:pt-8">
                  <button
                    disabled={!novoPlano.titulo}
                    onClick={() => setStep(2)}
                    className="w-full py-5 md:py-6 bg-brand hover:bg-brand-hover disabled:bg-overlay disabled:text-text-muted text-brand-fg rounded-2xl md:rounded-3xl font-black uppercase tracking-[0.2em] text-xs transition-all shadow-xl flex items-center justify-center gap-3 active:scale-95"
                  >
                    Continuar para Montagem <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            </div>

          ) : (
            /* PASSO 2: EDITOR */
            <div className="flex-1 overflow-hidden flex relative">

              {/* ── DESKTOP: coluna esquerda — biblioteca ─────────────────── */}
              <div className="hidden md:flex w-[380px] border-r border-border bg-surface overflow-hidden flex-col flex-shrink-0">
                <BibliotecaExercicios onSelectExercicio={handleAddFromLibrary} />
              </div>

              {/* ── EDITOR: coluna direita (desktop) / tela inteira (mobile) ─ */}
              <div className="flex-1 bg-canvas overflow-hidden flex flex-col min-w-0">

                {/* Tabs de treino */}
                <div className="bg-surface px-3 py-3 md:p-4 border-b border-border flex items-center gap-2 overflow-x-auto custom-scrollbar flex-shrink-0">
                  {novoPlano.treinos.map((treino, idx) => (
                    <button
                      key={idx}
                      onClick={() => setActiveTreinoIndex(idx)}
                      className={`px-4 md:px-6 py-2.5 md:py-3 rounded-xl md:rounded-2xl text-xs font-black uppercase tracking-widest transition-all whitespace-nowrap flex items-center gap-2 md:gap-3 flex-shrink-0
                        ${activeTreinoIndex === idx
                          ? 'bg-brand text-brand-fg shadow-md shadow-brand/20'
                          : 'bg-overlay text-text-muted'}`}
                    >
                      <span>{treino.nome || `Treino ${idx + 1}`}</span>
                      {activeTreinoIndex === idx && novoPlano.treinos.length > 1 && (
                        <span className="flex items-center gap-1.5">
                          <ChevronLeft size={13}
                            className={`transition-colors ${idx === 0 ? 'opacity-30 cursor-default' : 'hover:text-brand-fg/70 cursor-pointer'}`}
                            title="Mover para a esquerda"
                            onClick={(e) => { e.stopPropagation(); moveTreino(idx, -1); }} />
                          <ChevronRight size={13}
                            className={`transition-colors ${idx === novoPlano.treinos.length - 1 ? 'opacity-30 cursor-default' : 'hover:text-brand-fg/70 cursor-pointer'}`}
                            title="Mover para a direita"
                            onClick={(e) => { e.stopPropagation(); moveTreino(idx, 1); }} />
                          <X size={12} className="hover:text-danger transition-colors"
                            onClick={(e) => { e.stopPropagation(); handleRemoveTreino(idx); }} />
                        </span>
                      )}
                    </button>
                  ))}
                  <button
                    onClick={handleAddTreino}
                    className="w-9 h-9 flex-shrink-0 bg-overlay text-text-muted hover:bg-brand/5 hover:text-brand rounded-xl flex items-center justify-center transition-all border border-dashed border-border"
                  >
                    <Plus size={16} />
                  </button>
                </div>

                {/* Lista de exercícios */}
                <div ref={editorScrollRef} className="flex-1 overflow-y-auto p-4 md:p-8 space-y-3 md:space-y-8 custom-scrollbar pb-24 md:pb-8">

                  {/* Identificação do treino */}
                  <div className="flex items-center gap-3 md:gap-4 bg-surface px-4 py-3 md:p-6 rounded-2xl md:rounded-[2rem] border border-border shadow-sm">
                    <div className="w-10 h-10 md:w-12 md:h-12 bg-text-primary text-brand-fg rounded-xl md:rounded-2xl flex items-center justify-center font-black text-lg md:text-xl flex-shrink-0">
                      {activeTreinoIndex < 26 ? "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[activeTreinoIndex] : "#"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <label className="text-2xs font-black text-text-muted uppercase tracking-widest ml-1">Nome do Treino</label>
                      <input
                        type="text"
                        className="w-full bg-transparent text-xl md:text-2xl font-black text-text-primary outline-none placeholder:text-text-muted"
                        value={novoPlano.treinos[activeTreinoIndex].nome}
                        onChange={e => handleTreinoChange(activeTreinoIndex, 'nome', e.target.value)}
                        placeholder="Ex: A — Peito e Tríceps"
                      />
                    </div>
                  </div>

                  {/* Planejamento semanal do treino */}
                  <div className="bg-surface px-4 py-4 md:p-6 rounded-2xl md:rounded-[2rem] border border-border shadow-sm space-y-4">
                    <div className="flex flex-col lg:flex-row lg:items-center gap-4 lg:gap-8">
                      <div className="flex items-center gap-3">
                        <div>
                          <label className="text-2xs font-black text-text-muted uppercase tracking-widest ml-1 block">Vezes / semana</label>
                          <input
                            type="number"
                            min="1"
                            max="7"
                            value={treinoAtivo?.vezes_por_semana ?? 1}
                            onChange={(e) => handleTreinoChange(activeTreinoIndex, 'vezes_por_semana', e.target.value)}
                            className="w-24 bg-overlay border border-border rounded-xl py-2.5 px-3 text-center text-lg font-black text-text-primary outline-none focus:ring-2 focus:ring-brand/20"
                          />
                        </div>
                        <p className="text-xs text-text-muted font-medium max-w-[150px] leading-snug mt-4">
                          Quantas sessões deste treino na semana.
                        </p>
                      </div>

                      <div className="flex-1">
                        <label className="text-2xs font-black text-text-muted uppercase tracking-widest ml-1 block">Dias sugeridos</label>
                        <div className="flex flex-wrap gap-1.5 mt-1.5">
                          {DIAS_SEMANA.map((dia) => {
                            const ativo = (treinoAtivo?.dias_sugeridos || []).includes(dia.valor);
                            return (
                              <button
                                key={dia.valor}
                                type="button"
                                onClick={() => toggleDia(dia.valor)}
                                className={`px-3 py-2 rounded-xl text-xs font-black uppercase tracking-widest transition-all border ${
                                  ativo
                                    ? 'bg-brand text-brand-fg border-brand shadow-sm'
                                    : 'bg-overlay text-text-muted border-border hover:text-text-secondary'
                                }`}
                                title={dia.longo}
                              >
                                {dia.curto}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>

                    {volumePlanejado.length > 0 && (
                      <div className="border-t border-border pt-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-2xs font-black text-text-muted uppercase tracking-widest">Volume semanal planejado</p>
                          <p className="text-2xs font-black text-text-secondary uppercase tracking-widest tabular-nums">{totalVolume} séries</p>
                        </div>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {volumePlanejado.map(([grupo, series]) => (
                            <span key={grupo} className="px-2.5 py-1 bg-brand/8 text-brand rounded-lg text-2xs font-black uppercase tracking-widest">
                              {grupo} · {series}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Exercícios */}
                  <div className="space-y-2 md:space-y-4">
                    {prescricoes.length === 0 ? (
                      <div className="py-16 md:py-20 text-center space-y-4 text-text-muted border-2 border-dashed border-border rounded-3xl">
                        <Dumbbell size={40} className="mx-auto opacity-20" />
                        <p className="text-xs font-black uppercase tracking-widest leading-relaxed">
                          {/* Mobile: prompt diferente */}
                          <span className="md:hidden">Toque em "Adicionar" para escolher exercícios</span>
                          <span className="hidden md:inline">Selecione um exercício na biblioteca à esquerda</span>
                        </p>
                      </div>
                    ) : (
                      prescricoes.map((presc, exIdx) => {
                        const isGrouping = METODOS_AGRUPADORES.includes(presc.metodo);
                        const prevIsSame = exIdx > 0 && prescricoes[exIdx - 1].metodo === presc.metodo && isGrouping;
                        const nextIsSame = exIdx < prescricoes.length - 1 && prescricoes[exIdx + 1].metodo === presc.metodo && isGrouping;
                        const isJustAdded = lastAddedIdx === exIdx;

                        const groupClasses = `
                          ${prevIsSame ? 'mt-0 border-t-0 rounded-t-none' : 'rounded-t-2xl md:rounded-t-3xl'}
                          ${nextIsSame ? 'mb-0 rounded-b-none' : 'rounded-b-2xl md:rounded-b-3xl'}
                        `;

                        return (
                          <div
                            key={exIdx}
                            className={`border p-4 md:p-6 shadow-sm group animate-in slide-in-from-right-2 duration-200 transition-colors
                              ${groupClasses}
                              ${isGrouping ? (METHOD_BG[presc.metodo] || '') : ''}
                              ${isJustAdded ? 'bg-brand/8 border-brand/25' : 'bg-surface border-border'}`}
                            style={{ transitionDuration: isJustAdded ? '0ms' : '700ms' }}
                          >
                            {/* ── Layout mobile: vertical ── */}
                            <div className="flex items-start gap-3 md:hidden">
                              <span className="mt-0.5 w-6 h-6 rounded-md bg-overlay flex items-center justify-center text-2xs font-black text-text-muted flex-shrink-0">
                                {exIdx + 1}
                              </span>
                              <div className="flex-1 min-w-0">
                                <p className="text-base font-black text-text-primary leading-tight">{presc.nome_exercicio}</p>
                                <input
                                  type="text"
                                  placeholder="Nota (ex: Até a falha)"
                                  className="w-full bg-transparent text-xs text-text-muted font-medium mt-1 outline-none border-b border-transparent focus:border-brand/20"
                                  value={presc.observacoes || ''}
                                  onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, 'observacoes', e.target.value)}
                                />
                              </div>
                              <div className="flex flex-col gap-0.5 flex-shrink-0">
                                <button
                                  onClick={() => moveExercicio(activeTreinoIndex, exIdx, -1)}
                                  disabled={exIdx === 0}
                                  className="p-1 text-text-muted active:text-brand disabled:opacity-30 transition-colors"
                                  aria-label="Mover exercício para cima"
                                >
                                  <ChevronUp size={14} />
                                </button>
                                <button
                                  onClick={() => moveExercicio(activeTreinoIndex, exIdx, 1)}
                                  disabled={exIdx === prescricoes.length - 1}
                                  className="p-1 text-text-muted active:text-brand disabled:opacity-30 transition-colors"
                                  aria-label="Mover exercício para baixo"
                                >
                                  <ChevronDown size={14} />
                                </button>
                              </div>
                              <button
                                onClick={() => handleRemoveExercicio(activeTreinoIndex, exIdx)}
                                className="p-1.5 text-text-muted active:text-danger transition-colors flex-shrink-0"
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>

                            {/* Mobile: campos em grid */}
                            <div className="md:hidden mt-3 grid grid-cols-3 gap-2">
                              <div className="space-y-1">
                                <label className="text-2xs font-black text-text-muted uppercase tracking-widest text-center block">Séries</label>
                                <input
                                  type="number" value={presc.series}
                                  className="w-full bg-overlay border border-border rounded-xl py-2.5 text-center text-sm font-black text-text-primary outline-none"
                                  onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, 'series', e.target.value)}
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="text-2xs font-black text-text-muted uppercase tracking-widest text-center block">Reps</label>
                                <input
                                  type="text" value={presc.repeticoes}
                                  className="w-full bg-overlay border border-border rounded-xl py-2.5 text-center text-sm font-black text-text-primary outline-none"
                                  onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, 'repeticoes', e.target.value)}
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="text-2xs font-black text-text-muted uppercase tracking-widest text-center block">Carga</label>
                                <input
                                  type="text" value={presc.carga}
                                  className="w-full bg-overlay border border-border rounded-xl py-2.5 text-center text-sm font-black text-accent outline-none"
                                  onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, 'carga', e.target.value)}
                                  placeholder="0kg"
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="text-2xs font-black text-text-muted uppercase tracking-widest text-center block">Desc.</label>
                                <input
                                  type="number"
                                  value={nextIsSame ? 0 : presc.descanso}
                                  disabled={nextIsSame}
                                  className={`w-full border border-border rounded-xl py-2.5 text-center text-sm font-black outline-none ${nextIsSame ? 'bg-overlay/50 text-text-muted' : 'bg-overlay text-text-muted'}`}
                                  onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, 'descanso', e.target.value)}
                                />
                              </div>
                              <div className="col-span-2 space-y-1">
                                <label className="text-2xs font-black text-text-muted uppercase tracking-widest text-center block">Método</label>
                                <select
                                  value={presc.metodo}
                                  className="w-full bg-overlay border border-border rounded-xl py-2.5 px-2 text-center text-xs font-black text-text-primary outline-none appearance-none cursor-pointer"
                                  onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, 'metodo', e.target.value)}
                                >
                                  {METODOS_TREINO.map(m => <option key={m} value={m}>{m}</option>)}
                                </select>
                              </div>
                            </div>

                            {/* ── Layout desktop: horizontal (original) ── */}
                            <div className="hidden md:flex items-center gap-6">
                              <div className="w-8 h-8 rounded-lg bg-overlay flex items-center justify-center text-xs font-black text-text-muted flex-shrink-0">
                                {exIdx + 1}
                              </div>
                              <div className="flex-1 min-w-[150px]">
                                <p className="text-lg font-black text-text-primary leading-tight">{presc.nome_exercicio}</p>
                                <input
                                  type="text"
                                  placeholder="Adicionar nota (ex: Até a falha)"
                                  className="w-full bg-transparent text-xs text-text-muted font-black uppercase tracking-widest mt-1 outline-none border-b border-transparent focus:border-brand/20"
                                  value={presc.observacoes || ''}
                                  onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, 'observacoes', e.target.value)}
                                />
                              </div>
                              <div className="flex gap-2">
                                {[
                                  { key: 'series', label: 'Séries', type: 'number', width: 'w-14', className: 'text-text-primary' },
                                  { key: 'repeticoes', label: 'Reps', type: 'text', width: 'w-16', className: 'text-text-primary' },
                                  { key: 'carga', label: 'Carga', type: 'text', width: 'w-16', className: 'text-accent', placeholder: '0kg' },
                                ].map(({ key, label, type, width, className, placeholder }) => (
                                  <div key={key} className="space-y-1">
                                    <label className="text-2xs font-black text-text-muted uppercase tracking-widest text-center block">{label}</label>
                                    <input
                                      type={type}
                                      value={presc[key]}
                                      placeholder={placeholder}
                                      className={`${width} bg-overlay border border-border rounded-xl py-2 text-center text-sm font-black outline-none ${className}`}
                                      onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, key, e.target.value)}
                                    />
                                  </div>
                                ))}
                                <div className="space-y-1">
                                  <label className="text-2xs font-black text-text-muted uppercase tracking-widest text-center block">Desc.</label>
                                  <input
                                    type="number"
                                    value={nextIsSame ? 0 : presc.descanso}
                                    disabled={nextIsSame}
                                    className={`w-14 border border-border rounded-xl py-2 text-center text-sm font-black outline-none ${nextIsSame ? 'bg-overlay/50 text-text-muted cursor-not-allowed' : 'bg-overlay text-text-muted'}`}
                                    onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, 'descanso', e.target.value)}
                                  />
                                </div>
                                <div className="space-y-1">
                                  <label className="text-2xs font-black text-text-muted uppercase tracking-widest text-center block">Método</label>
                                  <select
                                    value={presc.metodo}
                                    className="w-24 bg-overlay border border-border rounded-xl py-2 px-2 text-center text-xs font-black text-text-primary outline-none appearance-none cursor-pointer"
                                    onChange={e => handleExercicioChange(activeTreinoIndex, exIdx, 'metodo', e.target.value)}
                                  >
                                    {METODOS_TREINO.map(m => <option key={m} value={m}>{m}</option>)}
                                  </select>
                                </div>
                              </div>
                              <div className="flex flex-col opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                  onClick={() => moveExercicio(activeTreinoIndex, exIdx, -1)}
                                  disabled={exIdx === 0}
                                  className="p-0.5 text-text-muted hover:text-brand disabled:opacity-30 transition-colors"
                                  aria-label="Mover exercício para cima"
                                  title="Mover para cima"
                                >
                                  <ChevronUp size={16} />
                                </button>
                                <button
                                  onClick={() => moveExercicio(activeTreinoIndex, exIdx, 1)}
                                  disabled={exIdx === prescricoes.length - 1}
                                  className="p-0.5 text-text-muted hover:text-brand disabled:opacity-30 transition-colors"
                                  aria-label="Mover exercício para baixo"
                                  title="Mover para baixo"
                                >
                                  <ChevronDown size={16} />
                                </button>
                              </div>
                              <button
                                onClick={() => handleRemoveExercicio(activeTreinoIndex, exIdx)}
                                className="p-2 text-text-muted hover:text-danger transition-colors opacity-0 group-hover:opacity-100"
                              >
                                <Trash2 size={18} />
                              </button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* ── Botão flutuante mobile: Adicionar Exercício ─────────── */}
                <div className="md:hidden absolute bottom-[72px] inset-x-0 flex justify-center pointer-events-none z-10">
                  <button
                    onClick={() => setMobileLibOpen(true)}
                    className="pointer-events-auto flex items-center gap-2 px-6 py-3.5 bg-brand text-brand-fg rounded-full font-black text-xs uppercase tracking-widest shadow-xl shadow-brand/30 active:scale-95 transition-transform"
                  >
                    <Plus size={16} /> Adicionar Exercício
                  </button>
                </div>
              </div>

              {/* ── MOBILE: biblioteca como overlay deslizante ────────────── */}
              <div
                className={`md:hidden absolute inset-0 z-20 bg-canvas flex flex-col transition-transform duration-300 ${mobileLibOpen ? 'translate-y-0' : 'translate-y-full'}`}
                style={{ transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)' }}
                aria-hidden={!mobileLibOpen}
              >
                {/* Header da biblioteca mobile */}
                <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-surface flex-shrink-0">
                  <button
                    onClick={() => setMobileLibOpen(false)}
                    className="flex items-center gap-1.5 px-3 py-2 bg-overlay text-text-secondary rounded-xl text-xs font-black uppercase tracking-widest active:scale-95 transition-transform"
                  >
                    <ChevronLeft size={14} /> Voltar
                  </button>
                  <h3 className="flex-1 text-sm font-black text-text-primary tracking-tight">Adicionar Exercício</h3>
                  {prescricoes.length > 0 && (
                    <span className="text-xs font-black text-text-muted bg-overlay px-2 py-1 rounded-lg">
                      {prescricoes.length} no treino
                    </span>
                  )}
                </div>

                {/* Biblioteca */}
                <div className="flex-1 overflow-hidden">
                  <BibliotecaExercicios
                    onSelectExercicio={(ex) => {
                      handleAddFromLibrary(ex);
                    }}
                  />
                </div>
              </div>

            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 md:p-8 bg-surface border-t border-border flex justify-between items-center gap-3 flex-shrink-0">
          <div className="flex gap-3">
            {step === 2 && (
              <button
                onClick={() => setStep(1)}
                className="px-4 md:px-6 py-3 md:py-4 bg-overlay text-text-muted rounded-xl md:rounded-2xl text-xs font-black uppercase tracking-widest transition-all active:scale-95 flex items-center gap-2"
              >
                <ChevronLeft size={14} /> <span className="hidden sm:inline">Voltar</span>
              </button>
            )}
          </div>

          {step === 2 && (
            <div className="flex gap-2 md:gap-3">
              {!planoEdicao && (
                <button
                  onClick={() => {
                    const payload = {
                      ...novoPlano,
                      treinos: novoPlano.treinos.map(t => ({
                        ...t,
                        prescricoes: t.prescricoes.map(p => ({
                          exercicio_id: parseInt(p.exercicio_id),
                          series: parseInt(p.series) || 1,
                          repeticoes: p.repeticoes,
                          carga: p.carga || null,
                          descanso: parseInt(p.descanso) || 0,
                          metodo: p.metodo,
                          observacoes: p.observacoes || null,
                        }))
                      }))
                    };
                    treinoService.criarTemplate(payload)
                      .then(() => {
                        toast({ tipo: 'sucesso', texto: 'Modelo global salvo com sucesso!' });
                        carregarTemplates();
                      })
                      .catch(err => {
                        toast({ tipo: 'erro', texto: 'Erro ao salvar modelo: ' + err.message });
                      });
                  }}
                  className="px-4 md:px-8 py-3 md:py-4 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded-xl md:rounded-2xl text-xs font-black uppercase tracking-widest transition-all active:scale-95 flex items-center gap-2"
                >
                  <Save size={14} /> <span className="hidden sm:inline">Salvar como Modelo</span>
                </button>
              )}
              <button
                onClick={handleFormSubmit}
                disabled={prescricoes.length === 0 && novoPlano.treinos.every(t => t.prescricoes.length === 0)}
                className="px-6 md:px-12 py-3 md:py-4 bg-brand hover:bg-brand-hover disabled:opacity-50 text-brand-fg rounded-xl md:rounded-2xl text-xs font-black uppercase tracking-widest transition-all shadow-lg shadow-brand/20 active:scale-95 flex items-center gap-2"
              >
                <CheckCircle2 size={14} /> {planoEdicao ? 'Salvar' : 'Finalizar'}
              </button>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
