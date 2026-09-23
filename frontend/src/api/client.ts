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
