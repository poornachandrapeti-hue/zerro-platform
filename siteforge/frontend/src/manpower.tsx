import { FormEvent, useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { BellRing, CalendarCheck, CalendarClock, CalendarRange, ClipboardCheck, ClipboardList, Gauge, HardHat, TrendingUp, IdCard, LayoutDashboard, Pencil, Plus, Search, UserRound, UsersRound } from "lucide-react";
import { api } from "./api";
import { Count, Err, ReviewBox, statusClass } from "./hr";
import { HseRoutes } from "./hse";
import type { Page, Project, Session } from "./types";

const TABS = ["Dashboard", "Workforce demand", "Crews", "Availability", "Allocation", "Daily returns", "Utilization", "Productivity", "Alerts", "HR references"] as const;
type Tab = (typeof TABS)[number];
const TAB_ICON: Record<Tab, LucideIcon> = {
  Dashboard: LayoutDashboard,
  "Workforce demand": ClipboardList,
  Crews: HardHat,
  Availability: CalendarRange,
  Allocation: CalendarCheck,
  "Daily returns": ClipboardCheck,
  Utilization: Gauge,
  Productivity: TrendingUp,
  Alerts: BellRing,
  "HR references": IdCard,
};
const TAB_TONE: Record<Tab, string> = {
  Dashboard: "tone-mdash",
  "Workforce demand": "tone-mdemand",
  Crews: "tone-mcrew",
  Availability: "tone-mavail",
  Allocation: "tone-malloc",
  "Daily returns": "tone-mreturn",
  Utilization: "tone-mutil",
  Productivity: "tone-mprod",
  Alerts: "tone-malert",
  "HR references": "tone-mref",
};
const DAY_CODE: Record<string, string> = { Available: "A", Expected: "E", "On leave": "L", Unavailable: "U", "Not deployed": "·" };
const dayClass = (status: string) => `mp-day mp-day-${status.toLowerCase().replace(/\s+/g, "-")}`;
const DEMAND_ROUTES = [{ recordType: "hr.request", label: "Workforce demand reviewer", stage: "Workforce demand review" }];
const ALLOCATING = ["Open", "Partially Allocated", "Allocated"];
const EDITABLE = ["Draft", "Returned"];

type Option = { id: number; name: string };
type Review = { id: number; version: number; actions: string[]; state: string };
type Tracking = { requested: number; approved: number; proposed: number; confirmed: number; shortfall: number | null };
type Demand = {
  id: number;
  number: string;
  discipline_id: number | null;
  discipline: string;
  area_id: number | null;
  area: string;
  package_id: number | null;
  package: string;
  activity_id: number | null;
  activity: string;
  company_id: number;
  company_name: string;
  trade_id: number;
  trade: string;
  grade_id: number | null;
  grade: string;
  headcount: number;
  required_hours: number | null;
  required_mobilization: string | null;
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
  tracking: Tracking;
  planned_hours: number;
  lines: { id: number; personnel_id: number; person: string; state: string; deployment_id: number | null }[];
  version: number;
  review: Review | null;
};
type Reference = {
  id: number;
  code: string;
  full_name: string;
  company_id: number;
  company_name: string;
  trade_id: number;
  trade: string;
  grade: string;
  discipline: string;
  status: string;
  deployment_status: string;
  deployment_from: string | null;
  deployment_to: string | null;
  today: string;
};
type CrewMember = {
  id: number;
  personnel_id: number;
  person: string;
  start_date: string;
  end_date: string | null;
  active: boolean;
  today: string;
};
type Crew = {
  id: number;
  code: string;
  name: string;
  company_id: number;
  company_name: string;
  discipline_id: number | null;
  discipline: string;
  trade_id: number | null;
  trade: string;
  area_id: number | null;
  area: string;
  supervisor_id: number | null;
  supervisor: string;
  lead_id: number | null;
  lead: string;
  shift_id: number | null;
  shift: string;
  effective_from: string;
  effective_to: string | null;
  active: boolean;
  version: number;
  members: CrewMember[];
  strength: { members: number; available: number; away: number };
};
type Availability = {
  note: string;
  start: string;
  dates: string[];
  statuses: string[];
  people: { id: number; code: string; full_name: string; company_name: string; trade: string; days: { status: string; crew: string }[] }[];
  trades: { trade_id: number; trade: string; days: { available: number; expected: number; away: number; needed: number; gap: number }[] }[];
};
type Board = {
  note: string;
  demand_note: string;
  reference_note: string;
  today: string;
  references: Reference[];
  demands: Demand[];
  companies: Option[];
  project_disciplines: Option[];
  areas: Option[];
  packages: Option[];
  activities: { id: number; name: string; title: string; package_id: number; company_id: number }[];
  trades: Option[];
  grades: Option[];
  shifts: string[];
  shift_options: (Option & { active: boolean })[];
  crews: Crew[];
  crew_note: string;
  priorities: string[];
  members: Option[];
  deployments: { id: number; personnel_id: number; status: string; planned_start: string; planned_end: string | null }[];
  can_demand: boolean;
  can_coordinate: boolean;
  can_allocate: boolean;
  counts: Record<string, number>;
};

export function ManpowerHome({ session, initialProjectId = null }: { session: Session; initialProjectId?: number | null }) {
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
        <ManpowerBoard pid={pid} session={session} />
      </>
    );
  }
  return (
    <section className="panel">
      <h2>Manpower</h2>
      <p className="muted">Open a project to coordinate its workforce demand.</p>
      <Err text={error} />
      {projects.map((project) => (
        <button key={project.id} onClick={() => setPid(project.id || null)}>
          <UserRound size={16} strokeWidth={2.4} />
          {project.code} · {project.name}
        </button>
      ))}
    </section>
  );
}

function ManpowerBoard({ pid, session }: { pid: number; session: Session }) {
  const [tab, setTab] = useState<Tab>("Dashboard");
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState("");
  async function load() {
    setBoard(await api<Board>(`/projects/${pid}/manpower`));
  }
  useEffect(() => {
    void load().catch((err) => setError((err as Error).message));
  }, [pid]);
  return (
    <section className="panel hr-panel mp-panel">
      <h2>Manpower</h2>
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
      {board ? <p className="note-card mp-note">{board.note}</p> : null}
      {tab === "Dashboard" && board ? <Dashboard pid={pid} board={board} onOpen={setTab} /> : null}
      {tab === "Workforce demand" && board ? (
        <Demands pid={pid} board={board} admin={session.user.organization_admin} userId={session.user.id} onError={setError} reload={load} />
      ) : null}
      {tab === "Crews" && board ? <Crews pid={pid} board={board} onError={setError} reload={load} /> : null}
      {tab === "Availability" && board ? <AvailabilityGrid pid={pid} today={board.today} onError={setError} /> : null}
      {tab === "Allocation" && board ? <Allocation pid={pid} board={board} onError={setError} /> : null}
      {tab === "Daily returns" && board ? <DailyReturns pid={pid} board={board} onError={setError} /> : null}
      {tab === "Utilization" && board ? <Utilization pid={pid} today={board.today} onError={setError} /> : null}
      {tab === "Productivity" && board ? <Productivity pid={pid} today={board.today} onError={setError} /> : null}
      {tab === "Alerts" && board ? <Alerts pid={pid} onError={setError} onOpen={setTab} /> : null}
      {tab === "HR references" && board ? <References board={board} /> : null}
    </section>
  );
}

function Dashboard({ pid, board, onOpen }: { pid: number; board: Board; onOpen: (tab: Tab) => void }) {
  const c = board.counts;
  const [week, setWeek] = useState<Summary | null>(null);
  useEffect(() => {
    api<Summary>(`/projects/${pid}/manpower/summary`)
      .then(setWeek)
      .catch(() => setWeek(null));
  }, [pid]);
  const soon = new Date(board.today);
  soon.setDate(soon.getDate() + 14);
  const horizon = soon.toISOString().slice(0, 10);
  const due = board.demands
    .filter((row) => ALLOCATING.includes(row.status) && (row.tracking.shortfall || 0) > 0)
    .filter((row) => (row.required_mobilization || row.start_date) <= horizon)
    .sort((a, b) => (a.required_mobilization || a.start_date).localeCompare(b.required_mobilization || b.start_date));
  return (
    <>
      {week ? <WeekSummary week={week} onOpen={onOpen} /> : null}
      <h3 className="section-mark mp-mark">
        <IdCard size={18} strokeWidth={2.4} /> From HR today
      </h3>
      <div className="dash-grid mp-counts">
        <Count label="Engaged" value={c.engaged} />
        <Count label="Deployed today" value={c.deployed} />
        <Count label="Approved for mobilization" value={c.approved_mobilization} />
        <Count label="Temporarily unavailable" value={c.unavailable} />
        <Count label="Available today" value={c.available_today} />
        <Count label="On approved leave today" value={c.on_leave_today} />
        <Count label="Active crews" value={c.active_crews} />
        <Count label="Crew members away today" value={c.crew_away} />
      </div>
      <p className="muted">{board.reference_note} Available today is mobilized and not on approved leave; it is not eligibility for an activity.</p>
      <h3 className="section-mark mp-mark">
        <ClipboardList size={18} strokeWidth={2.4} /> Workforce demand
      </h3>
      <div className="mp-funnel">
        <span>
          <strong>{c.demands_pending}</strong>Waiting for review
        </span>
        <span>
          <strong>{c.demands_open}</strong>Open demands
        </span>
        <span>
          <strong>{c.requested}</strong>Requested
        </span>
        <span>
          <strong>{c.approved}</strong>Approved
        </span>
        <span>
          <strong>{c.proposed}</strong>Proposed
        </span>
        <span className="is-good">
          <strong>{c.confirmed}</strong>Confirmed
        </span>
        <span className={c.shortfall ? "is-bad" : "is-good"}>
          <strong>{c.shortfall}</strong>Shortfall
        </span>
      </div>
      <p className="muted">Headcounts cover approved demands that are still open. {board.demand_note}</p>
      <article className="hr-breakdown mp-due">
        <h3>
          <CalendarClock size={16} /> Shortfall due within 14 days
        </h3>
        {due.length === 0 ? (
          <p className="muted">No open demand is short within the next 14 days.</p>
        ) : (
          <ul>
            {due.map((row) => (
              <li key={row.id}>
                <span>
                  {row.number} · {row.trade} · {row.company_name}
                </span>
                <strong>
                  {row.tracking.shortfall} short · by {row.required_mobilization || row.start_date}
                </strong>
              </li>
            ))}
          </ul>
        )}
      </article>
    </>
  );
}

