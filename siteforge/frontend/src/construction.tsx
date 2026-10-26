import { FormEvent, useEffect, useState } from "react";
import {
  CalendarDays,
  CalendarRange,
  AlertTriangle,
  ClipboardCheck,
  FolderCheck,
  ClipboardList,
  Cog,
  HardHat,
  LayoutDashboard,
  Link2,
  ListTree,
  Lock,
  Package,
  Ruler,
  ShieldAlert,
  Users,
} from "lucide-react";
import { api } from "./api";
import { RouteLockNotice, routeLocked, useSavedRoutes } from "./approval_levels";
import type { Page, Project, Session } from "./types";

function Err({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}

const TABS = ["Dashboard", "Templates", "Work packages", "Readiness", "Daily progress", "Connections", "Monitoring", "Material balance", "Handover", "Activities", "Later steps"] as const;
const TAB_ICON = {
  Dashboard: LayoutDashboard,
  Templates: Ruler,
  "Work packages": HardHat,
  Readiness: ClipboardCheck,
  "Daily progress": CalendarDays,
  Connections: Link2,
  Monitoring: AlertTriangle,
  "Material balance": Package,
  Handover: FolderCheck,
  Activities: ListTree,
  "Later steps": Lock,
};
const TAB_TONE = {
  Dashboard: "tone-cdash",
  Templates: "tone-ctpl",
  "Work packages": "tone-cpack",
  Readiness: "tone-cready",
  "Daily progress": "tone-cprog",
  Connections: "tone-clink",
  Monitoring: "tone-cmon",
  "Material balance": "tone-cpack",
  Handover: "tone-chover",
  Activities: "tone-cact",
  "Later steps": "tone-later",
};

type Summary = {
  packages_draft: number;
  templates: number;
  activities: number;
  items: number;
  note: string;
  closed: string[];
};
type Sources = {
  disciplines: { id: number; name: string }[];
  areas: { id: number; code: string; name: string; area_type: string }[];
  companies: { id: number; name: string }[];
  members: { id: number; name: string }[];
  revisions: { id: number; label: string }[];
  requirements: { id: number; number: string }[];
};
type Template = {
  id: number;
  discipline_id: number;
  discipline_name: string;
  code: string;
  name: string;
  unit: string;
  prerequisites: string;
  required_evidence: string;
  checkpoints: string[];
  progress_method: string;
  completion_conditions: string;
  active: boolean;
  version: number;
};
type Package = {
  id: number;
  code: string;
  name: string;
  discipline_id: number;
  discipline_name: string;
  area_id: number;
  area_name: string;
  scope_description: string;
  company_id: number;
  company_name: string;
  responsible_user_id: number | null;
  responsible_name: string;
  supervisor_user_id: number | null;
  supervisor_name: string;
  priority: string;
  planning_reference: string;
  planned_start: string | null;
  planned_finish: string | null;
  remarks: string;
  status: string;
  release_state: string;
  cancellation_reason: string;
  impact_state: string;
  impact_detail: string;
  impact_revision_id: number | null;
  revision_ids: number[];
  revisions: { id: number; label: string }[];
  requirement_ids: number[];
  requirements: { id: number; number: string }[];
  activity_count: number;
  version: number;
  release_open: boolean;
};
type Activity = {
  id: number;
  package_id: number;
  package_code: string;
  template_id: number | null;
  code: string;
  name: string;
  description: string;
  baseline_quantity: string;
  quantity: string;
  unit: string;
  company_id: number;
  company_name: string;
  responsible_user_id: number | null;
  drawing_revision_id: number | null;
  drawing_label: string;
  predecessor_ids: number[];
  measurement_method: string;
  progress_weight: string | null;
  target_start: string | null;
  target_finish: string | null;
  active: boolean;
  version: number;
  scope_changes: { previous_quantity: string; new_quantity: string; reason: string }[];
  progress_note: string;
};
type WorkItem = {
  id: number;
  activity_id: number;
  activity_code: string;
  identifier: string;
  description: string;
  item_kind: string;
  quantity: string | null;
  active: boolean;
};

const DISCIPLINE_CLASS: Record<string, string> = {
  Civil: "fn-client",
  Mechanical: "fn-pmc",
  Electrical: "fn-procurement",
  Instrumentation: "fn-project-manager",
  Piping: "fn-stores",
};

export function ConstructionHome({
  session,
  initialProjectId = null,
}: {
  session: Session;
  initialProjectId?: number | null;
}) {
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
        <ConstructionBoard pid={pid} session={session} />
      </>
    );
  }
  return (
    <section className="panel">
      <h2>Construction</h2>
      <p className="muted">Open a project to keep its work packages, activity templates, and work items.</p>
      <Err text={error} />
      {projects.map((project) => (
        <button key={project.id} onClick={() => setPid(project.id || null)}>
          {project.code} · {project.name}
        </button>
      ))}
    </section>
  );
}

function ConstructionBoard({ pid, session }: { pid: number; session: Session }) {
  const canEdit =
    session.user.organization_admin ||
    session.memberships.some(
      (item) => item.project_id === pid && item.permissions?.includes("construction.edit"),
    );
  const [tab, setTab] = useState<(typeof TABS)[number]>("Dashboard");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sources, setSources] = useState<Sources | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [packages, setPackages] = useState<Package[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [items, setItems] = useState<WorkItem[]>([]);

  async function load() {
    const [board, ctx, templateRows, packageRows, activityRows, itemRows] = await Promise.all([
      api<Summary>(`/projects/${pid}/construction/summary`),
      api<Sources>(`/projects/${pid}/construction/sources`),
      api<Template[]>(`/projects/${pid}/construction/templates`),
      api<Package[]>(`/projects/${pid}/construction/packages`),
      api<Activity[]>(`/projects/${pid}/construction/activities`),
      api<WorkItem[]>(`/projects/${pid}/construction/items`),
    ]);
    setSummary(board);
    setSources(ctx);
    setTemplates(templateRows);
    setPackages(packageRows);
    setActivities(activityRows);
    setItems(itemRows);
  }

  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);

  return (
    <>
      <h2>Construction</h2>
      <p className="muted">
        Work packages, activity templates, and work items are stored here. Daily progress is recorded after work has started. A posted stores issue can be named on a line. Approving a report verifies the quantity. An approved handover dossier marks the package handed over. Quality records acceptance.
      </p>
      <Err text={error} />
      {note ? <p className="note-card note-good">{note}</p> : null}
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
      {tab === "Dashboard" && summary && (
        <section className="panel">
          <div className="dash-grid">
            <button type="button" className="dash-card const-pack" onClick={() => setTab("Work packages")}>
              <span className="dash-mark"><HardHat size={15} strokeWidth={2.4} /></span>
              <strong>{summary.packages_draft}</strong>
              <span className="dash-label">Draft packages</span>
            </button>
            <button type="button" className="dash-card const-template" onClick={() => setTab("Templates")}>
              <span className="dash-mark"><Ruler size={15} strokeWidth={2.4} /></span>
              <strong>{summary.templates}</strong>
              <span className="dash-label">Activity templates</span>
            </button>
            <button type="button" className="dash-card const-activity" onClick={() => setTab("Activities")}>
              <span className="dash-mark"><ListTree size={15} strokeWidth={2.4} /></span>
              <strong>{summary.activities}</strong>
              <span className="dash-label">Activities</span>
            </button>
            <button type="button" className="dash-card const-item" onClick={() => setTab("Activities")}>
              <span className="dash-mark"><ClipboardList size={15} strokeWidth={2.4} /></span>
              <strong>{summary.items}</strong>
              <span className="dash-label">Work items</span>
            </button>
            <button type="button" className="dash-card const-progress" onClick={() => setTab("Daily progress")}>
              <span className="dash-mark"><CalendarDays size={15} strokeWidth={2.4} /></span>
              <strong>Open</strong>
              <span className="dash-label">Daily progress</span>
            </button>
            <button type="button" className="dash-card const-link" onClick={() => setTab("Connections")}>
              <span className="dash-mark"><Link2 size={15} strokeWidth={2.4} /></span>
              <strong>Open</strong>
              <span className="dash-label">Connections</span>
            </button>
            <button type="button" className="dash-card const-mon" onClick={() => setTab("Monitoring")}>
              <span className="dash-mark"><AlertTriangle size={15} strokeWidth={2.4} /></span>
              <strong>Open</strong>
              <span className="dash-label">Monitoring</span>
            </button>
            <button type="button" className="dash-card const-hand" onClick={() => setTab("Handover")}>
              <span className="dash-mark"><FolderCheck size={15} strokeWidth={2.4} /></span>
              <strong>Open</strong>
              <span className="dash-label">Handover</span>
            </button>
            <button type="button" className="dash-card const-ready" onClick={() => setTab("Readiness")}>
              <span className="dash-mark"><ClipboardCheck size={15} strokeWidth={2.4} /></span>
              <strong>{packages.filter((row) => row.status !== "Cancelled").length}</strong>
              <span className="dash-label">Release board</span>
            </button>
          </div>
          <p className="note-card">{summary.note}</p>
        </section>
      )}
      {tab === "Templates" && sources && (
        <Templates
          pid={pid}
          canEdit={canEdit}
          sources={sources}
          rows={templates}
          onSaved={async (message) => {
            setNote(message);
            await load();
          }}
          onError={setError}
        />
      )}
      {tab === "Work packages" && sources && (
        <Packages
          pid={pid}
          canEdit={canEdit}
          sources={sources}
          rows={packages}
          onSaved={async (message) => {
            setNote(message);
            await load();
          }}
          onError={setError}
        />
      )}
      {tab === "Activities" && sources && (
        <Activities
          pid={pid}
          canEdit={canEdit}
          sources={sources}
          packages={packages.filter((row) => row.status === "Draft" && row.release_state !== "In Review")}
          templates={templates.filter((row) => row.active)}
          rows={activities}
          items={items}
          onSaved={async (message) => {
            setNote(message);
            await load();
          }}
          onError={setError}
        />
      )}
      {tab === "Readiness" && sources && (
        <Readiness
          pid={pid}
          session={session}
          canEdit={canEdit}
          sources={sources}
          onSaved={async (message) => {
            setNote(message);
            await load();
          }}
          onError={setError}
        />
      )}
      {tab === "Daily progress" && sources && (
        <DailyProgress
          pid={pid}
          session={session}
          canEdit={canEdit}
          sources={sources}
          onSaved={async (message) => {
            setNote(message);
            await load();
          }}
          onError={setError}
        />
      )}
      {tab === "Connections" && <Connections pid={pid} onError={setError} />}
      {tab === "Monitoring" && sources && (
        <Monitoring
          pid={pid}
          canEdit={canEdit}
          sources={sources}
          onSaved={async (message) => {
            setNote(message);
            await load();
          }}
          onError={setError}
        />
      )}
      {tab === "Material balance" && <ConstructionMaterialBalance pid={pid} />}
      {tab === "Handover" && sources && (
        <Handover
          pid={pid}
          session={session}
          canEdit={canEdit}
          sources={sources}
          onSaved={async (message) => {
            setNote(message);
            await load();
          }}
          onError={setError}
        />
      )}
      {tab === "Later steps" && (
        <section className="panel">
          <h3>These steps stay closed</h3>
          <ul className="closed-steps">
            {(summary?.closed || []).map((name) => (
              <li key={name}>
                <Lock size={14} /> {name}
              </li>
            ))}
          </ul>
          <p className="muted">
            Quality plans and inspection offers are in Quality. Permits and isolations are in Safety. A handover dossier records verified quantity and does not create a commissioning test. Schedule baselines, attendance, and billing certification stay closed.
          </p>
        </section>
      )}
    </>
  );
}


