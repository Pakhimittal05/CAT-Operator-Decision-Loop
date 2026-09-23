import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchAnomalies,
  fetchTrainingRecommendations,
  fetchElearningModules,
  fetchInstructorSlots,
  fetchOperatorBookings,
  createInstructorBooking,
  fetchOperators,
  AnomalyItem,
  InstructorSlot,
} from '../api/client';

export const AnomalyFeed: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedOperatorId, setSelectedOperatorId] = useState<number>(1);
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [selectedSlot, setSelectedSlot] = useState<InstructorSlot | null>(null);
  const [coachingTopic, setCoachingTopic] = useState<string>('Hydraulic Modulation & Pass Pacing');
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookingSuccess, setBookingSuccess] = useState<string | null>(null);

  // Queries
  const { data: operators = [] } = useQuery({
    queryKey: ['operators'],
    queryFn: fetchOperators,
  });

  const { data: anomalyData, isLoading: loadingAnomalies } = useQuery({
    queryKey: ['anomalies', selectedOperatorId, severityFilter],
    queryFn: () =>
      fetchAnomalies({
        operator_id: selectedOperatorId > 0 ? selectedOperatorId : undefined,
        severity: severityFilter !== 'all' ? severityFilter : undefined,
        limit: 50,
      }),
  });

  const { data: recommendations = [], isLoading: loadingRecs } = useQuery({
    queryKey: ['training-recommendations', selectedOperatorId],
    queryFn: () => fetchTrainingRecommendations(selectedOperatorId),
    enabled: selectedOperatorId > 0,
  });

  const { data: modules = [] } = useQuery({
    queryKey: ['elearning-modules'],
    queryFn: fetchElearningModules,
  });

  const { data: slots = [], isLoading: loadingSlots } = useQuery({
    queryKey: ['instructor-slots'],
    queryFn: () => fetchInstructorSlots(true),
  });

  const { data: bookings = [] } = useQuery({
    queryKey: ['operator-bookings', selectedOperatorId],
    queryFn: () => fetchOperatorBookings(selectedOperatorId),
    enabled: selectedOperatorId > 0,
  });

  // Booking Mutation
  const bookingMutation = useMutation({
    mutationFn: createInstructorBooking,
    onSuccess: (data) => {
      setBookingSuccess(
        `Session confirmed with ${data.instructor_name} on ${data.slot_date} at ${data.start_time}!`
      );
      setBookingError(null);
      setSelectedSlot(null);
      queryClient.invalidateQueries({ queryKey: ['instructor-slots'] });
      queryClient.invalidateQueries({ queryKey: ['operator-bookings', selectedOperatorId] });
      queryClient.invalidateQueries({ queryKey: ['training-recommendations', selectedOperatorId] });
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail || 'Booking request failed.';
      setBookingError(detail);
      setBookingSuccess(null);
    },
  });

  const handleBookSlot = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSlot || !selectedOperatorId) return;
    setBookingError(null);
    setBookingSuccess(null);
    bookingMutation.mutate({
      operator_id: selectedOperatorId,
      instructor_slot_id: selectedSlot.id,
      topic: coachingTopic,
    });
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      case 'high':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      default:
        return 'bg-blue-500/20 text-blue-300 border-blue-500/40';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="bg-amber-400 text-slate-950 text-xs font-black px-2 py-0.5 rounded tracking-wide">
              PHASE 6
            </span>
            <h1 className="text-xl font-bold text-slate-100 tracking-tight">
              Anomaly Stream, Coaching & Training Hub
            </h1>
          </div>
          <p className="text-xs text-slate-400 max-w-2xl">
            Statistical deviation anomaly detection powered by shared reference models. Explanations
            are strictly framed as non-causal <strong className="text-slate-200">Probable Contributing Factors</strong>, mapped to targeted CAT E-Learning pathways and 1-on-1 instructor sessions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div>
            <label className="block text-[10px] text-slate-400 uppercase tracking-wider mb-1">
              Select Operator
            </label>
            <select
              value={selectedOperatorId}
              onChange={(e) => setSelectedOperatorId(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-amber-400"
            >
              {operators.map((op) => (
                <option key={op.id} value={op.id}>
                  #{op.id} — {op.name} ({op.derived_label})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] text-slate-400 uppercase tracking-wider mb-1">
              Severity Filter
            </label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-amber-400"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
            </select>
          </div>
        </div>
      </div>

      {/* KPI Metrics Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <div className="text-[11px] text-slate-400 uppercase tracking-wider">
            Detected Anomaly Events
          </div>
          <div className="text-2xl font-black text-amber-400 mt-1">
            {anomalyData?.total_count ?? 0}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Statistical outliers ($\ge 2.0\sigma$ or $|z| \ge 2.5\sigma$)
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <div className="text-[11px] text-slate-400 uppercase tracking-wider">
            Active Skill-Gap Recommendations
          </div>
          <div className="text-2xl font-black text-blue-400 mt-1">
            {recommendations.length}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Dimensions score &lt; 50 in operator dynamic EWMA
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <div className="text-[11px] text-slate-400 uppercase tracking-wider">
            Certified Instructor Slots Open
          </div>
          <div className="text-2xl font-black text-emerald-400 mt-1">
            {slots.length}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Available 1-on-1 coaching reservations
          </div>
        </div>
      </div>

      {/* Feedback Banners */}
      {bookingSuccess && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs rounded-lg flex items-center justify-between">
          <span>{bookingSuccess}</span>
          <button
            onClick={() => setBookingSuccess(null)}
            className="text-emerald-400 hover:text-emerald-200"
          >
            ✕
          </button>
        </div>
      )}
      {bookingError && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs rounded-lg flex items-center justify-between">
          <span>{bookingError}</span>
          <button
            onClick={() => setBookingError(null)}
            className="text-rose-400 hover:text-rose-200"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Grid: Left = Anomalies, Right = Training & Booking */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Anomaly Feed (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              Performance Deviation Anomaly Stream
            </h2>
            <span className="text-[11px] text-slate-400">
              Showing {anomalyData?.anomalies.length ?? 0} events
            </span>
          </div>

          {loadingAnomalies ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              Loading statistical anomaly evaluations...
            </div>
          ) : anomalyData?.anomalies.length === 0 ? (
            <div className="bg-slate-900/50 border border-slate-800 p-8 rounded-xl text-center text-slate-400 text-xs">
              No performance anomalies recorded matching this filter. Normal variance envelope maintained.
            </div>
          ) : (
            <div className="space-y-4">
              {anomalyData?.anomalies.map((anomaly: AnomalyItem) => (
                <div
                  key={anomaly.id ?? anomaly.task_instance_id}
                  className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-md hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${getSeverityBadge(
                          anomaly.severity
                        )}`}
                      >
                        {anomaly.severity}
                      </span>
                      <span className="text-xs font-semibold text-slate-200">
                        Task #{anomaly.task_instance_id}
                      </span>
                      <span className="text-xs text-slate-400">
                        • {anomaly.operator_name}
                      </span>
                      {anomaly.machine_name && (
                        <span className="text-xs text-slate-500">
                          ({anomaly.machine_name})
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] font-mono text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20">
                      Mag: {anomaly.composite_magnitude.toFixed(2)}σ
                    </div>
                  </div>

                  <p className="text-xs text-slate-300 mb-3 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
                    {anomaly.observed_pattern}
                  </p>

                  {/* Probable Contributing Factors Breakdown */}
                  {anomaly.probable_factors && anomaly.probable_factors.length > 0 && (
                    <div className="space-y-2 pt-1 border-t border-slate-800/60">
                      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                        Ranked Probable Contributing Factors (Non-Causal Evidence):
                      </div>
                      <div className="space-y-1.5">
                        {anomaly.probable_factors.map((f, idx) => (
                          <div
                            key={idx}
                            className="bg-slate-950/40 p-2 rounded border border-slate-800/40 text-xs"
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-medium text-slate-300">
                                {f.dimension.replace('_', ' ').toUpperCase()}
                              </span>
                              <div className="flex items-center gap-2">
                                <span
                                  className={`text-[11px] font-mono px-1.5 py-0.2 rounded ${
                                    f.z_score >= 0
                                      ? 'text-amber-400 bg-amber-400/10'
                                      : 'text-blue-400 bg-blue-400/10'
                                  }`}
                                >
                                  {f.z_score >= 0 ? `+${f.z_score.toFixed(2)}σ` : `${f.z_score.toFixed(2)}σ`}
                                </span>
                                <span className="text-[10px] text-slate-400 font-mono">
                                  {f.contribution_weight_pct.toFixed(1)}% weight
                                </span>
                              </div>
                            </div>
                            {/* Weight Bar */}
                            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mb-1">
                              <div
                                className="bg-amber-400 h-full rounded-full"
                                style={{ width: `${Math.min(100, f.contribution_weight_pct)}%` }}
                              />
                            </div>
                            <div className="text-[11px] text-slate-400 italic">
                              {f.description}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Coaching Recommendations & Instructor Booking (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Skill-Gap E-Learning Pathways */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-400" />
                Targeted E-Learning Pathways
              </h2>
              <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                EWMA &lt; 50
              </span>
            </div>

            {loadingRecs ? (
              <div className="text-xs text-slate-400 py-4 text-center">
                Evaluating skill gap criteria...
              </div>
            ) : recommendations.length === 0 ? (
              <div className="space-y-3">
                <div className="p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-lg text-xs text-emerald-400">
                  ✓ No active skill deficits detected in operator state. All performance dimensions operate above baseline threshold (50.0).
                </div>
                <div className="text-[11px] text-slate-400 font-medium pt-1">
                  General E-Learning Enrichment Catalog ({modules.length} courses):
                </div>
                {modules.map((mod) => (
                  <div key={mod.id} className="p-2.5 bg-slate-950/40 border border-slate-800 rounded-lg text-xs flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-slate-200">{mod.name}</div>
                      <div className="text-[11px] text-slate-400">⏱ {mod.duration_minutes}m self-paced</div>
                    </div>
                    <a href={mod.content_url || '#'} target="_blank" rel="noreferrer" className="text-amber-400 hover:underline text-[11px]">
                      View →
                    </a>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {recommendations.map((rec) => (
                  <div
                    key={rec.id}
                    className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wide bg-blue-500/20 text-blue-300 border border-blue-500/30 px-2 py-0.5 rounded">
                        {rec.dimension.replace('_', ' ')}
                      </span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                          rec.status === 'in_progress'
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {rec.status.toUpperCase()}
                      </span>
                    </div>

                    <div className="text-xs font-semibold text-slate-200">
                      {rec.elearning_module?.name || `${rec.dimension} Refresher`}
                    </div>

                    <p className="text-[11px] text-slate-400">{rec.reason}</p>

                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/80 text-[11px]">
                      <span className="text-slate-500 font-mono">
                        ⏱ {rec.elearning_module?.duration_minutes ?? 30} mins self-paced
                      </span>
                      <a
                        href={rec.elearning_module?.content_url || '#'}
                        target="_blank"
                        rel="noreferrer"
                        className="text-amber-400 hover:text-amber-300 font-semibold hover:underline"
                      >
                        Open Course →
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 1-on-1 Certified Instructor Booking */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                1-on-1 Instructor Coaching
              </h2>
              <span className="text-[11px] text-slate-400 font-mono">
                {slots.length} open slots
              </span>
            </div>

            {loadingSlots ? (
              <div className="text-xs text-slate-400 py-4 text-center">
                Checking coach schedules...
              </div>
            ) : slots.length === 0 ? (
              <div className="text-xs text-slate-400 p-4 bg-slate-950 rounded-lg text-center">
                No slots currently open. Check back for next week's schedule.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
                {slots.map((s) => (
                  <div
                    key={s.id}
                    onClick={() => setSelectedSlot(s)}
                    className={`p-3 rounded-lg border text-xs cursor-pointer transition-colors ${
                      selectedSlot?.id === s.id
                        ? 'bg-amber-500/10 border-amber-400 text-slate-100'
                        : 'bg-slate-950/60 border-slate-800 hover:border-slate-700 text-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between font-semibold">
                      <span className="text-amber-300">{s.instructor_name}</span>
                      <span className="text-slate-400 font-mono text-[11px]">{s.slot_date}</span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between">
                      <span>
                        Time: {s.start_time} – {s.end_time}
                      </span>
                      <span className="text-emerald-400 font-medium">Click to select</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Booking Form (when slot selected) */}
            {selectedSlot && (
              <form
                onSubmit={handleBookSlot}
                className="p-3.5 bg-slate-950 border border-amber-400/40 rounded-lg space-y-3"
              >
                <div className="text-xs font-bold text-amber-300">
                  Book Slot with {selectedSlot.instructor_name}
                </div>
                <div className="text-[11px] text-slate-400">
                  Date: <strong className="text-slate-200">{selectedSlot.slot_date}</strong> ({selectedSlot.start_time} – {selectedSlot.end_time})
                </div>

                <div>
                  <label className="block text-[10px] text-slate-400 uppercase tracking-wider mb-1">
                    Coaching Focus Topic
                  </label>
                  <input
                    type="text"
                    value={coachingTopic}
                    onChange={(e) => setCoachingTopic(e.target.value)}
                    required
                    className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-amber-400"
                  />
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <button
                    type="submit"
                    disabled={bookingMutation.isPending}
                    className="flex-1 bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs py-2 px-3 rounded shadow transition-colors disabled:opacity-50"
                  >
                    {bookingMutation.isPending ? 'Reserving...' : 'Confirm Reservation'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedSlot(null)}
                    className="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-2 px-3 rounded transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            {/* Operator's Confirmed Bookings */}
            {bookings.length > 0 && (
              <div className="pt-2 border-t border-slate-800 space-y-2">
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                  Confirmed Coaching Sessions for Selected Operator:
                </div>
                <div className="space-y-1.5">
                  {bookings.map((b) => (
                    <div
                      key={b.id}
                      className="p-2.5 bg-emerald-500/5 border border-emerald-500/20 rounded text-xs text-slate-300 flex items-center justify-between"
                    >
                      <div>
                        <div className="font-semibold text-emerald-400">{b.topic}</div>
                        <div className="text-[11px] text-slate-400">
                          {b.instructor_name} • {b.slot_date} ({b.start_time} - {b.end_time})
                        </div>
                      </div>
                      <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30 uppercase">
                        {b.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
