import type { Contractor, Dashboard, ProjectListItem, Role, SubTask, WorkPackage } from "./types";

const API_URL = "/command-api";

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


export type StoresApprovalWorkload = {
  organization_id: number;
  project_id: number;
  as_of: string;
  stale: boolean;
  pending_approval_count: number;
  past_required_date_count: number;
  partner_origin_pending_count: number;
  pending_without_active_task_count: number;
  overdue_active_task_count: number;
  physical_stock_readiness: "Unverified";
};

/** Requires the separate Command Center backend to enforce current viewer grants.
 *  No service credential is ever supplied by the browser. */
export async function commandCenterStoresWorkload(projectId: number): Promise<StoresApprovalWorkload> {
  const response = await fetch(`/command-api/api/projects/${projectId}/stores-approval-workload`, { credentials: "include" });
  if (!response.ok) throw new Error(response.status === 404 ? "Stores Command Center endpoint is not deployed" : `Stores workload unavailable (${response.status})`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object") throw new Error("Invalid Stores workload response");
  const data = payload as Record<string, unknown>;
  const keys = ["pending_approval_count", "past_required_date_count", "partner_origin_pending_count", "pending_without_active_task_count", "overdue_active_task_count"];
  if (data.project_id !== projectId || typeof data.organization_id !== "number" || data.physical_stock_readiness !== "Unverified" || typeof data.stale !== "boolean" ||
      typeof data.as_of !== "string" || !Number.isFinite(Date.parse(data.as_of)) ||
      keys.some(key => !Number.isSafeInteger(data[key]) || (data[key] as number) < 0)) {
    throw new Error("Stores feed failed validation");
  }
  const age = Date.now() - Date.parse(data.as_of as string);
  if (age < -60000 || age > 300000 || data.stale) throw new Error("Stores workload data is stale; refresh required");
  return data as StoresApprovalWorkload;
}

export type StoresPhase8Exceptions = {
  source: string; organization_id: number; project_id: number; as_of: string;
  stale: false; record_count: number; coverage: string; complete_history: false;
  exception_counts: Record<string, number>;
  exception_records: Array<{material_request_id:number;work_package_id:number|null;exception_codes:string[];review_state:string}>;
  external_inspection_verified: false; financials_authority_verified: false; billing_certified: false;
};

/** Browser calls only the separate authenticated Command Center backend, NEVER Stores directly. */
export async function commandCenterStoresPhase8Exceptions(projectId: number): Promise<StoresPhase8Exceptions> {
  const response = await fetch(`/command-api/api/projects/${projectId}/stores-phase8-exceptions`, { credentials: "include", cache: "no-store" });
  if (!response.ok) throw new Error(`Stores exceptions unavailable (${response.status})`);
  const data: unknown = await response.json();
  if (!data || typeof data !== "object") throw new Error("Invalid Stores exception response");
  const d = data as Record<string, unknown>;
  if (d.source !== "zerrobuild.stores.phase8_cross_module_audit" || d.project_id !== projectId ||
      typeof d.organization_id !== "number" || !Number.isSafeInteger(d.organization_id) || d.organization_id <= 0 ||
      d.stale !== false || d.complete_history !== false || d.external_inspection_verified !== false ||
      d.financials_authority_verified !== false || d.billing_certified !== false ||
      typeof d.as_of !== "string" || !Number.isFinite(Date.parse(d.as_of)) ||
      Date.now() - Date.parse(d.as_of) > 300000 || Date.now() - Date.parse(d.as_of) < -60000 ||
      !Number.isSafeInteger(d.record_count) || (d.record_count as number) < 0 || (d.record_count as number) > 500 ||
      typeof d.coverage !== "string" || !d.exception_counts || typeof d.exception_counts !== "object" ||
      Array.isArray(d.exception_counts) || !Array.isArray(d.exception_records) ||
      Object.values(d.exception_counts).some(v => !Number.isSafeInteger(v) || (v as number) < 0 || (v as number) > (d.record_count as number)) ||
      d.exception_records.length > (d.record_count as number) ||
      d.exception_records.some((r: unknown) => {if (!r || typeof r !== "object") return true; const item = r as Record<string,unknown>;
        return !Number.isSafeInteger(item.material_request_id) || (item.material_request_id as number) <= 0 ||
          (item.work_package_id !== null && (!Number.isSafeInteger(item.work_package_id) || (item.work_package_id as number) <= 0)) ||
          !Array.isArray(item.exception_codes) || !item.exception_codes.length || !item.exception_codes.every((c:unknown) => typeof c === "string" && Object.prototype.hasOwnProperty.call(d.exception_counts,c)) || typeof item.review_state !== "string";
      })) throw new Error("Stores exception feed failed validation");
  return d as StoresPhase8Exceptions;
}

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
  const response = await fetch(`${API_URL}${path.replace(/^\/api(?=\/)/, "")}`, { ...init, credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(errorMessage(body.detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export type FinancialIntelligence = {
  project_code: string;
  generated_at: string;
  basis: string;
  currencies: Record<string, Record<string, string>>;
  estimate_at_completion: null;
  forecast_variance: null;
  payment_request_aging_by_currency?: Record<string, Record<string, string>>;
  alerts?: Array<{kind: string; currency?: string; amount?: string; number?: string; days_overdue?: number}>;
  receivables_aging?: null;
  unmapped_purchase_order_count: number;
  limitations: string[];
};

export type FinancialEvidence = {project_code:string; category:string; currency:string|null; total_records:number; truncated:boolean; read_only:boolean; rows:Array<{source_type:string;source_id:number;reference:string;status:string;currency:string;amount:string;[key:string]:unknown}>};

export const api = {
  financialEvidence: (projectId: number, category: string, currency: string, role: Role) => request<FinancialEvidence>(`/api/projects/${projectId}/financial-evidence?category=${encodeURIComponent(category)}&currency=${encodeURIComponent(currency)}`, role),
  financialIntelligence: (projectId: number, role: Role) => request<FinancialIntelligence>(`/api/projects/${projectId}/financial-intelligence`, role),
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