const NEW_DEMAND = {
  number: "",
  company_id: "",
  discipline_id: "",
  area_id: "",
  package_id: "",
  activity_id: "",
  trade_id: "",
  grade_id: "",
  qualifications: "",
  headcount: "1",
  required_hours: "",
  start_date: "",
  end_date: "",
  shift: "",
  priority: "Normal",
  required_mobilization: "",
  justification: "",
};
type DemandForm = typeof NEW_DEMAND;

function formFrom(row: Demand): DemandForm {
  const text = (value: number | string | null) => (value === null || value === undefined ? "" : String(value));
  return {
    number: row.number,
    company_id: text(row.company_id),
    discipline_id: text(row.discipline_id),
    area_id: text(row.area_id),
    package_id: text(row.package_id),
    activity_id: text(row.activity_id),
    trade_id: text(row.trade_id),
    grade_id: text(row.grade_id),
    qualifications: row.qualifications,
    headcount: text(row.headcount),
    required_hours: text(row.required_hours),
    start_date: row.start_date,
    end_date: text(row.end_date),
    shift: row.shift,
    priority: row.priority,
    required_mobilization: text(row.required_mobilization),
    justification: row.justification,
  };
}

function DemandEditor({
  pid,
  board,
  row,
  onDone,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  row: Demand | null;
  onDone: () => void;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [form, setForm] = useState<DemandForm>(row ? formFrom(row) : NEW_DEMAND);
  const set = (key: keyof DemandForm) => (event: { target: { value: string } }) => {
    const next = { ...form, [key]: event.target.value };
    if (key === "package_id") next.activity_id = "";
    setForm(next);
  };
  const num = (value: string) => (value ? Number(value) : null);
  const activities = board.activities.filter((item) => !form.package_id || item.package_id === Number(form.package_id));

  async function save(event: FormEvent) {
    event.preventDefault();
    onError("");
    const body = {
      number: form.number,
      company_id: Number(form.company_id),
      trade_id: Number(form.trade_id),
      grade_id: num(form.grade_id),
      headcount: Number(form.headcount),
      required_hours: num(form.required_hours),
      start_date: form.start_date,
      end_date: form.end_date || null,
      required_mobilization: form.required_mobilization || null,
      discipline_id: num(form.discipline_id),
      area_id: num(form.area_id),
      package_id: num(form.package_id),
      activity_id: num(form.activity_id),
      shift: form.shift,
      priority: form.priority,
      qualifications: form.qualifications,
      justification: form.justification,
    };
    try {
      if (row) {
        await api(`/projects/${pid}/manpower/demands/${row.id}`, "PUT", { ...body, version: row.version });
      } else {
        await api(`/projects/${pid}/manpower/demands`, "POST", body);
      }
      onDone();
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }

  const choose = (label: string, key: keyof DemandForm, rows: Option[], required = false) => (
    <label>
      {label}
      <select required={required} value={form[key]} onChange={set(key)}>
        <option value="">{required ? "Choose" : "Not set"}</option>
        {rows.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <form className="contact-form hr-form mp-form" onSubmit={(event) => void save(event)}>
      <h4 className="wide">{row ? `Edit demand ${row.number}` : "New workforce demand"}</h4>
      <label>
        Demand number
        <input required value={form.number} onChange={set("number")} placeholder="e.g. MD-001" />
      </label>
      {choose("Requesting company", "company_id", board.companies, true)}
      {choose("Discipline", "discipline_id", board.project_disciplines)}
      {choose("Location", "area_id", board.areas)}
      {choose("Work package", "package_id", board.packages)}
      {choose("Activity", "activity_id", activities)}
      {choose("Trade", "trade_id", board.trades, true)}
      {choose("Skill grade", "grade_id", board.grades)}
      <label>
        Required qualifications
        <input value={form.qualifications} onChange={set("qualifications")} />
      </label>
      <label>
        Headcount
        <input required type="number" min={1} max={10000} value={form.headcount} onChange={set("headcount")} />
      </label>
      <label>
        Required hours
        <input type="number" min={1} value={form.required_hours} onChange={set("required_hours")} placeholder="Where applicable" />
      </label>
      <label>
        Needed from
        <input required type="date" value={form.start_date} onChange={set("start_date")} />
      </label>
      <label>
        Needed until
        <input type="date" value={form.end_date} onChange={set("end_date")} />
      </label>
      <label>
        Required mobilization
        <input type="date" max={form.start_date || undefined} value={form.required_mobilization} onChange={set("required_mobilization")} />
      </label>
      <label>
        Shift
        <input list="mp-shifts" value={form.shift} onChange={set("shift")} />
        <datalist id="mp-shifts">
          {board.shifts.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      </label>
      <label>
        Priority
        <select value={form.priority} onChange={set("priority")}>
          {board.priorities.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
      </label>
      <label className="wide">
        Justification
        <input required minLength={3} value={form.justification} onChange={set("justification")} />
      </label>
      <div className="wide hr-actions">
        <button className="primary" type="submit">
          {row ? "Save changes" : "Save draft"}
        </button>
        <button type="button" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function Demands({
  pid,
  board,
  admin,
  userId,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  admin: boolean;
  userId: number;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("Open");
  const groups: Record<string, (row: Demand) => boolean> = {
    Open: (row) => ALLOCATING.includes(row.status),
    "In review": (row) => ["Draft", "Pending Review", "Returned"].includes(row.status),
    Closed: (row) => ["Closed", "Cancelled", "Rejected"].includes(row.status),
    All: () => true,
  };
  const rows = board.demands.filter(groups[filter]);
  return (
    <>
      <HseRoutes pid={pid} admin={admin} routes={DEMAND_ROUTES} members={board.members} disciplines={board.project_disciplines} />
      <p className="muted">{board.demand_note}</p>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <ClipboardList size={18} strokeWidth={2.4} /> Workforce demand
        </h3>
        <div className="mp-filter" role="radiogroup" aria-label="Demand filter">
          {Object.keys(groups).map((name) => (
            <button key={name} type="button" role="radio" aria-checked={filter === name} className={filter === name ? "is-on" : ""} onClick={() => setFilter(name)}>
              {name} ({board.demands.filter(groups[name]).length})
            </button>
          ))}
        </div>
        {board.can_demand && !open ? (
          <button className="primary" type="button" onClick={() => setOpen(true)}>
            <Plus size={16} /> New demand
          </button>
        ) : null}
      </div>
      {board.can_demand && open ? <DemandEditor pid={pid} board={board} row={null} onDone={() => setOpen(false)} onError={onError} reload={reload} /> : null}
      {rows.length === 0 ? (
        <p className="muted">{board.demands.length ? "No demand in this view." : "No workforce demand is recorded on this project."}</p>
      ) : (
        <div className="hr-cards">
          {rows.map((row) => (
            <DemandCard key={row.id} pid={pid} row={row} board={board} mine={row.requested_by === userId || admin} onError={onError} reload={reload} />
          ))}
        </div>
      )}
    </>
  );
}

function DemandCard({
  pid,
  row,
  board,
  mine,
  onError,
  reload,
}: {
  pid: number;
  row: Demand;
  board: Board;
  mine: boolean;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [person, setPerson] = useState("");
  const [picked, setPicked] = useState<Record<number, string>>({});
  const [forecast, setForecast] = useState(row.expected_mobilization || "");
  const [reason, setReason] = useState("");
  const allocating = ALLOCATING.includes(row.status);
  const coordinate = board.can_coordinate && allocating;
  const onList = new Set(row.lines.filter((line) => line.state !== "Released").map((line) => line.personnel_id));
  const candidates = board.references.filter((item) => item.status === "Active" && item.trade_id === row.trade_id && !onList.has(item.id));
  const t = row.tracking;

  async function run(path: string, body: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/manpower/demands/${row.id}${path}`, "POST", body);
      setReason("");
      setPerson("");
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  const line = (personnel_id: number, state: string, deployment_id: number | null = null) =>
    run("/lines", { personnel_id, state, deployment_id, version: row.version });

  if (editing) {
    return <DemandEditor pid={pid} board={board} row={row} onDone={() => setEditing(false)} onError={onError} reload={reload} />;
  }
  return (
    <article className="hr-card mp-card">
      <header>
        <strong>
          {row.number} · {row.headcount} × {row.trade}
          {row.grade ? ` (${row.grade})` : ""}
        </strong>
        <span className={statusClass(row.status)}>{row.status}</span>
      </header>
      <p className="hr-tags">
        <span>{row.company_name}</span>
        <span className={`hr-priority hr-priority-${row.priority.toLowerCase()}`}>{row.priority}</span>
        {row.discipline ? <span>{row.discipline}</span> : null}
        {row.area ? <span>{row.area}</span> : null}
        {row.package ? <span>{row.package}</span> : null}
        {row.activity ? <span className="mp-activity">{row.activity}</span> : null}
        {row.shift ? <span>{row.shift}</span> : null}
      </p>
      <p className="muted">
        Needed {row.start_date}
        {row.end_date ? ` to ${row.end_date}` : ""}
        {row.required_hours ? ` · ${row.required_hours} h` : ""}
        {row.planned_hours ? ` · ${row.planned_hours} h confirmed in allocations` : ""} · Requested by {row.requester}
      </p>
      <p className="mp-dates">
        <span>
          Required mobilization <strong>{row.required_mobilization || "Not set"}</strong>
        </span>
        <span>
          Forecast <strong>{row.expected_mobilization || "Not set"}</strong>
        </span>
      </p>
      <p className="muted">{row.justification}</p>
      {row.qualifications ? <p className="muted">Qualifications: {row.qualifications}</p> : null}
      {row.status_reason ? <p className="muted">Reason: {row.status_reason}</p> : null}
      <div className="mp-track">
        <span>
          Requested <strong>{t.requested}</strong>
        </span>
        <span>
          Approved <strong>{t.approved}</strong>
        </span>
        <span>
          Proposed <strong>{t.proposed}</strong>
        </span>
        <span className="is-good">
          Confirmed <strong>{t.confirmed}</strong>
        </span>
        <span className={t.shortfall === null ? "" : t.shortfall ? "is-bad" : "is-good"}>
          Shortfall <strong>{t.shortfall === null ? "—" : t.shortfall}</strong>
        </span>
      </div>
      {row.lines.length ? (
        <ul className="hr-checks">
          {row.lines.map((item) => {
            const options = board.deployments.filter((dep) => dep.personnel_id === item.personnel_id);
            return (
              <li key={item.id} className={`is-${item.state.toLowerCase()}`}>
                <div>
                  <strong>{item.person}</strong>
                  <span className="muted">{item.state === "Allocated" ? "Confirmed" : item.state}</span>
                </div>
                {coordinate && item.state !== "Released" ? (
                  <div className="hr-check-act">
                    {item.state === "Proposed" ? (
                      <>
                        <select aria-label={`HR deployment for ${item.person}`} value={picked[item.id] || ""} onChange={(event) => setPicked({ ...picked, [item.id]: event.target.value })}>
                          <option value="">{options.length ? "Choose HR deployment" : "No approved HR deployment"}</option>
                          {options.map((dep) => (
                            <option key={dep.id} value={dep.id}>
                              {dep.status} · {dep.planned_start}
                            </option>
                          ))}
                        </select>
                        <button type="button" className="primary" disabled={!picked[item.id]} onClick={() => void line(item.personnel_id, "Allocated", Number(picked[item.id]))}>
                          Confirm
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
      {coordinate ? (
        <div className="hr-move">
          <select aria-label="Propose person" value={person} onChange={(event) => setPerson(event.target.value)}>
            <option value="">{candidates.length ? "Propose a person with this trade" : "No other active person with this trade"}</option>
            {candidates.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} · {item.full_name}
                {item.deployment_status ? ` · ${item.deployment_status}` : ""}
              </option>
            ))}
          </select>
          <button type="button" className="primary" disabled={!person} onClick={() => void line(Number(person), "Proposed")}>
            Propose
          </button>
          <input type="date" aria-label="Forecast mobilization" value={forecast} onChange={(event) => setForecast(event.target.value)} />
          <button type="button" onClick={() => void run("/forecast", { expected_mobilization: forecast || null, version: row.version })}>
            Save forecast
          </button>
        </div>
      ) : null}
      {(mine && EDITABLE.includes(row.status)) || ((mine || board.can_coordinate) && (allocating || EDITABLE.includes(row.status))) ? (
        <div className="hr-move">
          {mine && EDITABLE.includes(row.status) && board.can_demand ? (
            <button type="button" onClick={() => setEditing(true)}>
              <Pencil size={14} /> Edit
            </button>
          ) : null}
          {mine && row.status === "Draft" && board.can_demand ? (
            <button type="button" className="primary" onClick={() => void run("/submit", { version: row.version })}>
              Submit for review
            </button>
          ) : null}
          <input aria-label="Close or cancel reason" placeholder="Reason to close or cancel" value={reason} onChange={(event) => setReason(event.target.value)} />
          {board.can_coordinate && allocating ? (
            <button type="button" onClick={() => void run("/close", { action: "close", reason, version: row.version })}>
              Close demand
            </button>
          ) : null}
          <button type="button" className="hr-danger" onClick={() => void run("/close", { action: "cancel", reason, version: row.version })}>
            Cancel demand
          </button>
        </div>
      ) : null}
    </article>
  );
}

function References({ board }: { board: Board }) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const rows = board.references.filter((row) =>
    !q || [row.code, row.full_name, row.company_name, row.trade, row.grade, row.discipline, row.deployment_status].some((value) => value.toLowerCase().includes(q)),
  );
  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <UsersRound size={18} strokeWidth={2.4} /> HR personnel references
        </h3>
        <label className="mp-search">
          <Search size={15} />
          <input aria-label="Search personnel" placeholder="Search code, name, company, trade" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
      </div>
      <p className="muted">These rows are read from HR. Manpower does not edit them. {board.reference_note}</p>
      {rows.length === 0 ? (
        <p className="muted">{board.references.length ? "No person matches this search." : "No personnel is recorded for the companies on this project."}</p>
      ) : (
        <div className="mp-table-wrap">
          <table className="mp-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Company</th>
                <th>Trade</th>
                <th>Grade</th>
                <th>Discipline</th>
                <th>Employment</th>
                <th>HR deployment</th>
                <th>Today</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.code}</td>
                  <td>{row.full_name}</td>
                  <td>{row.company_name}</td>
                  <td>{row.trade}</td>
                  <td>{row.grade || "—"}</td>
                  <td>{row.discipline || "—"}</td>
                  <td>
                    <span className={statusClass(row.status)}>{row.status}</span>
                  </td>
                  <td>
                    {row.deployment_status ? (
                      <>
                        <span className={statusClass(row.deployment_status)}>{row.deployment_status}</span>
                        <small className="muted">
                          {" "}
                          {row.deployment_from}
                          {row.deployment_to ? ` to ${row.deployment_to}` : ""}
                        </small>
                      </>
                    ) : (
                      <span className="muted">Not deployed</span>
                    )}
                  </td>
                  <td>
                    <span className={`mp-pill ${dayClass(row.today)}`}>{row.today}</span>
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

const NEW_CREW = { code: "", name: "", company_id: "", discipline_id: "", trade_id: "", area_id: "", supervisor_id: "", lead_id: "", shift_id: "", effective_from: "", effective_to: "" };
type CrewForm = typeof NEW_CREW;
const MEMBER_DEPLOYMENTS = ["Approved for Mobilization", "Mobilized", "Temporarily Unavailable"];

function crewBody(form: CrewForm) {
  const num = (value: string) => (value ? Number(value) : null);
  return {
    code: form.code,
    name: form.name,
    company_id: Number(form.company_id),
    discipline_id: num(form.discipline_id),
    trade_id: num(form.trade_id),
    area_id: num(form.area_id),
    supervisor_id: num(form.supervisor_id),
    lead_id: num(form.lead_id),
    shift_id: num(form.shift_id),
    effective_from: form.effective_from,
    effective_to: form.effective_to || null,
  };
}

function crewForm(row: Crew): CrewForm {
  const text = (value: number | string | null) => (value === null || value === undefined ? "" : String(value));
  return {
    code: row.code,
    name: row.name,
    company_id: text(row.company_id),
    discipline_id: text(row.discipline_id),
    trade_id: text(row.trade_id),
    area_id: text(row.area_id),
    supervisor_id: text(row.supervisor_id),
    lead_id: text(row.lead_id),
    shift_id: text(row.shift_id),
    effective_from: row.effective_from,
    effective_to: text(row.effective_to),
  };
}

function CrewEditor({
  pid,
  board,
  row,
  onDone,
  onError,
  reload,
}: {
  pid: number;
  board: Board;
  row: Crew | null;
  onDone: () => void;
  onError: (text: string) => void;
  reload: () => Promise<void>;
}) {
  const [form, setForm] = useState<CrewForm>(row ? crewForm(row) : NEW_CREW);
  const set = (key: keyof CrewForm) => (event: { target: { value: string } }) => {
    const next = { ...form, [key]: event.target.value };
    if (key === "company_id") next.lead_id = "";
    setForm(next);
  };
  const leads = board.references.filter((item) => item.status === "Active" && String(item.company_id) === form.company_id);

  async function save(event: FormEvent) {
    event.preventDefault();
    onError("");
    try {
      if (row) {
        await api(`/projects/${pid}/manpower/crews/${row.id}`, "PUT", { ...crewBody(form), active: row.active, version: row.version });
      } else {
        await api(`/projects/${pid}/manpower/crews`, "POST", crewBody(form));
      }
      onDone();
      await reload();
    } catch (err) {
      onError((err as Error).message);
    }
  }

  const choose = (label: string, key: keyof CrewForm, rows: Option[], required = false, empty = "Not set") => (
    <label>
      {label}
      <select required={required} value={form[key]} onChange={set(key)}>
        <option value="">{required ? "Choose" : empty}</option>
        {rows.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <form className="contact-form hr-form mp-form mp-crew-form" onSubmit={(event) => void save(event)}>
      <h4 className="wide">{row ? `Edit crew ${row.code}` : "New crew"}</h4>
      <label>
        Crew code
        <input required value={form.code} onChange={set("code")} placeholder="e.g. PF-01" />
      </label>
      <label>
        Crew name
        <input value={form.name} onChange={set("name")} placeholder="e.g. Pipe erection crew" />
      </label>
      {choose("Employing company", "company_id", board.companies, true)}
      {choose("Discipline", "discipline_id", board.project_disciplines)}
      {choose("Main trade", "trade_id", board.trades)}
      {choose("Work location", "area_id", board.areas)}
      {choose("Supervisor", "supervisor_id", board.members)}
      {choose("Crew lead", "lead_id", leads.map((item) => ({ id: item.id, name: `${item.code} · ${item.full_name}` })), false, form.company_id ? "Not set" : "Choose a company first")}
      {choose("Shift", "shift_id", board.shift_options.filter((item) => item.active || String(item.id) === form.shift_id), false, "Any shift")}
      <label>
        Effective from
        <input required type="date" value={form.effective_from} onChange={set("effective_from")} />
      </label>
      <label>
        Effective to
        <input type="date" min={form.effective_from || undefined} value={form.effective_to} onChange={set("effective_to")} />
      </label>
      <p className="wide muted">The supervisor is a project user who oversees the crew. The crew lead is a worker from HR employed by the crew company.</p>
      <div className="wide hr-actions">
        <button className="primary" type="submit">
          {row ? "Save changes" : "Save crew"}
        </button>
        <button type="button" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function Crews({ pid, board, onError, reload }: { pid: number; board: Board; onError: (text: string) => void; reload: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [showOff, setShowOff] = useState(false);
  const rows = board.crews.filter((row) => showOff || row.active);
  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <HardHat size={18} strokeWidth={2.4} /> Crews
        </h3>
        <div className="mp-filter" role="radiogroup" aria-label="Crew filter">
          <button type="button" role="radio" aria-checked={!showOff} className={!showOff ? "is-on" : ""} onClick={() => setShowOff(false)}>
            Active ({board.crews.filter((row) => row.active).length})
          </button>
          <button type="button" role="radio" aria-checked={showOff} className={showOff ? "is-on" : ""} onClick={() => setShowOff(true)}>
            All ({board.crews.length})
          </button>
        </div>
        {board.can_coordinate && !open ? (
          <button className="primary" type="button" onClick={() => setOpen(true)}>
            <Plus size={16} /> New crew
          </button>
        ) : null}
      </div>
      <p className="muted">{board.crew_note} HR attendance and overtime use these same crews. Members join through an HR deployment on this project.</p>
      {board.can_coordinate && open ? <CrewEditor pid={pid} board={board} row={null} onDone={() => setOpen(false)} onError={onError} reload={reload} /> : null}
      {rows.length === 0 ? (
        <p className="muted">{board.crews.length ? "No active crew. Show all to see inactive crews." : "No crew is set up on this project."}</p>
      ) : (
        <div className="hr-cards">
          {rows.map((row) => (
            <CrewCard key={row.id} pid={pid} row={row} board={board} onError={onError} reload={reload} />
          ))}
        </div>
      )}
    </>
  );
}

function CrewCard({ pid, row, board, onError, reload }: { pid: number; row: Crew; board: Board; onError: (text: string) => void; reload: () => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [person, setPerson] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [ending, setEnding] = useState<Record<number, string>>({});
  const edit = board.can_coordinate;
  const inCrew = new Set(row.members.filter((m) => m.active).map((m) => m.personnel_id));
  const workers = board.references.filter((item) => item.status === "Active" && item.company_id === row.company_id);
  const deployed = workers.filter((item) => MEMBER_DEPLOYMENTS.includes(item.deployment_status));
  const candidates = deployed.filter((item) => !inCrew.has(item.id));
  const blocked = !workers.length
    ? `HR has no active worker employed by ${row.company_name}. Add workers in HR → Personnel first.`
    : !deployed.length
      ? `${workers.length} worker${workers.length === 1 ? "" : "s"} from ${row.company_name} ${workers.length === 1 ? "has" : "have"} no approved HR deployment on this project. Deploy them in HR → Deployments and get the deployment approved for mobilization.`
      : !candidates.length
        ? "Everyone deployed from this company is already in this crew."
        : "";
  const s = row.strength;

  async function run(path: string, method: string, body: Record<string, unknown>) {
    onError("");
    try {
      await api(`/projects/${pid}/manpower/crews/${row.id}${path}`, method, body);
      await reload();
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }
  async function add() {
    if (await run("/members", "POST", { personnel_id: Number(person), start_date: start, end_date: end || null, version: row.version })) {
      setPerson("");
      setStart("");
      setEnd("");
    }
  }

  if (editing) return <CrewEditor pid={pid} board={board} row={row} onDone={() => setEditing(false)} onError={onError} reload={reload} />;
  return (
    <article className={`hr-card mp-card mp-crew${row.active ? "" : " is-off"}`}>
      <header>
        <strong>
          {row.code}
          {row.name ? ` · ${row.name}` : ""}
        </strong>
        <span className={`rel-chip ${row.active ? "hr-status-active" : "hr-status-inactive"}`}>{row.active ? "Active" : "Inactive"}</span>
      </header>
      <p className="hr-tags">
        <span>{row.company_name}</span>
        {row.trade ? <span className="mp-activity">{row.trade}</span> : null}
        {row.discipline ? <span>{row.discipline}</span> : null}
        {row.area ? <span>{row.area}</span> : null}
        {row.shift ? <span>{row.shift}</span> : null}
      </p>
      <p className="muted">
        {row.supervisor ? `Supervisor ${row.supervisor} · ` : ""}
        {row.lead ? `Lead ${row.lead} · ` : ""}From {row.effective_from}
        {row.effective_to ? ` to ${row.effective_to}` : ""}
      </p>
      <div className="mp-track mp-strength">
        <span>
          Members today <strong>{s.members}</strong>
        </span>
        <span className="is-good">
          Available <strong>{s.available}</strong>
        </span>
        <span className={s.away ? "is-bad" : ""}>
          Away <strong>{s.away}</strong>
        </span>
      </div>
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
              <div className="hr-check-act">
                {m.today ? <span className={`mp-pill ${dayClass(m.today)}`}>{m.today}</span> : <span className="muted">Ended</span>}
                {edit && m.active ? (
                  <>
                    <input type="date" aria-label={`End ${m.person}`} min={m.start_date} value={ending[m.id] || ""} onChange={(event) => setEnding({ ...ending, [m.id]: event.target.value })} />
                    <button type="button" disabled={!ending[m.id]} onClick={() => void run(`/members/${m.id}/end`, "POST", { end_date: ending[m.id], version: row.version })}>
                      End membership
                    </button>
                  </>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
      {edit && row.active ? (
        <div className="mp-add-member">
          <h4>
            <UsersRound size={15} strokeWidth={2.4} /> Add members
          </h4>
          {blocked ? (
            <p className="mp-add-blocked">{blocked}</p>
          ) : (
            <div className="mp-add-row">
              <label>
                Worker
                <select value={person} onChange={(event) => setPerson(event.target.value)}>
                  <option value="">Choose a deployed worker</option>
                  {candidates.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.code} · {item.full_name} · {item.trade}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                From
                <input type="date" min={row.effective_from} value={start} onChange={(event) => setStart(event.target.value)} />
              </label>
              <label>
                Until
                <input type="date" min={start || row.effective_from} max={row.effective_to || undefined} value={end} onChange={(event) => setEnd(event.target.value)} />
              </label>
              <button type="button" className="primary" disabled={!person || !start} onClick={() => void add()}>
                <Plus size={15} /> Add member
              </button>
            </div>
          )}
        </div>
      ) : null}
      {edit ? (
        <div className="hr-move">
          {row.active ? (
            <button type="button" onClick={() => setEditing(true)}>
              <Pencil size={14} /> Edit crew
            </button>
          ) : null}
          <button type="button" onClick={() => void run("", "PUT", { ...crewBody(crewForm(row)), active: !row.active, version: row.version })}>
            {row.active ? "Deactivate crew" : "Reactivate crew"}
          </button>
        </div>
      ) : null}
    </article>
  );
}

function AvailabilityGrid({ pid, today, onError }: { pid: number; today: string; onError: (text: string) => void }) {
  const [start, setStart] = useState(today);
  const [days, setDays] = useState(14);
  const [data, setData] = useState<Availability | null>(null);
  const [query, setQuery] = useState("");
  useEffect(() => {
    setData(null);
    api<Availability>(`/projects/${pid}/manpower/availability?start=${start}&days=${days}`)
      .then(setData)
      .catch((err) => onError((err as Error).message));
  }, [pid, start, days]);
  const q = query.trim().toLowerCase();
  const people = (data?.people || []).filter((row) => !q || [row.code, row.full_name, row.company_name, row.trade].some((value) => value.toLowerCase().includes(q)));
  const label = (iso: string) => {
    const d = new Date(`${iso}T00:00:00`);
    return { day: d.toLocaleDateString(undefined, { weekday: "short" }), date: d.getDate() };
  };
  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <CalendarRange size={18} strokeWidth={2.4} /> Demand against availability
        </h3>
        <div className="mp-range">
          <label>
            From
            <input type="date" value={start} onChange={(event) => event.target.value && setStart(event.target.value)} />
          </label>
          <div className="mp-filter" role="radiogroup" aria-label="Days shown">
            {[7, 14, 28].map((n) => (
              <button key={n} type="button" role="radio" aria-checked={days === n} className={days === n ? "is-on" : ""} onClick={() => setDays(n)}>
                {n} days
              </button>
            ))}
          </div>
        </div>
      </div>
      {!data ? (
        <p className="muted">Loading availability…</p>
      ) : (
        <>
          <p className="muted">{data.note}</p>
          <p className="mp-legend">
            {data.statuses.map((name) => (
              <span key={name}>
                <i className={dayClass(name)}>{DAY_CODE[name]}</i> {name}
              </span>
            ))}
          </p>
          <h4 className="mp-sub">By trade · available / needed</h4>
          {data.trades.length === 0 ? (
            <p className="muted">No deployed person or approved demand in this period.</p>
          ) : (
            <div className="mp-table-wrap">
              <table className="mp-grid">
                <thead>
                  <tr>
                    <th>Trade</th>
                    {data.dates.map((iso) => (
                      <th key={iso} className={iso === today ? "is-today" : ""}>
                        <small>{label(iso).day}</small>
                        {label(iso).date}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.trades.map((row) => (
                    <tr key={row.trade_id}>
                      <th>{row.trade}</th>
                      {row.days.map((cell, i) => (
                        <td
                          key={data.dates[i]}
                          className={`mp-cover${cell.needed ? (cell.gap ? " is-short" : " is-met") : ""}`}
                          title={`${cell.available} available, ${cell.expected} expected, ${cell.away} away, ${cell.needed} needed`}
                        >
                          <strong>{cell.available}</strong>
                          {cell.needed ? <small>/{cell.needed}</small> : null}
                          {cell.gap ? <em>−{cell.gap}</em> : null}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="hr-toolbar">
            <h4 className="mp-sub">People</h4>
            <label className="mp-search">
              <Search size={15} />
              <input aria-label="Search availability" placeholder="Search code, name, company, trade" value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
          </div>
          {people.length === 0 ? (
            <p className="muted">{data.people.length ? "No person matches this search." : "No one is deployed on this project in this period."}</p>
          ) : (
            <div className="mp-table-wrap">
              <table className="mp-grid">
                <thead>
                  <tr>
                    <th>Person</th>
                    {data.dates.map((iso) => (
                      <th key={iso} className={iso === today ? "is-today" : ""}>
                        <small>{label(iso).day}</small>
                        {label(iso).date}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {people.map((row) => (
                    <tr key={row.id}>
                      <th>
                        {row.code} · {row.full_name}
                        <small>
                          {row.trade} · {row.company_name}
                        </small>
                      </th>
                      {row.days.map((cell, i) => (
                        <td key={data.dates[i]} title={`${cell.status}${cell.crew ? ` · Crew ${cell.crew}` : ""}`}>
                          <i className={dayClass(cell.status)}>{DAY_CODE[cell.status]}</i>
                          {cell.crew ? <small className="mp-crew-code">{cell.crew}</small> : null}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}

type AssignmentRow = {
  id: number;
  work_date: string;
  shift_id: number;
  shift: string;
  activity_id: number;
  activity: string;
  personnel_id: number;
  person: string;
  trade: string;
  crew: string;
  demand: string;
  planned: string;
  planned_minutes: number;
  note: string;
  state: string;
  release_reason: string;
  problems: string[];
  version: number;
};
type AllocationBoard = {
  note: string;
  start: string;
  dates: string[];
  assignments: AssignmentRow[];
  counts: { proposed: number; confirmed: number; flagged: number; planned_hours: number };
};
type Skipped = { personnel_id: number; person: string; problems: string[] };
const NEW_ASSIGNMENT = { activity_id: "", work_date: "", shift_id: "", target: "person", personnel_id: "", crew_id: "", demand_id: "", hours: "8", note: "" };
const HELD = ["Approved for Mobilization", "Mobilized"];

function Allocation({ pid, board, onError }: { pid: number; board: Board; onError: (text: string) => void }) {
  const [start, setStart] = useState(board.today);
  const [days, setDays] = useState(7);
  const [data, setData] = useState<AllocationBoard | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...NEW_ASSIGNMENT, work_date: board.today });
  const [skipped, setSkipped] = useState<Skipped[]>([]);
  const [made, setMade] = useState(0);
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [showReleased, setShowReleased] = useState(false);

  async function load() {
    setData(await api<AllocationBoard>(`/projects/${pid}/manpower/allocations?start=${start}&days=${days}`));
  }
  useEffect(() => {
    setData(null);
    load().catch((err) => onError((err as Error).message));
  }, [pid, start, days]);

  const set = (key: keyof typeof NEW_ASSIGNMENT) => (event: { target: { value: string } }) => {
    const next = { ...form, [key]: event.target.value };
    if (key === "activity_id") Object.assign(next, { personnel_id: "", crew_id: "", demand_id: "" });
    setForm(next);
  };
  const activity = board.activities.find((item) => String(item.id) === form.activity_id);
  const people = board.references.filter((item) => item.status === "Active" && HELD.includes(item.deployment_status) && (!activity || item.company_id === activity.company_id));
  const crews = board.crews.filter((item) => item.active && (!activity || item.company_id === activity.company_id));
  const demands = board.demands.filter((item) => ALLOCATING.includes(item.status) && (!item.activity_id || item.activity_id === activity?.id));

  async function submit(event: FormEvent) {
    event.preventDefault();
    onError("");
    setSkipped([]);
    try {
      const result = await api<{ created: number[]; skipped: Skipped[] }>(`/projects/${pid}/manpower/assignments`, "POST", {
        activity_id: Number(form.activity_id),
        work_date: form.work_date,
        shift_id: Number(form.shift_id),
        personnel_id: form.target === "person" ? Number(form.personnel_id) : null,
        crew_id: form.target === "crew" ? Number(form.crew_id) : null,
        demand_id: form.demand_id ? Number(form.demand_id) : null,
        planned_minutes: Math.round(Number(form.hours) * 60),
        note: form.note,
      });
      setMade(result.created.length);
      setSkipped(result.skipped);
      setForm({ ...form, personnel_id: "", crew_id: "", note: "" });
      await load();
    } catch (err) {
      setMade(0);
      onError((err as Error).message);
    }
  }
  async function act(row: AssignmentRow, action: "confirm" | "release") {
    onError("");
    try {
      const body = action === "confirm" ? { version: row.version } : { reason: reasons[row.id] || "", version: row.version };
      await api(`/projects/${pid}/manpower/assignments/${row.id}/${action}`, "POST", body);
      setReasons({ ...reasons, [row.id]: "" });
      await load();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  async function confirmReady(rows: AssignmentRow[]) {
    for (const row of rows) await act(row, "confirm");
  }

  const label = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });
  const visible = (data?.assignments || []).filter((row) => showReleased || row.state !== "Released");
  const c = data?.counts;

  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <CalendarCheck size={18} strokeWidth={2.4} /> Activity allocation
        </h3>
        <div className="mp-range mp-range-alloc">
          <label>
            From
            <input type="date" value={start} onChange={(event) => event.target.value && setStart(event.target.value)} />
          </label>
          <div className="mp-filter" role="radiogroup" aria-label="Days shown">
            {[1, 7, 14].map((n) => (
              <button key={n} type="button" role="radio" aria-checked={days === n} className={days === n ? "is-on" : ""} onClick={() => setDays(n)}>
                {n === 1 ? "1 day" : `${n} days`}
              </button>
            ))}
          </div>
        </div>
        {board.can_allocate && !open ? (
          <button className="primary" type="button" onClick={() => setOpen(true)}>
            <Plus size={16} /> Assign work
          </button>
        ) : null}
      </div>
      {data ? <p className="muted">{data.note}</p> : null}
      {board.can_allocate && open ? (
        <form className="contact-form hr-form mp-form mp-alloc-form" onSubmit={(event) => void submit(event)}>
          <h4 className="wide">Assign work</h4>
          <label>
            Activity
            <select required value={form.activity_id} onChange={set("activity_id")}>
              <option value="">{board.activities.length ? "Choose" : "No active activity on this project"}</option>
              {board.activities.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Date
            <input required type="date" value={form.work_date} onChange={set("work_date")} />
          </label>
          <label>
            Shift
            <select required value={form.shift_id} onChange={set("shift_id")}>
              <option value="">{board.shift_options.some((item) => item.active) ? "Choose" : "No active shift · set one in HR"}</option>
              {board.shift_options
                .filter((item) => item.active)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Planned hours
            <input required type="number" min={0.5} max={24} step={0.5} value={form.hours} onChange={set("hours")} />
          </label>
          <div className="wide mp-target" role="radiogroup" aria-label="Assign to">
            {(["person", "crew"] as const).map((name) => (
              <button key={name} type="button" role="radio" aria-checked={form.target === name} className={form.target === name ? "is-on" : ""} onClick={() => setForm({ ...form, target: name })}>
                {name === "person" ? <UserRound size={14} /> : <UsersRound size={14} />} {name === "person" ? "One person" : "A whole crew"}
              </button>
            ))}
          </div>
          {form.target === "person" ? (
            <label>
              Person
              <select required value={form.personnel_id} onChange={set("personnel_id")}>
                <option value="">{people.length ? "Choose a deployed worker" : activity ? "No deployed worker from the executing company" : "Choose an activity first"}</option>
                {people.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code} · {item.full_name} · {item.trade} · {item.today}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label>
              Crew
              <select required value={form.crew_id} onChange={set("crew_id")}>
                <option value="">{crews.length ? "Choose a crew" : activity ? "No active crew from the executing company" : "Choose an activity first"}</option>
                {crews.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code}
                    {item.name ? ` · ${item.name}` : ""} · {item.strength.members} members
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Against demand (optional)
            <select value={form.demand_id} onChange={set("demand_id")}>
              <option value="">Not linked</option>
              {demands.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.number} · {item.headcount} × {item.trade}
                </option>
              ))}
            </select>
          </label>
          <label className="wide">
            Note
            <input value={form.note} onChange={set("note")} placeholder="e.g. Lift spools on rack 3" />
          </label>
          <p className="wide muted">
            Only workers deployed from the company executing the activity are listed. Leave, qualifications, mobilization, and overlapping shifts are checked when you save; a crew assignment adds everyone who can work and lists the rest.
          </p>
          <div className="wide hr-actions">
            <button className="primary" type="submit">
              Propose assignment
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setSkipped([]);
                setMade(0);
              }}
            >
              Close
            </button>
          </div>
          {made || skipped.length ? (
            <div className="wide mp-result">
              {made ? <p className="mp-result-ok">{made} assignment{made === 1 ? "" : "s"} proposed.</p> : null}
              {skipped.length ? (
                <>
                  <p className="mp-result-bad">Not assigned:</p>
                  <ul>
                    {skipped.map((item) => (
                      <li key={item.personnel_id}>
                        <strong>{item.person}</strong> · {item.problems.join(", ")}
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
            </div>
          ) : null}
        </form>
      ) : null}
      {c ? (
        <div className="mp-track mp-alloc-counts">
          <span>
            Proposed <strong>{c.proposed}</strong>
          </span>
          <span className="is-good">
            Confirmed <strong>{c.confirmed}</strong>
          </span>
          <span className={c.flagged ? "is-bad" : ""}>
            Need attention <strong>{c.flagged}</strong>
          </span>
          <span>
            Confirmed hours <strong>{c.planned_hours}</strong>
          </span>
        </div>
      ) : null}
      <label className="mp-check">
        <input type="checkbox" checked={showReleased} onChange={(event) => setShowReleased(event.target.checked)} /> Show released
      </label>
      {!data ? (
        <p className="muted">Loading allocations…</p>
      ) : visible.length === 0 ? (
        <p className="muted">No work is assigned in this period.</p>
      ) : (
        data.dates.map((iso) => {
          const rows = visible.filter((row) => row.work_date === iso);
          if (!rows.length) return null;
          const ready = rows.filter((row) => row.state === "Proposed" && !row.problems.length);
          return (
            <section key={iso} className="mp-alloc-day">
              <header>
                <h4>
                  {label(iso)}
                  {iso === board.today ? <span className="mp-today">Today</span> : null}
                </h4>
                {board.can_allocate && ready.length > 1 ? (
                  <button type="button" className="primary" onClick={() => void confirmReady(ready)}>
                    Confirm {ready.length} ready
                  </button>
                ) : null}
              </header>
              <div className="mp-table-wrap">
                <table className="mp-table mp-alloc-table">
                  <thead>
                    <tr>
                      <th>Shift</th>
                      <th>Activity</th>
                      <th>Person</th>
                      <th>Crew · demand</th>
                      <th>Planned</th>
                      <th>State</th>
                      <th>Checks</th>
                      {board.can_allocate ? <th>Actions</th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id} className={row.state === "Released" ? "is-released" : ""}>
                        <td>
                          <strong>{row.shift}</strong>
                        </td>
                        <td>
                          {row.activity}
                          {row.note ? <small className="muted mp-block">{row.note}</small> : null}
                        </td>
                        <td>
                          {row.person}
                          <small className="muted mp-block">{row.trade}</small>
                        </td>
                        <td>
                          {row.crew || "—"}
                          {row.demand ? <small className="muted mp-block">{row.demand}</small> : null}
                        </td>
                        <td>{row.planned} h</td>
                        <td>
                          <span className={`mp-pill mp-state-${row.state.toLowerCase()}`}>{row.state}</span>
                        </td>
                        <td>
                          {row.state === "Released" ? (
                            <small className="muted">{row.release_reason}</small>
                          ) : row.problems.length ? (
                            <div className="mp-problems">
                              <small>{row.state === "Proposed" ? "Blocks confirmation" : "Needs attention"}</small>
                              {row.problems.map((text) => (
                                <span key={text}>{text}</span>
                              ))}
                            </div>
                          ) : (
                            <span className="mp-ok">All checks pass</span>
                          )}
                        </td>
                        {board.can_allocate ? (
                          <td>
                            {row.state === "Released" ? null : (
                              <div className="mp-row-act">
                                {row.state === "Proposed" ? (
                                  <button type="button" className="primary" disabled={row.problems.length > 0} onClick={() => void act(row, "confirm")}>
                                    Confirm
                                  </button>
                                ) : null}
                                <input aria-label={`Release reason for ${row.person}`} placeholder="Reason to release" value={reasons[row.id] || ""} onChange={(event) => setReasons({ ...reasons, [row.id]: event.target.value })} />
                                <button type="button" disabled={(reasons[row.id] || "").trim().length < 3} onClick={() => void act(row, "release")}>
                                  Release
                                </button>
                              </div>
                            )}
                          </td>
                        ) : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          );
        })
      )}
    </>
  );
}

type ReturnLineRow = {
  personnel_id: number;
  person: string;
  trade: string;
  planned: string;
  attended: string;
  booked: string;
  attendance: string;
  flags: string[];
  reason: string;
};
type ReturnView = {
  note: string;
  work_date: string;
  shift: string;
  record: { id: number; state: string; note: string; return_reason: string; submitted_by: string; submitted_at: string; accepted_by: string; version: number } | null;
  lines: ReturnLineRow[];
  changed: boolean;
  flagged: number;
  can_submit: boolean;
  can_accept: boolean;
};

function DailyReturns({ pid, board, onError }: { pid: number; board: Board; onError: (text: string) => void }) {
  const shifts = board.shift_options.filter((item) => item.active);
  const [day, setDay] = useState(board.today);
  const [shiftId, setShiftId] = useState(shifts[0] ? String(shifts[0].id) : "");
  const [data, setData] = useState<ReturnView | null>(null);
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [note, setNote] = useState("");
  const [back, setBack] = useState("");

  async function load() {
    if (!shiftId) return;
    const view = await api<ReturnView>(`/projects/${pid}/manpower/returns?work_date=${day}&shift_id=${shiftId}`);
    setData(view);
    setReasons(Object.fromEntries(view.lines.map((line) => [line.personnel_id, line.reason])));
    setNote(view.record?.note || "");
  }
  useEffect(() => {
    setData(null);
    load().catch((err) => onError((err as Error).message));
  }, [pid, day, shiftId]);

  async function send(path: string, body: object) {
    onError("");
    try {
      await api(`/projects/${pid}/manpower/returns${path}`, "POST", body);
      setBack("");
      await load();
    } catch (err) {
      onError((err as Error).message);
    }
  }
  const record = data?.record || null;
  const editable = !record || record.state === "Returned";
  const ready = (data?.lines || []).every((line) => !line.flags.length || (reasons[line.personnel_id] || "").trim().length >= 3);

  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <ClipboardCheck size={18} strokeWidth={2.4} /> Daily returns
        </h3>
        <div className="mp-range mp-range-return">
          <label>
            Date
            <input type="date" value={day} max={board.today} onChange={(event) => event.target.value && setDay(event.target.value)} />
          </label>
          <label>
            Shift
            <select value={shiftId} onChange={(event) => setShiftId(event.target.value)}>
              {shifts.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {!shifts.length ? <p className="muted">No active shift yet. HR adds shifts on the HR screen.</p> : null}
      {data ? <p className="muted">{data.note}</p> : null}
      {record ? (
        <div className={`mp-return-state mp-return-${record.state.toLowerCase()}`}>
          <span className={`mp-pill mp-state-${record.state.toLowerCase()}`}>{record.state}</span>
          <span>
            Submitted by {record.submitted_by}
            {record.accepted_by ? ` · accepted by ${record.accepted_by}` : ""}
          </span>
          {record.return_reason ? <span className="mp-return-why">Sent back: {record.return_reason}</span> : null}
        </div>
      ) : null}
      {data?.changed ? <p className="mp-return-changed">Source records changed since submission. The saved return is shown unchanged.</p> : null}
      {shiftId && !data ? (
        <p className="muted">Loading return…</p>
      ) : data && !data.lines.length ? (
        <p className="muted">Nobody was confirmed or recorded in attendance on this shift.</p>
      ) : data ? (
        <div className="mp-table-wrap">
          <table className="mp-table mp-return-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Planned</th>
                <th>Attended</th>
                <th>Booked</th>
                <th>Checks</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line) => (
                <tr key={line.personnel_id} className={line.flags.length ? "is-flagged" : ""}>
                  <td>
                    {line.person}
                    <small className="muted mp-block">{line.trade}</small>
                  </td>
                  <td>{line.planned} h</td>
                  <td>
                    {line.attended} h<small className="muted mp-block">{line.attendance || "No record"}</small>
                  </td>
                  <td>{line.booked} h</td>
                  <td>
                    {line.flags.length ? (
                      <div className="mp-problems">
                        {line.flags.map((text) => (
                          <span key={text}>{text}</span>
                        ))}
                      </div>
                    ) : (
                      <span className="mp-ok">Matches</span>
                    )}
                  </td>
                  <td>
                    {editable && data.can_submit && line.flags.length ? (
                      <input
                        aria-label={`Reason for ${line.person}`}
                        placeholder="Why it differs"
                        value={reasons[line.personnel_id] || ""}
                        onChange={(event) => setReasons({ ...reasons, [line.personnel_id]: event.target.value })}
                      />
                    ) : (
                      <small>{line.reason || "—"}</small>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {data && data.lines.length && editable && data.can_submit ? (
        <div className="mp-return-actions">
          <input aria-label="Return note" placeholder="Note (optional)" value={note} onChange={(event) => setNote(event.target.value)} />
          <button
            type="button"
            className="primary"
            disabled={!ready}
            onClick={() =>
              void send("", {
                work_date: day,
                shift_id: Number(shiftId),
                note,
                reasons: Object.entries(reasons).map(([id, reason]) => ({ personnel_id: Number(id), reason })),
                version: record ? record.version : null,
              })
            }
          >
            Submit return
          </button>
        </div>
      ) : null}
      {record && record.state === "Submitted" && data?.can_accept ? (
        <div className="mp-return-actions">
          <button type="button" className="primary" onClick={() => void send(`/${record.id}/accept`, { version: record.version })}>
            Accept
          </button>
          <input aria-label="Reason to send back" placeholder="Reason to send back" value={back} onChange={(event) => setBack(event.target.value)} />
          <button type="button" disabled={back.trim().length < 3} onClick={() => void send(`/${record.id}/return`, { reason: back, version: record.version })}>
            Send back
          </button>
        </div>
      ) : null}
    </>
  );
}

type UsePct = number | null;
type UtilTrade = { trade_id: number; trade: string; people: number; available_hours: number; planned_hours: number; attended_hours: number; allocation_pct: UsePct; utilization_pct: UsePct };
type UtilPerson = { id: number; person: string; trade: string; available_days: number; available: string; planned: string; attended: string; allocation_pct: UsePct; utilization_pct: UsePct };
type Shortfall = { id: number; number: string; trade: string; priority: string; headcount: number; first_short: string; worst_gap: number; short_days: number; days: { date: string; needed: number; assigned: number; gap: number }[] };
type UtilData = { note: string; start: string; dates: string[]; trades: UtilTrade[]; people: UtilPerson[]; shortfalls: Shortfall[] };
type AlertRow = { kind: string; severity: "High" | "Medium" | "Low"; owner: string; since: string; age_days: number; detail: string; tab: string };
type AlertData = { note: string; today: string; alerts: AlertRow[]; counts: Record<string, number> };

function Meter({ label, pct }: { label: string; pct: UsePct }) {
  const tone = pct === null ? "none" : pct < 50 ? "low" : pct > 100 ? "over" : "ok";
  return (
    <div className={`mp-meter mp-meter-${tone}`}>
      <span>{label}</span>
      <div className="mp-meter-bar">
        <i style={{ width: `${Math.min(pct ?? 0, 100)}%` }} />
      </div>
      <strong>{pct === null ? "—" : `${pct}%`}</strong>
    </div>
  );
}

function Utilization({ pid, today, onError }: { pid: number; today: string; onError: (text: string) => void }) {
  const [start, setStart] = useState(() => {
    const day = new Date(`${today}T00:00:00Z`);
    day.setUTCDate(day.getUTCDate() - 6);
    return day.toISOString().slice(0, 10);
  });
  const [days, setDays] = useState(7);
  const [data, setData] = useState<UtilData | null>(null);

  useEffect(() => {
    setData(null);
    api<UtilData>(`/projects/${pid}/manpower/utilization?start=${start}&days=${days}`)
      .then(setData)
      .catch((err) => onError((err as Error).message));
  }, [pid, start, days]);

  const short = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });

  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <Gauge size={18} strokeWidth={2.4} /> Utilization and shortfalls
        </h3>
        <div className="mp-range mp-range-util">
          <label>
            From
            <input type="date" value={start} onChange={(event) => event.target.value && setStart(event.target.value)} />
          </label>
          <div className="mp-filter" role="radiogroup" aria-label="Days shown">
            {[7, 14, 28].map((n) => (
              <button key={n} type="button" role="radio" aria-checked={days === n} className={days === n ? "is-on" : ""} onClick={() => setDays(n)}>
                {n} days
              </button>
            ))}
          </div>
        </div>
      </div>
      {!data ? (
        <p className="muted">Loading utilization…</p>
      ) : (
        <>
          <p className="muted">{data.note}</p>
          <h4 className="mp-sub">By trade</h4>
          {!data.trades.length ? (
            <p className="muted">Nobody is deployed in this period. HR deploys and mobilizes people first.</p>
          ) : (
            <div className="mp-util-grid">
              {data.trades.map((row) => (
                <article key={row.trade_id} className="mp-util-card">
                  <header>
                    <strong>{row.trade || "No trade"}</strong>
                    <small>{row.people} {row.people === 1 ? "person" : "people"}</small>
                  </header>
                  <Meter label="Allocated" pct={row.allocation_pct} />
                  <Meter label="Utilized" pct={row.utilization_pct} />
                  <footer>
                    <span>Available {row.available_hours} h</span>
                    <span>Planned {row.planned_hours} h</span>
                    <span>Attended {row.attended_hours} h</span>
                  </footer>
                </article>
              ))}
            </div>
          )}
          <h4 className="mp-sub">Shortfalls against open demand</h4>
          {!data.shortfalls.length ? (
            <p className="mp-ok mp-ok-wide">Every open demand in this period has its approved headcount confirmed.</p>
          ) : (
            data.shortfalls.map((row) => (
              <article key={row.id} className="mp-short-card">
                <header>
                  <strong>
                    {row.number} · {row.trade}
                  </strong>
                  <span className={`mp-pill mp-prio-${row.priority.toLowerCase()}`}>{row.priority}</span>
                  <small className="muted">
                    Short on {row.short_days} day(s) from {short(row.first_short)}, up to {row.worst_gap} of {row.headcount}
                  </small>
                </header>
                <div className="mp-short-days">
                  {row.days.map((cell) => (
                    <span key={cell.date} className={cell.gap ? "is-short" : "is-met"} title={`${cell.assigned} of ${cell.needed} confirmed`}>
                      <small>{short(cell.date)}</small>
                      {cell.assigned}/{cell.needed}
                    </span>
                  ))}
                </div>
              </article>
            ))
          )}
          {data.people.length ? (
            <>
              <h4 className="mp-sub">By person</h4>
              <div className="mp-table-wrap">
                <table className="mp-table mp-util-table">
                  <thead>
                    <tr>
                      <th>Person</th>
                      <th>Available</th>
                      <th>Planned</th>
                      <th>Attended</th>
                      <th>Allocated</th>
                      <th>Utilized</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.people.map((row) => (
                      <tr key={row.id}>
                        <td>
                          {row.person}
                          <small className="muted mp-block">{row.trade}</small>
                        </td>
                        <td>
                          {row.available} h<small className="muted mp-block">{row.available_days} day(s)</small>
                        </td>
                        <td>{row.planned} h</td>
                        <td>{row.attended} h</td>
                        <td>
                          <Meter label="" pct={row.allocation_pct} />
                        </td>
                        <td>
                          <Meter label="" pct={row.utilization_pct} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </>
      )}
    </>
  );
}

function Alerts({ pid, onError, onOpen }: { pid: number; onError: (text: string) => void; onOpen: (tab: Tab) => void }) {
  const [data, setData] = useState<AlertData | null>(null);

  useEffect(() => {
    api<AlertData>(`/projects/${pid}/manpower/alerts`)
      .then(setData)
      .catch((err) => onError((err as Error).message));
  }, [pid]);

  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <BellRing size={18} strokeWidth={2.4} /> Alerts
        </h3>
      </div>
      {!data ? (
        <p className="muted">Working out alerts…</p>
      ) : (
        <>
          <p className="muted">{data.note}</p>
          {Object.keys(data.counts).length ? (
            <div className="mp-alert-counts">
              {Object.entries(data.counts).map(([kind, count]) => (
                <span key={kind}>
                  {kind} <strong>{count}</strong>
                </span>
              ))}
            </div>
          ) : null}
          {!data.alerts.length ? (
            <p className="mp-ok mp-ok-wide">No open alerts. Demand is covered, confirmed work passes its checks, and daily returns are filed.</p>
          ) : (
            <ul className="mp-alert-list">
              {data.alerts.map((row, index) => (
                <li key={`${row.kind}-${index}`} className={`mp-alert mp-alert-${row.severity.toLowerCase()}`}>
                  <span className={`mp-pill mp-sev-${row.severity.toLowerCase()}`}>{row.severity}</span>
                  <div>
                    <strong>{row.kind}</strong>
                    <p>{row.detail}</p>
                    <small className="muted">
                      Owner: {row.owner} · open {row.age_days === 0 ? "today" : `${row.age_days} day(s)`}
                    </small>
                  </div>
                  {(TABS as readonly string[]).includes(row.tab) ? (
                    <button type="button" onClick={() => onOpen(row.tab as Tab)}>
                      Open {row.tab}
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </>
  );
}

type ProdRow = {
  activity_id: number;
  code: string;
  name: string;
  unit: string;
  method: string;
  quantity: string | null;
  productive_hours: number;
  idle_hours: number;
  rework_hours: number;
  idle_pct: UsePct;
  rate: string | null;
  people: number;
  reports: number;
  idle_reasons: { reason: string; hours: number }[];
};
type ProdData = {
  note: string;
  start: string;
  end: string;
  activities: ProdRow[];
  totals: { productive_hours: number; idle_hours: number; rework_hours: number; idle_pct: UsePct; people: number };
};
type Summary = {
  week_start: string;
  today: string;
  allocation_pct: UsePct;
  utilization_pct: UsePct;
  planned_hours: number;
  attended_hours: number;
  short_today: number;
  alerts: { High: number; Medium: number; Low: number };
  alert_total: number;
  returns_pending: number;
  returns_sent_back: number;
  productive_hours: number;
  idle_hours: number;
  idle_pct: UsePct;
  top_idle: ProdRow[];
  top_output: ProdRow[];
};

const pctText = (pct: UsePct) => (pct === null ? "—" : `${pct}%`);

function WeekSummary({ week, onOpen }: { week: Summary; onOpen: (tab: Tab) => void }) {
  const cards: { label: string; value: string; hint: string; tone: string; tab: Tab }[] = [
    { label: "Utilization", value: pctText(week.utilization_pct), hint: `${week.attended_hours} h attended`, tone: week.utilization_pct !== null && week.utilization_pct < 50 ? "warn" : "good", tab: "Utilization" },
    { label: "Allocation", value: pctText(week.allocation_pct), hint: `${week.planned_hours} h planned`, tone: "info", tab: "Allocation" },
    { label: "Short today", value: String(week.short_today), hint: "people against open demand", tone: week.short_today ? "bad" : "good", tab: "Utilization" },
    { label: "Open alerts", value: String(week.alert_total), hint: `${week.alerts.High} high · ${week.alerts.Medium} medium`, tone: week.alerts.High ? "bad" : week.alert_total ? "warn" : "good", tab: "Alerts" },
    { label: "Returns to accept", value: String(week.returns_pending), hint: `${week.returns_sent_back} sent back`, tone: week.returns_pending || week.returns_sent_back ? "warn" : "good", tab: "Daily returns" },
    { label: "Idle time", value: pctText(week.idle_pct), hint: `${week.idle_hours} of ${Math.round((week.productive_hours + week.idle_hours) * 10) / 10} h`, tone: week.idle_pct !== null && week.idle_pct > 15 ? "warn" : "good", tab: "Productivity" },
  ];
  return (
    <>
      <h3 className="section-mark mp-mark">
        <TrendingUp size={18} strokeWidth={2.4} /> Last 7 days
      </h3>
      <div className="mp-week">
        {cards.map((card) => (
          <button key={card.label} type="button" className={`mp-week-card is-${card.tone}`} onClick={() => onOpen(card.tab)}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
            <small>{card.hint}</small>
          </button>
        ))}
      </div>
      {week.top_idle.length ? (
        <article className="hr-breakdown mp-idle">
          <h3>Most idle time</h3>
          <ul>
            {week.top_idle.map((row) => (
              <li key={row.activity_id}>
                <span>
                  {row.code} · {row.name}
                  {row.idle_reasons[0] ? <small className="muted mp-block">{row.idle_reasons[0].reason}</small> : null}
                </span>
                <strong>
                  {row.idle_hours} h idle · {pctText(row.idle_pct)}
                </strong>
              </li>
            ))}
          </ul>
        </article>
      ) : null}
      <p className="muted">
        From {week.week_start} to {week.today}. Read from HR, Manpower, daily returns, and approved Construction reports; nothing here is stored and no cost is shown.
      </p>
    </>
  );
}

function Productivity({ pid, today, onError }: { pid: number; today: string; onError: (text: string) => void }) {
  const back = (days: number) => {
    const day = new Date(`${today}T00:00:00Z`);
    day.setUTCDate(day.getUTCDate() - days);
    return day.toISOString().slice(0, 10);
  };
  const [start, setStart] = useState(back(6));
  const [end, setEnd] = useState(today);
  const [data, setData] = useState<ProdData | null>(null);

  useEffect(() => {
    setData(null);
    api<ProdData>(`/projects/${pid}/manpower/productivity?start=${start}&end=${end}`)
      .then(setData)
      .catch((err) => onError((err as Error).message));
  }, [pid, start, end]);

  const preset = (days: number) => {
    setEnd(today);
    setStart(back(days - 1));
  };
  const t = data?.totals;

  return (
    <>
      <div className="hr-toolbar">
        <h3 className="section-mark mp-mark">
          <TrendingUp size={18} strokeWidth={2.4} /> Labour productivity
        </h3>
        <div className="mp-range mp-range-prod">
          <label>
            From
            <input type="date" value={start} max={end} onChange={(event) => event.target.value && setStart(event.target.value)} />
          </label>
          <label>
            To
            <input type="date" value={end} min={start} max={today} onChange={(event) => event.target.value && setEnd(event.target.value)} />
          </label>
          <div className="mp-filter" role="group" aria-label="Quick periods">
            {[7, 30, 90].map((n) => (
              <button key={n} type="button" className={start === back(n - 1) && end === today ? "is-on" : ""} onClick={() => preset(n)}>
                {n} days
              </button>
            ))}
          </div>
        </div>
      </div>
      {!data ? (
        <p className="muted">Loading productivity…</p>
      ) : (
        <>
          <p className="muted">{data.note}</p>
          {t ? (
            <div className="mp-week mp-prod-totals">
              <div className="mp-week-card is-info">
                <span>Productive</span>
                <strong>{t.productive_hours} h</strong>
                <small>{t.people} people</small>
              </div>
              <div className={`mp-week-card ${t.idle_pct !== null && t.idle_pct > 15 ? "is-warn" : "is-good"}`}>
                <span>Idle</span>
                <strong>{t.idle_hours} h</strong>
                <small>{pctText(t.idle_pct)} of labour time</small>
              </div>
              <div className={`mp-week-card ${t.rework_hours ? "is-warn" : "is-good"}`}>
                <span>Rework</span>
                <strong>{t.rework_hours} h</strong>
                <small>included in productive and idle</small>
              </div>
            </div>
          ) : null}
          {!data.activities.length ? (
            <p className="muted">No approved Construction daily report with labour falls in this period.</p>
          ) : (
            <div className="mp-table-wrap">
              <table className="mp-table mp-prod-table">
                <thead>
                  <tr>
                    <th>Activity</th>
                    <th>Quantity</th>
                    <th>Productive</th>
                    <th>Output per man-hour</th>
                    <th>Idle</th>
                    <th>Rework</th>
                    <th>Main idle reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {data.activities.map((row) => (
                    <tr key={row.activity_id}>
                      <td>
                        <strong>{row.code}</strong> · {row.name}
                        <small className="muted mp-block">
                          {row.people} people · {row.reports} report(s)
                        </small>
                      </td>
                      <td>{row.quantity === null ? <small className="muted">Weighted milestones</small> : `${row.quantity} ${row.unit}`}</td>
                      <td>{row.productive_hours} h</td>
                      <td>{row.rate === null ? "—" : <strong className="mp-rate">{row.rate} {row.unit}/h</strong>}</td>
                      <td>
                        {row.idle_hours} h<small className={`mp-block ${row.idle_pct !== null && row.idle_pct > 15 ? "mp-idle-high" : "muted"}`}>{pctText(row.idle_pct)}</small>
                      </td>
                      <td>{row.rework_hours ? `${row.rework_hours} h` : "—"}</td>
                      <td>
                        {row.idle_reasons.length ? (
                          <div className="mp-problems mp-reasons">
                            {row.idle_reasons.map((item) => (
                              <span key={item.reason}>
                                {item.reason} · {item.hours} h
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="mp-ok">No idle time</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}