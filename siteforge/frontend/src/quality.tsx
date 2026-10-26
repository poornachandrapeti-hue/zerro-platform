import { FormEvent, useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Award,
  BadgeCheck,
  Ban,
  ClipboardCheck,
  ClipboardList,
  Cog,
  Eye,
  FileSearch,
  FolderOpen,
  Gauge,
  ListTodo,
  HardHat,
  Hourglass,
  LayoutDashboard,
  ListChecks,
  Lock,
  OctagonAlert,
  PackageCheck,
  Plus,
  ScanEye,
  ScrollText,
  Send,
  ShieldAlert,
  Timer,
  Waypoints,
  Zap,
} from "lucide-react";
import { api } from "./api";
import { RouteLockNotice, routeLocked } from "./approval_levels";
import type { Page, Project, Session } from "./types";

const TABS = ["Dashboard", "Offers", "Requests", "Material", "NCRs", "Holds", "Plans & ITPs", "Templates", "Qualifications", "Calibration", "Dossiers", "Punch"] as const;
const TAB_ICON: Record<(typeof TABS)[number], LucideIcon> = {
  Dashboard: LayoutDashboard,
  Offers: ClipboardCheck,
  Requests: ClipboardList,
  Material: PackageCheck,
  NCRs: ShieldAlert,
  Holds: OctagonAlert,
  "Plans & ITPs": ScrollText,
  Templates: ListChecks,
  Qualifications: Award,
  Calibration: Timer,
  Dossiers: FolderOpen,
  Punch: ListTodo,
};
const TAB_TONE: Record<(typeof TABS)[number], string> = {
  Dashboard: "tone-qdash",
  Offers: "tone-qoffer",
  Requests: "tone-qreq",
  Material: "tone-qmat",
  NCRs: "tone-qncr",
  Holds: "tone-qhold",
  "Plans & ITPs": "tone-qplan",
  Templates: "tone-qform",
  Qualifications: "tone-qqual",
  Calibration: "tone-qcal",
  Dossiers: "tone-qdossier",
  Punch: "tone-qpunch",
};
const DISCIPLINE_ICON: Record<string, LucideIcon> = {
  Civil: HardHat,
  Mechanical: Cog,
  Electrical: Zap,
  Instrumentation: Gauge,
  Piping: Waypoints,
};
const POINT_ICON: Record<string, LucideIcon> = {
  Review: FileSearch,
  Witness: Eye,
  Hold: OctagonAlert,
  Surveillance: ScanEye,
};

function statusChip(status: string) {
  return `rel-chip hand-${status.replaceAll(" ", "-").toLowerCase()}`;
}

function PointMark({ type }: { type: string }) {
  const Icon = POINT_ICON[type] || FileSearch;
  return (
    <span className={`q-point q-${type.toLowerCase()}`}>
      <Icon size={13} strokeWidth={2.4} />
      {type}
    </span>
  );
}

function Err({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}

type RouteNeed = { recordType: string; label: string; stage: string; scoped: boolean };
type SavedRoute = {
  discipline_id: number | null;
  stages: { reviewers: { id: number; name: string }[] }[];
};
const OFFER_ROUTES: RouteNeed[] = [{ recordType: "quality.inspection", label: "Inspection offer reviewer", stage: "Inspection review", scoped: true }];
const REQUEST_ROUTES: RouteNeed[] = [{ recordType: "quality.construction", label: "Construction inspection reviewer", stage: "Construction inspection", scoped: true }];
const MATERIAL_ROUTES: RouteNeed[] = [{ recordType: "quality.material", label: "Material inspection reviewer", stage: "Material inspection", scoped: true }];
const NCR_ROUTES: RouteNeed[] = [
  { recordType: "quality.ncr", label: "NCR reviewer", stage: "NCR review", scoped: true },
  { recordType: "quality.ncr.close", label: "NCR closure reviewer", stage: "NCR closure", scoped: true },
  { recordType: "quality.concession", label: "Concession reviewer", stage: "Concession review", scoped: true },
];
const HOLD_ROUTES: RouteNeed[] = [{ recordType: "quality.hold", label: "Quality hold reviewer", stage: "Hold release", scoped: true }];
const PLAN_ROUTES: RouteNeed[] = [{ recordType: "quality.document", label: "Plan and ITP reviewer", stage: "Quality document review", scoped: true }];
const TEMPLATE_ROUTES: RouteNeed[] = [{ recordType: "quality.template", label: "Template reviewer", stage: "Template review", scoped: true }];
const QUAL_ROUTES: RouteNeed[] = [{ recordType: "quality.qualification", label: "Qualification reviewer", stage: "Qualification review", scoped: false }];
const CAL_ROUTES: RouteNeed[] = [{ recordType: "quality.calibration", label: "Calibration reviewer", stage: "Calibration review", scoped: false }];
const DOSSIER_ROUTES: RouteNeed[] = [{ recordType: "quality.dossier", label: "Quality dossier reviewer", stage: "Dossier review", scoped: false }];
const PUNCH_ROUTES: RouteNeed[] = [{ recordType: "quality.punch.close", label: "Punch closure reviewer", stage: "Punch closure", scoped: false }];
const ALL_QUALITY_ROUTES: RouteNeed[] = [
  ...PLAN_ROUTES,
  ...TEMPLATE_ROUTES,
  ...OFFER_ROUTES,
  ...MATERIAL_ROUTES,
  ...REQUEST_ROUTES,
  ...NCR_ROUTES,
  ...HOLD_ROUTES,
  ...QUAL_ROUTES,
  ...CAL_ROUTES,
  ...DOSSIER_ROUTES,
  ...PUNCH_ROUTES,
];

function routeText(rows: SavedRoute[], disciplines: { id: number; name: string }[]) {
  if (!rows.length) return "Not set";
  return rows
    .map((row) => {
      const people = row.stages.flatMap((stage) => stage.reviewers.map((person) => person.name)).join(", ") || "Not set";
      const scope = disciplines.find((item) => item.id === row.discipline_id)?.name || "All disciplines";
      return `${people} · ${scope}`;
    })
    .join("; ");
}

function QualityRoutes({ pid, admin, routes }: { pid: number; admin: boolean; routes: RouteNeed[] }) {
  const [members, setMembers] = useState<{ id: number; name: string }[]>([]);
  const [disciplines, setDisciplines] = useState<{ id: number; name: string }[]>([]);
  const [saved, setSaved] = useState<Record<string, SavedRoute[]>>({});
  const [picked, setPicked] = useState<Record<string, number>>({});
  const [scope, setScope] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!admin) return;
    void api<{ user_id: number; name: string; active: boolean }[]>(`/projects/${pid}/memberships`)
      .then((rows) => {
        const people = new Map<number, { id: number; name: string }>();
        for (const row of rows) {
          if (row.active) people.set(row.user_id, { id: row.user_id, name: row.name });
        }
        setMembers([...people.values()]);
      })
      .catch(() => setMembers([]));
    void api<{ disciplines: { id: number; name: string }[] }>(`/projects/${pid}/quality/plans`)
      .then((body) => setDisciplines(body.disciplines || []))
      .catch(() => setDisciplines([]));
  }, [pid, admin]);
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
        discipline_id: route.scoped && scope[route.recordType] ? Number(scope[route.recordType]) : null,
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
      <h3 className="section-mark wide"><Lock size={18} strokeWidth={2.4} /> Review route</h3>
      <p className="muted">The record owner is not the reviewer. Save an active project member other than the person who will submit. Leave discipline on all disciplines unless this route is only for one discipline.</p>
      <Err text={error} />
      {notice ? <p className="muted">{notice}</p> : null}
      {routes.map((route) => {
        const disciplineId = route.scoped && scope[route.recordType] ? Number(scope[route.recordType]) : null;
        const locked = routeLocked(saved[route.recordType], disciplineId);
        return (
        <div key={route.recordType} className="option-grid">
          <p><strong>{route.label}</strong> · {routeText(saved[route.recordType] || [], disciplines)}</p>
          {locked ? <RouteLockNotice target={{ projectId: pid, recordType: route.recordType, disciplineId }} /> : null}
          {route.scoped ? (
            <label>
              Discipline
              <select aria-label={`${route.label} discipline`} value={scope[route.recordType] || ""} onChange={(event) => setScope({ ...scope, [route.recordType]: event.target.value })}>
                <option value="">All disciplines</option>
                {disciplines.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>
          ) : null}
          <label>
            Reviewer
            <select aria-label={route.label} disabled={locked} value={picked[route.recordType] || ""} onChange={(event) => setPicked({ ...picked, [route.recordType]: Number(event.target.value) })}>
              <option value="">Choose a project member</option>
              {members.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
            </select>
          </label>
          <button type="button" className="primary" disabled={locked || !picked[route.recordType]} onClick={() => void save(route)}>Save</button>
        </div>
        );
      })}
    </div>
  );
}

type Activity = {
  id: number;
  code: string;
  name: string;
  method: string;
  unit: string;
  scope_quantity: string | null;
  verified_quantity: string | null;
  verified_percent: string | null;
  accepted_quantity: string | null;
  accepted_note: string;
};
type Package = {
  id: number;
  code: string;
  status: string;
  version: number;
  activities: Activity[];
};
type Offer = {
  id: number;
  number: string;
  package_code: string;
  package_status: string;
  status: string;
  statement: string;
  version: number;
  payload: { activities?: { code: string; verified_quantity: string | null; verified_percent: string | null; unit: string }[] };
  lines: { accepted_quantity: string | null; accepted_percent: string | null }[];
};
type Board = { note: string; offers: Offer[]; packages: Package[] };

export function QualityHome({ session, initialProjectId = null }: { session: Session; initialProjectId?: number | null }) {
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
        <QualityBoard pid={pid} session={session} />
      </>
    );
  }
  return (
    <section className="panel">
      <h2>Quality / QAQC</h2>
      <p className="muted">Open a project to keep its quality plans, inspection templates, inspection offers, and material inspections.</p>
      <Err text={error} />
      {projects.map((project) => (
        <button key={project.id} onClick={() => setPid(project.id || null)}>
          <ClipboardCheck size={16} strokeWidth={2.4} />
          {project.code} · {project.name}
        </button>
      ))}
    </section>
  );
}

