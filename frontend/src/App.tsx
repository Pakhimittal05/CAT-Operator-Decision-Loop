import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SyntheticDataBanner } from './components/SyntheticDataBanner';
import { Dashboard } from './pages/Dashboard';
import { OperatorProfile } from './pages/OperatorProfile';
import { WhatIfSimulator } from './pages/WhatIfSimulator';

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
    { to: '/', label: 'Operations Dashboard' },
    { to: '/operators/1', label: 'Operator Dynamic State' },
    { to: '/simulate', label: 'What-If Simulator' },
  ];

  return (
    <header className="bg-slate-900 border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2">
              <span className="bg-amber-400 text-slate-950 font-black px-2 py-0.5 rounded text-sm tracking-wider">
                CAT
              </span>
              <span className="font-bold text-slate-100 text-sm tracking-tight hidden sm:inline">
                Decision Loop
              </span>
            </Link>
            <nav className="flex items-center gap-1 sm:gap-2">
              {navLinks.map((link) => {
                const isActive =
                  link.to === '/'
                    ? location.pathname === '/' || location.pathname === '/dashboard'
                    : link.to === '/simulate'
                    ? location.pathname === '/simulate'
                    : location.pathname.startsWith('/operators');
                return (
                  <Link
                    key={link.to}
                    to={link.to}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-slate-800 text-amber-300 font-semibold'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-slate-400 hidden md:inline">
              Hackathon Prototype — Phase 4
            </span>
            <div className="flex items-center gap-1.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px] font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              API ONLINE
            </div>
          </div>
        </div>
      </div>
    </header>
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
