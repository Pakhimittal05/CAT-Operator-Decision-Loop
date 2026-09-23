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
