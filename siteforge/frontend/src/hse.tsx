import { FormEvent, useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { BadgeCheck, Ban, ClipboardCheck, LayoutDashboard, Leaf, LifeBuoy, ListChecks, Lock, LockKeyhole, Megaphone, ScrollText, Shield, ShieldAlert, Siren, TriangleAlert, Waypoints } from "lucide-react";
import { api } from "./api";
import { RouteLockNotice, routeLocked } from "./approval_levels";
import type { Page, Project, Session } from "./types";

const TABS = ["Dashboard", "Documents", "Risk assessments", "Permits", "Isolations", "Workfront", "Induction", "Toolbox", "Inspections", "Incidents", "Actions", "Safety holds", "Emergency", "Environmental"] as const;
const TAB_ICON: Record<(typeof TABS)[number], LucideIcon> = {
  Dashboard: LayoutDashboard,
  Documents: ScrollText,
  "Risk assessments": TriangleAlert,
  Permits: ShieldAlert,
  Isolations: LockKeyhole,
  Workfront: Waypoints,
  Induction: BadgeCheck,
  Toolbox: Megaphone,
  Inspections: ClipboardCheck,
  Incidents: Siren,
  Actions: ListChecks,
  "Safety holds": Ban,
  Emergency: LifeBuoy,
  Environmental: Leaf,
};
const TAB_TONE: Record<(typeof TABS)[number], string> = {
  Dashboard: "tone-hdash",
  Documents: "tone-hdoc",
  "Risk assessments": "tone-hrisk",
  Permits: "tone-hpermit",
  Isolations: "tone-hiso",
  Workfront: "tone-hsim",
  Induction: "tone-hinduct",
  Toolbox: "tone-htalk",
  Inspections: "tone-hfind",
  Incidents: "tone-hinc",
  Actions: "tone-hact",
  "Safety holds": "tone-hhold",
  Emergency: "tone-hemerg",
  Environmental: "tone-henv",
};

function statusChip(status: string) {
  return `rel-chip hand-${status.replaceAll(" ", "-").toLowerCase()}`;
}

function Err({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}

type Person = { id: number; name: string };
type Named = { id: number; name: string };
type PackageRow = { id: number; code: string; status: string };
type ActivityRow = { id: number; package_id: number; code: string; name: string };
type Review = { id: number; version: number; actions: string[] };
type PermitCheck = { id: number; name: string; evidence: string; acknowledged: boolean };
type PermitRow = {
  id: number;
  number: string;
  type_name: string;
  status: string;
  package_code: string;
  package_status: string;
  activity_code: string;
  task_description: string;
  issuer_name: string;
  valid_from: string | null;
  valid_until: string | null;
  effective_until: string | null;
  statement: string;
  version: number;
  checks: PermitCheck[];
  events: { id: number; kind: string; note: string; valid_until: string | null }[];
};
type IsolationRow = {
  id: number;
  kind: string;
  number: string;
  status: string;
  authority_name: string;
  version: number;
  permit_ids: number[];
  allow_removal_with_active_permit: boolean;
};
type ConflictRow = {
  id: number;
  permit_id: number;
  permit_number: string;
  other_permit_id: number;
  other_number: string;
  status: string;
  decision: string;
  controls: string;
  require_decision: boolean;
};
type DocumentRow = {
  id: number;
  kind: string;
  number: string;
  title: string;
  revision_label: string;
  status: string;
  owner_name: string;
  applicability: string;
  engineering_reference: string;
  statement: string;
  withdrawal_reason: string;
  version: number;
  review: Review | null;
};
type AssessmentRow = {
  id: number;
  number: string;
  status: string;
  package_code: string;
  package_status: string;
  activity_code: string;
  document_label: string;
  task_description: string;
  initial_rating: string;
  residual_rating: string;
  statement: string;
  withdrawal_reason: string;
  supersedes_id: number | null;
  version: number;
  review: Review | null;
};
type IncidentRow = {
  id: number;
  number: string;
  category: string;
  status: string;
  event_at: string | null;
  timezone_name: string;
  description: string;
  immediate_actions: string;
  initial_severity: string;
  reporter_name: string;
  verified_classification: string;
  package_status: string;
  statement: string;
  version: number;
};
type ActionRow = {
  id: number;
  number: string;
  description: string;
  severity: string;
  status: string;
  owner_id: number;
  owner_name: string;
  verifier_id: number;
  verifier_name: string;
  evidence: string;
  effectiveness: string;
  task_status: string;
  statement: string;
  version: number;
};
type HoldRow = {
  id: number;
  number: string;
  kind: string;
  status: string;
  reason: string;
  scope_kind: string;
  package_status: string;
  owner_id: number | null;
  owner_name: string;
  issuer_name: string;
  statement: string;
  version: number;
  events: { id: number; kind: string; note: string }[];
};
type Board = {
  note: string;
  rating_note: string;
  document_statement: string;
  counts: {
    documents: number;
    approved_documents: number;
    assessments: number;
    pending_assessments: number;
    approved_assessments: number;
    permits?: number;
    active_permits?: number;
    pending_permits?: number;
    expired_permits?: number;
    suspended_permits?: number;
    eligibility_gaps?: number;
    talks?: number;
    open_findings?: number;
    observations?: number;
    incidents?: number;
    open_incidents?: number;
    open_actions?: number;
    active_holds?: number;
    emergency_contacts?: number;
    emergency_reviews_due?: number;
    drills?: number;
    environment_records?: number;
    environment_outside?: number;
  };
  environment_note?: string;
  environment_action_note?: string;
  environment_kinds?: string[];
  environment_results?: string[];
  environment_criteria?: { id: number; name: string; kind: string; threshold: string }[];
  environment_records?: { id: number; number: string; kind: string; description: string; recorded_on: string; reading: string; result: string; evidence: string; criterion_name: string; threshold: string; action_number: string; action_status: string; package_status: string; statement: string; action_note: string }[];
  emergency_note?: string;
  gear_note?: string;
  drill_note?: string;
  drill_finding_note?: string;
  suggested_response_roles?: string[];
  emergency_rule?: { procedure: string; review_days: number | null };
  project_contacts?: { id: number; name: string; function: string; active: boolean }[];
  emergency_contacts?: { id: number; name: string; function: string; response_role: string; phone: string | null; email: string | null; status: string; review_due_on: string | null; version: number; statement: string }[];
  muster_points?: { id: number; name: string; note: string }[];
  emergency_gear?: { id: number; name: string; location: string; statement: string }[];
  emergency_plans?: { id: number; number: string; title: string; engineering_reference: string }[];
  drills?: { id: number; number: string; title: string; planned_on: string; status: string; findings: string; version: number; statement: string; finding_note: string; acknowledgments: { member_name: string; evidence: string }[] }[];
  hold_note?: string;
  concern_note?: string;
  hold_scopes?: string[];
  hold_issuers?: { id: number; user_id: number; name: string }[];
  hold_rule?: { separate_release: boolean };
  holds?: HoldRow[];
  incident_note?: string;
  incident_statement?: string;
  action_note?: string;
  suggested_incident_categories?: string[];
  incident_categories?: { id: number; name: string }[];
  incident_rules?: { id: number; severity: string; requires_investigation: boolean }[];
  incidents?: IncidentRow[];
  action_rule?: { effectiveness_required: boolean };
  actions?: ActionRow[];
  eligibility_note?: string;
  toolbox_note?: string;
  inspection_note?: string;
  observation_note?: string;
  follow_up_note?: string;
  suggested_eligibility?: string[];
  inspection_types?: string[];
  observation_types?: string[];
  eligibility_rules?: { id: number; category: string; package_id: number | null; activity_id: number | null }[];
  eligibility?: { id: number; member_name: string; category: string; evidence: string; expires_on: string | null; status: string; version: number; statement: string }[];
  gaps?: { member_id: number; member_name: string; category: string; reason: string }[];
  toolbox_rules?: { id: number; package_id: number | null; activity_id: number | null }[];
  talks?: { id: number; number: string; talk_on: string; shift: string; topic: string; status: string; presenter_name: string; issues: string; follow_up: string; version: number; acknowledgments: { member_name: string; evidence: string }[]; statement: string; follow_up_note: string }[];
  finding_rules?: { id: number; severity: string; blocks_work: boolean }[];
  inspections?: { id: number; number: string; inspection_type: string; inspector_name: string; inspected_on: string; status: string; statement: string; findings: { id: number; description: string; severity: string; owner_name: string; status: string; version: number; photo_reference: string }[] }[];
  observations?: { id: number; number: string; observation_type: string; description: string; reporter_name: string; status: string; statement: string }[];
  permit_statement?: string;
  simops_note?: string;
  suggested_permit_types?: string[];
  isolation_kinds?: string[];
  permit_types?: { id: number; name: string; physical_required: boolean; handover_required: boolean }[];
  permits?: PermitRow[];
  isolations?: IsolationRow[];
  conflict_rules?: { id: number; type_a_id: number; type_b_id: number; require_decision: boolean; note: string }[];
  conflicts?: ConflictRow[];
  documents: DocumentRow[];
  assessments: AssessmentRow[];
  companies: Named[];
  disciplines: Named[];
  areas: Named[];
  packages: PackageRow[];
  activities: ActivityRow[];
  members: Person[];
  kinds: string[];
  dashboard?: SafetyDashboard;
};

type SafetyDashboard = {
  note: string;
  observation_note: string;
  rate: string;
  rate_note: string;
  date_kinds: string[];
  permits: { active: number; pending: number; expired: number; suspended: number };
  blocked_work: { code: string; reason: string }[];
  open_critical_observations: number;
  incidents_by_category: { name: string; count: number }[];
  open_actions: number;
  overdue_actions: number;
  active_holds: number;
  eligibility_gaps: number;
  inspection_completion: { done: number; total: number; label: string };
  upcoming_drills: { number: string; title: string; planned_on: string }[];
  environmental_issues: { number: string; detail: string }[];
};

type RouteNeed = { recordType: string; label: string; stage: string };
type SavedRoute = { discipline_id: number | null; stages: { reviewers: { id: number; name: string }[] }[] };
const DOCUMENT_ROUTES: RouteNeed[] = [{ recordType: "hse.document", label: "HSE document reviewer", stage: "HSE document review" }];
const ASSESSMENT_ROUTES: RouteNeed[] = [{ recordType: "hse.assessment", label: "Risk assessment reviewer", stage: "Risk assessment review" }];
const PERMIT_ROUTES: RouteNeed[] = [{ recordType: "hse.permit", label: "Permit reviewer", stage: "Permit authorization" }];
const INCIDENT_ROUTES: RouteNeed[] = [{ recordType: "hse.incident", label: "Incident closure reviewer", stage: "Incident closure" }];
const HOLD_ROUTES: RouteNeed[] = [{ recordType: "hse.hold", label: "Safety hold release reviewer", stage: "Safety hold release" }];

function routeText(rows: SavedRoute[], disciplines: Named[]) {
  if (!rows.length) return "Not set";
  return rows
    .map((row) => {
      const people = row.stages.flatMap((stage) => stage.reviewers.map((person) => person.name)).join(", ") || "Not set";
      const scope = disciplines.find((item) => item.id === row.discipline_id)?.name || "All disciplines";
      return `${people} · ${scope}`;
    })
    .join("; ");
}

export function HseRoutes({
  pid,
  admin,
  routes,
  members,
  disciplines,
}: {
  pid: number;
  admin: boolean;
  routes: RouteNeed[];
  members: Person[];
  disciplines: Named[];
}) {
  const [saved, setSaved] = useState<Record<string, SavedRoute[]>>({});
  const [picked, setPicked] = useState<Record<string, number>>({});
  const [scope, setScope] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!admin) return;
    void Promise.all(
      routes.map((route) =>
        api<SavedRoute[]>(`/projects/${pid}/approval-policies?record_type=${route.recordType}`).then((rows) => [route.recordType, rows] as const),
      ),
    )
      .then((pairs) => {
        const next: Record<string, SavedRoute[]> = {};
        for (const [key, rows] of pairs) next[key] = rows;
        setSaved(next);
        setPicked((current) => {
          const chosen = { ...current };
          for (const [key, rows] of pairs) {
            const id = rows[0]?.stages.flatMap((stage) => stage.reviewers)[0]?.id;
            if (id) chosen[key] = id;
          }
          return chosen;
        });
      })
      .catch((err) => setError((err as Error).message));
  }, [pid, admin, tick, routes]);
  if (!admin) return null;
  async function save(route: RouteNeed) {
    const reviewer = picked[route.recordType] || 0;
    if (!reviewer) {
      setError("Choose a project member");
      return;
    }
    setError("");
    setNotice("");
    try {
      await api(`/projects/${pid}/approval-policies`, "POST", {
        record_type: route.recordType,
        company_id: null,
        discipline_id: scope[route.recordType] ? Number(scope[route.recordType]) : null,
        allow_self_approval: false,
        stages: [
          {
            name: route.stage,
            rule: "all",
            quorum_count: 1,
            reviewer_ids: [reviewer],
            reviewers: [],
            purpose: route.label,
          },
        ],
      });
      setTick((value) => value + 1);
      setNotice(`${route.label} saved. Only that person can approve, and they cannot approve their own submission.`);
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <div className="quality-routes">
      <h3 className="section-mark wide">
        <Lock size={18} strokeWidth={2.4} /> Review route
      </h3>
      <p className="muted">The record owner is not the reviewer. Save an active project member other than the person who will submit. Leave discipline on all disciplines unless this route is only for one discipline.</p>
      <Err text={error} />
      {notice ? <p className="muted">{notice}</p> : null}
      {routes.map((route) => {
        const disciplineId = scope[route.recordType] ? Number(scope[route.recordType]) : null;
        const locked = routeLocked(saved[route.recordType], disciplineId);
        return (
        <div key={route.recordType} className="option-grid">
          <p>
            <strong>{route.label}</strong> · {routeText(saved[route.recordType] || [], disciplines)}
          </p>
          {locked ? <RouteLockNotice target={{ projectId: pid, recordType: route.recordType, disciplineId }} /> : null}
          <label>
            Discipline
            <select aria-label={`${route.label} discipline`} value={scope[route.recordType] || ""} onChange={(event) => setScope({ ...scope, [route.recordType]: event.target.value })}>
              <option value="">All disciplines</option>
              {disciplines.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Reviewer
            <select aria-label={route.label} disabled={locked} value={picked[route.recordType] || ""} onChange={(event) => setPicked({ ...picked, [route.recordType]: Number(event.target.value) })}>
              <option value="">Choose a project member</option>
              {members.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="primary" disabled={locked || !picked[route.recordType]} onClick={() => void save(route)}>
            Save
          </button>
        </div>
        );
      })}
    </div>
  );
}

export function HseHome({ session, initialProjectId = null }: { session: Session; initialProjectId?: number | null }) {
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
        <HseBoard pid={pid} session={session} />
      </>
    );
  }
  return (
    <section className="panel">
      <h2>Safety / HSE</h2>
      <p className="muted">Open a project to keep its HSE references, permits, induction, and incidents.</p>
      <Err text={error} />
      {projects.map((project) => (
        <button key={project.id} onClick={() => setPid(project.id || null)}>
          <Shield size={16} strokeWidth={2.4} />
          {project.code} · {project.name}
        </button>
      ))}
    </section>
  );
}

