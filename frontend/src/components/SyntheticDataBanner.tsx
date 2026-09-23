import React from 'react';

export const SyntheticDataBanner: React.FC = () => {
  return (
    <div className="bg-amber-500/10 border-b border-amber-500/30 px-4 py-1.5 text-xs font-medium text-amber-300 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        <span className="font-bold tracking-wider uppercase bg-amber-500/20 px-2 py-0.5 rounded text-[10px] text-amber-200">
          Synthetic Demonstration Data
        </span>
        <span className="hidden sm:inline text-amber-400/90 text-[11px]">
          All operators, telemetry, equipment, and scenarios are synthetically generated for demonstration. Not connected to Caterpillar proprietary operational systems.
        </span>
      </div>
      <div className="text-[11px] text-amber-400/80 font-mono hidden md:inline">
        CAT Operator Decision Loop — Closed-Loop Intelligence
      </div>
    </div>
  );
};
