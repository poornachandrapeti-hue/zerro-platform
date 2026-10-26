import { FormEvent, Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, CalendarDays, ChevronDown, ChevronRight, CircleDollarSign, Gauge, Landmark, LayoutDashboard, ListTodo, MapPin, Pencil, Plus, Search, Trash2, UsersRound, Wrench, Zap } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api";
import type { LiveVerifiedProgress, PlanningMonitor, Phase9FinanceMonitor } from "./api";
import type { Contractor, Dashboard, Discipline, ProjectListItem, Role, SubTask, WorkPackage } from "./types";

const roles: Role[] = [
  { label: "Management view (role determined by login)", role: "CMD" },
  { label: "Director view (role determined by login)", role: "PROJECT_DIRECTOR" },
  { label: "Mechanical view (role determined by login)", role: "DISCIPLINE_HEAD", discipline: "MECHANICAL" },
  { label: "Electrical view (role determined by login)", role: "DISCIPLINE_HEAD", discipline: "ELECTRICAL" },
  { label: "Civil view (role determined by login)", role: "DISCIPLINE_HEAD", discipline: "CIVIL" },
];

const icons = { MECHANICAL: Wrench, ELECTRICAL: Zap, CIVIL: Landmark };
const colors = { MECHANICAL: "#087354", ELECTRICAL: "#d77806", CIVIL: "#198664" };
const STATUS_OPTIONS = ["On Track", "At Risk", "Delayed", "Completed"];
const WRITE_ROLES = new Set(["CMD", "PROJECT_DIRECTOR", "PROJECT_MANAGER", "DISCIPLINE_HEAD"]);
const PROJECT_CREATE_ROLES = new Set(["CMD", "PROJECT_DIRECTOR", "PROJECT_MANAGER"]);
const POLL_MS = 8000;

function money(value: number) {
  return `₹${(Number(value) / 10_000_000).toFixed(1)} Cr`;
}

function date(value: string) {
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(`${value}T00:00:00`));
}

function badge(status: string) {
  const name = status.toLowerCase().replaceAll(" ", "-");
  return <span className={`status ${name}`}><i />{status}</span>;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

/** Merge only observed timestamps; missing captures are null, never zero or interpolated. */
function planningCurveRows(monitor: PlanningMonitor) {
  const rows = new Map<string, { date: string; planned: number | null; verified: number | null }>();
  for (const p of monitor.planned) {
    const day = p.date.slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !Number.isFinite(p.planned_percent)) continue;
    const existing = rows.get(day) ?? { date: day, planned: null, verified: null };
    existing.planned = p.planned_percent;
    rows.set(day, existing);
  }
  for (const p of monitor.observed) {
    const day = p.date.slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) continue;
    const existing = rows.get(day) ?? { date: day, planned: null, verified: null };
    existing.verified = typeof p.verified_percent === "number" && Number.isFinite(p.verified_percent) ? p.verified_percent : null;
    rows.set(day, existing);
  }
  return [...rows.values()].sort((a,b) => a.date.localeCompare(b.date));
}

type ProgressForm = { actual_progress: string; actual_cost: string; status: string };
type ContractorForm = { code: string; name: string; contact_name: string; phone: string };
type ProjectForm = {
  code: string;
  name: string;
  client: string;
  location: string;
  start_date: string;
  planned_finish: string;
  forecast_finish: string;
  approved_budget: string;
  status: string;
};
type PackageForm = {
  discipline_code: string;
  code: string;
  name: string;
  area: string;
  contractor_id: string;
  weight: string;
  planned_progress: string;
  actual_progress: string;
  budget: string;
  committed_cost: string;
  actual_cost: string;
  start_date: string;
  target_date: string;
  status: string;
};
type SubTaskForm = {
  code: string;
  name: string;
  owner: string;
  weight: string;
  planned_progress: string;
  actual_progress: string;
  status: string;
  start_date: string;
  target_date: string;
  notes: string;
};

const emptyProjectForm = (): ProjectForm => ({
  code: "",
  name: "",
  client: "",
  location: "",
  start_date: todayIso(),
  planned_finish: todayIso(),
  forecast_finish: todayIso(),
  approved_budget: "",
  status: "Active",
});

const emptyPackageForm = (discipline = "MECHANICAL"): PackageForm => ({
  discipline_code: discipline,
  code: "",
  name: "",
  area: "",
  contractor_id: "",
  weight: "10",
  planned_progress: "0",
  actual_progress: "0",
  budget: "0",
  committed_cost: "0",
  actual_cost: "0",
  start_date: todayIso(),
  target_date: todayIso(),
  status: "On Track",
});

const emptySubTaskForm = (): SubTaskForm => ({
  code: "",
  name: "",
  owner: "",
  weight: "25",
  planned_progress: "0",
  actual_progress: "0",
  status: "On Track",
  start_date: todayIso(),
  target_date: todayIso(),
  notes: "",
});

