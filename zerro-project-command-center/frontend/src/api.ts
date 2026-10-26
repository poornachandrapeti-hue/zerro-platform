import type { Contractor, Dashboard, ProjectListItem, Role, SubTask, WorkPackage } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export type VerifiedActivity = {
  activity_id: number;
  activity_code: string;
  method: string;
  scope_quantity: number;
  verified_quantity: number;
  verified_percent: number;
  baseline_status?: "approved" | "unmatched" | "scope_or_unit_mismatch";
  planned_quantity?: number;
  planned_percent?: number;
  variance_pp?: number;
  unit: string;
};
export type VerifiedPackage = {
  package_id: number;
  package_code: string;
  name: string;
  status: string;
  discipline_id: number;
  discipline_name: string;
  planned_start: string | null;
  planned_finish: string | null;
  date_reference_percent: number | null;
  date_reference_note: string;
  activities: VerifiedActivity[];
};
export type LiveVerifiedProgress = {
  source: "siteforge";
  project_code: string;
  generated_at: string;
  measurement: string;
  packages: VerifiedPackage[];
  package_count: number;
  approved_baseline?: {status:string; revision?:string; approval_reference?:string; approved_on?:string};
  alerts?: {package_code:string; activity_code:string; discipline:string; variance_pp:number; level:string; message:string}[];
};

export type PlanningMonitor = {
  source: "siteforge_planning";
  project_code: string;
  generated_at: string;
  approved_revision: string | null;
  approved_forecast?: {revision:number;data_date:string;project_finish:string|null;baseline_finish?:string|null;finish_variance_days?:number|null;finish_variance_basis?:string;basis:string;source_actuals_verified:boolean;note:string}|null;
  advanced_monitoring?: {
    criticality_changes:{activity_code:string;activity_name:string;baseline_critical:boolean;forecast_critical:boolean;forecast_finish:string|null}[];
    milestone_risks:{activity_code:string;activity_name:string;baseline_finish:string|null;forecast_finish:string|null;difference_calendar_days:number|null;risk_status:string}[];
    unmatched_baseline_activity_count:number;
    duplicate_activity_codes:string[];
    basis:string; note:string;
  }|null;
  planned: {date:string; planned_percent:number}[];
  observed: {date:string; verified_percent:number|null}[];
  active_alert_count: number;
  alert_severity_counts: Record<string,number>;
  milestones?: {activity_code:string;activity_name:string;baseline_start:string|null;baseline_finish:string|null;actual_finish:string|null;variance_days:number|null;variance_status:string;completion_status?:string;verified_percent?:number|null;monitoring_status?:string;verification_source?:string}[];
  critical_activities?: {activity_code:string;activity_name:string;baseline_start:string|null;baseline_finish:string|null;total_float_hours:number|null;critical:boolean}[];
  calculation_info?: {status:string;basis?:string;note?:string};
  alerts_detail?: {id:number;severity:string;status:string;trigger_type:string;source_type:string;first_detected_at:string|null;last_detected_at:string|null}[];
  note: string;
};

export type Phase9FinanceMonitor = {
  source: "zerrobuild.financials.phase9_proposal_monitor";
  organization_id: number;
  project_id: number;
  as_of: string;
  read_only: true;
  complete_history: false;
  gl_posted_verified: false;
  inventory_valuation_certified: false;
  billing_certified: false;
  coverage: string;
  record_count: number;
  status_counts: Record<string, number>;
  proposal_records: Array<{
    proposal_id: number;
    source_movement_line_id: number;
    status: "Draft" | "Pending Review" | "Approved" | "Rejected";
    proposal_revision: number;
  }>;
};

export type ProgressPayload = { actual_progress: number; actual_cost: number; status: string };
export type ContractorPayload = { code?: string; name: string; contact_name: string; phone: string };
export type ProjectPayload = {
  code: string;
  name: string;
  client: string;
  location: string;
  start_date: string;
  planned_finish: string;
  forecast_finish: string;
  approved_budget: number;
  currency?: string;
  status?: string;
};
export type WorkPackagePayload = {
  code?: string;
  name: string;
  area: string;
  contractor_id: number;
  weight: number;
  planned_progress: number;
  actual_progress: number;
  budget: number;
  committed_cost: number;
  actual_cost: number;
  start_date: string;
  target_date: string;
  status: string;
};
export type SubTaskPayload = {
  code?: string;
  name: string;
  owner: string;
  weight: number;
  planned_progress: number;
  actual_progress: number;
  status: string;
  start_date?: string | null;
  target_date?: string | null;
  notes?: string;
};