function QualityBoard({ pid, session }: { pid: number; session: Session }) {
  const [tab, setTab] = useState("Dashboard");
  const admin = session.user.organization_admin;
  const canPlan =
    session.user.organization_admin ||
    session.memberships.some(
      (item) => item.project_id === pid && item.permissions?.includes("quality.plan"),
    );
  const canRequest =
    canPlan ||
    session.memberships.some(
      (item) => item.project_id === pid && item.permissions?.includes("quality.edit"),
    );
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState("");
  const [number, setNumber] = useState("");
  const [packageId, setPackageId] = useState("");
  const [activityId, setActivityId] = useState("");
  async function load() {
    setBoard(await api<Board>(`/projects/${pid}/quality`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  const selected = board?.packages.find((row) => String(row.id) === packageId);
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/projects/${pid}/quality/offers`, "POST", {
        number,
        package_id: Number(packageId),
        activity_id: activityId ? Number(activityId) : null,
      });
      setNumber("");
      setActivityId("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  async function submit(row: Offer) {
    setError("");
    const path = row.status === "Returned for Correction" ? "resubmit" : "submit";
    try {
      await api(`/projects/${pid}/quality/offers/${row.id}/${path}`, "POST", { version: row.version });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h2>Quality / QAQC</h2>
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
      {tab === "Dashboard" ? <DashboardPanel pid={pid} admin={admin} /> : null}
      {tab === "Qualifications" ? <QualificationsPanel pid={pid} canPlan={canPlan} admin={admin} /> : null}
      {tab === "Calibration" ? <CalibrationsPanel pid={pid} canPlan={canPlan} admin={admin} /> : null}
      {tab === "Dossiers" ? <DossiersPanel pid={pid} canPlan={canPlan} admin={admin} /> : null}
      {tab === "Punch" ? <PunchPanel pid={pid} canRequest={canRequest} companyId={session.user.company_id || 0} admin={admin} /> : null}
      {tab === "Plans & ITPs" ? <PlansPanel pid={pid} canPlan={canPlan} admin={admin} /> : null}
      {tab === "Templates" ? <TemplatesPanel pid={pid} canPlan={canPlan} admin={admin} /> : null}
      {tab === "Requests" ? <RequestsPanel pid={pid} canRequest={canRequest} admin={admin} /> : null}
      {tab === "Material" ? <MaterialPanel pid={pid} canPlan={canPlan} admin={admin} /> : null}
      {tab === "NCRs" ? <NcrPanel pid={pid} canPlan={canPlan} canRequest={canRequest} admin={admin} /> : null}
      {tab === "Holds" ? <HoldsPanel pid={pid} canPlan={canPlan} canRequest={canRequest} admin={admin} /> : null}
      {tab === "Offers" ? (
      <>
      <QualityRoutes pid={pid} admin={admin} routes={OFFER_ROUTES} />
      <p>{board?.note}</p>
      <form className="contact-form" onSubmit={(event) => void create(event)}>
        <h3 className="section-mark wide">
          <ClipboardCheck size={18} strokeWidth={2.4} /> Offer for inspection
        </h3>
        <label>
          Number
          <input value={number} onChange={(event) => setNumber(event.target.value)} required />
        </label>
        <label>
          Work package
          <select value={packageId} onChange={(event) => { setPackageId(event.target.value); setActivityId(""); }} required>
            <option value="">Choose a released package</option>
            {board?.packages.map((row) => (
              <option key={row.id} value={row.id}>
                {row.code} · {row.status}
              </option>
            ))}
          </select>
        </label>
        <label>
          Activity
          <select value={activityId} onChange={(event) => setActivityId(event.target.value)}>
            <option value="">Whole package</option>
            {selected?.activities.map((row) => (
              <option key={row.id} value={row.id}>
                {row.code} · {row.name}
              </option>
            ))}
          </select>
        </label>
        <button className="primary" type="submit">
          <Plus size={15} /> Save draft
        </button>
      </form>
      <h3 className="section-mark">
        <BadgeCheck size={18} strokeWidth={2.4} /> Verified and accepted
      </h3>
      <div className="contact-grid">
      {board?.packages.map((row) => (
        <article key={row.id} className="contact-card q-offer">
          <header>
            <strong><HardHat size={15} /> {row.code}</strong>
            <span className="rel-chip q-kind">{row.status}</span>
          </header>
          <ul>
            {row.activities.map((activity) => (
              <li key={activity.id}>
                {activity.code}: verified {activity.verified_quantity ?? activity.verified_percent ?? "—"}
                {activity.unit ? ` ${activity.unit}` : ""}
                {activity.accepted_quantity ? `, accepted ${activity.accepted_quantity} ${activity.unit}` : ""}
              </li>
            ))}
          </ul>
        </article>
      ))}
      </div>
      <h3 className="section-mark">
        <Send size={18} strokeWidth={2.4} /> Inspection offers
      </h3>
      <div className="contact-grid">
      {board?.offers.map((row) => (
        <article key={row.id} className="contact-card q-offer">
          <header>
            <strong>{row.number}</strong>
            <span className={statusChip(row.status)}>{row.status}</span>
          </header>
          <p>{row.package_code}</p>
          <p className="muted">Package stays {row.package_status}. Rejection does not move it out of construction.</p>
          <ul>
            {(row.payload.activities || []).map((activity) => (
              <li key={activity.code}>
                {activity.code}: offered {activity.verified_quantity ?? activity.verified_percent}
                {activity.unit ? ` ${activity.unit}` : ""}
              </li>
            ))}
          </ul>
          {row.status === "Draft" || row.status === "Returned for Correction" ? (
            <button className="primary" type="button" onClick={() => void submit(row)}>
              <Send size={15} /> {row.status === "Draft" ? "Submit" : "Resubmit"}
            </button>
          ) : null}
        </article>
      ))}
      </div>
      </>
      ) : null}
    </section>
  );
}

type PlanCompany = { id: number; name: string };
type PlanDiscipline = { id: number; name: string };
type Checkpoint = {
  sequence: number;
  name: string;
  criteria_reference: string;
  responsible_parties: string;
  point_type: string;
  notice_hours: number;
  required_evidence: string;
  required_signatories: string;
  partial_allowed: boolean;
  next_release_conditions: string;
};
type QualityDocumentRow = {
  id: number;
  kind: string;
  number: string;
  title: string;
  revision_label: string;
  status: string;
  version: number;
  witness_rule: string;
  engineering_reference: string;
  applicable_activities: string;
  checkpoints: Checkpoint[];
};
type QualityFormRow = {
  id: number;
  code: string;
  title: string;
  revision_label: string;
  status: string;
  version: number;
  criteria_label: string;
  criteria_status: string;
  units: string;
  items: string[];
};
type PlanRegister = {
  statement: string;
  witness_rule: string;
  documents: QualityDocumentRow[];
  forms: QualityFormRow[];
  companies: PlanCompany[];
  disciplines: PlanDiscipline[];
  examples: { discipline: string; inspections: string[] }[];
  counts: { draft_documents: number; approved_documents: number; draft_forms: number; approved_forms: number };
};

function PlansPanel({ pid, canPlan, admin }: { pid: number; canPlan: boolean; admin: boolean }) {
  const [register, setRegister] = useState<PlanRegister | null>(null);
  const [error, setError] = useState("");
  const [kind, setKind] = useState("ITP");
  const [number, setNumber] = useState("");
  const [title, setTitle] = useState("");
  const [revision, setRevision] = useState("A");
  const [companyId, setCompanyId] = useState("");
  const [disciplineId, setDisciplineId] = useState("");
  const [reference, setReference] = useState("");
  const [activities, setActivities] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [points, setPoints] = useState<Checkpoint[]>([]);
  async function load() {
    const body = await api<PlanRegister>(`/projects/${pid}/quality/plans`);
    setRegister(body);
    if (!companyId && body.companies[0]) setCompanyId(String(body.companies[0].id));
    if (!disciplineId && body.disciplines[0]) setDisciplineId(String(body.disciplines[0].id));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  const current = register?.documents.find((row) => row.id === selected);
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const saved = await api<QualityDocumentRow>(`/projects/${pid}/quality/documents`, "POST", {
        kind,
        number,
        title,
        revision_label: revision,
        discipline_id: disciplineId ? Number(disciplineId) : null,
        company_id: Number(companyId),
        engineering_reference: reference,
        applicable_activities: activities,
        template_ids: [],
      });
      setSelected(saved.id);
      setPoints([]);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  async function savePoints() {
    if (!current) return;
    setError("");
    try {
      await api(`/projects/${pid}/quality/documents/${current.id}/checkpoints`, "PUT", {
        version: current.version,
        checkpoints: points,
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  async function submit(row: QualityDocumentRow) {
    setError("");
    const path = row.status === "Returned for Correction" ? "resubmit" : "submit";
    try {
      await api(`/projects/${pid}/quality/documents/${row.id}/${path}`, "POST", { version: row.version });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      <p>{register?.statement}</p>
      <div className="dash-grid">
        <article className="contact-card q-plan">
          <header><ScrollText size={16} /> Approved</header>
          <strong>{register?.counts.approved_documents ?? 0}</strong>
        </article>
        <article className="contact-card q-offer">
          <header><FileSearch size={16} /> Draft</header>
          <strong>{register?.counts.draft_documents ?? 0}</strong>
        </article>
      </div>
      <p className="muted">Only an approved revision can be used on an inspection template.</p>
      <QualityRoutes pid={pid} admin={admin} routes={PLAN_ROUTES} />
      <Err text={error} />
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide">
            <ScrollText size={18} strokeWidth={2.4} /> New quality document
          </h3>
          <label>
            Kind
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {["Project Quality Plan", "ITP", "Inspection Procedure", "Test Procedure", "Acceptance Criteria", "Checklist", "Report Template"].map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Number
            <input value={number} onChange={(event) => setNumber(event.target.value)} required />
          </label>
          <label>
            Title
            <input value={title} onChange={(event) => setTitle(event.target.value)} required />
          </label>
          <label>
            Revision
            <input value={revision} onChange={(event) => setRevision(event.target.value)} required />
          </label>
          <label>
            Company
            <select value={companyId} onChange={(event) => setCompanyId(event.target.value)} required>
              <option value="">Choose a company</option>
              {register?.companies.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Discipline
            <select value={disciplineId} onChange={(event) => setDisciplineId(event.target.value)}>
              <option value="">Project-wide</option>
              {register?.disciplines.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Engineering reference
            <input value={reference} onChange={(event) => setReference(event.target.value)} />
          </label>
          <label>
            Applicable activities
            <input value={activities} onChange={(event) => setActivities(event.target.value)} />
          </label>
          <button className="primary" type="submit">
            <Plus size={15} /> Save draft
          </button>
        </form>
      ) : (
        <p className="muted">QA/QC maintains these documents. Approval still needs the saved reviewer.</p>
      )}
      <div className="contact-grid">
      {register?.documents.map((row) => (
        <article key={row.id} className="contact-card q-plan">
          <header>
            <strong>{row.number}</strong>
            <span className={statusChip(row.status)}>{row.status}</span>
          </header>
          <p><span className="rel-chip q-kind">{row.kind}</span> rev {row.revision_label}</p>
          <p>{row.title}</p>
          {row.witness_rule ? <p className="muted"><Eye size={14} /> {row.witness_rule}</p> : null}
          <ul>
            {row.checkpoints.map((point) => (
              <li key={`${row.id}-${point.sequence}`}>
                {point.sequence}. {point.name} <PointMark type={point.point_type} />
                {point.point_type === "Hold" ? ` · release: ${point.next_release_conditions}` : ""}
              </li>
            ))}
          </ul>
          {canPlan && (row.status === "Draft" || row.status === "Returned for Correction") ? (
            <button className="primary" type="button" onClick={() => void submit(row)}>
              <Send size={15} /> {row.status === "Draft" ? "Submit" : "Resubmit"}
            </button>
          ) : null}
          {canPlan && row.kind === "ITP" && (row.status === "Draft" || row.status === "Returned for Correction") ? (
            <button
              type="button"
              onClick={() => {
                setSelected(row.id);
                setPoints(row.checkpoints.length ? row.checkpoints : [{
                  sequence: 1,
                  name: "",
                  criteria_reference: "",
                  responsible_parties: "",
                  point_type: "Hold",
                  notice_hours: 24,
                  required_evidence: "",
                  required_signatories: "",
                  partial_allowed: false,
                  next_release_conditions: "",
                }]);
              }}
            >
              <ListChecks size={15} /> Edit checkpoints
            </button>
          ) : null}
        </article>
      ))}
      </div>
      {current && canPlan ? (
        <form
          className="contact-form"
          onSubmit={(event) => {
            event.preventDefault();
            void savePoints();
          }}
        >
          <h3 className="section-mark wide">
            <ListChecks size={18} strokeWidth={2.4} /> Checkpoints for {current.number}
          </h3>
          <p className="muted">{register?.witness_rule}</p>
          {points.map((point, index) => (
            <div key={index}>
              <label>
                Sequence
                <input
                  type="number"
                  value={point.sequence}
                  onChange={(event) => {
                    const next = [...points];
                    next[index] = { ...point, sequence: Number(event.target.value) };
                    setPoints(next);
                  }}
                />
              </label>
              <label>
                Inspection
                <input
                  value={point.name}
                  onChange={(event) => {
                    const next = [...points];
                    next[index] = { ...point, name: event.target.value };
                    setPoints(next);
                  }}
                />
              </label>
              <label>
                Point type
                <select
                  value={point.point_type}
                  onChange={(event) => {
                    const next = [...points];
                    next[index] = { ...point, point_type: event.target.value };
                    setPoints(next);
                  }}
                >
                  {["Review", "Witness", "Hold", "Surveillance"].map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
              </label>
              <label>
                Acceptance criteria reference
                <input
                  value={point.criteria_reference}
                  onChange={(event) => {
                    const next = [...points];
                    next[index] = { ...point, criteria_reference: event.target.value };
                    setPoints(next);
                  }}
                />
              </label>
              <label>
                Responsible parties
                <input
                  value={point.responsible_parties}
                  onChange={(event) => {
                    const next = [...points];
                    next[index] = { ...point, responsible_parties: event.target.value };
                    setPoints(next);
                  }}
                />
              </label>
              <label>
                Required evidence
                <input
                  value={point.required_evidence}
                  onChange={(event) => {
                    const next = [...points];
                    next[index] = { ...point, required_evidence: event.target.value };
                    setPoints(next);
                  }}
                />
              </label>
              <label>
                Required signatories
                <input
                  value={point.required_signatories}
                  onChange={(event) => {
                    const next = [...points];
                    next[index] = { ...point, required_signatories: event.target.value };
                    setPoints(next);
                  }}
                />
              </label>
              <label>
                Release condition
                <input
                  value={point.next_release_conditions}
                  onChange={(event) => {
                    const next = [...points];
                    next[index] = { ...point, next_release_conditions: event.target.value };
                    setPoints(next);
                  }}
                />
              </label>
            </div>
          ))}
          <button className="wide" type="button" onClick={() => setPoints([...points, {
            sequence: points.length + 1,
            name: "",
            criteria_reference: "",
            responsible_parties: "",
            point_type: "Review",
            notice_hours: 0,
            required_evidence: "",
            required_signatories: "",
            partial_allowed: false,
            next_release_conditions: "",
          }])}>
            <Plus size={15} /> Add checkpoint
          </button>
          <button className="primary" type="submit">
            <BadgeCheck size={15} /> Save checkpoints
          </button>
        </form>
      ) : null}
    </>
  );
}

function TemplatesPanel({ pid, canPlan, admin }: { pid: number; canPlan: boolean; admin: boolean }) {
  const [register, setRegister] = useState<PlanRegister | null>(null);
  const [error, setError] = useState("");
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [revision, setRevision] = useState("A");
  const [disciplineId, setDisciplineId] = useState("");
  const [criteriaId, setCriteriaId] = useState("");
  const [units, setUnits] = useState("");
  const [items, setItems] = useState("");
  async function load() {
    const body = await api<PlanRegister>(`/projects/${pid}/quality/plans`);
    setRegister(body);
    if (!disciplineId && body.disciplines[0]) setDisciplineId(String(body.disciplines[0].id));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/projects/${pid}/quality/forms`, "POST", {
        discipline_id: Number(disciplineId),
        code,
        title,
        revision_label: revision,
        criteria_document_id: criteriaId ? Number(criteriaId) : null,
        units,
        prerequisites: "",
        required_attachments: "",
        items: items.split("\n").map((row) => row.trim()).filter(Boolean),
      });
      setCode("");
      setItems("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  async function submit(row: QualityFormRow) {
    setError("");
    const path = row.status === "Returned for Correction" ? "resubmit" : "submit";
    try {
      await api(`/projects/${pid}/quality/forms/${row.id}/${path}`, "POST", { version: row.version });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  const approved = register?.documents.filter((row) => row.status === "Approved") || [];
  return (
    <>
      <p className="muted">
        Example names are not approved templates. Acceptance limits come from an approved project document.
        A submitted template keeps its own copy. Approved templates {register?.counts.approved_forms ?? 0}.
      </p>
      <QualityRoutes pid={pid} admin={admin} routes={TEMPLATE_ROUTES} />
      <Err text={error} />
      <div className="contact-grid">
      {register?.examples.map((group) => {
        const Icon = DISCIPLINE_ICON[group.discipline] || ListChecks;
        return (
          <article key={group.discipline} className="contact-card q-form">
            <header>
              <strong><Icon size={16} /> {group.discipline}</strong>
            </header>
            <p className="muted">{group.inspections.join(" · ")}</p>
          </article>
        );
      })}
      </div>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide">
            <ListChecks size={18} strokeWidth={2.4} /> New inspection template
          </h3>
          <label>
            Code
            <input value={code} onChange={(event) => setCode(event.target.value)} required />
          </label>
          <label>
            Title
            <input value={title} onChange={(event) => setTitle(event.target.value)} required />
          </label>
          <label>
            Revision
            <input value={revision} onChange={(event) => setRevision(event.target.value)} required />
          </label>
          <label>
            Discipline
            <select value={disciplineId} onChange={(event) => setDisciplineId(event.target.value)} required>
              <option value="">Choose a discipline</option>
              {register?.disciplines.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Approved criteria
            <select value={criteriaId} onChange={(event) => setCriteriaId(event.target.value)}>
              <option value="">Choose an approved document</option>
              {approved.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.number} rev {row.revision_label} · {row.kind}
                </option>
              ))}
            </select>
          </label>
          <label>
            Units
            <input value={units} onChange={(event) => setUnits(event.target.value)} />
          </label>
          <label className="wide">
            Checklist items, one per line
            <textarea value={items} onChange={(event) => setItems(event.target.value)} />
          </label>
          <button className="primary" type="submit">
            <Plus size={15} /> Save draft
          </button>
        </form>
      ) : null}
      <div className="contact-grid">
      {register?.forms.map((row) => (
        <article key={row.id} className="contact-card q-form">
          <header>
            <strong><ListChecks size={15} /> {row.code}</strong>
            <span className={statusChip(row.status)}>{row.status}</span>
          </header>
          <p>rev {row.revision_label}</p>
          <p>{row.title}</p>
          <p className="muted">
            <ScrollText size={14} /> Criteria {row.criteria_label || "not chosen"} {row.criteria_status ? `· ${row.criteria_status}` : ""}
          </p>
          <ul>
            {row.items.map((item) => (
              <li key={item}><BadgeCheck size={13} /> {item}</li>
            ))}
          </ul>
          {canPlan && (row.status === "Draft" || row.status === "Returned for Correction") ? (
            <button className="primary" type="button" onClick={() => void submit(row)}>
              <Send size={15} /> {row.status === "Draft" ? "Submit" : "Resubmit"}
            </button>
          ) : null}
        </article>
      ))}
      </div>
    </>
  );
}

