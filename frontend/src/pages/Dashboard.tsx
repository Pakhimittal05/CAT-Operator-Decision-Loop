import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchDailyTasks, fetchOperators } from '../api/client';

export const Dashboard: React.FC = () => {
  const [taskLimit, setTaskLimit] = useState(20);

  const {
    data: dashboardData,
    isLoading: isTasksLoading,
    error: tasksError,
  } = useQuery({
    queryKey: ['dailyTasks', taskLimit],
    queryFn: () => fetchDailyTasks(taskLimit),
  });

  const { data: operators, isLoading: isOpsLoading } = useQuery({
    queryKey: ['operators'],
    queryFn: fetchOperators,
  });

  if (isTasksLoading || isOpsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-amber-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Loading dashboard telemetry and daily tasks...</p>
        </div>
      </div>
    );
  }

  if (tasksError) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center my-8">
        <h3 className="text-red-400 font-semibold mb-1">Failed to connect to backend API</h3>
        <p className="text-slate-400 text-xs mb-3">Ensure FastAPI is running on http://localhost:8000</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-1.5 bg-red-500/20 text-red-300 text-xs rounded hover:bg-red-500/30 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const compliance = dashboardData?.compliance;
  const tasks = dashboardData?.tasks || [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <span>Operations Dashboard</span>
            <span className="text-xs font-mono uppercase bg-slate-800 text-amber-400 px-2 py-0.5 rounded border border-slate-700">
              Live Feed
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time daily task execution, machine telemetry, and site safety compliance
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/operators/1"
            className="px-3 py-1.5 bg-amber-500 text-slate-950 font-semibold text-xs rounded-lg hover:bg-amber-400 transition-colors shadow-sm flex items-center gap-1.5"
          >
            <span>View Operator Profiles</span>
            <span>&rarr;</span>
          </Link>
        </div>
      </div>

      {/* Safety Compliance & KPI Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400 font-medium">Recent Tasks Analyzed</div>
          <div className="text-2xl font-bold text-slate-100 mt-1">{compliance?.total_tasks || 0}</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Database total: {dashboardData?.total_count.toLocaleString()} tasks
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400 font-medium flex justify-between">
            <span>Seatbelt Compliance</span>
            <span className="text-emerald-400 font-bold">{compliance?.seatbelt_compliance_pct}%</span>
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">
            {compliance?.seatbelt_compliance_pct}%
          </div>
          <div className="w-full bg-slate-800 h-2 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-emerald-500 h-full rounded-full transition-all"
              style={{ width: `${compliance?.seatbelt_compliance_pct || 0}%` }}
            />
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400 font-medium flex justify-between">
            <span>Proximity Safe Buffer</span>
            <span className="text-amber-400 font-bold">{compliance?.proximity_safe_pct}%</span>
          </div>
          <div className="text-2xl font-bold text-amber-400 mt-1">
            {compliance?.proximity_safe_pct}%
          </div>
          <div className="w-full bg-slate-800 h-2 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-amber-400 h-full rounded-full transition-all"
              style={{ width: `${compliance?.proximity_safe_pct || 0}%` }}
            />
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-400 font-medium">Safety Violations Logged</div>
          <div className="text-2xl font-bold text-rose-400 mt-1">
            {compliance?.safety_violations_count || 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Seatbelt unlatched or proximity &lt; 5.0m
          </div>
        </div>
      </div>

      {/* Operator Quick Roster */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-200">Active Operators (Dynamic State Roster)</h2>
          <span className="text-xs text-slate-500">Showing top active operators</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
          {operators?.slice(0, 6).map((op) => (
            <Link
              key={op.id}
              to={`/operators/${op.id}`}
              className="p-3 bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 rounded-lg transition-all group"
            >
              <div className="text-xs font-semibold text-slate-200 group-hover:text-amber-300 transition-colors truncate">
                {op.name}
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-lg font-bold text-amber-400 font-mono">
                  {Math.round(op.composite_score)}
                </span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                    op.derived_label === 'Expert'
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : op.derived_label === 'Intermediate'
                      ? 'bg-amber-500/20 text-amber-300'
                      : 'bg-rose-500/20 text-rose-300'
                  }`}
                >
                  {op.derived_label}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Daily Tasks Feed Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">Recent Completed Tasks</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Show:</span>
            <select
              value={taskLimit}
              onChange={(e) => setTaskLimit(Number(e.target.value))}
              className="bg-slate-800 text-slate-200 border border-slate-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-amber-400"
            >
              <option value={10}>10 tasks</option>
              <option value={20}>20 tasks</option>
              <option value={50}>50 tasks</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Task ID</th>
                <th className="py-2.5 px-3">Operator</th>
                <th className="py-2.5 px-3">Machine</th>
                <th className="py-2.5 px-3">Task Type</th>
                <th className="py-2.5 px-3">Weather</th>
                <th className="py-2.5 px-3">Duration</th>
                <th className="py-2.5 px-3">Idle Time</th>
                <th className="py-2.5 px-3">Efficiency</th>
                <th className="py-2.5 px-3">Seatbelt</th>
                <th className="py-2.5 px-3">Proximity</th>
                <th className="py-2.5 px-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
              {tasks.map((t) => (
                <tr key={t.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-2 px-3 text-slate-400 font-semibold">#{t.id}</td>
                  <td className="py-2 px-3 text-slate-200 font-sans">
                    <Link
                      to={`/operators/${t.operator_id}`}
                      className="text-amber-400 hover:underline font-medium"
                    >
                      {t.operator_name}
                    </Link>
                  </td>
                  <td className="py-2 px-3 text-slate-300">{t.machine_name}</td>
                  <td className="py-2 px-3 text-slate-300 font-sans">{t.task_type}</td>
                  <td className="py-2 px-3 text-slate-400 capitalize font-sans">{t.weather}</td>
                  <td className="py-2 px-3 text-slate-200">{t.duration_minutes.toFixed(1)}m</td>
                  <td className="py-2 px-3 text-slate-400">{Math.round(t.idle_seconds)}s</td>
                  <td className="py-2 px-3 text-amber-300">{(t.efficiency_score * 100).toFixed(1)}%</td>
                  <td className="py-2 px-3">
                    {t.seatbelt_engaged ? (
                      <span className="text-emerald-400 font-bold">&#x2713; Engaged</span>
                    ) : (
                      <span className="text-rose-400 font-bold">&#x26A0; UNLATCHED</span>
                    )}
                  </td>
                  <td className="py-2 px-3">
                    <span
                      className={
                        t.min_proximity_distance < 5.0 ? 'text-rose-400 font-bold' : 'text-slate-300'
                      }
                    >
                      {t.min_proximity_distance.toFixed(1)}m
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    <span className="bg-emerald-500/20 text-emerald-300 text-[10px] px-1.5 py-0.5 rounded font-sans">
                      {t.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
