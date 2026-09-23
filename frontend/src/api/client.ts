import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface OperatorSummary {
  id: number;
  name: string;
  legacy_skill_tier: string;
  composite_score: number;
  derived_label: 'Expert' | 'Intermediate' | 'Beginner';
  trend_direction: 'improving' | 'stable' | 'declining';
  confidence: number;
  sample_count: number;
  is_synthetic: boolean;
}

export interface OperatorStateResponse {
  operator_id: number;
  task_type_id: number | null;
  efficiency_score: number;
  idling_score: number;
  duration_score: number;
  load_cycle_score: number;
  safety_score: number;
  composite_score: number;
  trend_direction: 'improving' | 'stable' | 'declining';
  confidence: number;
  derived_label: 'Expert' | 'Intermediate' | 'Beginner';
  sample_count: number;
  is_synthetic: boolean;
}

export interface TaskHistoryItem {
  task_instance_id: number;
  task_type: string;
  machine_name: string;
  weather: string;
  completed_at: string;
  duration_minutes: number;
  idle_seconds: number;
  load_cycles: number;
  efficiency_score: number;
  seatbelt_engaged: boolean;
  min_proximity_distance: number;
  d_cycle_efficiency: number;
  d_idling: number;
  d_duration: number;
  d_load_cycle: number;
  d_safety: number;
  composite_magnitude: number;
  is_synthetic: boolean;
}

export interface OperatorHistoryResponse {
  operator_id: number;
  operator_name: string;
  total_tasks: number;
  history: TaskHistoryItem[];
  is_synthetic: boolean;
}

export interface DailyTaskItem {
  id: number;
  operator_id: number;
  operator_name: string;
  machine_name: string;
  task_type: string;
  weather: string;
  completed_at: string;
  duration_minutes: number;
  idle_seconds: number;
  load_cycles: number;
  efficiency_score: number;
  seatbelt_engaged: boolean;
  min_proximity_distance: number;
  status: string;
  is_synthetic: boolean;
}

export interface SafetyComplianceSummary {
  total_tasks: number;
  seatbelt_compliance_pct: number;
  proximity_safe_pct: number;
  safety_violations_count: number;
  is_synthetic: boolean;
}

export interface DashboardDailyTasksResponse {
  tasks: DailyTaskItem[];
  compliance: SafetyComplianceSummary;
  total_count: number;
  is_synthetic: boolean;
}

export const fetchOperators = async (): Promise<OperatorSummary[]> => {
  const { data } = await apiClient.get<OperatorSummary[]>('/operators');
  return data;
};

export const fetchOperatorState = async (id: number): Promise<OperatorStateResponse> => {
  const { data } = await apiClient.get<OperatorStateResponse>(`/operators/${id}/state`);
  return data;
};

export const fetchOperatorHistory = async (id: number, limit = 20): Promise<OperatorHistoryResponse> => {
  const { data } = await apiClient.get<OperatorHistoryResponse>(`/operators/${id}/history`, {
    params: { limit },
  });
  return data;
};

export const fetchDailyTasks = async (limit = 25): Promise<DashboardDailyTasksResponse> => {
  const { data } = await apiClient.get<DashboardDailyTasksResponse>('/dashboard/daily-tasks', {
    params: { limit },
  });
  return data;
};

// ── What-If Simulation (§12, §24) ──────────────────────────────────────────

export interface ContributingFactor {
  factor_name: string;
  impact_direction: 'increases_duration' | 'decreases_duration';
  impact_percentage: number;
  confidence: number;
  description: string;
}

export interface SimulationRequest {
  operator_id: number;
  machine_id: number;
  task_type_id: number;
  weather: string;
}

export interface SimulationResponse {
  prediction_id: number;
  operator_id: number;
  operator_name: string;
  machine_id: number;
  machine_name: string;
  task_type_id: number;
  task_type_name: string;
  weather: string;
  predicted_duration_minutes: number;
  p10_minutes: number;
  p90_minutes: number;
  uncertainty_range_minutes: number;
  skill_fit_score: number;
  skill_fit_label: string;
  safety_risk_score: number;
  safety_risk_level: 'low' | 'moderate' | 'elevated';
  training_recommended: boolean;
  training_reason?: string | null;
  probable_factors: ContributingFactor[];
  is_synthetic: boolean;
  created_at: string;
}

export interface OperatorOption {
  id: number;
  name: string;
  composite_score: number;
  derived_label: string;
}

export interface MachineOption {
  id: number;
  name: string;
  machine_type: string;
  age_years: number;
  wear_factor: number;
}

export interface TaskCatalogOption {
  id: number;
  name: string;
  baseline_duration_minutes: number;
  difficulty: number;
}

export interface SimulationOptionsResponse {
  operators: OperatorOption[];
  machines: MachineOption[];
  tasks: TaskCatalogOption[];
  weather_options: string[];
  is_synthetic: boolean;
}

export const fetchSimulationOptions = async (): Promise<SimulationOptionsResponse> => {
  const { data } = await apiClient.get<SimulationOptionsResponse>('/simulate/options');
  return data;
};

export const runSimulation = async (payload: SimulationRequest): Promise<SimulationResponse> => {
  const { data } = await apiClient.post<SimulationResponse>('/simulate/whatif', payload);
  return data;
};

export const fetchPredictionExplanation = async (predictionId: number): Promise<any> => {
  const { data } = await apiClient.get(`/models/explain/${predictionId}`);
  return data;
};

// ── Phase 5: Unified Incidents & Safety Events (§13, §B, §C) ──────────────