type ConstructionBalanceRow = {
  handover_id: number; work_package_id: number | null; item_id: number; unit: string;
  issued_quantity: string; ledger_posted_return_quantity: string;
  ledger_outstanding_quantity: string; pending_custody_return_quantity: string;
  verified_consumed_quantity: string; verified_installed_quantity: string;
  pending_qa_consumed_quantity: string; pending_qa_installed_quantity: string;
  rejected_evidence_quantity: string; unallocated_outstanding_quantity: string;
  physical_inventory_verified: boolean; coverage: string;
};
type ConstructionBalanceData = {
  records: ConstructionBalanceRow[]; coverage: string; inventory_verified: boolean; as_of: string;
};

/** Construction-authorized cross-request view: never use the requester-scoped Stores endpoint. */
function ConstructionMaterialBalance({ pid }: { pid: number }) {
  const [packageId, setPackageId] = useState("");
  const [data, setData] = useState<ConstructionBalanceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  async function reload(filter: string) {
    const trimmed = filter.trim();
    if (trimmed && (!/^\d+$/.test(trimmed) || !Number.isSafeInteger(Number(trimmed)) || Number(trimmed) <= 0)) {
      setData(null); setError("Enter a positive work-package ID."); return;
    }
    setData(null); setSelected(null); setError(""); setLoading(true);
    try {
      const suffix = trimmed ? `?work_package_id=${encodeURIComponent(trimmed)}` : "";
      const result = await api<ConstructionBalanceData>(`/projects/${pid}/stores/phase5/construction-manager-material-balance${suffix}`);
      if (!result || !Array.isArray(result.records) || result.inventory_verified !== false) {
        throw new Error("Unexpected material balance response; cannot display verified stock figures.");
      }
      setData(result);
    } catch (err) { setError((err as Error).message); }
    finally { setLoading(false); }
  }
  useEffect(() => { void reload(""); }, [pid]);
  const filtered = data?.records ?? [];
  const decimal = (value: string) => {
    const n = Number(value);
    return Number.isFinite(n) ? n.toLocaleString(undefined, {maximumFractionDigits: 3}) : "Invalid";
  };
  const selectedRows = filtered.filter(row => row.work_package_id === selected);
  return <section className="panel" aria-label="Construction material balance">
    <h3>Construction material balance</h3>
    <p className="muted">Read-only, across authorized project work packages. Quantities come from exact, request-linked issues and QA-reviewed usage. They are not physical stock availability or certified progress.</p>
    <div className="note-card" role="status">Physical inventory: <strong>Unverified</strong>. Historical unmapped movements are not included. No stock posting or construction progress is performed here.</div>
    <form onSubmit={e => { e.preventDefault(); void reload(packageId); }} className="form-row">
      <label>Work-package ID (optional) <input aria-label="Filter work package ID" type="number" min="1" value={packageId} onChange={e=>setPackageId(e.target.value)} placeholder="All authorized work packages" /></label>
      <button type="submit" disabled={loading}>{loading ? "Loading…" : "Refresh balances"}</button>
    </form>
    <Err text={error} />
    {loading && <p role="status">Loading material balances…</p>}
    {data && <>
      <p className="muted">Coverage: {data.coverage}. As of {new Date(data.as_of).toLocaleString()}.</p>
      {filtered.length === 0 ? <p>No material issue records match the current work-package filter.</p> : <>
        <p className="muted">{filtered.length} issue handovers in scope. Quantities are shown per item and unit; unlike units are never added together.</p>
        <div style={{overflowX:"auto"}}><table className="data-table"><thead><tr><th>Work package</th><th>Handover</th><th>Item</th><th>Issued</th><th>Posted return</th><th>Outstanding</th><th>Pending return</th><th>QA pending</th><th>Verified consumed</th><th>Verified installed</th><th>Unallocated</th></tr></thead><tbody>
          {filtered.map(row => <tr key={row.handover_id}>
            <td><button type="button" className="btn" onClick={()=>setSelected(row.work_package_id)}>{row.work_package_id ?? "Unassigned"}</button></td>
            <td>{row.handover_id}</td><td>{row.item_id}</td>
            {[row.issued_quantity,row.ledger_posted_return_quantity,row.ledger_outstanding_quantity,row.pending_custody_return_quantity,String(Number(row.pending_qa_consumed_quantity)+Number(row.pending_qa_installed_quantity)),row.verified_consumed_quantity,row.verified_installed_quantity,row.unallocated_outstanding_quantity].map((v,i)=><td key={i}>{decimal(v)} {row.unit}</td>)}
          </tr>)}
        </tbody></table></div>
        {selected !== null && <section className="note-card"><h4>Work package {selected}: issue trace</h4><p>{selectedRows.length} handover record(s). Read-only; open the Stores return and usage workflows for evidence and QA decisions.</p><button type="button" onClick={()=>setSelected(null)}>Close details</button></section>}
      </>}
    </>}
  </section>;
}

