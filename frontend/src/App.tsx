import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SyntheticDataBanner } from './components/SyntheticDataBanner';
import { Dashboard } from './pages/Dashboard';
import { OperatorProfile } from './pages/OperatorProfile';
import { WhatIfSimulator } from './pages/WhatIfSimulator';
import { AnomalyFeed } from './pages/AnomalyFeed';
import { PredictedVsActual } from './pages/PredictedVsActual';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 30, // 30 seconds
    },
  },
});

const Navigation: React.FC = () => {
  const location = useLocation();

  const navLinks = [
    { to: '/', label: 'Dashboard', step: 'OBSERVE' },
    { to: '/operators/1', label: 'Operator Profile', step: 'UNDERSTAND' },
    { to: '/simulate', label: 'What-If Simulator', step: 'PREDICT' },
    { to: '/compare', label: 'Predicted vs Actual', step: 'ACT & COMPARE' },
    { to: '/coaching', label: 'Safety & Coaching', step: 'LEARN' },
  ];

  const isLinkActive = (to: string) => {
    if (to === '/') {
      return location.pathname === '/' || location.pathname === '/dashboard';
    }
    if (to.startsWith('/operators')) {
      return location.pathname.startsWith('/operators');
    }
    if (to === '/simulate') {
      return location.pathname.startsWith('/simulate');
    }
    if (to === '/compare') {
      return location.pathname.startsWith('/compare');
    }
    if (to === '/coaching') {
      return location.pathname === '/coaching' || location.pathname === '/anomalies';
    }
    return false;
  };

  return (
    <>
      <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-40 backdrop-blur-md bg-slate-900/95">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-6">
              <Link to="/" className="flex items-center gap-2 group">
                <span className="bg-amber-400 text-slate-950 font-black px-2 py-0.5 rounded text-sm tracking-wider shadow-sm group-hover:bg-amber-300 transition-colors">
                  CAT
                </span>
                <span className="font-bold text-slate-100 text-sm tracking-tight hidden sm:inline group-hover:text-amber-300 transition-colors">
                  Operator Decision Loop
                </span>
              </Link>
              <nav className="flex items-center gap-1 sm:gap-1.5">
                {navLinks.map((link) => {
                  const active = isLinkActive(link.to);
                  return (
                    <Link
                      key={link.to}
                      to={link.to}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                        active
                          ? 'bg-amber-400 text-slate-950 font-bold shadow-sm'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800/80'
                      }`}
                    >
                      {link.label}
                    </Link>
                  );
                })}
              </nav>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-slate-400 font-mono hidden lg:inline">
                Enterprise Decision Platform
              </span>
              <div className="flex items-center gap-1.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px] font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                CLOSED LOOP ONLINE
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Decision Loop Workflow Indicator Ribbon */}
      <div className="bg-slate-950 border-b border-slate-800/70 px-4 py-2">
        <div className="max-w-7xl mx-auto flex items-center justify-between overflow-x-auto text-[11px] font-mono gap-4">
          <div className="flex items-center gap-2 text-slate-500 shrink-0">
            <span className="text-amber-400 font-bold uppercase tracking-wider text-[10px]">
              Continuous Intelligence Loop:
            </span>
          </div>
          <div className="flex items-center gap-2 sm:gap-4 shrink-0 text-slate-400">
            <Link
              to="/"
              className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                isLinkActive('/')
                  ? 'bg-amber-400/20 text-amber-300 border border-amber-400/30 font-bold'
                  : 'hover:text-slate-200'
              }`}
            >
              <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-[9px] flex items-center justify-center font-bold">1</span>
              <span>OBSERVE</span>
            </Link>
            <span className="text-slate-700">→</span>
            <Link
              to="/operators/1"
              className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                isLinkActive('/operators')
                  ? 'bg-amber-400/20 text-amber-300 border border-amber-400/30 font-bold'
                  : 'hover:text-slate-200'
              }`}
            >
              <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-[9px] flex items-center justify-center font-bold">2</span>
              <span>UNDERSTAND</span>
            </Link>
            <span className="text-slate-700">→</span>
            <Link
              to="/simulate"
              className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                isLinkActive('/simulate')
                  ? 'bg-amber-400/20 text-amber-300 border border-amber-400/30 font-bold'
                  : 'hover:text-slate-200'
              }`}
            >
              <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-[9px] flex items-center justify-center font-bold">3</span>
              <span>PREDICT</span>
            </Link>
            <span className="text-slate-700">→</span>
            <Link
              to="/compare"
              className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                isLinkActive('/compare')
                  ? 'bg-amber-400/20 text-amber-300 border border-amber-400/30 font-bold'
                  : 'hover:text-slate-200'
              }`}
            >
              <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-[9px] flex items-center justify-center font-bold">4</span>
              <span>ACT & COMPARE</span>
            </Link>
            <span className="text-slate-700">→</span>
            <Link
              to="/coaching"
              className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                isLinkActive('/coaching')
                  ? 'bg-amber-400/20 text-amber-300 border border-amber-400/30 font-bold'
                  : 'hover:text-slate-200'
              }`}
            >
              <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-[9px] flex items-center justify-center font-bold">5</span>
              <span>LEARN</span>
            </Link>
          </div>
        </div>
      </div>
    </>
  );
};

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
          {/* Persistent Synthetic Data Watermark Banner */}
          <SyntheticDataBanner />

          {/* Top Navigation */}
          <Navigation />

          {/* Main Content Area */}
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/operators" element={<OperatorProfile />} />
              <Route path="/operators/:id" element={<OperatorProfile />} />
              <Route path="/simulate" element={<WhatIfSimulator />} />
              <Route path="/compare" element={<PredictedVsActual />} />
              <Route path="/compare/:predictionId" element={<PredictedVsActual />} />
              <Route path="/coaching" element={<AnomalyFeed />} />
              <Route path="/anomalies" element={<AnomalyFeed />} />
            </Routes>
          </main>

          {/* Footer */}
          <footer className="border-t border-slate-900 bg-slate-950/80 py-4 text-center text-xs text-slate-500">
            CAT Operator Decision Loop — Closed Loop Intelligence Prototype
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