type BalanceLine = {
  id: number;
  item_code: string;
  unit: string;
  received: string;
  pending: string;
  accepted: string;
  rejected: string;
  quarantined: string;
};
type MaterialReceipt = { id: number; number: string; status: string; lines: BalanceLine[] };
type MaterialMove = {
  goods_receipt_line_id: number;
  item_code: string;
  unit: string;
  from_state: string;
  to_state: string;
  quantity: string;
  batch_number: string;
  heat_number: string;
  serial_number: string;
};
type MaterialInspectionRow = {
  id: number;
  number: string;
  receipt_number: string;
  status: string;
  statement: string;
  inspector_name: string;
  certificate_reference: string;
  findings: string;
  version: number;
  lines: MaterialMove[];
};
type MaterialRegister = {
  note: string;
  receipts: MaterialReceipt[];
  inspections: MaterialInspectionRow[];
  members: { id: number; name: string }[];
};
type DraftMove = {
  goods_receipt_line_id: number;
  item_code: string;
  unit: string;
  pending: string;
  quarantined: string;
  from_state: string;
  to_state: string;
  quantity: string;
  batch_number: string;
  heat_number: string;
  serial_number: string;
};

function Split({ line }: { line: BalanceLine }) {
  return (
    <div className="q-split">
      <span className="q-bucket pending"><Hourglass size={13} /> Pending {line.pending}</span>
      <span className="q-bucket accepted"><BadgeCheck size={13} /> Accepted {line.accepted}</span>
      <span className="q-bucket rejected"><Ban size={13} /> Rejected {line.rejected}</span>
      <span className="q-bucket quarantined"><ShieldAlert size={13} /> Quarantined {line.quarantined}</span>
    </div>
  );
}

