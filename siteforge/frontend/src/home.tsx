import { useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { api } from "./api";
import { ContinuousSupportRibbon } from "./home/poster/ContinuousSupportRibbon";
import { LifecycleConnectors } from "./home/poster/LifecycleConnectors";
import { LifecycleStageCard } from "./home/poster/LifecycleStageCard";
import { ModuleTile } from "./home/poster/ModuleTile";
import { SUPPORT, STAGES } from "./home/poster/lifecycleConfig";
import type { LifeModule } from "./home/Lifecycle";
import {
  AdminIcon,
  ChangeIcon,
  CommissioningIcon,
  ConstructionIcon,
  ContractsIcon,
  DocumentsIcon,
  EquipmentIcon,
  FinancialsIcon,
  GearIcon,
  HrIcon,
  LogisticsIcon,
  ManpowerIcon,
  MeetingsIcon,
  PlanningIcon,
  ProcurementIcon,
  ProgressIcon,
  ProjectIcon,
  QualityIcon,
  RequestsIcon,
  RisksIcon,
  SafetyIcon,
  StoresIcon,
} from "./home/moduleIcons";
import type { Page, Project, Session } from "./types";

type Access = "open" | "denied" | "later";
type Module = LifeModule & { tint: string };
type Group = {
  id: string;
  title: string;
  hint: string;
  icon: LucideIcon;
  tone: string;
  modules: Module[];
};

const GROUPS: Group[] = [
  {
    id: "engineering",
    title: "Project & engineering",
    hint: "From project setup to design, planning and performance tracking.",
    icon: AdminIcon,
    tone: "tone-blue",
    modules: [
      {
        id: "project",
        title: "Project Details",
        detail: "Key information, stakeholders and configuration",
        icon: ProjectIcon,
        tint: "tint-blue",
        built: true,
        permissions: ["projects.view"],
        destination: "projects",
      },
      {
        id: "engineering",
        title: "Engineering & Drawings",
        detail: "Drawings, models and technical documents",
        icon: GearIcon,
        tint: "tint-orange",
        built: true,
        permissions: ["drawings.view"],
        destination: "drawings",
      },
      {
        id: "planning",
        title: "Planning",
        detail: "Schedules, milestones and resources",
        icon: PlanningIcon,
        tint: "tint-blue",
        built: true,
        permissions: ["planning.view", "planning.manage"],
        destination: "planning",
      },
      {
        id: "progress",
        title: "Progress & Reporting",
        detail: "Track progress, KPIs and reports",
        icon: ProgressIcon,
        tint: "tint-blue",
        built: true,
        permissions: ["planning.view", "planning.manage"],
        destination: "progress",
      },
    ],
  },
  {
    id: "delivery",
    title: "Site operations",
    hint: "Manage the resources that deliver the project.",
    icon: LogisticsIcon,
    tone: "tone-green",
    modules: [
      {
        id: "procurement",
        title: "Procurement",
        detail: "Requirements, requisitions and purchasing",
        icon: ProcurementIcon,
        tint: "tint-orange",
        built: true,
        permissions: ["procurement.view"],
        destination: "procurement",
      },
      module("stores", "Stores & Inventory", "Materials, stock and warehousing", StoresIcon, "tint-blue"),
      {
        id: "construction",
        title: "Construction",
        detail: "Work packages, activities and site items",
        icon: ConstructionIcon,
        tint: "tint-orange",
        built: true,
        permissions: ["construction.view"],
        destination: "construction",
      },
      {
        id: "manpower",
        title: "Manpower",
        detail: "Workforce demand, crews and allocations",
        icon: ManpowerIcon,
        tint: "tint-blue",
        built: true,
        permissions: ["manpower.view"],
        destination: "manpower",
      },
      module("equipment", "Equipment & Tools", "Assets, tools and maintenance", EquipmentIcon, "tint-purple"),
      module("logistics", "Site Logistics", "Transport, access and site coordination", LogisticsIcon, "tint-orange"),
    ],
  },
];

const ASSURANCE: Group = {
  id: "assurance",
  title: "Quality, safety & handover",
  hint: "",
  icon: QualityIcon,
  tone: "tone-amber",
  modules: [
    {
      id: "quality",
      title: "Quality / QAQC",
      detail: "Inspections, test records and compliance",
      icon: QualityIcon,
      tint: "tint-rose",
      built: true,
      permissions: ["quality.view"],
      destination: "quality",
    },
    {
      id: "safety",
      title: "Safety / HSE",
      detail: "HSE references, permits, induction and incidents",
      icon: SafetyIcon,
      tint: "tint-orange",
      built: true,
      permissions: ["hse.view"],
      destination: "safety",
    },
    module("commissioning", "Commissioning & Handover", "Pre-commissioning, commissioning and final handover", CommissioningIcon, "tint-green"),
  ],
};

const COMMERCIAL: Group = {
  id: "commercial",
  title: "Business & people",
  hint: "Control cost, contracts and people.",
  icon: FinancialsIcon,
  tone: "tone-violet",
  modules: [
    {
      id: "financials",
      title: "Financials",
      detail: "Budgets, cost control and forecasting",
      icon: FinancialsIcon,
      tint: "tint-orange",
      built: true,
      permissions: ["financials.view", "financials.manage"],
      fullScope: true,
      destination: "financials",
    },
    module("contracts", "Contracts", "Contract management and variations", ContractsIcon, "tint-blue"),
    {
      id: "hr",
      title: "HR & Workforce",
      detail: "Personnel register and workforce lists",
      icon: HrIcon,
      tint: "tint-orange",
      built: true,
      permissions: ["hr.view"],
      destination: "hr",
    },
  ],
};

const CONTROL: Group = {
  id: "control",
  title: "Governance & collaboration",
  hint: "Keep information, decisions and changes under control.",
  icon: RequestsIcon,
  tone: "tone-blue",
  modules: [
    {
      id: "requests",
      title: "Requirements & Requests",
      detail: "Material requirements from manual entry, drawing MTOs and lists",
      icon: RequestsIcon,
      tint: "tint-orange",
      built: true,
      permissions: ["procurement.view"],
      destination: "requests",
    },
    {
      id: "documents",
      title: "Document Control",
      detail: "Controlled files, revisions and transmittals",
      icon: DocumentsIcon,
      tint: "tint-blue",
      built: true,
      permissions: ["drawings.view", "transmittals.issue"],
      destination: "drawings",
    },
    module("risks", "Risks & Issues", "Risk register, issues and mitigation", RisksIcon, "tint-rose"),
    module("change", "Change Management", "Change requests, assessments and approvals", ChangeIcon, "tint-teal"),
    {
      id: "meetings",
      title: "Meetings & Actions",
      detail: "Tasks and action tracking",
      icon: MeetingsIcon,
      tint: "tint-orange",
      built: true,
      permissions: [],
      destination: "tasks",
    },
    {
      id: "administration",
      title: "Administration",
      detail: "Project settings, lists and configuration",
      icon: AdminIcon,
      tint: "tint-slate",
      built: true,
      permissions: [],
      adminOnly: true,
      destination: "settings",
    },
  ],
};

function module(id: string, title: string, detail: string, icon: LucideIcon, tint: string): Module {
  return { id, title, detail, icon, tint, built: false, permissions: [], destination: `soon:${title}` };
}

function accessFor(session: Session, projectId: number | null, item: Module): Access {
  if (!item.built) return "open";
  if (item.adminOnly) return session.user.organization_admin ? "open" : "denied";
  if (item.permissions.length === 0) return "open";
  if (session.user.organization_admin) return "open";
  const memberships = session.memberships.filter(
    (row) => (!projectId || row.project_id === projectId) && (!item.fullScope || row.scope === "ALL"),
  );
  const allowed = memberships.some((row) =>
    item.permissions.some((permission) => row.permissions?.includes(permission)),
  );
  return allowed ? "open" : "denied";
}

function favoriteKey(userId: number) {
  return `siteforge.favorites.${userId}`;
}

export function HomePage({
  session,
  favoritesOnly,
  onOpen,
  onProject,
  onNotifications,
  onSignOut,
}: {
  session: Session;
  favoritesOnly: boolean;
  onOpen: (destination: string, projectId: number | null) => void;
  onProject: (projectId: number | null) => void;
  onNotifications: () => void;
  onSignOut: () => void;
}) {
  const [projectId, setProjectId] = useState<number | null>(null);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem(favoriteKey(session.user.id));
    try {
      setFavorites(stored ? (JSON.parse(stored) as string[]) : []);
    } catch {
      setFavorites([]);
    }
    void api<Page<Project>>("/projects?limit=100")
      .then((page) => {
        setProjects(page.items);
        if (page.items[0]?.id) {
          setProjectId(page.items[0].id);
          onProject(page.items[0].id);
        }
      })
      .catch(() => setProjectId(null));
  }, [session.user.id]);

  function visible(items: Module[]) {
    return items.filter((item) => !favoritesOnly || favorites.includes(item.id));
  }

  const catalog = [...GROUPS.flatMap((group) => group.modules), ...ASSURANCE.modules, ...COMMERCIAL.modules, ...CONTROL.modules];
  const modules = Object.fromEntries(catalog.map((item) => [item.id, item]));
  const shown = new Set(catalog.filter((item) => visible([item]).length > 0).map((item) => item.id));
  const denied = new Set(
    catalog.filter((item) => accessFor(session, projectId, item) === "denied").map((item) => item.id),
  );

  function tileState(id: string) {
    const item = modules[id];
    if (!item) return { item: undefined, disabled: true, reason: "This module is not available." };
    const blocked = denied.has(id) || !item.built;
    const reason = !item.built
      ? "This module is not available yet."
      : denied.has(id)
        ? "No access for this role."
        : undefined;
    return { item, disabled: blocked, reason };
  }

  const supportItems = SUPPORT.filter((row) => shown.has(row.id)).map((row) => {
    const state = tileState(row.id);
    return {
      id: row.id,
      label: row.label,
      icon: row.icon,
      disabled: state.disabled,
      reason: state.reason,
      onOpen: () => {
        if (state.item && !state.disabled) onOpen(state.item.destination, projectId);
      },
    };
  });

  return (
    <div className="zb-dashboard">
      <section className="zb-dashboard-hero">
        <div>
          <span className="zb-eyebrow">ZERROBUILD / INTERNAL WORKSPACE</span>
          <h1>Welcome back, {session.user.name.split(" ")[0]}.</h1>
          <p>One connected view of your industrial projects, decisions and delivery workflows.</p>
          <div className="zb-hero-tags"><span>Engineering to execution</span><span>Project-scoped access</span><span>Full lifecycle</span></div>
        </div>
        <div className="zb-hero-actions">
          <button type="button" onClick={onNotifications}>Notifications</button>
          <button type="button" onClick={() => onOpen("tasks", projectId)}>My tasks →</button>
        </div>
      </section>
      <div className="zb-home-toolbar">
        <div><strong>{favoritesOnly ? "My Favorites" : "Project command center"}</strong><small>Modules are available according to your current project permissions.</small></div>
        <label>Project context <select value={projectId ?? ""} onChange={(e) => { const id = e.target.value ? Number(e.target.value) : null; setProjectId(id); onProject(id); }}>
          <option value="">All my projects</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select></label>
      </div>
      <section className="zb-insight-strip">
        <div><span>Accessible projects</span><strong>{projects.length}</strong><small>From your existing project API</small></div>
        <div><span>Available modules</span><strong>{catalog.filter((m) => m.built && accessFor(session, projectId, m) === "open").length}</strong><small>Based on RBAC</small></div>
        <div><span>Project workflow</span><strong>Connected</strong><small>Engineering · Procurement · Execution</small></div>
        <div><span>Cross-system impact</span><strong>In progress</strong><small>Extended intelligence planned</small></div>
      </section>
      {favoritesOnly && favorites.length === 0 && <p className="zb-empty">You have no favorites yet. Open Home to browse the complete module catalog.</p>}
      {[...GROUPS, ASSURANCE, COMMERCIAL, CONTROL].map((group) => {
        const items = group.modules.filter((item) => visible([item]).length > 0);
        if (!items.length) return null;
        return <section className="zb-module-section" key={group.id}>
          <div className="zb-module-heading"><div><h2>{group.title}</h2><p>{group.hint}</p></div><span>{items.length} modules</span></div>
          <div className="zb-module-cards">{items.map((item) => {
            const state = tileState(item.id);
            const Icon = item.icon;
            return <button type="button" key={item.id} disabled={state.disabled} title={state.reason} className="zb-module-card" onClick={() => onOpen(item.destination, projectId)}>
              <span className="zb-module-icon"><Icon size={24} /></span>
              <strong>{item.title}</strong><small>{item.detail}</small>
              <span className="zb-module-foot">{!item.built ? "Coming later" : state.disabled ? "Access restricted" : "Open module →"}</span>
            </button>;
          })}</div>
        </section>;
      })}
      <div className="zb-home-footer">Existing access rules and backend APIs are unchanged. Cross-system analytics and partner transactions will be enabled as their backend integrations are completed.</div>
    </div>
  );
}

