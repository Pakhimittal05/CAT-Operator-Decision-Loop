import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchOperatorState, fetchOperatorHistory, fetchOperators } from '../api/client';
import { DeviationRadar } from '../components/DeviationRadar';

export const OperatorProfile: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const operatorId = id ? parseInt(id, 10) : 1;
  const [historyLimit, setHistoryLimit] = useState(25);

  const { data: operators } = useQuery({
    queryKey: ['operators'],
    queryFn: fetchOperators,
  });

  const {
    data: state,
    isLoading: isStateLoading,
    error: stateError,
  } = useQuery({
    queryKey: ['operatorState', operatorId],
    queryFn: () => fetchOperatorState(operatorId),
  });

  const {
    data: historyData,
    isLoading: isHistoryLoading,
  } = useQuery({
    queryKey: ['operatorHistory', operatorId, historyLimit],
    queryFn: () => fetchOperatorHistory(operatorId, historyLimit),
  });

  const currentOp = operators?.find((o) => o.id === operatorId);

  if (isStateLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-amber-400 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-slate-400 text-xs">Computing dynamic EWMA operator state...</p>
        </div>
      </div>
    );
  }

  if (stateError || !state) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center my-6">
        <h3 className="text-red-400 font-semibold mb-1">Operator #{operatorId} Not Found</h3>
        <p className="text-slate-400 text-xs mb-3">Unable to retrieve dynamic state from backend.</p>
        <button
          onClick={() => navigate('/operators/1')}
          className="px-3 py-1 bg-amber-500 text-slate-950 font-semibold text-xs rounded"
        >
          View Operator 1
        </button>
      </div>
    );
  }

  const dimensionBars = [
    { label: 'Cycle Efficiency', score: state.efficiency_score, desc: 'Telemetry work output vs reference model' },
    { label: 'Idling Control', score: state.idling_score, desc: 'Non-productive engine time penalty' },
    { label: 'Pacing / Duration', score: state.duration_score, desc: 'Task completion pace relative to expected baseline' },
    { label: 'Load Cycles', score: state.load_cycle_score, desc: 'Cycle volume throughput vs baseline difficulty' },
    { label: 'Safety Clearance', score: state.safety_score, desc: 'Proximity hazard distance from boundaries' },
  ];

  return (
    <div className="space-y-6">
      {/* Header & Operator Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-100">
              {currentOp?.name || `Operator #${operatorId}`}
            </h1>
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                state.derived_label === 'Expert'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : state.derived_label === 'Intermediate'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
              }`}
            >
              {state.derived_label}
            </span>
            <span className="text-xs text-slate-500 font-mono">
              Legacy: {currentOp?.legacy_skill_tier}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Dynamic performance state aggregated via recency-weighted EWMA from actual task telemetry deviations
          </p>
        </div>

        {/* Switcher dropdown */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 font-medium">Select Operator:</label>
          <select
            value={operatorId}
            onChange={(e) => navigate(`/operators/${e.target.value}`)}
            className="bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-amber-400"
          >
            {operators?.map((op) => (
              <option key={op.id} value={op.id}>
                {op.name} ({op.derived_label} — {Math.round(op.composite_score)})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Primary KPI Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Composite Score Card */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="text-xs text-slate-400 font-medium">Overall Composite State</div>
          <div className="flex items-baseline gap-2 my-2">
            <span className="text-4xl font-extrabold text-amber-400 font-mono">
              {state.composite_score.toFixed(1)}
            </span>
            <span className="text-slate-500 text-sm">/ 100</span>
          </div>
          <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                state.composite_score >= 75
                  ? 'bg-emerald-500'
                  : state.composite_score >= 50
                  ? 'bg-amber-400'
                  : 'bg-rose-500'
              }`}
              style={{ width: `${Math.min(100, Math.max(0, state.composite_score))}%` }}
            />
          </div>
          <div className="text-[10px] text-slate-500 mt-2">
            Thresholds: Expert &ge; 75 | Intermediate &ge; 50 | Beginner &lt; 50
          </div>
        </div>

        {/* Trend Indicator */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="text-xs text-slate-400 font-medium">Performance Trend</div>
          <div className="my-2">
            <span
              className={`inline-flex items-center gap-1.5 text-base font-bold px-3 py-1 rounded-lg ${
                state.trend_direction === 'improving'
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : state.trend_direction === 'declining'
                  ? 'bg-rose-500/20 text-rose-300'
                  : 'bg-slate-800 text-slate-300'
              }`}
            >
              <span>
                {state.trend_direction === 'improving' && '▲ Improving'}
                {state.trend_direction === 'declining' && '▼ Declining'}
                {state.trend_direction === 'stable' && '━ Stable'}
              </span>
            </span>
          </div>
          <div className="text-[11px] text-slate-400">
            EWMA recency weight &alpha; = 0.20
          </div>
        </div>

        {/* Confidence & Sample Count */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="text-xs text-slate-400 font-medium">Evaluation Confidence</div>
          <div className="my-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-slate-200 font-mono">
              {(state.confidence * 100).toFixed(0)}%
            </span>
            <span className="text-xs text-slate-500">
              ({state.sample_count} tasks)
            </span>
          </div>
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <div
              className="bg-sky-400 h-full rounded-full transition-all"
              style={{ width: `${state.confidence * 100}%` }}
            />
          </div>
          <div className="text-[10px] text-slate-500 mt-2">
            Sample saturation model: 1 &minus; e<sup>&minus;n/10</sup>
          </div>
        </div>

        {/* Intelligence Architecture Note */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="text-xs text-slate-400 font-medium">Continuous State Note</div>
          <p className="text-xs text-slate-300 leading-relaxed mt-1">
            Categorical badges are UI labels computed from continuous state. The continuous score directly drives what-if simulation and anomaly detection.
          </p>
          <div className="text-[10px] text-amber-400/90 font-mono mt-2">
            Zero LLM in state logic
          </div>
        </div>
      </div>

      {/* Visualizations: Radar Chart + 5 Dimension Progress Bars */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DeviationRadar
          scores={{
            efficiency_score: state.efficiency_score,
            idling_score: state.idling_score,
            duration_score: state.duration_score,
            load_cycle_score: state.load_cycle_score,
            safety_score: state.safety_score,
          }}
          title="Dynamic Skill Radar (5 Dimensions)"
        />

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-200 mb-3">
              Per-Dimension Continuous Skill Breakdown
            </h3>
            <div className="space-y-3.5">
              {dimensionBars.map((dim) => (
                <div key={dim.label}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-medium text-slate-300">{dim.label}</span>
                    <span className="font-mono text-amber-300 font-bold">
                      {dim.score.toFixed(1)} <span className="text-slate-500 text-[10px]">/ 100</span>
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        dim.score >= 75
                          ? 'bg-emerald-400'
                          : dim.score >= 50
                          ? 'bg-amber-400'
                          : 'bg-rose-400'
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, dim.score))}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{dim.desc}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="pt-3 border-t border-slate-800 text-[11px] text-slate-400">
            Calculated via shared <code className="text-amber-300 bg-slate-800 px-1 py-0.5 rounded font-mono">compute_deviation()</code> pipeline.
          </div>
        </div>
      </div>

      {/* Historical Tasks & Deviation Vectors Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">
              Chronological Task History &amp; Standardized Deviation Vectors (D)
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Standardized z-scores D = [d_eff, d_idle, d_dur, d_load, d_safe] and composite Euclidean magnitude
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Items:</span>
            <select
              value={historyLimit}
              onChange={(e) => setHistoryLimit(Number(e.target.value))}
              className="bg-slate-800 text-slate-200 border border-slate-700 rounded px-2 py-1 text-xs focus:outline-none"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Task ID</th>
                <th className="py-2.5 px-3">Task Type</th>
                <th className="py-2.5 px-3">Machine</th>
                <th className="py-2.5 px-3">Weather</th>
                <th className="py-2.5 px-3 text-right">d_efficiency</th>
                <th className="py-2.5 px-3 text-right">d_idling</th>
                <th className="py-2.5 px-3 text-right">d_duration</th>
                <th className="py-2.5 px-3 text-right">d_load_cycle</th>
                <th className="py-2.5 px-3 text-right">d_safety</th>
                <th className="py-2.5 px-3 text-right font-bold text-amber-300">||D|| Mag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
              {isHistoryLoading ? (
                <tr>
                  <td colSpan={10} className="py-6 text-center text-slate-400 font-sans">
                    Loading task history...
                  </td>
                </tr>
              ) : (
                historyData?.history.map((h) => (
                <tr key={h.task_instance_id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-2 px-3 text-slate-400 font-semibold">#{h.task_instance_id}</td>
                  <td className="py-2 px-3 font-sans text-slate-200">{h.task_type}</td>
                  <td className="py-2 px-3 text-slate-300">{h.machine_name}</td>
                  <td className="py-2 px-3 capitalize font-sans text-slate-400">{h.weather}</td>
                  <td className={`py-2 px-3 text-right ${h.d_cycle_efficiency >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {h.d_cycle_efficiency > 0 ? `+${h.d_cycle_efficiency.toFixed(2)}` : h.d_cycle_efficiency.toFixed(2)}
                  </td>
                  <td className={`py-2 px-3 text-right ${h.d_idling <= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {h.d_idling > 0 ? `+${h.d_idling.toFixed(2)}` : h.d_idling.toFixed(2)}
                  </td>
                  <td className={`py-2 px-3 text-right ${h.d_duration <= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {h.d_duration > 0 ? `+${h.d_duration.toFixed(2)}` : h.d_duration.toFixed(2)}
                  </td>
                  <td className={`py-2 px-3 text-right ${h.d_load_cycle >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {h.d_load_cycle > 0 ? `+${h.d_load_cycle.toFixed(2)}` : h.d_load_cycle.toFixed(2)}
                  </td>
                  <td className={`py-2 px-3 text-right ${h.d_safety >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {h.d_safety > 0 ? `+${h.d_safety.toFixed(2)}` : h.d_safety.toFixed(2)}
                  </td>
                  <td className="py-2 px-3 text-right font-bold text-amber-300">
                    {h.composite_magnitude.toFixed(2)}
                  </td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