function MaterialPanel({ pid, canPlan, admin }: { pid: number; canPlan: boolean; admin: boolean }) {
  const [register, setRegister] = useState<MaterialRegister | null>(null);
  const [error, setError] = useState("");
  const [number, setNumber] = useState("");
  const [receiptId, setReceiptId] = useState("");
  const [inspectorId, setInspectorId] = useState("");
  const [requestedOn, setRequestedOn] = useState("");
  const [certificate, setCertificate] = useState("");
  const [findings, setFindings] = useState("");
  const [moves, setMoves] = useState<DraftMove[]>([]);
  async function load() {
    const next = await api<MaterialRegister>(`/projects/${pid}/quality/materials`);
    setRegister(next);
    return next;
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  function chooseReceipt(value: string) {
    setReceiptId(value);
    const receipt = register?.receipts.find((row) => String(row.id) === value);
    setMoves(
      (receipt?.lines || []).map((line) => ({
        goods_receipt_line_id: line.id,
        item_code: line.item_code,
        unit: line.unit,
        pending: line.pending,
        quarantined: line.quarantined,
        from_state: "Pending",
        to_state: "Accepted",
        quantity: "",
        batch_number: "",
        heat_number: "",
        serial_number: "",
      })),
    );
  }
  function editMove(index: number, patch: Partial<DraftMove>) {
    setMoves((rows) => rows.map((row, position) => (position === index ? { ...row, ...patch } : row)));
  }
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    const lines = moves
      .filter((row) => row.quantity.trim())
      .map((row) => ({
        goods_receipt_line_id: row.goods_receipt_line_id,
        from_state: row.from_state,
        to_state: row.to_state,
        quantity: row.quantity,
        batch_number: row.batch_number,
        heat_number: row.heat_number,
        serial_number: row.serial_number,
      }));
    try {
      await api(`/projects/${pid}/quality/materials`, "POST", {
        number,
        goods_receipt_id: Number(receiptId),
        inspector_id: Number(inspectorId),
        requested_on: requestedOn,
        certificate_reference: certificate,
        findings,
        lines,
      });
      setNumber("");
      setCertificate("");
      setFindings("");
      setMoves([]);
      setReceiptId("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  async function submit(row: MaterialInspectionRow) {
    setError("");
    const path = row.status === "Returned for Correction" ? "resubmit" : "submit";
    try {
      await api(`/projects/${pid}/quality/materials/${row.id}/${path}`, "POST", { version: row.version });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      <QualityRoutes pid={pid} admin={admin} routes={MATERIAL_ROUTES} />
      <p>{register?.note}</p>
      <Err text={error} />
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide">
            <PackageCheck size={18} strokeWidth={2.4} /> Inspect received material
          </h3>
          <label>
            Number
            <input value={number} onChange={(event) => setNumber(event.target.value)} required />
          </label>
          <label>
            Goods receipt
            <select value={receiptId} onChange={(event) => chooseReceipt(event.target.value)} required>
              <option value="">Choose a posted receipt</option>
              {register?.receipts.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.number}
                </option>
              ))}
            </select>
          </label>
          <label>
            Inspector
            <select value={inspectorId} onChange={(event) => setInspectorId(event.target.value)} required>
              <option value="">Choose a project member</option>
              {register?.members.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Requested on
            <input type="date" value={requestedOn} onChange={(event) => setRequestedOn(event.target.value)} required />
          </label>
          <label>
            Certificate
            <input value={certificate} onChange={(event) => setCertificate(event.target.value)} />
          </label>
          <label className="wide">
            Findings
            <textarea value={findings} onChange={(event) => setFindings(event.target.value)} />
          </label>
          {moves.map((row, index) => (
            <div className="wide" key={row.goods_receipt_line_id}>
              <p>
                <PackageCheck size={14} /> {row.item_code} · pending {row.pending} {row.unit} · quarantined {row.quarantined}
              </p>
              <div className="contact-grid">
                <label>
                  From
                  <select value={row.from_state} onChange={(event) => editMove(index, { from_state: event.target.value, to_state: event.target.value === "Quarantined" ? "Accepted" : row.to_state })}>
                    <option>Pending</option>
                    <option>Quarantined</option>
                  </select>
                </label>
                <label>
                  To
                  <select value={row.to_state} onChange={(event) => editMove(index, { to_state: event.target.value })}>
                    <option>Accepted</option>
                    <option>Rejected</option>
                    {row.from_state === "Pending" ? <option>Quarantined</option> : null}
                  </select>
                </label>
                <label>
                  Quantity
                  <input value={row.quantity} onChange={(event) => editMove(index, { quantity: event.target.value })} />
                </label>
                <label>
                  Batch
                  <input value={row.batch_number} onChange={(event) => editMove(index, { batch_number: event.target.value })} />
                </label>
                <label>
                  Heat
                  <input value={row.heat_number} onChange={(event) => editMove(index, { heat_number: event.target.value })} />
                </label>
                <label>
                  Serial
                  <input value={row.serial_number} onChange={(event) => editMove(index, { serial_number: event.target.value })} />
                </label>
              </div>
            </div>
          ))}
          <button className="primary" type="submit">
            <Plus size={15} /> Save draft
          </button>
        </form>
      ) : null}
      <div className="contact-grid">
        {register?.receipts.map((row) => (
          <article key={row.id} className="contact-card q-mat">
            <header>
              <strong><PackageCheck size={15} /> {row.number}</strong>
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            {row.lines.map((line) => (
              <div key={line.id}>
                <p>{line.item_code} · received {line.received} {line.unit}</p>
                <Split line={line} />
              </div>
            ))}
          </article>
        ))}
        {register?.inspections.map((row) => (
          <article key={row.id} className="contact-card q-mat">
            <header>
              <strong><PackageCheck size={15} /> {row.number}</strong>
              <span className={statusChip(row.status)}>{row.status}</span>
            </header>
            <p>{row.receipt_number} · {row.inspector_name}</p>
            <p className="muted">{row.statement}</p>
            {row.certificate_reference ? <p>Certificate {row.certificate_reference}</p> : null}
            <ul>
              {row.lines.map((line) => (
                <li key={`${line.goods_receipt_line_id}-${line.from_state}-${line.to_state}-${line.quantity}`}>
                  <BadgeCheck size={13} /> {line.item_code}: {line.quantity} {line.unit} from {line.from_state} to {line.to_state}
                  {line.batch_number ? ` · batch ${line.batch_number}` : ""}
                  {line.heat_number ? ` · heat ${line.heat_number}` : ""}
                  {line.serial_number ? ` · serial ${line.serial_number}` : ""}
                </li>
              ))}
            </ul>
            {canPlan && (row.status === "Draft" || row.status === "Returned for Correction") ? (
              <button className="primary" type="button" onClick={() => void submit(row)}>
                <Send size={15} /> {row.status === "Draft" ? "Submit" : "Resubmit"}
              </button>
            ) : null}
          </article>
        ))}
      </div>
    </>
  );
}

type RequestActivity = {
  id: number;
  code: string;
  package_code: string;
  package_status: string;
  discipline_id: number;
  unit: string;
  verified_quantity: string | null;
  verified_percent: string | null;
  waiting_quantity: string | null;
};
type RequestForm = { id: number; label: string; discipline_id: number; units: string };
type RequestPoint = { id: number; name: string; point_type: string; discipline_id: number | null; document_label: string };
type RequestResult = { item: string; result: string; measurement: string };
type ConstructionRequestRow = {
  id: number;
  number: string;
  package_code: string;
  package_status: string;
  activity_code: string;
  template_label: string;
  checkpoint_name: string;
  point_type: string;
  status: string;
  outcome: string;
  location: string;
  statement: string;
  version: number;
  offered_quantity: string | null;
  accepted_quantity: string | null;
  rejected_quantity: string | null;
  results: RequestResult[];
  inspector_id: number;
  attendees: string;
  findings: string;
  requested_on: string;
};
type RequestRegister = {
  note: string;
  activities: RequestActivity[];
  forms: RequestForm[];
  checkpoints: RequestPoint[];
  members: { id: number; name: string }[];
  requests: ConstructionRequestRow[];
};