export type IncidentSource = 'seatbelt' | 'proximity' | 'deviation_anomaly' | 'manual';
export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface IncidentItem {
  id: number;
  operator_id: number;
  operator_name: string;
  machine_id?: number | null;
  machine_name?: string | null;
  task_instance_id?: number | null;
  source: IncidentSource;
  severity: IncidentSeverity;
  description?: string | null;
  created_at: string;
  is_synthetic: boolean;
}

export interface IncidentListResponse {
  incidents: IncidentItem[];
  total_count: number;
  is_synthetic: boolean;
}

export interface IncidentStatsResponse {
  total_incidents: number;
  by_severity: Record<string, number>;
  by_source: Record<string, number>;
  is_synthetic: boolean;
}

export interface IncidentCreateRequest {
  operator_id: number;
  machine_id?: number | null;
  task_instance_id?: number | null;
  source?: IncidentSource;
  severity: IncidentSeverity;
  description: string;
}

export const fetchIncidents = async (params?: {
  source?: string;
  severity?: string;
  operator_id?: number;
  limit?: number;
  offset?: number;
}): Promise<IncidentListResponse> => {
  const { data } = await apiClient.get<IncidentListResponse>('/incidents', { params });
  return data;
};

export const fetchIncidentStats = async (): Promise<IncidentStatsResponse> => {
  const { data } = await apiClient.get<IncidentStatsResponse>('/incidents/stats');
  return data;
};

export const createIncident = async (payload: IncidentCreateRequest): Promise<IncidentItem> => {
  const { data } = await apiClient.post<IncidentItem>('/incidents', payload);
  return data;
};

export const evaluateTaskSafety = async (taskId: number): Promise<any> => {
  const { data } = await apiClient.post(`/safety/evaluate-task/${taskId}`);
  return data;
};

// ── Phase 6 Anomaly & Coaching / Training Types ────────────────────────────

export interface ProbableContributingFactor {
  dimension: string;
  z_score: number;
  contribution_weight_pct: number;
  description: string;
}

export interface AnomalyItem {
  id?: number | null;
  task_instance_id: number;
  operator_id: number;
  operator_name: string;
  machine_id?: number | null;
  machine_name?: string | null;
  composite_magnitude: number;
  severity: string;
  observed_pattern: string;
  probable_factors: ProbableContributingFactor[];
  created_at: string;
  is_synthetic: boolean;
}

export interface AnomalyListResponse {
  anomalies: AnomalyItem[];
  total_count: number;
  is_synthetic: boolean;
}

export interface TaskAnomalyEvaluationResponse {
  task_instance_id: number;
  is_anomaly: boolean;
  composite_magnitude: number;
  severity?: string | null;
  observed_pattern?: string | null;
  probable_factors: ProbableContributingFactor[];
  incident_event_id?: number | null;
  is_synthetic: boolean;
}

export interface ElearningModule {
  id: number;
  name: string;
  dimension: string;
  description?: string | null;
  content_url?: string | null;
  duration_minutes: number;
  is_synthetic: boolean;
}

export interface TrainingRecommendation {
  id: number;
  operator_id: number;
  operator_name?: string | null;
  dimension: string;
  elearning_module_id?: number | null;
  elearning_module?: ElearningModule | null;
  reason: string;
  status: 'pending' | 'in_progress' | 'completed';
  created_at: string;
  is_synthetic: boolean;
}

export interface InstructorSlot {
  id: number;
  instructor_name: string;
  slot_date: string;
  start_time: string;
  end_time: string;
  is_available: boolean;
  is_synthetic: boolean;
}

export interface BookingCreateRequest {
  operator_id: number;
  instructor_slot_id: number;
  topic: string;
}

export interface InstructorBooking {
  id: number;
  operator_id: number;
  operator_name?: string | null;
  instructor_slot_id: number;
  instructor_name?: string | null;
  slot_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  topic: string;
  status: string;
  created_at: string;
  is_synthetic: boolean;
}

export const fetchAnomalies = async (params?: {
  operator_id?: number;
  severity?: string;
  limit?: number;
}): Promise<AnomalyListResponse> => {
  const { data } = await apiClient.get<AnomalyListResponse>('/anomalies', { params });
  return data;
};

export const detectTaskAnomaly = async (
  taskId: number
): Promise<TaskAnomalyEvaluationResponse> => {
  const { data } = await apiClient.post<TaskAnomalyEvaluationResponse>(
    `/anomalies/detect/${taskId}`
  );
  return data;
};

export const fetchTrainingRecommendations = async (
  operatorId: number
): Promise<TrainingRecommendation[]> => {
  const { data } = await apiClient.get<TrainingRecommendation[]>(
    `/training/recommendations/${operatorId}`
  );
  return data;
};

export const fetchElearningModules = async (): Promise<ElearningModule[]> => {
  const { data } = await apiClient.get<ElearningModule[]>('/training/modules');
  return data;
};

export const fetchInstructorSlots = async (
  availableOnly: boolean = true
): Promise<InstructorSlot[]> => {
  const { data } = await apiClient.get<InstructorSlot[]>('/training/slots', {
    params: { available_only: availableOnly },
  });
  return data;
};

export const createInstructorBooking = async (
  payload: BookingCreateRequest
): Promise<InstructorBooking> => {
  const { data } = await apiClient.post<InstructorBooking>('/training/bookings', payload);
  return data;
};

export const fetchOperatorBookings = async (
  operatorId: number
): Promise<InstructorBooking[]> => {
  const { data } = await apiClient.get<InstructorBooking[]>(
    `/training/bookings/${operatorId}`
  );
  return data;
};
