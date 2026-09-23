import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchComparison,
  fetchRecentComparisons,
  triggerProcessBOutcome,
} from '../api/client';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';

export const PredictedVsActual: React.FC = () => {
  const { predictionId } = useParams<{ predictionId?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [activePredictionId, setActivePredictionId] = useState<number | null>(
    predictionId ? Number(predictionId) : null
  );

  useEffect(() => {
    if (predictionId) {
      setActivePredictionId(Number(predictionId));
    }
  }, [predictionId]);

  // Query recent execution comparisons
  const {
    data: historyData,
    isLoading: historyLoading,
    refetch: refetchHistory,
  } = useQuery({
    queryKey: ['recentComparisons'],
    queryFn: () => fetchRecentComparisons(10),
  });

  // Automatically select most recent executed prediction if none selected in URL
  useEffect(() => {
    if (!activePredictionId && historyData && historyData.comparisons.length > 0) {
      setActivePredictionId(historyData.comparisons[0].prediction_id);
    }
  }, [historyData, activePredictionId]);

  // Query comparison for active prediction
  const {
    data: comparison,
    isLoading: comparisonLoading,
    isError: comparisonError,
  } = useQuery({
    queryKey: ['predictionComparison', activePredictionId],
    queryFn: () => fetchComparison(activePredictionId!),
    enabled: activePredictionId !== null,
    retry: false,
  });

  // Mutation to trigger Process B execution
  const executeMutation = useMutation({
    mutationFn: ({ predId, seed }: { predId: number; seed?: number }) =>
      triggerProcessBOutcome(predId, seed),
    onSuccess: (data) => {
      queryClient.setQueryData(['predictionComparison', data.prediction_id], data);
      refetchHistory();
      navigate(`/compare/${data.prediction_id}`);
    },
  });

  const handleExecute = (seed?: number) => {
    if (activePredictionId) {
      executeMutation.mutate({ predId: activePredictionId, seed });
    }
  };

  // Chart data for Predicted vs Actual duration
  const chartData = comparison
    ? [
        {
          name: 'Lower Bound (P10)',
          value: comparison.p10_minutes,
          color: '#64748b', // slate-500
        },
        {
          name: 'Predicted Time',
          value: comparison.predicted_duration_minutes,
          color: '#f59e0b', // amber-500
        },
        {
          name: 'Upper Bound (P90)',
          value: comparison.p90_minutes,
          color: '#64748b', // slate-500
        },
        {
          name: 'Actual Outcome (Process B)',
          value: comparison.actual_duration_minutes,
          color: comparison.is_within_interval ? '#10b981' : '#f43f5e', // emerald vs rose
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="bg-amber-400 text-slate-950 text-xs font-black px-2 py-0.5 rounded tracking-wide">
              STEP 4: ACT &amp; COMPARE
            </span>
            <span className="text-xs font-mono text-amber-400">CLOSED-LOOP INTELLIGENCE</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
            Predicted vs Actual Outcome Comparison
          </h1>
          <p className="text-xs text-slate-400 max-w-2xl mt-1">
            Validates simulation accuracy against independent Stochastic Process B real-world telemetry.
            Computes evidence-based deviation and dynamically recalibrates operator state.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/simulate')}
            className="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-900 text-xs font-medium text-slate-300 hover:bg-slate-800 transition-colors"
          >
            ← Back to Simulator
          </button>
        </div>
      </div>

      {/* ── Closed-Loop Visual Pipeline Indicator ── */}
      <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-xs font-mono">
          <div className="flex items-center gap-2 text-slate-400">
            <span className="w-5 h-5 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] text-amber-400 font-bold">
              1
            </span>
            <span>PREDICT (What-If)</span>
          </div>
          <span className="text-slate-600 hidden sm:inline">⟶</span>

          <div className="flex items-center gap-2 text-slate-400">
            <span className="w-5 h-5 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] text-emerald-400 font-bold">
              2
            </span>
            <span>EXECUTE (Process B)</span>
          </div>
          <span className="text-slate-600 hidden sm:inline">⟶</span>

          <div className="flex items-center gap-2 text-amber-400 font-semibold">
            <span className="w-5 h-5 rounded-full bg-amber-400 text-slate-950 flex items-center justify-center text-[10px] font-black">
              3
            </span>
            <span>COMPARE (Uncertainty & Error)</span>
          </div>
          <span className="text-slate-600 hidden sm:inline">⟶</span>

          <div className="flex items-center gap-2 text-emerald-400 font-semibold">
            <span className="w-5 h-5 rounded-full bg-emerald-400 text-slate-950 flex items-center justify-center text-[10px] font-black">
              4
            </span>
            <span>LEARN (EWMA Recalibration)</span>
          </div>
        </div>
      </div>

      {/* ── Loading State ── */}
      {comparisonLoading && (
        <div className="bg-slate-900 border border-slate-800 p-8 rounded-xl text-center">
          <p className="text-sm text-slate-400 font-mono animate-pulse">
            Loading predicted vs actual telemetry comparison...
          </p>
        </div>
      )}

      {/* ── Execution Prompt (If prediction pending execution) ── */}
      {comparisonError && activePredictionId && (
        <div className="bg-amber-950/40 border border-amber-800/60 p-5 rounded-xl space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-amber-300">
                Pending Simulation Execution — Prediction #{activePredictionId}
              </h3>
              <p className="text-xs text-amber-200/80 mt-1">
                This simulated scenario has not yet executed in field telemetry. Trigger independent Process B to
                generate actual telemetry and close the decision loop.
              </p>
            </div>
            <span className="text-[10px] font-mono bg-amber-900/60 text-amber-300 px-2 py-0.5 rounded border border-amber-700">
              PENDING
            </span>
          </div>

          <div className="pt-2 flex flex-wrap items-center gap-3">
            <button
              onClick={() => handleExecute(42)}
              disabled={executeMutation.isPending}
              className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs shadow-md transition-colors flex items-center gap-2"
            >
              <span>⚡ Run Demo Execution (Reproducible Seed)</span>
            </button>
            <button
              onClick={() => handleExecute(undefined)}
              disabled={executeMutation.isPending}
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium text-xs transition-colors flex items-center gap-2"
            >
              <span>🎲 Run Stochastic Live Execution</span>
            </button>
            {executeMutation.isPending && (
              <span className="text-xs text-slate-400 font-mono animate-pulse">
                Generating Process B Telemetry & Recalibrating State...
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Main Comparison View ── */}
      {comparison && (
        <div className="space-y-6">
          {/* Metadata & Controls Bar */}
          <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
              <div>
                <span className="text-slate-500">OPERATOR: </span>
                <span className="text-slate-200 font-bold">{comparison.operator_name}</span>
              </div>
              <span className="text-slate-700">|</span>
              <div>
                <span className="text-slate-500">MACHINE: </span>
                <span className="text-slate-200 font-semibold">{comparison.machine_name}</span>
              </div>
              <span className="text-slate-700">|</span>
              <div>
                <span className="text-slate-500">TASK: </span>
                <span className="text-slate-200 font-semibold">{comparison.task_type_name}</span>
              </div>
              <span className="text-slate-700">|</span>
              <div>
                <span className="text-slate-500">WEATHER: </span>
                <span className="text-amber-400 font-semibold">{comparison.weather}</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-2 py-1 rounded border border-slate-800">
                TaskInstance #{comparison.task_instance_id} (Process B)
              </span>
              <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-2 py-1 rounded border border-slate-800">
                Prediction #{comparison.prediction_id}
              </span>
            </div>
          </div>

          {/* Primary Metrics Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Predicted Duration */}
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                Predicted Duration
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-black text-amber-400 font-mono">
                  {comparison.predicted_duration_minutes.toFixed(1)}
                </span>
                <span className="text-xs text-slate-400 font-mono">min</span>
              </div>
              <div className="mt-2 text-[11px] text-slate-400 font-mono">
                P10: {comparison.p10_minutes.toFixed(1)}m — P90: {comparison.p90_minutes.toFixed(1)}m
              </div>
            </div>

            {/* 2. Actual Duration */}
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                Actual Duration (Process B)
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-black text-slate-100 font-mono">
                  {comparison.actual_duration_minutes.toFixed(1)}
                </span>
                <span className="text-xs text-slate-400 font-mono">min</span>
              </div>
              <div className="mt-2 flex items-center gap-1.5">
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
                    comparison.is_within_interval
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                  }`}
                >
                  {comparison.is_within_interval
                    ? '✓ Within Calibrated Interval'
                    : '! Outside Uncertainty Band'}
                </span>
              </div>
            </div>

            {/* 3. Observed Difference */}
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                Observed Difference
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span
                  className={`text-3xl font-black font-mono ${
                    comparison.duration_difference_minutes > 0
                      ? 'text-rose-400'
                      : 'text-emerald-400'
                  }`}
                >
                  {comparison.duration_difference_minutes > 0 ? '+' : ''}
                  {comparison.duration_difference_minutes.toFixed(1)}
                </span>
                <span className="text-xs text-slate-400 font-mono">min</span>
              </div>
              <div className="mt-2 text-[11px] text-slate-400 font-mono">
                Absolute Error: {comparison.absolute_error_minutes.toFixed(1)} min
              </div>
            </div>

            {/* 4. Percentage Error */}
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                Relative Error
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-black text-slate-100 font-mono">
                  {comparison.percentage_error.toFixed(1)}%
                </span>
              </div>
              <div className="mt-2 text-[11px] text-slate-400 font-mono">
                Relative to actual execution
              </div>
            </div>
          </div>

          {/* Duration & Interval Visual Comparison */}
          <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
            <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider font-mono mb-1">
              Duration Distribution & Interval Calibration
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Comparison of predicted point estimate and calibrated uncertainty band against independent actual execution.
            </p>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 20 }}>
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} unit="m" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <ReferenceLine
                    y={comparison.actual_duration_minutes}
                    stroke="#10b981"
                    strokeDasharray="3 3"
                    label={{
                      value: `Actual: ${comparison.actual_duration_minutes.toFixed(1)}m`,
                      fill: '#10b981',
                      fontSize: 10,
                      position: 'top',
                    }}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Two-Column: 5D Deviation Breakdown + Dynamic State Recalibration */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 5-Dimension Deviation Vector Breakdown */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-4">
              <div>
                <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider font-mono">
                  Shared Deviation Engine Output
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Standardized residual z-scores relative to context baseline for this task execution.
                </p>
              </div>

              <div className="space-y-3 font-mono text-xs">
                {Object.entries(comparison.deviation_vector).map(([dim, zScore]) => (
                  <div key={dim} className="bg-slate-950/70 p-3 rounded-lg border border-slate-800/80">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-slate-300 font-semibold capitalize">
                        {dim.replace('d_', '').replace('_', ' ')}
                      </span>
                      <span
                        className={`text-xs font-bold ${
                          Math.abs(zScore) > 1.8
                            ? 'text-amber-400'
                            : 'text-slate-300'
                        }`}
                      >
                        {zScore > 0 ? '+' : ''}
                        {zScore.toFixed(2)}σ
                      </span>
                    </div>

                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          zScore >= 0 ? 'bg-amber-400' : 'bg-slate-500'
                        }`}
                        style={{
                          width: `${Math.min(Math.abs(zScore) * 30, 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}

                <div className="pt-2 flex items-center justify-between text-xs text-slate-400 border-t border-slate-800">
                  <span>Composite Deviation Magnitude:</span>
                  <span className="text-amber-400 font-bold">
                    {comparison.composite_magnitude.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            {/* Dynamic State Recalibration (Closed Loop Learning) */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-4">
              <div>
                <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider font-mono">
                  Dynamic State Recalibration (Learning)
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Operator EWMA skill state before vs after incorporating this new actual task telemetry.
                </p>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-slate-400">Composite Skill Score</span>
                  <div className="flex items-center gap-2 font-mono">
                    <span className="text-slate-400">
                      {comparison.state_before.composite_score.toFixed(1)}
                    </span>
                    <span className="text-slate-600">⟶</span>
                    <span className="text-lg font-bold text-amber-400">
                      {comparison.state_after.composite_score.toFixed(1)}
                    </span>
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded font-bold ${
                        comparison.composite_score_delta >= 0
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-rose-500/10 text-rose-400'
                      }`}
                    >
                      {comparison.composite_score_delta >= 0 ? '+' : ''}
                      {comparison.composite_score_delta.toFixed(2)} pts
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs font-mono pt-2 border-t border-slate-900">
                  <span className="text-slate-400">Derived Performance Tier</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400">{comparison.state_before.derived_label}</span>
                    <span className="text-slate-600">⟶</span>
                    <span className="text-slate-200 font-bold">{comparison.state_after.derived_label}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs font-mono pt-2 border-t border-slate-900">
                  <span className="text-slate-400">Sample Count & Confidence</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-300">
                      {comparison.state_after.sample_count} tasks
                    </span>
                    <span className="text-amber-400">
                      ({(comparison.state_after.confidence * 100).toFixed(0)}% confidence)
                    </span>
                  </div>
                </div>
              </div>

              {/* Safety Compliance & Incidents */}
              <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl space-y-2">
                <span className="text-xs font-mono text-slate-400 uppercase tracking-wider block">
                  Safety Compliance in Actual Run
                </span>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Seatbelt Compliance:</span>
                  <span
                    className={`font-semibold ${
                      comparison.seatbelt_engaged ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {comparison.seatbelt_engaged ? 'Engaged (Compliant)' : 'Unengaged (Violation)'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Min Proximity Distance:</span>
                  <span className="text-slate-200 font-semibold">
                    {comparison.min_proximity_distance.toFixed(1)} meters
                  </span>
                </div>

                {comparison.incidents_recorded.length > 0 && (
                  <div className="pt-2 border-t border-slate-900 space-y-1">
                    <span className="text-[11px] font-mono text-rose-400 font-bold block">
                      ⚠ Incident Recorded by IncidentService:
                    </span>
                    {comparison.incidents_recorded.map((inc) => (
                      <div
                        key={inc.id}
                        className="text-[11px] font-mono text-slate-300 bg-rose-950/30 border border-rose-800/40 p-2 rounded"
                      >
                        <span className="font-bold text-rose-300 uppercase">{inc.source}</span> —{' '}
                        {inc.description || 'Safety threshold excursion'}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── Step 5: Close the Loop CTA Banner ── */}
          <div className="bg-gradient-to-r from-amber-500/10 via-slate-900 to-slate-900 border border-amber-500/30 p-4 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded font-black bg-emerald-400 text-slate-950 uppercase">
                  Step 5: LEARN
                </span>
                <span className="text-xs font-mono text-slate-300 font-semibold">
                  Operator State Recalibrated via Recency-Weighted EWMA
                </span>
              </div>
              <p className="text-xs text-slate-400 max-w-2xl mt-0.5">
                The decision loop is complete. Observed deviations have updated the operator's dynamic profile.
                Explore targeted CAT E-Learning pathways or reserve 1-on-1 certified instructor coaching sessions.
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => navigate('/coaching')}
                className="px-4 py-2 bg-gradient-to-r from-amber-400 to-amber-500 hover:brightness-110 text-slate-950 font-bold text-xs rounded-lg shadow-md transition-all flex items-center gap-1.5"
              >
                <span>View Targeted Coaching &rarr;</span>
              </button>
              <button
                onClick={() => navigate('/simulate')}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium text-xs rounded-lg transition-colors"
              >
                Simulate Another Task
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Completed Simulation Executions History ── */}
      <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
        <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider font-mono mb-1">
          Recent Completed Simulation Comparisons
        </h3>
        <p className="text-xs text-slate-400 mb-4">
          History of simulated tasks that have executed Process B actual outcomes. Click to inspect full closed-loop comparison.
        </p>

        {historyLoading && (
          <div className="text-xs font-mono text-slate-500 py-4">Loading simulation history...</div>
        )}

        {historyData && historyData.comparisons.length === 0 && (
          <div className="text-xs text-slate-400 py-4">
            No simulation comparisons recorded yet. Run a What-If simulation and trigger Process B execution to populate.
          </div>
        )}

        {historyData && historyData.comparisons.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-2">Pred ID</th>
                  <th className="pb-2">Operator</th>
                  <th className="pb-2">Task</th>
                  <th className="pb-2">Weather</th>
                  <th className="pb-2 text-right">Predicted</th>
                  <th className="pb-2 text-right">Actual</th>
                  <th className="pb-2 text-right">Difference</th>
                  <th className="pb-2 text-center">Interval</th>
                  <th className="pb-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {historyData.comparisons.map((item) => (
                  <tr
                    key={item.prediction_id}
                    className={`hover:bg-slate-800/30 transition-colors ${
                      item.prediction_id === activePredictionId ? 'bg-amber-400/5' : ''
                    }`}
                  >
                    <td className="py-2.5 text-slate-400">#{item.prediction_id}</td>
                    <td className="py-2.5 font-semibold text-slate-200">{item.operator_name}</td>
                    <td className="py-2.5 text-slate-300">{item.task_type_name}</td>
                    <td className="py-2.5 text-amber-400/90">{item.weather}</td>
                    <td className="py-2.5 text-right text-slate-300">
                      {item.predicted_duration_minutes.toFixed(1)}m
                    </td>
                    <td className="py-2.5 text-right font-bold text-slate-100">
                      {item.actual_duration_minutes.toFixed(1)}m
                    </td>
                    <td
                      className={`py-2.5 text-right font-bold ${
                        item.duration_difference_minutes > 0 ? 'text-rose-400' : 'text-emerald-400'
                      }`}
                    >
                      {item.duration_difference_minutes > 0 ? '+' : ''}
                      {item.duration_difference_minutes.toFixed(1)}m
                    </td>
                    <td className="py-2.5 text-center">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                          item.is_within_interval
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : 'bg-rose-500/10 text-rose-400'
                        }`}
                      >
                        {item.is_within_interval ? 'INSIDE' : 'OUTSIDE'}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      <button
                        onClick={() => {
                          setActivePredictionId(item.prediction_id);
                          navigate(`/compare/${item.prediction_id}`);
                        }}
                        className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-medium border border-slate-700 transition-colors"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
