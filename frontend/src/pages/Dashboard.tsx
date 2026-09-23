import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  fetchDailyTasks,
  fetchOperators,
  fetchIncidents,
  fetchIncidentStats,
  createIncident,
  IncidentSeverity,
  IncidentSource,
} from '../api/client';

export const Dashboard: React.FC = () => {
  const queryClient = useQueryClient();
  const [taskLimit, setTaskLimit] = useState(20);

  // Safety Incident Feed Filters
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  // Manual Incident Modal State
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [reportOperatorId, setReportOperatorId] = useState<number>(1);
  const [reportSeverity, setReportSeverity] = useState<IncidentSeverity>('medium');
  const [reportSource, setReportSource] = useState<IncidentSource>('manual');
  const [reportDescription, setReportDescription] = useState('');
  const [reportError, setReportError] = useState<string | null>(null);

  // Queries
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

  const { data: incidentData, isLoading: isIncidentsLoading } = useQuery({
    queryKey: ['incidents', sourceFilter, severityFilter],
    queryFn: () =>
      fetchIncidents({
        source: sourceFilter !== 'all' ? sourceFilter : undefined,
        severity: severityFilter !== 'all' ? severityFilter : undefined,
        limit: 15,
      }),
  });

  const { data: incidentStats } = useQuery({
    queryKey: ['incidentStats'],
    queryFn: fetchIncidentStats,
  });

  // Manual incident creation mutation
  const createIncidentMutation = useMutation({
    mutationFn: createIncident,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['incidentStats'] });
      setIsReportModalOpen(false);
      setReportDescription('');
      setReportError(null);
    },
    onError: (err: any) => {
      setReportError(err?.response?.data?.detail || 'Failed to record manual incident.');
    },
  });

  const handleSubmitManualIncident = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportDescription.trim()) {
      setReportError('Description is required.');
      return;
    }
    createIncidentMutation.mutate({
      operator_id: reportOperatorId,
      source: reportSource,
      severity: reportSeverity,
      description: reportDescription.trim(),
    });
  };

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
  const incidents = incidentData?.incidents || [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <span>Operations & Safety Dashboard</span>
            <span className="text-xs font-mono uppercase bg-slate-800 text-amber-400 px-2 py-0.5 rounded border border-slate-700">
              Live Feed
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time daily task execution, machine telemetry, and unified site safety compliance
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsReportModalOpen(true)}
            className="px-3 py-1.5 bg-rose-500 hover:bg-rose-400 text-slate-950 font-bold text-xs rounded-lg transition-colors shadow-sm flex items-center gap-1.5"
          >
            <span>+ Log Safety Incident</span>
          </button>
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
          <div className="text-xs text-slate-400 font-medium flex justify-between">
            <span>Total Logged Incidents</span>
            <span className="text-rose-400 font-bold">{incidentStats?.total_incidents || compliance?.safety_violations_count || 0}</span>
          </div>
          <div className="text-2xl font-bold text-rose-400 mt-1">
            {incidentStats?.total_incidents || compliance?.safety_violations_count || 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Crit: {incidentStats?.by_severity?.critical || 0} | High: {incidentStats?.by_severity?.high || 0} | Med: {incidentStats?.by_severity?.medium || 0}
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

      {/* Unified Safety Incident Feed (§2, §13, §F) */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
                Unified Safety Incident Feed
              </h2>
              <span className="bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] px-2 py-0.5 rounded-full font-mono font-bold">
                {incidentData?.total_count || 0} Events
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Deterministic rule engine detections (seatbelt &amp; proximity) and supervisor logs
            </p>
          </div>

          {/* Filter Chips */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-[11px]">
              <span className="text-slate-500 px-1 font-medium">Source:</span>
              {['all', 'seatbelt', 'proximity', 'manual'].map((src) => (
                <button
                  key={src}
                  onClick={() => setSourceFilter(src)}
                  className={`px-2 py-0.5 rounded capitalize transition-colors ${
                    sourceFilter === src
                      ? 'bg-amber-500 text-slate-950 font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {src}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-[11px]">
              <span className="text-slate-500 px-1 font-medium">Severity:</span>
              {['all', 'critical', 'high', 'medium', 'low'].map((sev) => (
                <button
                  key={sev}
                  onClick={() => setSeverityFilter(sev)}
                  className={`px-2 py-0.5 rounded capitalize transition-colors ${
                    severityFilter === sev
                      ? 'bg-rose-500 text-white font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {sev}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Incident List */}
        {isIncidentsLoading ? (
          <div className="py-8 text-center text-slate-500 text-xs">Loading safety incidents...</div>
        ) : incidents.length === 0 ? (
          <div className="py-8 text-center text-slate-500 text-xs bg-slate-950/40 rounded-lg border border-slate-800/60">
            No safety incidents match the selected filter criteria.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[380px] overflow-y-auto pr-1">
            {incidents.map((inc) => (
              <div
                key={inc.id}
                className={`p-3 rounded-lg border transition-all text-xs flex flex-col justify-between ${
                  inc.severity === 'critical'
                    ? 'bg-rose-950/20 border-rose-600/40 text-rose-200'
                    : inc.severity === 'high'
                    ? 'bg-orange-950/20 border-orange-600/40 text-orange-200'
                    : inc.severity === 'medium'
                    ? 'bg-amber-950/20 border-amber-600/40 text-amber-200'
                    : 'bg-slate-950/40 border-slate-800 text-slate-300'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span
                      className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded font-bold border ${
                        inc.source === 'seatbelt'
                          ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                          : inc.source === 'proximity'
                          ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                          : 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                      }`}
                    >
                      {inc.source === 'seatbelt' && '⛑ Seatbelt'}
                      {inc.source === 'proximity' && '⚠️ Proximity'}
                      {inc.source === 'manual' && '📝 Manual Report'}
                      {inc.source === 'deviation_anomaly' && '⚡ Anomaly'}
                    </span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                        inc.severity === 'critical'
                          ? 'bg-rose-600 text-white animate-pulse'
                          : inc.severity === 'high'
                          ? 'bg-rose-500/30 text-rose-300'
                          : inc.severity === 'medium'
                          ? 'bg-amber-500/30 text-amber-300'
                          : 'bg-slate-700 text-slate-300'
                      }`}
                    >
                      {inc.severity}
                    </span>
                  </div>

                  <p className="text-slate-200 text-[11px] leading-relaxed line-clamp-2 mt-1">
                    {inc.description || 'Safety incident registered.'}
                  </p>
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-400 border-t border-slate-800/80 pt-2 mt-2">
                  <Link
                    to={`/operators/${inc.operator_id}`}
                    className="text-amber-400 hover:underline font-semibold"
                  >
                    {inc.operator_name}
                  </Link>
                  <div className="flex items-center gap-1.5 font-mono text-[9px] text-slate-500">
                    {inc.machine_name && <span>{inc.machine_name}</span>}
                    <span>•</span>
                    <span>{new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
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

      {/* Manual Incident Report Modal */}
      {isReportModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 shadow-2xl relative">
            <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
              <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <span>⚠️</span>
                <span>Log Safety Incident</span>
              </h3>
              <button
                onClick={() => setIsReportModalOpen(false)}
                className="text-slate-400 hover:text-slate-200 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            {reportError && (
              <div className="mb-4 p-2.5 bg-rose-500/20 border border-rose-500/40 rounded text-rose-300 text-xs">
                {reportError}
              </div>
            )}

            <form onSubmit={handleSubmitManualIncident} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Involved Operator</label>
                <select
                  value={reportOperatorId}
                  onChange={(e) => setReportOperatorId(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-400"
                >
                  {operators?.map((op) => (
                    <option key={op.id} value={op.id}>
                      {op.name} ({op.derived_label})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">Source Category</label>
                  <select
                    value={reportSource}
                    onChange={(e) => setReportSource(e.target.value as IncidentSource)}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-400"
                  >
                    <option value="manual">Manual Supervisor Log</option>
                    <option value="seatbelt">Seatbelt Violation</option>
                    <option value="proximity">Proximity Hazard</option>
                    <option value="deviation_anomaly">Telemetry Anomaly</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Severity</label>
                  <select
                    value={reportSeverity}
                    onChange={(e) => setReportSeverity(e.target.value as IncidentSeverity)}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-400"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Incident Description</label>
                <textarea
                  rows={3}
                  value={reportDescription}
                  onChange={(e) => setReportDescription(e.target.value)}
                  placeholder="Detail the observation or safety hazard observed..."
                  className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-400"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsReportModalOpen(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createIncidentMutation.isPending}
                  className="px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded transition-colors shadow-sm disabled:opacity-50"
                >
                  {createIncidentMutation.isPending ? 'Logging...' : 'Submit Incident Event'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
