import React from 'react';

export const SyntheticDataBanner: React.FC = () => {
  return (
    <div className="bg-amber-500/10 border-b border-amber-500/30 px-4 py-2 text-xs font-medium text-amber-300 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        <span className="font-bold tracking-wider uppercase bg-amber-500/20 px-2 py-0.5 rounded text-[10px] text-amber-200">
          Synthetic Data — Hackathon Demo
        </span>
        <span className="hidden sm:inline text-amber-400/80">
          All operators, telemetry, machines, and scenarios are synthetically generated for demonstration. Not connected to Caterpillar proprietary systems.
        </span>
      </div>
      <div className="text-[11px] text-amber-400/70 font-mono">
        CAT Decision Loop v1.0
      </div>
    </div>
  );
};