function HseBoard({ pid, session }: { pid: number; session: Session }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Dashboard");
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState("");
  const admin = session.user.organization_admin;
  const canPlan =
    admin || session.memberships.some((item) => item.project_id === pid && item.permissions?.includes("hse.plan"));
  const canEdit =
    canPlan || session.memberships.some((item) => item.project_id === pid && item.permissions?.includes("hse.edit"));
  async function load() {
    setBoard(await api<Board>(`/projects/${pid}/hse`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  return (
    <section className="panel">
      <h2>Safety / HSE</h2>
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
      {tab === "Dashboard" && board ? (
        <>
          <HseRoutes pid={pid} admin={admin} routes={[...DOCUMENT_ROUTES, ...ASSESSMENT_ROUTES, ...PERMIT_ROUTES, ...INCIDENT_ROUTES, ...HOLD_ROUTES]} members={board.members} disciplines={board.disciplines} />
          <div className="dash-grid">
            <Count label="Documents" value={board.counts.documents} />
            <Count label="Approved documents" value={board.counts.approved_documents} />
            <Count label="Assessments" value={board.counts.assessments} />
            <Count label="Active permits" value={board.counts.active_permits || 0} />
            <Count label="Pending permits" value={board.counts.pending_permits || 0} />
            <Count label="Expired permits" value={board.counts.expired_permits || 0} />
            <Count label="Suspended permits" value={board.counts.suspended_permits || 0} />
            <Count label="Eligibility gaps" value={board.counts.eligibility_gaps || 0} />
            <Count label="Toolbox talks" value={board.counts.talks || 0} />
            <Count label="Open findings" value={board.counts.open_findings || 0} />
            <Count label="Observations" value={board.counts.observations || 0} />
            <Count label="Incidents" value={board.counts.incidents || 0} />
            <Count label="Open actions" value={board.counts.open_actions || 0} />
            <Count label="Active holds" value={board.counts.active_holds || 0} />
            <Count label="Emergency contacts" value={board.counts.emergency_contacts || 0} />
            <Count label="Reviews due" value={board.counts.emergency_reviews_due || 0} />
            <Count label="Drills" value={board.counts.drills || 0} />
            <Count label="Environmental records" value={board.counts.environment_records || 0} />
            <Count label="Outside criteria" value={board.counts.environment_outside || 0} />
            <Count label="Incident rate" value="N/A" />
          </div>
          <p className="muted">{board.incident_note}</p>
          {board.dashboard ? <SafetyBoard pid={pid} initial={board.dashboard} companies={board.companies} disciplines={board.disciplines} areas={board.areas} packages={board.packages} members={board.members} /> : null}
        </>
      ) : null}
      {tab === "Documents" && board ? (
        <Documents
          pid={pid}
          board={board}
          canPlan={canPlan}
          admin={admin}
          onError={setError}
          reload={load}
        />
      ) : null}
      {tab === "Risk assessments" && board ? (
        <Assessments pid={pid} board={board} canEdit={canEdit} admin={admin} onError={setError} reload={load} />
      ) : null}
      {tab === "Permits" && board ? <Permits pid={pid} board={board} canPlan={canPlan} canEdit={canEdit} admin={admin} onError={setError} reload={load} /> : null}
      {tab === "Isolations" && board ? <Isolations pid={pid} board={board} canPlan={canPlan} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Workfront" && board ? <Workfront pid={pid} board={board} canPlan={canPlan} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Induction" && board ? <Induction pid={pid} board={board} canPlan={canPlan} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Toolbox" && board ? <Toolbox pid={pid} board={board} canPlan={canPlan} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Inspections" && board ? <Inspections pid={pid} board={board} canPlan={canPlan} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Incidents" && board ? <Incidents pid={pid} board={board} canPlan={canPlan} admin={admin} onError={setError} reload={load} /> : null}
      {tab === "Actions" && board ? <Actions pid={pid} board={board} userId={session.user.id} canPlan={canPlan} canEdit={canEdit} onError={setError} reload={load} /> : null}
      {tab === "Safety holds" && board ? <Holds pid={pid} board={board} userId={session.user.id} canPlan={canPlan} admin={admin} onError={setError} reload={load} /> : null}
      {tab === "Emergency" && board ? <Emergency pid={pid} board={board} canPlan={canPlan} onError={setError} reload={load} /> : null}
      {tab === "Environmental" && board ? <Environmental pid={pid} board={board} canPlan={canPlan} onError={setError} reload={load} /> : null}
    </section>
  );
}

function Count({ label, value }: { label: string; value: number | string }) {
  return (
    <article className="hse-count">
      <strong>{value}</strong>
      <span>{label}</span>
    </article>
  );
}

function SafetyBoard({
  pid,
  initial,
  companies,
  disciplines,
  areas,
  packages,
  members,
}: {
  pid: number;
  initial: SafetyDashboard;
  companies: Named[];
  disciplines: Named[];
  areas: Named[];
  packages: PackageRow[];
  members: Person[];
}) {
  const [view, setView] = useState(initial);
  const [companyId, setCompanyId] = useState("");
  const [disciplineId, setDisciplineId] = useState("");
  const [areaId, setAreaId] = useState("");
  const [packageId, setPackageId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [severity, setSeverity] = useState("");
  const [dateKind, setDateKind] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [error, setError] = useState("");
  async function apply(event: FormEvent) {
    event.preventDefault();
    setError("");
    const query = new URLSearchParams();
    if (companyId) query.set("company_id", companyId);
    if (disciplineId) query.set("discipline_id", disciplineId);
    if (areaId) query.set("area_id", areaId);
    if (packageId) query.set("package_id", packageId);
    if (ownerId) query.set("owner_id", ownerId);
    if (severity) query.set("severity", severity);
    if (dateKind) query.set("date_kind", dateKind);
    if (dateFrom) query.set("date_from", dateFrom);
    if (dateTo) query.set("date_to", dateTo);
    try {
      setView(await api<SafetyDashboard>(`/projects/${pid}/hse/dashboard?${query.toString()}`));
    } catch (err) {
      setError((err as Error).message);
    }
  }
  function clear() {
    setCompanyId("");
    setDisciplineId("");
    setAreaId("");
    setPackageId("");
    setOwnerId("");
    setSeverity("");
    setDateKind("");
    setDateFrom("");
    setDateTo("");
    setView(initial);
    setError("");
  }
  return (
    <>
      <h3>Filtered view</h3>
      <p className="note-card">{view.note}</p>
      <form className="contact-form" onSubmit={(event) => void apply(event)}>
        <label>
          Company
          <select aria-label="Dashboard company" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
            <option value="">All companies</option>
            {companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>
          Discipline
          <select aria-label="Dashboard discipline" value={disciplineId} onChange={(event) => setDisciplineId(event.target.value)}>
            <option value="">All disciplines</option>
            {disciplines.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>
          Location
          <select aria-label="Dashboard location" value={areaId} onChange={(event) => setAreaId(event.target.value)}>
            <option value="">All locations</option>
            {areas.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>
          Work package
          <select aria-label="Dashboard package" value={packageId} onChange={(event) => setPackageId(event.target.value)}>
            <option value="">All packages</option>
            {packages.map((row) => <option key={row.id} value={row.id}>{row.code}</option>)}
          </select>
        </label>
        <label>
          Responsible owner
          <select aria-label="Dashboard owner" value={ownerId} onChange={(event) => setOwnerId(event.target.value)}>
            <option value="">All owners</option>
            {members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>Severity<input aria-label="Dashboard severity" value={severity} onChange={(event) => setSeverity(event.target.value)} /></label>
        <label>
          Date type
          <select aria-label="Dashboard date type" value={dateKind} onChange={(event) => setDateKind(event.target.value)}>
            <option value="">Any date</option>
            {view.date_kinds.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <label>From<input aria-label="Dashboard from" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
        <label>To<input aria-label="Dashboard to" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label>
        <button className="primary" type="submit">Apply filters</button>
        <button type="button" onClick={clear}>Clear filters</button>
      </form>
      <Err text={error} />
      <div className="dash-grid">
        <Count label="Active permits" value={view.permits.active} />
        <Count label="Pending permits" value={view.permits.pending} />
        <Count label="Expired permits" value={view.permits.expired} />
        <Count label="Suspended permits" value={view.permits.suspended} />
        <Count label="Work blocked" value={view.blocked_work.length} />
        <Count label="Open critical observations" value={view.open_critical_observations} />
        <Count label="Open actions" value={view.open_actions} />
        <Count label="Overdue actions" value={view.overdue_actions} />
        <Count label="Active holds" value={view.active_holds} />
        <Count label="Eligibility gaps" value={view.eligibility_gaps} />
        <Count label="Incident rate" value={view.rate} />
      </div>
      <p className="muted">{view.rate_note}</p>
      <p className="muted">{view.observation_note}</p>
      <p className="muted">{view.inspection_completion.label}</p>
      <h3>Incidents by category</h3>
      {view.incidents_by_category.length === 0 ? <p className="muted">No incident in this filter.</p> : (
        <ul className="link-list">
          {view.incidents_by_category.map((row) => <li key={row.name}>{row.name}: {row.count}</li>)}
        </ul>
      )}
      <h3>Work blocked by an HSE restriction</h3>
      {view.blocked_work.length === 0 ? <p className="muted">No package in this filter is blocked by a permit, field rule, or safety hold.</p> : (
        <ul className="link-list">
          {view.blocked_work.map((row) => <li key={row.code}><strong>{row.code}</strong> · {row.reason}</li>)}
        </ul>
      )}
      <h3>Upcoming drills</h3>
      {view.upcoming_drills.length === 0 ? <p className="muted">No planned drill is still ahead.</p> : (
        <ul className="link-list">
          {view.upcoming_drills.map((row) => <li key={row.number}>{row.number} · {row.title} · {row.planned_on}</li>)}
        </ul>
      )}
      <h3>Environmental issues</h3>
      {view.environmental_issues.length === 0 ? <p className="muted">No reading is outside a saved criterion, and no environmental concern is open.</p> : (
        <ul className="link-list">
          {view.environmental_issues.map((row) => <li key={`${row.number}-${row.detail}`}>{row.number} · {row.detail}</li>)}
        </ul>
      )}
    </>
  );
}

function Documents({
  pid,
  board,
  canPlan,
  admin,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  admin: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [kind, setKind] = useState(board.kinds[0] || "HSE Plan");
  const [number, setNumber] = useState("");
  const [title, setTitle] = useState("");
  const [revision, setRevision] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [disciplineId, setDisciplineId] = useState("");
  const [areaId, setAreaId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [applicability, setApplicability] = useState("");
  const [reference, setReference] = useState("");
  async function create(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/documents`, "POST", {
        kind,
        number,
        title,
        revision_label: revision,
        company_id: Number(companyId),
        discipline_id: disciplineId ? Number(disciplineId) : null,
        area_id: areaId ? Number(areaId) : null,
        owner_id: Number(ownerId),
        effective_from: from || null,
        effective_to: to || null,
        applicability,
        engineering_reference: reference,
      });
      setNumber("");
      setTitle("");
      setRevision("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function act(row: DocumentRow, path: "submit" | "resubmit" | "withdraw") {
    onError("");
    const reason = path === "withdraw" ? window.prompt("Reason for withdrawal") || "" : "";
    if (path === "withdraw" && reason.trim().length < 3) return;
    try {
      await api(`/projects/${pid}/hse/documents/${row.id}/${path}`, "POST", {
        version: path === "resubmit" ? row.review?.version : row.version,
        reason,
      });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={DOCUMENT_ROUTES} members={board.members} disciplines={board.disciplines} />
      <p className="muted">{board.document_statement}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <label>
            Kind
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {board.kinds.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Number
            <input value={number} onChange={(event) => setNumber(event.target.value)} required maxLength={40} />
          </label>
          <label>
            Title
            <input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={200} />
          </label>
          <label>
            Revision
            <input value={revision} onChange={(event) => setRevision(event.target.value)} required maxLength={20} />
          </label>
          <label>
            Company
            <select value={companyId} onChange={(event) => setCompanyId(event.target.value)} required>
              <option value="">Choose a company</option>
              {board.companies.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Discipline
            <select value={disciplineId} onChange={(event) => setDisciplineId(event.target.value)}>
              <option value="">All disciplines</option>
              {board.disciplines.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Area
            <select value={areaId} onChange={(event) => setAreaId(event.target.value)}>
              <option value="">Not set</option>
              {board.areas.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Owner
            <select value={ownerId} onChange={(event) => setOwnerId(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Effective from
            <input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
          </label>
          <label>
            Effective to
            <input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
          </label>
          <label>
            Applicability
            <input value={applicability} onChange={(event) => setApplicability(event.target.value)} />
          </label>
          <label>
            Document control reference
            <input value={reference} onChange={(event) => setReference(event.target.value)} />
          </label>
          <button className="primary" type="submit">
            Save draft
          </button>
        </form>
      ) : null}
      <div className="contact-grid">
        {board.documents.map((row) => (
          <article key={row.id} className="contact-card">
            <header>
              <ScrollText size={15} />
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            <h4>
              {row.kind} {row.number} rev {row.revision_label}
            </h4>
            <p>{row.title}</p>
            <p className="muted">Owner {row.owner_name || "not set"}</p>
            {row.applicability ? <p>{row.applicability}</p> : null}
            {row.engineering_reference ? <p className="muted">File reference {row.engineering_reference}</p> : null}
            <p className="muted">{row.statement}</p>
            {row.withdrawal_reason ? <p>Withdrawn: {row.withdrawal_reason}</p> : null}
            {canPlan && row.status === "Draft" ? (
              <button type="button" className="primary" onClick={() => void act(row, "submit")}>
                Submit
              </button>
            ) : null}
            {canPlan && row.status === "Returned for Correction" ? (
              <button type="button" className="primary" onClick={() => void act(row, "resubmit")}>
                Resubmit
              </button>
            ) : null}
            {canPlan && row.status === "Approved" ? (
              <button type="button" onClick={() => void act(row, "withdraw")}>
                Withdraw
              </button>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}

function Assessments({
  pid,
  board,
  canEdit,
  admin,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canEdit: boolean;
  admin: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [number, setNumber] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [disciplineId, setDisciplineId] = useState("");
  const [areaId, setAreaId] = useState("");
  const [packageId, setPackageId] = useState("");
  const [activityId, setActivityId] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [task, setTask] = useState("");
  const [steps, setSteps] = useState("");
  const [hazards, setHazards] = useState("");
  const [exposed, setExposed] = useState("");
  const [existing, setExisting] = useState("");
  const [initial, setInitial] = useState("");
  const [additional, setAdditional] = useState("");
  const [residual, setResidual] = useState("");
  const [owners, setOwners] = useState("");
  const [permits, setPermits] = useState("");
  const [competencies, setCompetencies] = useState("");
  const [preparedBy, setPreparedBy] = useState("");
  const [reviewOn, setReviewOn] = useState("");
  const activities = board.activities.filter((row) => String(row.package_id) === packageId);
  const approvedDocs = board.documents.filter((row) => row.status === "Approved");
  async function create(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/assessments`, "POST", {
        number,
        company_id: Number(companyId),
        discipline_id: disciplineId ? Number(disciplineId) : null,
        area_id: areaId ? Number(areaId) : null,
        package_id: packageId ? Number(packageId) : null,
        activity_id: activityId ? Number(activityId) : null,
        document_id: documentId ? Number(documentId) : null,
        task_description: task,
        steps,
        hazards,
        exposed,
        existing_controls: existing,
        initial_rating: initial,
        additional_controls: additional,
        residual_rating: residual,
        control_owners: owners,
        required_permits: permits,
        required_competencies: competencies,
        prepared_by: Number(preparedBy),
        review_on: reviewOn || null,
      });
      setNumber("");
      setTask("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function act(row: AssessmentRow, path: "submit" | "resubmit" | "withdraw" | "reassess") {
    onError("");
    const reason = path === "withdraw" ? window.prompt("Reason for withdrawal") || "" : "";
    if (path === "withdraw" && reason.trim().length < 3) return;
    const nextNumber = path === "reassess" ? window.prompt("New assessment number") || "" : "";
    if (path === "reassess" && !nextNumber.trim()) return;
    try {
      await api(`/projects/${pid}/hse/assessments/${row.id}/${path}`, "POST", {
        version: path === "resubmit" ? row.review?.version : row.version,
        reason,
        number: nextNumber,
      });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={ASSESSMENT_ROUTES} members={board.members} disciplines={board.disciplines} />
      <p className="muted">{board.rating_note}</p>
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <label>
            Number
            <input value={number} onChange={(event) => setNumber(event.target.value)} required maxLength={40} />
          </label>
          <label>
            Company
            <select value={companyId} onChange={(event) => setCompanyId(event.target.value)} required>
              <option value="">Choose a company</option>
              {board.companies.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Discipline
            <select value={disciplineId} onChange={(event) => setDisciplineId(event.target.value)}>
              <option value="">Not set</option>
              {board.disciplines.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Area
            <select value={areaId} onChange={(event) => setAreaId(event.target.value)}>
              <option value="">Not set</option>
              {board.areas.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Work package
            <select value={packageId} onChange={(event) => { setPackageId(event.target.value); setActivityId(""); }}>
              <option value="">Not set</option>
              {board.packages.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.code} · {row.status}
                </option>
              ))}
            </select>
          </label>
          <label>
            Activity
            <select value={activityId} onChange={(event) => setActivityId(event.target.value)}>
              <option value="">Not set</option>
              {activities.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.code} · {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Approved HSE document
            <select value={documentId} onChange={(event) => setDocumentId(event.target.value)}>
              <option value="">Not set</option>
              {approvedDocs.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.number} rev {row.revision_label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Task
            <input value={task} onChange={(event) => setTask(event.target.value)} required />
          </label>
          <label>
            Steps
            <input value={steps} onChange={(event) => setSteps(event.target.value)} />
          </label>
          <label>
            Hazards
            <input value={hazards} onChange={(event) => setHazards(event.target.value)} />
          </label>
          <label>
            Persons and assets exposed
            <input value={exposed} onChange={(event) => setExposed(event.target.value)} />
          </label>
          <label>
            Existing controls
            <input value={existing} onChange={(event) => setExisting(event.target.value)} />
          </label>
          <label>
            Initial rating
            <input value={initial} onChange={(event) => setInitial(event.target.value)} maxLength={80} />
          </label>
          <label>
            Additional controls
            <input value={additional} onChange={(event) => setAdditional(event.target.value)} />
          </label>
          <label>
            Residual rating
            <input value={residual} onChange={(event) => setResidual(event.target.value)} maxLength={80} />
          </label>
          <label>
            Control owners
            <input value={owners} onChange={(event) => setOwners(event.target.value)} />
          </label>
          <label>
            Required permits
            <input value={permits} onChange={(event) => setPermits(event.target.value)} />
          </label>
          <label>
            Required competencies
            <input value={competencies} onChange={(event) => setCompetencies(event.target.value)} />
          </label>
          <label>
            Prepared by
            <select value={preparedBy} onChange={(event) => setPreparedBy(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Review date
            <input type="date" value={reviewOn} onChange={(event) => setReviewOn(event.target.value)} />
          </label>
          <button className="primary" type="submit">
            Save draft
          </button>
        </form>
      ) : null}
      <div className="contact-grid">
        {board.assessments.map((row) => (
          <article key={row.id} className="contact-card">
            <header>
              <TriangleAlert size={15} />
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            <h4>{row.number}</h4>
            <p>{row.task_description}</p>
            {row.package_code ? (
              <p className="muted">
                Work package {row.package_code} stays {row.package_status || "unchanged"}
              </p>
            ) : null}
            {row.activity_code ? <p className="muted">Activity {row.activity_code}</p> : null}
            {row.document_label ? <p className="muted">Document {row.document_label}</p> : null}
            <p>
              Initial {row.initial_rating || "not written"} · Residual {row.residual_rating || "not written"}
            </p>
            <p className="muted">{row.statement}</p>
            {row.withdrawal_reason ? <p>Withdrawn: {row.withdrawal_reason}</p> : null}
            {canEdit && row.status === "Draft" ? (
              <button type="button" className="primary" onClick={() => void act(row, "submit")}>
                Submit
              </button>
            ) : null}
            {canEdit && row.status === "Returned for Correction" ? (
              <button type="button" className="primary" onClick={() => void act(row, "resubmit")}>
                Resubmit
              </button>
            ) : null}
            {canEdit && row.status === "Approved" ? (
              <button type="button" onClick={() => void act(row, "reassess")}>
                Reassess
              </button>
            ) : null}
            {canEdit && row.status === "Approved" ? (
              <button type="button" onClick={() => void act(row, "withdraw")}>
                Withdraw
              </button>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}

function stamp(value: string) {
  return value ? new Date(value).toISOString() : "";
}

function Permits({
  pid,
  board,
  canPlan,
  canEdit,
  admin,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  canEdit: boolean;
  admin: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const suggested = board.suggested_permit_types || [];
  const [typeName, setTypeName] = useState(suggested[0] || "");
  const [customType, setCustomType] = useState("");
  const [physical, setPhysical] = useState(false);
  const [handover, setHandover] = useState(false);
  const [typeId, setTypeId] = useState("");
  const [number, setNumber] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [areaId, setAreaId] = useState("");
  const [packageId, setPackageId] = useState("");
  const [activityId, setActivityId] = useState("");
  const [task, setTask] = useState("");
  const [applicant, setApplicant] = useState("");
  const [authority, setAuthority] = useState("");
  const [owner, setOwner] = useState("");
  const [issuer, setIssuer] = useState("");
  const [from, setFrom] = useState("");
  const [until, setUntil] = useState("");
  const [checks, setChecks] = useState("");
  const [conditions, setConditions] = useState("");
  const [crew, setCrew] = useState("");
  const [equipment, setEquipment] = useState("");
  const activities = board.activities.filter((row) => String(row.package_id) === packageId);
  async function saveType(event: FormEvent) {
    event.preventDefault();
    onError("");
    const name = typeName === "Other" ? customType : typeName;
    try {
      await api(`/projects/${pid}/hse/permit-types`, "POST", { name, physical_required: physical, handover_required: handover });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function create(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/permits`, "POST", {
        type_id: Number(typeId),
        number,
        company_id: Number(companyId),
        area_id: areaId ? Number(areaId) : null,
        package_id: packageId ? Number(packageId) : null,
        activity_id: activityId ? Number(activityId) : null,
        task_description: task,
        applicant_id: Number(applicant),
        performing_authority_id: Number(authority),
        area_owner_id: Number(owner),
        issuer_id: Number(issuer),
        valid_from: stamp(from),
        valid_until: stamp(until),
        checks: checks.split(",").map((item) => item.trim()).filter(Boolean),
        conditions,
        crew_note: crew,
        equipment_note: equipment,
      });
      setNumber("");
      setTask("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function post(row: PermitRow, path: string, extra: Record<string, unknown> = {}) {
    onError("");
    try {
      await api(`/projects/${pid}/hse/permits/${row.id}/${path}`, "POST", { version: row.version, ...extra });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={PERMIT_ROUTES} members={board.members} disciplines={board.disciplines} />
      <p className="muted">{board.permit_statement}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveType(event)}>
          <label>
            Permit type
            <select value={typeName} onChange={(event) => setTypeName(event.target.value)}>
              {suggested.map((name) => <option key={name}>{name}</option>)}
              <option>Other</option>
            </select>
          </label>
          {typeName === "Other" ? (
            <label>
              Project type name
              <input value={customType} onChange={(event) => setCustomType(event.target.value)} required />
            </label>
          ) : null}
          <label>
            Paper or external permit required
            <input type="checkbox" checked={physical} onChange={(event) => setPhysical(event.target.checked)} />
          </label>
          <label>
            Handover required when the responsible person changes
            <input type="checkbox" checked={handover} onChange={(event) => setHandover(event.target.checked)} />
          </label>
          <button className="primary" type="submit">Save type</button>
        </form>
      ) : null}
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <label>
            Type
            <select value={typeId} onChange={(event) => setTypeId(event.target.value)} required>
              <option value="">Choose a saved type</option>
              {(board.permit_types || []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Number<input value={number} onChange={(event) => setNumber(event.target.value)} required maxLength={40} /></label>
          <label>
            Company
            <select value={companyId} onChange={(event) => setCompanyId(event.target.value)} required>
              <option value="">Choose a company</option>
              {board.companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Area
            <select value={areaId} onChange={(event) => setAreaId(event.target.value)}>
              <option value="">Not set</option>
              {board.areas.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Work package
            <select value={packageId} onChange={(event) => { setPackageId(event.target.value); setActivityId(""); }}>
              <option value="">Not set</option>
              {board.packages.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.status}</option>)}
            </select>
          </label>
          <label>
            Activity
            <select value={activityId} onChange={(event) => setActivityId(event.target.value)}>
              <option value="">Whole package</option>
              {activities.map((row) => <option key={row.id} value={row.id}>{row.code}</option>)}
            </select>
          </label>
          <label>Task<input value={task} onChange={(event) => setTask(event.target.value)} required /></label>
          <label>
            Applicant
            <select value={applicant} onChange={(event) => setApplicant(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Performing authority
            <select value={authority} onChange={(event) => setAuthority(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Area owner
            <select value={owner} onChange={(event) => setOwner(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Permit issuer
            <select value={issuer} onChange={(event) => setIssuer(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Valid from<input type="datetime-local" value={from} onChange={(event) => setFrom(event.target.value)} required /></label>
          <label>Valid until<input type="datetime-local" value={until} onChange={(event) => setUntil(event.target.value)} required /></label>
          <label>Required checks<input value={checks} onChange={(event) => setChecks(event.target.value)} placeholder="Gas test, Fire watch" /></label>
          <label>Conditions<input value={conditions} onChange={(event) => setConditions(event.target.value)} /></label>
          <label>Crew<input value={crew} onChange={(event) => setCrew(event.target.value)} /></label>
          <label>Equipment<input value={equipment} onChange={(event) => setEquipment(event.target.value)} /></label>
          <button className="primary" type="submit">Save draft</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.permits || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header>
              <ShieldAlert size={15} />
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            <h4>{row.type_name} {row.number}</h4>
            <p>{row.task_description}</p>
            <p className="muted">Issuer {row.issuer_name}. Original end {row.valid_until || "not set"}. Effective end {row.effective_until || "not set"}.</p>
            {row.package_code ? <p className="muted">Covers {row.package_code}{row.activity_code ? ` / ${row.activity_code}` : ""}. Package stays {row.package_status}.</p> : null}
            <p className="muted">{row.statement}</p>
            {row.checks.map((check) => (
              <p key={check.id}>
                {check.name}: {check.acknowledged ? check.evidence : "not verified"}
                {canEdit && !check.acknowledged ? (
                  <button type="button" onClick={() => {
                    const evidence = window.prompt(`Evidence for ${check.name}`) || "";
                    if (evidence.trim()) void api(`/projects/${pid}/hse/permits/${row.id}/checks/${check.id}/verify`, "POST", { evidence, acknowledged: true }).then(reload).catch((err) => onError((err as Error).message));
                  }}>Verify</button>
                ) : null}
              </p>
            ))}
            {row.events.map((event) => <p key={event.id} className="muted">{event.kind}{event.note ? `: ${event.note}` : ""}</p>)}
            {canEdit && row.status === "Draft" ? <button type="button" className="primary" onClick={() => void post(row, "submit")}>Submit</button> : null}
            {canEdit && row.status === "Returned for Correction" ? <button type="button" className="primary" onClick={() => void post(row, "resubmit")}>Resubmit</button> : null}
            {row.status === "Authorized" || row.status === "Suspended" ? <button type="button" className="primary" onClick={() => void post(row, "activate")}>Activate</button> : null}
            {row.status === "Active" ? <button type="button" onClick={() => {
              const reason = window.prompt("Suspension reason") || "";
              if (reason.trim().length >= 3) void post(row, "suspend", { reason });
            }}>Suspend</button> : null}
            {row.status === "Active" || row.status === "Expired" || row.status === "Suspended" || row.status === "Authorized" ? <button type="button" onClick={() => {
              const valid = window.prompt("New end, as YYYY-MM-DDTHH:MM") || "";
              const reason = window.prompt("Extension reason") || "";
              if (valid && reason.trim().length >= 3) void post(row, "extend", { valid_until: stamp(valid), reason });
            }}>Extend</button> : null}
          </article>
        ))}
      </div>
    </>
  );
}

function Isolations({
  pid,
  board,
  canPlan,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  canEdit: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [kind, setKind] = useState((board.isolation_kinds || [])[0] || "Isolation Certificate");
  const [number, setNumber] = useState("");
  const [authority, setAuthority] = useState("");
  const [evidence, setEvidence] = useState("");
  const [allow, setAllow] = useState(false);
  async function create(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/isolations`, "POST", {
        kind,
        number,
        authority_id: Number(authority),
        evidence,
        allow_removal_with_active_permit: allow,
      });
      setNumber("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="muted">Approval and removal are separate actions. An isolation stays in force while a dependent permit is authorized, active, or suspended, unless the saved procedure explicitly allows removal.</p>
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <label>
            Kind
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {(board.isolation_kinds || []).map((name) => <option key={name}>{name}</option>)}
            </select>
          </label>
          <label>Number<input value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label>
            Authority
            <select value={authority} onChange={(event) => setAuthority(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Evidence<input value={evidence} onChange={(event) => setEvidence(event.target.value)} /></label>
          <label>
            Procedure allows removal while a permit is still active
            <input type="checkbox" checked={allow} onChange={(event) => setAllow(event.target.checked)} />
          </label>
          <button className="primary" type="submit">Save draft</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.isolations || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header>
              <LockKeyhole size={15} />
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            <h4>{row.kind} {row.number}</h4>
            <p className="muted">Authority {row.authority_name}. Dependent permits {row.permit_ids.length}.</p>
            {canPlan && row.status === "Draft" ? (
              <button type="button" className="primary" onClick={() => void api(`/projects/${pid}/hse/isolations/${row.id}/approve`, "POST", { version: row.version }).then(reload).catch((err) => onError((err as Error).message))}>Approve</button>
            ) : null}
            {canEdit && row.status === "In Force" ? (
              <button type="button" onClick={() => {
                const reason = window.prompt("Removal reason") || "";
                if (reason.trim().length >= 3) void api(`/projects/${pid}/hse/isolations/${row.id}/remove`, "POST", { version: row.version, reason }).then(reload).catch((err) => onError((err as Error).message));
              }}>Remove</button>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}

function Workfront({
  pid,
  board,
  canPlan,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  canEdit: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [note, setNote] = useState("");
  async function saveRule(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/conflict-rules`, "POST", {
        type_a_id: Number(left),
        type_b_id: Number(right),
        same_area: true,
        require_decision: true,
        note,
      });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="note-card">{board.simops_note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveRule(event)}>
          <label>
            First permit type
            <select value={left} onChange={(event) => setLeft(event.target.value)} required>
              <option value="">Choose</option>
              {(board.permit_types || []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Second permit type
            <select value={right} onChange={(event) => setRight(event.target.value)} required>
              <option value="">Choose</option>
              {(board.permit_types || []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Rule note<input value={note} onChange={(event) => setNote(event.target.value)} /></label>
          <button className="primary" type="submit">Save conflict rule</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.conflicts || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header>
              <Waypoints size={15} />
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            <h4>{row.permit_number} overlaps {row.other_number}</h4>
            <p>{row.decision || "No coordination decision yet."}</p>
            {row.controls ? <p className="muted">{row.controls}</p> : null}
            {canEdit && row.status === "Open" ? (
              <button type="button" className="primary" onClick={() => {
                const decision = window.prompt("Coordination decision") || "";
                const controls = window.prompt("Controls") || "";
                if (decision.trim().length >= 3 && controls.trim().length >= 3) {
                  void api(`/projects/${pid}/hse/permits/${row.permit_id}/coordination`, "POST", { other_permit_id: row.other_permit_id, decision, controls }).then(reload).catch((err) => onError((err as Error).message));
                }
              }}>Record decision</button>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}

function packageName(board: Board, packageId: number | null) {
  if (!packageId) return "Whole project";
  return board.packages.find((row) => row.id === packageId)?.code || "Work package";
}

function Induction({
  pid,
  board,
  canPlan,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  canEdit: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const suggested = board.suggested_eligibility || [];
  const [category, setCategory] = useState(suggested[0] || "");
  const [other, setOther] = useState("");
  const [packageId, setPackageId] = useState("");
  const [memberId, setMemberId] = useState("");
  const [recordCategory, setRecordCategory] = useState(suggested[0] || "");
  const [evidence, setEvidence] = useState("");
  const [expires, setExpires] = useState("");
  const chosen = category === "Other" ? other : category;
  async function saveRule(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/eligibility-rules`, "POST", { category: chosen, package_id: packageId ? Number(packageId) : null });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveRecord(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/eligibility`, "POST", {
        member_id: Number(memberId),
        category: recordCategory,
        evidence,
        expires_on: expires || null,
      });
      setEvidence("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="note-card">{board.eligibility_note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveRule(event)}>
          <label>
            Required category
            <select aria-label="Required category" value={category} onChange={(event) => setCategory(event.target.value)}>
              {suggested.map((name) => <option key={name}>{name}</option>)}
              <option>Other</option>
            </select>
          </label>
          {category === "Other" ? <label>Category name<input value={other} onChange={(event) => setOther(event.target.value)} required /></label> : null}
          <label>
            Work package
            <select aria-label="Eligibility work package" value={packageId} onChange={(event) => setPackageId(event.target.value)}>
              <option value="">Whole project</option>
              {board.packages.map((row) => <option key={row.id} value={row.id}>{row.code}</option>)}
            </select>
          </label>
          <button className="primary" type="submit">Save rule</button>
        </form>
      ) : null}
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void saveRecord(event)}>
          <label>
            Person
            <select value={memberId} onChange={(event) => setMemberId(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Evidence category
            <select aria-label="Evidence category" value={recordCategory} onChange={(event) => setRecordCategory(event.target.value)}>
              {suggested.map((name) => <option key={name}>{name}</option>)}
            </select>
          </label>
          <label>Evidence<input value={evidence} onChange={(event) => setEvidence(event.target.value)} required /></label>
          <label>Expires<input type="date" value={expires} onChange={(event) => setExpires(event.target.value)} /></label>
          <button className="primary" type="submit">Save evidence</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.eligibility_rules || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header><BadgeCheck size={15} /></header>
            <h4>{row.category}</h4>
            <p className="muted">Required for {packageName(board, row.package_id)}. An assignment is blocked only when this evidence is missing or expired on the work date.</p>
          </article>
        ))}
        {(board.eligibility || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header>
              <BadgeCheck size={15} />
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            <h4>{row.member_name}</h4>
            <p>{row.category}</p>
            <p className="muted">{row.evidence}</p>
            <p className="muted">Expires {row.expires_on || "not set"}. {row.statement}</p>
            {canPlan && row.status === "Recorded" ? (
              <button type="button" className="primary" onClick={() => void api(`/projects/${pid}/hse/eligibility/${row.id}/verify`, "POST", { version: row.version }).then(reload).catch((err) => onError((err as Error).message))}>Verify</button>
            ) : null}
          </article>
        ))}
        {(board.gaps || []).map((row) => (
          <article key={`${row.member_id}-${row.category}`} className="contact-card">
            <h4>{row.member_name}</h4>
            <p>{row.category} · {row.reason}</p>
          </article>
        ))}
      </div>
    </>
  );
}

function Toolbox({
  pid,
  board,
  canPlan,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  canEdit: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [rulePackage, setRulePackage] = useState("");
  const [number, setNumber] = useState("");
  const [talkOn, setTalkOn] = useState("");
  const [shift, setShift] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [packageId, setPackageId] = useState("");
  const [topic, setTopic] = useState("");
  const [presenter, setPresenter] = useState("");
  const [issues, setIssues] = useState("");
  const [followUp, setFollowUp] = useState("");
  async function saveRule(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/toolbox-rules`, "POST", { package_id: rulePackage ? Number(rulePackage) : null });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveTalk(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/toolbox`, "POST", {
        number,
        talk_on: talkOn,
        shift,
        company_id: Number(companyId),
        package_id: packageId ? Number(packageId) : null,
        topic,
        presenter_id: Number(presenter),
        issues,
        follow_up: followUp,
      });
      setNumber("");
      setTopic("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="note-card">{board.toolbox_note}</p>
      <p className="muted">{board.follow_up_note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveRule(event)}>
          <label>
            Toolbox work package
            <select aria-label="Toolbox work package" value={rulePackage} onChange={(event) => setRulePackage(event.target.value)}>
              <option value="">Whole project</option>
              {board.packages.map((row) => <option key={row.id} value={row.id}>{row.code}</option>)}
            </select>
          </label>
          <button className="primary" type="submit">Save toolbox rule</button>
        </form>
      ) : null}
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void saveTalk(event)}>
          <label>Number<input value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label>Date<input type="date" value={talkOn} onChange={(event) => setTalkOn(event.target.value)} required /></label>
          <label>Shift<input value={shift} onChange={(event) => setShift(event.target.value)} /></label>
          <label>
            Company
            <select value={companyId} onChange={(event) => setCompanyId(event.target.value)} required>
              <option value="">Choose a company</option>
              {board.companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Talk work package
            <select aria-label="Talk work package" value={packageId} onChange={(event) => setPackageId(event.target.value)}>
              <option value="">Not set</option>
              {board.packages.map((row) => <option key={row.id} value={row.id}>{row.code}</option>)}
            </select>
          </label>
          <label>Topic<input value={topic} onChange={(event) => setTopic(event.target.value)} required /></label>
          <label>
            Presenter
            <select value={presenter} onChange={(event) => setPresenter(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Issues raised<input value={issues} onChange={(event) => setIssues(event.target.value)} /></label>
          <label>Follow-up<input value={followUp} onChange={(event) => setFollowUp(event.target.value)} /></label>
          <button className="primary" type="submit">Save talk</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.talks || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header>
              <Megaphone size={15} />
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            <h4>{row.number}</h4>
            <p>{row.topic}</p>
            <p className="muted">{row.talk_on} {row.shift}. Presenter {row.presenter_name}.</p>
            <p className="muted">{row.statement}</p>
            {row.acknowledgments.map((ack) => <p key={`${ack.member_name}-${ack.evidence}`}>{ack.member_name}: {ack.evidence}</p>)}
            {canEdit && row.status === "Draft" ? (
              <button type="button" className="primary" onClick={() => void api(`/projects/${pid}/hse/toolbox/${row.id}/hold`, "POST", { version: row.version }).then(reload).catch((err) => onError((err as Error).message))}>Mark held</button>
            ) : null}
            {canEdit && row.status === "Held" ? <Acknowledge pid={pid} talkId={row.id} members={board.members} onError={onError} reload={reload} /> : null}
          </article>
        ))}
      </div>
    </>
  );
}

function Acknowledge({
  pid,
  talkId,
  members,
  onError,
  reload,
}: {
  pid: number;
  talkId: number;
  members: Person[];
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [memberId, setMemberId] = useState("");
  const [evidence, setEvidence] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/toolbox/${talkId}/acknowledgments`, "POST", { member_id: Number(memberId), evidence });
      setEvidence("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <form onSubmit={(event) => void save(event)}>
      <label>
        Attendee
        <select aria-label="Attendee" value={memberId} onChange={(event) => setMemberId(event.target.value)} required>
          <option value="">Choose a member</option>
          {members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
      </label>
      <label>Acknowledgment<input value={evidence} onChange={(event) => setEvidence(event.target.value)} required /></label>
      <button type="submit">Acknowledge</button>
    </form>
  );
}

function Inspections({
  pid,
  board,
  canPlan,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  canEdit: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const types = board.inspection_types || [];
  const observationTypes = board.observation_types || [];
  const [severity, setSeverity] = useState("");
  const [blocks, setBlocks] = useState(false);
  const [number, setNumber] = useState("");
  const [inspectionType, setInspectionType] = useState(types[0] || "Routine");
  const [companyId, setCompanyId] = useState("");
  const [packageId, setPackageId] = useState("");
  const [inspector, setInspector] = useState("");
  const [inspectedOn, setInspectedOn] = useState("");
  const [finding, setFinding] = useState("");
  const [findingSeverity, setFindingSeverity] = useState("");
  const [owner, setOwner] = useState("");
  const [obsNumber, setObsNumber] = useState("");
  const [obsType, setObsType] = useState(observationTypes[0] || "Unsafe Condition");
  const [description, setDescription] = useState("");
  async function saveRule(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/finding-rules`, "POST", { severity, blocks_work: blocks });
      setSeverity("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveInspection(event: FormEvent) {
    event.preventDefault();
    onError("");
    const findings = finding.trim()
      ? [{ description: finding, severity: findingSeverity, owner_id: Number(owner), action: "", photo_reference: "" }]
      : [];
    try {
      await api(`/projects/${pid}/hse/inspections`, "POST", {
        number,
        inspection_type: inspectionType,
        company_id: Number(companyId),
        package_id: packageId ? Number(packageId) : null,
        inspector_id: Number(inspector),
        inspected_on: inspectedOn,
        findings,
      });
      setNumber("");
      setFinding("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveObservation(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/observations`, "POST", { number: obsNumber, observation_type: obsType, description });
      setObsNumber("");
      setDescription("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="note-card">{board.inspection_note}</p>
      <p className="muted">{board.observation_note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveRule(event)}>
          <label>Severity word<input value={severity} onChange={(event) => setSeverity(event.target.value)} required /></label>
          <label>
            Blocks the named work
            <input type="checkbox" checked={blocks} onChange={(event) => setBlocks(event.target.checked)} />
          </label>
          <button className="primary" type="submit">Save finding rule</button>
        </form>
      ) : null}
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void saveInspection(event)}>
          <label>Number<input aria-label="Inspection number" value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label>
            Type
            <select aria-label="Inspection type" value={inspectionType} onChange={(event) => setInspectionType(event.target.value)}>
              {types.map((name) => <option key={name}>{name}</option>)}
            </select>
          </label>
          <label>
            Company
            <select aria-label="Inspection company" value={companyId} onChange={(event) => setCompanyId(event.target.value)} required>
              <option value="">Choose a company</option>
              {board.companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Inspection work package
            <select aria-label="Inspection work package" value={packageId} onChange={(event) => setPackageId(event.target.value)}>
              <option value="">Not set</option>
              {board.packages.map((row) => <option key={row.id} value={row.id}>{row.code}</option>)}
            </select>
          </label>
          <label>
            Inspector
            <select value={inspector} onChange={(event) => setInspector(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Date<input type="date" aria-label="Inspection date" value={inspectedOn} onChange={(event) => setInspectedOn(event.target.value)} required /></label>
          <label>Finding<input value={finding} onChange={(event) => setFinding(event.target.value)} /></label>
          <label>Finding severity<input value={findingSeverity} onChange={(event) => setFindingSeverity(event.target.value)} /></label>
          <label>
            Responsible owner
            <select value={owner} onChange={(event) => setOwner(event.target.value)}>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <button className="primary" type="submit">Save inspection</button>
        </form>
      ) : null}
      <form className="contact-form" onSubmit={(event) => void saveObservation(event)}>
        <label>Observation number<input value={obsNumber} onChange={(event) => setObsNumber(event.target.value)} required /></label>
        <label>
          Observation type
          <select aria-label="Observation type" value={obsType} onChange={(event) => setObsType(event.target.value)}>
            {observationTypes.map((name) => <option key={name}>{name}</option>)}
          </select>
        </label>
        <label>What was seen<input value={description} onChange={(event) => setDescription(event.target.value)} required /></label>
        <button className="primary" type="submit">Report observation</button>
      </form>
      <div className="contact-grid">
        {(board.finding_rules || []).map((row) => (
          <article key={row.id} className="contact-card">
            <h4>{row.severity}</h4>
            <p className="muted">{row.blocks_work ? "This severity blocks the inspection's work package until the finding is closed." : "This severity is recorded and does not block work."}</p>
          </article>
        ))}
        {(board.inspections || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header>
              <ClipboardCheck size={15} />
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            <h4>{row.number}</h4>
            <p>{row.inspection_type} · {row.inspected_on} · {row.inspector_name}</p>
            <p className="muted">{row.statement}</p>
            {row.findings.map((item) => (
              <p key={item.id}>
                {item.severity}: {item.description} · {item.status}
                {canPlan && item.status === "Open" ? (
                  <button type="button" onClick={() => {
                    const evidence = window.prompt("Close evidence") || "";
                    if (evidence.trim().length >= 3) void api(`/projects/${pid}/hse/findings/${item.id}/close`, "POST", { version: item.version, evidence }).then(reload).catch((err) => onError((err as Error).message));
                  }}>Close finding</button>
                ) : null}
              </p>
            ))}
          </article>
        ))}
        {(board.observations || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header><TriangleAlert size={15} /><span className={statusChip(row.status)}>{row.status}</span></header>
            <h4>{row.number}</h4>
            <p>{row.observation_type}. {row.description}</p>
            <p className="muted">{row.reporter_name}. {row.statement}</p>
          </article>
        ))}
      </div>
    </>
  );
}

function Incidents({
  pid,
  board,
  canPlan,
  admin,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  admin: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const suggestions = board.suggested_incident_categories || [];
  const [categoryName, setCategoryName] = useState(suggestions[0] || "");
  const [severity, setSeverity] = useState("");
  const [requires, setRequires] = useState(true);
  const [number, setNumber] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [eventAt, setEventAt] = useState("");
  const [timezoneName, setTimezoneName] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [packageId, setPackageId] = useState("");
  const [description, setDescription] = useState("");
  const [severityText, setSeverityText] = useState("");
  const [classification, setClassification] = useState("");
  async function saveCategory(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/incident-categories`, "POST", { name: categoryName });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveRule(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/incident-rules`, "POST", { severity, requires_investigation: requires });
      setSeverity("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveReport(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/incidents`, "POST", {
        category_id: Number(categoryId),
        number,
        event_at: stamp(eventAt),
        timezone_name: timezoneName,
        company_id: Number(companyId),
        package_id: packageId ? Number(packageId) : null,
        description,
        initial_severity: severityText,
      });
      setNumber("");
      setDescription("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function investigate(row: IncidentRow) {
    onError("");
    try {
      await api(`/projects/${pid}/hse/incidents/${row.id}/investigate`, "POST", {
        version: row.version,
        verified_classification: classification || row.category,
        team_ids: [],
      });
      setClassification("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function submit(row: IncidentRow) {
    onError("");
    try {
      await api(`/projects/${pid}/hse/incidents/${row.id}/submit`, "POST", { version: row.version });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="note-card">{board.incident_statement}</p>
      <HseRoutes pid={pid} admin={admin} routes={INCIDENT_ROUTES} members={board.members} disciplines={board.disciplines} />
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveCategory(event)}>
          <div className="option-grid">
            {[...suggestions, "Other"].map((name) => (
              <button key={name} type="button" className={categoryName === name ? "is-on" : ""} onClick={() => setCategoryName(name === "Other" ? "" : name)}>
                {name}
              </button>
            ))}
          </div>
          <label>Category name<input aria-label="Incident category" value={categoryName} onChange={(event) => setCategoryName(event.target.value)} required /></label>
          <button className="primary" type="submit">Save category</button>
        </form>
      ) : null}
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveRule(event)}>
          <label>Initial severity word<input aria-label="Incident severity rule" value={severity} onChange={(event) => setSeverity(event.target.value)} required /></label>
          <label>
            Investigation required before closure
            <input type="checkbox" checked={requires} onChange={(event) => setRequires(event.target.checked)} />
          </label>
          <button className="primary" type="submit">Save severity rule</button>
        </form>
      ) : null}
      <form className="contact-form" onSubmit={(event) => void saveReport(event)}>
        <label>Incident number<input aria-label="Incident number" value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
        <label>
          Category
          <select aria-label="Incident category choice" value={categoryId} onChange={(event) => setCategoryId(event.target.value)} required>
            <option value="">Choose a saved category</option>
            {(board.incident_categories || []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>Event time<input type="datetime-local" aria-label="Event time" value={eventAt} onChange={(event) => setEventAt(event.target.value)} required /></label>
        <label>Timezone<input aria-label="Event timezone" placeholder="IST" value={timezoneName} onChange={(event) => setTimezoneName(event.target.value)} required /></label>
        <label>
          Company
          <select aria-label="Incident company" value={companyId} onChange={(event) => setCompanyId(event.target.value)} required>
            <option value="">Choose a company</option>
            {board.companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>
          Work package
          <select aria-label="Incident work package" value={packageId} onChange={(event) => setPackageId(event.target.value)}>
            <option value="">Not set</option>
            {board.packages.map((row) => <option key={row.id} value={row.id}>{row.code}</option>)}
          </select>
        </label>
        <label>What happened<textarea aria-label="Incident description" value={description} onChange={(event) => setDescription(event.target.value)} required /></label>
        <label>Initial severity<input aria-label="Initial severity" value={severityText} onChange={(event) => setSeverityText(event.target.value)} /></label>
        <button className="primary" type="submit">Report incident</button>
      </form>
      <div className="contact-grid">
        {(board.incident_rules || []).map((row) => (
          <article key={row.id} className="contact-card">
            <h4>{row.severity}</h4>
            <p className="muted">{row.requires_investigation ? "Closure waits for an investigation." : "Closure does not wait for an investigation."}</p>
          </article>
        ))}
        {(board.incidents || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header><Siren size={15} /><span className={statusChip(row.status)}>{row.status}</span></header>
            <h4>{row.number}</h4>
            <p>{row.category} · {row.timezone_name}{row.package_status ? ` · Package ${row.package_status}` : ""}</p>
            <p>{row.description}</p>
            <p className="muted">{row.reporter_name}. {row.statement}</p>
            {row.verified_classification ? <p>Verified classification: {row.verified_classification}</p> : null}
            {canPlan && ["Reported", "Under Investigation", "Returned for Correction"].includes(row.status) ? (
              <>
                <label>Verified classification<input aria-label={`Classification ${row.number}`} value={classification} onChange={(event) => setClassification(event.target.value)} /></label>
                <button type="button" onClick={() => void investigate(row)}>Record investigation</button>
                <button type="button" className="primary" onClick={() => void submit(row)}>Submit closure</button>
              </>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}

function Actions({
  pid,
  board,
  userId,
  canPlan,
  canEdit,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  userId: number;
  canPlan: boolean;
  canEdit: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [number, setNumber] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [verifierId, setVerifierId] = useState("");
  const [interim, setInterim] = useState("");
  const [evidence, setEvidence] = useState("");
  const [effectiveness, setEffectiveness] = useState("");
  const [required, setRequired] = useState(board.action_rule?.effectiveness_required || false);
  async function saveRule(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/action-rules`, "POST", { effectiveness_required: required });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveAction(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/actions`, "POST", {
        number,
        description,
        severity,
        company_id: Number(companyId),
        owner_id: Number(ownerId),
        verifier_id: Number(verifierId),
        interim_controls: interim,
      });
      setNumber("");
      setDescription("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function post(row: ActionRow, path: string, body: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/hse/actions/${row.id}/${path}`, "POST", { version: row.version, ...body });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="note-card">{board.action_note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveRule(event)}>
          <label>
            Effectiveness review required before closure
            <input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} />
          </label>
          <button className="primary" type="submit">Save action rule</button>
        </form>
      ) : null}
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void saveAction(event)}>
          <label>Action number<input aria-label="Action number" value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label>What must be done<textarea aria-label="Action description" value={description} onChange={(event) => setDescription(event.target.value)} required /></label>
          <label>Risk or severity<input aria-label="Action severity" value={severity} onChange={(event) => setSeverity(event.target.value)} /></label>
          <label>
            Company
            <select aria-label="Action company" value={companyId} onChange={(event) => setCompanyId(event.target.value)} required>
              <option value="">Choose a company</option>
              {board.companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Owner
            <select aria-label="Action owner" value={ownerId} onChange={(event) => setOwnerId(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Verifier
            <select aria-label="Action verifier" value={verifierId} onChange={(event) => setVerifierId(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Interim controls<input value={interim} onChange={(event) => setInterim(event.target.value)} /></label>
          <button className="primary" type="submit">Save action</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.actions || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header><ListChecks size={15} /><span className={statusChip(row.status)}>{row.status}</span></header>
            <h4>{row.number}</h4>
            <p>{row.description}</p>
            <p className="muted">{row.owner_name} owns it. {row.verifier_name} verifies it. {row.statement}</p>
            {row.task_status ? <p className="muted">Task {row.task_status}</p> : null}
            {userId === row.owner_id && ["Open", "In Progress"].includes(row.status) ? (
              <>
                <label>Evidence<input aria-label={`Evidence ${row.number}`} value={evidence} onChange={(event) => setEvidence(event.target.value)} /></label>
                <button type="button" onClick={() => void post(row, "evidence", { evidence })}>Submit evidence</button>
              </>
            ) : null}
            {userId === row.verifier_id && row.status === "Pending Verification" ? (
              <>
                <label>Effectiveness<input aria-label={`Effectiveness ${row.number}`} value={effectiveness} onChange={(event) => setEffectiveness(event.target.value)} /></label>
                <button type="button" className="primary" onClick={() => void post(row, "close", { effectiveness })}>Close action</button>
              </>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}

function Holds({
  pid,
  board,
  userId,
  canPlan,
  admin,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  userId: number;
  canPlan: boolean;
  admin: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [issuer, setIssuer] = useState("");
  const [separate, setSeparate] = useState(board.hold_rule?.separate_release || false);
  const [number, setNumber] = useState("");
  const [reason, setReason] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [scopeKind, setScopeKind] = useState("package");
  const [packageId, setPackageId] = useState("");
  const [areaId, setAreaId] = useState("");
  const [equipment, setEquipment] = useState("");
  const [affected, setAffected] = useState("");
  const [restricted, setRestricted] = useState("");
  const [conditions, setConditions] = useState("");
  const [evidence, setEvidence] = useState("");
  const [concernNumber, setConcernNumber] = useState("");
  const [concernReason, setConcernReason] = useState("");
  async function saveIssuer(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/hold-issuers`, "POST", { user_id: Number(issuer) });
      setIssuer("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveRule(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/hold-rules`, "POST", { separate_release: separate });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveConcern(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/concerns`, "POST", {
        number: concernNumber,
        company_id: Number(companyId),
        reason: concernReason,
        package_id: packageId ? Number(packageId) : null,
      });
      setConcernNumber("");
      setConcernReason("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveHold(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/holds`, "POST", {
        number,
        company_id: Number(companyId),
        owner_id: Number(ownerId),
        reason,
        source: "Field",
        scope_kind: scopeKind,
        package_id: packageId ? Number(packageId) : null,
        area_id: areaId ? Number(areaId) : null,
        equipment_note: equipment,
        affected_work: affected,
        restricted_actions: restricted,
        release_conditions: conditions,
      });
      setNumber("");
      setReason("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function requestRelease(row: HoldRow) {
    onError("");
    try {
      await api(`/projects/${pid}/hse/holds/${row.id}/release`, "POST", { version: row.version, evidence });
      setEvidence("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="note-card">{board.hold_note}</p>
      <p className="muted">{board.concern_note}</p>
      <HseRoutes pid={pid} admin={admin} routes={HOLD_ROUTES} members={board.members} disciplines={board.disciplines} />
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveIssuer(event)}>
          <label>
            Hold issuer
            <select aria-label="Hold issuer" value={issuer} onChange={(event) => setIssuer(event.target.value)} required>
              <option value="">Choose a member</option>
              {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <button className="primary" type="submit">Save hold issuer</button>
        </form>
      ) : null}
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveRule(event)}>
          <label>
            Issuer cannot own or release the hold
            <input type="checkbox" checked={separate} onChange={(event) => setSeparate(event.target.checked)} />
          </label>
          <button className="primary" type="submit">Save hold rule</button>
        </form>
      ) : null}
      <form className="contact-form" onSubmit={(event) => void saveConcern(event)}>
        <label>Concern number<input aria-label="Concern number" value={concernNumber} onChange={(event) => setConcernNumber(event.target.value)} required /></label>
        <label>
          Company
          <select aria-label="Concern company" value={companyId} onChange={(event) => setCompanyId(event.target.value)} required>
            <option value="">Choose a company</option>
            {board.companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>What was seen<textarea aria-label="Concern" value={concernReason} onChange={(event) => setConcernReason(event.target.value)} required /></label>
        <button className="primary" type="submit">Report concern</button>
      </form>
      <form className="contact-form" onSubmit={(event) => void saveHold(event)}>
        <label>Hold number<input aria-label="Hold number" value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
        <label>
          Scope
          <select aria-label="Hold scope" value={scopeKind} onChange={(event) => setScopeKind(event.target.value)}>
            <option value="package">Work package</option>
            <option value="activity">Activity</option>
            <option value="area">Location</option>
            <option value="equipment">Equipment</option>
            <option value="work">Affected work</option>
          </select>
        </label>
        <label>
          Work package
          <select aria-label="Hold work package" value={packageId} onChange={(event) => setPackageId(event.target.value)}>
            <option value="">Not set</option>
            {board.packages.map((row) => <option key={row.id} value={row.id}>{row.code}</option>)}
          </select>
        </label>
        <label>
          Location
          <select aria-label="Hold location" value={areaId} onChange={(event) => setAreaId(event.target.value)}>
            <option value="">Not set</option>
            {board.areas.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>Equipment<input aria-label="Hold equipment" value={equipment} onChange={(event) => setEquipment(event.target.value)} /></label>
        <label>Affected work<input aria-label="Affected work" value={affected} onChange={(event) => setAffected(event.target.value)} /></label>
        <label>
          Responsible owner
          <select aria-label="Hold owner" value={ownerId} onChange={(event) => setOwnerId(event.target.value)} required>
            <option value="">Choose a member</option>
            {board.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>Reason<textarea aria-label="Hold reason" value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
        <label>Restricted actions<input aria-label="Restricted actions" value={restricted} onChange={(event) => setRestricted(event.target.value)} required /></label>
        <label>Release conditions<input aria-label="Release conditions" value={conditions} onChange={(event) => setConditions(event.target.value)} required /></label>
        <button className="primary" type="submit">Place hold</button>
      </form>
      <div className="contact-grid">
        {(board.hold_issuers || []).map((row) => (
          <article key={row.id} className="contact-card">
            <h4>{row.name}</h4>
            <p className="muted">Saved hold issuer</p>
          </article>
        ))}
        {(board.holds || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header><Ban size={15} /><span className={statusChip(row.status)}>{row.status}</span></header>
            <h4>{row.number}</h4>
            <p>{row.kind}{row.scope_kind ? ` · ${row.scope_kind}` : ""}{row.package_status ? ` · Package ${row.package_status}` : ""}</p>
            <p>{row.reason}</p>
            <p className="muted">{row.issuer_name ? `${row.issuer_name} issued it. ` : ""}{row.owner_name ? `${row.owner_name} owns the release. ` : ""}{row.statement}</p>
            {userId === row.owner_id && row.status === "Active" ? (
              <>
                <label>Release evidence<input aria-label={`Release evidence ${row.number}`} value={evidence} onChange={(event) => setEvidence(event.target.value)} /></label>
                <button type="button" onClick={() => void requestRelease(row)}>Request release</button>
              </>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}

function Emergency({
  pid,
  board,
  canPlan,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [procedure, setProcedure] = useState(board.emergency_rule?.procedure || "");
  const [days, setDays] = useState(board.emergency_rule?.review_days ? String(board.emergency_rule.review_days) : "");
  const [contactId, setContactId] = useState("");
  const [role, setRole] = useState("");
  const [muster, setMuster] = useState("");
  const [musterNote, setMusterNote] = useState("");
  const [gear, setGear] = useState("");
  const [location, setLocation] = useState("");
  const [planNumber, setPlanNumber] = useState("");
  const [planTitle, setPlanTitle] = useState("");
  const [planRef, setPlanRef] = useState("");
  const [drillNumber, setDrillNumber] = useState("");
  const [drillTitle, setDrillTitle] = useState("");
  const [plannedOn, setPlannedOn] = useState("");
  const [findings, setFindings] = useState("");
  const [memberId, setMemberId] = useState("");
  const [evidence, setEvidence] = useState("");
  const contacts = (board.project_contacts || []).filter((row) => row.active);
  async function saveRule(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/emergency-rules`, "POST", {
        procedure,
        review_days: days ? Number(days) : null,
      });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveContact(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/emergency-contacts`, "POST", { contact_id: Number(contactId), response_role: role });
      setRole("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function verify(row: { id: number; version: number }) {
    onError("");
    try {
      await api(`/projects/${pid}/hse/emergency-contacts/${row.id}/verify`, "POST", { version: row.version });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveMuster(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/muster-points`, "POST", { name: muster, note: musterNote });
      setMuster("");
      setMusterNote("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveGear(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/emergency-gear`, "POST", { name: gear, location });
      setGear("");
      setLocation("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function savePlan(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/emergency-plans`, "POST", { number: planNumber, title: planTitle, engineering_reference: planRef });
      setPlanNumber("");
      setPlanTitle("");
      setPlanRef("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveDrill(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/drills`, "POST", { number: drillNumber, title: drillTitle, planned_on: plannedOn, findings });
      setDrillNumber("");
      setDrillTitle("");
      setFindings("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function hold(row: { id: number; version: number }) {
    onError("");
    try {
      await api(`/projects/${pid}/hse/drills/${row.id}/hold`, "POST", { version: row.version });
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function acknowledge(row: { id: number }) {
    onError("");
    try {
      await api(`/projects/${pid}/hse/drills/${row.id}/acknowledgments`, "POST", { member_id: Number(memberId), evidence });
      setEvidence("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="note-card">{board.emergency_note}</p>
      <p className="muted">{board.emergency_rule?.procedure ? `Approved communication procedure: ${board.emergency_rule.procedure}` : "The approved communication procedure is not named yet. This application does not place the emergency call."}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveRule(event)}>
          <label>Communication procedure<textarea aria-label="Communication procedure" value={procedure} onChange={(event) => setProcedure(event.target.value)} /></label>
          <label>Review interval in days<input aria-label="Review interval" value={days} onChange={(event) => setDays(event.target.value)} /></label>
          <button className="primary" type="submit">Save procedure</button>
        </form>
      ) : null}
      <p className="muted">Add the person on Project contacts first. Phone and email stay there.</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveContact(event)}>
          <label>
            Project contact
            <select aria-label="Emergency contact" value={contactId} onChange={(event) => setContactId(event.target.value)} required>
              <option value="">Choose a contact</option>
              {contacts.map((row) => <option key={row.id} value={row.id}>{row.name} · {row.function}</option>)}
            </select>
          </label>
          <label>
            Response role
            <input aria-label="Response role" list="response-roles" value={role} onChange={(event) => setRole(event.target.value)} required />
            <datalist id="response-roles">
              {(board.suggested_response_roles || []).map((name) => <option key={name} value={name} />)}
            </datalist>
          </label>
          <button className="primary" type="submit">Save contact</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.emergency_contacts || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header><LifeBuoy size={15} /><span className={statusChip(row.status)}>{row.status}</span></header>
            <h4>{row.name}</h4>
            <p>{row.response_role} · {row.function}</p>
            <p className="muted">{row.phone || row.email ? `${row.phone || ""} ${row.email || ""}` : "Phone and email stay on the project contact."}</p>
            {row.review_due_on ? <p className="muted">Review due {row.review_due_on}</p> : null}
            <p className="muted">{row.statement}</p>
            {canPlan && row.status === "Recorded" ? <button type="button" onClick={() => void verify(row)}>Verify</button> : null}
          </article>
        ))}
      </div>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveMuster(event)}>
          <label>Muster point<input aria-label="Muster point" value={muster} onChange={(event) => setMuster(event.target.value)} required /></label>
          <label>Note<input aria-label="Muster note" value={musterNote} onChange={(event) => setMusterNote(event.target.value)} /></label>
          <button className="primary" type="submit">Save muster point</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.muster_points || []).map((row) => (
          <article key={row.id} className="contact-card">
            <h4>{row.name}</h4>
            <p className="muted">{row.note}</p>
          </article>
        ))}
      </div>
      <p className="muted">{board.gear_note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveGear(event)}>
          <label>Equipment<input aria-label="Emergency equipment" value={gear} onChange={(event) => setGear(event.target.value)} required /></label>
          <label>Location<input aria-label="Equipment location" value={location} onChange={(event) => setLocation(event.target.value)} required /></label>
          <button className="primary" type="submit">Save equipment location</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.emergency_gear || []).map((row) => (
          <article key={row.id} className="contact-card">
            <h4>{row.name}</h4>
            <p>{row.location}</p>
            <p className="muted">{row.statement}</p>
          </article>
        ))}
      </div>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void savePlan(event)}>
          <label>Plan number<input aria-label="Plan number" value={planNumber} onChange={(event) => setPlanNumber(event.target.value)} required /></label>
          <label>Title<input aria-label="Plan title" value={planTitle} onChange={(event) => setPlanTitle(event.target.value)} required /></label>
          <label>Engineering reference<input aria-label="Engineering reference" value={planRef} onChange={(event) => setPlanRef(event.target.value)} /></label>
          <button className="primary" type="submit">Save plan reference</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.emergency_plans || []).map((row) => (
          <article key={row.id} className="contact-card">
            <h4>{row.number}</h4>
            <p>{row.title}</p>
            <p className="muted">{row.engineering_reference}</p>
          </article>
        ))}
      </div>
      <p className="muted">{board.drill_note} {board.drill_finding_note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveDrill(event)}>
          <label>Drill number<input aria-label="Drill number" value={drillNumber} onChange={(event) => setDrillNumber(event.target.value)} required /></label>
          <label>Title<input aria-label="Drill title" value={drillTitle} onChange={(event) => setDrillTitle(event.target.value)} required /></label>
          <label>Planned on<input aria-label="Drill date" type="date" value={plannedOn} onChange={(event) => setPlannedOn(event.target.value)} required /></label>
          <label>Findings<textarea aria-label="Drill findings" value={findings} onChange={(event) => setFindings(event.target.value)} /></label>
          <button className="primary" type="submit">Save drill</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.drills || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header><LifeBuoy size={15} /><span className={statusChip(row.status)}>{row.status}</span></header>
            <h4>{row.number}</h4>
            <p>{row.title} · {row.planned_on}</p>
            {row.findings ? <p>{row.findings}</p> : null}
            <p className="muted">{row.statement} {row.finding_note}</p>
            {row.acknowledgments.map((item) => <p key={item.member_name}>{item.member_name}: {item.evidence}</p>)}
            {canPlan && row.status === "Planned" ? <button type="button" onClick={() => void hold(row)}>Mark held</button> : null}
            {row.status === "Held" ? (
              <>
                <label>
                  Person
                  <select aria-label={`Drill attendee ${row.number}`} value={memberId} onChange={(event) => setMemberId(event.target.value)}>
                    <option value="">Choose a member</option>
                    {board.members.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
                  </select>
                </label>
                <label>Evidence<input aria-label={`Drill evidence ${row.number}`} value={evidence} onChange={(event) => setEvidence(event.target.value)} /></label>
                <button type="button" onClick={() => void acknowledge(row)}>Acknowledge</button>
              </>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}

function Environmental({
  pid,
  board,
  canPlan,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  canPlan: boolean;
  onError: (message: string) => void;
  reload: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [criterionKind, setCriterionKind] = useState("");
  const [threshold, setThreshold] = useState("");
  const [number, setNumber] = useState("");
  const [kind, setKind] = useState("Spill");
  const [description, setDescription] = useState("");
  const [recordedOn, setRecordedOn] = useState("");
  const [criterionId, setCriterionId] = useState("");
  const [reading, setReading] = useState("");
  const [result, setResult] = useState("Not assessed");
  const [evidence, setEvidence] = useState("");
  const [actionId, setActionId] = useState("");
  const [packageId, setPackageId] = useState("");
  async function saveCriterion(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/environment-criteria`, "POST", { name, kind: criterionKind, threshold });
      setName("");
      setThreshold("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function saveRecord(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/hse/environment-records`, "POST", {
        number,
        kind,
        description,
        recorded_on: recordedOn,
        criterion_id: criterionId ? Number(criterionId) : null,
        reading,
        result,
        evidence,
        action_id: actionId ? Number(actionId) : null,
        package_id: packageId ? Number(packageId) : null,
      });
      setNumber("");
      setDescription("");
      setReading("");
      setEvidence("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <>
      <p className="note-card">{board.environment_note}</p>
      <p className="muted">{board.environment_action_note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void saveCriterion(event)}>
          <label>Criterion<input aria-label="Criterion name" value={name} onChange={(event) => setName(event.target.value)} required /></label>
          <label>
            Applies to
            <select aria-label="Criterion kind" value={criterionKind} onChange={(event) => setCriterionKind(event.target.value)}>
              <option value="">Any record</option>
              {(board.environment_kinds || []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>Threshold<textarea aria-label="Criterion threshold" value={threshold} onChange={(event) => setThreshold(event.target.value)} required /></label>
          <button className="primary" type="submit">Save criterion</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {(board.environment_criteria || []).map((row) => (
          <article key={row.id} className="contact-card">
            <h4>{row.name}</h4>
            <p className="muted">{row.kind || "Any record"}</p>
            <p>{row.threshold}</p>
          </article>
        ))}
      </div>
      <form className="contact-form" onSubmit={(event) => void saveRecord(event)}>
        <label>Number<input aria-label="Environmental number" value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
        <label>
          Kind
          <select aria-label="Environmental kind" value={kind} onChange={(event) => setKind(event.target.value)}>
            {(board.environment_kinds || []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>Description<textarea aria-label="Environmental description" value={description} onChange={(event) => setDescription(event.target.value)} required /></label>
        <label>Recorded on<input aria-label="Environmental date" type="date" value={recordedOn} onChange={(event) => setRecordedOn(event.target.value)} required /></label>
        <label>
          Work package
          <select aria-label="Environmental package" value={packageId} onChange={(event) => setPackageId(event.target.value)}>
            <option value="">None</option>
            {board.packages.map((row) => <option key={row.id} value={row.id}>{row.code}</option>)}
          </select>
        </label>
        <label>
          Criterion
          <select aria-label="Environmental criterion" value={criterionId} onChange={(event) => setCriterionId(event.target.value)}>
            <option value="">Not compared</option>
            {(board.environment_criteria || []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label>Reading<input aria-label="Environmental reading" value={reading} onChange={(event) => setReading(event.target.value)} /></label>
        <label>
          Result
          <select aria-label="Environmental result" value={result} onChange={(event) => setResult(event.target.value)}>
            {(board.environment_results || ["Not assessed", "Within criteria", "Outside criteria"]).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>Evidence<textarea aria-label="Environmental evidence" value={evidence} onChange={(event) => setEvidence(event.target.value)} /></label>
        <label>
          Existing action
          <select aria-label="Environmental action" value={actionId} onChange={(event) => setActionId(event.target.value)}>
            <option value="">None</option>
            {(board.actions || []).map((row) => <option key={row.id} value={row.id}>{row.number}</option>)}
          </select>
        </label>
        <button className="primary" type="submit">Save record</button>
      </form>
      <div className="contact-grid">
        {(board.environment_records || []).map((row) => (
          <article key={row.id} className="contact-card">
            <header><Leaf size={15} /><span className={statusChip(row.result)}>{row.result}</span></header>
            <h4>{row.number}</h4>
            <p>{row.kind} · {row.recorded_on}</p>
            <p>{row.description}</p>
            {row.reading ? <p>Reading {row.reading}{row.criterion_name ? ` against ${row.criterion_name}` : ""}</p> : null}
            {row.threshold ? <p className="muted">{row.threshold}</p> : null}
            {row.action_number ? <p className="muted">Action {row.action_number} is {row.action_status}. {row.action_note}</p> : <p className="muted">{row.action_note}</p>}
            {row.package_status ? <p className="muted">Package {row.package_status}</p> : null}
            <p className="muted">{row.statement}</p>
          </article>
        ))}
      </div>
    </>
  );
}