function headers(role: Role, json = false) {
  const result: Record<string, string> = { "X-User-Role": role.role };
  if (role.discipline) result["X-Discipline"] = role.discipline;
  if (json) result["Content-Type"] = "application/json";
  return result;
}

function errorMessage(detail: unknown) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item: { msg?: string }) => item.msg ?? JSON.stringify(item)).join("; ");
  return "Request failed";
}

async function request<T>(path: string, role: Role, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(errorMessage(body.detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  projects: (role: Role) => request<ProjectListItem[]>("/api/projects", role, { headers: headers(role) }),
  createProject: (role: Role, payload: ProjectPayload) =>
    request<ProjectListItem>("/api/projects", role, {
      method: "POST",
      headers: headers(role, true),
      body: JSON.stringify(payload),
    }),
  deleteProject: (projectId: number, role: Role) =>
    request<void>(`/api/projects/${projectId}`, role, {
      method: "DELETE",
      headers: headers(role),
    }),
  phase9FinanceMonitor: (projectId: number, role: Role) =>
    request<Phase9FinanceMonitor>(`/api/projects/${projectId}/phase9-finance-monitor`, role, { headers: headers(role), cache: "no-store" }),
  planningMonitor: (projectId: number, role: Role) =>
    request<PlanningMonitor>(`/api/projects/${projectId}/planning-monitor`, role),
  liveProgress: (projectId: number, role: Role) =>
    request<LiveVerifiedProgress>(`/api/projects/${projectId}/live-progress`, role),
  dashboard: (projectId: number, role: Role) =>
    request<Dashboard>(`/api/projects/${projectId}/dashboard`, role, { headers: headers(role) }),
  contractors: (role: Role) => request<Contractor[]>("/api/contractors", role, { headers: headers(role) }),
  createWorkPackage: (projectId: number, disciplineCode: string, role: Role, payload: WorkPackagePayload & { code: string }) =>
    request<WorkPackage>(`/api/projects/${projectId}/disciplines/${disciplineCode}/work-packages`, role, {
      method: "POST",
      headers: headers(role, true),
      body: JSON.stringify(payload),
    }),
  updateWorkPackage: (packageId: number, role: Role, payload: WorkPackagePayload) =>
    request<WorkPackage>(`/api/work-packages/${packageId}`, role, {
      method: "PATCH",
      headers: headers(role, true),
      body: JSON.stringify(payload),
    }),
  updateProgress: (packageId: number, role: Role, payload: ProgressPayload) =>
    request<WorkPackage>(`/api/work-packages/${packageId}/progress`, role, {
      method: "PATCH",
      headers: headers(role, true),
      body: JSON.stringify(payload),
    }),
  createSubTask: (packageId: number, role: Role, payload: SubTaskPayload & { code: string }) =>
    request<SubTask>(`/api/work-packages/${packageId}/sub-tasks`, role, {
      method: "POST",
      headers: headers(role, true),
      body: JSON.stringify(payload),
    }),
  updateSubTask: (taskId: number, role: Role, payload: SubTaskPayload) =>
    request<SubTask>(`/api/sub-tasks/${taskId}`, role, {
      method: "PATCH",
      headers: headers(role, true),
      body: JSON.stringify(payload),
    }),
  deleteSubTask: (taskId: number, role: Role) =>
    request<void>(`/api/sub-tasks/${taskId}`, role, {
      method: "DELETE",
      headers: headers(role),
    }),
  createContractor: (role: Role, payload: ContractorPayload & { code: string }) =>
    request<Contractor>("/api/contractors", role, {
      method: "POST",
      headers: headers(role, true),
      body: JSON.stringify(payload),
    }),
  updateContractor: (contractorId: number, role: Role, payload: ContractorPayload) =>
    request<Contractor>(`/api/contractors/${contractorId}`, role, {
      method: "PATCH",
      headers: headers(role, true),
      body: JSON.stringify({
        name: payload.name,
        contact_name: payload.contact_name,
        phone: payload.phone,
      }),
    }),
};
