import { FormEvent, useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Award,
  BadgeCheck,
  BellRing,
  LogOut,
  CalendarClock,
  CalendarOff,
  ClipboardList,
  Clock3,
  FilePenLine,
  HardHat,
  IdCard,
  LayoutDashboard,
  ListChecks,
  ListTree,
  Lock,
  LockOpen,
  Moon,
  Pencil,
  Plus,
  Scale,
  ShieldCheck,
  Timer,
  Trash2,
  UserRoundCheck,
  Users,
  UsersRound,
} from "lucide-react";
import { api } from "./api";
import { HseRoutes } from "./hse";
import type { Page, Project, Session } from "./types";

const TABS = ["Dashboard", "Personnel", "Deployments", "Requests", "Crews & shifts", "Attendance", "Corrections", "Leave", "Overtime", "Reconciliation", "Qualifications", "Offboarding", "Alerts", "Workforce lists"] as const;
type Tab = (typeof TABS)[number];
const TAB_ICON: Record<Tab, LucideIcon> = {
  Dashboard: LayoutDashboard,
  Personnel: IdCard,
  Deployments: HardHat,
  Requests: ClipboardList,
  "Crews & shifts": UsersRound,
  Attendance: Clock3,
  Corrections: FilePenLine,
  Leave: CalendarOff,
  Overtime: Timer,
  Reconciliation: Scale,
  Qualifications: Award,
  Offboarding: LogOut,
  Alerts: BellRing,
  "Workforce lists": ListTree,
};
const TAB_TONE: Record<Tab, string> = {
  Dashboard: "tone-wdash",
  Personnel: "tone-wpeople",
  Deployments: "tone-wdeploy",
  Requests: "tone-wreq",
  "Crews & shifts": "tone-wcrew",
  Attendance: "tone-watt",
  Corrections: "tone-wfix",
  Leave: "tone-wleave",
  Overtime: "tone-wot",
  Reconciliation: "tone-wrecon",
  Qualifications: "tone-wqual",
  Offboarding: "tone-woff",
  Alerts: "tone-walert",
  "Workforce lists": "tone-wlist",
};
const LEAVE_ROUTES = [{ recordType: "hr.leave", label: "Leave approver", stage: "Leave approval" }];
const OVERTIME_ROUTES = [{ recordType: "hr.overtime", label: "Overtime approver", stage: "Overtime approval" }];
const LEAVE_OPEN = ["Draft", "Returned"];
const CANCELLABLE = ["Draft", "Returned", "Approved"];
const ATTENDANCE_ROUTES = [{ recordType: "hr.attendance", label: "Attendance reviewer", stage: "Attendance review" }];
const CORRECTION_ROUTES = [{ recordType: "hr.correction", label: "Correction reviewer", stage: "Attendance correction review" }];
const DEPLOYMENT_ROUTES = [{ recordType: "hr.deployment", label: "Mobilization approver", stage: "Mobilization approval" }];
const ON_SITE = ["Approved for Mobilization", "Mobilized"];
const ALLOCATING = ["Open", "Partially Allocated", "Allocated"];

type Option = { id: number; name: string };
type Master = { id: number; kind: string; name: string; active: boolean; version: number };
type Person = {
  id: number;
  code: string;
  full_name: string;
  company_id: number;
  company_name: string;
  personnel_type: string;
  designation_id: number;
  designation: string;
  trade_id: number;
  trade: string;
  grade_id: number | null;
  grade: string;
  discipline_id: number | null;
  discipline: string;
  start_date: string;
  end_date: string | null;
  supervisor_id: number | null;
  supervisor_name: string;
  status: string;
  user_id: number | null;
  login_name: string;
  login_active: boolean;
  access_review: boolean;
  restricted_visible: boolean;
  contact_number: string | null;
  emergency_contact: string | null;
  date_of_birth: string | null;
  address: string | null;
  identity_reference: string | null;
  version: number;
};
type Board = {
  note: string;
  restricted_visible: boolean;
  personnel: Person[];
  masters: Master[];
  master_kinds: string[];
  personnel_types: string[];
  statuses: string[];
  companies: Option[];
  disciplines: Option[];
  logins: { id: number; name: string; email: string }[];
  counts: Record<string, number>;
  by_type: Record<string, number>;
  by_company: Record<string, number>;
  by_trade: Record<string, number>;
  count_note: string;
  deployments: Deployment[];
  requests: WorkRequest[];
  deployment_note: string;
  request_note: string;
  check_types: { name: string; owner: string }[];
  priorities: string[];
  areas: Option[];
  packages: Option[];
  project_disciplines: Option[];
  members: Option[];
  can_request: boolean;
  upcoming_mobilizations: Deployment[];
  upcoming_demobilizations: Deployment[];
  deployed_note: string;
  shifts: ShiftRow[];
  crews: CrewRow[];
  sheets: Sheet[];
  corrections: Correction[];
  locks: LockRow[];
  attendance_statuses: string[];
  correction_kinds: string[];
  attributions: string[];
  crew_note: string;
  attendance_note: string;
  can_attend: boolean;
  present_by_shift: Record<string, number>;
  attendance_count_note: string;
  leaves: LeaveRow[];
  overtime: OvertimeRow[];
  leave_note: string;
  overtime_note: string;
  reconciliation: ReconRow[];
  reconciliation_from: string;
  reconciliation_note: string;
  credential_types: CredentialType[];
  credentials: CredentialRow[];
  credential_rules: CredentialRule[];
  eligibility: EligibilityRow[];
  activities: { id: number; name: string; package_id: number }[];
  credential_note: string;
  rule_note: string;
  eligibility_note: string;
  can_manage_credentials: boolean;
  credential_owners_i_verify: string[];
  offboardings: OffboardingRow[];
  offboarding_note: string;
  alerts: AlertRow[];
  monitor_settings: MonitorSettings;
  monitor_note: string;
  escalation_names: string[];
};
type OffboardingRow = {
  id: number;
  deployment_id: number;
  personnel_id: number;
  person: string;
  last_working_date: string;
  reason: string;
  status: string;
  status_reason: string;
  requester: string;
  approved_at: string | null;
  version: number;
  items: { id: number; item: string; status: string; note: string; done_by: string; version: number }[];
  findings: {
    open_tasks: { id: number; title: string; due_date: string | null }[];
    pending_sheets: string[];
    pending_corrections: number;
    crew_memberships: number;
    allocations: number;
    login_active: boolean;
    project_memberships: number;
    other_project_memberships: number;
    attendance_after_last_day: number;
  } | null;
  review: Review | null;
};
type AlertRow = {
  kind: string;
  key: string;
  subject: string;
  body: string;
  since: string;
  age_days: number;
  escalated: boolean;
  recipient_ids: number[];
  recipients: string[];
};
type MonitorSettings = {
  enabled: boolean;
  mobilization_grace_days: number;
  onboarding_lead_days: number;
  attendance_grace_days: number;
  escalate_after_days: number;
  escalation_user_ids: number[];
  version: number | null;
  saved: boolean;
};
type CredentialType = { id: number; name: string; owner: string; requires_expiry: boolean; active: boolean; version: number };
type CredentialRow = {
  id: number;
  personnel_id: number;
  person: string;
  type_id: number;
  type: string;
  owner: string;
  certificate_number: string;
  issuer: string;
  issue_date: string;
  expiry_date: string | null;
  evidence: string;
  applicable_activities: string;
  status: string;
  state: string;
  superseded: boolean;
  decision_reason: string;
  verified_by: string;
  verified_at: string | null;
  created_by: string;
  can_decide: boolean;
  decide_block: string;
  can_withdraw: boolean;
  version: number;
};
type CredentialRule = { id: number; type_id: number; type: string; owner: string; active: boolean; package_id: number | null; activity_id: number | null; scope: string };
type EligibilityRow = {
  personnel_id: number;
  person: string;
  deployment_status: string;
  status: string;
  items: { type_id: number; type: string; status: string }[];
  scoped: { rule_id: number; type: string; scope: string; status: string }[];
};
type ReconRow = {
  date: string;
  personnel_id: number;
  person: string;
  attendance: string;
  activity: string;
  idle: string;
  unallocated: string;
  overtime_attended: string;
  overtime_approved: string;
  overtime_payable: string;
  exceptions: string[];
};
type LeaveRow = {
  id: number;
  personnel_id: number;
  person: string;
  company_name: string;
  leave_type_id: number;
  leave_type: string;
  start_date: string;
  end_date: string;
  start_time: string | null;
  end_time: string | null;
  duration: string;
  reason: string | null;
  evidence: string | null;
  requester: string;
  mine: boolean;
  status: string;
  status_reason: string;
  effects: string[];
  version: number;
  review: Review | null;
};
type OvertimeRow = {
  id: number;
  target: string;
  crew_id: number | null;
  personnel_id: number | null;
  work_date: string;
  shift: string;
  package: string;
  requested: string;
  requested_minutes: number;
  approved: string | null;
  approved_minutes: number | null;
  reason: string;
  requester: string;
  mine: boolean;
  status: string;
  status_reason: string;
  can_set_hours: boolean;
  lines: { personnel_id: number; person: string; attended: string; payable: string }[];
  version: number;
  review: Review | null;
};
type ShiftRow = {
  id: number;
  code: string;
  name: string;
  start_time: string;
  end_time: string;
  break_minutes: number;
  overnight: boolean;
  scheduled: string;
  attribution: string;
  calendar: string;
  effective_from: string;
  effective_to: string | null;
  active: boolean;
  version: number;
};
type CrewRow = {
  id: number;
  code: string;
  company_id: number;
  company_name: string;
  discipline_id: number | null;
  discipline: string;
  lead_id: number | null;
  lead: string;
  shift_id: number | null;
  shift: string;
  effective_from: string;
  effective_to: string | null;
  active: boolean;
  version: number;
  members: { id: number; personnel_id: number; person: string; start_date: string; end_date: string | null; active: boolean }[];
};
type AttendanceRow = {
  id: number;
  personnel_id: number;
  person: string;
  own: boolean;
  on_leave: boolean;
  status: string;
  source: string;
  segments: [string, string][];
  worked: string;
  regular: string;
  overtime: string;
  remarks: string;
  version: number;
};
type Sheet = {
  id: number;
  attendance_date: string;
  shift_id: number;
  shift: string;
  crew_id: number | null;
  crew: string;
  status: string;
  late: boolean;
  submitted_by: string;
  locked: boolean;
  version: number;
  records: AttendanceRow[];
  review: Review | null;
};
type Values = { status: string; segments: [string, string][]; worked: string; overtime_minutes: number };
type Correction = {
  id: number;
  person: string;
  attendance_date: string;
  kind: string;
  original: Values;
  proposed: Values;
  reason: string;
  evidence: string;
  status: string;
  requested_by: string;
  applied_at: string | null;
  review: Review | null;
};
type LockRow = {
  id: number;
  period_start: string;
  period_end: string;
  reason: string;
  locked_by: string;
  reopened: boolean;
  reopened_by: string;
  reopen_reason: string;
};
type Review = { id: number; version: number; actions: string[]; state: string };
type Check = {
  id: number;
  check_type: string;
  owner: string;
  status: string;
  evidence: string;
  verified_by: string;
  can_verify: boolean;
  version: number;
};
type Deployment = {
  id: number;
  personnel_id: number;
  person: string;
  trade_id: number | null;
  company_name: string;
  discipline: string;
  supervisor_name: string;
  area: string;
  planned_start: string;
  planned_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  shift: string;
  required_skills: string;
  status: string;
  status_reason: string;
  flagged_allocations: number;
  version: number;
  checks: Check[];
  review: Review | null;
};
type WorkRequest = {
  id: number;
  number: string;
  discipline: string;
  area: string;
  package: string;
  company_name: string;
  trade_id: number;
  trade: string;
  headcount: number;
  qualifications: string;
  start_date: string;
  end_date: string | null;
  shift: string;
  priority: string;
  requested_by: number;
  requester: string;
  justification: string;
  expected_mobilization: string | null;
  status: string;
  status_reason: string;
  counts: { required: number; proposed: number; allocated: number; shortfall: number };
  lines: { id: number; personnel_id: number; person: string; state: string; deployment_id: number | null }[];
  version: number;
  review: Review | null;
};

