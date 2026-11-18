import { useState, useEffect, useSyncExternalStore } from 'react';
import { LoginView } from './features/auth/LoginView';
import { authService, getUserRole } from './services/api';
import { ToastProvider } from './components/ToastProvider';
import { lerRota } from './rotas';

// Imports de Features
import { ListaAlunosFeature } from './features/alunos/ListaAlunos';
import { DetalheAluno } from './features/alunos/DetalheAluno';
import { ModuloTreinos } from './features/treinos/ModuloTreinos';
import DashboardFinanceiro from './features/financeiro/DashboardFinanceiro';
import DashboardFinanceiroPersonais from './features/financeiro/DashboardFinanceiroPersonais';
import { PainelAdmin } from './features/admin/PainelAdmin';

const lerHash = () => window.location.hash;
const ouvirHash = (atualizar) => {
  window.addEventListener('hashchange', atualizar);
  return () => window.removeEventListener('hashchange', atualizar);
};
const abrirAluno = (id) => { window.location.hash = `/aluno/${id}`; };
const abrirLista = () => { window.location.hash = '/alunos'; };

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'));
  const hash = useSyncExternalStore(ouvirHash, lerHash);
  const userRole = getUserRole();
  const { aba: abaAtiva, alunoId } = lerRota(hash, userRole);

  const handleLogout = () => {
    authService.logout();
    setIsAuthenticated(false);
  };

  // Sessão expirada (401): api.js limpa o token e dispara este evento
  useEffect(() => {
    const onAuthExpired = () => setIsAuthenticated(false);
    window.addEventListener('auth:expired', onAuthExpired);
    return () => window.removeEventListener('auth:expired', onAuthExpired);
  }, []);

  if (!isAuthenticated) {
    return <LoginView onLoginSuccess={() => setIsAuthenticated(true)} />;
  }

  const renderConteudo = () => {
    if (alunoId) return <DetalheAluno key={alunoId} alunoId={alunoId} onBack={abrirLista} />;
    switch (abaAtiva) {
      case 'alunos':
        return <ListaAlunosFeature onSelectAluno={abrirAluno} />;
      case 'treinos':
        return <ModuloTreinos />;
      case 'financeiro':
        return userRole === 'admin' ? <DashboardFinanceiroPersonais /> : <DashboardFinanceiro />;
      case 'admin':
        return <PainelAdmin />;
      default:
        return <ListaAlunosFeature onSelectAluno={abrirAluno} />;
    }
  };

  return (
    <div className="min-h-screen bg-canvas text-text-primary font-sans selection:bg-brand/20 overflow-x-hidden">
      <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">

        <header className="sticky top-4 z-40 flex flex-col lg:flex-row justify-between items-center mb-10 gap-6 bg-surface/80 p-3 md:p-4 rounded-xl border border-border backdrop-blur-md shadow-sm">
          <div className="flex items-center justify-between w-full lg:w-auto px-2">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-brand flex items-center justify-center font-bold text-brand-fg shadow-sm text-xs">PT</div>
              <h1 className="text-lg font-bold text-text-primary tracking-tight">PTRoster<span className="text-brand">.</span></h1>
            </div>

            <button
              onClick={handleLogout}
              className="lg:hidden px-4 py-2 bg-overlay hover:bg-border text-xs font-bold text-text-secondary rounded-lg transition-all active:scale-95 uppercase tracking-widest"
            >
              Sair
            </button>
          </div>

          <nav
            aria-label="Navegação principal"
            className="flex p-1 bg-overlay rounded-lg border border-border w-full lg:w-auto overflow-x-auto no-scrollbar"
          >
            {[
              { id: 'alunos', label: 'Alunos' },
              { id: 'treinos', label: 'Treinos' },
              { id: 'financeiro', label: 'Financeiro' },
              ...(userRole === 'admin' ? [{ id: 'admin', label: 'Operações' }] : []),
            ].map((aba) => (
              <a
                key={aba.id}
                href={`#/${aba.id}`}
                aria-current={abaAtiva === aba.id ? 'page' : undefined}
                className={`flex-1 lg:flex-none px-6 py-2 rounded-md text-xs font-bold transition-all duration-200 whitespace-nowrap ${
                  abaAtiva === aba.id
                    ? 'bg-surface text-text-primary shadow-sm ring-1 ring-text-ink/5'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {aba.label}
              </a>
            ))}
          </nav>

          <button
            onClick={handleLogout}
            className="hidden lg:block px-6 py-2.5 bg-overlay hover:bg-border text-xs font-bold text-text-secondary rounded-lg transition-all active:scale-95 border border-border"
          >
            Logout
          </button>
        </header>

        <main
          className="min-h-[60vh] animate-in fade-in slide-in-from-bottom-2 duration-300"
        >
          {renderConteudo()}
        </main>

        <footer className="mt-20 pt-8 border-t border-border text-center">
          <p className="text-text-muted text-xs font-bold uppercase tracking-widest">
            © 2026 PTRoster · v1.0.2 Premium
          </p>
        </footer>
      </div>

    </div>
  );
}

export default function AppWithToast() {
  return (
    <ToastProvider>
      <App />
    </ToastProvider>
  );
}
