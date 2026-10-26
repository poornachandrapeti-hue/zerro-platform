import { FormEvent, useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  Building2,
  FilePlus,
  Files,
  FileText,
  LayoutDashboard,
  Link2,
  ListChecks,
  Send,
  Settings,
  ShieldCheck,
  Upload,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { api, downloadFile, postForm } from "./api";
import type { Catalog, Company, Page, Project, Session, User } from "./types";
import { type DashboardView, EngineeringDashboard, Pill, day, stamp } from "./engineering_dashboard";
import { MaterialsTab } from "./materials";

const ENG_TABS = [
  "Dashboard",
  "Drawing register",
  "Attention",
  "Drawing detail",
  "Transmittals",
  "My tasks",
  "New drawing",
  "Import drawings",
  "Review policy",
  "Integrations",
  "Wrench",
  "Setup",
] as const;
const ADMIN_TABS: readonly EngTab[] = ["Review policy", "Setup"];
type EngTab = (typeof ENG_TABS)[number];
const ENG_ICON: Record<EngTab, LucideIcon> = {
  Dashboard: LayoutDashboard,
  "Drawing register": Files,
  Attention: AlertTriangle,
  "Drawing detail": FileText,
  Transmittals: Send,
  "My tasks": ListChecks,
  "New drawing": FilePlus,
  "Import drawings": Upload,
  "Review policy": ShieldCheck,
  Integrations: Link2,
  Wrench: Wrench,
  Setup: Settings,
};
const ENG_TONE: Record<EngTab, string> = {
  Dashboard: "tone-edash",
  "Drawing register": "tone-ereg",
  Attention: "tone-eattn",
  "Drawing detail": "tone-edetail",
  Transmittals: "tone-etrans",
  "My tasks": "tone-etask",
  "New drawing": "tone-enew",
  "Import drawings": "tone-eimport",
  "Review policy": "tone-epolicy",
  Integrations: "tone-eint",
  Wrench: "tone-ewrench",
  Setup: "tone-eset",
};
const VIEW_OF: Partial<Record<EngTab, DashboardView>> = {
  Dashboard: "dashboard",
  "Drawing register": "register",
  Attention: "attention",
};

function Err({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}

type ReviewStep = {
  name: string;
  purpose: string;
  status: string;
  reviewers: { id: number; name: string }[];
};
type Review = {
  id: number;
  state: string;
  version: number;
  stage_purpose?: string;
  reviewers?: { id: number; name: string }[];
  chain?: ReviewStep[];
  actions: string[];
  decisions: { id: number; action: string; reason: string; attempt: number; reviewer_name?: string }[];
};
type Comment = {
  id: number;
  page_ref: string;
  body: string;
  severity: string;
  stage?: string;
  comment_number?: number;
  owner_id: number;
  owner_name?: string;
  raised_by?: string;
  can_respond?: boolean;
  can_close?: boolean;
  due_date: string | null;
  response: string;
  closure_evidence: string;
  status: string;
  version: number;
};
type Revision = {
  id: number;
  code: string;
  review_state: string;
  release_state: string;
  file_name: string;
  version: number;
  review: Review | null;
  comments: Comment[];
  events: { id: number; kind: string; detail: string; created_at?: string; actor?: string }[];
  actions: string[];
  created_by_name?: string;
  prepared_at?: string | null;
  released_by_name?: string;
  released_at?: string | null;
  release_reference?: string;
  client_outcome?: string | null;
  external_reviewer?: string;
  decision_reference?: string;
  decision_recorded_by_name?: string;
  scan_status?: string;
};
type Tracking = {
  area: string;
  current_revision: string | null;
  released_revision: string | null;
  release_status: string;
  overall_status: string;
  preparation_status: string;
  internal_status: string;
  client_status: string;
  open_comments: number;
  client_comments: number;
  required_date: string | null;
  required_for: string;
  pending_with: string[];
  overdue: { action: string; due_date: string; days: number; pending_with: string[] }[];
  days_overdue: number;
  last_updated: string | null;
  lifecycle_label: string;
  planned_date: string | null;
  planned_submission: string | null;
  planned_approval: string | null;
  work_packages: {
    id: number;
    code: string;
    name: string;
    planned_start: string | null;
    linked_revision: string;
    linked_release_state: string;
    blocking: boolean;
    withdrawn: boolean;
  }[];
  attention: { issue: string; pending_with: string; due_date: string | null; work_packages: string }[];
};
type Drawing = {
  id: number;
  number: string;
  title: string;
  drawing_type: string;
  discipline_id: number;
  discipline: string;
  company_id: number;
  company: string;
  responsible_user_id: number | null;
  responsible: string;
  planned_date: string | null;
  priority: string;
  preparation: string;
  work_reference: string;
  provenance: string;
  version: number;
  bucket: string;
  preparation_status?: string;
  internal_status?: string;
  client_status?: string;
  record_status?: string;
  cancellation_reason?: string;
  remarks?: string;
  latest_revision: string;
  review_state: string;
  release_state: string;
  latest_released: { id: number; code: string } | null;
  revisions?: Revision[];
  actions?: string[];
  links?: { id: number; related_id: number }[];
  tracking?: Tracking;
  assignments?: Assignments;
  area_id?: number | null;
  category_id?: number | null;
  reviewer_id?: number | null;
  planned_submission?: string | null;
  planned_approval?: string | null;
};
type Assignments = {
  discipline: string;
  responsible: { id: number; name: string } | null;
  can_assign: boolean;
  review_route: {
    policy_id: number;
    applies_to: string;
    stages: { name: string; purpose: string; rule: string; reviewers: string[] }[];
    self_approval: boolean;
  } | null;
  review_route_missing: string | null;
  release_authority: string[];
  document_controllers: string[];
};
type Category = { id: number; discipline_id: number; name: string };
type Area = { id: number; code: string; name: string };

function label(action: string) {
  const names: Record<string, string> = {
    approve: "Approve",
    approve_with_comments: "Approve with comments",
    return: "Return",
    reject: "Reject",
    comment: "Comment",
  };
  return names[action] || action.replaceAll("_", " ");
}

function actionClass(action: string) {
  const tones: Record<string, string> = {
    approve: "tone-approve",
    approve_with_comments: "tone-comments",
    return: "tone-return",
    reject: "tone-reject",
    comment: "tone-note",
    submit: "tone-submit",
    release: "tone-approve",
    withdraw: "tone-withdraw",
  };
  return tones[action] || "";
}

function stepLabel(status: string) {
  if (status === "current") return "Now";
  if (status === "done") return "Approved";
  if (status === "stopped") return "Stopped";
  return "Not started";
}

function reviewStatus(drawing: Drawing, revision: Revision) {
  const review = revision.review;
  if (!review) return `Revision ${revision.code} has not been submitted for review.`;
  const owner = drawing.responsible || "the responsible engineer";
  const current = (review.chain || []).find((step) => step.status === "current");
  const later = (review.chain || [])
    .filter((step) => step.status === "waiting")
    .flatMap((step) => step.reviewers.map((person) => person.name))
    .join(", ");
  if (review.state === "Approved") {
    return `Rev ${revision.code} of ${drawing.number} is accepted. This review is finished. Construction release is a separate step. A new revision is needed only when the drawing itself changes.`;
  }
  if (review.state === "Rejected") {
    return `Rev ${revision.code} of ${drawing.number} was rejected. ${owner} adds a new revision and submits that new file. This rejected revision stays on record and cannot be approved again.`;
  }
  if (review.state === "Returned") {
    return `Rev ${revision.code} of ${drawing.number} was returned for correction. ${owner} adds a new revision and submits it. This returned file cannot be approved again.`;
  }
  if (current && review.actions.length === 0) {
    const names = current.reviewers.map((person) => person.name).join(", ") || "the assigned reviewer";
    return `Rev ${revision.code} of ${drawing.number} is waiting for ${names}.${later ? ` ${later} is notified only after that approval.` : ""}`;
  }
  if (review.actions.length > 0) {
    return `This decision is only for rev ${revision.code} of ${drawing.number}.${later ? ` ${later} is notified only after you approve.` : ""} Reject or Return sends it back to ${owner}, who must submit a new revision.`;
  }
  return `Rev ${revision.code} of ${drawing.number} is ${review.state}.`;
}

export function DrawingsHome({
  session,
  catalog,
  initialProjectId = null,
}: {
  session: Session;
  catalog: Catalog;
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
        <EngineeringBoard pid={pid} session={session} catalog={catalog} />
      </>
    );
  }
  return (
    <section className="panel">
      <h2>Drawing register</h2>
      <p className="muted">Open a project to manage its drawings.</p>
      <Err text={error} />
      {projects.map((project) => (
        <button key={project.id} onClick={() => setPid(project.id || null)}>
          {project.code} · {project.name}
        </button>
      ))}
    </section>
  );
}

export function EngineeringBoard({
  pid,
  session,
  catalog,
}: {
  pid: number;
  session: Session;
  catalog: Catalog;
}) {
  const admin = session.user.organization_admin;
  const [refreshKey, setRefreshKey] = useState(0);
  const [drawing, setDrawing] = useState<Drawing | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [people, setPeople] = useState<User[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);
  const [error, setError] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [tasks, setTasks] = useState<{
    preparation: { id: number; number: string }[];
    reviews: { id: number; number: string; stage: string }[];
    comments: { id: number; drawing_id: number; number: string; status: string }[];
    overdue: { id: number; number: string; kind: string }[];
  } | null>(null);
  const disciplines = project
    ? catalog.disciplines.filter((row) => project.discipline_ids.includes(row.id))
    : catalog.disciplines;

  async function loadRegister() {
    setRefreshKey((value) => value + 1);
  }
  const [tab, setTab] = useState<EngTab>("Dashboard");
  const [detailTab, setDetailTab] = useState("Overview");
  async function openDrawing(id: number, nextTab = "Overview") {
    setDetailTab(nextTab);
    setDrawing(await api<Drawing>(`/projects/${pid}/drawings/${id}`));
    setTab("Drawing detail");
  }
  async function refresh(id?: number) {
    await loadRegister();
    if (id || drawing) await openDrawing(id || drawing!.id, detailTab);
  }
  useEffect(() => {
    void api<Project>(`/projects/${pid}`)
      .then(setProject)
      .catch(() => setProject(null));
    void api<Page<Company>>("/companies?limit=100")
      .then((page) => setCompanies(page.items))
      .catch(() => {
        void api<{ company_id: number; name: string; active: boolean }[]>(`/projects/${pid}/companies`)
          .then((rows) =>
            setCompanies(
              rows
                .filter((row) => row.active)
                .map((row) => ({
                  id: row.company_id,
                  name: row.name,
                  company_type: "",
                  active: true,
                })),
            ),
          )
          .catch(() => {
            if (session.user.company_id)
              setCompanies([
                {
                  id: session.user.company_id,
                  name: "My company",
                  company_type: "",
                  active: true,
                },
              ]);
          });
      });
    void api<{ id: number; name: string }[]>(`/projects/${pid}/drawing-recipients`)
      .then((rows) =>
        setPeople(
          rows.map((row) => ({
            id: row.id,
            name: row.name,
            email: "",
            company_id: null,
            active: true,
            organization_admin: false,
          })),
        ),
      )
      .catch(() => setPeople([session.user]));
    void api<Area[]>(`/projects/${pid}/areas`)
      .then(setAreas)
      .catch(() => setAreas([]));
    void api<Category[]>("/drawing-categories")
      .then(setCategories)
      .catch(() => setCategories([]));
    void api<typeof tasks>("/projects/" + pid + "/engineering-tasks")
      .then(setTasks)
      .catch(() => setTasks(null));
  }, [pid]);

  const open = (id: number, next?: string) =>
    void openDrawing(id, next).catch((err) => setError((err as Error).message));
  const taskCount = tasks
    ? tasks.preparation.length + tasks.reviews.length + tasks.comments.length + tasks.overdue.length
    : 0;
  const view = VIEW_OF[tab];

  return (
    <section className="panel ed-shell">
      <header className="ed-head">
        <div className="ed-project">
          <span className="ed-project-icon">
            <Building2 size={22} />
          </span>
          <div>
            <small>Engineering &amp; Drawing Management</small>
            <h2>{project ? `${project.code} · ${project.name}` : "Loading project…"}</h2>
            <p className="muted">
              {disciplines.length} discipline{disciplines.length === 1 ? "" : "s"} on this project
              {drawing ? ` · open drawing ${drawing.number}` : ""}
            </p>
          </div>
        </div>
      </header>
      <div className="proc-nav ed-nav">
        {ENG_TABS.filter((name) => admin || !ADMIN_TABS.includes(name)).map((name) => {
          const Icon = ENG_ICON[name];
          const badge =
            name === "My tasks" && taskCount ? taskCount : name === "Drawing detail" && drawing ? drawing.number : null;
          return (
            <button
              key={name}
              type="button"
              className={`proc-tab ${ENG_TONE[name]}${tab === name ? " is-on" : ""}`}
              aria-pressed={tab === name}
              onClick={() => setTab(name)}
            >
              <Icon size={14} strokeWidth={2.4} />
              <span>{name}</span>
              {badge ? <em className="ed-badge">{badge}</em> : null}
            </button>
          );
        })}
      </div>
      <Err text={error} />
      {view && (
        <EngineeringDashboard
          pid={pid}
          view={view}
          refreshKey={refreshKey}
          onOpen={open}
          onView={(next) => setTab(next === "register" ? "Drawing register" : next === "attention" ? "Attention" : "Dashboard")}
        />
      )}
      {tab === "Drawing detail" &&
        (drawing ? (
          <DrawingDetail
            key={`${drawing.id}:${detailTab}`}
            pid={pid}
            drawing={drawing}
            initialTab={detailTab}
            people={people}
            companies={companies}
            userId={session.user.id}
            onChange={(row) => {
              setDrawing(row);
              void loadRegister().catch((err) => setError((err as Error).message));
            }}
            onError={setError}
          />
        ) : (
          <div className="ed-empty-state">
            <FileText size={28} />
            <p>No drawing is open. Pick one from the Drawing register, Attention or My tasks.</p>
            <button type="button" onClick={() => setTab("Drawing register")}>
              Open the drawing register
            </button>
          </div>
        ))}
      {tab === "Transmittals" && <TransmittalLog pid={pid} refreshKey={refreshKey} onOpen={open} onError={setError} />}
      {tab === "My tasks" && <MyTasks tasks={tasks} onOpen={open} />}
      {tab === "New drawing" && (
          <CreateForm
            pid={pid}
            session={session}
            disciplines={disciplines}
            categories={categories}
            companies={companies}
            people={people}
            areas={areas}
            onCreated={(row) => {
              setDrawing(row);
              setDetailTab("Overview");
              setTab("Drawing detail");
              void loadRegister().catch((err) => setError((err as Error).message));
            }}
            onError={setError}
          />
      )}
      {tab === "Import drawings" && (
        <ImportForm
          pid={pid}
          onDone={() => void refresh().catch((err) => setError((err as Error).message))}
          onError={setError}
          onRegister={() => setTab("Drawing register")}
        />
      )}
      {tab === "Review policy" && admin && (
        <PolicyForm pid={pid} people={people} disciplines={disciplines} onError={setError} />
      )}
      {tab === "Integrations" && <Integrations drawing={drawing} onOpen={open} />}
      {tab === "Wrench" && (
        <>
          {!drawing && (
            <p className="ed-note">Open a drawing first to link it to a Wrench record. Project Wrench settings work without one.</p>
          )}
          <WrenchPanel pid={pid} drawing={drawing} admin={admin} onError={setError} />
        </>
      )}
      {tab === "Setup" && admin && <DisciplineForm catalog={catalog} onError={setError} />}
    </section>
  );
}

type TaskList = {
  preparation: { id: number; number: string }[];
  reviews: { id: number; number: string; stage: string }[];
  comments: { id: number; drawing_id: number; number: string; status: string }[];
  overdue: { id: number; number: string; kind: string }[];
};

function MyTasks({ tasks, onOpen }: { tasks: TaskList | null; onOpen: (id: number, tab?: string) => void }) {
  if (!tasks) return <p className="muted ed-loading">Loading your tasks…</p>;
  const groups: { title: string; tone: string; rows: { key: string; id: number; text: string; tab: string }[] }[] = [
    {
      title: "Reviews waiting for you",
      tone: "amber",
      rows: tasks.reviews.map((row) => ({ key: `r${row.id}`, id: row.id, text: `${row.number} · ${row.stage} review`, tab: "Reviews & Comments" })),
    },
    {
      title: "Comments to answer",
      tone: "orange",
      rows: tasks.comments.map((row) => ({ key: `c${row.id}`, id: row.drawing_id, text: `${row.number} · comment ${row.status}`, tab: "Reviews & Comments" })),
    },
    {
      title: "Drawings to prepare",
      tone: "blue",
      rows: tasks.preparation.map((row) => ({ key: `p${row.id}`, id: row.id, text: row.number, tab: "Revisions & Files" })),
    },
    {
      title: "Overdue",
      tone: "red",
      rows: tasks.overdue.map((row) => ({ key: `o${row.id}-${row.kind}`, id: row.id, text: `${row.number} · ${row.kind}`, tab: "Overview" })),
    },
  ];
  return (
    <div className="ed-task-grid">
      {groups.map((group) => (
        <article key={group.title} className="ed-block">
          <h3>
            {group.title} <span className={`ed-pill ed-${group.tone}`}>{group.rows.length}</span>
          </h3>
          {group.rows.length === 0 ? (
            <p className="mp-ok">Nothing here.</p>
          ) : (
            <ul className="ed-task-list">
              {group.rows.map((row) => (
                <li key={row.key}>
                  <span>{row.text}</span>
                  <button type="button" className="ed-link" onClick={() => onOpen(row.id, row.tab)}>
                    Open
                  </button>
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}
    </div>
  );
}

type LoggedTransmittal = {
  id: number;
  number: string;
  purpose: string;
  issue_date: string;
  status: string;
  expected_response: string | null;
  dispatched_at: string | null;
  acknowledged_at: string | null;
  method: string;
  external_reference: string;
  recipient_company: string;
  sender: string;
  items: { revision_id: number; drawing_id: number | null; number: string; title: string; code: string }[];
  recipients: { user_id: number; name?: string; acknowledged_at: string | null }[];
};

function TransmittalLog({
  pid,
  refreshKey,
  onOpen,
  onError,
}: {
  pid: number;
  refreshKey: number;
  onOpen: (id: number, tab?: string) => void;
  onError: (text: string) => void;
}) {
  const [rows, setRows] = useState<LoggedTransmittal[] | null>(null);
  const [status, setStatus] = useState("");
  useEffect(() => {
    void api<LoggedTransmittal[]>(`/projects/${pid}/transmittals`)
      .then(setRows)
      .catch((err) => {
        setRows([]);
        onError((err as Error).message);
      });
  }, [pid, refreshKey]);
  if (!rows) return <p className="muted ed-loading">Loading transmittals…</p>;
  const today = new Date().toISOString().slice(0, 10);
  const shown = rows.filter((row) => !status || row.status === status);
  return (
    <div className="ed-block">
      <div className="ed-register-head">
        <h3>
          <Send size={16} /> Transmittal log
        </h3>
        <select aria-label="Transmittal status" value={status} onChange={(e) => setStatus(e.target.value)} className="ed-inline-select">
          <option value="">All statuses</option>
          {["Draft", "Issued", "Acknowledged"].map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
        <span className="muted">
          {shown.length} transmittal{shown.length === 1 ? "" : "s"}. New transmittals are issued from a drawing's Transmittals tab.
        </span>
      </div>
      {shown.length === 0 ? (
        <p className="muted ed-empty">No transmittals yet.</p>
      ) : (
        <div className="mp-table-wrap">
          <table className="mp-table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Purpose</th>
                <th>Issued</th>
                <th>Status</th>
                <th>To</th>
                <th>Drawings and revisions</th>
                <th>Recipients</th>
                <th>Response due</th>
                <th>Sender</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => (
                <tr key={row.id}>
                  <td>
                    <strong>{row.number}</strong>
                    {row.external_reference ? <small className="ed-sub">{row.external_reference}</small> : null}
                  </td>
                  <td>{row.purpose}</td>
                  <td>{day(row.issue_date)}</td>
                  <td>
                    <Pill text={row.status === "Acknowledged" ? "Approved" : row.status === "Issued" ? "Pending" : "Not started"} />{" "}
                    <small className="ed-sub">{row.status}</small>
                  </td>
                  <td>{row.recipient_company || "—"}</td>
                  <td>
                    {row.items.map((item) => (
                      <button
                        key={item.revision_id}
                        type="button"
                        className="ed-link ed-rev-link"
                        onClick={() => item.drawing_id && onOpen(item.drawing_id, "Transmittals")}
                      >
                        {item.number} rev {item.code}
                      </button>
                    ))}
                  </td>
                  <td className="ed-pending">
                    {row.recipients.map((person) => (
                      <span key={person.user_id} className="ed-sub">
                        {person.name || `User ${person.user_id}`} · {person.acknowledged_at ? "acknowledged" : "not acknowledged"}
                      </span>
                    ))}
                  </td>
                  <td>
                    {row.expected_response ? (
                      <span className={row.status === "Issued" && row.expected_response < today ? "ed-pill ed-red" : ""}>
                        {day(row.expected_response)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>{row.sender || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Integrations({
  drawing,
  onOpen,
}: {
  drawing: Drawing | null;
  onOpen: (id: number, tab?: string) => void;
}) {
  const packages = drawing?.tracking?.work_packages || [];
  return (
    <div className="ed-int-grid">
      <article className="ed-block">
        <h3>Document control</h3>
        <p className="muted">
          Drawing files, revisions and transmittals live in one repository. Every revision keeps its own file, checksum,
          review decisions and comments, and older revisions are never overwritten.
        </p>
      </article>
      <article className="ed-block">
        <h3>Planning and construction</h3>
        <p className="muted">
          Work packages link to an exact drawing revision. Construction readiness accepts only a revision that is still
          Released. A withdrawn release marks the package for review, and earlier execution records keep their revision.
        </p>
        {!drawing ? (
          <p className="muted">Open a drawing to see the work packages linked to it.</p>
        ) : packages.length === 0 ? (
          <p className="muted">No work package is linked to {drawing.number}.</p>
        ) : (
          <ul className="ed-task-list">
            {packages.map((item) => (
              <li key={`${item.id}-${item.linked_revision}`}>
                <span>
                  <strong>{item.code}</strong> {item.name} · rev {item.linked_revision} ({item.linked_release_state})
                  {item.planned_start ? ` · starts ${day(item.planned_start)}` : ""}
                </span>
                {item.withdrawn ? (
                  <span className="ed-pill ed-red">Release withdrawn</span>
                ) : item.blocking ? (
                  <span className="ed-pill ed-orange">Blocking start</span>
                ) : (
                  <span className="ed-pill ed-teal">OK</span>
                )}
              </li>
            ))}
          </ul>
        )}
        {drawing && (
          <button type="button" className="ed-link" onClick={() => onOpen(drawing.id, "Construction Release")}>
            Open construction release for {drawing.number}
          </button>
        )}
      </article>
      <article className="ed-block">
        <h3>Procurement</h3>
        <p className="muted">
          When a released revision is superseded or withdrawn, procurement records that reference it are flagged for review.
          Material requests stay in Procurement.
        </p>
      </article>
    </div>
  );
}

function DrawingTracking({ drawing }: { drawing: Drawing }) {
  const track = drawing.tracking;
  if (!track) return null;
  const facts: [string, ReactNode][] = [
    ["Current revision", track.current_revision ?? "No file yet"],
    ["Authorized for construction", track.released_revision ? `Rev ${track.released_revision}` : "None"],
    ["Lifecycle", track.lifecycle_label],
    ["Unit/Area/Block", track.area || "—"],
    ["Responsible engineer", drawing.responsible || "Unassigned"],
    ["Planned preparation", day(track.planned_date)],
    ["Planned client submission", day(track.planned_submission)],
    ["Planned approval", day(track.planned_approval)],
    ["Next required", track.required_date ? `${day(track.required_date)} · ${track.required_for}` : "—"],
    ["Pending with", track.pending_with.join(", ") || "—"],
    ["Open comments", `${track.open_comments}${track.client_comments ? ` (${track.client_comments} client)` : ""}`],
    ["Last updated", stamp(track.last_updated)],
  ];
  return (
    <div className="ed-track">
      <div className="ed-track-pills">
        <span>
          Preparation <Pill text={track.preparation_status} />
        </span>
        <span>
          Internal <Pill text={track.internal_status} />
        </span>
        <span>
          Client <Pill text={track.client_status} />
        </span>
        <span>
          Overall <Pill text={track.overall_status} />
        </span>
        <span>
          Release <Pill text={track.release_status} />
        </span>
      </div>
      <dl className="ed-facts">
        {facts.map(([name, value]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {track.overdue.length > 0 && (
        <div className="ed-overdue">
          {track.overdue.map((item) => (
            <p key={item.action}>
              <span className="ed-pill ed-red">{item.days}d overdue</span> <strong>{item.action}</strong> was due{" "}
              {day(item.due_date)} · waiting on {item.pending_with.join(", ")}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function OverviewCards({
  pid,
  drawing,
  people,
  onChange,
  onError,
}: {
  pid: number;
  drawing: Drawing;
  people: User[];
  onChange: (row: Drawing) => void;
  onError: (text: string) => void;
}) {
  const info = drawing.assignments;
  const [engineer, setEngineer] = useState(drawing.responsible_user_id ? String(drawing.responsible_user_id) : "");
  const [saving, setSaving] = useState(false);
  async function assign() {
    setSaving(true);
    try {
      const row = await api<Drawing>(`/projects/${pid}/drawings/${drawing.id}`, "PUT", {
        number: drawing.number,
        title: drawing.title,
        drawing_type: drawing.drawing_type || "General",
        category_id: drawing.category_id ?? null,
        discipline_id: drawing.discipline_id,
        company_id: drawing.company_id,
        responsible_user_id: engineer ? Number(engineer) : null,
        reviewer_id: drawing.reviewer_id ?? null,
        area_id: drawing.area_id ?? null,
        planned_date: drawing.planned_date,
        planned_submission: drawing.planned_submission ?? null,
        planned_approval: drawing.planned_approval ?? null,
        priority: drawing.priority,
        work_reference: drawing.work_reference || "",
        remarks: drawing.remarks || "",
        version: drawing.version,
      });
      onChange(row);
      onError("");
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }
  const details: [string, string][] = [
    ["Drawing number", drawing.number],
    ["Title", drawing.title],
    ["Discipline", drawing.discipline],
    ["Drawing type", drawing.drawing_type || "—"],
    ["Originator company", drawing.company || "—"],
    ["Unit/Area/Block", drawing.tracking?.area || "—"],
    ["Priority", drawing.priority],
    ["Source", drawing.provenance || "manual"],
    ["Work reference", drawing.work_reference || "—"],
    ["Register status", drawing.record_status || "Active"],
    ["Remarks", drawing.remarks || "—"],
  ];
  return (
    <div className="ed-overview">
      <article className="ed-block">
        <h3>Drawing information</h3>
        <dl className="ed-facts ed-facts-2">
          {details.map(([name, value]) => (
            <div key={name}>
              <dt>{name}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </article>
      <article className="ed-block">
        <h3>Assignments and review route</h3>
        <div className="ed-assign">
          <div className="ed-assign-row">
            <span className="ed-assign-label">Responsible engineer</span>
            {info?.can_assign ? (
              <div className="ed-assign-edit">
                <select aria-label="Responsible engineer" value={engineer} onChange={(e) => setEngineer(e.target.value)}>
                  <option value="">Unassigned</option>
                  {people.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="primary"
                  disabled={saving || engineer === (drawing.responsible_user_id ? String(drawing.responsible_user_id) : "")}
                  onClick={() => void assign()}
                >
                  {saving ? "Saving…" : "Save"}
                </button>
              </div>
            ) : (
              <strong>{info?.responsible?.name || "Unassigned"}</strong>
            )}
          </div>
          {!info?.responsible && (
            <p className="ed-hint">
              The responsible engineer prepares and uploads revisions and answers comments. The review policy assigns the
              reviewers below, not the preparer.
            </p>
          )}
          <div className="ed-assign-row ed-assign-top">
            <span className="ed-assign-label">Review route</span>
            {info?.review_route ? (
              <div>
                <small className="ed-sub">Policy for {info.review_route.applies_to}</small>
                <ol className="ed-route">
                  {info.review_route.stages.map((stage, index) => (
                    <li key={`${stage.name}-${index}`}>
                      <span className={`ed-pill ed-${stage.purpose === "client" ? "amber" : "blue"}`}>
                        {index + 1}. {stage.name || stage.purpose}
                      </span>
                      <strong>{stage.reviewers.join(", ") || "No reviewer"}</strong>
                      <small className="ed-sub">{stage.rule}</small>
                    </li>
                  ))}
                </ol>
              </div>
            ) : (
              <span className="ed-pill ed-red">{info?.review_route_missing || "No review policy"}</span>
            )}
          </div>
          <div className="ed-assign-row">
            <span className="ed-assign-label">Construction release</span>
            <strong>{info?.release_authority.join(", ") || "Nobody holds release permission for this discipline"}</strong>
          </div>
          <div className="ed-assign-row">
            <span className="ed-assign-label">Transmittals and client decisions</span>
            <strong>{info?.document_controllers.join(", ") || "Nobody holds transmittal permission"}</strong>
          </div>
        </div>
      </article>
    </div>
  );
}

function RevisionTracker({ revisions }: { revisions: Revision[] }) {
  if (revisions.length === 0) return <p className="muted">No revision has been uploaded yet.</p>;
  return (
    <div className="mp-table-wrap ed-rev-table">
      <table className="mp-table">
        <thead>
          <tr>
            <th>Rev</th>
            <th>File</th>
            <th>Uploaded</th>
            <th>Review</th>
            <th>Client outcome</th>
            <th>Construction release</th>
            <th>Open comments</th>
          </tr>
        </thead>
        <tbody>
          {[...revisions].reverse().map((revision) => (
            <tr key={revision.id}>
              <td>
                <strong>{revision.code}</strong>
              </td>
              <td>
                {revision.file_name || "—"}
                {revision.scan_status && revision.scan_status !== "available" ? (
                  <small className="ed-sub">File {revision.scan_status}</small>
                ) : null}
              </td>
              <td>
                {revision.created_by_name || "—"}
                <small className="ed-sub">{stamp(revision.prepared_at || null)}</small>
              </td>
              <td>
                <Pill text={revision.review_state} />
              </td>
              <td>
                {revision.client_outcome ? <Pill text={revision.client_outcome} /> : <span className="muted">—</span>}
                {revision.external_reviewer ? (
                  <small className="ed-sub">
                    {revision.external_reviewer}
                    {revision.decision_reference ? ` · ${revision.decision_reference}` : ""}
                  </small>
                ) : null}
              </td>
              <td>
                <Pill text={revision.release_state} />
                {revision.released_by_name ? (
                  <small className="ed-sub">
                    {revision.released_by_name} · {stamp(revision.released_at || null)}
                  </small>
                ) : null}
              </td>
              <td>{revision.comments.filter((row) => row.status !== "Closed").length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Timeline({ revisions }: { revisions: Revision[] }) {
  const events = revisions
    .flatMap((revision) => revision.events.map((event) => ({ ...event, code: revision.code })))
    .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "") || b.id - a.id);
  if (events.length === 0) return <p className="muted">No history has been recorded yet.</p>;
  return (
    <ol className="ed-timeline">
      {events.map((event) => (
        <li key={event.id} className={`ed-tl-${statusTone(event.kind)}`}>
          <div>
            <strong>{event.kind.replaceAll("_", " ")}</strong> · rev {event.code}
            {event.detail ? <p>{event.detail}</p> : null}
          </div>
          <small>
            {event.actor || "System"}
            <br />
            {stamp(event.created_at || null)}
          </small>
        </li>
      ))}
    </ol>
  );
}

function statusTone(kind: string) {
  if (["released"].includes(kind)) return "teal";
  if (["accepted", "accepted_with_comments", "client_decision"].includes(kind)) return "green";
  if (["rejected", "withdrawn"].includes(kind)) return "red";
  if (["returned", "superseded"].includes(kind)) return "orange";
  if (["submitted"].includes(kind)) return "amber";
  return "blue";
}

type SavedDrawingPolicy = {
  id: number;
  discipline_id: number | null;
  stages: { purpose: string; reviewers: { id: number; name: string }[] }[];
};

function PolicyForm({
  pid,
  people,
  disciplines,
  onError,
}: {
  pid: number;
  people: User[];
  disciplines: { id: number; name: string }[];
  onError: (text: string) => void;
}) {
  const [internal, setInternal] = useState(0);
  const [client, setClient] = useState(0);
  const [discipline, setDiscipline] = useState("");
  const [notice, setNotice] = useState("");
  const [savedTick, setSavedTick] = useState(0);
  const [saved, setSaved] = useState<SavedDrawingPolicy[]>([]);
  useEffect(() => {
    void api<SavedDrawingPolicy[]>(`/projects/${pid}/approval-policies?record_type=drawing.revision`)
      .then(setSaved)
      .catch(() => setSaved([]));
  }, [pid, savedTick]);
  function reviewerId(policy: SavedDrawingPolicy | undefined, purpose: string) {
    return policy?.stages.find((stage) => stage.purpose === purpose)?.reviewers[0]?.id || 0;
  }
  useEffect(() => {
    const wanted = discipline ? Number(discipline) : null;
    const match =
      saved.find((row) => row.discipline_id === wanted) ||
      saved.find((row) => row.discipline_id == null) ||
      saved[0];
    setInternal(reviewerId(match, "internal"));
    setClient(reviewerId(match, "client"));
  }, [saved, discipline]);
  function reviewerNames(policy: SavedDrawingPolicy, purpose: string) {
    return policy.stages.find((stage) => stage.purpose === purpose)?.reviewers.map((row) => row.name).join(", ") || "";
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api(`/projects/${pid}/approval-policies`, "POST", {
        record_type: "drawing.revision",
        discipline_id: discipline ? Number(discipline) : null,
        allow_self_approval: false,
        stages: [
          { name: "Internal", rule: "all", purpose: "internal", reviewer_ids: [internal] },
          ...(client
            ? [{ name: "Client", rule: "all", purpose: "client", reviewer_ids: [client] }]
            : []),
        ],
      });
      onError("");
      setNotice("Drawing policy saved.");
      setSavedTick((value) => value + 1);
    } catch (err) {
      setNotice("");
      onError((err as Error).message);
    }
  }
  return (
    <form className="panel option-grid" onSubmit={save}>
      <h3>Review policy</h3>
      <div className="policy-saved">
        <h3>Saved policy</h3>
        {saved.length === 0 ? (
          <p className="muted">No drawing review policy is saved yet.</p>
        ) : (
          saved.map((policy) => (
            <dl key={policy.id}>
              <dt>Internal reviewer</dt>
              <dd>{reviewerNames(policy, "internal") || "Not set"}</dd>
              <dt>Client reviewer</dt>
              <dd>{reviewerNames(policy, "client") || "No client review"}</dd>
              <dt>Discipline</dt>
              <dd>{disciplines.find((row) => row.id === policy.discipline_id)?.name || "All disciplines"}</dd>
            </dl>
          ))
        )}
        {notice ? <p>{notice}</p> : null}
      </div>
      <p className="muted">Pick the reviewers and save. The saved names above are the ones who approve.</p>
      <label>
        Internal reviewer
        <select required aria-label="Internal reviewer" value={internal || ""} onChange={(e) => setInternal(Number(e.target.value))}>
          <option value="">Select reviewer</option>
          {people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Client reviewer
        <select aria-label="Client reviewer" value={client || ""} onChange={(e) => setClient(Number(e.target.value))}>
          <option value="">No client review</option>
          {people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Discipline
        <select aria-label="Policy discipline" value={discipline} onChange={(e) => setDiscipline(e.target.value)}>
          <option value="">All disciplines</option>
          {disciplines.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <button className="primary">Save drawing policy</button>
    </form>
  );
}

function CreateForm({
  pid,
  session,
  disciplines,
  categories,
  companies,
  people,
  areas,
  onCreated,
  onError,
}: {
  pid: number;
  session: Session;
  disciplines: { id: number; name: string }[];
  categories: Category[];
  companies: Company[];
  people: User[];
  areas: Area[];
  onCreated: (row: Drawing) => void;
  onError: (text: string) => void;
}) {
  const [number, setNumber] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("General");
  const [categoryId, setCategoryId] = useState(0);
  const [discipline, setDiscipline] = useState(0);
  const [company, setCompany] = useState(session.user.company_id || 0);
  const [owner, setOwner] = useState(0);
  const [reviewer, setReviewer] = useState(0);
  const [area, setArea] = useState(0);
  const [planned, setPlanned] = useState("");
  const [submission, setSubmission] = useState("");
  const [approval, setApproval] = useState("");
  const [priority, setPriority] = useState("Normal");
  const [reference, setReference] = useState("");
  const [remarks, setRemarks] = useState("");
  const choices = categories.filter((row) => row.discipline_id === discipline);
  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      const row = await api<Drawing>(`/projects/${pid}/drawings`, "POST", {
        number,
        title,
        drawing_type: kind,
        category_id: categoryId || null,
        discipline_id: discipline,
        company_id: company,
        responsible_user_id: owner || null,
        reviewer_id: reviewer || null,
        area_id: area || null,
        planned_date: planned || null,
        planned_submission: submission || null,
        planned_approval: approval || null,
        priority,
        work_reference: reference,
        remarks,
      });
      setNumber("");
      setTitle("");
      onError("");
      onCreated(row);
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <form className="panel option-grid" onSubmit={save}>
      <h3>New drawing</h3>
      <label>
        Drawing number
        <input required aria-label="Drawing number" placeholder="Number" value={number} onChange={(e) => setNumber(e.target.value)} />
      </label>
      <label>
        Drawing title
        <input required aria-label="Drawing title" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Discipline
        <select required aria-label="Drawing discipline" value={discipline || ""} onChange={(e) => { setDiscipline(Number(e.target.value)); setCategoryId(0); }}>
          <option value="">Select discipline</option>
          {disciplines.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Category
        <select
          aria-label="Drawing category"
          value={categoryId || ""}
          onChange={(e) => {
            const id = Number(e.target.value);
            setCategoryId(id);
            const found = choices.find((row) => row.id === id);
            if (found) setKind(found.name);
          }}
        >
          <option value="">Select category</option>
          {choices.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Originating company
        <select required aria-label="Originator company" value={company || ""} onChange={(e) => setCompany(Number(e.target.value))}>
          <option value="">Select company</option>
          {companies.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Responsible engineer
        <select aria-label="Responsible engineer" value={owner || ""} onChange={(e) => setOwner(Number(e.target.value))}>
          <option value="">Select engineer</option>
          {people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Reviewer
        <select aria-label="Reviewer" value={reviewer || ""} onChange={(e) => setReviewer(Number(e.target.value))}>
          <option value="">No reviewer</option>
          {people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Location
        <select aria-label="Location" value={area || ""} onChange={(e) => setArea(Number(e.target.value))}>
          <option value="">No location</option>
          {areas.map((row) => (
            <option key={row.id} value={row.id}>
              {row.code} · {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Planned preparation
        <input aria-label="Planned preparation date" type="date" value={planned} onChange={(e) => setPlanned(e.target.value)} />
      </label>
      <label>
        Planned client submission
        <input aria-label="Planned client submission" type="date" value={submission} onChange={(e) => setSubmission(e.target.value)} />
      </label>
      <label>
        Planned approval
        <input aria-label="Planned approval" type="date" value={approval} onChange={(e) => setApproval(e.target.value)} />
      </label>
      <label>
        Priority
        <select aria-label="Priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
          {["Low", "Normal", "High", "Critical"].map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </label>
      <label>
        Work reference
        <input aria-label="Work reference" placeholder="Optional" value={reference} onChange={(e) => setReference(e.target.value)} />
      </label>
      <label>
        Remarks
        <input aria-label="Remarks" placeholder="Optional" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
      </label>
      <button className="primary">Create drawing</button>
    </form>
  );
}

function ImportForm({
  pid,
  onDone,
  onError,
  onRegister,
}: {
  pid: number;
  onDone: () => void;
  onError: (text: string) => void;
  onRegister?: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("create");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [result, setResult] = useState<ImportReport | null>(null);
  const [locationMappings, setLocationMappings] = useState<Record<string, number>>({});
  const [hiddenColumns, setHiddenColumns] = useState<string[]>([]);
  const [mappingDirty, setMappingDirty] = useState(false);
  const [sortColumn, setSortColumn] = useState("row");
  const [sortAscending, setSortAscending] = useState(true);
  const [rowFilter, setRowFilter] = useState("");
  async function send(dryRun: boolean) {
    if (!file) return;
    const body = new FormData();
    body.set("upload", file);
    body.set("dry_run", dryRun ? "true" : "false");
    body.set("mode", mode);
    body.set("location_mappings", JSON.stringify(locationMappings));
    setBusy(true);
    setProblem("");
    try {
      const report = await postForm<ImportReport>(`/projects/${pid}/drawing-imports`, body);
      setResult(report);
      setMappingDirty(false);
      if (!dryRun && (report.created.length || (report.updated?.length || 0))) onDone();
      onError("");
    } catch (err) {
      setResult(null);
      setProblem((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function template() {
    try { await downloadFile(`/projects/${pid}/drawing-imports/template`, "drawing-import-template.xlsx"); }
    catch(err) { setProblem((err as Error).message); }
  }
  const valid = result ? result.created.length + (result.updated?.length || 0) : 0;
  const imported = result && !result.preview;
  const displayRows = [...(result?.rows || [])].filter(r => !rowFilter || [r.number, r.title, r.outcome, r.reason, ...Object.values(r.values || {})].some(v => String(v).toLowerCase().includes(rowFilter.toLowerCase()))).sort((a,b) => {
    const val = (r: ImportReport["rows"][number]) => sortColumn === "row" ? String(r.row).padStart(10,"0") : sortColumn === "outcome" ? r.outcome : sortColumn === "reason" ? r.reason : r.values?.[sortColumn] || "";
    return (sortAscending ? 1 : -1) * val(a).localeCompare(val(b),undefined,{numeric:true});
  });
  const unknownLocations = result ? [...new Set(result.rows.filter(r => r.outcome === "conflict" && /Location '.*' was not found/.test(r.reason)).map(r => String(r.values?.location || "")).filter(Boolean))] : [];
  function exportErrors() {
    if (!result) return;
    const csv = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const cols = ["row", ...result.columns, "outcome", "reason"];
    const lines = [cols.map(csv).join(","), ...result.rows.filter(r => r.outcome === "conflict").map(r => cols.map(c => csv(c === "row" ? r.row : c === "outcome" ? r.outcome : c === "reason" ? r.reason : r.values?.[c])).join(","))];
    const url = URL.createObjectURL(new Blob(["\uFEFF" + lines.join("\r\n")], {type: "text/csv;charset=utf-8"}));
    const a = document.createElement("a"); a.href = url; a.download = "drawing-import-errors.csv"; a.click(); URL.revokeObjectURL(url);
  }
  return (
    <form
      className="panel ed-import"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        void send(true);
      }}
    >
      <div className="ed-import-head">
        <h3>Import drawings</h3>
        <button type="button" className="ed-link" onClick={() => void template()}>
          Download project Excel template
        </button>
      </div>
      <p className="muted">
        Upload a .csv or .xlsx file with a header row. Required columns: <strong>number</strong>, <strong>title</strong>,{" "}
        <strong>discipline</strong>. Optional: type, company (blank uses your company), responsible (email or name),
        location (area code or name), planned_date, planned_submission, planned_approval (YYYY-MM-DD or DD/MM/YYYY),
        priority, work_reference, remarks. Headers such as "Drawing Number" or "Drawing Title" also work. Preview first;
        nothing is saved until you confirm.
      </p>
      <div className="ed-import-row">
        <label>
          Import file
          <input
            aria-label="Drawing import file"
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setResult(null);
              setLocationMappings({});
              setMappingDirty(false);
              setProblem("");
            }}
          />
        </label>
        <label>
          Duplicate handling
          <select aria-label="Import mode" value={mode} onChange={(e) => {setMode(e.target.value); setResult(null);}}>
            <option value="create">Skip or reject duplicates</option>
            <option value="update">Update existing register fields</option>
          </select>
        </label>
        <button className="primary" disabled={!file || busy}>
          {busy ? "Reading…" : "Preview"}
        </button>
        {result?.preview && !mappingDirty && valid > 0 && (
          <button type="button" className="tone-approve" disabled={busy} onClick={() => void send(false)}>
            Import {valid} valid row{valid === 1 ? "" : "s"}
          </button>
        )}
      </div>
      {problem && (
        <div role="alert" className="error">
          {problem}
        </div>
      )}
      {result && (
        <>
          <div className="ed-import-summary">
            <span className="ed-pill ed-blue">Total: {result.total ?? result.rows.length}</span>
            <span className="ed-pill ed-green">Valid: {result.valid ?? valid}</span>
            <span className="ed-pill ed-red">Invalid: {result.invalid ?? result.conflicts.length}</span>
            <span className="ed-pill ed-green">Successfully imported: {imported ? result.created.length + (result.updated?.length || 0) : 0}</span>
            <span className="ed-pill ed-red">Failed: {imported ? result.conflicts.length : 0}</span>
            <span className="ed-pill ed-grey">Duplicates: {result.duplicates ?? result.skipped.length}</span>
            {!!result.conflicts.length && <button type="button" onClick={exportErrors}>Download error CSV</button>}
            {imported && <span className="mp-ok">Backend confirmed saved rows.</span>}
            {imported && onRegister && <button type="button" onClick={onRegister}>Open register</button>}
          </div>
          {!!result.unsupported_columns?.length && <p role="alert" className="muted">Unsupported columns (not saved): {result.unsupported_columns.join(", ")}</p>}
          {unknownLocations.length > 0 && <div className="ed-location-mapping">
            <strong>Map unknown Excel locations to active project locations</strong>
            <p className="muted">Selections are project-scoped and must be revalidated before importing. No locations are automatically created.</p>
            {unknownLocations.map(name => <label key={name}>{name}
              <select value={locationMappings[name.toLowerCase()] || ""} onChange={e => {setLocationMappings(prev => ({...prev, [name.toLowerCase()]: Number(e.target.value)})); setMappingDirty(true);}}>
                <option value="">Choose existing location</option>
                {(result.areas || []).map(a => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
              </select>
            </label>)}
            <button type="button" onClick={() => void send(true)} disabled={busy}>Revalidate mapping</button>
          </div>}
          <label>Filter preview rows <input aria-label="Filter import rows" value={rowFilter} onChange={e => setRowFilter(e.target.value)} placeholder="Search any column" /></label>
          <div className="ed-column-options"><strong>Visible columns</strong>{["row", ...result.columns, "outcome", "reason"].map(c => <label key={c}><input type="checkbox" checked={!hiddenColumns.includes(c)} onChange={e => setHiddenColumns(prev => e.target.checked ? prev.filter(x => x !== c) : [...prev, c])}/>{c.replaceAll("_", " ")}</label>)}</div>
          {result.rows.length === 0 ? <p className="muted">No data rows found.</p> :
          <div className="mp-table-wrap ed-import-table-wrap" role="region" aria-label="Drawing import preview" tabIndex={0}>
            <table className="mp-table ed-import-grid">
              <thead><tr>{["row", ...result.columns, "outcome", "reason"].filter(c => !hiddenColumns.includes(c)).map(c => <th key={c}><button type="button" className="ed-sort-heading" onClick={() => {setSortColumn(c);setSortAscending(sortColumn === c ? !sortAscending : true);}}>{c === "outcome" ? "Result" : c === "reason" ? "Validation error" : c.replaceAll("_", " ")}{sortColumn === c ? (sortAscending ? " ↑" : " ↓") : ""}</button></th>)}</tr></thead>
              <tbody>{displayRows.map(r => <tr key={r.row}>{["row", ...result.columns, "outcome", "reason"].filter(c => !hiddenColumns.includes(c)).map(c => <td key={c}>{c === "row" ? r.row : c === "outcome" ? IMPORT_LABEL[r.outcome] || r.outcome : c === "reason" ? r.reason || "—" : r.values?.[c] || (c === "number" ? r.number : c === "title" ? r.title : "—")}</td>)}</tr>)}</tbody>
            </table>
          </div>}
        </>
      )}
    </form>
  );
}

type ImportReport = {
  created: string[];
  updated?: string[];
  skipped: string[];
  conflicts: { row: number; number: string; reason: string }[];
  rows: { row: number; number: string; title: string; outcome: string; reason: string; values?: Record<string,string> }[];
  total?: number;
  valid?: number;
  invalid?: number;
  duplicates?: number;
  areas?: {id:number;code:string;name:string}[];
  unsupported_columns?: string[];
  columns: string[];
  preview: boolean;
};
const IMPORT_COLUMNS = [
  "number",
  "title",
  "type",
  "discipline",
  "company",
  "responsible",
  "location",
  "planned_date",
  "planned_submission",
  "planned_approval",
  "priority",
  "work_reference",
  "remarks",
];
const IMPORT_TONE: Record<string, string> = { created: "green", updated: "blue", skipped: "grey", conflict: "red" };
const IMPORT_LABEL: Record<string, string> = {
  created: "Create",
  updated: "Update",
  skipped: "Already exists",
  conflict: "Problem",
};

const DETAIL_TABS = [
  "Overview",
  "Revisions & Files",
  "Reviews & Comments",
  "Transmittals",
  "Construction Release",
  "Materials (MTO)",
  "History",
] as const;

function CommentList({
  pid,
  drawingId,
  comments,
  onChange,
  onError,
}: {
  pid: number;
  drawingId: number;
  comments: Comment[];
  onChange: (row: Drawing) => void;
  onError: (text: string) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  function draft(key: string) {
    return drafts[key] || "";
  }
  async function send(path: string, body: Record<string, unknown>) {
    try {
      await api(path, "POST", body);
      onChange(await api<Drawing>(`/projects/${pid}/drawings/${drawingId}`));
      onError("");
      setNote("");
    } catch (err) {
      const message = (err as Error).message;
      setNote(message);
      onError(message);
    }
  }
  if (comments.length === 0) return <p className="muted">No comments on this revision.</p>;
  return (
    <div>
      {comments.map((comment) => {
        const number = comment.comment_number || comment.id;
        const owner = comment.owner_name || "the assigned engineer";
        return (
          <article
            key={comment.id}
            className={`comment-card severity-${(comment.severity || "normal").toLowerCase()} status-${(comment.status || "open").toLowerCase()}`}
          >
            <p>
              <strong>#{number}</strong> {comment.stage || "Internal"} · {comment.severity} · {comment.status}
              {comment.page_ref ? ` · p. ${comment.page_ref}` : ""}
            </p>
            <p>{comment.body}</p>
            <p className="muted">
              Assigned to {owner}
              {comment.raised_by ? `. Raised by ${comment.raised_by}` : ""}.
            </p>
            {comment.response ? <p>Response: {comment.response}</p> : null}
            {comment.closure_evidence ? <p>Closed: {comment.closure_evidence}</p> : null}
            {comment.can_respond && (
              <>
                <textarea
                  aria-label={`Response to comment ${number}`}
                  placeholder="What changed, or why the comment stands"
                  value={draft(`respond-${comment.id}`)}
                  onChange={(e) => setDrafts({ ...drafts, [`respond-${comment.id}`]: e.target.value })}
                />
                <button
                  className="tone-note"
                  disabled={!draft(`respond-${comment.id}`).trim()}
                  onClick={() =>
                    void send(`/projects/${pid}/comments/${comment.id}/respond`, {
                      response: draft(`respond-${comment.id}`).trim(),
                      version: comment.version,
                    })
                  }
                >
                  Respond
                </button>
              </>
            )}
            {comment.can_close && (
              <>
                <textarea
                  aria-label={`Closure for comment ${number}`}
                  placeholder="Evidence that this comment is closed"
                  value={draft(`close-${comment.id}`)}
                  onChange={(e) => setDrafts({ ...drafts, [`close-${comment.id}`]: e.target.value })}
                />
                <button
                  className="tone-approve"
                  disabled={!draft(`close-${comment.id}`).trim()}
                  onClick={() =>
                    void send(`/projects/${pid}/comments/${comment.id}/close`, {
                      evidence: draft(`close-${comment.id}`).trim(),
                      version: comment.version,
                    })
                  }
                >
                  Close
                </button>
              </>
            )}
            {!comment.can_respond && !comment.can_close && comment.status !== "Closed" && (
              <p className="muted">{owner} can respond. The reviewer who raised it can close it.</p>
            )}
          </article>
        );
      })}
      {note ? <p className="error">{note}</p> : null}
    </div>
  );
}

function DrawingDetail({
  pid,
  drawing,
  people,
  companies,
  userId,
  initialTab = "Overview",
  onChange,
  onError,
}: {
  pid: number;
  drawing: Drawing;
  people: User[];
  companies: Company[];
  userId: number;
  initialTab?: string;
  onChange: (row: Drawing) => void;
  onError: (text: string) => void;
}) {
  const [tab, setTab] = useState<(typeof DETAIL_TABS)[number]>(
    DETAIL_TABS.includes(initialTab as (typeof DETAIL_TABS)[number])
      ? (initialTab as (typeof DETAIL_TABS)[number])
      : "Overview",
  );
  const [code, setCode] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [reason, setReason] = useState("");
  const [pageRef, setPageRef] = useState("");
  const [body, setBody] = useState("");
  const [severity, setSeverity] = useState("Minor");
  const owners =
    drawing.responsible_user_id &&
    !people.some((person) => person.id === drawing.responsible_user_id)
      ? [
          ...people,
          {
            id: drawing.responsible_user_id,
            name: drawing.responsible || "Responsible engineer",
            email: "",
            company_id: drawing.company_id,
            active: true,
            organization_admin: false,
          },
        ]
      : people;
  const [commentOwner, setCommentOwner] = useState(drawing.responsible_user_id || owners[0]?.id || 0);
  const [due, setDue] = useState("");
  async function run(work: () => Promise<Drawing>) {
    try {
      onChange(await work());
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <section className="panel ed-detail">
      <div className="ed-detail-head">
        <div>
          <h2>
            {drawing.number} · {drawing.title}
          </h2>
          <p className="muted">
            {drawing.discipline} · {drawing.drawing_type} · {drawing.company} · priority {drawing.priority} · source{" "}
            {drawing.provenance || "manual"}
            {drawing.work_reference ? ` · work ${drawing.work_reference}` : ""}
          </p>
        </div>
      </div>
      {drawing.record_status === "Cancelled" && (
        <p className="ed-note">
          This drawing is cancelled{drawing.cancellation_reason ? `: ${drawing.cancellation_reason}` : ""}. It is not in review.
        </p>
      )}
      <DrawingTracking drawing={drawing} />
      <div className="ed-subtabs">
        {DETAIL_TABS.map((name) => (
          <button key={name} type="button" aria-pressed={tab === name} className={tab === name ? "is-on" : ""} onClick={() => setTab(name)}>
            {name}
          </button>
        ))}
      </div>
      {tab === "Revisions & Files" && <RevisionTracker revisions={drawing.revisions || []} />}
      {tab === "History" && <Timeline revisions={drawing.revisions || []} />}
      {tab === "Materials (MTO)" && (
        <MaterialsTab
          pid={pid}
          drawingId={drawing.id}
          revisions={drawing.revisions || []}
          userId={userId}
          onError={onError}
        />
      )}
      {tab === "Overview" && (
        <div className="ed-actions">
          {drawing.actions?.includes("start_preparation") && (
            <button
              type="button"
              className="primary"
              onClick={() =>
                void run(() =>
                  api<Drawing>(`/projects/${pid}/drawings/${drawing.id}/preparation`, "POST", {
                    version: drawing.version,
                  }),
                )
              }
            >
              Start preparation
            </button>
          )}
          {drawing.actions?.includes("add_revision") && (
            <button type="button" className="tone-submit" onClick={() => setTab("Revisions & Files")}>
              Upload a revision
            </button>
          )}
          {drawing.record_status !== "Cancelled" && drawing.assignments?.can_assign && (
            <button
              type="button"
              className="ed-danger"
              onClick={() => {
                const reason = window.prompt("Cancellation reason");
                if (!reason) return;
                void run(() =>
                  api<Drawing>(`/projects/${pid}/drawings/${drawing.id}/cancel`, "POST", {
                    reason,
                    version: drawing.version,
                  }),
                );
              }}
            >
              Cancel drawing
            </button>
          )}
        </div>
      )}
      {tab === "Overview" && <OverviewCards pid={pid} drawing={drawing} people={people} onChange={onChange} onError={onError} />}
      {tab === "Revisions & Files" && drawing.actions?.includes("add_revision") && (
        <form
          className="toolbar"
          onSubmit={(e) => {
            e.preventDefault();
            if (!file) return;
            const data = new FormData();
            data.set("code", code);
            data.set("upload", file);
            void run(() => postForm<Drawing>(`/projects/${pid}/drawings/${drawing.id}/revisions`, data));
          }}
        >
          <input required aria-label="Revision code" placeholder="Revision code" value={code} onChange={(e) => setCode(e.target.value)} />
          <input
            required
            aria-label="Revision file"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <button className="primary">Add revision</button>
        </form>
      )}
      {tab === "Transmittals" && (
        <TransmittalForm pid={pid} drawing={drawing} people={people} companies={companies} userId={userId} onError={onError} />
      )}
      {tab === "Reviews & Comments" && (drawing.revisions || []).length === 0 && (
        <p>
          No revision has been submitted, so there is nothing to approve yet.
          {drawing.actions?.includes("start_preparation")
            ? " Start preparation on Overview, add a revision on Revisions & Files, then submit it."
            : " The engineer adds a revision and submits it. Approve, Approve with comments, and Return then appear for the saved reviewer."}
        </p>
      )}
      {tab !== "Overview" && tab !== "Transmittals" && tab !== "History" && [...(drawing.revisions || [])].reverse().map((revision) => (
        <article key={revision.id} className="ed-rev-card">
          <h3>
            Rev {revision.code}{" "}
            <span className={`state-pill state-${revision.review_state.toLowerCase().replaceAll(" ", "-")}`}>
              {revision.review_state}
            </span>{" "}
            <span className={`state-pill state-${revision.release_state.toLowerCase().replaceAll(" ", "-")}`}>
              {revision.release_state}
            </span>
          </h3>
          <p className="muted">{revision.file_name}</p>
          {(tab === "Revisions & Files" || tab === "Construction Release") &&
            (revision.actions.includes("release") || revision.actions.includes("withdraw")) && (
            <input aria-label="Release or withdrawal note" placeholder="Note, required to withdraw" value={reason} onChange={(e) => setReason(e.target.value)} />
          )}
          {tab === "Revisions & Files" && (
          <button
            onClick={() =>
              void downloadFile(
                `/projects/${pid}/drawings/${drawing.id}/revisions/${revision.id}/file`,
                revision.file_name || `${revision.code}.pdf`,
              ).catch((err) => onError((err as Error).message))
            }
          >
            Download file
          </button>
          )}
          {(tab === "Revisions & Files" || tab === "Construction Release") && (
          <div className="inline">
            {revision.actions.includes("submit") && (
              <button
                className="tone-submit"
                onClick={() =>
                  void run(() =>
                    api<Drawing>(`/projects/${pid}/drawings/${drawing.id}/revisions/${revision.id}/submit`, "POST"),
                  )
                }
              >
                Submit for review
              </button>
            )}
            {revision.actions.includes("release") && (
              <button
                className="tone-approve"
                onClick={() =>
                  void run(() =>
                    api<Drawing>(`/projects/${pid}/drawings/${drawing.id}/revisions/${revision.id}/release`, "POST", {
                      version: revision.version,
                      reason,
                    }),
                  )
                }
              >
                Release for construction
              </button>
            )}
            {revision.actions.includes("withdraw") && (
              <button
                className="tone-withdraw"
                onClick={() =>
                  void run(() =>
                    api<Drawing>(`/projects/${pid}/drawings/${drawing.id}/revisions/${revision.id}/withdraw`, "POST", {
                      version: revision.version,
                      reason,
                    }),
                  )
                }
              >
                Withdraw
              </button>
            )}
          </div>
          )}
          {tab === "Reviews & Comments" && !revision.review && (
            <>
              <p>Revision {revision.code} has not been submitted for review.</p>
              {revision.actions.includes("submit") && (
                <button
                  className="tone-submit"
                  onClick={() =>
                    void run(() =>
                      api<Drawing>(`/projects/${pid}/drawings/${drawing.id}/revisions/${revision.id}/submit`, "POST"),
                    )
                  }
                >
                  Submit for review
                </button>
              )}
            </>
          )}
          {tab === "Reviews & Comments" && revision.review && (
            <>
              <p>{reviewStatus(drawing, revision)}</p>
              {(revision.review.chain || []).length > 0 && (
                <ol className="review-chain">
                  {(revision.review.chain || []).map((step) => (
                    <li key={`${step.purpose}-${step.name}`} className={`review-step ${step.status}`}>
                      <strong>{step.name || step.purpose}</strong>
                      <span>{step.reviewers.map((person) => person.name).join(", ") || "No reviewer"}</span>
                      <em>{stepLabel(step.status)}</em>
                    </li>
                  ))}
                </ol>
              )}
              <ul className="decisions">
                {revision.review.decisions.map((decision) => (
                  <li key={decision.id} className={`decision decision-${decision.action}`}>
                    {decision.reviewer_name ? `${decision.reviewer_name}: ` : ""}
                    {label(decision.action)}
                    {decision.reason ? `: ${decision.reason}` : ""}
                  </li>
                ))}
              </ul>
              {revision.review.actions.length > 0 && (
                <>
                <input aria-label="Decision reason" placeholder="Reason, required for Reject, Return, and Approve with comments" value={reason} onChange={(e) => setReason(e.target.value)} />
                <div className="inline decision-actions">
                  {revision.review.actions.map((action) => (
                    <button
                      key={action}
                      className={actionClass(action)}
                      onClick={() => {
                        if (
                          (action === "reject" || action === "return" || action === "approve_with_comments") &&
                          !reason.trim()
                        ) {
                          onError("Type the reason in the note box, then choose Reject, Return, or Approve with comments.");
                          return;
                        }
                        void run(() =>
                          api<Drawing>(`/reviews/${revision.review!.id}/decisions`, "POST", {
                            action,
                            reason,
                            version: revision.review!.version,
                          }).then(() => api<Drawing>(`/projects/${pid}/drawings/${drawing.id}`)),
                        );
                      }}
                    >
                      {label(action)}
                    </button>
                  ))}
                </div>
                </>
              )}
            </>
          )}
          {tab === "Reviews & Comments" && (
            <CommentList
              pid={pid}
              drawingId={drawing.id}
              comments={revision.comments}
              onChange={onChange}
              onError={onError}
            />
          )}
          {tab === "Reviews & Comments" && revision.actions.includes("comment") && (
            <form
              className="toolbar"
              onSubmit={(e) => {
                e.preventDefault();
                void api(`/projects/${pid}/drawings/${drawing.id}/revisions/${revision.id}/comments`, "POST", {
                  page_ref: pageRef,
                  body,
                  severity,
                  owner_id: commentOwner,
                  due_date: due || null,
                })
                  .then(() => api<Drawing>(`/projects/${pid}/drawings/${drawing.id}`))
                  .then(onChange)
                  .catch((err) => onError((err as Error).message));
              }}
            >
              <input aria-label="Page reference" placeholder="Page or reference" value={pageRef} onChange={(e) => setPageRef(e.target.value)} />
              <input required aria-label="Comment" placeholder="Comment" value={body} onChange={(e) => setBody(e.target.value)} />
              <select aria-label="Severity" value={severity} onChange={(e) => setSeverity(e.target.value)}>
                {["Blocking", "Major", "Minor"].map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
              <select aria-label="Comment owner" value={commentOwner || ""} onChange={(e) => setCommentOwner(Number(e.target.value))}>
                {owners.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.name}
                  </option>
                ))}
              </select>
              <input aria-label="Comment due date" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
              <button>Add comment</button>
            </form>
          )}
        </article>
      ))}
    </section>
  );
}

type SentTransmittal = {
  id: number;
  number: string;
  purpose: string;
  status: string;
  revision_ids: number[];
  recipients: { user_id: number; acknowledged_at: string | null }[];
};

function TransmittalForm({
  pid,
  drawing,
  people,
  companies,
  userId,
  onError,
}: {
  pid: number;
  drawing: Drawing | null;
  people: User[];
  companies: Company[];
  userId: number;
  onError: (text: string) => void;
}) {
  const [number, setNumber] = useState("");
  const [purpose, setPurpose] = useState("Review");
  const [issued, setIssued] = useState("");
  const [expected, setExpected] = useState("");
  const [method, setMethod] = useState("");
  const [externalRef, setExternalRef] = useState("");
  const [senderCompany, setSenderCompany] = useState(0);
  const [recipientCompany, setRecipientCompany] = useState(0);
  const [recipient, setRecipient] = useState(0);
  const [revision, setRevision] = useState(0);
  const [status, setStatus] = useState("");
  const [sent, setSent] = useState<SentTransmittal[]>([]);
  async function loadSent() {
    setSent(await api<SentTransmittal[]>(`/projects/${pid}/transmittals`));
  }
  useEffect(() => {
    void loadSent().catch((err) => onError((err as Error).message));
  }, [pid]);
  async function create(e: FormEvent) {
    e.preventDefault();
    try {
      const row = await api<{ id: number; status: string; version: number; revision_ids: number[] }>(
        `/projects/${pid}/transmittals`,
        "POST",
        {
          number,
          purpose,
          issue_date: issued,
          revision_ids: [revision],
          recipient_ids: [recipient],
          sender_company_id: senderCompany || null,
          recipient_company_id: recipientCompany || null,
          expected_response: expected || null,
          method,
          external_reference: externalRef,
        },
      );
      const dispatched = await api<SentTransmittal>(
        `/projects/${pid}/transmittals/${row.id}/dispatch`,
        "POST",
        { version: row.version },
      );
      setStatus(
        `${dispatched.status}. Pinned revisions ${dispatched.revision_ids.join(", ")}. Acknowledgement is separate from acceptance.`,
      );
      await loadSent();
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <form className="panel option-grid" onSubmit={create}>
      <h3>Drawing transmittal</h3>
      <p className="muted">Recording a transmittal does not send email. Dispatch records issue. It does not accept or release the revision.</p>
      <label>
        Transmittal number
        <input required aria-label="Transmittal number" placeholder="Number" value={number} onChange={(e) => setNumber(e.target.value)} />
      </label>
      <label>
        Purpose
        <input required aria-label="Submission purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)} />
      </label>
      <label>
        Issue date
        <input required aria-label="Issue date" type="date" value={issued} onChange={(e) => setIssued(e.target.value)} />
      </label>
      <label>
        Expected response
        <input aria-label="Expected response" type="date" value={expected} onChange={(e) => setExpected(e.target.value)} />
      </label>
      <label>
        Method
        <input aria-label="Submission method" placeholder="Method" value={method} onChange={(e) => setMethod(e.target.value)} />
      </label>
      <label>
        External reference
        <input aria-label="External reference" placeholder="External reference" value={externalRef} onChange={(e) => setExternalRef(e.target.value)} />
      </label>
      <label>
        Sender company
        <select aria-label="Sender company" value={senderCompany || ""} onChange={(e) => setSenderCompany(Number(e.target.value))}>
          <option value="">Select company</option>
          {companies.map((row) => (
            <option key={row.id} value={row.id}>{row.name}</option>
          ))}
        </select>
      </label>
      <label>
        Recipient company
        <select aria-label="Recipient company" value={recipientCompany || ""} onChange={(e) => setRecipientCompany(Number(e.target.value))}>
          <option value="">Select company</option>
          {companies.map((row) => (
            <option key={row.id} value={row.id}>{row.name}</option>
          ))}
        </select>
      </label>
      <label>
        Revision
        <select required aria-label="Pinned revision" value={revision || ""} onChange={(e) => setRevision(Number(e.target.value))}>
          <option value="">Select revision</option>
          {(drawing?.revisions || []).map((row) => (
            <option key={row.id} value={row.id}>
              {drawing?.number} rev {row.code}
            </option>
          ))}
        </select>
      </label>
      <label>
        Recipient
        <select required aria-label="Recipient" value={recipient || ""} onChange={(e) => setRecipient(Number(e.target.value))}>
          <option value="">Select recipient</option>
          {people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>
      <button className="primary">Issue transmittal</button>
      {status ? <p className="muted">{status}</p> : null}
      <ul>
        {sent.map((row) => {
          const mine = row.recipients.find((item) => item.user_id === userId);
          return (
            <li key={row.id}>
              {row.number}: {row.status}. Purpose {row.purpose}. Pinned revisions {row.revision_ids.join(", ")}.
              {mine && !mine.acknowledged_at && row.status !== "Draft" && (
                <button
                  type="button"
                  onClick={() =>
                    void api<SentTransmittal>(`/projects/${pid}/transmittals/${row.id}/acknowledge`, "POST")
                      .then(async (updated) => {
                        setStatus(`${updated.number} is ${updated.status}. Receipt is not technical acceptance.`);
                        await loadSent();
                      })
                      .catch((err) => onError((err as Error).message))
                  }
                >
                  Acknowledge
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </form>
  );
}

function WrenchPanel({
  pid,
  drawing,
  admin,
  onError,
}: {
  pid: number;
  drawing: Drawing | null;
  admin: boolean;
  onError: (text: string) => void;
}) {
  const [spec, setSpec] = useState("");
  const [label, setLabel] = useState("");
  const [external, setExternal] = useState("");
  const [note, setNote] = useState("Synchronization is disabled.");
  useEffect(() => {
    void api<{ status: string; specification: string; credential_label: string }>(`/projects/${pid}/wrench`).then((row) => {
      setSpec(row.specification);
      setLabel(row.credential_label);
      setNote("Synchronization is disabled. Manual drawings and imports remain available.");
    });
  }, [pid]);
  return (
    <section className="panel">
      <h3>Wrench</h3>
      <p className="muted">{note}</p>
      {admin && (
        <form
          className="toolbar"
          onSubmit={(e) => {
            e.preventDefault();
            void api(`/projects/${pid}/wrench`, "PUT", {
              enabled: false,
              specification: spec,
              credential_label: label,
            })
              .then(() => setNote("Configuration saved. The connector stays disabled."))
              .catch((err) => onError((err as Error).message));
          }}
        >
          <input aria-label="Wrench specification" placeholder="Verified API specification" value={spec} onChange={(e) => setSpec(e.target.value)} />
          <input aria-label="Credential label" placeholder="Credential label, not the secret" value={label} onChange={(e) => setLabel(e.target.value)} />
          <button>Save disabled configuration</button>
        </form>
      )}
      {drawing && (
        <form
          className="toolbar"
          onSubmit={(e) => {
            e.preventDefault();
            void api<{ conflict_status: string; external_document_id: string }>(
              `/projects/${pid}/drawings/${drawing.id}/wrench-link`,
              "POST",
              {
                external_document_id: external,
                external_revision_id: "",
              },
            )
              .then((row) =>
                setNote(`Manual link ${row.external_document_id}. Conflict status: ${row.conflict_status}.`),
              )
              .catch((err) => onError((err as Error).message));
          }}
        >
          <input aria-label="External document id" placeholder="External document id" value={external} onChange={(e) => setExternal(e.target.value)} />
          <button>Store manual link</button>
        </form>
      )}
      <button
        onClick={() =>
          void api(`/projects/${pid}/wrench/sync`, "POST")
            .then(() => setNote("Unexpected success"))
            .catch((err) => setNote((err as Error).message))
        }
      >
        Sync (disabled)
      </button>
    </section>
  );
}

function DisciplineForm({
  catalog,
  onError,
}: {
  catalog: Catalog;
  onError: (text: string) => void;
}) {
  const [name, setName] = useState("");
  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api("/disciplines", "POST", { name });
      setName("");
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }
  return (
    <form className="panel toolbar" onSubmit={save}>
      <h3>Disciplines</h3>
      <p className="muted">{catalog.disciplines.map((row) => row.name).join(", ")}</p>
      <input required aria-label="New discipline" placeholder="New discipline" value={name} onChange={(e) => setName(e.target.value)} />
      <button>Add discipline</button>
    </form>
  );
}