export function Err({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}

export function Count({ label, value }: { label: string; value: number | string }) {
  return (
    <article className="hr-count">
      <strong>{value}</strong>
      <span>{label}</span>
    </article>
  );
}

export function statusClass(status: string) {
  return `rel-chip hr-status-${status.toLowerCase().replace(/\s+/g, "-")}`;
}

export function ReviewBox({ review, onError, reload }: { review: Review | null; onError: (text: string) => void; reload: () => Promise<void> }) {
  const [reason, setReason] = useState("");
  if (!review) return null;
  const choices = review.actions.filter((action) => ["approve", "return", "reject", "resubmit"].includes(action));
  if (!choices.length) return <p className="muted">Review: {review.state}</p>;
  async function act(action: string) {
    if ((action === "return" || action === "reject") && !reason.trim()) {
      onError("Type the reason, then choose Return or Reject.");
      return;
    }
    onError("");
    try {
      if (action === "resubmit") {
        await api(`/reviews/${review!.id}/resubmit`, "POST", { version: review!.version });
      } else {
        await api(`/reviews/${review!.id}/decisions`, "POST", { action, reason: action === "approve" ? "" : reason, comment: "", version: review!.version });
      }
      setReason("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <div className="hr-review">
      <ShieldCheck size={15} />
      <input aria-label="Decision reason" placeholder="Reason, required for Return and Reject" value={reason} onChange={(event) => setReason(event.target.value)} />
      {choices.map((action) => (
        <button key={action} type="button" className={action === "approve" ? "primary" : ""} onClick={() => void act(action)}>
          {action === "approve" ? "Approve" : action === "return" ? "Return" : action === "reject" ? "Reject" : "Resubmit"}
        </button>
      ))}
    </div>
  );
}

export function HrHome({ session, initialProjectId = null }: { session: Session; initialProjectId?: number | null }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [pid, setPid] = useState<number | null>(initialProjectId);
  const [error, setError] = useState("");
  useEffect(() => {
    void api<Page<Project>>("/projects?limit=100")
      .then((page) => setProjects(page.items))
      .catch((err) => setError((err as Error).message));
  }, []);
  if (pid) {
    return (
      <>
        <button className="back" onClick={() => setPid(null)}>
          ← Projects
        </button>
        <HrBoard pid={pid} session={session} />
      </>
    );
  }
  return (
    <section className="panel">
      <h2>HR & Workforce</h2>
      <p className="muted">Open a project to keep the personnel of the companies working on it.</p>
      <Err text={error} />
      {projects.map((project) => (
        <button key={project.id} onClick={() => setPid(project.id || null)}>
          <Users size={16} strokeWidth={2.4} />
          {project.code} · {project.name}
        </button>
      ))}
    </section>
  );
}

function HrBoard({ pid, session }: { pid: number; session: Session }) {
  const [tab, setTab] = useState<Tab>("Dashboard");
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState("");
  const admin = session.user.organization_admin;
  const canEdit =
    admin || session.memberships.some((item) => item.project_id === pid && item.permissions?.includes("hr.edit"));
  async function load() {
    setBoard(await api<Board>(`/projects/${pid}/hr`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  return (
    <section className="panel hr-panel">
      <h2>HR & Workforce</h2>
      <div className="proc-nav">
        {TABS.map((name) => {
          const Icon = TAB_ICON[name];
          return (
            <button
              key={name}
              type="button"
              className={`proc-tab ${TAB_TONE[name]}${tab === name ? " is-on" : ""}`}
              aria-pressed={tab === name}
              onClick={() => setTab(name)}
            >
              <Icon size={14} strokeWidth={2.4} />
              <span>{name}</span>
            </button>
          );
        })}
      </div>
      <Err text={error} />
      {board ? <p className="note-card">{board.note}</p> : null}
      {tab === "Dashboard" && board ? <Dashboard board={board} /> : null}
      {tab === "Personnel" && board ? (
        <Personnel pid={pid} board={board} canEdit={canEdit} onError={setError} reload={load} onLists={() => setTab("Workforce lists")} />
      ) : null}
      {tab === "Deployments" && board ? (
        <Deployments pid={pid} board={board} admin={admin} canEdit={canEdit} onError={setError} reload={load} />
      ) : null}
      {tab === "Requests" && board ? (
        <Requests pid={pid} board={board} onError={setError} reload={load} />
      ) : null}
      {tab === "Crews & shifts" && board ? <CrewsShifts pid={pid} board={board} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Attendance" && board ? <Attendance pid={pid} board={board} admin={admin} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Corrections" && board ? <Corrections pid={pid} board={board} admin={admin} onError={setError} reload={load} /> : null}
      {tab === "Leave" && board ? (
        <LeaveTab pid={pid} board={board} admin={admin} canEdit={canEdit} userId={session.user.id} onError={setError} reload={load} />
      ) : null}
      {tab === "Overtime" && board ? <OvertimeTab pid={pid} board={board} admin={admin} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Reconciliation" && board ? <Reconciliation board={board} /> : null}
      {tab === "Qualifications" && board ? (
        <Qualifications pid={pid} board={board} canEdit={canEdit} userId={session.user.id} onError={setError} reload={load} />
      ) : null}
      {tab === "Offboarding" && board ? <OffboardingTab pid={pid} board={board} admin={admin} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Alerts" && board ? <AlertsTab pid={pid} board={board} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Workforce lists" && board ? (
        <Lists pid={pid} board={board} canEdit={canEdit} onError={setError} reload={load} />
      ) : null}
    </section>
  );
}

function Breakdown({ title, rows }: { title: string; rows: Record<string, number> }) {
  const entries = Object.entries(rows).sort((a, b) => b[1] - a[1]);
  return (
    <article className="hr-breakdown">
      <h3>{title}</h3>
      {entries.length === 0 ? (
        <p className="muted">No active person yet.</p>
      ) : (
        <ul>
          {entries.map(([name, value]) => (
            <li key={name}>
              <span>{name || "Not set"}</span>
              <strong>{value}</strong>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function Dashboard({ board }: { board: Board }) {
  return (
    <>
      <div className="dash-grid">
        <Count label="Personnel" value={board.counts.personnel} />
        <Count label="Active" value={board.counts.active} />
        <Count label="Inactive" value={board.counts.inactive} />
        <Count label="Separated" value={board.counts.separated} />
        <Count label="Without a login" value={board.counts.without_login} />
        <Count label="Login reviews" value={board.counts.access_reviews} />
      </div>
      <p className="muted">{board.count_note}</p>
      <div className="hr-breakdowns">
        <Breakdown title="Active by type" rows={board.by_type} />
        <Breakdown title="Active by company" rows={board.by_company} />
        <Breakdown title="Active by trade" rows={board.by_trade} />
      </div>
      <h3 className="section-mark">
        <HardHat size={18} strokeWidth={2.4} /> Deployment and demand
      </h3>
      <div className="dash-grid">
        <Count label="Deployed today" value={board.counts.deployed} />
        <Count label="Pending onboarding" value={board.counts.pending_onboarding} />
        <Count label="Awaiting approval" value={board.counts.pending_approval} />
        <Count label="Temporarily unavailable" value={board.counts.unavailable} />
        <Count label="Open requests" value={board.counts.open_requests} />
        <Count label="Shortfall" value={board.counts.shortfall} />
      </div>
      <p className="muted">{board.deployed_note}</p>
      <div className="hr-breakdowns">
        <Upcoming title="Mobilizing in the next 14 days" rows={board.upcoming_mobilizations} field="planned_start" />
        <Upcoming title="Demobilizing in the next 14 days" rows={board.upcoming_demobilizations} field="planned_end" />
      </div>
      <h3 className="section-mark">
        <Clock3 size={18} strokeWidth={2.4} /> Attendance today
      </h3>
      <div className="dash-grid">
        <Count label="Present today" value={board.counts.present_today} />
        <Count label="Available today" value={board.counts.available_today} />
        <Count label="Missing attendance" value={board.counts.missing_attendance} />
        <Count label="Sheets to review" value={board.counts.pending_sheets} />
        <Count label="Corrections to review" value={board.counts.pending_corrections} />
        <Count label="Active crews" value={board.counts.active_crews} />
      </div>
      <p className="muted">{board.attendance_count_note}</p>
      <div className="hr-breakdowns">
        <Breakdown title="Present today by shift" rows={board.present_by_shift} />
      </div>
      <h3 className="section-mark">
        <CalendarOff size={18} strokeWidth={2.4} /> Leave and overtime
      </h3>
      <div className="dash-grid">
        <Count label="On leave today" value={board.counts.on_leave_today} />
        <Count label="Leave to approve" value={board.counts.pending_leave} />
        <Count label="Overtime to approve" value={board.counts.pending_overtime} />
        <Count label="Reconciliation exceptions" value={board.counts.recon_exceptions} />
      </div>
      <h3 className="section-mark">
        <Award size={18} strokeWidth={2.4} /> Qualifications and eligibility
      </h3>
      <div className="dash-grid">
        <Count label="Waiting for verification" value={board.counts.credentials_pending} />
        <Count label="Expiring in 30 days" value={board.counts.credentials_expiring} />
        <Count label="Expired" value={board.counts.credentials_expired} />
        <Count label="Deployed people not eligible today" value={board.counts.not_eligible} />
      </div>
      <h3 className="section-mark">
        <BellRing size={18} strokeWidth={2.4} /> Offboarding and alerts
      </h3>
      <div className="dash-grid">
        <Count label="Open offboardings" value={board.counts.open_offboardings} />
        <Count label="Open alerts" value={board.counts.open_alerts} />
        <Count label="Escalated alerts" value={board.counts.escalated_alerts} />
      </div>
    </>
  );
}

const NEW_SHIFT = { code: "", name: "", start_time: "08:00", end_time: "17:00", break_minutes: "60", attribution: "Start day", calendar: "", effective_from: "", effective_to: "" };
function CrewsShifts({
  pid,
  board,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [shift, setShift] = useState(NEW_SHIFT);
  const [open, setOpen] = useState<"" | "shift">("");
  const setS = (key: keyof typeof NEW_SHIFT) => (event: { target: { value: string } }) => setShift({ ...shift, [key]: event.target.value });

  async function run(path: string, method: string, body: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/hr/${path}`, method, body);
      await reload();
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }
  function shiftBody(row: typeof NEW_SHIFT) {
    return {
      code: row.code,
      name: row.name,
      start_time: row.start_time,
      end_time: row.end_time,
      break_minutes: Number(row.break_minutes || 0),
      attribution: row.attribution,
      calendar: row.calendar,
      effective_from: row.effective_from,
      effective_to: row.effective_to || null,
    };
  }
  async function addShift(event: FormEvent) {
    event.preventDefault();
    if (await run("shifts", "POST", shiftBody(shift))) {
      setShift(NEW_SHIFT);
      setOpen("");
    }
  }
  function toggleShift(row: ShiftRow) {
    void run(`shifts/${row.id}`, "PUT", {
      ...shiftBody({ ...row, break_minutes: String(row.break_minutes), effective_to: row.effective_to || "" }),
      active: !row.active,
      version: row.version,
    });
  }
  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark">
          <Clock3 size={18} strokeWidth={2.4} /> Shifts
        </h3>
        {canEdit && open !== "shift" ? (
          <button className="primary" type="button" onClick={() => setOpen("shift")}>
            <Plus size={16} /> New shift
          </button>
        ) : null}
      </div>
      {canEdit && open === "shift" ? (
        <form className="contact-form hr-form" onSubmit={(event) => void addShift(event)}>
          <h4 className="wide">New shift</h4>
          <label>
            Shift code
            <input required value={shift.code} onChange={setS("code")} placeholder="e.g. DAY" />
          </label>
          <label>
            Name
            <input required value={shift.name} onChange={setS("name")} placeholder="e.g. Day shift" />
          </label>
          <label>
            Start time
            <input required type="time" value={shift.start_time} onChange={setS("start_time")} />
          </label>
          <label>
            End time
            <input required type="time" value={shift.end_time} onChange={setS("end_time")} />
          </label>
          <label>
            Break (minutes)
            <input type="number" min={0} max={720} value={shift.break_minutes} onChange={setS("break_minutes")} />
          </label>
          <label>
            Overnight counts on
            <select value={shift.attribution} onChange={setS("attribution")}>
              {board.attributions.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Calendar
            <input value={shift.calendar} onChange={setS("calendar")} placeholder="e.g. Mon–Sat" />
          </label>
          <label>
            Effective from
            <input required type="date" value={shift.effective_from} onChange={setS("effective_from")} />
          </label>
          <label>
            Effective to
            <input type="date" value={shift.effective_to} onChange={setS("effective_to")} />
          </label>
          <p className="wide muted">An end time at or before the start time makes the shift overnight. Attendance then counts on the day you choose.</p>
          <div className="wide hr-actions">
            <button className="primary" type="submit">
              Save shift
            </button>
            <button type="button" onClick={() => setOpen("")}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}
      {board.shifts.length === 0 ? (
        <p className="muted">No shift is defined on this project.</p>
      ) : (
        <div className="hr-shifts">
          {board.shifts.map((row) => (
            <article key={row.id} className={`hr-shift${row.active ? "" : " is-off"}${row.overnight ? " is-night" : ""}`}>
              <header>
                <strong>{row.code}</strong>
                {row.overnight ? (
                  <span className="hr-night">
                    <Moon size={12} /> Overnight
                  </span>
                ) : null}
              </header>
              <p className="hr-shift-time">
                {row.start_time} – {row.end_time}
              </p>
              <p className="muted">
                {row.name} · {row.scheduled} h scheduled · {row.break_minutes} min break
              </p>
              <p className="muted">
                Counts on {row.attribution.toLowerCase()}
                {row.calendar ? ` · ${row.calendar}` : ""} · from {row.effective_from}
                {row.effective_to ? ` to ${row.effective_to}` : ""}
              </p>
              {canEdit ? (
                <button type="button" onClick={() => toggleShift(row)}>
                  {row.active ? "Deactivate" : "Reactivate"}
                </button>
              ) : (
                <em className="muted">{row.active ? "Active" : "Inactive"}</em>
              )}
            </article>
          ))}
        </div>
      )}

      <div className="hr-toolbar">
        <h3 className="section-mark">
          <UsersRound size={18} strokeWidth={2.4} /> Crews
        </h3>
      </div>
      <p className="muted">{board.crew_note}</p>
      <p className="note-card hr-requests-moved">Crews are now built and staffed in Manpower. HR attendance and overtime keep using the same crews, shown here read only.</p>
      {board.crews.length === 0 ? (
        <p className="muted">No crew is set up on this project.</p>
      ) : (
        <div className="hr-cards">
          {board.crews.map((row) => (
            <CrewCard key={row.id} row={row} />
          ))}
        </div>
      )}
    </>
  );
}

function CrewCard({ row }: { row: CrewRow }) {
  return (
    <article className={`hr-card hr-card-crew${row.active ? "" : " is-off"}`}>
      <header>
        <strong>{row.code}</strong>
        <span className={`rel-chip ${row.active ? "hr-status-active" : "hr-status-inactive"}`}>{row.active ? "Active" : "Inactive"}</span>
      </header>
      <p className="hr-tags">
        <span>{row.company_name}</span>
        {row.discipline ? <span>{row.discipline}</span> : null}
        {row.shift ? <span>{row.shift}</span> : null}
      </p>
      <p className="muted">
        {row.lead ? `Lead ${row.lead} · ` : ""}From {row.effective_from}
        {row.effective_to ? ` to ${row.effective_to}` : ""}
      </p>
      {row.members.length === 0 ? (
        <p className="muted">No members yet.</p>
      ) : (
        <ul className="hr-checks">
          {row.members.map((m) => (
            <li key={m.id} className={m.active ? "is-verified" : "is-released"}>
              <div>
                <strong>{m.person}</strong>
                <span className="muted">
                  {m.start_date}
                  {m.end_date ? ` to ${m.end_date}` : " onward"}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function shiftTimes(board: Board, shiftId: number, day: string): [string, string] {
  const shift = board.shifts.find((row) => row.id === shiftId);
  if (!shift) return [`${day}T08:00`, `${day}T17:00`];
  const next = new Date(`${day}T00:00:00`);
  next.setDate(next.getDate() + 1);
  const pad = (n: number) => String(n).padStart(2, "0");
  const tomorrow = `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
  return [`${day}T${shift.start_time}`, `${shift.overnight ? tomorrow : day}T${shift.end_time}`];
}

function Segments({ value, onChange, fresh }: { value: [string, string][]; onChange: (next: [string, string][]) => void; fresh: [string, string] }) {
  return (
    <div className="hr-segments">
      {value.map(([a, b], index) => (
        <div key={index} className="hr-segment">
          <input type="datetime-local" aria-label="Check-in" value={a} onChange={(event) => onChange(value.map((pair, i) => (i === index ? [event.target.value, pair[1]] : pair)))} />
          <span>→</span>
          <input type="datetime-local" aria-label="Check-out" value={b} onChange={(event) => onChange(value.map((pair, i) => (i === index ? [pair[0], event.target.value] : pair)))} />
          <button type="button" aria-label="Remove segment" onClick={() => onChange(value.filter((_, i) => i !== index))}>
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...value, fresh])}>
        <Plus size={14} /> Add segment
      </button>
    </div>
  );
}

const WORKED = ["Present", "Partial Attendance"];

function Attendance({
  pid,
  board,
  admin,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  admin: boolean;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [form, setForm] = useState({ attendance_date: "", shift_id: "", crew_id: "" });
  const [lock, setLock] = useState({ period_start: "", period_end: "", reason: "" });
  const [reopen, setReopen] = useState<Record<number, string>>({});

  async function run(path: string, body: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/hr/${path}`, "POST", body);
      await reload();
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }
  async function addSheet(event: FormEvent) {
    event.preventDefault();
    const ok = await run("attendance", { attendance_date: form.attendance_date, shift_id: Number(form.shift_id), crew_id: form.crew_id ? Number(form.crew_id) : null });
    if (ok) setForm({ attendance_date: "", shift_id: "", crew_id: "" });
  }
  async function addLock(event: FormEvent) {
    event.preventDefault();
    if (await run("attendance-locks", lock)) setLock({ period_start: "", period_end: "", reason: "" });
  }
  const crews = board.crews.filter((row) => row.active && (!form.shift_id || !row.shift_id || String(row.shift_id) === form.shift_id));

  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={ATTENDANCE_ROUTES} members={board.members} disciplines={board.project_disciplines} />
      <p className="muted">{board.attendance_note}</p>
      {board.can_attend ? (
        <form className="contact-form hr-form" onSubmit={(event) => void addSheet(event)}>
          <h4 className="wide">
            <Clock3 size={16} /> Start an attendance sheet
          </h4>
          <label>
            Attendance date
            <input required type="date" value={form.attendance_date} onChange={(event) => setForm({ ...form, attendance_date: event.target.value })} />
          </label>
          <label>
            Shift
            <select required value={form.shift_id} onChange={(event) => setForm({ ...form, shift_id: event.target.value })}>
              <option value="">Choose</option>
              {board.shifts
                .filter((row) => row.active)
                .map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.code} · {row.start_time}–{row.end_time}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Crew (optional)
            <select value={form.crew_id} onChange={(event) => setForm({ ...form, crew_id: event.target.value })}>
              <option value="">Any deployed person</option>
              {crews.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.code} · {row.company_name}
                </option>
              ))}
            </select>
          </label>
          <div className="hr-actions">
            <button className="primary" type="submit" disabled={!board.shifts.length}>
              <Plus size={16} /> Start sheet
            </button>
          </div>
          {!board.shifts.length ? <p className="wide note-card note-alert">Define a shift on Crews & shifts first.</p> : null}
        </form>
      ) : null}
      {canEdit ? (
        <div className="hr-locks">
          <h3 className="section-mark">
            <Lock size={18} strokeWidth={2.4} /> Period locks
          </h3>
          <form className="hr-move" onSubmit={(event) => void addLock(event)}>
            <input required type="date" aria-label="Lock from" value={lock.period_start} onChange={(event) => setLock({ ...lock, period_start: event.target.value })} />
            <input required type="date" aria-label="Lock to" value={lock.period_end} onChange={(event) => setLock({ ...lock, period_end: event.target.value })} />
            <input aria-label="Lock reason" placeholder="Reason, e.g. week closed" value={lock.reason} onChange={(event) => setLock({ ...lock, reason: event.target.value })} />
            <button className="primary" type="submit">
              <Lock size={14} /> Lock period
            </button>
          </form>
          {board.locks.length ? (
            <ul className="hr-checks">
              {board.locks.map((row) => (
                <li key={row.id} className={row.reopened ? "is-released" : "is-verified"}>
                  <div>
                    <strong>
                      {row.period_start} to {row.period_end}
                    </strong>
                    <span className="muted">
                      Locked by {row.locked_by}
                      {row.reason ? ` · ${row.reason}` : ""}
                      {row.reopened ? ` · Reopened by ${row.reopened_by}: ${row.reopen_reason}` : ""}
                    </span>
                  </div>
                  {!row.reopened ? (
                    <div className="hr-check-act">
                      <input aria-label="Reopen reason" placeholder="Reason to reopen" value={reopen[row.id] || ""} onChange={(event) => setReopen({ ...reopen, [row.id]: event.target.value })} />
                      <button type="button" onClick={() => void run(`attendance-locks/${row.id}/reopen`, { reason: reopen[row.id] || "" })}>
                        <LockOpen size={14} /> Reopen
                      </button>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No period is locked.</p>
          )}
        </div>
      ) : null}
      <h3 className="section-mark">
        <Clock3 size={18} strokeWidth={2.4} /> Attendance sheets
      </h3>
      {board.sheets.length === 0 ? (
        <p className="muted">No attendance is recorded on this project.</p>
      ) : (
        <div className="hr-sheets">
          {board.sheets.map((row) => (
            <SheetCard key={row.id} pid={pid} row={row} board={board} onError={onError} reload={reload} run={run} />
          ))}
        </div>
      )}
    </>
  );
}

function SheetCard({
  row,
  board,
  onError,
  reload,
  run,
}: {
  pid: number;
  row: Sheet;
  board: Board;
  onError: (text: string) => void;
  reload: () => Promise<void>;
  run: (path: string, body: Record<string, unknown>) => Promise<boolean>;
}) {
  const fresh = shiftTimes(board, row.shift_id, row.attendance_date);
  const blank = { personnel_id: "", status: "Present", segments: [fresh] as [string, string][], remarks: "" };
  const [entry, setEntry] = useState(blank);
  const [fixing, setFixing] = useState<AttendanceRow | null>(null);
  const editable = board.can_attend && ["Draft", "Returned"].includes(row.status) && !row.locked;
  const crew = board.crews.find((c) => c.id === row.crew_id);
  const onSheet = new Set(row.records.map((r) => r.personnel_id));
  const people = crew
    ? board.personnel.filter((p) => crew.members.some((m) => m.personnel_id === p.id && m.active))
    : board.personnel.filter((p) => p.status === "Active" && board.deployments.some((d) => d.personnel_id === p.id && ["Mobilized", "Temporarily Unavailable", "Demobilized"].includes(d.status)));

  async function save() {
    const ok = await run(`attendance/${row.id}/records`, {
      personnel_id: Number(entry.personnel_id),
      status: entry.status,
      segments: WORKED.includes(entry.status) ? entry.segments.map(([check_in, check_out]) => ({ check_in, check_out })) : [],
      remarks: entry.remarks,
      version: row.version,
    });
    if (ok) setEntry(blank);
  }
  function edit(record: AttendanceRow) {
    setEntry({ personnel_id: String(record.personnel_id), status: record.status, segments: record.segments.length ? record.segments : [fresh], remarks: record.remarks });
  }

  return (
    <article className="hr-card hr-sheet">
      <header>
        <strong>
          {row.attendance_date} · {row.shift}
          {row.crew ? ` · Crew ${row.crew}` : ""}
        </strong>
        <span className="hr-sheet-flags">
          {row.late ? <span className="rel-chip hr-status-returned">Late submission</span> : null}
          {row.locked ? (
            <span className="rel-chip hr-status-closed">
              <Lock size={11} /> Locked
            </span>
          ) : null}
          <span className={statusClass(row.status)}>{row.status}</span>
        </span>
      </header>
      {row.submitted_by ? <p className="muted">Submitted by {row.submitted_by}</p> : null}
      {row.records.length ? (
        <div className="hr-table-wrap">
          <table className="hr-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Status</th>
                <th>Segments</th>
                <th>Worked</th>
                <th>Regular</th>
                <th>Proposed OT</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {row.records.map((record) => (
                <tr key={record.id}>
                  <td>
                    <strong>{record.person}</strong>
                    {record.on_leave ? <span className="hr-leave-flag">On approved leave</span> : null}
                    {record.remarks ? <span className="muted">{record.remarks}</span> : null}
                  </td>
                  <td>
                    <span className={`hr-att hr-att-${record.status.toLowerCase().replace(/[^a-z]+/g, "-")}`}>{record.status}</span>
                  </td>
                  <td>
                    {record.segments.length
                      ? record.segments.map(([a, b]) => (
                          <span key={a} className="hr-seg">
                            {a.slice(5).replace("T", " ")} → {b.slice(5).replace("T", " ")}
                          </span>
                        ))
                      : "—"}
                  </td>
                  <td>{record.worked}</td>
                  <td>{record.regular}</td>
                  <td className={record.overtime !== "0:00" ? "hr-ot" : ""}>{record.overtime}</td>
                  <td className="hr-row-act">
                    {editable ? (
                      <>
                        <button type="button" aria-label={`Edit ${record.person}`} onClick={() => edit(record)}>
                          <Pencil size={13} />
                        </button>
                        <button type="button" aria-label={`Remove ${record.person}`} onClick={() => void run(`attendance/${row.id}/remove`, { personnel_id: record.personnel_id, version: row.version })}>
                          <Trash2 size={13} />
                        </button>
                      </>
                    ) : null}
                    {row.status === "Approved" && !row.locked && (board.can_attend || record.own) ? (
                      <button type="button" onClick={() => setFixing(record)}>
                        <FilePenLine size={13} /> Correct
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">No one is on this sheet yet.</p>
      )}
      {editable ? (
        <div className="hr-entry">
          <select aria-label="Person" value={entry.personnel_id} onChange={(event) => setEntry({ ...entry, personnel_id: event.target.value })}>
            <option value="">{people.length ? "Choose a person" : crew ? "No active crew member" : "No mobilized person"}</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code} · {p.full_name}
                {onSheet.has(p.id) ? " (recorded)" : ""}
              </option>
            ))}
          </select>
          <select aria-label="Attendance status" value={entry.status} onChange={(event) => setEntry({ ...entry, status: event.target.value })}>
            {board.attendance_statuses.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
          <input aria-label="Remarks" placeholder="Remarks" value={entry.remarks} onChange={(event) => setEntry({ ...entry, remarks: event.target.value })} />
          {WORKED.includes(entry.status) ? <Segments value={entry.segments} onChange={(segments) => setEntry({ ...entry, segments })} fresh={fresh} /> : null}
          <div className="hr-actions">
            <button type="button" className="primary" disabled={!entry.personnel_id} onClick={() => void save()}>
              Save attendance
            </button>
            {row.status === "Draft" ? (
              <button type="button" onClick={() => void run(`attendance/${row.id}/submit`, { version: row.version })} disabled={!row.records.length}>
                Submit for review
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
      <ReviewBox review={row.status === "Pending Review" || row.review?.actions.includes("resubmit") ? row.review : null} onError={onError} reload={reload} />
      {fixing ? <CorrectionForm record={fixing} board={board} fresh={fresh} onClose={() => setFixing(null)} run={run} /> : null}
    </article>
  );
}

function CorrectionForm({
  record,
  board,
  fresh,
  onClose,
  run,
}: {
  record: AttendanceRow;
  board: Board;
  fresh: [string, string];
  onClose: () => void;
  run: (path: string, body: Record<string, unknown>) => Promise<boolean>;
}) {
  const [kind, setKind] = useState(board.correction_kinds[0] || "Missing punch");
  const [status, setStatus] = useState(record.status);
  const [segments, setSegments] = useState<[string, string][]>(record.segments.length ? record.segments : [fresh]);
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");

  async function send() {
    const ok = await run(`attendance/records/${record.id}/corrections`, {
      kind,
      status,
      segments: WORKED.includes(status) ? segments.map(([check_in, check_out]) => ({ check_in, check_out })) : [],
      reason,
      evidence,
    });
    if (ok) onClose();
  }

  return (
    <div className="hr-correction-form">
      <h4>
        <FilePenLine size={15} /> Correct {record.person}
      </h4>
      <p className="muted">
        Recorded: {record.status} · {record.worked} worked. The recorded values are kept with the correction.
      </p>
      <div className="hr-entry">
        <select aria-label="Correction type" value={kind} onChange={(event) => setKind(event.target.value)}>
          {board.correction_kinds.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
        <select aria-label="Proposed status" value={status} onChange={(event) => setStatus(event.target.value)}>
          {board.attendance_statuses.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
        {WORKED.includes(status) ? <Segments value={segments} onChange={setSegments} fresh={fresh} /> : null}
        <input aria-label="Correction reason" placeholder="Reason" value={reason} onChange={(event) => setReason(event.target.value)} />
        <input aria-label="Evidence" placeholder="Evidence, e.g. gate log page" value={evidence} onChange={(event) => setEvidence(event.target.value)} />
        <div className="hr-actions">
          <button type="button" className="primary" onClick={() => void send()}>
            Send for review
          </button>
          <button type="button" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function ValuesBox({ title, values }: { title: string; values: Values }) {
  return (
    <div className="hr-values">
      <span className="hr-values-title">{title}</span>
      <strong>{values.status}</strong>
      {values.segments.length ? (
        values.segments.map(([a, b]) => (
          <span key={a} className="hr-seg">
            {a.slice(5).replace("T", " ")} → {b.slice(5).replace("T", " ")}
          </span>
        ))
      ) : (
        <span className="muted">No times</span>
      )}
      <span className="muted">{values.worked} worked</span>
    </div>
  );
}

function Corrections({ pid, board, admin, onError, reload }: { pid: number; board: Board; admin: boolean; onError: (text: string) => void; reload: () => Promise<void> }) {
  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={CORRECTION_ROUTES} members={board.members} disciplines={board.project_disciplines} />
      <p className="muted">Approved attendance changes only through a correction. Request one from an approved sheet on the Attendance tab.</p>
      {board.corrections.length === 0 ? (
        <p className="muted">No correction has been requested.</p>
      ) : (
        <div className="hr-cards">
          {board.corrections.map((row) => (
            <article key={row.id} className="hr-card hr-card-fix">
              <header>
                <strong>
                  {row.person} · {row.attendance_date}
                </strong>
                <span className={statusClass(row.status)}>{row.status}</span>
              </header>
              <p className="hr-tags">
                <span>{row.kind}</span>
                <span>Requested by {row.requested_by}</span>
              </p>
              <div className="hr-compare">
                <ValuesBox title="Original" values={row.original} />
                <span className="hr-compare-arrow">→</span>
                <ValuesBox title="Proposed" values={row.proposed} />
              </div>
              <p className="muted">Reason: {row.reason}</p>
              <p className="muted">Evidence: {row.evidence}</p>
              {row.applied_at ? <p className="muted">Applied {row.applied_at.slice(0, 16).replace("T", " ")}</p> : null}
              <ReviewBox review={row.status === "Pending Review" || row.review?.actions.includes("resubmit") ? row.review : null} onError={onError} reload={reload} />
            </article>
          ))}
        </div>
      )}
    </>
  );
}

const NEW_LEAVE = { personnel_id: "", leave_type_id: "", start_date: "", end_date: "", partial: false, start_time: "09:00", end_time: "13:00", reason: "", evidence: "" };

function LeaveTab({
  pid,
  board,
  admin,
  canEdit,
  userId,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  admin: boolean;
  canEdit: boolean;
  userId: number;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [form, setForm] = useState(NEW_LEAVE);
  const [editing, setEditing] = useState<LeaveRow | null>(null);
  const forOthers = canEdit || board.can_attend;
  const people = board.personnel.filter((p) => p.status === "Active" && (forOthers || p.user_id === userId));
  const types = board.masters.filter((m) => m.kind === "Leave type" && (m.active || m.id === editing?.leave_type_id));

  async function run(path: string, body: Record<string, unknown>, method: "POST" | "PUT" = "POST") {
    onError("");
    try {
      await api(`/projects/${pid}/hr/${path}`, method, body);
      await reload();
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    const body: Record<string, unknown> = {
      personnel_id: Number(form.personnel_id),
      leave_type_id: Number(form.leave_type_id),
      start_date: form.start_date,
      end_date: form.partial ? form.start_date : form.end_date,
      start_time: form.partial ? form.start_time : null,
      end_time: form.partial ? form.end_time : null,
      reason: form.reason,
      evidence: form.evidence,
    };
    const ok = editing ? await run(`leave/${editing.id}`, { ...body, version: editing.version }, "PUT") : await run("leave", body);
    if (ok) {
      setForm(NEW_LEAVE);
      setEditing(null);
    }
  }
  function edit(row: LeaveRow) {
    setEditing(row);
    setForm({
      personnel_id: String(row.personnel_id),
      leave_type_id: String(row.leave_type_id),
      start_date: row.start_date,
      end_date: row.end_date,
      partial: row.start_time !== null,
      start_time: row.start_time || "09:00",
      end_time: row.end_time || "13:00",
      reason: row.reason || "",
      evidence: row.evidence || "",
    });
  }

  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={LEAVE_ROUTES} members={board.members} disciplines={board.project_disciplines} />
      <p className="muted">{board.leave_note}</p>
      {people.length ? (
        <form className="contact-form hr-form hr-leave-form" onSubmit={(event) => void save(event)}>
          <h4 className="wide">
            <CalendarOff size={16} /> {editing ? `Edit leave for ${editing.person}` : "Request leave or unavailability"}
          </h4>
          <label>
            Person
            <select required disabled={!!editing} value={form.personnel_id} onChange={(event) => setForm({ ...form, personnel_id: event.target.value })}>
              <option value="">Choose</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} · {p.full_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Leave type
            <select required value={form.leave_type_id} onChange={(event) => setForm({ ...form, leave_type_id: event.target.value })}>
              <option value="">{types.length ? "Choose" : "Add a leave type on Workforce lists"}</option>
              {types.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </label>
          <label className="hr-inline-check">
            <input type="checkbox" checked={form.partial} onChange={(event) => setForm({ ...form, partial: event.target.checked })} />
            Part of one day
          </label>
          <label>
            {form.partial ? "Date" : "From"}
            <input required type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value })} />
          </label>
          {form.partial ? (
            <>
              <label>
                From time
                <input required type="time" value={form.start_time} onChange={(event) => setForm({ ...form, start_time: event.target.value })} />
              </label>
              <label>
                To time
                <input required type="time" value={form.end_time} onChange={(event) => setForm({ ...form, end_time: event.target.value })} />
              </label>
            </>
          ) : (
            <label>
              To
              <input required type="date" min={form.start_date || undefined} value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} />
            </label>
          )}
          <label className="wide">
            Reason (restricted)
            <input value={form.reason} placeholder="Seen only by HR, the requester, and the person" onChange={(event) => setForm({ ...form, reason: event.target.value })} />
          </label>
          <label className="wide">
            Evidence (restricted)
            <input value={form.evidence} placeholder="e.g. leave form reference" onChange={(event) => setForm({ ...form, evidence: event.target.value })} />
          </label>
          <div className="hr-actions">
            <button className="primary" type="submit" disabled={!types.length}>
              {editing ? <Pencil size={16} /> : <Plus size={16} />} {editing ? "Save changes" : "Save as draft"}
            </button>
            {editing ? (
              <button
                type="button"
                onClick={() => {
                  setEditing(null);
                  setForm(NEW_LEAVE);
                }}
              >
                Cancel edit
              </button>
            ) : null}
          </div>
        </form>
      ) : null}
      <h3 className="section-mark">
        <CalendarOff size={18} strokeWidth={2.4} /> Leave on this project
      </h3>
      {board.leaves.length === 0 ? (
        <p className="muted">No leave is recorded on this project.</p>
      ) : (
        <div className="hr-cards">
          {board.leaves.map((row) => (
            <LeaveCard key={row.id} row={row} canEdit={canEdit} onEdit={() => edit(row)} onError={onError} reload={reload} run={run} />
          ))}
        </div>
      )}
    </>
  );
}

function LeaveCard({
  row,
  canEdit,
  onEdit,
  onError,
  reload,
  run,
}: {
  row: LeaveRow;
  canEdit: boolean;
  onEdit: () => void;
  onError: (text: string) => void;
  reload: () => Promise<void>;
  run: (path: string, body: Record<string, unknown>) => Promise<boolean>;
}) {
  const [reason, setReason] = useState("");
  const owner = row.mine || canEdit;
  return (
    <article className="hr-card hr-card-leave">
      <header>
        <strong>{row.person}</strong>
        <span className={statusClass(row.status)}>{row.status}</span>
      </header>
      <p className="hr-tags">
        <span>{row.leave_type}</span>
        <span>{row.duration}</span>
        <span>Requested by {row.requester}</span>
      </p>
      <p className="hr-leave-dates">
        <CalendarClock size={14} />
        {row.start_date === row.end_date ? row.start_date : `${row.start_date} → ${row.end_date}`}
        {row.start_time ? ` · ${row.start_time}–${row.end_time}` : ""}
      </p>
      {row.reason !== null ? (
        <p className="muted">
          Reason: {row.reason || "—"}
          {row.evidence ? ` · Evidence: ${row.evidence}` : ""}
        </p>
      ) : (
        <p className="muted hr-restricted">Reason restricted</p>
      )}
      {row.status_reason ? <p className="muted">Cancelled: {row.status_reason}</p> : null}
      {row.effects.length ? (
        <div className="hr-effects">
          <strong>Affects</strong>
          {row.effects.map((text) => (
            <span key={text}>{text}</span>
          ))}
        </div>
      ) : null}
      {owner && (LEAVE_OPEN.includes(row.status) || CANCELLABLE.includes(row.status)) ? (
        <div className="hr-move">
          {LEAVE_OPEN.includes(row.status) ? (
            <button type="button" onClick={onEdit}>
              <Pencil size={14} /> Edit
            </button>
          ) : null}
          {row.status === "Draft" ? (
            <button type="button" className="primary" onClick={() => void run(`leave/${row.id}/submit`, { version: row.version })}>
              Submit for approval
            </button>
          ) : null}
          <input aria-label="Cancel reason" placeholder="Reason to cancel" value={reason} onChange={(event) => setReason(event.target.value)} />
          <button type="button" className="hr-danger" onClick={() => void run(`leave/${row.id}/cancel`, { reason, version: row.version })}>
            Cancel leave
          </button>
        </div>
      ) : null}
      <ReviewBox review={row.status === "Pending Approval" || row.review?.actions.includes("resubmit") ? row.review : null} onError={onError} reload={reload} />
    </article>
  );
}

const NEW_OVERTIME = { target: "crew", personnel_id: "", crew_id: "", work_date: "", shift_id: "", package_id: "", hours: "2", reason: "" };

function OvertimeTab({
  pid,
  board,
  admin,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  admin: boolean;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [form, setForm] = useState(NEW_OVERTIME);
  const deployed = board.personnel.filter(
    (p) => p.status === "Active" && board.deployments.some((d) => d.personnel_id === p.id && ["Approved for Mobilization", "Mobilized", "Temporarily Unavailable"].includes(d.status)),
  );

  async function run(path: string, body: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/hr/${path}`, "POST", body);
      await reload();
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    const ok = await run("overtime", {
      personnel_id: form.target === "person" ? Number(form.personnel_id) : null,
      crew_id: form.target === "crew" ? Number(form.crew_id) : null,
      work_date: form.work_date,
      shift_id: Number(form.shift_id),
      package_id: form.package_id ? Number(form.package_id) : null,
      requested_minutes: Math.round(Number(form.hours) * 60),
      reason: form.reason,
    });
    if (ok) setForm(NEW_OVERTIME);
  }

  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={OVERTIME_ROUTES} members={board.members} disciplines={board.project_disciplines} />
      <p className="muted">{board.overtime_note}</p>
      {board.can_attend ? (
        <form className="contact-form hr-form hr-ot-form" onSubmit={(event) => void save(event)}>
          <h4 className="wide">
            <Timer size={16} /> Request overtime
          </h4>
          <div className="wide hr-segmented" role="radiogroup" aria-label="Overtime for">
            {(["crew", "person"] as const).map((name) => (
              <button key={name} type="button" role="radio" aria-checked={form.target === name} className={form.target === name ? "is-on" : ""} onClick={() => setForm({ ...form, target: name })}>
                {name === "crew" ? <UsersRound size={14} /> : <UserRoundCheck size={14} />} {name === "crew" ? "A crew" : "One person"}
              </button>
            ))}
          </div>
          {form.target === "crew" ? (
            <label>
              Crew
              <select required value={form.crew_id} onChange={(event) => setForm({ ...form, crew_id: event.target.value })}>
                <option value="">{board.crews.some((c) => c.active) ? "Choose" : "No active crew"}</option>
                {board.crews
                  .filter((c) => c.active)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code} · {c.company_name}
                    </option>
                  ))}
              </select>
            </label>
          ) : (
            <label>
              Person
              <select required value={form.personnel_id} onChange={(event) => setForm({ ...form, personnel_id: event.target.value })}>
                <option value="">{deployed.length ? "Choose" : "No deployed person"}</option>
                {deployed.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.code} · {p.full_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Work date
            <input required type="date" value={form.work_date} onChange={(event) => setForm({ ...form, work_date: event.target.value })} />
          </label>
          <label>
            Shift
            <select required value={form.shift_id} onChange={(event) => setForm({ ...form, shift_id: event.target.value })}>
              <option value="">Choose</option>
              {board.shifts
                .filter((s) => s.active)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} · {s.start_time}–{s.end_time}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Work package (optional)
            <select value={form.package_id} onChange={(event) => setForm({ ...form, package_id: event.target.value })}>
              <option value="">None</option>
              {board.packages.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Hours requested
            <input required type="number" min="0.25" max="16" step="0.25" value={form.hours} onChange={(event) => setForm({ ...form, hours: event.target.value })} />
          </label>
          <label className="wide">
            Reason
            <input required minLength={3} value={form.reason} placeholder="e.g. Slab pour must finish before curing window" onChange={(event) => setForm({ ...form, reason: event.target.value })} />
          </label>
          <div className="hr-actions">
            <button className="primary" type="submit" disabled={!board.shifts.length}>
              <Plus size={16} /> Save as draft
            </button>
          </div>
          {!board.shifts.length ? <p className="wide note-card note-alert">Define a shift on Crews & shifts first.</p> : null}
        </form>
      ) : null}
      <h3 className="section-mark">
        <Timer size={18} strokeWidth={2.4} /> Overtime on this project
      </h3>
      {board.overtime.length === 0 ? (
        <p className="muted">No overtime is requested on this project.</p>
      ) : (
        <div className="hr-cards">
          {board.overtime.map((row) => (
            <OvertimeCard key={row.id} row={row} canEdit={canEdit} onError={onError} reload={reload} run={run} />
          ))}
        </div>
      )}
    </>
  );
}

function OvertimeCard({
  row,
  canEdit,
  onError,
  reload,
  run,
}: {
  row: OvertimeRow;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
  run: (path: string, body: Record<string, unknown>) => Promise<boolean>;
}) {
  const [reason, setReason] = useState("");
  const [hours, setHours] = useState(String((row.approved_minutes ?? row.requested_minutes) / 60));
  const owner = row.mine || canEdit;
  return (
    <article className="hr-card hr-card-ot">
      <header>
        <strong>
          {row.target} · {row.work_date}
        </strong>
        <span className={statusClass(row.status)}>{row.status}</span>
      </header>
      <p className="hr-tags">
        <span>Shift {row.shift}</span>
        {row.package ? <span>{row.package}</span> : null}
        <span>Requested by {row.requester}</span>
      </p>
      <p className="muted">{row.reason}</p>
      <div className="hr-demand hr-ot-hours">
        <span>
          <strong>{row.requested}</strong>Requested
        </span>
        <span className={row.approved ? "is-good" : ""}>
          <strong>{row.approved ?? "—"}</strong>Approved
        </span>
      </div>
      {row.lines.length ? (
        <div className="hr-table-wrap">
          <table className="hr-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Attended OT</th>
                <th>Payable</th>
              </tr>
            </thead>
            <tbody>
              {row.lines.map((line) => (
                <tr key={line.personnel_id}>
                  <td>
                    <strong>{line.person}</strong>
                  </td>
                  <td className={line.attended !== "0:00" ? "hr-ot" : ""}>{line.attended}</td>
                  <td className={line.payable !== "0:00" ? "hr-payable" : ""}>{line.payable}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {row.status_reason ? <p className="muted">Cancelled: {row.status_reason}</p> : null}
      {row.can_set_hours ? (
        <div className="hr-move">
          <label className="hr-hours">
            Approved hours
            <input type="number" min="0" max={row.requested_minutes / 60} step="0.25" value={hours} onChange={(event) => setHours(event.target.value)} />
          </label>
          <button type="button" onClick={() => void run(`overtime/${row.id}/hours`, { approved_minutes: Math.round(Number(hours) * 60), version: row.version })}>
            <Clock3 size={14} /> Set approved hours
          </button>
        </div>
      ) : null}
      {owner && CANCELLABLE.includes(row.status) ? (
        <div className="hr-move">
          {row.status === "Draft" ? (
            <button type="button" className="primary" onClick={() => void run(`overtime/${row.id}/submit`, { version: row.version })}>
              Submit for approval
            </button>
          ) : null}
          <input aria-label="Cancel reason" placeholder="Reason to cancel" value={reason} onChange={(event) => setReason(event.target.value)} />
          <button type="button" className="hr-danger" onClick={() => void run(`overtime/${row.id}/cancel`, { reason, version: row.version })}>
            Cancel overtime
          </button>
        </div>
      ) : null}
      <ReviewBox review={row.status === "Pending Approval" || row.review?.actions.includes("resubmit") ? row.review : null} onError={onError} reload={reload} />
    </article>
  );
}

function Reconciliation({ board }: { board: Board }) {
  const [onlyExceptions, setOnlyExceptions] = useState(false);
  const rows = onlyExceptions ? board.reconciliation.filter((row) => row.exceptions.length) : board.reconciliation;
  const flagged = board.reconciliation.filter((row) => row.exceptions.length).length;
  return (
    <>
      <p className="muted">{board.reconciliation_note}</p>
      <div className="hr-recon-head">
        <h3 className="section-mark">
          <Scale size={18} strokeWidth={2.4} /> Attendance against activity hours since {board.reconciliation_from}
        </h3>
        <div className="hr-segmented hr-recon-filter" role="radiogroup" aria-label="Rows">
          <button type="button" role="radio" aria-checked={!onlyExceptions} className={!onlyExceptions ? "is-on" : ""} onClick={() => setOnlyExceptions(false)}>
            All ({board.reconciliation.length})
          </button>
          <button type="button" role="radio" aria-checked={onlyExceptions} className={onlyExceptions ? "is-on" : ""} onClick={() => setOnlyExceptions(true)}>
            Exceptions ({flagged})
          </button>
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="muted">{onlyExceptions ? "No exception in this period." : "No approved attendance or approved activity hours in this period."}</p>
      ) : (
        <div className="hr-table-wrap">
          <table className="hr-table hr-recon">
            <thead>
              <tr>
                <th>Date</th>
                <th>Person</th>
                <th>Attendance</th>
                <th>Activity</th>
                <th>Idle</th>
                <th>Unallocated</th>
                <th>OT attended</th>
                <th>OT approved</th>
                <th>OT payable</th>
                <th>Exceptions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.date}-${row.personnel_id}`} className={row.exceptions.length ? "is-flagged" : ""}>
                  <td>{row.date}</td>
                  <td>
                    <strong>{row.person}</strong>
                  </td>
                  <td>{row.attendance}</td>
                  <td className="hr-recon-act">{row.activity}</td>
                  <td>{row.idle}</td>
                  <td className={row.unallocated !== "0:00" ? "hr-recon-gap" : ""}>{row.unallocated}</td>
                  <td className={row.overtime_attended !== "0:00" ? "hr-ot" : ""}>{row.overtime_attended}</td>
                  <td>{row.overtime_approved}</td>
                  <td className={row.overtime_payable !== "0:00" ? "hr-payable" : ""}>{row.overtime_payable}</td>
                  <td>
                    {row.exceptions.length ? (
                      row.exceptions.map((text) => (
                        <span key={text} className="hr-recon-flag">
                          {text}
                        </span>
                      ))
                    ) : (
                      <span className="hr-recon-ok">Matches</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

const OFFBOARDING_ROUTES = [{ recordType: "hr.offboarding", label: "Demobilization approver", stage: "Demobilization approval" }];
const OFFBOARDING_OPEN = ["Draft", "Pending Approval", "Returned"];
const NEW_OFFBOARDING = { deployment_id: "", last_working_date: "", reason: "" };

function OffboardingTab({
  pid,
  board,
  admin,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  admin: boolean;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [form, setForm] = useState(NEW_OFFBOARDING);
  const busy = new Set(board.offboardings.filter((row) => OFFBOARDING_OPEN.includes(row.status)).map((row) => row.deployment_id));
  const leaving = board.deployments.filter((row) => ["Mobilized", "Temporarily Unavailable"].includes(row.status) && !busy.has(row.id));
  const chosen = leaving.find((row) => String(row.id) === form.deployment_id);

  async function run(path: string, body: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/hr/${path}`, "POST", body);
      await reload();
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }
  async function start(event: FormEvent) {
    event.preventDefault();
    const ok = await run("offboardings", { deployment_id: Number(form.deployment_id), last_working_date: form.last_working_date, reason: form.reason });
    if (ok) setForm(NEW_OFFBOARDING);
  }

  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={OFFBOARDING_ROUTES} members={board.members} disciplines={board.project_disciplines} />
      <p className="muted">{board.offboarding_note}</p>
      {canEdit ? (
        leaving.length ? (
          <form className="contact-form hr-form hr-off-form" onSubmit={(event) => void start(event)}>
            <h4 className="wide">
              <LogOut size={16} /> Start demobilization
            </h4>
            <label>
              Deployment
              <select required value={form.deployment_id} onChange={(event) => setForm({ ...form, deployment_id: event.target.value })}>
                <option value="">Choose</option>
                {leaving.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.person} · {row.status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Last working date
              <input
                required
                type="date"
                min={chosen?.actual_start || undefined}
                value={form.last_working_date}
                onChange={(event) => setForm({ ...form, last_working_date: event.target.value })}
              />
            </label>
            <label className="wide">
              Reason
              <input value={form.reason} placeholder="e.g. scope complete, transfer, end of contract" onChange={(event) => setForm({ ...form, reason: event.target.value })} />
            </label>
            <div className="hr-actions">
              <button className="primary" type="submit">
                <Plus size={16} /> Start checklist
              </button>
            </div>
          </form>
        ) : (
          <p className="muted">No mobilized deployment is waiting to be demobilized.</p>
        )
      ) : null}
      <h3 className="section-mark hr-off-mark">
        <LogOut size={18} strokeWidth={2.4} /> Demobilizations on this project
      </h3>
      {board.offboardings.length === 0 ? (
        <p className="muted">No demobilization has been started on this project.</p>
      ) : (
        <div className="hr-cards hr-off-cards">
          {board.offboardings.map((row) => (
            <OffboardingCard key={row.id} row={row} canEdit={canEdit} onError={onError} reload={reload} run={run} />
          ))}
        </div>
      )}
    </>
  );
}

function OffboardingItemRow({
  item,
  editable,
  path,
  run,
}: {
  item: OffboardingRow["items"][number];
  editable: boolean;
  path: string;
  run: (path: string, body: Record<string, unknown>) => Promise<boolean>;
}) {
  const [status, setStatus] = useState(item.status);
  const [note, setNote] = useState(item.note);
  const changed = status !== item.status || note !== item.note;
  return (
    <li className={`hr-off-item is-${item.status.toLowerCase().replace(/\s+/g, "-")}`}>
      <span className="hr-off-item-name">{item.item}</span>
      {editable ? (
        <>
          <select aria-label={`${item.item} status`} value={status} onChange={(event) => setStatus(event.target.value)}>
            <option>Pending</option>
            <option>Done</option>
            <option>Not applicable</option>
          </select>
          <input aria-label={`${item.item} note`} placeholder="What was done, or why it does not apply" value={note} onChange={(event) => setNote(event.target.value)} />
          <button type="button" disabled={!changed} onClick={() => void run(path, { status, note, version: item.version })}>
            Save
          </button>
        </>
      ) : (
        <>
          <span className={statusClass(item.status)}>{item.status}</span>
          {item.note ? <span className="muted">{item.note}</span> : null}
          {item.done_by ? <span className="muted">· {item.done_by}</span> : null}
        </>
      )}
    </li>
  );
}

function OffboardingCard({
  row,
  canEdit,
  onError,
  reload,
  run,
}: {
  row: OffboardingRow;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
  run: (path: string, body: Record<string, unknown>) => Promise<boolean>;
}) {
  const [reason, setReason] = useState("");
  const editable = canEdit && ["Draft", "Returned"].includes(row.status);
  const found = row.findings;
  const done = row.items.filter((item) => item.status !== "Pending").length;
  return (
    <article className="hr-card hr-card-off">
      <header>
        <strong>{row.person}</strong>
        <span className={statusClass(row.status)}>{row.status}</span>
      </header>
      <p className="hr-leave-dates hr-off-dates">
        <CalendarClock size={14} /> Last working date {row.last_working_date}
      </p>
      <p className="muted">
        {row.reason ? `${row.reason} · ` : ""}Started by {row.requester}
        {row.status_reason ? ` · ${row.status_reason}` : ""}
      </p>
      {found ? (
        <div className="hr-off-findings">
          <span className={found.open_tasks.length ? "is-bad" : "is-ok"}>
            {found.open_tasks.length ? `${found.open_tasks.length} open task${found.open_tasks.length === 1 ? "" : "s"}` : "No open tasks"}
          </span>
          <span className={found.pending_sheets.length || found.pending_corrections ? "is-bad" : "is-ok"}>
            {found.pending_sheets.length || found.pending_corrections
              ? `Timesheets waiting: ${found.pending_sheets.length} sheet${found.pending_sheets.length === 1 ? "" : "s"}, ${found.pending_corrections} correction${found.pending_corrections === 1 ? "" : "s"}`
              : "No timesheets waiting"}
          </span>
          {found.attendance_after_last_day ? <span className="is-bad">Attendance after the last day</span> : null}
          <span className={found.crew_memberships || found.allocations ? "is-info" : "is-ok"}>
            {found.crew_memberships} crew · {found.allocations} allocation{found.allocations === 1 ? "" : "s"} end on approval
          </span>
          <span className={found.project_memberships ? "is-info" : "is-ok"}>
            {!found.login_active
              ? "No active login"
              : found.project_memberships
                ? "Login still has access here; admin review on approval"
                : "Login has no access here"}
          </span>
          {found.login_active && found.other_project_memberships ? (
            <span className="is-info">Access on {found.other_project_memberships} other project{found.other_project_memberships === 1 ? "" : "s"} is not touched</span>
          ) : null}
        </div>
      ) : null}
      {found && found.open_tasks.length ? (
        <ul className="hr-off-tasks">
          {found.open_tasks.map((task) => (
            <li key={task.id}>
              {task.title}
              {task.due_date ? <span className="muted"> · due {task.due_date}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="hr-off-progress">
        Checklist {done} of {row.items.length}
        <span className="hr-off-bar">
          <span style={{ width: `${row.items.length ? (done / row.items.length) * 100 : 0}%` }} />
        </span>
      </p>
      <ul className="hr-off-items">
        {row.items.map((item) => (
          <OffboardingItemRow key={`${item.id}-${item.version}`} item={item} editable={editable} path={`offboardings/${row.id}/items/${item.id}`} run={run} />
        ))}
      </ul>
      {editable ? (
        <div className="hr-move">
          {row.status === "Draft" ? (
            <button type="button" className="primary" onClick={() => void run(`offboardings/${row.id}/submit`, { version: row.version })}>
              Submit for approval
            </button>
          ) : null}
          <input aria-label="Cancel reason" placeholder="Reason to cancel" value={reason} onChange={(event) => setReason(event.target.value)} />
          <button type="button" className="hr-danger" onClick={() => void run(`offboardings/${row.id}/cancel`, { reason, version: row.version })}>
            Cancel
          </button>
        </div>
      ) : null}
      <ReviewBox review={row.status === "Pending Approval" || row.review?.actions.includes("resubmit") ? row.review : null} onError={onError} reload={reload} />
    </article>
  );
}

function AlertsTab({
  pid,
  board,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const saved = board.monitor_settings;
  const [form, setForm] = useState({
    enabled: saved.saved ? saved.enabled : true,
    mobilization_grace_days: String(saved.mobilization_grace_days),
    onboarding_lead_days: String(saved.onboarding_lead_days),
    attendance_grace_days: String(saved.attendance_grace_days),
    escalate_after_days: String(saved.escalate_after_days),
    escalation_user_ids: saved.escalation_user_ids,
  });
  const [onlyEscalated, setOnlyEscalated] = useState(false);
  const alerts = onlyEscalated ? board.alerts.filter((row) => row.escalated) : board.alerts;
  const escalatedCount = board.alerts.filter((row) => row.escalated).length;

  async function save(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hr/monitor`, "PUT", {
        enabled: form.enabled,
        mobilization_grace_days: Number(form.mobilization_grace_days),
        onboarding_lead_days: Number(form.onboarding_lead_days),
        attendance_grace_days: Number(form.attendance_grace_days),
        escalate_after_days: Number(form.escalate_after_days),
        escalation_user_ids: form.escalation_user_ids,
        version: saved.version,
      });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  function toggle(id: number) {
    const has = form.escalation_user_ids.includes(id);
    setForm({ ...form, escalation_user_ids: has ? form.escalation_user_ids.filter((x) => x !== id) : [...form.escalation_user_ids, id] });
  }

  return (
    <>
      <p className="muted">{board.monitor_note}</p>
      <p className={`hr-alert-state ${saved.saved && saved.enabled ? "is-on" : "is-off"}`}>
        <BellRing size={15} />
        {saved.saved
          ? saved.enabled
            ? `Sending is on. Escalates after ${saved.escalate_after_days} days to ${board.escalation_names.join(", ") || "nobody yet"}.`
            : "Sending is turned off for this project."
          : "Settings are not saved yet, so no notification is sent. Alerts below are still worked out."}
      </p>
      {canEdit ? (
        <form className="contact-form hr-form hr-alert-form" onSubmit={(event) => void save(event)}>
          <h4 className="wide">
            <BellRing size={16} /> Alert settings
          </h4>
          <label className="hr-inline-check">
            <input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />
            Send notifications
          </label>
          <label>
            Mobilization grace (days)
            <input type="number" min={0} max={60} value={form.mobilization_grace_days} onChange={(event) => setForm({ ...form, mobilization_grace_days: event.target.value })} />
          </label>
          <label>
            Onboarding warning before start (days)
            <input type="number" min={0} max={60} value={form.onboarding_lead_days} onChange={(event) => setForm({ ...form, onboarding_lead_days: event.target.value })} />
          </label>
          <label>
            Attendance checked after (days)
            <input type="number" min={1} max={14} value={form.attendance_grace_days} onChange={(event) => setForm({ ...form, attendance_grace_days: event.target.value })} />
          </label>
          <label>
            Escalate after (days)
            <input type="number" min={1} max={60} value={form.escalate_after_days} onChange={(event) => setForm({ ...form, escalate_after_days: event.target.value })} />
          </label>
          <fieldset className="wide hr-alert-people">
            <legend>Escalation recipients</legend>
            {board.members.map((member) => (
              <label key={member.id} className={form.escalation_user_ids.includes(member.id) ? "is-on" : ""}>
                <input type="checkbox" checked={form.escalation_user_ids.includes(member.id)} onChange={() => toggle(member.id)} />
                {member.name}
              </label>
            ))}
          </fieldset>
          <div className="hr-actions">
            <button className="primary" type="submit">
              Save settings
            </button>
          </div>
        </form>
      ) : null}
      <div className="hr-recon-head">
        <h3 className="section-mark hr-alert-mark">
          <BellRing size={18} strokeWidth={2.4} /> Open alerts
        </h3>
        <div className="hr-segmented hr-alert-filter" role="radiogroup" aria-label="Alerts">
          <button type="button" role="radio" aria-checked={!onlyEscalated} className={!onlyEscalated ? "is-on" : ""} onClick={() => setOnlyEscalated(false)}>
            All ({board.alerts.length})
          </button>
          <button type="button" role="radio" aria-checked={onlyEscalated} className={onlyEscalated ? "is-on" : ""} onClick={() => setOnlyEscalated(true)}>
            Escalated ({escalatedCount})
          </button>
        </div>
      </div>
      {alerts.length === 0 ? (
        <p className="muted">{onlyEscalated ? "Nothing has escalated." : "No open alert on this project."}</p>
      ) : (
        <ul className="hr-alerts">
          {alerts.map((row) => (
            <li key={`${row.key}-${row.since}`} className={row.escalated ? "is-escalated" : ""}>
              <div>
                <strong>{row.kind}</strong>
                {row.escalated ? <span className="hr-alert-esc">Escalated</span> : null}
                <span className="hr-alert-age">
                  open {row.age_days} day{row.age_days === 1 ? "" : "s"} · since {row.since}
                </span>
              </div>
              <p>{row.body}</p>
              <p className="muted">Goes to {row.recipients.filter(Boolean).join(", ") || "nobody with a login"}</p>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

const NEW_TYPE = { name: "", owner: "HSE", requires_expiry: true };
const NEW_RULE = { type_id: "", package_id: "", activity_id: "" };
const NEW_CREDENTIAL = { personnel_id: "", type_id: "", certificate_number: "", issuer: "", issue_date: "", expiry_date: "", evidence: "", applicable_activities: "" };
const CREDENTIAL_VIEWS = ["All", "Waiting", "Expiring or expired"] as const;

function ownerClass(owner: string) {
  return `hr-owner hr-owner-${owner.toLowerCase().replace(/[^a-z]/g, "")}`;
}

function Qualifications({
  pid,
  board,
  canEdit,
  userId,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canEdit: boolean;
  userId: number;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [typeForm, setTypeForm] = useState(NEW_TYPE);
  const [ruleForm, setRuleForm] = useState(NEW_RULE);
  const [form, setForm] = useState(NEW_CREDENTIAL);
  const [view, setView] = useState<(typeof CREDENTIAL_VIEWS)[number]>("All");
  const verifies = board.credential_owners_i_verify;
  const ruleTypes = board.credential_types.filter((t) => t.active && (canEdit || verifies.includes(t.owner)));
  const activeTypes = board.credential_types.filter((t) => t.active);
  const people = board.personnel.filter((p) => p.status === "Active" && (canEdit || p.user_id === userId));
  const chosenType = activeTypes.find((t) => String(t.id) === form.type_id);
  const activities = board.activities.filter((a) => !ruleForm.package_id || String(a.package_id) === ruleForm.package_id);
  const shown = board.credentials.filter((row) =>
    view === "Waiting" ? row.status === "Pending Verification" : view === "Expiring or expired" ? ["Expiring", "Expired"].includes(row.state) : true,
  );

  async function run(path: string, body: Record<string, unknown> | null, method: "POST" | "PUT" | "DELETE" = "POST") {
    onError("");
    try {
      await api(`/projects/${pid}/hr/${path}`, method, body ?? undefined);
      await reload();
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }
  async function addType(event: FormEvent) {
    event.preventDefault();
    if (await run("credential-types", typeForm)) setTypeForm(NEW_TYPE);
  }
  async function addRule(event: FormEvent) {
    event.preventDefault();
    const body = {
      type_id: Number(ruleForm.type_id),
      package_id: ruleForm.package_id ? Number(ruleForm.package_id) : null,
      activity_id: ruleForm.activity_id ? Number(ruleForm.activity_id) : null,
    };
    if (await run("credential-rules", body)) setRuleForm(NEW_RULE);
  }
  async function addCredential(event: FormEvent) {
    event.preventDefault();
    const body = {
      ...form,
      personnel_id: Number(form.personnel_id),
      type_id: Number(form.type_id),
      expiry_date: form.expiry_date || null,
    };
    if (await run("credentials", body)) setForm(NEW_CREDENTIAL);
  }

  return (
    <>
      <p className="muted">{board.credential_note}</p>

      <h3 className="section-mark hr-qual-mark">
        <Award size={18} strokeWidth={2.4} /> Qualification types
      </h3>
      {board.credential_types.length === 0 ? (
        <p className="muted">No qualification type yet. HR adds each type and names who verifies it.</p>
      ) : (
        <div className="hr-qual-types">
          {board.credential_types.map((t) => (
            <span key={t.id} className={`hr-qual-type${t.active ? "" : " is-off"}`}>
              <strong>{t.name}</strong>
              <span className={ownerClass(t.owner)}>{t.owner}</span>
              {!t.requires_expiry ? <em>No expiry</em> : null}
              {canEdit ? (
                <button
                  type="button"
                  onClick={() => void run(`credential-types/${t.id}`, { name: t.name, owner: t.owner, requires_expiry: t.requires_expiry, active: !t.active, version: t.version }, "PUT")}
                >
                  {t.active ? "Retire" : "Restore"}
                </button>
              ) : null}
            </span>
          ))}
        </div>
      )}
      {canEdit ? (
        <form className="contact-form hr-form hr-qual-form" onSubmit={(event) => void addType(event)}>
          <h4 className="wide">
            <Plus size={16} /> Add a qualification type
          </h4>
          <label>
            Name
            <input required minLength={2} value={typeForm.name} placeholder="e.g. Working at height" onChange={(event) => setTypeForm({ ...typeForm, name: event.target.value })} />
          </label>
          <label>
            Verified by
            <select value={typeForm.owner} onChange={(event) => setTypeForm({ ...typeForm, owner: event.target.value })}>
              <option value="HSE">HSE</option>
              <option value="QA/QC">QA/QC</option>
              <option value="HR">HR</option>
            </select>
          </label>
          <label className="hr-inline-check">
            <input type="checkbox" checked={typeForm.requires_expiry} onChange={(event) => setTypeForm({ ...typeForm, requires_expiry: event.target.checked })} />
            Needs an expiry date
          </label>
          <div className="hr-actions">
            <button className="primary" type="submit">
              <Plus size={16} /> Add type
            </button>
          </div>
          <p className="muted wide">An HSE type with the same name as an HSE eligibility category also counts there for a linked login.</p>
        </form>
      ) : null}

      <h3 className="section-mark hr-qual-mark">
        <ShieldCheck size={18} strokeWidth={2.4} /> Project requirements
      </h3>
      <p className="muted">{board.rule_note}</p>
      {board.credential_rules.length === 0 ? (
        <p className="muted">No requirement on this project. Nobody is blocked for a qualification.</p>
      ) : (
        <ul className="hr-qual-rules">
          {board.credential_rules.map((rule) => (
            <li key={rule.id} className={rule.active ? "" : "is-off"}>
              <strong>{rule.type}</strong>
              <span className={ownerClass(rule.owner)}>{rule.owner}</span>
              <span className="hr-qual-scope">{rule.scope}</span>
              {!rule.active ? <em>Type retired, not enforced</em> : null}
              {canEdit || verifies.includes(rule.owner) ? (
                <button type="button" className="labour-remove" aria-label={`Remove ${rule.type} requirement`} onClick={() => void run(`credential-rules/${rule.id}`, null, "DELETE")}>
                  <Trash2 size={13} />
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {ruleTypes.length ? (
        <form className="contact-form hr-form hr-qual-form" onSubmit={(event) => void addRule(event)}>
          <h4 className="wide">
            <ShieldCheck size={16} /> Require a qualification
          </h4>
          <label>
            Qualification
            <select required value={ruleForm.type_id} onChange={(event) => setRuleForm({ ...ruleForm, type_id: event.target.value })}>
              <option value="">Choose</option>
              {ruleTypes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} · {t.owner}
                </option>
              ))}
            </select>
          </label>
          <label>
            Work package
            <select value={ruleForm.package_id} onChange={(event) => setRuleForm({ ...ruleForm, package_id: event.target.value, activity_id: "" })}>
              <option value="">Whole project</option>
              {board.packages.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Activity
            <select value={ruleForm.activity_id} onChange={(event) => setRuleForm({ ...ruleForm, activity_id: event.target.value })}>
              <option value="">{ruleForm.package_id ? "Whole package" : "Any activity"}</option>
              {activities.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <div className="hr-actions">
            <button className="primary" type="submit">
              <Plus size={16} /> Add requirement
            </button>
          </div>
        </form>
      ) : null}

      <h3 className="section-mark hr-qual-mark">
        <UserRoundCheck size={18} strokeWidth={2.4} /> Eligibility today
      </h3>
      <p className="muted">{board.eligibility_note}</p>
      {board.eligibility.length === 0 ? (
        <p className="muted">Nobody has an open deployment on this project.</p>
      ) : (
        <div className="hr-table-wrap">
          <table className="hr-table hr-qual-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Deployment</th>
                <th>Project-wide</th>
                <th>Requirements</th>
                <th>Package and activity</th>
              </tr>
            </thead>
            <tbody>
              {board.eligibility.map((row) => (
                <tr key={row.personnel_id} className={row.status !== "Eligible" ? "is-flagged" : ""}>
                  <td>
                    <strong>{row.person}</strong>
                  </td>
                  <td>{row.deployment_status}</td>
                  <td>
                    <span className={statusClass(row.status)}>{row.status}</span>
                  </td>
                  <td>
                    {row.items.length
                      ? row.items.map((item) => (
                          <span key={item.type_id} className={`hr-qual-pill ${statusClass(item.status)}`}>
                            {item.type}: {item.status}
                          </span>
                        ))
                      : <span className="muted">None</span>}
                  </td>
                  <td>
                    {row.scoped.length
                      ? row.scoped.map((item) => (
                          <span key={item.rule_id} className={`hr-qual-pill ${statusClass(item.status)}`}>
                            {item.type} · {item.scope}: {item.status}
                          </span>
                        ))
                      : <span className="muted">None</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {people.length && activeTypes.length ? (
        <form className="contact-form hr-form hr-qual-form" onSubmit={(event) => void addCredential(event)}>
          <h4 className="wide">
            <BadgeCheck size={16} /> Record a qualification
          </h4>
          <label>
            Person
            <select required value={form.personnel_id} onChange={(event) => setForm({ ...form, personnel_id: event.target.value })}>
              <option value="">Choose</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} · {p.full_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Qualification
            <select required value={form.type_id} onChange={(event) => setForm({ ...form, type_id: event.target.value })}>
              <option value="">Choose</option>
              {activeTypes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} · verified by {t.owner}
                </option>
              ))}
            </select>
          </label>
          <label>
            Certificate number
            <input value={form.certificate_number} onChange={(event) => setForm({ ...form, certificate_number: event.target.value })} />
          </label>
          <label>
            Issuer
            <input value={form.issuer} onChange={(event) => setForm({ ...form, issuer: event.target.value })} />
          </label>
          <label>
            Issued on
            <input required type="date" value={form.issue_date} onChange={(event) => setForm({ ...form, issue_date: event.target.value })} />
          </label>
          <label>
            Expires on{chosenType && !chosenType.requires_expiry ? " (optional)" : ""}
            <input
              type="date"
              required={!chosenType || chosenType.requires_expiry}
              min={form.issue_date || undefined}
              value={form.expiry_date}
              onChange={(event) => setForm({ ...form, expiry_date: event.target.value })}
            />
          </label>
          <label className="wide">
            Evidence
            <input required minLength={3} value={form.evidence} placeholder="e.g. card sighted, copy on file" onChange={(event) => setForm({ ...form, evidence: event.target.value })} />
          </label>
          <label className="wide">
            Applicable activities
            <input value={form.applicable_activities} placeholder="Optional" onChange={(event) => setForm({ ...form, applicable_activities: event.target.value })} />
          </label>
          <div className="hr-actions">
            <button className="primary" type="submit">
              <Plus size={16} /> Save for verification
            </button>
          </div>
        </form>
      ) : null}

      <div className="hr-recon-head">
        <h3 className="section-mark hr-qual-mark">
          <BadgeCheck size={18} strokeWidth={2.4} /> Qualification records
        </h3>
        <div className="hr-segmented hr-qual-filter" role="radiogroup" aria-label="Records">
          {CREDENTIAL_VIEWS.map((name) => (
            <button key={name} type="button" role="radio" aria-checked={view === name} className={view === name ? "is-on" : ""} onClick={() => setView(name)}>
              {name}
            </button>
          ))}
        </div>
      </div>
      {shown.length === 0 ? (
        <p className="muted">{board.credentials.length ? "No record in this view." : "No qualification is recorded for people of this project's companies."}</p>
      ) : (
        <div className="hr-cards">
          {shown.map((row) => (
            <CredentialCard key={row.id} row={row} run={run} />
          ))}
        </div>
      )}
    </>
  );
}

function CredentialCard({
  row,
  run,
}: {
  row: CredentialRow;
  run: (path: string, body: Record<string, unknown> | null) => Promise<boolean>;
}) {
  const [reason, setReason] = useState("");
  return (
    <article className={`hr-card hr-card-qual${row.state === "Expired" ? " is-expired" : ""}`}>
      <header>
        <strong>{row.person}</strong>
        <span className={statusClass(row.state)}>{row.state}</span>
      </header>
      <p className="hr-tags">
        <span>{row.type}</span>
        <span className={ownerClass(row.owner)}>Verified by {row.owner}</span>
        {row.superseded ? <span>Renewed</span> : null}
      </p>
      <p className="hr-leave-dates hr-qual-dates">
        <CalendarClock size={14} />
        Issued {row.issue_date}
        {row.expiry_date ? ` · expires ${row.expiry_date}` : " · no expiry"}
      </p>
      <p className="muted">
        {row.certificate_number ? `Certificate ${row.certificate_number}` : "No certificate number"}
        {row.issuer ? ` · ${row.issuer}` : ""}
      </p>
      <p className="muted">Evidence: {row.evidence}</p>
      {row.applicable_activities ? <p className="muted">Applies to: {row.applicable_activities}</p> : null}
      <p className="muted">
        Entered by {row.created_by}
        {row.verified_by ? ` · verified by ${row.verified_by}` : ""}
      </p>
      {row.decision_reason ? <p className="muted">Note: {row.decision_reason}</p> : null}
      {row.decide_block ? <p className="muted hr-restricted">{row.decide_block}</p> : null}
      {row.can_decide || row.can_withdraw ? (
        <div className="hr-move">
          <input aria-label="Reason" placeholder={row.can_decide ? "Reason, required to reject" : "Reason to withdraw"} value={reason} onChange={(event) => setReason(event.target.value)} />
          {row.can_decide ? (
            <>
              <button type="button" className="primary" onClick={() => void run(`credentials/${row.id}/decide`, { action: "verify", reason, version: row.version })}>
                <BadgeCheck size={14} /> Verify
              </button>
              <button type="button" onClick={() => void run(`credentials/${row.id}/decide`, { action: "reject", reason, version: row.version })}>
                Reject
              </button>
            </>
          ) : null}
          {row.can_withdraw ? (
            <button type="button" className="hr-danger" onClick={() => void run(`credentials/${row.id}/withdraw`, { reason, version: row.version })}>
              Withdraw
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function Upcoming({ title, rows, field }: { title: string; rows: Deployment[]; field: "planned_start" | "planned_end" }) {
  return (
    <article className="hr-breakdown">
      <h3>
        <CalendarClock size={15} /> {title}
      </h3>
      {rows.length === 0 ? (
        <p className="muted">Nothing scheduled.</p>
      ) : (
        <ul>
          {rows.map((row) => (
            <li key={row.id}>
              <span>{row.person}</span>
              <strong>{row[field]}</strong>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

const NEW_DEPLOYMENT = {
  personnel_id: "",
  discipline_id: "",
  supervisor_id: "",
  area_id: "",
  planned_start: "",
  planned_end: "",
  shift: "",
  required_skills: "",
};

function Deployments({
  pid,
  board,
  admin,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  admin: boolean;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [form, setForm] = useState(NEW_DEPLOYMENT);
  const [checks, setChecks] = useState<string[]>(["Personnel documents", "Site induction"]);
  const [open, setOpen] = useState(false);
  const set = (key: keyof typeof NEW_DEPLOYMENT) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value });
  const num = (value: string) => (value ? Number(value) : null);
  const active = board.personnel.filter((row) => row.status === "Active");

  async function create(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hr/deployments`, "POST", {
        personnel_id: Number(form.personnel_id),
        discipline_id: num(form.discipline_id),
        supervisor_id: num(form.supervisor_id),
        area_id: num(form.area_id),
        planned_start: form.planned_start,
        planned_end: form.planned_end || null,
        shift: form.shift,
        required_skills: form.required_skills,
        checks,
      });
      setForm(NEW_DEPLOYMENT);
      setOpen(false);
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }

  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={DEPLOYMENT_ROUTES} members={board.members} disciplines={board.project_disciplines} />
      <p className="muted">{board.deployment_note}</p>
      <div className="hr-toolbar">
        <h3 className="section-mark">
          <HardHat size={18} strokeWidth={2.4} /> Project deployments
        </h3>
        {canEdit && !open ? (
          <button className="primary" type="button" onClick={() => setOpen(true)}>
            <Plus size={16} /> Propose deployment
          </button>
        ) : null}
      </div>
      {canEdit && open ? (
        <form className="contact-form hr-form" onSubmit={(event) => void create(event)}>
          <h4 className="wide">New deployment</h4>
          <label>
            Person
            <select required value={form.personnel_id} onChange={set("personnel_id")}>
              <option value="">Choose an active person</option>
              {active.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.code} · {row.full_name} · {row.trade}
                </option>
              ))}
            </select>
          </label>
          <label>
            Discipline
            <select value={form.discipline_id} onChange={set("discipline_id")}>
              <option value="">Person's primary discipline</option>
              {board.project_disciplines.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Site supervisor
            <select value={form.supervisor_id} onChange={set("supervisor_id")}>
              <option value="">Not set</option>
              {active
                .filter((row) => String(row.id) !== form.personnel_id)
                .map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.code} · {row.full_name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Work area
            <select value={form.area_id} onChange={set("area_id")}>
              <option value="">Not set</option>
              {board.areas.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Planned start
            <input required type="date" value={form.planned_start} onChange={set("planned_start")} />
          </label>
          <label>
            Planned end
            <input type="date" value={form.planned_end} onChange={set("planned_end")} />
          </label>
          <label>
            Shift
            <input value={form.shift} onChange={set("shift")} placeholder="e.g. Day shift" />
          </label>
          <label>
            Required skills
            <input value={form.required_skills} onChange={set("required_skills")} />
          </label>
          <fieldset className="wide hr-checks-pick">
            <legend>Onboarding checks needed before approval</legend>
            {board.check_types.map((row) => (
              <label key={row.name}>
                <input
                  type="checkbox"
                  checked={checks.includes(row.name)}
                  onChange={(event) => setChecks(event.target.checked ? [...checks, row.name] : checks.filter((name) => name !== row.name))}
                />
                {row.name} <em>verified by {row.owner}</em>
              </label>
            ))}
          </fieldset>
          <div className="wide hr-actions">
            <button className="primary" type="submit">
              Propose deployment
            </button>
            <button type="button" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}
      {board.deployments.length === 0 ? (
        <p className="muted">No deployment is recorded on this project.</p>
      ) : (
        <div className="hr-cards">
          {board.deployments.map((row) => (
            <DeploymentCard key={row.id} pid={pid} row={row} canEdit={canEdit} onError={onError} reload={reload} />
          ))}
        </div>
      )}
    </>
  );
}

function DeploymentCard({
  pid,
  row,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  row: Deployment;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [on, setOn] = useState("");
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState<Record<number, string>>({});

  async function run(path: string, body: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/hr/deployments/${row.id}${path}`, "POST", body);
      setOn("");
      setReason("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  const move = (action: string) => run("/move", { action, on: on || null, reason, version: row.version });
  const status = row.status;

  return (
    <article className="hr-card hr-card-deploy">
      <header>
        <strong>{row.person}</strong>
        <span className={statusClass(status)}>{status}</span>
      </header>
      <p className="hr-tags">
        <span>{row.company_name}</span>
        {row.discipline ? <span>{row.discipline}</span> : null}
        {row.area ? <span>{row.area}</span> : null}
        {row.shift ? <span>{row.shift}</span> : null}
      </p>
      <p className="muted">
        Planned {row.planned_start}
        {row.planned_end ? ` to ${row.planned_end}` : ""}
        {row.actual_start ? ` · On site from ${row.actual_start}` : ""}
        {row.actual_end ? ` · Left ${row.actual_end}` : ""}
        {row.supervisor_name ? ` · Supervisor ${row.supervisor_name}` : ""}
      </p>
      {row.required_skills ? <p className="muted">Skills: {row.required_skills}</p> : null}
      {row.status_reason ? <p className="muted">Reason: {row.status_reason}</p> : null}
      {row.flagged_allocations ? (
        <p className="note-card note-alert">This person is allocated to {row.flagged_allocations} workforce request(s) while unavailable.</p>
      ) : null}
      <ul className="hr-checks">
        {row.checks
          .filter((check) => check.status !== "Not required")
          .map((check) => (
            <li key={check.id} className={`is-${check.status.toLowerCase()}`}>
              <div>
                <strong>{check.check_type}</strong>
                <span className="muted">
                  {check.owner} · {check.status}
                  {check.verified_by ? ` by ${check.verified_by}` : ""}
                </span>
                {check.evidence ? <span className="muted">Evidence: {check.evidence}</span> : null}
              </div>
              {check.can_verify && check.status === "Pending" ? (
                <div className="hr-check-act">
                  <input
                    aria-label={`${check.check_type} evidence`}
                    placeholder="Evidence reference"
                    value={evidence[check.id] || ""}
                    onChange={(event) => setEvidence({ ...evidence, [check.id]: event.target.value })}
                  />
                  <button
                    type="button"
                    className="primary"
                    onClick={() => void run(`/checks/${check.id}`, { status: "Verified", evidence: evidence[check.id] || "", version: check.version })}
                  >
                    Verify
                  </button>
                </div>
              ) : null}
            </li>
          ))}
      </ul>
      <ReviewBox review={status === "Pending Approval" || row.review?.actions.includes("resubmit") ? row.review : null} onError={onError} reload={reload} />
      {canEdit && ["Proposed", "Approved for Mobilization", "Mobilized", "Temporarily Unavailable"].includes(status) ? (
        <div className="hr-move">
          {status === "Approved for Mobilization" ? (
            <input type="date" aria-label="Date" value={on} onChange={(event) => setOn(event.target.value)} />
          ) : null}
          <input aria-label="Reason" placeholder="Reason" value={reason} onChange={(event) => setReason(event.target.value)} />
          {status === "Proposed" && !row.review?.actions.includes("resubmit") ? (
            <button type="button" className="primary" onClick={() => void run("/submit", { version: row.version })}>
              Submit for approval
            </button>
          ) : null}
          {status === "Approved for Mobilization" ? (
            <button type="button" className="primary" onClick={() => void move("mobilize")}>
              Mobilize on date
            </button>
          ) : null}
          {status === "Mobilized" ? (
            <button type="button" onClick={() => void move("unavailable")}>
              Temporarily unavailable
            </button>
          ) : null}
          {status === "Temporarily Unavailable" ? (
            <button type="button" className="primary" onClick={() => void move("return")}>
              Back on site
            </button>
          ) : null}
          {status === "Mobilized" || status === "Temporarily Unavailable" ? (
            <span className="muted hr-offboard-hint">
              <LogOut size={13} /> Demobilize on the Offboarding tab
            </span>
          ) : null}
          {status === "Proposed" || status === "Approved for Mobilization" ? (
            <button type="button" className="hr-danger" onClick={() => void move("cancel")}>
              Cancel deployment
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function Requests({
  pid,
  board,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  return (
    <>
      <p className="note-card hr-requests-moved">
        Workforce demand is now raised, reviewed, and staffed in Manpower. This list is read only here; the numbers and reviews are the same records.
      </p>
      <p className="muted">{board.request_note}</p>
      <h3 className="section-mark">
        <ClipboardList size={18} strokeWidth={2.4} /> Workforce demand
      </h3>
      {board.requests.length === 0 ? (
        <p className="muted">No workforce demand is recorded on this project.</p>
      ) : (
        <div className="hr-cards">
          {board.requests.map((row) => (
            <RequestCard key={row.id} pid={pid} row={row} board={board} mine={false} canEdit={false} onError={onError} reload={reload} />
          ))}
        </div>
      )}
    </>
  );
}

function RequestCard({
  pid,
  row,
  board,
  mine,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  row: WorkRequest;
  board: Board;
  mine: boolean;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [person, setPerson] = useState("");
  const [picked, setPicked] = useState<Record<number, string>>({});
  const [forecast, setForecast] = useState(row.expected_mobilization || "");
  const [reason, setReason] = useState("");
  const allocating = ALLOCATING.includes(row.status);
  const onList = new Set(row.lines.filter((line) => line.state !== "Released").map((line) => line.personnel_id));
  const candidates = board.personnel.filter((item) => item.status === "Active" && item.trade_id === row.trade_id && !onList.has(item.id));

  async function run(path: string, body: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/hr/requests/${row.id}${path}`, "POST", body);
      setReason("");
      setPerson("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  const line = (personnel_id: number, state: string, deployment_id: number | null = null) =>
    run("/lines", { personnel_id, state, deployment_id, version: row.version });

  return (
    <article className="hr-card hr-card-request">
      <header>
        <strong>
          {row.number} · {row.headcount} × {row.trade}
        </strong>
        <span className={statusClass(row.status)}>{row.status}</span>
      </header>
      <p className="hr-tags">
        <span>{row.company_name}</span>
        <span className={`hr-priority hr-priority-${row.priority.toLowerCase()}`}>{row.priority}</span>
        {row.discipline ? <span>{row.discipline}</span> : null}
        {row.area ? <span>{row.area}</span> : null}
        {row.package ? <span>{row.package}</span> : null}
        {row.shift ? <span>{row.shift}</span> : null}
      </p>
      <p className="muted">
        Needed {row.start_date}
        {row.end_date ? ` to ${row.end_date}` : ""} · Requested by {row.requester}
        {row.expected_mobilization ? ` · Expected mobilization ${row.expected_mobilization}` : ""}
      </p>
      <p className="muted">{row.justification}</p>
      {row.qualifications ? <p className="muted">Qualifications: {row.qualifications}</p> : null}
      {row.status_reason ? <p className="muted">Reason: {row.status_reason}</p> : null}
      <div className="hr-demand">
        <span>
          Required <strong>{row.counts.required}</strong>
        </span>
        <span>
          Proposed <strong>{row.counts.proposed}</strong>
        </span>
        <span className="is-good">
          Allocated <strong>{row.counts.allocated}</strong>
        </span>
        <span className={row.counts.shortfall ? "is-bad" : "is-good"}>
          Shortfall <strong>{row.counts.shortfall}</strong>
        </span>
      </div>
      {row.lines.length ? (
        <ul className="hr-checks">
          {row.lines.map((item) => {
            const options = board.deployments.filter((dep) => dep.personnel_id === item.personnel_id && ON_SITE.includes(dep.status));
            return (
              <li key={item.id} className={`is-${item.state.toLowerCase()}`}>
                <div>
                  <strong>{item.person}</strong>
                  <span className="muted">{item.state}</span>
                </div>
                {canEdit && allocating && item.state !== "Released" ? (
                  <div className="hr-check-act">
                    {item.state === "Proposed" ? (
                      <>
                        <select aria-label={`Deployment for ${item.person}`} value={picked[item.id] || ""} onChange={(event) => setPicked({ ...picked, [item.id]: event.target.value })}>
                          <option value="">{options.length ? "Choose deployment" : "No approved deployment"}</option>
                          {options.map((dep) => (
                            <option key={dep.id} value={dep.id}>
                              {dep.status} · {dep.planned_start}
                            </option>
                          ))}
                        </select>
                        <button type="button" className="primary" disabled={!picked[item.id]} onClick={() => void line(item.personnel_id, "Allocated", Number(picked[item.id]))}>
                          Allocate
                        </button>
                      </>
                    ) : null}
                    <button type="button" onClick={() => void line(item.personnel_id, "Released")}>
                      Release
                    </button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      <ReviewBox review={row.status === "Pending Review" || row.review?.actions.includes("resubmit") ? row.review : null} onError={onError} reload={reload} />
      {canEdit && allocating ? (
        <div className="hr-move">
          <select aria-label="Propose person" value={person} onChange={(event) => setPerson(event.target.value)}>
            <option value="">{candidates.length ? "Propose a person with this trade" : "No other active person with this trade"}</option>
            {candidates.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} · {item.full_name}
              </option>
            ))}
          </select>
          <button type="button" className="primary" disabled={!person} onClick={() => void line(Number(person), "Proposed")}>
            Propose
          </button>
          <input type="date" aria-label="Expected mobilization" value={forecast} onChange={(event) => setForecast(event.target.value)} />
          <button type="button" onClick={() => void run("/forecast", { expected_mobilization: forecast || null, version: row.version })}>
            Save forecast
          </button>
        </div>
      ) : null}
      {(mine && row.status === "Draft") || ((mine || canEdit) && (allocating || row.status === "Returned" || row.status === "Draft")) ? (
        <div className="hr-move">
          {mine && row.status === "Draft" ? (
            <button type="button" className="primary" onClick={() => void run("/submit", { version: row.version })}>
              Submit for review
            </button>
          ) : null}
          <input aria-label="Close or cancel reason" placeholder="Reason to close or cancel" value={reason} onChange={(event) => setReason(event.target.value)} />
          {canEdit && allocating ? (
            <button type="button" onClick={() => void run("/close", { action: "close", reason, version: row.version })}>
              Close request
            </button>
          ) : null}
          <button type="button" className="hr-danger" onClick={() => void run("/close", { action: "cancel", reason, version: row.version })}>
            Cancel request
          </button>
        </div>
      ) : null}
    </article>
  );
}

const EMPTY = {
  code: "",
  full_name: "",
  company_id: "",
  personnel_type: "Employee",
  designation_id: "",
  trade_id: "",
  grade_id: "",
  discipline_id: "",
  start_date: "",
  end_date: "",
  supervisor_id: "",
  status: "Active",
  user_id: "",
  contact_number: "",
  emergency_contact: "",
  date_of_birth: "",
  address: "",
  identity_reference: "",
};
type Form = typeof EMPTY;

function fromPerson(row: Person): Form {
  const text = (value: number | string | null) => (value === null || value === undefined ? "" : String(value));
  return {
    code: row.code,
    full_name: row.full_name,
    company_id: text(row.company_id),
    personnel_type: row.personnel_type,
    designation_id: text(row.designation_id),
    trade_id: text(row.trade_id),
    grade_id: text(row.grade_id),
    discipline_id: text(row.discipline_id),
    start_date: row.start_date,
    end_date: text(row.end_date),
    supervisor_id: text(row.supervisor_id),
    status: row.status,
    user_id: text(row.user_id),
    contact_number: text(row.contact_number),
    emergency_contact: text(row.emergency_contact),
    date_of_birth: text(row.date_of_birth),
    address: text(row.address),
    identity_reference: text(row.identity_reference),
  };
}

function Personnel({
  pid,
  board,
  canEdit,
  onError,
  reload,
  onLists,
}: {
  pid: number;
  board: Board;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
  onLists: () => void;
}) {
  const [form, setForm] = useState<Form>(EMPTY);
  const [editing, setEditing] = useState<Person | null>(null);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const pick = (kind: string) => board.masters.filter((row) => row.kind === kind && (row.active || [form.designation_id, form.trade_id, form.grade_id].includes(String(row.id))));
  const set = (key: keyof Form) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value });
  const num = (value: string) => (value ? Number(value) : null);

  function start(row: Person | null) {
    setEditing(row);
    setForm(row ? fromPerson(row) : EMPTY);
    setOpen(true);
    onError("");
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    onError("");
    const body: Record<string, unknown> = {
      code: form.code,
      full_name: form.full_name,
      company_id: Number(form.company_id),
      personnel_type: form.personnel_type,
      designation_id: Number(form.designation_id),
      trade_id: Number(form.trade_id),
      grade_id: num(form.grade_id),
      discipline_id: num(form.discipline_id),
      start_date: form.start_date,
      end_date: form.end_date || null,
      supervisor_id: num(form.supervisor_id),
      status: form.status,
      user_id: num(form.user_id),
    };
    if (board.restricted_visible) {
      Object.assign(body, {
        contact_number: form.contact_number,
        emergency_contact: form.emergency_contact,
        date_of_birth: form.date_of_birth || null,
        address: form.address,
        identity_reference: form.identity_reference,
      });
    }
    try {
      if (editing) {
        await api(`/projects/${pid}/hr/personnel/${editing.id}`, "PUT", { ...body, version: editing.version });
      } else {
        await api(`/projects/${pid}/hr/personnel`, "POST", body);
      }
      setOpen(false);
      setEditing(null);
      setForm(EMPTY);
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }

  const query = filter.trim().toLowerCase();
  const rows = board.personnel.filter(
    (row) =>
      !query ||
      [row.code, row.full_name, row.company_name, row.trade, row.designation].some((value) => value.toLowerCase().includes(query)),
  );
  const missingLists = pick("Designation").length === 0 || pick("Trade").length === 0;
  const missing = ["Designation", "Trade", "Skill grade"].filter((kind) => pick(kind).length === 0);
  const emptyLabel = (kind: string, fallback: string) => (pick(kind).length ? fallback : "None yet · add on Workforce lists");
  const bosses = board.personnel.filter((row) => row.id !== editing?.id);

  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark">
          <IdCard size={18} strokeWidth={2.4} /> Personnel register
        </h3>
        <input placeholder="Search code, name, company, or trade" value={filter} onChange={(event) => setFilter(event.target.value)} />
        {canEdit && !open ? (
          <button className="primary" type="button" onClick={() => start(null)}>
            <Plus size={16} /> Add person
          </button>
        ) : null}
      </div>
      {canEdit && open ? (
        <form className="contact-form hr-form" onSubmit={(event) => void save(event)}>
          <h4 className="wide">{editing ? `Edit ${editing.code}` : "New person"}</h4>
          {missing.length ? (
            <div className="wide note-card note-alert hr-lists-hint">
              <p>
                {missing.join(", ")} {missing.length === 1 ? "has" : "have"} no values yet. These dropdowns come from Workforce lists, which are shared across the organization.
                {missingLists ? " A designation and a trade are required to save a person." : ""}
              </p>
              <button type="button" className="primary" onClick={onLists}>
                <ListChecks size={15} /> Open Workforce lists
              </button>
            </div>
          ) : null}
          <label>
            Worker code
            <input required value={form.code} onChange={set("code")} />
          </label>
          <label>
            Full name
            <input required value={form.full_name} onChange={set("full_name")} />
          </label>
          <label>
            Employing company
            <select required value={form.company_id} onChange={set("company_id")}>
              <option value="">Choose</option>
              {board.companies.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Personnel type
            <select value={form.personnel_type} onChange={set("personnel_type")}>
              {board.personnel_types.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Designation
            <select required value={form.designation_id} onChange={set("designation_id")}>
              <option value="">{emptyLabel("Designation", "Choose")}</option>
              {pick("Designation").map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Trade / skill
            <select required value={form.trade_id} onChange={set("trade_id")}>
              <option value="">{emptyLabel("Trade", "Choose")}</option>
              {pick("Trade").map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Skill grade
            <select value={form.grade_id} onChange={set("grade_id")}>
              <option value="">{emptyLabel("Skill grade", "Not set")}</option>
              {pick("Skill grade").map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Primary discipline
            <select value={form.discipline_id} onChange={set("discipline_id")}>
              <option value="">Not set</option>
              {board.disciplines.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Employment start
            <input required type="date" value={form.start_date} onChange={set("start_date")} />
          </label>
          <label>
            Employment end
            <input type="date" value={form.end_date} onChange={set("end_date")} />
          </label>
          <label>
            Status
            <select value={form.status} onChange={set("status")}>
              {board.statuses.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Supervisor
            <select value={form.supervisor_id} onChange={set("supervisor_id")}>
              <option value="">{bosses.length ? "Not set" : "No other worker yet · optional"}</option>
              {bosses.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.code} · {row.full_name}
                </option>
              ))}
            </select>
            <small className="muted">A worker already in this register who supervises this person.</small>
          </label>
          <label>
            Linked login (optional)
            <select value={form.user_id} onChange={set("user_id")}>
              <option value="">No login</option>
              {board.logins.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name} · {row.email}
                </option>
              ))}
            </select>
          </label>
          <p className="wide muted">Linking a login stores the reference only. Access and project roles stay in People & access and project members.</p>
          {board.restricted_visible ? (
            <fieldset className="wide hr-restricted">
              <legend>
                <Lock size={14} /> Restricted details
              </legend>
              <label>
                Contact number
                <input value={form.contact_number} onChange={set("contact_number")} />
              </label>
              <label>
                Emergency contact
                <input value={form.emergency_contact} onChange={set("emergency_contact")} />
              </label>
              <label>
                Date of birth
                <input type="date" value={form.date_of_birth} onChange={set("date_of_birth")} />
              </label>
              <label>
                Identity reference
                <input value={form.identity_reference} onChange={set("identity_reference")} />
              </label>
              <label className="wide">
                Address
                <input value={form.address} onChange={set("address")} />
              </label>
            </fieldset>
          ) : (
            <p className="wide muted">
              <Lock size={14} /> Contact, emergency, and identity details are kept by HR with restricted access.
            </p>
          )}
          <div className="wide hr-actions">
            <button className="primary" type="submit">
              {editing ? "Save person" : "Add person"}
            </button>
            <button type="button" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}
      {rows.length === 0 ? (
        <p className="muted">{board.personnel.length === 0 ? "No person is registered for the companies on this project." : "No person matches this search."}</p>
      ) : (
        <div className="hr-people">
          {rows.map((row) => (
            <article key={row.id} className="hr-person">
              <div className="hr-avatar" aria-hidden="true">
                {row.full_name.slice(0, 1).toUpperCase()}
              </div>
              <div className="hr-person-main">
                <header>
                  <strong>{row.full_name}</strong>
                  <span className={statusClass(row.status)}>{row.status}</span>
                </header>
                <p>
                  {row.code} · {row.company_name}
                </p>
                <p className="hr-tags">
                  <span>{row.designation}</span>
                  <span>{row.trade}</span>
                  {row.grade ? <span>{row.grade}</span> : null}
                  {row.discipline ? <span>{row.discipline}</span> : null}
                  <span>{row.personnel_type}</span>
                </p>
                <p className="muted">
                  From {row.start_date}
                  {row.end_date ? ` to ${row.end_date}` : ""}
                  {row.supervisor_name ? ` · Supervisor ${row.supervisor_name}` : ""}
                </p>
                <p className="muted">
                  <UserRoundCheck size={14} /> {row.user_id ? `Login: ${row.login_name}${row.login_active ? "" : " (inactive)"}` : "No login"}
                </p>
                {row.access_review ? <p className="note-card note-alert">Employment ended and the login is still active. An organization administrator should review that access.</p> : null}
                {row.restricted_visible && (row.contact_number || row.emergency_contact) ? (
                  <p className="muted">
                    <Lock size={14} /> {row.contact_number || "No number"} · Emergency: {row.emergency_contact || "Not recorded"}
                  </p>
                ) : null}
              </div>
              {canEdit ? (
                <button type="button" className="hr-edit" onClick={() => start(row)} aria-label={`Edit ${row.full_name}`}>
                  <Pencil size={15} /> Edit
                </button>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </>
  );
}

function Lists({
  pid,
  board,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canEdit: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [kind, setKind] = useState(board.master_kinds[0] || "Designation");
  const [name, setName] = useState("");

  async function add(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hr/masters`, "POST", { kind, name });
      setName("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function toggle(row: Master) {
    onError("");
    try {
      await api(`/projects/${pid}/hr/masters/${row.id}`, "PUT", { name: row.name, active: !row.active, version: row.version });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }

  return (
    <>
      <p className="muted">These lists are shared across the organization. Designation, trade, grade, discipline, and application role are separate.</p>
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void add(event)}>
          <label>
            List
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {board.master_kinds.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Name
            <input required value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Steel Fixer" />
          </label>
          <div className="hr-actions">
            <button className="primary" type="submit">
              <Plus size={16} /> Add to list
            </button>
          </div>
        </form>
      ) : null}
      <div className="hr-lists">
        {board.master_kinds.map((value) => {
          const items = board.masters.filter((row) => row.kind === value);
          return (
            <article key={value} className="hr-breakdown">
              <h3>{value}</h3>
              {items.length === 0 ? (
                <p className="muted">Nothing listed yet.</p>
              ) : (
                <ul>
                  {items.map((row) => (
                    <li key={row.id} className={row.active ? "" : "is-off"}>
                      <span>{row.name}</span>
                      {canEdit ? (
                        <button type="button" onClick={() => void toggle(row)}>
                          {row.active ? "Deactivate" : "Reactivate"}
                        </button>
                      ) : (
                        <em>{row.active ? "Active" : "Inactive"}</em>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </article>
          );
        })}
      </div>
    </>
  );
}
