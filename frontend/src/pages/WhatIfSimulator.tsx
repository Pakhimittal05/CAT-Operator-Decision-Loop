import React, { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  fetchSimulationOptions,
  runSimulation,
  SimulationResponse,
  SimulationRequest,
} from '../api/client';

export const WhatIfSimulator: React.FC = () => {
  const [selectedOperatorId, setSelectedOperatorId] = useState<number>(1);
  const [selectedMachineId, setSelectedMachineId] = useState<number>(1);
  const [selectedTaskId, setSelectedTaskId] = useState<number>(1);
  const [selectedWeather, setSelectedWeather] = useState<string>('Clear');

  // Query simulation options
  const {
    data: options,
    isLoading: optionsLoading,
    isError: optionsError,
  } = useQuery({
    queryKey: ['simulationOptions'],
    queryFn: fetchSimulationOptions,
  });

  // Automatically select first available options once loaded
  useEffect(() => {
    if (options) {
      if (options.operators.length > 0 && !options.operators.some((o) => o.id === selectedOperatorId)) {
        setSelectedOperatorId(options.operators[0].id);
      }
      if (options.machines.length > 0 && !options.machines.some((m) => m.id === selectedMachineId)) {
        setSelectedMachineId(options.machines[0].id);
      }
      if (options.tasks.length > 0 && !options.tasks.some((t) => t.id === selectedTaskId)) {
        setSelectedTaskId(options.tasks[0].id);
      }
    }
  }, [options]);

  // Mutation to execute simulation
  const simulationMutation = useMutation({
    mutationFn: (req: SimulationRequest) => runSimulation(req),
  });

  const handleRunSimulation = () => {
    simulationMutation.mutate({
      operator_id: selectedOperatorId,
      machine_id: selectedMachineId,
      task_type_id: selectedTaskId,
      weather: selectedWeather,
    });
  };

  const selectedOperator = options?.operators.find((o) => o.id === selectedOperatorId);
  const selectedMachine = options?.machines.find((m) => m.id === selectedMachineId);
  const selectedTask = options?.tasks.find((t) => t.id === selectedTaskId);
  const result: SimulationResponse | undefined = simulationMutation.data;

  return (
    <div className="space-y-6">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="bg-amber-400 text-slate-950 text-xs font-black px-2 py-0.5 rounded tracking-wide">
              PILLAR 3
            </span>
            <span className="text-xs font-mono text-amber-400">WHAT-IF TASK SIMULATOR</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
            Pre-Task Scenario & Time-Uncertainty Simulator
          </h1>
          <p className="text-xs text-slate-400 max-w-2xl mt-1">
            Simulate operational outcomes before assigning tasks. Consumes dynamic operator state, machine wear,
            and task difficulty to predict duration with calibrated uncertainty bounds (P10–P90) and safety risk.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-right">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">Shared Intelligence</div>
            <div className="text-xs font-semibold text-slate-300">EWMA Dynamic State + Quantile GB</div>
          </div>
        </div>
      </div>

      {optionsError && (
        <div className="bg-rose-950/50 border border-rose-800/60 p-4 rounded-xl text-rose-300 text-sm">
          Failed to load simulator configuration options from backend. Please ensure the API is running.
        </div>
      )}

      {/* ── Simulation Configuration Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* 1. Operator Selector */}
        <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
          <div>
            <label className="block text-xs font-mono uppercase text-slate-400 mb-2">1. Select Operator</label>
            <select
              value={selectedOperatorId}
              onChange={(e) => setSelectedOperatorId(Number(e.target.value))}
              disabled={optionsLoading}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-400"
            >
              {options?.operators.map((op) => (
                <option key={op.id} value={op.id}>
                  {op.name} ({op.derived_label})
                </option>
              ))}
            </select>
          </div>

          {selectedOperator && (
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-slate-400">Dynamic Score:</span>
              <div className="flex items-center gap-1.5 font-mono">
                <span className="font-bold text-amber-400">{selectedOperator.composite_score.toFixed(1)}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                  {selectedOperator.derived_label}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* 2. Machine Selector */}
        <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
          <div>
            <label className="block text-xs font-mono uppercase text-slate-400 mb-2">2. Select Equipment</label>
            <select
              value={selectedMachineId}
              onChange={(e) => setSelectedMachineId(Number(e.target.value))}
              disabled={optionsLoading}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-400"
            >
              {options?.machines.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.machine_type})
                </option>
              ))}
            </select>
          </div>

          {selectedMachine && (
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-slate-400">Wear Index:</span>
              <div className="flex items-center gap-2">
                <div className="w-16 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${
                      selectedMachine.wear_factor > 0.5 ? 'bg-amber-400' : 'bg-emerald-400'
                    }`}
                    style={{ width: `${selectedMachine.wear_factor * 100}%` }}
                  />
                </div>
                <span className="font-mono text-slate-300">{selectedMachine.wear_factor.toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>

        {/* 3. Task Type Selector */}
        <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
          <div>
            <label className="block text-xs font-mono uppercase text-slate-400 mb-2">3. Select Task Type</label>
            <select
              value={selectedTaskId}
              onChange={(e) => setSelectedTaskId(Number(e.target.value))}
              disabled={optionsLoading}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-400"
            >
              {options?.tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} (Diff: {t.difficulty.toFixed(2)})
                </option>
              ))}
            </select>
          </div>

          {selectedTask && (
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-slate-400">Baseline Duration:</span>
              <span className="font-mono text-slate-300 font-semibold">
                {selectedTask.baseline_duration_minutes.toFixed(1)} min
              </span>
            </div>
          )}
        </div>

        {/* 4. Weather Condition Selector */}
        <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl flex flex-col justify-between">
          <div>
            <label className="block text-xs font-mono uppercase text-slate-400 mb-2">4. Weather Context</label>
            <div className="grid grid-cols-2 gap-1.5">
              {(options?.weather_options || ['Clear', 'Rain', 'Mud', 'Snow/Ice']).map((w) => {
                const isSelected = selectedWeather === w;
                return (
                  <button
                    key={w}
                    type="button"
                    onClick={() => setSelectedWeather(w)}
                    className={`px-2 py-1.5 text-xs rounded font-medium transition-colors border ${
                      isSelected
                        ? 'bg-amber-400 text-slate-950 border-amber-400 font-bold'
                        : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200 hover:border-slate-700'
                    }`}
                  >
                    {w}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80">
            <button
              onClick={handleRunSimulation}
              disabled={simulationMutation.isPending || optionsLoading}
              className="w-full bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 font-bold py-2 px-4 rounded-lg text-xs uppercase tracking-wider hover:brightness-110 active:brightness-95 transition-all shadow-md shadow-amber-500/10 disabled:opacity-50"
            >
              {simulationMutation.isPending ? 'Simulating...' : 'Run Simulation'}
            </button>
          </div>
        </div>
      </div>

      {/* ── Results Panel (Appears after simulation) ── */}
      {result && (
        <div className="space-y-6 pt-2">
          {/* Main KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Predicted Duration */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl relative overflow-hidden">
              <div className="text-[11px] font-mono uppercase text-slate-400 mb-1">Expected Completion Time</div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-amber-400 tracking-tight font-mono">
                  {result.predicted_duration_minutes.toFixed(1)}
                </span>
                <span className="text-slate-400 text-sm font-medium">minutes</span>
              </div>
              {selectedTask && (
                <div className="text-[11px] text-slate-500 mt-2">
                  {result.predicted_duration_minutes > selectedTask.baseline_duration_minutes ? (
                    <span className="text-amber-400/90 font-mono">
                      +{(result.predicted_duration_minutes - selectedTask.baseline_duration_minutes).toFixed(1)}m
                    </span>
                  ) : (
                    <span className="text-emerald-400/90 font-mono">
                      -{(selectedTask.baseline_duration_minutes - result.predicted_duration_minutes).toFixed(1)}m
                    </span>
                  )}{' '}
                  vs {selectedTask.name} baseline ({selectedTask.baseline_duration_minutes.toFixed(1)}m)
                </div>
              )}
            </div>

            {/* 2. Uncertainty Interval (P10 - P90) */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
              <div className="text-[11px] font-mono uppercase text-slate-400 mb-1">Uncertainty Band (P10 – P90)</div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-100 font-mono">
                  {result.p10_minutes.toFixed(1)} – {result.p90_minutes.toFixed(1)}
                </span>
                <span className="text-slate-400 text-xs">min</span>
              </div>
              <div className="mt-3">
                {/* Visual Whisker Bar */}
                <div className="w-full bg-slate-950 h-2 rounded-full relative overflow-hidden border border-slate-800">
                  <div
                    className="absolute bg-amber-400/40 h-full rounded-full"
                    style={{
                      left: '15%',
                      width: '70%',
                    }}
                  />
                  <div
                    className="absolute bg-amber-400 h-full w-1 rounded"
                    style={{ left: '50%' }}
                  />
                </div>
                <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1">
                  <span>P10: {result.p10_minutes.toFixed(1)}m</span>
                  <span>Point: {result.predicted_duration_minutes.toFixed(1)}m</span>
                  <span>P90: {result.p90_minutes.toFixed(1)}m</span>
                </div>
              </div>
            </div>

            {/* 3. Skill Fit Match */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
              <div className="text-[11px] font-mono uppercase text-slate-400 mb-1">Operator Skill Fit</div>
              <div className="flex items-baseline gap-2">
                <span
                  className={`text-3xl font-black font-mono tracking-tight ${
                    result.skill_fit_score >= 70
                      ? 'text-emerald-400'
                      : result.skill_fit_score >= 50
                      ? 'text-amber-400'
                      : 'text-rose-400'
                  }`}
                >
                  {result.skill_fit_score.toFixed(1)}%
                </span>
                <span className="text-xs font-semibold text-slate-300">{result.skill_fit_label}</span>
              </div>
              <div className="w-full bg-slate-950 h-1.5 rounded-full mt-3 overflow-hidden">
                <div
                  className={`h-full ${
                    result.skill_fit_score >= 70
                      ? 'bg-emerald-400'
                      : result.skill_fit_score >= 50
                      ? 'bg-amber-400'
                      : 'bg-rose-400'
                  }`}
                  style={{ width: `${result.skill_fit_score}%` }}
                />
              </div>
              <div className="text-[10px] text-slate-500 mt-2">
                Evaluated against task difficulty rating
              </div>
            </div>

            {/* 4. Behavioral & Safety Risk */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
              <div className="text-[11px] font-mono uppercase text-slate-400 mb-1">Safety & Operational Risk</div>
              <div className="flex items-baseline gap-2">
                <span
                  className={`text-3xl font-black font-mono tracking-tight ${
                    result.safety_risk_level === 'low'
                      ? 'text-emerald-400'
                      : result.safety_risk_level === 'moderate'
                      ? 'text-amber-400'
                      : 'text-rose-400'
                  }`}
                >
                  {result.safety_risk_score.toFixed(1)}%
                </span>
                <span
                  className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                    result.safety_risk_level === 'low'
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      : result.safety_risk_level === 'moderate'
                      ? 'bg-amber-950 text-amber-300 border border-amber-800'
                      : 'bg-rose-950 text-rose-300 border border-rose-800'
                  }`}
                >
                  {result.safety_risk_level}
                </span>
              </div>
              <div className="w-full bg-slate-950 h-1.5 rounded-full mt-3 overflow-hidden">
                <div
                  className={`h-full ${
                    result.safety_risk_level === 'low'
                      ? 'bg-emerald-400'
                      : result.safety_risk_level === 'moderate'
                      ? 'bg-amber-400'
                      : 'bg-rose-400'
                  }`}
                  style={{ width: `${result.safety_risk_score}%` }}
                />
              </div>
              <div className="text-[10px] text-slate-500 mt-2">
                Composite of safety score, machine wear, & weather
              </div>
            </div>
          </div>

          {/* Training Recommendation Banner */}
          {result.training_recommended && (
            <div className="bg-amber-950/40 border border-amber-500/40 p-4 rounded-xl flex items-start gap-3">
              <div className="p-2 rounded bg-amber-500/20 text-amber-300 mt-0.5">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h4 className="text-xs font-bold text-amber-300 uppercase tracking-wide">
                  Targeted Coaching / Training Recommended Before Task Assignment
                </h4>
                <p className="text-xs text-amber-200/90 mt-1 leading-relaxed">
                  {result.training_reason}
                </p>
              </div>
            </div>
          )}

          {/* Model Explainability: Probable Contributing Factors (§24) */}
          <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider font-mono">
                  Probable Contributing Factors (Attribution Analysis)
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Probabilistic feature attribution explaining model output variance. In accordance with CAT AI governance, attributions represent observed correlation patterns, not proven causation.
                </p>
              </div>
              <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-2 py-1 rounded border border-slate-800">
                Prediction #{result.prediction_id} Persisted
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {result.probable_factors.map((factor, idx) => (
                <div
                  key={idx}
                  className="bg-slate-950/80 border border-slate-800/80 p-3.5 rounded-lg flex flex-col justify-between"
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="text-xs font-semibold text-slate-200">{factor.factor_name}</span>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold whitespace-nowrap ${
                        factor.impact_direction === 'increases_duration'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      }`}
                    >
                      {factor.impact_direction === 'increases_duration' ? '+ Duration' : '- Duration'}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed mb-3">
                    {factor.description}
                  </p>

                  <div className="pt-2 border-t border-slate-900 flex items-center justify-between text-[11px] font-mono text-slate-500">
                    <div className="flex items-center gap-2">
                      <span>Attribution:</span>
                      <span className="text-amber-400 font-semibold">{factor.impact_percentage}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span>Confidence:</span>
                      <span className="text-slate-300">{factor.confidence}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