export function HelpPage() {
  return (
    <section className="panel">
      <h2>Help</h2>
      <p>The home page lists every ZerroBuild module. A tile opens only when that module exists and your role on the selected project allows it.</p>
      <p>Project Details, Engineering & Drawings, Planning, Progress & Reporting, Procurement, Financials, Document Control, and Meetings & Actions are available to people with the matching access. Administration is limited to an organization administrator.</p>
    </section>
  );
}

export function SettingsPage({
  session,
  onSignOut,
  onOpen,
}: {
  session: Session;
  onSignOut: () => void;
  onOpen: (destination: string) => void;
}) {
  return (
    <section className="panel">
      <h2>Settings</h2>
      <p>
        {session.user.name}
        <small>{session.user.email}</small>
      </p>
      {session.user.organization_admin ? (
        <div className="inline">
          <button onClick={() => onOpen("users")}>People & access</button>
          <button onClick={() => onOpen("companies")}>Companies</button>
          <button onClick={() => onOpen("audit")}>Audit history</button>
          <button onClick={() => onOpen("approval-levels")}>Approval levels</button>
        </div>
      ) : (
        <p className="muted">People, companies and audit history stay with an organization administrator.</p>
      )}
      <button className="primary" onClick={onSignOut}>
        Sign out
      </button>
    </section>
  );
}