function Templates({
  pid,
  canEdit,
  sources,
  rows,
  onSaved,
  onError,
}: {
  pid: number;
  canEdit: boolean;
  sources: Sources;
  rows: Template[];
  onSaved: (message: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [form, setForm] = useState({
    discipline_id: sources.disciplines[0]?.id || 0,
    code: "",
    name: "",
    unit: "",
    prerequisites: "",
    required_evidence: "",
    checkpoints: "",
    progress_method: "Quantity",
    completion_conditions: "",
  });
  async function addExamples() {
    try {
      const saved = await api<{ added: number }>(`/projects/${pid}/construction/templates/examples`, "POST");
      await onSaved(
        saved.added
          ? `${saved.added} standard activities added. Each discipline keeps its own checkpoints.`
          : "Standard activities are already on this project.",
      );
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    const checkpoints = form.checkpoints.split(",").map((item) => item.trim()).filter(Boolean);
    try {
      await api(`/projects/${pid}/construction/templates`, "POST", { ...form, checkpoints });
      await onSaved("Template saved for this discipline.");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <div className="inline">
        <h3>Activity templates</h3>
        {canEdit ? (
          <button type="button" onClick={() => void addExamples()}>
            Add standard activities
          </button>
        ) : null}
      </div>
      <p className="muted">Civil, mechanical, electrical, instrumentation, and piping each keep their own checkpoints.</p>
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void save(event)}>
          <label>
            Discipline
            <select
              value={form.discipline_id}
              onChange={(event) => setForm({ ...form, discipline_id: Number(event.target.value) })}
            >
              {sources.disciplines.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Code
            <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} required />
          </label>
          <label>
            Name
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
          </label>
          <label>
            Unit
            <input value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} required />
          </label>
          <label>
            Measurement
            <select value={form.progress_method} onChange={(event) => setForm({ ...form, progress_method: event.target.value })}>
              <option>Quantity</option>
              <option>Item completion</option>
              <option>Weighted milestones</option>
            </select>
          </label>
          <label className="wide">
            Checkpoints, separated by commas
            <input value={form.checkpoints} onChange={(event) => setForm({ ...form, checkpoints: event.target.value })} required />
          </label>
          <label className="wide">
            Completion condition
            <input value={form.completion_conditions} onChange={(event) => setForm({ ...form, completion_conditions: event.target.value })} />
          </label>
          <button className="primary" type="submit">Save template</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {rows.map((row) => (
          <article key={row.id} className={`contact-card ${DISCIPLINE_CLASS[row.discipline_name] || "fn-other"}`}>
            <header>
              <span className={`fn-chip ${DISCIPLINE_CLASS[row.discipline_name] || "fn-other"}`}>{row.discipline_name}</span>
              <span className={row.active ? "state-active" : "state-inactive"}>{row.active ? "Active" : "Inactive"}</span>
            </header>
            <h4>{row.code} · {row.name}</h4>
            <p>{row.unit} · {row.progress_method}</p>
            <p>{row.checkpoints.join(" · ")}</p>
            <p className="muted">{row.completion_conditions}</p>
          </article>
        ))}
      </div>
      {rows.length === 0 ? <p className="muted">No activity templates yet.</p> : null}
    </section>
  );
}

function Packages({
  pid,
  canEdit,
  sources,
  rows,
  onSaved,
  onError,
}: {
  pid: number;
  canEdit: boolean;
  sources: Sources;
  rows: Package[];
  onSaved: (message: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [form, setForm] = useState({
    code: "",
    name: "",
    discipline_id: sources.disciplines[0]?.id || 0,
    area_id: sources.areas[0]?.id || 0,
    scope_description: "",
    company_id: sources.companies[0]?.id || 0,
    responsible_user_id: 0,
    supervisor_user_id: 0,
    priority: "Normal",
    planning_reference: "",
    planned_start: "",
    planned_finish: "",
    remarks: "",
    revision_id: 0,
    requirement_id: 0,
  });
  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      await api(`/projects/${pid}/construction/packages`, "POST", {
        code: form.code,
        name: form.name,
        discipline_id: form.discipline_id,
        area_id: form.area_id,
        scope_description: form.scope_description,
        company_id: form.company_id,
        responsible_user_id: form.responsible_user_id || null,
        supervisor_user_id: form.supervisor_user_id || null,
        priority: form.priority,
        planning_reference: form.planning_reference,
        planned_start: form.planned_start || null,
        planned_finish: form.planned_finish || null,
        remarks: form.remarks,
        revision_ids: form.revision_id ? [form.revision_id] : [],
        requirement_ids: form.requirement_id ? [form.requirement_id] : [],
      });
      await onSaved("Work package saved as Draft. Release stays closed.");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3>Work package register</h3>
      <p className="muted">
        A package belongs to one discipline and one location. Naming a supervisor does not grant access. Release stays closed.
      </p>
      {canEdit ? (
        sources.areas.length === 0 ? (
          <p className="muted">Add a unit, area, or block on the project before creating a work package.</p>
        ) : (
          <form className="contact-form" onSubmit={(event) => void save(event)}>
            <label>
              Code
              <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} required />
            </label>
            <label>
              Name
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
            </label>
            <label>
              Discipline
              <select value={form.discipline_id} onChange={(event) => setForm({ ...form, discipline_id: Number(event.target.value) })}>
                {sources.disciplines.map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              Location
              <select value={form.area_id} onChange={(event) => setForm({ ...form, area_id: Number(event.target.value) })}>
                {sources.areas.map((row) => (
                  <option key={row.id} value={row.id}>{row.area_type} {row.code} · {row.name}</option>
                ))}
              </select>
            </label>
            <label>
              Company
              <select value={form.company_id} onChange={(event) => setForm({ ...form, company_id: Number(event.target.value) })}>
                {sources.companies.map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              Priority
              <select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>
                <option>Normal</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </label>
            <label>
              Responsible engineer
              <select value={form.responsible_user_id} onChange={(event) => setForm({ ...form, responsible_user_id: Number(event.target.value) })}>
                <option value={0}>Not assigned yet</option>
                {sources.members.map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              Supervisor
              <select value={form.supervisor_user_id} onChange={(event) => setForm({ ...form, supervisor_user_id: Number(event.target.value) })}>
                <option value={0}>No supervisor</option>
                {sources.members.map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label className="wide">
              Scope
              <input value={form.scope_description} onChange={(event) => setForm({ ...form, scope_description: event.target.value })} required />
            </label>
            <label>
              Planning reference
              <input value={form.planning_reference} onChange={(event) => setForm({ ...form, planning_reference: event.target.value })} />
            </label>
            <label>
              Planned start
              <input type="date" value={form.planned_start} onChange={(event) => setForm({ ...form, planned_start: event.target.value })} />
            </label>
            <label>
              Planned finish
              <input type="date" value={form.planned_finish} onChange={(event) => setForm({ ...form, planned_finish: event.target.value })} />
            </label>
            <label>
              Released drawing
              <select value={form.revision_id} onChange={(event) => setForm({ ...form, revision_id: Number(event.target.value) })}>
                <option value={0}>None</option>
                {sources.revisions.map((row) => (
                  <option key={row.id} value={row.id}>{row.label}</option>
                ))}
              </select>
            </label>
            <label>
              Material requirement
              <select value={form.requirement_id} onChange={(event) => setForm({ ...form, requirement_id: Number(event.target.value) })}>
                <option value={0}>None</option>
                {sources.requirements.map((row) => (
                  <option key={row.id} value={row.id}>{row.number}</option>
                ))}
              </select>
            </label>
            <button className="primary" type="submit">Save draft package</button>
          </form>
        )
      ) : null}
      <div className="contact-grid">
        {rows.map((row) => (
          <article key={row.id} className={`contact-card ${DISCIPLINE_CLASS[row.discipline_name] || "fn-other"}`}>
            <header>
              <span className={`fn-chip ${DISCIPLINE_CLASS[row.discipline_name] || "fn-other"}`}>{row.discipline_name}</span>
              <span className={row.status === "Draft" ? "state-clear" : "state-also"}>{row.status}</span>
              <span className={`rel-chip rel-${row.release_state.replaceAll(" ", "-").toLowerCase()}`}>{row.release_state}</span>
            </header>
            <h4>{row.code} · {row.name}</h4>
            {row.impact_state === "Review required" ? (
              <p className="note-card note-alert">Drawing impact review: {row.impact_detail}</p>
            ) : null}
            <p>{row.area_name}</p>
            <p>{row.company_name} · {row.priority}</p>
            <p>{row.scope_description}</p>
            <p>{row.responsible_name || "Engineer not assigned"}</p>
            <p>{row.supervisor_name ? `Supervisor: ${row.supervisor_name}` : "No supervisor"}</p>
            <p>{row.activity_count} activities</p>
            {row.revisions.map((revision) => (
              <p key={revision.id}>Drawing {revision.label}</p>
            ))}
            {row.requirements.map((requirement) => (
              <p key={requirement.id}>Requirement {requirement.number}</p>
            ))}
            {canEdit && row.status === "Draft" && row.release_state !== "In Review" ? (
              <button
                type="button"
                onClick={() => {
                  const reason = window.prompt("Reason for cancelling this draft");
                  if (!reason) return;
                  void api(`/projects/${pid}/construction/packages/${row.id}/cancel`, "POST", {
                    reason,
                    version: row.version,
                  })
                    .then(() => onSaved("Draft cancelled. Release was not opened."))
                    .catch((err) => onError((err as Error).message));
                }}
              >
                Cancel draft
              </button>
            ) : null}
          </article>
        ))}
      </div>
      {rows.length === 0 ? <p className="muted">No work packages yet.</p> : null}
    </section>
  );
}

function Activities({
  pid,
  canEdit,
  sources,
  packages,
  templates,
  rows,
  items,
  onSaved,
  onError,
}: {
  pid: number;
  canEdit: boolean;
  sources: Sources;
  packages: Package[];
  templates: Template[];
  rows: Activity[];
  items: WorkItem[];
  onSaved: (message: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [form, setForm] = useState({
    package_id: packages[0]?.id || 0,
    template_id: 0,
    code: "",
    name: "",
    quantity: "",
    unit: "",
    company_id: sources.companies[0]?.id || 0,
    measurement_method: "Quantity",
    item_identifier: "",
    item_kind: "Other",
  });
  const packageTemplates = templates.filter((row) => {
    const pack = packages.find((item) => item.id === form.package_id);
    return pack && row.discipline_id === pack.discipline_id;
  });
  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      const activity = await api<Activity>(`/projects/${pid}/construction/activities`, "POST", {
        package_id: form.package_id,
        template_id: form.template_id || null,
        code: form.code,
        name: form.name,
        quantity: form.quantity,
        unit: form.unit,
        company_id: form.company_id,
        measurement_method: form.measurement_method,
        predecessor_ids: [],
      });
      if (form.item_identifier) {
        await api(`/projects/${pid}/construction/items`, "POST", {
          activity_id: activity.id,
          identifier: form.item_identifier,
          item_kind: form.item_kind,
          description: form.name,
        });
      }
      await onSaved("Activity saved. The first quantity is the baseline. Progress is not calculated yet.");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel">
      <h3>Activities and work items</h3>
      <p className="muted">
        The baseline quantity stays when the scope changes. Reported, verified, accepted, and certified quantities are not calculated yet.
      </p>
      {canEdit && packages.length > 0 ? (
        <form className="contact-form" onSubmit={(event) => void save(event)}>
          <label>
            Work package
            <select value={form.package_id} onChange={(event) => setForm({ ...form, package_id: Number(event.target.value), template_id: 0 })}>
              {packages.map((row) => (
                <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Template
            <select value={form.template_id} onChange={(event) => {
              const template = packageTemplates.find((row) => row.id === Number(event.target.value));
              setForm({
                ...form,
                template_id: Number(event.target.value),
                code: template?.code || form.code,
                name: template?.name || form.name,
                unit: template?.unit || form.unit,
                measurement_method: template?.progress_method || form.measurement_method,
              });
            }}>
              <option value={0}>No template</option>
              {packageTemplates.map((row) => (
                <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Code
            <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} required />
          </label>
          <label>
            Name
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
          </label>
          <label>
            Baseline quantity
            <input value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} required />
          </label>
          <label>
            Unit
            <input value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} required />
          </label>
          <label>
            Company
            <select value={form.company_id} onChange={(event) => setForm({ ...form, company_id: Number(event.target.value) })}>
              {sources.companies.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Measurement
            <select value={form.measurement_method} onChange={(event) => setForm({ ...form, measurement_method: event.target.value })}>
              <option>Quantity</option>
              <option>Item completion</option>
              <option>Weighted milestones</option>
            </select>
          </label>
          <label>
            Work item
            <input value={form.item_identifier} placeholder="Optional tag" onChange={(event) => setForm({ ...form, item_identifier: event.target.value })} />
          </label>
          <label>
            Item kind
            <select value={form.item_kind} onChange={(event) => setForm({ ...form, item_kind: event.target.value })}>
              {["Pile", "Foundation", "Equipment", "Cable", "Instrument", "Spool", "Joint", "Other"].map((kind) => (
                <option key={kind}>{kind}</option>
              ))}
            </select>
          </label>
          <button className="primary" type="submit">Save activity</button>
        </form>
      ) : null}
      {canEdit && packages.length === 0 ? <p className="muted">Save a draft work package before adding an activity.</p> : null}
      <div className="contact-grid">
        {rows.map((row) => (
          <article key={row.id} className="contact-card fn-discipline">
            <header>
              <span className="fn-chip fn-discipline">{row.package_code}</span>
              <span className={row.active ? "state-active" : "state-inactive"}>{row.active ? "Active" : "Inactive"}</span>
            </header>
            <h4>{row.code} · {row.name}</h4>
            <p>Baseline {row.baseline_quantity} {row.unit}</p>
            <p>Current scope {row.quantity} {row.unit}</p>
            <p>{row.measurement_method}</p>
            <p className="muted">{row.progress_note}</p>
            {row.scope_changes[0] ? <p>Last change: {row.scope_changes[0].reason}</p> : null}
            {items.filter((item) => item.activity_id === row.id).map((item) => (
              <p key={item.id}>{item.item_kind} {item.identifier}{item.active ? "" : " · Inactive"}</p>
            ))}
          </article>
        ))}
      </div>
    </section>
  );
}

const CHECK_TYPES = [
  "Drawing",
  "Material",
  "Material issue",
  "Predecessor",
  "Workfront",
  "Manpower",
  "Procedure",
  "Inspection",
  "Permit",
  "Quality hold",
];

type LiveState = "Ready" | "Blocked" | "Pending" | "Not Applicable";
type CheckRow = {
  id: number;
  check_type: string;
  classification: string;
  source_label: string;
  evidence: string;
  status: string;
  live_drawing: string | null;
  live_material: string | null;
  live_crew: string | null;
  live_state: LiveState;
  live_reason: string;
  live_owner: string;
  verified_by: string;
  version: number;
  manual: boolean;
};
type ReleaseReview = {
  id: number;
  state: string;
  version: number;
  actions: string[];
  subject: string;
};
type ReleaseCard = {
  package: Package;
  checks: CheckRow[];
  warnings: string[];
  problems: string[];
  review: ReleaseReview | null;
  snapshot: { manual_note?: string; activities?: { code: string; inspection_points: string[] }[] } | null;
  impact_choices: { id: number; code: string }[];
};

function checkClass(status: string) {
  if (status === "Satisfied" || status === "Ready" || status === "Not Applicable") return "chk-ok";
  if (status === "Blocked") return "chk-block";
  if (status === "Pending") return "chk-wait";
  return "chk-open";
}

function DrawingImpact({
  pid,
  card,
  canEdit,
  onDone,
  onError,
}: {
  pid: number;
  card: ReleaseCard;
  canEdit: boolean;
  onDone: (message: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [revisionId, setRevisionId] = useState(card.impact_choices[0]?.id ?? 0);
  const [reason, setReason] = useState("");
  if (card.package.impact_state !== "Review required") return null;
  async function resolve(action: "relink" | "accept") {
    onError("");
    try {
      await api(`/projects/${pid}/construction/packages/${card.package.id}/drawing-impact`, "POST", {
        version: card.package.version,
        action,
        revision_id: action === "relink" ? revisionId : null,
        reason,
      });
      setReason("");
      await onDone(action === "relink" ? "Package relinked to the released revision." : "Drawing impact accepted.");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <div className="note-card note-alert">
      <p>
        <strong>Drawing impact review.</strong> {card.package.impact_detail} Daily progress stays closed until the
        responsible engineer relinks or accepts it.
      </p>
      {canEdit ? (
        <div className="check-actions">
          <select value={revisionId} onChange={(event) => setRevisionId(Number(event.target.value))}>
            <option value={0}>Released revision</option>
            {card.impact_choices.map((row) => (
              <option key={row.id} value={row.id}>Rev {row.code}</option>
            ))}
          </select>
          <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Reason" />
          <button type="button" className="primary" disabled={!revisionId} onClick={() => void resolve("relink")}>
            Relink
          </button>
          <button type="button" onClick={() => void resolve("accept")}>Accept without change</button>
        </div>
      ) : null}
    </div>
  );
}

function HseWorkNote({ pid, packageId }: { pid: number; packageId: number }) {
  const [note, setNote] = useState<{
    note: string;
    permit_block?: string;
    field_block?: string;
    incident_note?: string;
    emergency_note?: string;
    environment_note?: string;
    hold_block?: string;
    assessments: { id: number; number: string; status: string }[];
    permits?: { id: number; number: string; status: string }[];
  } | null>(null);
  useEffect(() => {
    void api<{
      note: string;
      permit_block?: string;
      field_block?: string;
      incident_note?: string;
      emergency_note?: string;
      environment_note?: string;
      hold_block?: string;
      assessments: { id: number; number: string; status: string }[];
      permits?: { id: number; number: string; status: string }[];
    }>(`/projects/${pid}/hse/work?package_id=${packageId}`)
      .then(setNote)
      .catch(() => setNote(null));
  }, [pid, packageId]);
  if (!note) return null;
  const approved = note.assessments.filter((row) => row.status === "Approved").map((row) => row.number);
  const permits = (note.permits || []).map((row) => `${row.number} ${row.status}`);
  return (
    <p className="note-card">
      {approved.length ? `Approved assessments: ${approved.join(", ")}. ` : ""}
      {permits.length ? `Permits: ${permits.join(", ")}. ` : ""}
      {note.permit_block ? `${note.permit_block} ` : ""}
      {note.field_block ? `${note.field_block} ` : ""}
      {note.incident_note ? `${note.incident_note} ` : ""}
      {note.emergency_note ? `${note.emergency_note} ` : ""}
      {note.environment_note ? `${note.environment_note} ` : ""}
      {note.hold_block ? `${note.hold_block} ` : ""}
      {note.note}
    </p>
  );
}

function Readiness({
  pid,
  session,
  canEdit,
  sources,
  onSaved,
  onError,
}: {
  pid: number;
  session: Session;
  canEdit: boolean;
  sources: Sources;
  onSaved: (message: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [cards, setCards] = useState<ReleaseCard[]>([]);
  const [checkType, setCheckType] = useState("Drawing");
  const [classification, setClassification] = useState("Mandatory");
  const [packageId, setPackageId] = useState(0);
  const [reviewerId, setReviewerId] = useState(0);
  const [disciplineId, setDisciplineId] = useState(0);
  const [reason, setReason] = useState("");
  const releaseRoutes = useSavedRoutes(pid, "construction.release", session.user.organization_admin);
  const releaseLocked = routeLocked(releaseRoutes, disciplineId || null);

  async function loadCards() {
    setCards(await api<ReleaseCard[]>(`/projects/${pid}/construction/readiness`));
  }

  useEffect(() => {
    void loadCards().catch((err) => onError((err as Error).message));
  }, [pid]);

  const editable = cards.filter(
    (card) => card.package.status === "Draft" && card.package.release_state !== "In Review",
  );

  async function savePolicy(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/approval-policies`, "POST", {
        record_type: "construction.release",
        company_id: null,
        discipline_id: disciplineId || null,
        allow_self_approval: false,
        stages: [
          {
            name: "Construction release",
            rule: "all",
            quorum_count: 1,
            reviewer_ids: [reviewerId],
            reviewers: [],
            purpose: "Release this work package",
          },
        ],
      });
      await onSaved("Release route saved. Only this reviewer can approve it.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function addCheck(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/construction/packages/${packageId}/checks`, "POST", {
        check_type: checkType,
        classification,
      });
      await loadCards();
      await onSaved("Readiness check added. It starts as Not Checked.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function setStatus(card: ReleaseCard, check: CheckRow, status: string, evidence: string) {
    onError("");
    try {
      await api(
        `/projects/${pid}/construction/packages/${card.package.id}/checks/${check.id}`,
        "PUT",
        { status, evidence, version: check.version },
      );
      await loadCards();
      await onSaved(`${check.check_type} is ${status}.`);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function release(card: ReleaseCard) {
    onError("");
    try {
      const view = await api<ReleaseCard>(
        `/projects/${pid}/construction/packages/${card.package.id}/release`,
        "POST",
        { version: card.package.version },
      );
      await loadCards();
      const warning = view.warnings.length ? ` Advisory: ${view.warnings.join(", ")}.` : "";
      await onSaved(`Release sent for review.${warning}`);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function resubmit(card: ReleaseCard) {
    onError("");
    try {
      await api(`/projects/${pid}/construction/packages/${card.package.id}/resubmit`, "POST", {
        version: card.package.version,
      });
      await loadCards();
      await onSaved("Release resubmitted.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function start(card: ReleaseCard) {
    onError("");
    try {
      await api(`/projects/${pid}/construction/packages/${card.package.id}/start`, "POST", {
        version: card.package.version,
      });
      await loadCards();
      await onSaved("Work started. Daily progress is still closed.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function decide(card: ReleaseCard, action: string) {
    if (!card.review) return;
    onError("");
    try {
      await api(`/reviews/${card.review.id}/decisions`, "POST", {
        action,
        reason: action === "approve" ? "" : reason,
        comment: "",
        version: card.review.version,
      });
      setReason("");
      await loadCards();
      await onSaved(action === "approve" ? "Work package released." : `Release ${action}ed.`);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  return (
    <section className="panel">
      <h3>Readiness and release</h3>
      <p className="muted">
        Add the checks that apply. A mandatory check must be Ready before release and start. An advisory check only warns.
        Drawing, Material, Material issue, Manpower, Permit, and Quality hold are read from the owning module each time: a released drawing, stock reserved or issued for this package, confirmed Manpower assignments, an active permit with no safety hold, and no quality hold. A typed note does not make them ready. Other checks are manual evidence; only those can be marked Not applicable, with a reason. Manual evidence does not create an inspection, a permit, or a schedule.
      </p>
      {session.user.organization_admin ? (
        <form className="contact-form" onSubmit={(event) => void savePolicy(event)}>
          <h4>Release route</h4>
          <p className="muted">One saved stage runs. The reviewer must already be a project member. An administrator is not an automatic reviewer.</p>
          <label>
            Discipline
            <select value={disciplineId} onChange={(event) => setDisciplineId(Number(event.target.value))}>
              <option value={0}>All disciplines on this project</option>
              {sources.disciplines.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          {releaseLocked ? (
            <RouteLockNotice target={{ projectId: pid, recordType: "construction.release", disciplineId: disciplineId || null }} />
          ) : null}
          <label>
            Reviewer
            <select value={reviewerId} disabled={releaseLocked} onChange={(event) => setReviewerId(Number(event.target.value))} required>
              <option value={0}>Select a project member</option>
              {sources.members.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <button className="primary" type="submit" disabled={releaseLocked || !reviewerId}>Save release route</button>
        </form>
      ) : null}
      {canEdit && editable.length > 0 ? (
        <form className="contact-form" onSubmit={(event) => void addCheck(event)}>
          <label>
            Work package
            <select value={packageId} onChange={(event) => setPackageId(Number(event.target.value))} required>
              <option value={0}>Select a draft package</option>
              {editable.map((card) => (
                <option key={card.package.id} value={card.package.id}>
                  {card.package.code} · {card.package.release_state}
                </option>
              ))}
            </select>
          </label>
          <label>
            Check
            <select value={checkType} onChange={(event) => setCheckType(event.target.value)}>
              {CHECK_TYPES.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Weight
            <select value={classification} onChange={(event) => setClassification(event.target.value)}>
              <option>Mandatory</option>
              <option>Advisory</option>
            </select>
          </label>
          <button className="primary" type="submit" disabled={!packageId}>Add check</button>
        </form>
      ) : null}
      {cards.length === 0 ? <p className="muted">No work package is waiting here yet.</p> : null}
      <div className="contact-grid">
        {cards.map((card) => (
          <article key={card.package.id} className="contact-card release-card">
            <header>
              <span className={`fn-chip ${DISCIPLINE_CLASS[card.package.discipline_name] || "fn-other"}`}>
                {card.package.discipline_name}
              </span>
              <span className={`rel-chip rel-${card.package.release_state.replaceAll(" ", "-").toLowerCase()}`}>
                {card.package.release_state}
              </span>
            </header>
            <h4>{card.package.code} · {card.package.status}</h4>
            <p>{card.package.responsible_name || "Engineer required before release"}</p>
            <p>
              {card.package.planned_start || "Start not set"} → {card.package.planned_finish || "Finish not set"}
            </p>
            <DrawingImpact
              pid={pid}
              card={card}
              canEdit={canEdit}
              onError={onError}
              onDone={async (message) => {
                await loadCards();
                await onSaved(message);
              }}
            />
            {card.checks.map((check) => (
              <div key={check.id} className={`check-row ${checkClass(check.manual ? check.status : check.live_state)}`}>
                <strong>{check.check_type}</strong>
                <span>{check.classification}</span>
                <span>{check.manual ? check.status : check.live_state}</span>
                <p>
                  {check.live_owner}: {check.manual ? check.source_label : check.live_reason}
                </p>
                {check.verified_by ? <p>Verified by {check.verified_by}</p> : null}
                {canEdit && card.package.status === "Draft" && card.package.release_state !== "In Review" ? (
                  <CheckActions check={check} onSet={(status, evidence) => void setStatus(card, check, status, evidence)} />
                ) : null}
              </div>
            ))}
            {card.warnings.map((warning) => (
              <p key={warning} className="note-card">Advisory: {warning}</p>
            ))}
            {card.problems.map((problem) => (
              <p key={problem} className="muted">{problem}</p>
            ))}
            {card.snapshot?.activities?.length ? (
              <p className="muted">
                Stored scope keeps the baseline. Inspection names on that snapshot were not created as inspections.
                {card.snapshot.manual_note ? ` ${card.snapshot.manual_note}` : ""}
              </p>
            ) : null}
            <HseWorkNote pid={pid} packageId={card.package.id} />
            {canEdit && (card.package.release_state === "Not Submitted" || card.package.release_state === "Rejected") ? (
              <button type="button" className="primary" onClick={() => void release(card)}>Release for execution</button>
            ) : null}
            {canEdit && card.package.release_state === "Returned" ? (
              <button type="button" className="primary" onClick={() => void resubmit(card)}>Resubmit release</button>
            ) : null}
            {canEdit && card.package.status === "Ready" ? (
              <button type="button" className="primary" onClick={() => void start(card)}>Start work</button>
            ) : null}
            {card.review && card.review.actions.some((action) => action !== "comment" && action !== "resubmit") ? (
              <div className="check-actions">
                <input
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Reason for return or reject"
                />
                {card.review.actions.includes("approve") ? (
                  <button type="button" className="primary" onClick={() => void decide(card, "approve")}>Approve release</button>
                ) : null}
                {card.review.actions.includes("return") ? (
                  <button type="button" onClick={() => void decide(card, "return")}>Return</button>
                ) : null}
                {card.review.actions.includes("reject") ? (
                  <button type="button" onClick={() => void decide(card, "reject")}>Reject</button>
                ) : null}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function CheckActions({
  check,
  onSet,
}: {
  check: CheckRow;
  onSet: (status: string, evidence: string) => void;
}) {
  const [evidence, setEvidence] = useState(check.evidence);
  return (
    <div className="check-actions">
      {check.manual ? (
        <input value={evidence} onChange={(event) => setEvidence(event.target.value)} placeholder="Evidence" />
      ) : null}
      <button type="button" onClick={() => onSet("Pending", evidence)}>Pending</button>
      {check.manual || check.live_state === "Ready" ? (
        <button type="button" className="primary" onClick={() => onSet("Satisfied", evidence)}>Satisfied</button>
      ) : null}
      <button type="button" onClick={() => onSet("Blocked", evidence)}>Blocked</button>
      {check.manual ? (
        <button type="button" onClick={() => onSet("Not Applicable", evidence)}>Not applicable</button>
      ) : null}
    </div>
  );
}

type Measure = {
  activity_id: number;
  activity_code: string;
  package_code: string;
  package_status: string;
  method: string;
  scope_quantity: string | null;
  unit: string;
  reported_quantity: string | null;
  verified_quantity: string | null;
  rework_quantity: string;
  reported_percent: string | null;
  verified_percent: string | null;
  accepted_quantity: string | null;
  accepted_note: string;
  certified_note: string;
  milestones: { id: number; name: string; weight: string }[];
};
type StorePosting = {
  id: number;
  number: string;
  kind: string;
  status: string;
  quantity_label: string;
  note: string;
  lines: { item_code: string; item_name: string; quantity: string; unit: string }[];
};
type DailyLine = {
  id: number;
  activity_code: string;
  quantity: string | null;
  unit: string;
  rework: boolean;
  milestone_name: string;
  reverses_line_id: number | null;
  crew_reference: string;
  equipment_hours: string | null;
  source_note: string;
  stores: StorePosting | null;
  labour: LabourEntry[];
};
type LabourEntry = { id: number; personnel_id: number; person: string; productive: string; idle: string; idle_reason: string };
type LabourPerson = { id: number; name: string; company_id: number; windows: [string, string | null][] };
type DailyReview = { id: number; version: number; actions: string[] };
type DailyReport = {
  id: number;
  number: string;
  company_id: number;
  report_date: string;
  shift: string;
  discipline_name: string;
  area_name: string;
  status: string;
  version: number;
  site_engineer_name: string;
  lines: DailyLine[];
  warnings: string[];
  review: DailyReview | null;
};

function DailyProgress({
  pid,
  session,
  canEdit,
  sources,
  onSaved,
  onError,
}: {
  pid: number;
  session: Session;
  canEdit: boolean;
  sources: Sources;
  onSaved: (message: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [measures, setMeasures] = useState<Measure[]>([]);
  const [number, setNumber] = useState("");
  const [reportDate, setReportDate] = useState("");
  const [shift, setShift] = useState("Day");
  const [disciplineId, setDisciplineId] = useState(0);
  const [areaId, setAreaId] = useState(0);
  const [companyId, setCompanyId] = useState(0);
  const [engineerId, setEngineerId] = useState(0);
  const [reviewerId, setReviewerId] = useState(0);
  const [routeDiscipline, setRouteDiscipline] = useState(0);
  const [reportId, setReportId] = useState(0);
  const [activityId, setActivityId] = useState(0);
  const [quantity, setQuantity] = useState("");
  const [milestoneId, setMilestoneId] = useState(0);
  const [evidence, setEvidence] = useState("");
  const [rework, setRework] = useState(false);
  const [reason, setReason] = useState("");
  const [crew, setCrew] = useState("");
  const [equipmentHours, setEquipmentHours] = useState("");
  const [storesId, setStoresId] = useState(0);
  const [postings, setPostings] = useState<StorePosting[]>([]);
  const [labourPeople, setLabourPeople] = useState<LabourPerson[]>([]);
  const [labourNote, setLabourNote] = useState("");
  const progressRoutes = useSavedRoutes(pid, "construction.progress", session.user.organization_admin);
  const progressLocked = routeLocked(progressRoutes, routeDiscipline || null);

  async function loadBoard() {
    const [board, links] = await Promise.all([
      api<{ reports: DailyReport[]; activities: Measure[]; labour_people: LabourPerson[]; labour_note: string }>(`/projects/${pid}/construction/progress`),
      api<{ stores: { postings: StorePosting[] } }>(`/projects/${pid}/construction/connections`),
    ]);
    setReports(board.reports);
    setMeasures(board.activities);
    setLabourPeople(board.labour_people);
    setLabourNote(board.labour_note);
    setPostings(links.stores.postings);
  }

  async function labour(path: string, method: "POST" | "DELETE", body?: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/construction/progress/${path}`, method, body);
      await loadBoard();
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }

  useEffect(() => {
    void loadBoard().catch((err) => onError((err as Error).message));
  }, [pid]);

  const openReports = reports.filter((row) => row.status === "Draft" || row.status === "Returned for Correction");
  const started = measures.filter((row) => row.package_status === "In Progress");
  const chosen = started.find((row) => row.activity_id === activityId);

  async function saveRoute(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/approval-policies`, "POST", {
        record_type: "construction.progress",
        company_id: null,
        discipline_id: routeDiscipline || null,
        allow_self_approval: false,
        stages: [
          {
            name: "Quantity verification",
            rule: "all",
            quorum_count: 1,
            reviewer_ids: [reviewerId],
            reviewers: [],
            purpose: "Verify the executed quantity",
          },
        ],
      });
      await onSaved("Progress route saved. Only this reviewer can verify a report.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function saveReport(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/construction/progress`, "POST", {
        number,
        report_date: reportDate,
        shift,
        discipline_id: disciplineId,
        area_id: areaId,
        company_id: companyId,
        site_engineer_id: engineerId,
        weather: "",
        remarks: "",
      });
      setNumber("");
      await loadBoard();
      await onSaved("Daily report saved as a draft.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function addLine(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/construction/progress/${reportId}/lines`, "POST", {
        activity_id: activityId,
        milestone_id: chosen?.method === "Weighted milestones" ? milestoneId || null : null,
        quantity: chosen?.method === "Weighted milestones" ? null : quantity,
        evidence,
        rework,
        crew_reference: crew,
        equipment_hours: equipmentHours === "" ? null : equipmentHours,
        stock_posting_id: storesId || null,
      });
      setQuantity("");
      setEvidence("");
      setRework(false);
      setCrew("");
      setEquipmentHours("");
      setStoresId(0);
      await loadBoard();
      await onSaved("Work line added. A stores reference does not change the installed quantity.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function submit(report: DailyReport) {
    onError("");
    try {
      const view = await api<DailyReport>(`/projects/${pid}/construction/progress/${report.id}/submit`, "POST", {
        version: report.version,
      });
      await loadBoard();
      const warning = view.warnings.length ? ` ${view.warnings.join(" ")}` : "";
      await onSaved(`Daily report sent for verification.${warning}`);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function resubmit(report: DailyReport) {
    onError("");
    try {
      await api(`/projects/${pid}/construction/progress/${report.id}/resubmit`, "POST", { version: report.version });
      await loadBoard();
      await onSaved("Daily report resubmitted.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function decide(report: DailyReport, action: string) {
    if (!report.review) return;
    onError("");
    try {
      await api(`/reviews/${report.review.id}/decisions`, "POST", {
        action,
        reason: action === "approve" ? "" : reason,
        comment: "",
        version: report.review.version,
      });
      setReason("");
      await loadBoard();
      await onSaved(action === "approve" ? "Quantity verified. Quality acceptance was not granted." : `Report ${action}ed.`);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  return (
    <section className="panel">
      <h3>Daily progress</h3>
      <p className="muted">
        Enter the quantity executed on this report. Reported and verified totals are calculated from these lines.
        Approving a report verifies the quantity. It does not accept the work for quality or certify it for billing.
      </p>
      {labourNote ? <p className="note-card labour-note"><Users size={14} /> {labourNote}</p> : null}
      <div className="measure-grid">
        {measures.map((row) => (
          <article key={row.activity_id} className="measure-card">
            <header>
              <strong>{row.activity_code}</strong>
              <span>{row.package_code}</span>
            </header>
            <p>{row.method}</p>
            {row.scope_quantity ? <p>Scope {row.scope_quantity} {row.unit}</p> : <p>Scope is the milestone weight</p>}
            <p className="measure-reported">Reported {row.reported_percent ? `${row.reported_percent}%` : row.reported_quantity || "N/A"}</p>
            <p className="measure-verified">Verified {row.verified_percent ? `${row.verified_percent}%` : row.verified_quantity || "N/A"}</p>
            <p className={row.accepted_quantity ? "measure-verified" : "measure-closed"}>
              {row.accepted_quantity ? `Accepted ${row.accepted_quantity} ${row.unit}` : "Accepted: none recorded"}
            </p>
            <p className="measure-closed">Certified: not open</p>
            {row.rework_quantity !== "0.000" ? <p>Rework {row.rework_quantity} is recorded separately</p> : null}
          </article>
        ))}
      </div>
      {session.user.organization_admin ? (
        <form className="contact-form" onSubmit={(event) => void saveRoute(event)}>
          <h4>Verification route</h4>
          <p className="muted">The reviewer must already be a project member. An administrator is not an automatic verifier.</p>
          <label>
            Discipline
            <select value={routeDiscipline} onChange={(event) => setRouteDiscipline(Number(event.target.value))}>
              <option value={0}>All disciplines on this project</option>
              {sources.disciplines.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          {progressLocked ? (
            <RouteLockNotice target={{ projectId: pid, recordType: "construction.progress", disciplineId: routeDiscipline || null }} />
          ) : null}
          <label>
            Reviewer
            <select value={reviewerId} disabled={progressLocked} onChange={(event) => setReviewerId(Number(event.target.value))} required>
              <option value={0}>Select a project member</option>
              {sources.members.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <button className="primary" type="submit" disabled={progressLocked || !reviewerId}>Save verification route</button>
        </form>
      ) : null}
      {canEdit ? (
        <form className="contact-form" onSubmit={(event) => void saveReport(event)}>
          <h4>New daily report</h4>
          <label>
            Report number
            <input value={number} onChange={(event) => setNumber(event.target.value)} required />
          </label>
          <label>
            Date
            <input type="date" value={reportDate} onChange={(event) => setReportDate(event.target.value)} required />
          </label>
          <label>
            Shift
            <select value={shift} onChange={(event) => setShift(event.target.value)}>
              <option>Day</option>
              <option>Night</option>
              <option>General</option>
            </select>
          </label>
          <label>
            Discipline
            <select value={disciplineId} onChange={(event) => setDisciplineId(Number(event.target.value))} required>
              <option value={0}>Select discipline</option>
              {sources.disciplines.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Area
            <select value={areaId} onChange={(event) => setAreaId(Number(event.target.value))} required>
              <option value={0}>Select area</option>
              {sources.areas.map((row) => (
                <option key={row.id} value={row.id}>{row.code} · {row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Executing company
            <select value={companyId} onChange={(event) => setCompanyId(Number(event.target.value))} required>
              <option value={0}>Select company</option>
              {sources.companies.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Site engineer
            <select value={engineerId} onChange={(event) => setEngineerId(Number(event.target.value))} required>
              <option value={0}>Select a project member</option>
              {sources.members.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <button className="primary" type="submit" disabled={!disciplineId || !areaId || !companyId || !engineerId}>
            Save draft report
          </button>
        </form>
      ) : null}
      {canEdit && openReports.length > 0 && started.length > 0 ? (
        <form className="contact-form" onSubmit={(event) => void addLine(event)}>
          <h4>Work line</h4>
          <p className="muted">Only a package that is in progress can take a quantity. Naming a posted issue or reservation leaves the stores balance unchanged.</p>
          <label>
            Report
            <select value={reportId} onChange={(event) => setReportId(Number(event.target.value))} required>
              <option value={0}>Select a draft report</option>
              {openReports.map((row) => (
                <option key={row.id} value={row.id}>{row.number} · {row.status}</option>
              ))}
            </select>
          </label>
          <label>
            Activity
            <select value={activityId} onChange={(event) => setActivityId(Number(event.target.value))} required>
              <option value={0}>Select an in-progress activity</option>
              {started.map((row) => (
                <option key={row.activity_id} value={row.activity_id}>
                  {row.activity_code} · {row.package_code}
                </option>
              ))}
            </select>
          </label>
          {chosen?.method === "Weighted milestones" ? (
            <label>
              Milestone
              <select value={milestoneId} onChange={(event) => setMilestoneId(Number(event.target.value))} required>
                <option value={0}>Select milestone</option>
                {chosen.milestones.map((row) => (
                  <option key={row.id} value={row.id}>{row.name} · {row.weight}%</option>
                ))}
              </select>
            </label>
          ) : (
            <label>
              Quantity this report {chosen ? chosen.unit : ""}
              <input value={quantity} onChange={(event) => setQuantity(event.target.value)} required />
            </label>
          )}
          <label>
            Evidence
            <input value={evidence} onChange={(event) => setEvidence(event.target.value)} />
          </label>
          <label>
            Crew note
            <input value={crew} onChange={(event) => setCrew(event.target.value)} placeholder="Written crew. No attendance record." />
          </label>
          <label>
            Equipment hours
            <input value={equipmentHours} onChange={(event) => setEquipmentHours(event.target.value)} placeholder="Written hours. No equipment register." />
          </label>
          <label>
            Stores reference
            <select value={storesId} onChange={(event) => setStoresId(Number(event.target.value))}>
              <option value={0}>No stores posting</option>
              {postings.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.number} · {row.kind} · {row.quantity_label || "quantity on the posting"}
                </option>
              ))}
            </select>
          </label>
          <label>
            <input type="checkbox" checked={rework} onChange={(event) => setRework(event.target.checked)} />
            Rework, kept out of progress
          </label>
          <button className="primary" type="submit" disabled={!reportId || !activityId}>Add work line</button>
        </form>
      ) : null}
      {started.length === 0 ? <p className="muted">Start a released work package before recording daily progress.</p> : null}
      <div className="contact-grid">
        {reports.map((report) => (
          <article key={report.id} className="contact-card progress-card">
            <header>
              <span className={`rel-chip prog-${report.status.replaceAll(" ", "-").toLowerCase()}`}>{report.status}</span>
              <span>{report.shift}</span>
            </header>
            <h4>{report.number}</h4>
            <p>{report.report_date} · {report.discipline_name} · {report.area_name}</p>
            <p>{report.site_engineer_name}</p>
            {report.lines.map((line) => (
              <div key={line.id} className="labour-line">
                <p>
                  {line.activity_code}
                  {line.milestone_name ? ` · ${line.milestone_name}` : ""}
                  {line.quantity ? ` · ${line.quantity} ${line.unit}` : ""}
                  {line.rework ? " · Rework" : ""}
                  {line.reverses_line_id ? " · Correction" : ""}
                  {line.crew_reference ? ` · Crew ${line.crew_reference}` : ""}
                </p>
                <LabourBox
                  line={line}
                  report={report}
                  editable={canEdit && (report.status === "Draft" || report.status === "Returned for Correction") && !line.reverses_line_id}
                  people={labourPeople}
                  run={labour}
                />
              </div>
            ))}
            {report.lines.filter((line) => line.stores).map((line) => (
              <p key={`stores-${line.id}`} className="link-ref">
                Stores {line.stores?.number} · {line.stores?.kind}
                {line.stores?.quantity_label ? ` · ${line.stores.quantity_label}` : ""}. Not the installed quantity.
              </p>
            ))}
            {report.warnings.map((warning) => (
              <p key={warning} className="note-card">{warning}</p>
            ))}
            {canEdit && report.status === "Draft" ? (
              <button type="button" className="primary" onClick={() => void submit(report)}>Submit for verification</button>
            ) : null}
            {canEdit && report.status === "Returned for Correction" ? (
              <button type="button" className="primary" onClick={() => void resubmit(report)}>Resubmit report</button>
            ) : null}
            {report.review && report.review.actions.some((action) => action === "approve" || action === "return" || action === "reject") ? (
              <div className="check-actions">
                <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Reason for return or reject" />
                {report.review.actions.includes("approve") ? (
                  <button type="button" className="primary" onClick={() => void decide(report, "approve")}>Verify quantity</button>
                ) : null}
                {report.review.actions.includes("return") ? (
                  <button type="button" onClick={() => void decide(report, "return")}>Return</button>
                ) : null}
                {report.review.actions.includes("reject") ? (
                  <button type="button" onClick={() => void decide(report, "reject")}>Reject</button>
                ) : null}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function hoursToMinutes(value: string) {
  const hours = Number(value || "0");
  return Number.isFinite(hours) ? Math.round(hours * 60) : 0;
}

function LabourBox({
  line,
  report,
  editable,
  people,
  run,
}: {
  line: DailyLine;
  report: DailyReport;
  editable: boolean;
  people: LabourPerson[];
  run: (path: string, method: "POST" | "DELETE", body?: Record<string, unknown>) => Promise<boolean>;
}) {
  const [personId, setPersonId] = useState(0);
  const [productive, setProductive] = useState("8");
  const [idle, setIdle] = useState("");
  const [idleReason, setIdleReason] = useState("");
  const booked = new Set(line.labour.map((row) => row.personnel_id));
  const eligible = people.filter(
    (row) =>
      row.company_id === report.company_id &&
      !booked.has(row.id) &&
      row.windows.some(([start, end]) => start <= report.report_date && (end === null || report.report_date <= end)),
  );
  if (!line.labour.length && !editable) return null;

  async function add() {
    const ok = await run(`${report.id}/lines/${line.id}/labour`, "POST", {
      personnel_id: personId,
      productive_minutes: hoursToMinutes(productive),
      idle_minutes: hoursToMinutes(idle),
      idle_reason: idleReason,
    });
    if (ok) {
      setPersonId(0);
      setProductive("8");
      setIdle("");
      setIdleReason("");
    }
  }

  return (
    <div className="labour-box">
      {line.labour.length ? (
        <ul className="labour-list">
          {line.labour.map((row) => (
            <li key={row.id}>
              <Users size={13} />
              <strong>{row.person}</strong>
              <span className="labour-prod">{row.productive} productive</span>
              {row.idle !== "0:00" ? <span className="labour-idle" title={row.idle_reason}>{row.idle} idle · {row.idle_reason}</span> : null}
              {editable ? (
                <button type="button" className="labour-remove" aria-label={`Remove ${row.person}`} onClick={() => void run(`${report.id}/labour/${row.id}`, "DELETE")}>
                  ×
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {editable ? (
        <div className="labour-entry">
          <select aria-label="Labour person" value={personId} onChange={(event) => setPersonId(Number(event.target.value))}>
            <option value={0}>{eligible.length ? "Add a person" : "No mobilized person of this company"}</option>
            {eligible.map((row) => (
              <option key={row.id} value={row.id}>{row.name}</option>
            ))}
          </select>
          <input aria-label="Productive hours" type="number" min="0" max="24" step="0.25" value={productive} onChange={(event) => setProductive(event.target.value)} placeholder="Productive h" />
          <input aria-label="Idle hours" type="number" min="0" max="24" step="0.25" value={idle} onChange={(event) => setIdle(event.target.value)} placeholder="Idle h" />
          {idle && Number(idle) > 0 ? (
            <input aria-label="Idle reason" value={idleReason} onChange={(event) => setIdleReason(event.target.value)} placeholder="Idle reason" />
          ) : null}
          <button type="button" className="primary" disabled={!personId} onClick={() => void add()}>Add hours</button>
        </div>
      ) : null}
    </div>
  );
}

type LinkCheck = {
  id: number;
  package_code: string;
  check_type: string;
  status: string;
  evidence: string;
  source_label: string;
};
type LinkBoard = {
  stores: { note: string; postings: StorePosting[]; material_checks: LinkCheck[] };
  planning: {
    note: string;
    packages: {
      id: number;
      code: string;
      name: string;
      status: string;
      planning_reference: string;
      planned_start: string | null;
      planned_finish: string | null;
    }[];
  };
  hr: { note: string; checks: LinkCheck[]; crew: { report_number: string; activity_code: string; crew_reference: string }[] };
  equipment: { note: string; entries: { report_number: string; activity_code: string; equipment_hours: string }[] };
  hse: {
    note: string;
    assessment_note?: string;
    permit_note?: string;
    field_note?: string;
    incident_note?: string;
    hold_note?: string;
    emergency_note?: string;
    environment_note?: string;
    checks: LinkCheck[];
    assessments?: { id: number; number: string; status: string }[];
  };
  qa: { note: string; checks: LinkCheck[]; accepted: string };
};

function CheckList({ rows, empty }: { rows: LinkCheck[]; empty: string }) {
  if (rows.length === 0) return <p className="muted">{empty}</p>;
  return (
    <ul className="link-list">
      {rows.map((row) => (
        <li key={row.id}>
          <strong>{row.package_code}</strong> · {row.check_type} · {row.status}
          {row.evidence ? <span> · {row.evidence}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function Connections({ pid, onError }: { pid: number; onError: (message: string) => void }) {
  const [board, setBoard] = useState<LinkBoard | null>(null);

  useEffect(() => {
    void api<LinkBoard>(`/projects/${pid}/construction/connections`)
      .then(setBoard)
      .catch((err) => onError((err as Error).message));
  }, [pid]);

  if (!board) return null;
  return (
    <section className="panel">
      <h3>Connections</h3>
      <p className="muted">
        These cards read records that already exist. Schedule baselines, attendance, and billing certification stay closed.
      </p>
      <div className="link-grid">
        <article className="link-card link-stores">
          <header><Package size={15} /> Stores</header>
          <p>{board.stores.note}</p>
          {board.stores.postings.length === 0 ? <p className="muted">No posted issue or reservation is on this project.</p> : (
            <ul className="link-list">
              {board.stores.postings.map((row) => (
                <li key={row.id}>
                  <strong>{row.number}</strong> · {row.kind}
                  {row.quantity_label ? ` · ${row.quantity_label}` : ""}
                  {row.lines[0]?.item_name ? ` · ${row.lines[0].item_name}` : ""}
                </li>
              ))}
            </ul>
          )}
          <CheckList rows={board.stores.material_checks} empty="No material readiness note is stored." />
        </article>
        <article className="link-card link-planning">
          <header><CalendarRange size={15} /> Planning</header>
          <p>{board.planning.note}</p>
          <ul className="link-list">
            {board.planning.packages.map((row) => (
              <li key={row.id}>
                <strong>{row.code}</strong> · {row.status}
                <span> · {row.planned_start || "Start not set"} → {row.planned_finish || "Finish not set"}</span>
                {row.planning_reference ? <span> · {row.planning_reference}</span> : null}
              </li>
            ))}
          </ul>
        </article>
        <article className="link-card link-hr">
          <header><Users size={15} /> Crew</header>
          <p>{board.hr.note}</p>
          {board.hr.crew.length === 0 ? <p className="muted">Crew is entered on a daily report.</p> : (
            <ul className="link-list">
              {board.hr.crew.map((row) => (
                <li key={`${row.report_number}-${row.activity_code}-${row.crew_reference}`}>
                  <strong>{row.report_number}</strong> · {row.activity_code} · {row.crew_reference}
                </li>
              ))}
            </ul>
          )}
          <CheckList rows={board.hr.checks} empty="No manpower readiness note is stored." />
        </article>
        <article className="link-card link-equipment">
          <header><Cog size={15} /> Equipment</header>
          <p>{board.equipment.note}</p>
          {board.equipment.entries.length === 0 ? <p className="muted">Equipment hours are entered on a daily report.</p> : (
            <ul className="link-list">
              {board.equipment.entries.map((row) => (
                <li key={`${row.report_number}-${row.activity_code}-${row.equipment_hours}`}>
                  <strong>{row.report_number}</strong> · {row.activity_code} · {row.equipment_hours} h
                </li>
              ))}
            </ul>
          )}
        </article>
        <article className="link-card link-hse">
          <header><ShieldAlert size={15} /> HSE</header>
          <p>{board.hse.note}</p>
          {board.hse.assessment_note ? <p>{board.hse.assessment_note}</p> : null}
          {board.hse.permit_note ? <p>{board.hse.permit_note}</p> : null}
          {board.hse.field_note ? <p>{board.hse.field_note}</p> : null}
          {board.hse.incident_note ? <p>{board.hse.incident_note}</p> : null}
          {board.hse.hold_note ? <p>{board.hse.hold_note}</p> : null}
          {board.hse.emergency_note ? <p>{board.hse.emergency_note}</p> : null}
          {board.hse.environment_note ? <p>{board.hse.environment_note}</p> : null}
          {board.hse.assessments && board.hse.assessments.length > 0 ? (
            <ul className="link-list">
              {board.hse.assessments.map((row) => (
                <li key={row.id}>
                  <strong>{row.number}</strong> · {row.status}
                </li>
              ))}
            </ul>
          ) : null}
          <CheckList rows={board.hse.checks} empty="No permit readiness note is stored." />
        </article>
        <article className="link-card link-qa">
          <header><ClipboardCheck size={15} /> QA</header>
          <p>{board.qa.note}</p>
          <p className="measure-closed">Accepted: {board.qa.accepted}</p>
          <CheckList rows={board.qa.checks} empty="No inspection or quality-hold note is stored." />
        </article>
      </div>
    </section>
  );
}

type HoldReview = { id: number; version: number; actions: string[] };
type HoldRow = {
  id: number;
  package_id: number;
  package_code: string;
  package_status: string;
  release_state: string;
  package_version: number;
  reason: string;
  status: string;
  version: number;
  note: string;
  review: HoldReview | null;
};
type BlockerRow = {
  id: number;
  package_id: number;
  package_code: string;
  kind: string;
  description: string;
  owner_name: string;
  recovery_note: string;
  status: string;
  resolution_note: string;
  version: number;
};
type MonitorBoard = {
  note: string;
  packages: { id: number; code: string; status: string; release_state: string; version: number }[];
  holds: HoldRow[];
  blockers: BlockerRow[];
  rework: { line_id: number; report_number: string; report_status: string; activity_code: string; quantity: string | null; unit: string }[];
  rework_note: string;
  overdue_reports: { id: number; number: string; report_date: string; status: string; shift: string }[];
};

function Monitoring({
  pid,
  canEdit,
  sources,
  onSaved,
  onError,
}: {
  pid: number;
  canEdit: boolean;
  sources: Sources;
  onSaved: (message: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [board, setBoard] = useState<MonitorBoard | null>(null);
  const [packageId, setPackageId] = useState(0);
  const [reason, setReason] = useState("");
  const [blockerPackage, setBlockerPackage] = useState(0);
  const [kind, setKind] = useState("Delay");
  const [description, setDescription] = useState("");
  const [ownerId, setOwnerId] = useState(0);
  const [recovery, setRecovery] = useState("");
  const [resolution, setResolution] = useState("");
  const [decisionReason, setDecisionReason] = useState("");

  async function loadBoard() {
    setBoard(await api<MonitorBoard>(`/projects/${pid}/construction/monitoring`));
  }

  useEffect(() => {
    void loadBoard().catch((err) => onError((err as Error).message));
  }, [pid]);

  const running = board?.packages.filter((row) => row.status === "In Progress" && row.release_state === "Released") || [];
  const active = board?.packages.filter((row) => row.status === "In Progress" || row.status === "On Hold") || [];

  async function hold(event: FormEvent) {
    event.preventDefault();
    const chosen = running.find((row) => row.id === packageId);
    if (!chosen) return;
    onError("");
    try {
      await api(`/projects/${pid}/construction/packages/${chosen.id}/hold`, "POST", {
        reason,
        version: chosen.version,
      });
      setReason("");
      await loadBoard();
      await onSaved("Work is on hold. Daily progress stays closed until resume is approved.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function resume(holdRow: HoldRow) {
    onError("");
    try {
      await api(`/projects/${pid}/construction/holds/${holdRow.id}/resume`, "POST", { version: holdRow.version });
      await loadBoard();
      await onSaved("Resume sent to the saved release reviewer.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function resubmit(holdRow: HoldRow) {
    onError("");
    try {
      await api(`/projects/${pid}/construction/holds/${holdRow.id}/resubmit`, "POST", { version: holdRow.version });
      await loadBoard();
      await onSaved("Resume resubmitted.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function decide(holdRow: HoldRow, action: string) {
    if (!holdRow.review) return;
    onError("");
    try {
      await api(`/reviews/${holdRow.review.id}/decisions`, "POST", {
        action,
        reason: action === "approve" ? "" : decisionReason,
        comment: "",
        version: holdRow.review.version,
      });
      setDecisionReason("");
      await loadBoard();
      await onSaved(action === "approve" ? "Work resumed. Daily progress can be recorded again." : `Resume ${action}ed.`);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function addBlocker(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/construction/blockers`, "POST", {
        package_id: blockerPackage,
        kind,
        description,
        owner_user_id: ownerId,
        recovery_note: recovery,
      });
      setDescription("");
      setRecovery("");
      await loadBoard();
      await onSaved("Blocker recorded. The site engineer, discipline head, and project manager are notified.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function resolve(row: BlockerRow) {
    onError("");
    try {
      await api(`/projects/${pid}/construction/blockers/${row.id}/resolve`, "POST", {
        resolution_note: resolution,
        version: row.version,
      });
      setResolution("");
      await loadBoard();
      await onSaved("Blocker resolved.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  if (!board) return null;
  return (
    <section className="panel">
      <h3>Monitoring</h3>
      <p className="muted">{board.note} A hold does not create an inspection or a permit.</p>
      <div className="link-grid">
        <article className="link-card mon-hold">
          <header><AlertTriangle size={15} /> On hold</header>
          {board.holds.length === 0 ? <p className="muted">No package is on hold.</p> : board.holds.map((row) => (
            <div key={row.id} className="mon-item">
              <strong>{row.package_code}</strong>
              <span className="rel-chip mon-hold-chip">{row.status}</span>
              <p>{row.reason}</p>
              <p className="muted">{row.note}</p>
              {canEdit && (row.status === "Open" || row.status === "Rejected") ? (
                <button type="button" className="primary" onClick={() => void resume(row)}>Request resume</button>
              ) : null}
              {canEdit && row.status === "Returned" ? (
                <button type="button" className="primary" onClick={() => void resubmit(row)}>Resubmit resume</button>
              ) : null}
              {row.review && row.review.actions.some((action) => action === "approve" || action === "return" || action === "reject") ? (
                <div className="check-actions">
                  <input value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} placeholder="Reason for return or reject" />
                  {row.review.actions.includes("approve") ? (
                    <button type="button" className="primary" onClick={() => void decide(row, "approve")}>Approve resume</button>
                  ) : null}
                  {row.review.actions.includes("return") ? (
                    <button type="button" onClick={() => void decide(row, "return")}>Return</button>
                  ) : null}
                  {row.review.actions.includes("reject") ? (
                    <button type="button" onClick={() => void decide(row, "reject")}>Reject</button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}
        </article>
        <article className="link-card mon-block">
          <header><AlertTriangle size={15} /> Blockers</header>
          {board.blockers.filter((row) => row.status === "Open").length === 0 ? <p className="muted">No open blocker.</p> : null}
          {board.blockers.map((row) => (
            <div key={row.id} className="mon-item">
              <strong>{row.package_code}</strong> · {row.kind} · {row.status}
              <p>{row.description}</p>
              <p>Owner {row.owner_name}. Recovery: {row.recovery_note}</p>
              {row.resolution_note ? <p>Resolved: {row.resolution_note}</p> : null}
            </div>
          ))}
        </article>
        <article className="link-card mon-rework">
          <header><AlertTriangle size={15} /> Rework</header>
          <p>{board.rework_note}</p>
          {board.rework.length === 0 ? <p className="muted">No rework is recorded.</p> : (
            <ul className="link-list">
              {board.rework.map((row) => (
                <li key={row.line_id}>
                  <strong>{row.report_number}</strong> · {row.activity_code}
                  {row.quantity ? ` · ${row.quantity} ${row.unit}` : ""} · {row.report_status}
                </li>
              ))}
            </ul>
          )}
        </article>
        <article className="link-card mon-late">
          <header><CalendarDays size={15} /> Draft reports past their date</header>
          {board.overdue_reports.length === 0 ? <p className="muted">No draft report is past its date.</p> : (
            <ul className="link-list">
              {board.overdue_reports.map((row) => (
                <li key={row.id}><strong>{row.number}</strong> · {row.report_date} · {row.status}</li>
              ))}
            </ul>
          )}
        </article>
      </div>
      {canEdit && running.length > 0 ? (
        <form className="contact-form" onSubmit={(event) => void hold(event)}>
          <h4>Hold work</h4>
          <label>
            Package
            <select value={packageId} onChange={(event) => setPackageId(Number(event.target.value))} required>
              <option value={0}>Select an in-progress package</option>
              {running.map((row) => (
                <option key={row.id} value={row.id}>{row.code}</option>
              ))}
            </select>
          </label>
          <label>
            Reason
            <input value={reason} onChange={(event) => setReason(event.target.value)} required />
          </label>
          <button className="primary" type="submit" disabled={!packageId || reason.trim().length < 3}>Hold work</button>
        </form>
      ) : null}
      {canEdit && active.length > 0 ? (
        <form className="contact-form" onSubmit={(event) => void addBlocker(event)}>
          <h4>Blocker</h4>
          <label>
            Package
            <select value={blockerPackage} onChange={(event) => setBlockerPackage(Number(event.target.value))} required>
              <option value={0}>Select a package</option>
              {active.map((row) => (
                <option key={row.id} value={row.id}>{row.code} · {row.status}</option>
              ))}
            </select>
          </label>
          <label>
            Kind
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              <option>Delay</option>
              <option>Obstruction</option>
              <option>Weather</option>
              <option>Idle</option>
            </select>
          </label>
          <label>
            What is blocked
            <input value={description} onChange={(event) => setDescription(event.target.value)} required />
          </label>
          <label>
            Owner
            <select value={ownerId} onChange={(event) => setOwnerId(Number(event.target.value))} required>
              <option value={0}>Select a project member</option>
              {sources.members.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            Recovery note
            <input value={recovery} onChange={(event) => setRecovery(event.target.value)} required />
          </label>
          <button className="primary" type="submit" disabled={!blockerPackage || !ownerId}>Record blocker</button>
        </form>
      ) : null}
      {canEdit && board.blockers.some((row) => row.status === "Open") ? (
        <form className="contact-form" onSubmit={(event) => { event.preventDefault(); }}>
          <h4>Resolve a blocker</h4>
          <label>
            Resolution
            <input value={resolution} onChange={(event) => setResolution(event.target.value)} />
          </label>
          {board.blockers.filter((row) => row.status === "Open").map((row) => (
            <button key={row.id} type="button" className="primary" disabled={resolution.trim().length < 3} onClick={() => void resolve(row)}>
              Resolve {row.package_code} {row.kind}
            </button>
          ))}
        </form>
      ) : null}
    </section>
  );
}

type HandoverReview = { id: number; version: number; actions: string[] };
type DossierActivity = {
  code: string;
  verified_quantity: string | null;
  verified_percent: string | null;
  unit: string;
  accepted_quantity: null;
  certified_quantity: null;
};
type DossierRow = {
  id: number;
  number: string;
  package_code: string;
  package_status: string;
  status: string;
  statement: string;
  version: number;
  payload: { activities?: DossierActivity[]; checks?: { check_type: string; status: string }[]; statement?: string };
  review: HandoverReview | null;
};
type HandoverBoard = {
  note: string;
  dossiers: DossierRow[];
  packages: { id: number; code: string; status: string }[];
};

function Handover({
  pid,
  session,
  canEdit,
  sources,
  onSaved,
  onError,
}: {
  pid: number;
  session: Session;
  canEdit: boolean;
  sources: Sources;
  onSaved: (message: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [board, setBoard] = useState<HandoverBoard | null>(null);
  const [number, setNumber] = useState("");
  const [packageId, setPackageId] = useState(0);
  const [reviewerId, setReviewerId] = useState(0);
  const [routeDiscipline, setRouteDiscipline] = useState(0);
  const [reason, setReason] = useState("");
  const handoverRoutes = useSavedRoutes(pid, "construction.handover", session.user.organization_admin);
  const handoverLocked = routeLocked(handoverRoutes, routeDiscipline || null);

  async function loadBoard() {
    setBoard(await api<HandoverBoard>(`/projects/${pid}/construction/handover`));
  }

  useEffect(() => {
    void loadBoard().catch((err) => onError((err as Error).message));
  }, [pid]);

  async function saveRoute(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/approval-policies`, "POST", {
        record_type: "construction.handover",
        company_id: null,
        discipline_id: routeDiscipline || null,
        allow_self_approval: false,
        stages: [
          {
            name: "Handover",
            rule: "all",
            quorum_count: 1,
            reviewer_ids: [reviewerId],
            reviewers: [],
            purpose: "Confirm the construction handover dossier",
          },
        ],
      });
      await onSaved("Handover route saved. Only this reviewer can hand the package over.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function saveDossier(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      await api(`/projects/${pid}/construction/handover`, "POST", { number, package_id: packageId });
      setNumber("");
      await loadBoard();
      await onSaved("Handover dossier saved as a draft.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function submit(row: DossierRow) {
    onError("");
    try {
      await api(`/projects/${pid}/construction/handover/${row.id}/submit`, "POST", { version: row.version });
      await loadBoard();
      await onSaved("Dossier sent for handover. Daily progress stays closed while it is in review.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function resubmit(row: DossierRow) {
    onError("");
    try {
      await api(`/projects/${pid}/construction/handover/${row.id}/resubmit`, "POST", { version: row.version });
      await loadBoard();
      await onSaved("Handover dossier resubmitted.");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function decide(row: DossierRow, action: string) {
    if (!row.review) return;
    onError("");
    try {
      await api(`/reviews/${row.review.id}/decisions`, "POST", {
        action,
        reason: action === "approve" ? "" : reason,
        comment: "",
        version: row.review.version,
      });
      setReason("");
      await loadBoard();
      await onSaved(action === "approve" ? "Package handed over. No commissioning test was created." : `Handover ${action}ed.`);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  if (!board) return null;
  return (
    <section className="panel">
      <h3>Handover</h3>
      <p className="muted">{board.note} The commissioning module stays closed.</p>
      {session.user.organization_admin ? (
        <form className="contact-form" onSubmit={(event) => void saveRoute(event)}>
          <h4>Handover route</h4>
          <p className="muted">The reviewer must already be a project member. An administrator is not an automatic reviewer.</p>
          <label>
            Discipline
            <select value={routeDiscipline} onChange={(event) => setRouteDiscipline(Number(event.target.value))}>
              <option value={0}>All disciplines on this project</option>
              {sources.disciplines.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          {handoverLocked ? (
            <RouteLockNotice target={{ projectId: pid, recordType: "construction.handover", disciplineId: routeDiscipline || null }} />
          ) : null}
          <label>
            Reviewer
            <select value={reviewerId} disabled={handoverLocked} onChange={(event) => setReviewerId(Number(event.target.value))} required>
              <option value={0}>Select a project member</option>
              {sources.members.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <button className="primary" type="submit" disabled={handoverLocked || !reviewerId}>Save handover route</button>
        </form>
      ) : null}
      {canEdit && board.packages.length > 0 ? (
        <form className="contact-form" onSubmit={(event) => void saveDossier(event)}>
          <h4>New dossier</h4>
          <label>
            Dossier number
            <input value={number} onChange={(event) => setNumber(event.target.value)} required />
          </label>
          <label>
            Package
            <select value={packageId} onChange={(event) => setPackageId(Number(event.target.value))} required>
              <option value={0}>Select an in-progress package</option>
              {board.packages.map((row) => (
                <option key={row.id} value={row.id}>{row.code}</option>
              ))}
            </select>
          </label>
          <button className="primary" type="submit" disabled={!packageId}>Save draft dossier</button>
        </form>
      ) : null}
      <div className="contact-grid">
        {board.dossiers.map((row) => (
          <article key={row.id} className="contact-card handover-card">
            <header>
              <span className={`rel-chip hand-${row.status.replaceAll(" ", "-").toLowerCase()}`}>{row.status}</span>
              <span>{row.package_status}</span>
            </header>
            <h4>{row.number}</h4>
            <p>{row.package_code}</p>
            <p className="muted">{row.statement}</p>
            {(row.payload.activities || []).map((activity) => (
              <p key={activity.code}>
                {activity.code} verified {activity.verified_percent ? `${activity.verified_percent}%` : activity.verified_quantity} {activity.unit}
              </p>
            ))}
            {row.payload.activities ? (
              <>
                <p className="measure-closed">Accepted quantity is recorded by Quality</p>
                <p className="measure-closed">Certified: not open</p>
              </>
            ) : null}
            {canEdit && row.status === "Draft" ? (
              <button type="button" className="primary" onClick={() => void submit(row)}>Submit for handover</button>
            ) : null}
            {canEdit && row.status === "Returned for Correction" ? (
              <button type="button" className="primary" onClick={() => void resubmit(row)}>Resubmit dossier</button>
            ) : null}
            {row.review && row.review.actions.some((action) => action === "approve" || action === "return" || action === "reject") ? (
              <div className="check-actions">
                <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Reason for return or reject" />
                {row.review.actions.includes("approve") ? (
                  <button type="button" className="primary" onClick={() => void decide(row, "approve")}>Approve handover</button>
                ) : null}
                {row.review.actions.includes("return") ? (
                  <button type="button" onClick={() => void decide(row, "return")}>Return</button>
                ) : null}
                {row.review.actions.includes("reject") ? (
                  <button type="button" onClick={() => void decide(row, "reject")}>Reject</button>
                ) : null}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