function RequestsPanel({ pid, canRequest, admin }: { pid: number; canRequest: boolean; admin: boolean }) {
  const [register, setRegister] = useState<RequestRegister | null>(null);
  const [error, setError] = useState("");
  const [number, setNumber] = useState("");
  const [activityId, setActivityId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [checkpointId, setCheckpointId] = useState("");
  const [location, setLocation] = useState("");
  const [requestedOn, setRequestedOn] = useState("");
  const [inspectorId, setInspectorId] = useState("");
  const [attendees, setAttendees] = useState("");
  const [findings, setFindings] = useState("");
  async function load() {
    setRegister(await api<RequestRegister>(`/projects/${pid}/quality/requests`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  const activity = register?.activities.find((row) => String(row.id) === activityId);
  const forms = register?.forms.filter((row) => !activity || row.discipline_id === activity.discipline_id) || [];
  const points = register?.checkpoints.filter((row) => !activity || row.discipline_id === activity.discipline_id || row.discipline_id == null) || [];
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/projects/${pid}/quality/requests`, "POST", {
        number,
        activity_id: Number(activityId),
        template_id: Number(templateId),
        checkpoint_id: checkpointId ? Number(checkpointId) : null,
        location,
        requested_on: requestedOn,
        requester_id: Number(inspectorId),
        inspector_id: Number(inspectorId),
        attendees,
        findings,
      });
      setNumber("");
      setLocation("");
      setAttendees("");
      setFindings("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  async function saveResults(row: ConstructionRequestRow, outcome: string, accepted: string, results: RequestResult[]) {
    setError("");
    try {
      const saved = await api<ConstructionRequestRow>(`/projects/${pid}/quality/requests/${row.id}`, "PUT", {
        version: row.version,
        outcome,
        accepted_quantity: outcome === "Partially Accepted" ? accepted : null,
        location: row.location,
        requested_on: row.requested_on,
        inspector_id: row.inspector_id,
        attendees: row.attendees,
        findings: row.findings,
        results,
      });
      await api(`/projects/${pid}/quality/requests/${row.id}/submit`, "POST", { version: saved.version });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      <QualityRoutes pid={pid} admin={admin} routes={REQUEST_ROUTES} />
      <p>{register?.note}</p>
      <Err text={error} />
      {canRequest ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide">
            <ClipboardList size={18} strokeWidth={2.4} /> Request a construction inspection
          </h3>
          <label>
            Number
            <input value={number} onChange={(event) => setNumber(event.target.value)} required />
          </label>
          <label>
            Activity
            <select value={activityId} onChange={(event) => { setActivityId(event.target.value); setTemplateId(""); setCheckpointId(""); }} required>
              <option value="">Choose verified work</option>
              {register?.activities.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.package_code} · {row.code}
                  {row.waiting_quantity ? ` · waiting ${row.waiting_quantity} ${row.unit}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Discipline form
            <select value={templateId} onChange={(event) => setTemplateId(event.target.value)} required>
              <option value="">Choose an approved form</option>
              {forms.map((row) => (
                <option key={row.id} value={row.id}>{row.label}</option>
              ))}
            </select>
          </label>
          <label>
            Checkpoint
            <select value={checkpointId} onChange={(event) => setCheckpointId(event.target.value)}>
              <option value="">No checkpoint</option>
              {points.map((row) => (
                <option key={row.id} value={row.id}>{row.point_type} · {row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Location
            <input value={location} onChange={(event) => setLocation(event.target.value)} required />
          </label>
          <label>
            Requested on
            <input type="date" value={requestedOn} onChange={(event) => setRequestedOn(event.target.value)} required />
          </label>
          <label>
            Inspector
            <select value={inspectorId} onChange={(event) => setInspectorId(event.target.value)} required>
              <option value="">Choose a project member</option>
              {register?.members.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Witness attendees
            <input value={attendees} onChange={(event) => setAttendees(event.target.value)} />
          </label>
          <label className="wide">
            Findings
            <textarea value={findings} onChange={(event) => setFindings(event.target.value)} />
          </label>
          <button className="primary" type="submit">
            <Plus size={15} /> Save draft
          </button>
        </form>
      ) : null}
      <div className="contact-grid">
        {register?.requests.map((row) => (
          <RequestCard key={row.id} row={row} canRequest={canRequest} onSave={saveResults} />
        ))}
      </div>
    </>
  );
}

function RequestCard({
  row,
  canRequest,
  onSave,
}: {
  row: ConstructionRequestRow;
  canRequest: boolean;
  onSave: (row: ConstructionRequestRow, outcome: string, accepted: string, results: RequestResult[]) => Promise<void>;
}) {
  const [outcome, setOutcome] = useState(row.outcome === "Pending" ? "Accepted" : row.outcome);
  const [accepted, setAccepted] = useState("");
  const [results, setResults] = useState<RequestResult[]>(row.results);
  const editable = canRequest && (row.status === "Draft" || row.status === "Returned for Correction");
  return (
    <article className="contact-card q-req">
      <header>
        <strong><ClipboardList size={15} /> {row.number}</strong>
        <span className={statusChip(row.status)}>{row.status}</span>
      </header>
      <p>{row.package_code} · {row.activity_code} · package {row.package_status}</p>
      <p>{row.template_label}{row.checkpoint_name ? ` · ${row.point_type} ${row.checkpoint_name}` : ""}</p>
      <p className="muted">{row.statement}</p>
      <p>{row.location}</p>
      {row.offered_quantity ? <p>Offered {row.offered_quantity} · accepted {row.accepted_quantity || "0"} · rejected {row.rejected_quantity || "0"}</p> : null}
      <span className={`q-point q-${(row.outcome || "pending").toLowerCase().split(" ")[0]}`}>{row.outcome}</span>
      {editable ? (
        <form
          className="contact-form"
          onSubmit={(event) => {
            event.preventDefault();
            void onSave(row, outcome, accepted, results);
          }}
        >
          {results.map((item, index) => (
            <label key={item.item}>
              {item.item}
              <select
                value={item.result}
                onChange={(event) => setResults((current) => current.map((line, position) => position === index ? { ...line, result: event.target.value } : line))}
                required
              >
                <option value="">Result</option>
                <option>Pass</option>
                <option>Fail</option>
                <option>Not applicable</option>
              </select>
            </label>
          ))}
          <label>
            Outcome
            <select value={outcome} onChange={(event) => setOutcome(event.target.value)}>
              <option>Accepted</option>
              <option>Partially Accepted</option>
              <option>Rejected</option>
            </select>
          </label>
          {outcome === "Partially Accepted" ? (
            <label>
              Accepted quantity
              <input value={accepted} onChange={(event) => setAccepted(event.target.value)} required />
            </label>
          ) : null}
          <button className="primary" type="submit">
            <Send size={15} /> Submit checklist
          </button>
        </form>
      ) : (
        <ul>
          {row.results.map((item) => (
            <li key={item.item}><BadgeCheck size={13} /> {item.item}: {item.result || "not recorded"}</li>
          ))}
        </ul>
      )}
    </article>
  );
}

type NcrBoard = {
  note: string;
  activities: { id: number; label: string }[];
  requests: { id: number; label: string }[];
  materials: { id: number; label: string }[];
  offers: { id: number; label: string }[];
  members: { id: number; name: string }[];
  companies: { id: number; name: string }[];
  disciplines: { id: number; name: string }[];
  ncrs: NcrRow[];
};

type NcrRow = {
  id: number;
  number: string;
  status: string;
  severity: string;
  disposition: string;
  description: string;
  corrective_action: string;
  source_label: string;
  owner_name: string;
  version: number;
  concessions: { id: number; number: string; status: string; proposal: string; version: number }[];
};

function NcrPanel({ pid, canPlan, canRequest, admin }: { pid: number; canPlan: boolean; canRequest: boolean; admin: boolean }) {
  const [board, setBoard] = useState<NcrBoard | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    number: "",
    source_kind: "activity",
    source_id: "",
    discipline_id: "",
    company_id: "",
    location: "",
    description: "",
    requirement: "",
    severity: "Major",
    affected_scope: "",
    containment: "",
    owner_id: "",
    raised_on: "",
    target_on: "",
    root_cause: "",
    corrective_action: "",
    disposition: "Rework",
  });
  async function load() {
    setBoard(await api<NcrBoard>(`/projects/${pid}/quality/ncrs`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  const sources =
    form.source_kind === "request"
      ? board?.requests || []
      : form.source_kind === "material"
        ? board?.materials || []
        : form.source_kind === "offer"
          ? board?.offers || []
          : board?.activities || [];
  function setField(key: string, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/projects/${pid}/quality/ncrs`, "POST", {
        ...form,
        source_id: Number(form.source_id),
        discipline_id: Number(form.discipline_id),
        company_id: Number(form.company_id),
        owner_id: Number(form.owner_id),
      });
      setForm((current) => ({ ...current, number: "" }));
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  async function act(path: string, body: object) {
    setError("");
    try {
      await api(path, "POST", body);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      <QualityRoutes pid={pid} admin={admin} routes={NCR_ROUTES} />
      <p>{board?.note}</p>
      <Err text={error} />
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide"><ShieldAlert size={18} strokeWidth={2.4} /> Raise an NCR</h3>
          <label>Number<input value={form.number} onChange={(event) => setField("number", event.target.value)} required /></label>
          <label>
            Source
            <select value={form.source_kind} onChange={(event) => setField("source_kind", event.target.value)}>
              <option value="activity">Activity</option>
              <option value="request">Construction inspection</option>
              <option value="material">Material inspection</option>
              <option value="offer">Inspection offer</option>
            </select>
          </label>
          <label>
            Record
            <select value={form.source_id} onChange={(event) => setField("source_id", event.target.value)} required>
              <option value="">Choose the record</option>
              {sources.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}
            </select>
          </label>
          <label>
            Discipline
            <select value={form.discipline_id} onChange={(event) => setField("discipline_id", event.target.value)} required>
              <option value="">Choose a discipline</option>
              {board?.disciplines.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Company
            <select value={form.company_id} onChange={(event) => setField("company_id", event.target.value)} required>
              <option value="">Choose a company</option>
              {board?.companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Location<input value={form.location} onChange={(event) => setField("location", event.target.value)} required /></label>
          <label>Severity
            <select value={form.severity} onChange={(event) => setField("severity", event.target.value)}>
              <option>Minor</option><option>Major</option><option>Critical</option>
            </select>
          </label>
          <label>Disposition
            <select value={form.disposition} onChange={(event) => setField("disposition", event.target.value)}>
              <option>Rework</option><option>Repair</option><option>Reject/Return</option><option>Use-As-Is</option>
            </select>
          </label>
          <label>Owner
            <select value={form.owner_id} onChange={(event) => setField("owner_id", event.target.value)} required>
              <option value="">Choose a project member</option>
              {board?.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Raised on<input type="date" value={form.raised_on} onChange={(event) => setField("raised_on", event.target.value)} required /></label>
          <label>Target<input type="date" value={form.target_on} onChange={(event) => setField("target_on", event.target.value)} required /></label>
          <label className="wide">Description<textarea value={form.description} onChange={(event) => setField("description", event.target.value)} required /></label>
          <label className="wide">Requirement<textarea value={form.requirement} onChange={(event) => setField("requirement", event.target.value)} required /></label>
          <label className="wide">Affected scope<textarea value={form.affected_scope} onChange={(event) => setField("affected_scope", event.target.value)} required /></label>
          <label className="wide">Containment<textarea value={form.containment} onChange={(event) => setField("containment", event.target.value)} required /></label>
          <label className="wide">Root cause<textarea value={form.root_cause} onChange={(event) => setField("root_cause", event.target.value)} required /></label>
          <label className="wide">Corrective action<textarea value={form.corrective_action} onChange={(event) => setField("corrective_action", event.target.value)} required /></label>
          <button className="primary" type="submit"><Plus size={15} /> Save draft</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {board?.ncrs.map((row) => (
          <NcrCard key={row.id} pid={pid} row={row} canPlan={canPlan} canRequest={canRequest} onAct={act} />
        ))}
      </div>
    </>
  );
}

function NcrCard({
  pid,
  row,
  canPlan,
  canRequest,
  onAct,
}: {
  pid: number;
  row: NcrRow;
  canPlan: boolean;
  canRequest: boolean;
  onAct: (path: string, body: object) => Promise<void>;
}) {
  const [proposal, setProposal] = useState("");
  const [number, setNumber] = useState("");
  const [evidence, setEvidence] = useState("");
  const [verification, setVerification] = useState("");
  const draft = row.status === "Draft" || row.status === "Returned for Correction";
  return (
    <article className="contact-card q-ncr">
      <header>
        <strong><ShieldAlert size={16} /> {row.number}</strong>
        <span className={statusChip(row.status)}>{row.status}</span>
      </header>
      <p>{row.source_label} · {row.severity} · {row.disposition}</p>
      <p>{row.description}</p>
      <p className="muted">Corrective action: {row.corrective_action}</p>
      <p className="muted">Owner {row.owner_name}</p>
      {row.concessions.map((item) => (
        <p key={item.id}>Concession {item.number}: {item.status}. {item.proposal}</p>
      ))}
      {canPlan && draft ? (
        <button className="primary" type="button" onClick={() => void onAct(`/projects/${pid}/quality/ncrs/${row.id}/submit`, { version: row.version })}>
          <Send size={15} /> Submit disposition
        </button>
      ) : null}
      {canRequest && row.disposition === "Use-As-Is" && !row.concessions.some((item) => item.status === "Approved" || item.status === "Draft" || item.status === "Pending Review") ? (
        <form
          className="contact-form"
          onSubmit={(event) => {
            event.preventDefault();
            void onAct(`/projects/${pid}/quality/concessions`, { ncr_id: row.id, number, proposal, technical_note: "" });
          }}
        >
          <label>Concession number<input value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label className="wide">Proposal<textarea value={proposal} onChange={(event) => setProposal(event.target.value)} required /></label>
          <button className="primary" type="submit"><Plus size={15} /> Save concession</button>
        </form>
      ) : null}
      {canRequest
        ? row.concessions
            .filter((item) => item.status === "Draft" || item.status === "Returned for Correction")
            .map((item) => (
              <button key={item.id} className="primary" type="button" onClick={() => void onAct(`/projects/${pid}/quality/concessions/${item.id}/submit`, { version: item.version })}>
                <Send size={15} /> Submit {item.number}
              </button>
            ))
        : null}
      {canRequest && (row.status === "Approved" || row.status === "Verification Returned") ? (
        <form
          className="contact-form"
          onSubmit={(event) => {
            event.preventDefault();
            void onAct(`/projects/${pid}/quality/ncrs/${row.id}/close`, { version: row.version, evidence, verification });
          }}
        >
          <label className="wide">Evidence<textarea value={evidence} onChange={(event) => setEvidence(event.target.value)} required /></label>
          <label className="wide">Verification<textarea value={verification} onChange={(event) => setVerification(event.target.value)} required /></label>
          <button className="primary" type="submit"><Send size={15} /> Submit closure</button>
        </form>
      ) : null}
    </article>
  );
}

type HoldBoard = {
  note: string;
  packages: { id: number; label: string }[];
  activities: { id: number; label: string }[];
  receipts: { id: number; label: string }[];
  checkpoints: { id: number; label: string }[];
  members: { id: number; name: string }[];
  holds: HoldRow[];
};

type HoldRow = {
  id: number;
  number: string;
  status: string;
  scope_kind: string;
  scope_label: string;
  reason: string;
  conditions: string;
  blocks_issue: boolean;
  blocks_work: boolean;
  blocks_handover: boolean;
  version: number;
};

function HoldsPanel({ pid, canPlan, canRequest, admin }: { pid: number; canPlan: boolean; canRequest: boolean; admin: boolean }) {
  const [board, setBoard] = useState<HoldBoard | null>(null);
  const [error, setError] = useState("");
  const [number, setNumber] = useState("");
  const [scopeKind, setScopeKind] = useState("activity");
  const [scopeId, setScopeId] = useState("");
  const [checkpointId, setCheckpointId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [reason, setReason] = useState("");
  const [conditions, setConditions] = useState("");
  const [blocksIssue, setBlocksIssue] = useState(false);
  const [blocksWork, setBlocksWork] = useState(true);
  const [blocksHandover, setBlocksHandover] = useState(false);
  async function load() {
    setBoard(await api<HoldBoard>(`/projects/${pid}/quality/holds`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  const scopes = scopeKind === "package" ? board?.packages || [] : scopeKind === "receipt" ? board?.receipts || [] : board?.activities || [];
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/projects/${pid}/quality/holds`, "POST", {
        number,
        scope_kind: scopeKind,
        scope_id: Number(scopeId),
        checkpoint_id: checkpointId ? Number(checkpointId) : null,
        owner_id: Number(ownerId),
        reason,
        conditions,
        blocks_issue: blocksIssue,
        blocks_work: blocksWork,
        blocks_handover: blocksHandover,
      });
      setNumber("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      <QualityRoutes pid={pid} admin={admin} routes={HOLD_ROUTES} />
      <p>{board?.note}</p>
      <Err text={error} />
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide"><OctagonAlert size={18} strokeWidth={2.4} /> Place a quality hold</h3>
          <label>Number<input value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label>
            Scope
            <select value={scopeKind} onChange={(event) => setScopeKind(event.target.value)}>
              <option value="activity">Activity</option>
              <option value="package">Work package</option>
              <option value="receipt">Receipt line</option>
            </select>
          </label>
          <label>
            Record
            <select value={scopeId} onChange={(event) => setScopeId(event.target.value)} required>
              <option value="">Choose the scope</option>
              {scopes.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}
            </select>
          </label>
          {scopeKind === "activity" ? (
            <label>
              Hold point
              <select value={checkpointId} onChange={(event) => setCheckpointId(event.target.value)}>
                <option value="">No hold point</option>
                {board?.checkpoints.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}
              </select>
            </label>
          ) : null}
          <label>
            Owner
            <select value={ownerId} onChange={(event) => setOwnerId(event.target.value)} required>
              <option value="">Choose a project member</option>
              {board?.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label className="wide">Reason<textarea value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
          <label className="wide">Release conditions<textarea value={conditions} onChange={(event) => setConditions(event.target.value)} required /></label>
          <label><input type="checkbox" checked={blocksIssue} onChange={(event) => setBlocksIssue(event.target.checked)} /> Block material issue</label>
          <label><input type="checkbox" checked={blocksWork} onChange={(event) => setBlocksWork(event.target.checked)} /> Block construction work</label>
          <label><input type="checkbox" checked={blocksHandover} onChange={(event) => setBlocksHandover(event.target.checked)} /> Block handover</label>
          <button className="primary" type="submit"><Plus size={15} /> Place hold</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {board?.holds.map((row) => (
          <HoldCard key={row.id} pid={pid} row={row} canRequest={canRequest} onDone={load} onError={setError} />
        ))}
      </div>
    </>
  );
}

function HoldCard({
  pid,
  row,
  canRequest,
  onDone,
  onError,
}: {
  pid: number;
  row: HoldRow;
  canRequest: boolean;
  onDone: () => Promise<void>;
  onError: (text: string) => void;
}) {
  const [evidence, setEvidence] = useState("");
  const blocks = [
    row.blocks_issue ? "material issue" : "",
    row.blocks_work ? "construction work" : "",
    row.blocks_handover ? "handover" : "",
  ].filter(Boolean).join(", ");
  async function release(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/quality/holds/${row.id}/release`, "POST", { version: row.version, evidence });
      await onDone();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <article className="contact-card q-holdcard">
      <header>
        <strong><OctagonAlert size={16} /> {row.number}</strong>
        <span className={statusChip(row.status)}>{row.status}</span>
      </header>
      <p>{row.scope_kind} · {row.scope_label}</p>
      <p>{row.reason}</p>
      <p className="muted">Release when: {row.conditions}</p>
      <p className="muted">Blocks {blocks}</p>
      {canRequest && (row.status === "Active" || row.status === "Release Returned") ? (
        <form className="contact-form" onSubmit={(event) => void release(event)}>
          <label className="wide">Release evidence<textarea value={evidence} onChange={(event) => setEvidence(event.target.value)} required /></label>
          <button className="primary" type="submit"><Send size={15} /> Request release</button>
        </form>
      ) : null}
    </article>
  );
}

type DashCount = { accepted: number; partial: number; rejected: number; originals: number; reinspections: number };
type DashBoard = {
  note: string;
  open_ncrs: number;
  overdue_ncrs: number;
  active_holds: number;
  pending_reviews: number;
  pending_material_lines: number;
  blocking_punches?: number;
  approved_dossiers?: number;
  first_pass: DashCount;
  expiring: { kind: string; number: string; label: string; due: string; state: string }[];
  impacts: { number: string; person: string; reason: string; inspections: { number: string; status: string; outcome: string }[] }[];
};

function DashboardPanel({ pid, admin }: { pid: number; admin: boolean }) {
  const [board, setBoard] = useState<DashBoard | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void api<DashBoard>(`/projects/${pid}/quality/dashboard`)
      .then(setBoard)
      .catch((err) => setError((err as Error).message));
  }, [pid]);
  const passed = board?.first_pass;
  const cards = board
    ? [
        ["Open NCRs", String(board.open_ncrs)],
        ["Overdue NCRs", String(board.overdue_ncrs)],
        ["Active holds", String(board.active_holds)],
        ["Pending reviews", String(board.pending_reviews)],
        ["Material lines still pending", String(board.pending_material_lines)],
        ["Reinspections", String(passed?.reinspections ?? 0)],
        ["Blocking punch items", String(board.blocking_punches ?? 0)],
        ["Approved dossiers", String(board.approved_dossiers ?? 0)],
      ]
    : [];
  return (
    <>
      <Err text={error} />
      <QualityRoutes pid={pid} admin={admin} routes={ALL_QUALITY_ROUTES} />
      <p>{board?.note}</p>
      <div className="contact-grid">
        {cards.map(([label, value]) => (
          <article key={label} className="contact-card q-dash">
            <header><strong><LayoutDashboard size={16} /> {label}</strong></header>
            <p>{value}</p>
          </article>
        ))}
        {passed ? (
          <article className="contact-card q-dash">
            <header><strong><BadgeCheck size={16} /> First-pass acceptance</strong></header>
            <p>{passed.accepted} accepted, {passed.partial} partial, {passed.rejected} rejected of {passed.originals} original inspections</p>
            <p className="muted">Reinspections are counted separately and are not added to this total.</p>
          </article>
        ) : null}
      </div>
      {board?.expiring.length ? (
        <div className="contact-grid">
          {board.expiring.map((row) => (
            <article key={`${row.kind}-${row.number}`} className="contact-card q-dash">
              <header>
                <strong>{row.kind === "Calibration" ? <Timer size={16} /> : <Award size={16} />} {row.number}</strong>
                <span className={statusChip(row.state)}>{row.state}</span>
              </header>
              <p>{row.kind} · {row.label}</p>
              <p className="muted">Due {row.due}. Elapsed time does not accept the work or release a hold.</p>
            </article>
          ))}
        </div>
      ) : null}
      {board?.impacts.map((row) => (
        <article key={row.number} className="contact-card q-qual">
          <header><strong><Award size={16} /> {row.number} withdrawn</strong></header>
          <p>{row.person}. {row.reason}</p>
          <p className="muted">
            {row.inspections.length
              ? row.inspections.map((item) => `${item.number} stays ${item.status} / ${item.outcome || "pending"}`).join(". ")
              : "No inspection outcome was changed."}
          </p>
        </article>
      ))}
    </>
  );
}

type QualRow = {
  id: number;
  number: string;
  person_id: number;
  person_name: string;
  status: string;
  qualification_type: string;
  applicable_activities: string;
  issuer: string;
  certificate_number: string;
  valid_from: string;
  valid_to: string;
  evidence: string;
  statement: string;
  withdrawal_reason: string;
  affected: { number: string; status: string; outcome: string; activity_code: string }[];
  version: number;
};
type QualBoard = { note: string; members: { id: number; name: string }[]; qualifications: QualRow[] };

function QualificationsPanel({ pid, canPlan, admin }: { pid: number; canPlan: boolean; admin: boolean }) {
  const [board, setBoard] = useState<QualBoard | null>(null);
  const [error, setError] = useState("");
  const [number, setNumber] = useState("");
  const [personId, setPersonId] = useState("");
  const [kind, setKind] = useState("");
  const [activities, setActivities] = useState("");
  const [issuer, setIssuer] = useState("");
  const [certificate, setCertificate] = useState("");
  const [validFrom, setValidFrom] = useState("");
  const [validTo, setValidTo] = useState("");
  const [evidence, setEvidence] = useState("");
  async function load() {
    setBoard(await api<QualBoard>(`/projects/${pid}/quality/qualifications`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/projects/${pid}/quality/qualifications`, "POST", {
        number,
        person_id: Number(personId),
        qualification_type: kind,
        applicable_activities: activities,
        issuer,
        certificate_number: certificate,
        valid_from: validFrom,
        valid_to: validTo,
        evidence,
      });
      setNumber("");
      setKind("");
      setActivities("");
      setIssuer("");
      setCertificate("");
      setEvidence("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      <QualityRoutes pid={pid} admin={admin} routes={QUAL_ROUTES} />
      <Err text={error} />
      <p>{board?.note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide"><Award size={18} strokeWidth={2.4} /> Record a qualification</h3>
          <label>Number<input value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label>
            Person
            <select value={personId} onChange={(event) => setPersonId(event.target.value)} required>
              <option value="">Choose a project member</option>
              {board?.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>Qualification<input value={kind} onChange={(event) => setKind(event.target.value)} required /></label>
          <label>Issuer<input value={issuer} onChange={(event) => setIssuer(event.target.value)} required /></label>
          <label>Certificate<input value={certificate} onChange={(event) => setCertificate(event.target.value)} required /></label>
          <label>Valid from<input type="date" value={validFrom} onChange={(event) => setValidFrom(event.target.value)} required /></label>
          <label>Valid to<input type="date" value={validTo} onChange={(event) => setValidTo(event.target.value)} required /></label>
          <label className="wide">Applicable activities<textarea value={activities} onChange={(event) => setActivities(event.target.value)} required /></label>
          <label className="wide">Evidence<textarea value={evidence} onChange={(event) => setEvidence(event.target.value)} required /></label>
          <button className="primary" type="submit"><Plus size={15} /> Save draft</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {board?.qualifications.map((row) => (
          <QualCard key={row.id} pid={pid} row={row} canPlan={canPlan} onDone={load} onError={setError} />
        ))}
      </div>
    </>
  );
}

function QualCard({
  pid,
  row,
  canPlan,
  onDone,
  onError,
}: {
  pid: number;
  row: QualRow;
  canPlan: boolean;
  onDone: () => Promise<void>;
  onError: (text: string) => void;
}) {
  const [reason, setReason] = useState("");
  async function submit() {
    onError("");
    const path = row.status === "Returned for Correction" ? "resubmit" : "submit";
    try {
      await api(`/projects/${pid}/quality/qualifications/${row.id}/${path}`, "POST", { version: row.version });
      await onDone();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function withdraw(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/quality/qualifications/${row.id}/withdraw`, "POST", { version: row.version, reason });
      await onDone();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <article className="contact-card q-qual">
      <header>
        <strong><Award size={16} /> {row.number}</strong>
        <span className={statusChip(row.status)}>{row.status}</span>
      </header>
      <p>{row.person_name} · {row.qualification_type}</p>
      <p className="muted">{row.certificate_number} · {row.issuer}</p>
      <p className="muted">{row.valid_from} to {row.valid_to}</p>
      <p className="muted">{row.applicable_activities}</p>
      <p className="muted">{row.statement}</p>
      {row.withdrawal_reason ? <p>Withdrawn: {row.withdrawal_reason}</p> : null}
      {row.affected.length ? (
        <p className="muted">Inspections left unchanged: {row.affected.map((item) => `${item.number} ${item.status}`).join(", ")}</p>
      ) : null}
      {canPlan && (row.status === "Draft" || row.status === "Returned for Correction") ? (
        <button type="button" onClick={() => void submit()}><Send size={15} /> Submit</button>
      ) : null}
      {canPlan && row.status === "Approved" ? (
        <form className="contact-form" onSubmit={(event) => void withdraw(event)}>
          <label className="wide">Withdrawal reason<textarea value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
          <button type="submit"><Ban size={15} /> Withdraw</button>
        </form>
      ) : null}
    </article>
  );
}

type CalRow = {
  id: number;
  number: string;
  status: string;
  equipment_code: string;
  description: string;
  serial_number: string;
  certificate_reference: string;
  calibrated_on: string;
  due_on: string;
  use_range: string;
  statement: string;
  withdrawal_reason: string;
  affected_note: string;
  version: number;
};
type CalBoard = { note: string; calibrations: CalRow[] };

function CalibrationsPanel({ pid, canPlan, admin }: { pid: number; canPlan: boolean; admin: boolean }) {
  const [board, setBoard] = useState<CalBoard | null>(null);
  const [error, setError] = useState("");
  const [number, setNumber] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [serial, setSerial] = useState("");
  const [certificate, setCertificate] = useState("");
  const [calibratedOn, setCalibratedOn] = useState("");
  const [dueOn, setDueOn] = useState("");
  const [useRange, setUseRange] = useState("");
  const [evidence, setEvidence] = useState("");
  async function load() {
    setBoard(await api<CalBoard>(`/projects/${pid}/quality/calibrations`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/projects/${pid}/quality/calibrations`, "POST", {
        number,
        equipment_code: code,
        description,
        serial_number: serial,
        certificate_reference: certificate,
        calibrated_on: calibratedOn,
        due_on: dueOn,
        use_range: useRange,
        evidence,
      });
      setNumber("");
      setCode("");
      setDescription("");
      setSerial("");
      setCertificate("");
      setUseRange("");
      setEvidence("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      <QualityRoutes pid={pid} admin={admin} routes={CAL_ROUTES} />
      <Err text={error} />
      <p>{board?.note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide"><Timer size={18} strokeWidth={2.4} /> Record a calibration</h3>
          <label>Number<input value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label>Equipment id<input value={code} onChange={(event) => setCode(event.target.value)} required /></label>
          <label>Description<input value={description} onChange={(event) => setDescription(event.target.value)} required /></label>
          <label>Serial<input value={serial} onChange={(event) => setSerial(event.target.value)} required /></label>
          <label>Certificate<input value={certificate} onChange={(event) => setCertificate(event.target.value)} required /></label>
          <label>Calibrated on<input type="date" value={calibratedOn} onChange={(event) => setCalibratedOn(event.target.value)} required /></label>
          <label>Due on<input type="date" value={dueOn} onChange={(event) => setDueOn(event.target.value)} required /></label>
          <label>Range and use<input value={useRange} onChange={(event) => setUseRange(event.target.value)} required /></label>
          <label className="wide">Evidence<textarea value={evidence} onChange={(event) => setEvidence(event.target.value)} required /></label>
          <button className="primary" type="submit"><Plus size={15} /> Save draft</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {board?.calibrations.map((row) => (
          <CalCard key={row.id} pid={pid} row={row} canPlan={canPlan} onDone={load} onError={setError} />
        ))}
      </div>
    </>
  );
}

function CalCard({
  pid,
  row,
  canPlan,
  onDone,
  onError,
}: {
  pid: number;
  row: CalRow;
  canPlan: boolean;
  onDone: () => Promise<void>;
  onError: (text: string) => void;
}) {
  const [reason, setReason] = useState("");
  async function submit() {
    onError("");
    const path = row.status === "Returned for Correction" ? "resubmit" : "submit";
    try {
      await api(`/projects/${pid}/quality/calibrations/${row.id}/${path}`, "POST", { version: row.version });
      await onDone();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function withdraw(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/quality/calibrations/${row.id}/withdraw`, "POST", { version: row.version, reason });
      await onDone();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <article className="contact-card q-cal">
      <header>
        <strong><Timer size={16} /> {row.number}</strong>
        <span className={statusChip(row.status)}>{row.status}</span>
      </header>
      <p>{row.equipment_code} · {row.description}</p>
      <p className="muted">Serial {row.serial_number} · {row.certificate_reference}</p>
      <p className="muted">{row.calibrated_on} due {row.due_on} · {row.use_range}</p>
      <p className="muted">{row.statement}</p>
      {row.withdrawal_reason ? <p>Withdrawn: {row.withdrawal_reason}. {row.affected_note}</p> : null}
      {canPlan && (row.status === "Draft" || row.status === "Returned for Correction") ? (
        <button type="button" onClick={() => void submit()}><Send size={15} /> Submit</button>
      ) : null}
      {canPlan && row.status === "Approved" ? (
        <form className="contact-form" onSubmit={(event) => void withdraw(event)}>
          <label className="wide">Withdrawal reason<textarea value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
          <button type="submit"><Ban size={15} /> Withdraw</button>
        </form>
      ) : null}
    </article>
  );
}

type DossierIndex = {
  procedures?: { kind: string; number: string; revision?: string; version: number }[];
  punches?: { number: string; blocking: boolean; status: string }[];
  gaps?: string[];
};
type DossierRow = {
  id: number;
  number: string;
  package_code: string;
  package_status: string;
  status: string;
  statement: string;
  payload: { index?: DossierIndex };
  version: number;
};
type PunchRow = {
  id: number;
  number: string;
  package_code: string;
  issue_type: string;
  status: string;
  description: string;
  owner_name: string;
  severity: string;
  blocking: boolean;
  due_on: string;
  blocker_label: string;
  statement: string;
  version: number;
};
type DossierBoard = {
  note: string;
  packages: { id: number; code: string; status: string }[];
  members: { id: number; name: string }[];
  blockers: { id: number; package_id: number; kind: string; description: string }[];
  dossiers: DossierRow[];
  punches: PunchRow[];
};

function DossiersPanel({ pid, canPlan, admin }: { pid: number; canPlan: boolean; admin: boolean }) {
  const [board, setBoard] = useState<DossierBoard | null>(null);
  const [error, setError] = useState("");
  const [number, setNumber] = useState("");
  const [packageId, setPackageId] = useState("");
  async function load() {
    setBoard(await api<DossierBoard>(`/projects/${pid}/quality/dossiers`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/projects/${pid}/quality/dossiers`, "POST", { number, package_id: Number(packageId) });
      setNumber("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      <QualityRoutes pid={pid} admin={admin} routes={DOSSIER_ROUTES} />
      <Err text={error} />
      <p>{board?.note}</p>
      {canPlan ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide"><FolderOpen size={18} strokeWidth={2.4} /> Build a quality dossier</h3>
          <label>Number<input value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label>
            Work package
            <select value={packageId} onChange={(event) => setPackageId(event.target.value)} required>
              <option value="">Choose a work package</option>
              {board?.packages.map((row) => (
                <option key={row.id} value={row.id}>{row.code} · {row.status}</option>
              ))}
            </select>
          </label>
          <button className="primary" type="submit"><Plus size={15} /> Save draft</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {board?.dossiers.map((row) => (
          <DossierCard key={row.id} pid={pid} row={row} canPlan={canPlan} onDone={load} onError={setError} />
        ))}
      </div>
    </>
  );
}

function DossierCard({
  pid,
  row,
  canPlan,
  onDone,
  onError,
}: {
  pid: number;
  row: DossierRow;
  canPlan: boolean;
  onDone: () => Promise<void>;
  onError: (text: string) => void;
}) {
  const index = row.payload.index;
  async function submit() {
    onError("");
    const path = row.status === "Returned for Correction" ? "resubmit" : "submit";
    try {
      await api(`/projects/${pid}/quality/dossiers/${row.id}/${path}`, "POST", { version: row.version });
      await onDone();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <article className="contact-card q-dossier">
      <header>
        <strong><FolderOpen size={16} /> {row.number}</strong>
        <span className={statusChip(row.status)}>{row.status}</span>
      </header>
      <p>{row.package_code} · {row.package_status}</p>
      <p className="muted">{row.statement}</p>
      {index ? (
        <p className="muted">
          {(index.procedures || []).length} procedures · {(index.punches || []).length} open punch items
          {(index.gaps || []).length ? ` · ${index.gaps?.join(". ")}` : ""}
        </p>
      ) : <p className="muted">Submit to freeze the index.</p>}
      {canPlan && (row.status === "Draft" || row.status === "Returned for Correction") ? (
        <button type="button" onClick={() => void submit()}><Send size={15} /> Submit</button>
      ) : null}
    </article>
  );
}

function PunchPanel({ pid, canRequest, companyId, admin }: { pid: number; canRequest: boolean; companyId: number; admin: boolean }) {
  const [board, setBoard] = useState<DossierBoard | null>(null);
  const [error, setError] = useState("");
  const [number, setNumber] = useState("");
  const [packageId, setPackageId] = useState("");
  const [issueType, setIssueType] = useState("Punch");
  const [description, setDescription] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [severity, setSeverity] = useState("Minor");
  const [blocking, setBlocking] = useState(true);
  const [dueOn, setDueOn] = useState("");
  const [blockerId, setBlockerId] = useState("");
  async function load() {
    setBoard(await api<DossierBoard>(`/projects/${pid}/quality/dossiers`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/projects/${pid}/quality/punches`, "POST", {
        number,
        package_id: Number(packageId),
        issue_type: issueType,
        description,
        company_id: companyId,
        owner_id: Number(ownerId),
        severity,
        blocking,
        due_on: dueOn,
        blocker_id: blockerId ? Number(blockerId) : null,
      });
      setNumber("");
      setDescription("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      <QualityRoutes pid={pid} admin={admin} routes={PUNCH_ROUTES} />
      <Err text={error} />
      <p>An observation or punch item stays on the quality record. Closing it does not resolve a construction blocker or certify billing.</p>
      {canRequest ? (
        <form className="contact-form" onSubmit={(event) => void create(event)}>
          <h3 className="section-mark wide"><ListTodo size={18} strokeWidth={2.4} /> Raise a punch item</h3>
          <label>Number<input value={number} onChange={(event) => setNumber(event.target.value)} required /></label>
          <label>
            Work package
            <select value={packageId} onChange={(event) => setPackageId(event.target.value)} required>
              <option value="">Choose a work package</option>
              {board?.packages.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.status}</option>)}
            </select>
          </label>
          <label>
            Type
            <select value={issueType} onChange={(event) => setIssueType(event.target.value)}>
              <option>Punch</option>
              <option>Observation</option>
            </select>
          </label>
          <label>
            Owner
            <select value={ownerId} onChange={(event) => setOwnerId(event.target.value)} required>
              <option value="">Choose a project member</option>
              {board?.members.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Severity
            <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
              <option>Minor</option>
              <option>Major</option>
              <option>Critical</option>
            </select>
          </label>
          <label>Due<input type="date" value={dueOn} onChange={(event) => setDueOn(event.target.value)} required /></label>
          <label>
            Construction blocker
            <select value={blockerId} onChange={(event) => setBlockerId(event.target.value)}>
              <option value="">None. This is a quality item</option>
              {board?.blockers.filter((row) => String(row.package_id) === packageId).map((row) => (
                <option key={row.id} value={row.id}>{row.kind} · {row.description}</option>
              ))}
            </select>
          </label>
          <label className="wide">Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} required /></label>
          <label><input type="checkbox" checked={blocking} onChange={(event) => setBlocking(event.target.checked)} /> Blocking</label>
          <button className="primary" type="submit"><Plus size={15} /> Save</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {board?.punches.map((row) => (
          <PunchCard key={row.id} pid={pid} row={row} canRequest={canRequest} onDone={load} onError={setError} />
        ))}
      </div>
    </>
  );
}

function PunchCard({
  pid,
  row,
  canRequest,
  onDone,
  onError,
}: {
  pid: number;
  row: PunchRow;
  canRequest: boolean;
  onDone: () => Promise<void>;
  onError: (text: string) => void;
}) {
  const [evidence, setEvidence] = useState("");
  const [verification, setVerification] = useState("");
  async function close(event: FormEvent) {
    event.preventDefault();
    onError("");
    const path = row.status === "Closure Returned" ? "resubmit" : "close";
    const body = path === "close" ? { version: row.version, evidence, verification } : { version: row.version };
    try {
      await api(`/projects/${pid}/quality/punches/${row.id}/${path}`, "POST", body);
      await onDone();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <article className="contact-card q-punch">
      <header>
        <strong><ListTodo size={16} /> {row.number}</strong>
        <span className={statusChip(row.status)}>{row.status}</span>
      </header>
      <p>{row.issue_type} · {row.package_code} · {row.severity}{row.blocking ? " · Blocking" : ""}</p>
      <p>{row.description}</p>
      <p className="muted">Owner {row.owner_name} · due {row.due_on}{row.blocker_label ? ` · construction ${row.blocker_label}` : ""}</p>
      <p className="muted">{row.statement}</p>
      {canRequest && (row.status === "Open" || row.status === "Closure Returned") ? (
        <form className="contact-form" onSubmit={(event) => void close(event)}>
          {row.status === "Open" ? (
            <>
              <label className="wide">Evidence<textarea value={evidence} onChange={(event) => setEvidence(event.target.value)} required /></label>
              <label className="wide">Verification<textarea value={verification} onChange={(event) => setVerification(event.target.value)} required /></label>
            </>
          ) : null}
          <button className="primary" type="submit"><Send size={15} /> Submit closure</button>
        </form>
      ) : null}
    </article>
  );
}