export default function App() {
  const [roleIndex, setRoleIndex] = useState(0);
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [projectId, setProjectId] = useState<number>();
  const [dashboard, setDashboard] = useState<Dashboard>();
  const [planningSummary, setPlanningSummary] = useState<PlanningMonitor>();
  const [planningError, setPlanningError] = useState("");
  const [financeMonitor, setFinanceMonitor] = useState<Phase9FinanceMonitor>();
  const [financeMonitorError, setFinanceMonitorError] = useState("");
  const [financeStatus, setFinanceStatus] = useState("ALL");
  const [liveProgress, setLiveProgress] = useState<LiveVerifiedProgress>();
  const [liveState, setLiveState] = useState<"loading" | "available" | "unavailable">("loading");
  const [liveError, setLiveError] = useState("");
  const [disciplineCode, setDisciplineCode] = useState("ALL");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [lastSynced, setLastSynced] = useState<Date>();
  const [editingPackage, setEditingPackage] = useState<WorkPackage | null>(null);
  const [detailPackage, setDetailPackage] = useState<WorkPackage | null>(null);
  const [addingPackage, setAddingPackage] = useState(false);
  const [expandedPackageId, setExpandedPackageId] = useState<number | null>(null);
  const [taskPackage, setTaskPackage] = useState<WorkPackage | null>(null);
  const [editingTask, setEditingTask] = useState<SubTask | null>(null);
  const [subTaskForm, setSubTaskForm] = useState<SubTaskForm>(emptySubTaskForm);
  const [editingContractor, setEditingContractor] = useState<Contractor | null>(null);
  const [addingContractor, setAddingContractor] = useState(false);
  const [addingProject, setAddingProject] = useState(false);
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [progressForm, setProgressForm] = useState<ProgressForm>({ actual_progress: "", actual_cost: "", status: "On Track" });
  const [contractorForm, setContractorForm] = useState<ContractorForm>({ code: "", name: "", contact_name: "", phone: "" });
  const [projectForm, setProjectForm] = useState<ProjectForm>(emptyProjectForm);
  const [packageForm, setPackageForm] = useState<PackageForm>(emptyPackageForm);
  const role = roles[roleIndex];
  const canWrite = WRITE_ROLES.has(role.role);
  const canCreateProject = PROJECT_CREATE_ROLES.has(role.role);
  const isExecutiveView = role.role === "CMD" || role.role === "PROJECT_DIRECTOR";
  const showExecutionDetail = !isExecutiveView;

  const loadDashboard = useCallback(async (silent = false) => {
    if (!projectId) return;
    try {
      const data = await api.dashboard(projectId, role);
      setDashboard(data);
      setLastSynced(new Date());
      if (!silent) setError("");
    } catch (e) {
      if (!silent) setError(e instanceof Error ? e.message : "Failed to load dashboard");
    }
  }, [projectId, role]);

  useEffect(() => {
    setError("");
    api.projects(role).then((items) => {
      setProjects(items);
      setProjectId((current) => (current && items.some((p) => p.id === current) ? current : items[0]?.id));
    }).catch((e) => setError(e.message));
  }, [roleIndex]);

  useEffect(() => {
    if (!projectId) return;
    setDisciplineCode(role.discipline ?? "ALL");
    if (isExecutiveView) setDisciplineCode("ALL");
    loadDashboard();
  }, [projectId, roleIndex, loadDashboard, isExecutiveView, role.discipline]);

  useEffect(() => {
    setPlanningSummary(undefined);
    setPlanningError("");
    if (!projectId) return;
    let active = true;
    const pull = async () => {
      try {
        const result = await api.planningMonitor(projectId, role);
        if (active) { setPlanningSummary(result); setPlanningError(""); }
      } catch (e) {
        if (active) { setPlanningSummary(undefined); setPlanningError(e instanceof Error ? e.message : "Planning unavailable"); }
      }
    };
    void pull();
    const timer = window.setInterval(() => void pull(), 60000);
    return () => {active = false; window.clearInterval(timer);};
  }, [projectId, roleIndex]);

  useEffect(() => {
    // Fail closed on a project or role change; never display prior-scope proposal data.
    setFinanceMonitor(undefined);
    setFinanceMonitorError("");
    setFinanceStatus("ALL");
    if (!projectId) return;
    let active = true;
    const refresh = async () => {
      try {
        const data = await api.phase9FinanceMonitor(projectId, role);
        if (!active) return;
        // Do not accept a snapshot that claims booked values or certified scope.
        if (data.gl_posted_verified !== false || data.inventory_valuation_certified !== false ||
            data.billing_certified !== false || data.complete_history !== false ||
            data.read_only !== true || data.record_count !== data.proposal_records.length) {
          throw new Error("Unsupported Finance assurance or malformed sample");
        }
        setFinanceMonitor(data);
        setFinanceMonitorError("");
      } catch (e) {
        if (!active) return;
        setFinanceMonitor(undefined);
        setFinanceMonitorError(e instanceof Error ? e.message : "Finance monitoring unavailable");
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60000);
    return () => { active = false; window.clearInterval(timer); };
  }, [projectId, roleIndex]);

  useEffect(() => {
    // Never show source figures from a previous project or role while loading a new scope.
    setLiveProgress(undefined);
    setLiveError("");
    if (!projectId) { setLiveState("unavailable"); return; }
    setLiveState("loading");
    let active = true;
    const pull = async () => {
      try {
        const result = await api.liveProgress(projectId, role);
        if (!active) return;
        setLiveProgress(result);
        setLiveError("");
        setLiveState("available");
      } catch (e) {
        if (!active) return;
        setLiveProgress(undefined); // Never display stale verification figures on source outage.
        setLiveError(e instanceof Error ? e.message : "Verified source progress unavailable");
        setLiveState("unavailable");
      }
    };
    void pull();
    const timer = window.setInterval(() => void pull(), 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [projectId, roleIndex]);

  useEffect(() => {
    if (!projectId) return;
    const timer = window.setInterval(() => loadDashboard(true), POLL_MS);
    return () => window.clearInterval(timer);
  }, [projectId, loadDashboard]);

  useEffect(() => {
    if (!canWrite) return;
    api.contractors(role).then(setContractors).catch(() => setContractors([]));
  }, [roleIndex, canWrite]);

  const activeDiscipline: Discipline | undefined = dashboard?.disciplines.find((item) => item.code === disciplineCode);
  const packages = activeDiscipline?.work_packages ?? dashboard?.disciplines.flatMap((item) => item.work_packages) ?? [];
  const allPackages = dashboard?.disciplines.flatMap((item) => item.work_packages) ?? [];
  const filtered = useMemo(
    () => packages.filter((item) => `${item.name} ${item.area} ${item.contractor.name}`.toLowerCase().includes(query.toLowerCase())),
    [packages, query],
  );
  const actual = activeDiscipline?.actual_progress ?? dashboard?.overall_progress ?? 0;
  const planned = activeDiscipline?.planned_progress ?? dashboard?.planned_progress ?? 0;
  const packageDisciplineOptions = role.discipline
    ? dashboard?.disciplines.filter((item) => item.code === role.discipline) ?? []
    : dashboard?.disciplines ?? [];
  const canAddPackage = showExecutionDetail && canWrite && packageDisciplineOptions.length > 0;

  const contractorRollup = useMemo(() => {
    const map = new Map<number, { contractor: Contractor; packages: number; committed: number; budget: number }>();
    for (const item of allPackages) {
      const current = map.get(item.contractor.id);
      if (current) {
        current.packages += 1;
        current.committed += item.committed_cost;
        current.budget += item.budget;
      } else {
        map.set(item.contractor.id, {
          contractor: item.contractor,
          packages: 1,
          committed: item.committed_cost,
          budget: item.budget,
        });
      }
    }
    return [...map.values()].sort((a, b) => b.committed - a.committed || b.budget - a.budget);
  }, [allPackages]);
  const mainContractor = contractorRollup[0];

  function openProgress(item: WorkPackage) {
    setEditingPackage(item);
    setProgressForm({
      actual_progress: String(item.actual_progress),
      actual_cost: String(item.actual_cost),
      status: item.status,
    });
  }

  function openContractor(item: Contractor) {
    setAddingContractor(false);
    setEditingContractor(item);
    setContractorForm({ code: item.code, name: item.name, contact_name: item.contact_name, phone: item.phone });
  }

  function openAddContractor() {
    setEditingContractor(null);
    setAddingContractor(true);
    setContractorForm({ code: "", name: "", contact_name: "", phone: "" });
  }

  function openAddProject() {
    setAddingProject(true);
    setProjectForm(emptyProjectForm());
  }

  function openAddPackage() {
    const defaultDiscipline = role.discipline ?? (disciplineCode !== "ALL" ? disciplineCode : packageDisciplineOptions[0]?.code ?? "MECHANICAL");
    setDetailPackage(null);
    setAddingPackage(true);
    setPackageForm({
      ...emptyPackageForm(defaultDiscipline),
      contractor_id: contractors[0] ? String(contractors[0].id) : "",
    });
  }

  function openEditPackage(item: WorkPackage) {
    const owner = dashboard?.disciplines.find((disc) => disc.work_packages.some((pkg) => pkg.id === item.id));
    setAddingPackage(false);
    setDetailPackage(item);
    setPackageForm({
      discipline_code: owner?.code ?? role.discipline ?? "MECHANICAL",
      code: item.code,
      name: item.name,
      area: item.area,
      contractor_id: String(item.contractor.id),
      weight: String(item.weight),
      planned_progress: String(item.planned_progress),
      actual_progress: String(item.actual_progress),
      budget: String(item.budget),
      committed_cost: String(item.committed_cost),
      actual_cost: String(item.actual_cost),
      start_date: item.start_date,
      target_date: item.target_date,
      status: item.status,
    });
  }

  function openAddTask(item: WorkPackage) {
    setExpandedPackageId(item.id);
    setEditingTask(null);
    setTaskPackage(item);
    setSubTaskForm(emptySubTaskForm());
  }

  function openEditTask(parent: WorkPackage, task: SubTask) {
    setTaskPackage(parent);
    setEditingTask(task);
    setSubTaskForm({
      code: task.code,
      name: task.name,
      owner: task.owner,
      weight: String(task.weight),
      planned_progress: String(task.planned_progress),
      actual_progress: String(task.actual_progress),
      status: task.status,
      start_date: task.start_date ?? todayIso(),
      target_date: task.target_date ?? todayIso(),
      notes: task.notes ?? "",
    });
  }

  function packagePayload() {
    return {
      name: packageForm.name,
      area: packageForm.area,
      contractor_id: Number(packageForm.contractor_id),
      weight: Number(packageForm.weight),
      planned_progress: Number(packageForm.planned_progress),
      actual_progress: Number(packageForm.actual_progress),
      budget: Number(packageForm.budget),
      committed_cost: Number(packageForm.committed_cost),
      actual_cost: Number(packageForm.actual_cost),
      start_date: packageForm.start_date,
      target_date: packageForm.target_date,
      status: packageForm.status,
    };
  }

  async function saveProgress(event: FormEvent) {
    event.preventDefault();
    if (!editingPackage) return;
    setSaving(true);
    setError("");
    try {
      await api.updateProgress(editingPackage.id, role, {
        actual_progress: Number(progressForm.actual_progress),
        actual_cost: Number(progressForm.actual_cost),
        status: progressForm.status,
      });
      setEditingPackage(null);
      setNotice("Work status saved. Dashboard will refresh live.");
      await loadDashboard(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save progress");
    } finally {
      setSaving(false);
    }
  }

  async function saveProject(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const created = await api.createProject(role, {
        code: projectForm.code,
        name: projectForm.name,
        client: projectForm.client,
        location: projectForm.location,
        start_date: projectForm.start_date,
        planned_finish: projectForm.planned_finish,
        forecast_finish: projectForm.forecast_finish,
        approved_budget: Number(projectForm.approved_budget),
        status: projectForm.status,
      });
      const items = await api.projects(role);
      setProjects(items);
      setProjectId(created.id);
      setAddingProject(false);
      setNotice(`Project "${created.name}" created with Mechanical, Electrical and Civil disciplines.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create project");
    } finally {
      setSaving(false);
    }
  }

  async function removeProject() {
    if (!projectId || !dashboard) return;
    const name = dashboard.name;
    if (!window.confirm(`Delete project "${name}"?\n\nThis permanently removes all disciplines, sub-projects, sub-tasks, milestones and risks for this project.`)) {
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.deleteProject(projectId, role);
      const items = await api.projects(role);
      setProjects(items);
      setDashboard(undefined);
      setProjectId(items[0]?.id);
      setNotice(`Project "${name}" deleted.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete project");
    } finally {
      setSaving(false);
    }
  }

  async function savePackage(event: FormEvent) {
    event.preventDefault();
    if (!projectId) return;
    if (!packageForm.contractor_id) {
      setError("Select a contractor first. Add one if the list is empty.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload = packagePayload();
      if (detailPackage) {
        await api.updateWorkPackage(detailPackage.id, role, payload);
        setNotice(`Sub-project "${payload.name}" updated.`);
      } else {
        await api.createWorkPackage(projectId, packageForm.discipline_code, role, {
          ...payload,
          code: packageForm.code,
        });
        setNotice(`Sub-project "${payload.name}" added under ${packageForm.discipline_code}.`);
        setDisciplineCode(packageForm.discipline_code);
      }
      setAddingPackage(false);
      setDetailPackage(null);
      await loadDashboard(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save sub-project");
    } finally {
      setSaving(false);
    }
  }

  async function saveSubTask(event: FormEvent) {
    event.preventDefault();
    if (!taskPackage) return;
    setSaving(true);
    setError("");
    try {
      const payload = {
        name: subTaskForm.name,
        owner: subTaskForm.owner,
        weight: Number(subTaskForm.weight),
        planned_progress: Number(subTaskForm.planned_progress),
        actual_progress: Number(subTaskForm.actual_progress),
        status: subTaskForm.status,
        start_date: subTaskForm.start_date || null,
        target_date: subTaskForm.target_date || null,
        notes: subTaskForm.notes,
      };
      if (editingTask) {
        await api.updateSubTask(editingTask.id, role, payload);
        setNotice(`Sub-task "${payload.name}" updated under ${taskPackage.name}.`);
      } else {
        await api.createSubTask(taskPackage.id, role, { ...payload, code: subTaskForm.code });
        setNotice(`Sub-task "${payload.name}" added under ${taskPackage.name}.`);
      }
      setTaskPackage(null);
      setEditingTask(null);
      await loadDashboard(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save sub-task");
    } finally {
      setSaving(false);
    }
  }

  async function removeSubTask(task: SubTask) {
    if (!window.confirm(`Delete sub-task "${task.name}"?`)) return;
    setSaving(true);
    setError("");
    try {
      await api.deleteSubTask(task.id, role);
      setNotice(`Sub-task "${task.name}" deleted.`);
      await loadDashboard(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete sub-task");
    } finally {
      setSaving(false);
    }
  }

  async function saveContractor(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (addingContractor) {
        const created = await api.createContractor(role, {
          code: contractorForm.code,
          name: contractorForm.name,
          contact_name: contractorForm.contact_name,
          phone: contractorForm.phone,
        });
        setContractors((items) => [...items, created].sort((a, b) => a.name.localeCompare(b.name)));
        setNotice("Contractor added. You can now assign them to a sub-project.");
      } else if (editingContractor) {
        const updated = await api.updateContractor(editingContractor.id, role, contractorForm);
        setContractors((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        setNotice("Contractor details updated.");
      }
      setAddingContractor(false);
      setEditingContractor(null);
      await loadDashboard(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save contractor");
    } finally {
      setSaving(false);
    }
  }

  const initials = role.label.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <i><Gauge size={20} /></i>
          <div><b>Zerro-R-vision-360</b><small>Project Command Center</small></div>
        </div>
        <nav>
          <button className="on" type="button"><LayoutDashboard size={18}/>Overview</button>
          <button type="button"><Building2 size={18}/>Projects <em>{projects.length}</em></button>
          <button type="button"><CalendarDays size={18}/>Milestones</button>
          <button type="button"><AlertTriangle size={18}/>Risks</button>
        </nav>
        <div className="project">
          <small>Current project</small>
          <b>{dashboard?.name ?? "Loading…"}</b>
          <span>{dashboard ? `${dashboard.code} · ${dashboard.location}` : "Selecting workspace"}</span>
          {lastSynced && <p>Live · synced {lastSynced.toLocaleTimeString()}</p>}
        </div>
        <div className="user">
          <i>{initials}</i>
          <div>
            <b>{role.label}</b>
            <small>{role.discipline ? `${role.discipline} access` : "Full portfolio access"}</small>
          </div>
        </div>
      </aside>

      <main className="work">
        <header>
          <div>
            <small>{dashboard ? `${dashboard.client} · Executive completion` : "Project workspace"}</small>
            <h1>{dashboard?.name ?? "Zerro-R-vision-360"}</h1>
          </div>
          <div>
            <div className="select-wrap">
              <label>Project</label>
              <select value={projectId ?? ""} onChange={(e) => setProjectId(Number(e.target.value))}>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
            </div>
            <div className="select-wrap role">
              <label>View as</label>
              <select value={roleIndex} onChange={(e) => setRoleIndex(Number(e.target.value))}>
                {roles.map((item, index) => <option key={item.label} value={index}>{item.label}</option>)}
              </select>
            </div>
            {canCreateProject && (
              <button type="button" className="primary" onClick={openAddProject}>
                <Plus size={16}/> Add project
              </button>
            )}
            {canCreateProject && projectId && (
              <button type="button" className="danger-btn" onClick={removeProject} disabled={saving}>
                <Trash2 size={16}/> Delete project
              </button>
            )}
            {showExecutionDetail && canWrite && (
              <button type="button" onClick={openAddContractor}>
                <Plus size={16}/> Add contractor
              </button>
            )}
          </div>
        </header>

        {error && <div className="error">{error}</div>}
        {notice && <div className="notice" onClick={() => setNotice("")}>{notice} · click to dismiss</div>}

        {!dashboard ? (
          <div className="loading">Loading project dashboard…</div>
        ) : (
          <>
            <div className="elec-banner">
              <div>
                <b>{dashboard.code} · {activeDiscipline?.name ?? "All disciplines"}</b>
                <span>Planned finish {date(dashboard.planned_finish)} · Forecast {date(dashboard.forecast_finish)}</span>
              </div>
              <span>{dashboard.status}</span>
            </div>

            <div className="summary">
              <div>
                <div className="score">{actual.toFixed(0)}%</div>
                <p><b>Actual progress</b><small>{planned.toFixed(0)}% planned</small></p>
              </div>
              <div>
                <CircleDollarSign size={22}/>
                <p><b>{money(dashboard.actual_cost)}</b><small>Actual cost booked</small></p>
              </div>
              <div>
                <UsersRound size={22}/>
                <p><b>{new Set(packages.map((item) => item.contractor.id)).size}</b><small>Active contractors</small></p>
              </div>
            </div>

            <section className="panel verified-panel" aria-label="Finance proposal monitoring">
              <div className="panel-title"><div><small>ZERROBUILD FINANCE · READ ONLY · PROPOSAL SAMPLE</small><h3>Stores → Finance proposal monitoring</h3></div></div>
              <p className="verified-note">Approval and proposal status only. <b>Not GL-posted, not certified inventory valuation, and not a project-wide financial balance.</b></p>
              {financeMonitorError && <p className="verified-error" role="alert">Finance monitoring unavailable or not authorized: {financeMonitorError}</p>}
              {!financeMonitor && !financeMonitorError && <p className="verified-note">Loading Finance proposal sample…</p>}
              {financeMonitor && <>
                <p className="verified-note"><b>Source:</b> {financeMonitor.source} · <b>Snapshot:</b> {new Date(financeMonitor.as_of).toLocaleString()} · {financeMonitor.coverage}</p>
                <div className="planning-executive-stats" aria-label="Finance proposal sample status">
                  <div><strong>{financeMonitor.record_count}</strong><span>Sampled proposals</span></div>
                  {(["Draft", "Pending Review", "Approved", "Rejected"] as const).map((status) =>
                    <div key={status}><strong>{financeMonitor.status_counts[status] ?? 0}</strong><span>{status}</span></div>)}
                </div>
                <label htmlFor="phase9-finance-status">Filter proposal status </label>
                <select id="phase9-finance-status" value={financeStatus} onChange={(e) => setFinanceStatus(e.target.value)}>
                  <option value="ALL">All statuses</option>
                  {(["Draft", "Pending Review", "Approved", "Rejected"] as const).map((status) => <option key={status} value={status}>{status}</option>)}
                </select>
                <div className="table-scroll" role="region" aria-label="Finance proposal source references" tabIndex={0}>
                  <table><thead><tr><th>Proposal ID</th><th>Stock movement line ID</th><th>Status (not posted)</th><th>Revision</th></tr></thead>
                    <tbody>{financeMonitor.proposal_records.filter((row) => financeStatus === "ALL" || row.status === financeStatus).map((row) =>
                      <tr key={row.proposal_id}><td>{row.proposal_id}</td><td>{row.source_movement_line_id}</td><td>{row.status}</td><td>{row.proposal_revision}</td></tr>)}
                    {!financeMonitor.proposal_records.some((row) => financeStatus === "ALL" || row.status === financeStatus) &&
                      <tr><td colSpan={4}>No matching proposals in this bounded sample</td></tr>}
                    </tbody></table>
                </div>
              </>}
            </section>

            <section className="panel verified-panel" aria-label="Approved SiteForge Planning executive monitoring">
              <div className="panel-title"><div><small>SITEFORGE PLANNING · READ ONLY</small><h3>Executive planning monitoring</h3></div></div>
              {planningError && <p className="verified-error" role="alert">Planning summary unavailable or not authorized: {planningError}</p>}
              {!planningSummary && !planningError && <p className="verified-note">Loading approved Planning data…</p>}
              {planningSummary && <>
                <p className="verified-note"><b>Approved revision:</b> {planningSummary.approved_revision ?? "Not available"} · <b>Source refreshed:</b> {new Date(planningSummary.generated_at).toLocaleString()} · <b>Basis:</b> approved cumulative targets vs captured verified physical progress</p>
                <p className="verified-note">{planningSummary.note}</p>
                <div className="verified-panel" style={{margin:'12px 0',padding:12}}>
                  <h4>Latest approved current forecast</h4>
                  {planningSummary.approved_forecast ? <>
                    <p><b>Forecast finish:</b> {planningSummary.approved_forecast.project_finish ?? 'No unfinished activities'} · <b>Data date:</b> {planningSummary.approved_forecast.data_date} · <b>Revision:</b> {planningSummary.approved_forecast.revision}</p>
                    <p><b>Approved baseline finish:</b> {planningSummary.approved_forecast.baseline_finish ?? 'Unavailable'} · <b>Forecast difference:</b> {planningSummary.approved_forecast.finish_variance_days == null ? 'Unavailable' : `${planningSummary.approved_forecast.finish_variance_days > 0 ? '+' : ''}${planningSummary.approved_forecast.finish_variance_days} calendar days`}</p>
                    <p className="verified-note">{planningSummary.approved_forecast.note} Baseline comparison is a calendar-day estimate, not a contractual delay determination.</p>
                  </> : <p className="verified-note">No approved forecast revision available.</p>}
                </div>
                <div className="planning-executive-stats" aria-label="Planning alert status">
                  <div><strong>{planningSummary.active_alert_count}</strong><span>Active Planning alerts</span></div>
                  {Object.entries(planningSummary.alert_severity_counts).sort(([a],[b])=>a.localeCompare(b)).map(([severity,count]) =>
                    <div key={severity}><strong>{count}</strong><span>{severity} severity</span></div>)}
                </div>
                <h4 className="planning-chart-heading">Planned vs captured verified progress</h4>
                {planningSummary.planned.length || planningSummary.observed.length ?
                  <div className="planning-chart" role="img" aria-label="Chart of approved cumulative planned progress and captured verified progress by date; missing values are not interpolated">
                    <ResponsiveContainer width="100%" height={280}>
                      <LineChart data={planningCurveRows(planningSummary)} margin={{top:10,right:20,bottom:10,left:0}}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" tick={{fontSize:11}} minTickGap={22}/>
                        <YAxis domain={[0,100]} tickFormatter={v=>`${v}%`} tick={{fontSize:11}}/>
                        <Tooltip/>
                        <Line type="linear" name="Approved plan" dataKey="planned" stroke="#2563eb" strokeWidth={2} connectNulls={false} dot={{r:3}}/>
                        <Line type="linear" name="Captured verified" dataKey="verified" stroke="#059669" strokeWidth={2} connectNulls={false} dot={{r:3}}/>
                      </LineChart>
                    </ResponsiveContainer>
                  </div> : <p className="verified-note">No approved period targets or verified captures to chart.</p>}
                <p className="verified-note">Points are shown at their recorded dates only. This chart does not interpolate missing periods; capture points are not automatically a daily historical series. It does not calculate variance unless both values share a comparable approved period.</p>
                <div className="verified-table-wrap"><table className="verified-table"><thead><tr><th>Approved target date</th><th>Cumulative plan</th></tr></thead><tbody>
                  {planningSummary.planned.length ? planningSummary.planned.map((item,i) => <tr key={`${item.date}-${i}`}><td>{item.date}</td><td>{item.planned_percent.toFixed(1)}%</td></tr>) : <tr><td colSpan={2}>No approved cumulative period targets</td></tr>}
                </tbody></table></div>
                <div className="verified-table-wrap"><table className="verified-table"><thead><tr><th>Captured at</th><th>Verified physical</th></tr></thead><tbody>
                  {planningSummary.observed.length ? planningSummary.observed.map((item,i) => <tr key={`${item.date}-${i}`}><td>{new Date(item.date).toLocaleString()}</td><td>{item.verified_percent === null ? "Incomplete measurement" : `${item.verified_percent.toFixed(1)}%`}</td></tr>) : <tr><td colSpan={2}>No saved verified progress captures</td></tr>}
                </tbody></table></div>
                <h4 className="planning-chart-heading">Approved milestones</h4>
                <p className="verified-note">Baseline dates come from the frozen approved schedule. Completion percentage is verified from approved Construction progress only when the source link matches. The actual achievement date and variance remain unavailable until dated milestone evidence is verified.</p>
                <div className="verified-table-wrap"><table className="verified-table"><thead><tr><th>Code</th><th>Milestone</th><th>Approved finish</th><th>Verified completion</th><th>Actual date</th><th>Variance</th></tr></thead><tbody>
                  {planningSummary.milestones?.length ? planningSummary.milestones.map((m,i)=><tr key={`${m.activity_code}-${i}`}><td>{m.activity_code}</td><td>{m.activity_name}</td><td>{m.baseline_finish ?? "N/A"}</td><td>{m.completion_status === "verified_complete" ? "Verified 100%" : m.completion_status === "incomplete" ? `${m.verified_percent?.toFixed(1) ?? "N/A"}% verified${m.monitoring_status === "past_baseline_date_unverified" ? " · Past baseline date" : ""}` : (m.completion_status ?? "Not verified")}</td><td>{m.actual_finish ?? "Not established"}</td><td>{m.variance_days == null ? "N/A" : `${m.variance_days > 0 ? "+" : ""}${m.variance_days} days`}</td></tr>) : <tr><td colSpan={6}>No approved milestone calculations available</td></tr>}
                </tbody></table></div>
                <h4 className="planning-chart-heading">Critical path at baseline approval</h4>
                <p className="verified-note">{planningSummary.calculation_info?.note ?? "No supported approved CPM snapshot is available."} This is not a live reforecast.</p>
                <div className="verified-table-wrap"><table className="verified-table"><thead><tr><th>Activity</th><th>Start</th><th>Finish</th><th>Total float</th></tr></thead><tbody>
                  {planningSummary.critical_activities?.length ? planningSummary.critical_activities.map((a,i)=><tr key={`${a.activity_code}-${i}`}><td>{a.activity_code} — {a.activity_name}</td><td>{a.baseline_start ?? "N/A"}</td><td>{a.baseline_finish ?? "N/A"}</td><td>{a.total_float_hours == null ? "N/A" : `${a.total_float_hours} h`}</td></tr>) : <tr><td colSpan={4}>No approved critical-path activities available</td></tr>}
                </tbody></table></div>
                <h4 className="planning-chart-heading">Approved forecast risk and critical-path changes</h4>
                {planningSummary.advanced_monitoring ? <>
                  <p className="verified-note">{planningSummary.advanced_monitoring.note} {planningSummary.advanced_monitoring.unmatched_baseline_activity_count} baseline activities were absent from the unfinished forecast and are not compared.</p>
                  <div className="verified-table-wrap"><table className="verified-table"><thead><tr><th>Activity</th><th>Baseline critical</th><th>Forecast critical</th><th>Forecast finish</th></tr></thead><tbody>
                    {planningSummary.advanced_monitoring.criticality_changes.length ? planningSummary.advanced_monitoring.criticality_changes.map((a,i)=><tr key={`${a.activity_code}-${i}`}><td>{a.activity_code} — {a.activity_name}</td><td>{a.baseline_critical ? 'Yes':'No'}</td><td>{a.forecast_critical ? 'Yes':'No'}</td><td>{a.forecast_finish ?? 'Unavailable'}</td></tr>):<tr><td colSpan={4}>No comparable criticality changes</td></tr>}
                  </tbody></table></div>
                  <h4>Milestone forecast risk</h4>
                  <div className="verified-table-wrap"><table className="verified-table"><thead><tr><th>Milestone</th><th>Baseline</th><th>Forecast</th><th>Difference</th><th>Assessment</th></tr></thead><tbody>
                    {planningSummary.advanced_monitoring.milestone_risks.length ? planningSummary.advanced_monitoring.milestone_risks.map((m,i)=><tr key={`${m.activity_code}-${i}`}><td>{m.activity_code} — {m.activity_name}</td><td>{m.baseline_finish ?? 'Unavailable'}</td><td>{m.forecast_finish ?? 'Unavailable'}</td><td>{m.difference_calendar_days == null ? 'Unavailable' : `${m.difference_calendar_days > 0 ? '+':''}${m.difference_calendar_days} days`}</td><td>{m.risk_status.replaceAll('_',' ')}</td></tr>):<tr><td colSpan={5}>No comparable milestone risks</td></tr>}
                  </tbody></table></div>
                </>:<p className="verified-note">No approved, compatible forecast and baseline are available for risk comparisons.</p>}
                <h4 className="planning-chart-heading">Active planning alerts — authorized summary</h4>
                <p className="verified-note">Showing trigger metadata only. Alert descriptions, personnel, and linked source details remain in SiteForge with their native permissions.</p>
                <div className="verified-table-wrap"><table className="verified-table"><thead><tr><th>Alert ID</th><th>Severity</th><th>Status</th><th>Trigger</th><th>Detected</th></tr></thead><tbody>
                  {planningSummary.alerts_detail?.length ? planningSummary.alerts_detail.map(a=><tr key={a.id}><td>{a.id}</td><td>{a.severity}</td><td>{a.status}</td><td>{a.trigger_type}</td><td>{a.first_detected_at ? new Date(a.first_detected_at).toLocaleString() : "N/A"}</td></tr>) : <tr><td colSpan={5}>No active alerts</td></tr>}
                </tbody></table></div>
              </>}
            </section>

            <section className="panel verified-panel" aria-label="SiteForge verified work progress">
              <div className="panel-title">
                <div><small>SITEFORGE SOURCE · READ ONLY</small><h3>Verified work progress</h3></div>
                <span className={`verified-state ${liveState}`}>{liveState === "available" ? "Connected" : liveState === "loading" ? "Loading" : "Source unavailable"}</span>
              </div>
              {liveState === "loading" && <p className="verified-note">Loading approved progress reports for your authorized project and disciplines…</p>}
              {liveState === "unavailable" && <p className="verified-error">Live progress could not be loaded: {liveError}. Existing Command Center figures above are separate and must not be treated as verified SiteForge progress.</p>}
              {liveProgress && liveState === "available" && <>
                <p className="verified-note">Source updated {new Date(liveProgress.generated_at).toLocaleString()} · {liveProgress.package_count} authorized work packages. Verified quantities are based on approved daily progress reports, not QA acceptance or billing certification.</p>
                <p className="verified-note"><b>Approved baseline:</b> {liveProgress.approved_baseline?.status === "approved" ? `Revision ${liveProgress.approved_baseline.revision} · approval ${liveProgress.approved_baseline.approval_reference}. Variance uses approved cumulative quantities as of the progress snapshot.` : "No approved quantity baseline configured. Date reference below is illustrative only."}</p>
                {Boolean(liveProgress.alerts?.length) && <div className="verified-error"><b>{liveProgress.alerts?.length} verified schedule deviations</b>{liveProgress.alerts?.map(a => <p key={`${a.package_code}-${a.activity_code}`}>{a.discipline} · {a.package_code} / {a.activity_code}: {a.variance_pp.toFixed(1)} percentage points vs approved plan</p>)}</div>}
                {liveProgress.packages.length === 0 ? <p className="verified-note">No authorized work packages are available in the source project.</p> :
                  <div className="verified-table-wrap"><table className="verified-table"><thead><tr><th>Discipline / Work package</th><th>Activity</th><th>Approved quantity</th><th>Scope</th><th>Verified %</th><th>Approved plan</th><th>Variance (pp)</th><th>Date reference*</th></tr></thead><tbody>
                    {liveProgress.packages.flatMap((pkg) => pkg.activities.length ? pkg.activities.map((activity) => <tr key={`${pkg.package_id}-${activity.activity_id}`}><td><b>{pkg.discipline_name}</b><small>{pkg.package_code} · {pkg.name}</small></td><td>{activity.activity_code}</td><td>{activity.verified_quantity} {activity.unit}</td><td>{activity.scope_quantity} {activity.unit}</td><td><b>{Number(activity.verified_percent).toFixed(1)}%</b></td><td>{activity.baseline_status === "approved" ? `${activity.planned_percent?.toFixed(1)}%` : "Unavailable"}</td><td>{activity.baseline_status === "approved" ? activity.variance_pp?.toFixed(1) : "—"}</td><td>{pkg.date_reference_percent == null ? "Not available" : `${pkg.date_reference_percent.toFixed(1)}% (linear)*`}</td></tr>) : [<tr key={`empty-${pkg.package_id}`}><td><b>{pkg.discipline_name}</b><small>{pkg.package_code} · {pkg.name}</small></td><td colSpan={7}>No measurable activities reported yet</td></tr>])}
                  </tbody></table><p className="verified-note">* Elapsed-time reference only; progress varies by activity and cannot be interpreted as verified schedule variance.</p></div>}
              </>}
            </section>

            <div className="content">
              {isExecutiveView ? (
                <>
                  <section className="panel exec-overview">
                    <div className="panel-title">
                      <div><small>PROJECT SNAPSHOT</small><h3>Major project information</h3></div>
                    </div>
                    <div className="exec-grid">
                      <div><span><MapPin size={15}/> Location</span><b>{dashboard.location}</b></div>
                      <div><span><Building2 size={15}/> Client</span><b>{dashboard.client}</b></div>
                      <div><span>Project code</span><b>{dashboard.code}</b></div>
                      <div><span>Status</span><b>{dashboard.status}</b></div>
                      <div><span>Start date</span><b>{date(dashboard.start_date)}</b></div>
                      <div><span>Planned finish</span><b>{date(dashboard.planned_finish)}</b></div>
                      <div><span>Forecast finish</span><b>{date(dashboard.forecast_finish)}</b></div>
                      <div><span>Currency</span><b>{dashboard.currency}</b></div>
                      <div className="span-2">
                        <span><UsersRound size={15}/> Main contractor</span>
                        <b>{mainContractor ? mainContractor.contractor.name : "Not assigned yet"}</b>
                        <small>
                          {mainContractor
                            ? `${mainContractor.contractor.contact_name} · ${mainContractor.contractor.phone} · ${mainContractor.packages} packages · Committed ${money(mainContractor.committed)}`
                            : "Contractors appear when discipline heads add sub-projects"}
                        </small>
                      </div>
                      <div><span>Approved budget</span><b>{money(dashboard.approved_budget)}</b></div>
                      <div><span>Committed cost</span><b>{money(dashboard.budget_committed)}</b></div>
                      <div><span>Actual cost</span><b>{money(dashboard.actual_cost)}</b></div>
                      <div><span>Overall progress</span><b>{dashboard.overall_progress.toFixed(0)}% actual · {dashboard.planned_progress.toFixed(0)}% planned</b></div>
                    </div>
                  </section>

                  <section className="middle">
                    <article className="panel">
                      <div className="panel-title"><div><small>DISCIPLINE PERFORMANCE</small><h3>Planned vs actual</h3></div></div>
                      <div className="chart">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={dashboard.disciplines}>
                            <CartesianGrid stroke="#e8efeb" vertical={false}/>
                            <XAxis dataKey="name" axisLine={false} tickLine={false}/>
                            <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`}/>
                            <Tooltip/>
                            <Bar dataKey="planned_progress" name="Planned" fill="#b7c7bf" radius={[5, 5, 0, 0]}/>
                            <Bar dataKey="actual_progress" name="Actual" fill="#087354" radius={[5, 5, 0, 0]}/>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </article>
                    <article className="panel">
                      <div className="panel-title"><div><small>KEY CONTRACTORS</small><h3>By committed value</h3></div></div>
                      {contractorRollup.length ? contractorRollup.slice(0, 5).map((item) => (
                        <div className="list-row" key={item.contractor.id}>
                          <div className="date-box"><UsersRound size={16}/></div>
                          <div>
                            <b>{item.contractor.name}</b>
                            <small>{item.contractor.contact_name} · {item.packages} packages · {money(item.committed)} committed</small>
                          </div>
                          <span className="status on-track"><i />Active</span>
                        </div>
                      )) : (
                        <p className="empty">No contractor assignments yet.</p>
                      )}
                    </article>
                  </section>

                  <section className="panel">
                    <div className="panel-title"><div><small>UPCOMING</small><h3>Key milestones</h3></div></div>
                    {dashboard.milestones.length ? dashboard.milestones.map((item) => (
                      <div className="list-row" key={item.id}>
                        <div className="date-box">
                          <b>{new Date(`${item.forecast_date}T00:00:00`).getDate()}</b>
                          <small>{new Date(`${item.forecast_date}T00:00:00`).toLocaleString("en", { month: "short" })}</small>
                        </div>
                        <div><b>{item.name}</b><small>{item.discipline_code} · Plan {date(item.planned_date)}</small></div>
                        {badge(item.status)}
                      </div>
                    )) : (
                      <p className="empty">No milestones recorded.</p>
                    )}
                  </section>
                </>
              ) : (
                <>
              <div className="discipline-tabs">
                {!role.discipline && <button className={disciplineCode === "ALL" ? "active" : ""} onClick={() => setDisciplineCode("ALL")}>Project overview</button>}
                {dashboard.disciplines.map((item) => (
                  <button key={item.code} className={disciplineCode === item.code ? "active" : ""} onClick={() => setDisciplineCode(item.code)}>{item.name}</button>
                ))}
              </div>

              <section className="hero">
                <div className="completion">
                  <div className="ring" style={{ "--progress": `${actual}%` } as React.CSSProperties}>
                    <span><b>{actual.toFixed(0)}%</b><small>actual</small></span>
                  </div>
                  <div>
                    <small>{activeDiscipline?.name ?? "Overall"} completion</small>
                    <h2>{planned.toFixed(0)}% planned</h2>
                    <strong className={actual >= planned ? "ahead" : "behind"}>
                      {Math.abs(actual - planned).toFixed(1)}% {actual >= planned ? "ahead" : "behind"}
                    </strong>
                    <p>Weighted from discipline and work-package progress.</p>
                  </div>
                </div>
                <div className="kpis">
                  <div><span><CircleDollarSign size={17}/>Approved budget</span><b>{money(activeDiscipline?.budget ?? dashboard.approved_budget)}</b><small>Management baseline</small></div>
                  <div><span><CircleDollarSign size={17}/>Committed cost</span><b>{money(dashboard.budget_committed)}</b><small>Orders and contracts</small></div>
                  <div><span><CircleDollarSign size={17}/>Actual cost</span><b>{money(dashboard.actual_cost)}</b><small>Booked to date</small></div>
                  <div><span><UsersRound size={17}/>Contractors</span><b>{new Set(packages.map((item) => item.contractor.id)).size}</b><small>Active in this view</small></div>
                  <div><span><CalendarDays size={17}/>Milestones</span><b>{dashboard.milestones.length}</b><small>Current access scope</small></div>
                </div>
              </section>

              <section className="middle">
                <article className="panel">
                  <div className="panel-title"><div><small>DISCIPLINE PERFORMANCE</small><h3>Planned vs actual</h3></div></div>
                  <div className="chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={dashboard.disciplines}>
                        <CartesianGrid stroke="#e8efeb" vertical={false}/>
                        <XAxis dataKey="name" axisLine={false} tickLine={false}/>
                        <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`}/>
                        <Tooltip/>
                        <Bar dataKey="planned_progress" name="Planned" fill="#b7c7bf" radius={[5, 5, 0, 0]}/>
                        <Bar dataKey="actual_progress" name="Actual" fill="#087354" radius={[5, 5, 0, 0]}/>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </article>
                <article className="panel health">
                  <div className="panel-title"><div><small>DELIVERY HEALTH</small><h3>Disciplines</h3></div></div>
                  {dashboard.disciplines.map((item) => {
                    const Icon = icons[item.code as keyof typeof icons] ?? Building2;
                    const color = colors[item.code as keyof typeof colors] ?? "#087354";
                    return (
                      <button key={item.code} type="button" onClick={() => setDisciplineCode(item.code)}>
                        <span className="disc-icon" style={{ color, background: `${color}18` }}><Icon size={19}/></span>
                        <span><b>{item.name}</b><small>{item.weight}% project weight · Target {date(item.target_date)}</small></span>
                        <span className="bar"><i style={{ width: `${item.actual_progress}%`, background: color }}/></span>
                        <strong>{item.actual_progress}%</strong>
                      </button>
                    );
                  })}
                </article>
              </section>

              <section className="panel packages">
                <div className="panel-title package-title">
                  <div><small>SUB-PROJECTS / WORK PACKAGES</small><h3>{activeDiscipline?.name ?? "All discipline"} execution</h3></div>
                  <div className="package-actions">
                    {canAddPackage && (
                      <button type="button" className="primary" onClick={openAddPackage}>
                        <Plus size={15}/> Add sub-project
                      </button>
                    )}
                    <label className="search"><Search size={16}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search package, area or contractor"/></label>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Sub-project / package</th>
                        <th>Contractor</th>
                        <th>Area</th>
                        <th>Completion</th>
                        <th>Target</th>
                        <th>Budget</th>
                        <th>Actual cost</th>
                        <th>Status</th>
                        {canWrite && <th>Actions</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((item) => {
                        const expanded = expandedPackageId === item.id;
                        const tasks = item.sub_tasks ?? [];
                        return (
                          <Fragment key={item.id}>
                            <tr>
                              <td>
                                <button
                                  type="button"
                                  className="expand-btn"
                                  onClick={() => setExpandedPackageId(expanded ? null : item.id)}
                                >
                                  {expanded ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}
                                  <span>
                                    <b>{item.name}</b>
                                    <small>{item.code} · {tasks.length} sub-task{tasks.length === 1 ? "" : "s"}</small>
                                  </span>
                                </button>
                              </td>
                              <td>
                                <b>{item.contractor.name}</b>
                                <small>{item.contractor.contact_name} · {item.contractor.phone}</small>
                              </td>
                              <td>{item.area}</td>
                              <td>
                                <div className="progress"><span><i style={{ width: `${item.actual_progress}%` }}/></span><b>{item.actual_progress}%</b></div>
                                <small>Plan {item.planned_progress}%</small>
                              </td>
                              <td>{date(item.target_date)}</td>
                              <td>{money(item.budget)}</td>
                              <td>{money(item.actual_cost)}</td>
                              <td>{badge(item.status)}</td>
                              {canWrite && (
                                <td className="actions">
                                  <button type="button" title="Add sub-task" onClick={() => openAddTask(item)}><ListTodo size={14}/> Task</button>
                                  <button type="button" title="Edit sub-project details" onClick={() => openEditPackage(item)}><Pencil size={14}/> Details</button>
                                  <button type="button" title="Update work status" onClick={() => openProgress(item)}><Gauge size={14}/> Status</button>
                                  <button type="button" title="Edit contractor" onClick={() => openContractor(item.contractor)}><UsersRound size={14}/> Contractor</button>
                                </td>
                              )}
                            </tr>
                            {expanded && (
                              <tr className="subtask-row">
                                <td colSpan={canWrite ? 9 : 8}>
                                  <div className="subtask-panel">
                                    <div className="subtask-head">
                                      <b>Sub-tasks under {item.name}</b>
                                      {canWrite && (
                                        <button type="button" className="primary" onClick={() => openAddTask(item)}>
                                          <Plus size={14}/> Add sub-task
                                        </button>
                                      )}
                                    </div>
                                    {tasks.length ? (
                                      <table className="subtask-table">
                                        <thead>
                                          <tr>
                                            <th>Task</th>
                                            <th>Owner</th>
                                            <th>Weight</th>
                                            <th>Progress</th>
                                            <th>Target</th>
                                            <th>Status</th>
                                            {canWrite && <th>Actions</th>}
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {tasks.map((task) => (
                                            <tr key={task.id}>
                                              <td><b>{task.name}</b><small>{task.code}</small></td>
                                              <td>{task.owner || "—"}</td>
                                              <td>{task.weight}%</td>
                                              <td>
                                                <div className="progress"><span><i style={{ width: `${task.actual_progress}%` }}/></span><b>{task.actual_progress}%</b></div>
                                                <small>Plan {task.planned_progress}%</small>
                                              </td>
                                              <td>{task.target_date ? date(task.target_date) : "—"}</td>
                                              <td>{badge(task.status)}</td>
                                              {canWrite && (
                                                <td className="actions">
                                                  <button type="button" onClick={() => openEditTask(item, task)}><Pencil size={14}/> Edit</button>
                                                  <button type="button" onClick={() => removeSubTask(task)}><Trash2 size={14}/> Delete</button>
                                                </td>
                                              )}
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    ) : (
                                      <p className="empty">No sub-tasks yet. Discipline heads can add tasks like fit-up, welding, NDT, etc.</p>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        );
                      })}
                      {!filtered.length && (
                        <tr>
                          <td colSpan={canWrite ? 9 : 8}>
                            <p className="empty">No sub-projects yet. Discipline heads can add packages for their discipline.</p>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="bottom">
                <article className="panel">
                  <div className="panel-title"><div><small>UPCOMING</small><h3>Milestones</h3></div></div>
                  {dashboard.milestones.map((item) => (
                    <div className="list-row" key={item.id}>
                      <div className="date-box">
                        <b>{new Date(`${item.forecast_date}T00:00:00`).getDate()}</b>
                        <small>{new Date(`${item.forecast_date}T00:00:00`).toLocaleString("en", { month: "short" })}</small>
                      </div>
                      <div><b>{item.name}</b><small>{item.discipline_code} · Plan {date(item.planned_date)}</small></div>
                      {badge(item.status)}
                    </div>
                  ))}
                </article>
                <article className="panel">
                  <div className="panel-title"><div><small>MANAGEMENT ATTENTION</small><h3>Risks and blockers</h3></div></div>
                  {dashboard.risks.map((item) => (
                    <div className="risk-row" key={item.id}>
                      <span className={`severity ${item.severity.toLowerCase()}`}>{item.severity}</span>
                      <div><b>{item.title}</b><p>{item.mitigation}</p><small>{item.owner} · Due {date(item.due_date)}</small></div>
                    </div>
                  ))}
                </article>
              </section>
                </>
              )}
            </div>
          </>
        )}
      </main>

      {editingPackage && (
        <div className="modal-backdrop" onClick={() => setEditingPackage(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={saveProgress}>
            <h3>Update work status</h3>
            <p>{editingPackage.name} · {editingPackage.code}</p>
            <label>Actual progress (%)
              <input type="number" min={0} max={100} step={0.1} required value={progressForm.actual_progress}
                onChange={(e) => setProgressForm((f) => ({ ...f, actual_progress: e.target.value }))}/>
            </label>
            <label>Actual cost (₹)
              <input type="number" min={0} step={1} required value={progressForm.actual_cost}
                onChange={(e) => setProgressForm((f) => ({ ...f, actual_cost: e.target.value }))}/>
            </label>
            <label>Status
              <select value={progressForm.status} onChange={(e) => setProgressForm((f) => ({ ...f, status: e.target.value }))}>
                {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
            </label>
            <div className="modal-actions">
              <button type="button" className="ghost-btn" onClick={() => setEditingPackage(null)}>Cancel</button>
              <button type="submit" className="primary" disabled={saving}>{saving ? "Saving…" : "Save status"}</button>
            </div>
          </form>
        </div>
      )}

      {(addingContractor || editingContractor) && (
        <div className="modal-backdrop" onClick={() => { setAddingContractor(false); setEditingContractor(null); }}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={saveContractor}>
            <h3>{addingContractor ? "Add contractor" : "Edit contractor details"}</h3>
            <p>Discipline heads and managers can maintain contractor contact data.</p>
            {addingContractor && (
              <label>Code
                <input required maxLength={30} value={contractorForm.code}
                  onChange={(e) => setContractorForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}/>
              </label>
            )}
            <label>Company name
              <input required maxLength={160} value={contractorForm.name}
                onChange={(e) => setContractorForm((f) => ({ ...f, name: e.target.value }))}/>
            </label>
            <label>Contact person
              <input required maxLength={100} value={contractorForm.contact_name}
                onChange={(e) => setContractorForm((f) => ({ ...f, contact_name: e.target.value }))}/>
            </label>
            <label>Phone
              <input required maxLength={30} value={contractorForm.phone}
                onChange={(e) => setContractorForm((f) => ({ ...f, phone: e.target.value }))}/>
            </label>
            <div className="modal-actions">
              <button type="button" className="ghost-btn" onClick={() => { setAddingContractor(false); setEditingContractor(null); }}>Cancel</button>
              <button type="submit" className="primary" disabled={saving}>{saving ? "Saving…" : "Save contractor"}</button>
            </div>
          </form>
        </div>
      )}

      {addingProject && (
        <div className="modal-backdrop" onClick={() => setAddingProject(false)}>
          <form className="modal modal-wide" onClick={(e) => e.stopPropagation()} onSubmit={saveProject}>
            <h3>Add new project</h3>
            <p>Creates Mechanical, Electrical and Civil disciplines with budget split 40% / 30% / 30%.</p>
            <div className="modal-grid">
              <label>Project code
                <input required maxLength={40} value={projectForm.code}
                  onChange={(e) => setProjectForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}/>
              </label>
              <label>Status
                <select value={projectForm.status} onChange={(e) => setProjectForm((f) => ({ ...f, status: e.target.value }))}>
                  {["Active", "On Track", "At Risk", "Delayed"].map((status) => <option key={status} value={status}>{status}</option>)}
                </select>
              </label>
              <label className="span-2">Project name
                <input required maxLength={180} value={projectForm.name}
                  onChange={(e) => setProjectForm((f) => ({ ...f, name: e.target.value }))}/>
              </label>
              <label>Client
                <input required maxLength={120} value={projectForm.client}
                  onChange={(e) => setProjectForm((f) => ({ ...f, client: e.target.value }))}/>
              </label>
              <label>Location
                <input required maxLength={160} value={projectForm.location}
                  onChange={(e) => setProjectForm((f) => ({ ...f, location: e.target.value }))}/>
              </label>
              <label>Start date
                <input type="date" required value={projectForm.start_date}
                  onChange={(e) => setProjectForm((f) => ({ ...f, start_date: e.target.value }))}/>
              </label>
              <label>Planned finish
                <input type="date" required value={projectForm.planned_finish}
                  onChange={(e) => setProjectForm((f) => ({ ...f, planned_finish: e.target.value }))}/>
              </label>
              <label>Forecast finish
                <input type="date" required value={projectForm.forecast_finish}
                  onChange={(e) => setProjectForm((f) => ({ ...f, forecast_finish: e.target.value }))}/>
              </label>
              <label>Approved budget (₹)
                <input type="number" min={1} step={1} required value={projectForm.approved_budget}
                  onChange={(e) => setProjectForm((f) => ({ ...f, approved_budget: e.target.value }))}/>
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" className="ghost-btn" onClick={() => setAddingProject(false)}>Cancel</button>
              <button type="submit" className="primary" disabled={saving}>{saving ? "Creating…" : "Create project"}</button>
            </div>
          </form>
        </div>
      )}

      {(addingPackage || detailPackage) && (
        <div className="modal-backdrop" onClick={() => { setAddingPackage(false); setDetailPackage(null); }}>
          <form className="modal modal-wide" onClick={(e) => e.stopPropagation()} onSubmit={savePackage}>
            <h3>{detailPackage ? "Edit sub-project details" : "Add sub-project"}</h3>
            <p>
              {role.discipline
                ? `${role.discipline} head can enter packages only for this discipline.`
                : "Enter package details, contractor, weight, budget and dates."}
            </p>
            <div className="modal-grid">
              <label>Discipline
                <select
                  required
                  disabled={Boolean(detailPackage) || Boolean(role.discipline)}
                  value={packageForm.discipline_code}
                  onChange={(e) => setPackageForm((f) => ({ ...f, discipline_code: e.target.value }))}
                >
                  {packageDisciplineOptions.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
                </select>
              </label>
              <label>Status
                <select value={packageForm.status} onChange={(e) => setPackageForm((f) => ({ ...f, status: e.target.value }))}>
                  {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}
                </select>
              </label>
              {!detailPackage && (
                <label>Package code
                  <input required maxLength={40} value={packageForm.code}
                    onChange={(e) => setPackageForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}/>
                </label>
              )}
              <label className={detailPackage ? "span-2" : undefined}>Sub-project name
                <input required maxLength={160} value={packageForm.name}
                  onChange={(e) => setPackageForm((f) => ({ ...f, name: e.target.value }))}/>
              </label>
              <label>Area
                <input required maxLength={120} value={packageForm.area}
                  onChange={(e) => setPackageForm((f) => ({ ...f, area: e.target.value }))}/>
              </label>
              <label>Contractor
                <select required value={packageForm.contractor_id}
                  onChange={(e) => setPackageForm((f) => ({ ...f, contractor_id: e.target.value }))}>
                  <option value="">Select contractor</option>
                  {contractors.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              <label>Weight (%)
                <input type="number" min={0.01} max={100} step={0.01} required value={packageForm.weight}
                  onChange={(e) => setPackageForm((f) => ({ ...f, weight: e.target.value }))}/>
              </label>
              <label>Planned progress (%)
                <input type="number" min={0} max={100} step={0.1} required value={packageForm.planned_progress}
                  onChange={(e) => setPackageForm((f) => ({ ...f, planned_progress: e.target.value }))}/>
              </label>
              <label>Actual progress (%)
                <input type="number" min={0} max={100} step={0.1} required value={packageForm.actual_progress}
                  onChange={(e) => setPackageForm((f) => ({ ...f, actual_progress: e.target.value }))}/>
              </label>
              <label>Budget (₹)
                <input type="number" min={0} step={1} required value={packageForm.budget}
                  onChange={(e) => setPackageForm((f) => ({ ...f, budget: e.target.value }))}/>
              </label>
              <label>Committed cost (₹)
                <input type="number" min={0} step={1} required value={packageForm.committed_cost}
                  onChange={(e) => setPackageForm((f) => ({ ...f, committed_cost: e.target.value }))}/>
              </label>
              <label>Actual cost (₹)
                <input type="number" min={0} step={1} required value={packageForm.actual_cost}
                  onChange={(e) => setPackageForm((f) => ({ ...f, actual_cost: e.target.value }))}/>
              </label>
              <label>Start date
                <input type="date" required value={packageForm.start_date}
                  onChange={(e) => setPackageForm((f) => ({ ...f, start_date: e.target.value }))}/>
              </label>
              <label>Target date
                <input type="date" required value={packageForm.target_date}
                  onChange={(e) => setPackageForm((f) => ({ ...f, target_date: e.target.value }))}/>
              </label>
            </div>
            {!contractors.length && (
              <p>No contractors yet. Use <b>Add contractor</b> first, then create the sub-project.</p>
            )}
            <div className="modal-actions">
              <button type="button" className="ghost-btn" onClick={() => { setAddingPackage(false); setDetailPackage(null); }}>Cancel</button>
              <button type="submit" className="primary" disabled={saving || !contractors.length}>
                {saving ? "Saving…" : detailPackage ? "Save details" : "Create sub-project"}
              </button>
            </div>
          </form>
        </div>
      )}

      {taskPackage && (
        <div className="modal-backdrop" onClick={() => { setTaskPackage(null); setEditingTask(null); }}>
          <form className="modal modal-wide" onClick={(e) => e.stopPropagation()} onSubmit={saveSubTask}>
            <h3>{editingTask ? "Edit sub-task" : "Add sub-task"}</h3>
            <p>Under sub-project <b>{taskPackage.name}</b>. Progress rolls up to the sub-project automatically.</p>
            <div className="modal-grid">
              {!editingTask && (
                <label>Task code
                  <input required maxLength={40} value={subTaskForm.code}
                    onChange={(e) => setSubTaskForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}/>
                </label>
              )}
              <label className={editingTask ? "span-2" : undefined}>Task name
                <input required maxLength={160} value={subTaskForm.name}
                  onChange={(e) => setSubTaskForm((f) => ({ ...f, name: e.target.value }))}/>
              </label>
              <label>Owner
                <input maxLength={100} value={subTaskForm.owner}
                  onChange={(e) => setSubTaskForm((f) => ({ ...f, owner: e.target.value }))}/>
              </label>
              <label>Status
                <select value={subTaskForm.status} onChange={(e) => setSubTaskForm((f) => ({ ...f, status: e.target.value }))}>
                  {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}
                </select>
              </label>
              <label>Weight (%)
                <input type="number" min={0.01} max={100} step={0.01} required value={subTaskForm.weight}
                  onChange={(e) => setSubTaskForm((f) => ({ ...f, weight: e.target.value }))}/>
              </label>
              <label>Planned progress (%)
                <input type="number" min={0} max={100} step={0.1} required value={subTaskForm.planned_progress}
                  onChange={(e) => setSubTaskForm((f) => ({ ...f, planned_progress: e.target.value }))}/>
              </label>
              <label>Actual progress (%)
                <input type="number" min={0} max={100} step={0.1} required value={subTaskForm.actual_progress}
                  onChange={(e) => setSubTaskForm((f) => ({ ...f, actual_progress: e.target.value }))}/>
              </label>
              <label>Start date
                <input type="date" value={subTaskForm.start_date}
                  onChange={(e) => setSubTaskForm((f) => ({ ...f, start_date: e.target.value }))}/>
              </label>
              <label>Target date
                <input type="date" value={subTaskForm.target_date}
                  onChange={(e) => setSubTaskForm((f) => ({ ...f, target_date: e.target.value }))}/>
              </label>
              <label className="span-2">Notes
                <input maxLength={500} value={subTaskForm.notes}
                  onChange={(e) => setSubTaskForm((f) => ({ ...f, notes: e.target.value }))}/>
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" className="ghost-btn" onClick={() => { setTaskPackage(null); setEditingTask(null); }}>Cancel</button>
              <button type="submit" className="primary" disabled={saving}>{saving ? "Saving…" : editingTask ? "Save task" : "Create task"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
