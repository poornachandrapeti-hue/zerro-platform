import CommandCenterWorkspace from "./command-center/CommandCenterWorkspace";
import { ReferenceHome } from "./ReferenceHome";
import { useEffect, useState, FormEvent } from "react";
import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  Building2,
  Eye,
  EyeOff,
  FolderKanban,
  Lightbulb,
  Lock,
  LogOut,
  Mail,
  Plus,
  ArrowRight,
  MapPin,
  Users,
  CheckCircle2,
  Bell,
  HelpCircle,
  Home,
  ListChecks,
  Settings,
  Truck,
  ShieldCheck,
  Star,
  Contact,
  Phone,
  Handshake,
  ClipboardCheck,
  ShoppingCart, FileText, HardHat, AlertTriangle, CalendarDays, ChartNoAxesCombined, Wallet, ScrollText, Warehouse, Wrench,
  IdCard, UsersRound,
} from "lucide-react";
import { api, setCsrf } from "./api";
import {
  AttachmentsPanel,
  HistoryPanel,
  InboxPage,
  MyTasksPage,
  NotificationsPage,
  ReviewsPanel,
  StatusPanel,
  TasksPanel,
} from "./phase2";
import { DrawingsHome, EngineeringBoard } from "./engineering";
import { ProcurementHome } from "./procurement";
import { StoresHome } from "./stores";
import { EquipmentHome } from "./equipment";
import { PlanningHome } from "./planning";
import { FinancialsHome } from "./financials";
import { ContractsHome, PartnerContracts } from "./contracts";
import { ProgressMonitoringHome } from "./progress_monitoring";
import { RequirementsHome } from "./materials";
import { ConstructionHome } from "./construction";
import { QualityHome } from "./quality";
import { HseHome } from "./hse";
import { HrHome } from "./hr";
import { ManpowerHome } from "./manpower";
import { HelpPage, HomePage, SettingsPage } from "./home";
import { Sidebar } from "./home/Sidebar";
import { PartnerHome } from "./partner/PartnerHome";
import { PartnerPurchaseOrders } from "./partner/PartnerPurchaseOrders";
import { PartnerDeliveries } from "./partner/PartnerDeliveries";
import { PartnerMaterialRequests } from "./partner/PartnerMaterialRequests";
import { PartnerMaterialHandovers } from "./partner/PartnerMaterialHandovers";
import { PartnerMaterialReturns } from "./partner/PartnerMaterialReturns";
import { PartnerPlanning } from "./partner/PartnerPlanning";
import { ModulePlaceholder } from "./home/ModuleSection";
import { Button } from "./components/ui/button";
import { ApprovalLevelsPage, OPEN_APPROVAL_LEVELS, type ApprovalTarget } from "./approval_levels";
import type {
  User,
  Company,
  Catalog,
  Session,
  Page,
  Project,
  Membership,
  Area,
  Participant,
  AuditEvent,
} from "./types";
const blank: Project = {
  code: "",
  name: "",
  description: "",
  project_type: "Industrial Plant",
  status: "Draft",
  site_name: "",
  address: "",
  country: "India",
  state: "",
  city: "",
  postal_code: "",
  timezone: "Asia/Kolkata",
  latitude: null,
  longitude: null,
  planned_start: null,
  planned_finish: null,
  actual_start: null,
  actual_finish: null,
  client_company_id: null,
  main_contractor_company_id: null,
  pmc_company_id: null,
  subcontractor_ids: [],
  lead_pm_id: null,
  discipline_ids: [],
  disciplines: [],
  hold_reason: "",
  cancellation_reason: "",
  contract_number: "",
  contract_date: null,
  contract_value: null,
  currency: "INR",
};
function Err({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}
function Badge({ text }: { text: string }) {
  return (
    <span className={"badge " + text.toLowerCase().replaceAll(" ", "-")}>
      {text}
    </span>
  );
}
function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 36 36" width="34" height="34">
        <polygon points="18,2 32,10 32,26 18,34 4,26 4,10" fill="#f5a018" />
        <path
          d="M12.5 15.2c1.6-2.4 6.2-2.6 8.2-.4 1.6 1.8.4 3.4-2.2 4.2-3.2 1-5.6 2-4.4 4.2 1.4 2.4 6.4 2.2 8.4-.2"
          fill="none"
          stroke="white"
          strokeWidth="2.3"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

function Login({ done }: { done: () => void }) {
  const [email, setEmail] = useState(() => localStorage.getItem("siteforge-login-email") || "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const r = await api<{ csrf_token: string }>("/auth/login", "POST", {
        email,
        password,
      });
      localStorage.setItem("siteforge-login-email", email);
      setCsrf(r.csrf_token);
      done();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login login-v10">
      <section className="login-left-panel">
        <div className="login-brand login-brand-v10">
          <span className="login-brand-z" aria-hidden="true">Z</span>
          <span className="login-brand-word">ZerroBuild</span>
        </div>
        <div className="login-copy-v10">
          <h1 className="login-platform-title">Industrial Construction<br />End-to-End Digital Platform.</h1>
          <div className="login-feature-list">
            <div className="login-feature-item">
              <span className="login-feature-icon"><Users size={22} /></span>
              <div>
                <strong>Connected Workflows</strong>
                <p>Break down silos. Keep projects moving.</p>
              </div>
            </div>
            <div className="login-feature-item">
              <span className="login-feature-icon"><BarChart3 size={22} /></span>
              <div>
                <strong>Cross-System Intelligence</strong>
                <p>Turn data into smarter decisions.</p>
              </div>
            </div>
            <div className="login-feature-item">
              <span className="login-feature-icon"><Handshake size={22} /></span>
              <div>
                <strong>Unified Partner Ecosystem</strong>
                <p>Owners, contractors and suppliers — all in sync.</p>
              </div>
            </div>
            <div className="login-feature-item">
              <span className="login-feature-icon"><ShieldCheck size={22} /></span>
              <div>
                <strong>End-to-End Traceability</strong>
                <p>From design to commissioning and beyond.</p>
              </div>
            </div>
          </div>
          <div className="login-bottom-copy">
            <h2>Build with clarity.</h2>
            <p>From engineering drawings to final billing.</p>
          </div>
        </div>
      </section>
      <section className="login-form login-form-v10">
        <div className="login-card login-card-v10">
          <div className="ref-login-tabs login-tabs-v10">
            <button type="button" className="active">Company Login</button>
            <button type="button" onClick={() => setNotice("SSO is not yet enabled for this deployment.")}>SSO</button>
          </div>
          <h2 className="login-welcome">Welcome to ZerroBuild</h2>
          <p className="login-lead">Sign in to your account</p>
          <form onSubmit={submit}>
            <label className="login-field">
              <span>Email address</span>
              <div className="login-input">
                <Mail size={18} />
                <input
                  type="email"
                  required
                  autoComplete="username"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </label>
            <label className="login-field">
              <span>Password</span>
              <div className="login-input">
                <Lock size={18} />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="login-eye"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>
            <div className="login-row login-row-v10">
              <span />
              <button type="button" className="login-link" onClick={() => setNotice("Ask your administrator to reset the password. Email reset is not open.")}>
                Forgot password?
              </button>
            </div>
            <Err text={error} />
            {notice ? <p className="login-notice">{notice}</p> : null}
            <button className="login-submit" disabled={busy}>
              {busy ? "Signing in…" : "Sign In"} <ArrowRight size={18} />
            </button>
          </form>
          <div className="login-or"><span>or</span></div>
          <button type="button" className="login-sso" onClick={() => setNotice("SSO is not open. Sign in with your work email.")}>
            <Building2 size={16} /> Sign in with SSO
          </button>
          <p className="login-access">New to ZerroBuild? <button type="button" className="login-access-link" onClick={() => setNotice("Request access through your organization administrator.")}>Request Access <ArrowRight size={14} /></button></p>
        </div>
      </section>
    </div>
  );
}
export default function App() {
  const [session, setSession] = useState<Session | null>(null),
    [loading, setLoading] = useState(true),
    [nav, setNav] = useState("home"),
    [workspace, setWorkspace] = useState<"choose" | "internal" | "partner" | "command">("choose"),
    [selected, setSelected] = useState<number | null>(null),
    [editingProject, setEditingProject] = useState(false),
    [homeProject, setHomeProject] = useState<number | null>(null),
    [unread, setUnread] = useState(0),
    [placeholderName, setPlaceholderName] = useState(""),
    [approvalTarget, setApprovalTarget] = useState<ApprovalTarget | null>(null),
    [navOpen, setNavOpen] = useState(false);
  const [catalog, setCatalog] = useState<Catalog>({
    roles: [],
    disciplines: [],
  });
  async function refresh() {
    try {
      const s = await api<Session>("/auth/me");
      setCsrf(s.csrf_token);
      setSession(s);
      setCatalog(await api<Catalog>("/catalog"));
    } catch {
      setSession(null);
      setWorkspace("choose");
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (!session) return;
    void api<{ unread: number }>("/notifications/unread-count")
      .then((row) => setUnread(row.unread))
      .catch(() => setUnread(0));
  }, [session, nav]);
  useEffect(() => {
    void refresh();
    const reset = () => {
      setSession(null);
      setWorkspace("choose");
      setSelected(null);
      setNav("home");
    };
    const openApprovalLevels = (event: Event) => {
      setApprovalTarget((event as CustomEvent<ApprovalTarget>).detail);
      setSelected(null);
      setNav("approval-levels");
    };
    window.addEventListener("session-expired", reset);
    window.addEventListener(OPEN_APPROVAL_LEVELS, openApprovalLevels);
    return () => {
      window.removeEventListener("session-expired", reset);
      window.removeEventListener(OPEN_APPROVAL_LEVELS, openApprovalLevels);
    };
  }, []);
  if (loading) return <div className="loading">Loading workspace…</div>;
  if (!session) return <Login done={() => { setWorkspace("choose"); setNav("home"); void refresh(); }} />;
  if (workspace === "choose") return <div className="zb-workspace-page">
    <div className="zb-workspace-panel">
      <div className="zb-workspace-panel-brand"><BrandMark /> <strong>ZerroBuild</strong></div>
      <h1>Select Your Access</h1>
      <p>Choose how you want to use ZerroBuild</p>
      <div className="zb-workspace-choices">
        <button type="button" onClick={() => { setWorkspace("internal"); setNav("home"); }}>
          <span className="zb-choice-icon"><Building2 size={35} /></span><strong>Internal Workspace</strong>
          <small>For project teams and internal departments</small>
          <ul><li>Project Management</li><li>Engineering & Drawings</li><li>Procurement</li><li>Construction</li><li>Quality & Safety</li><li>Planning, Progress & Financials</li></ul>
          <em>Continue as Internal User</em>
        </button>
        <button type="button" onClick={() => { setWorkspace("partner"); setNav("partner"); }}>
          <span className="zb-choice-icon"><Handshake size={35} /></span><strong>Partner Portal</strong>
          <small>For vendors, suppliers, contractors & subcontractors</small>
          <ul><li>View RFQs & Submit Quotes *</li><li>Manage Purchase Orders *</li><li>Track Deliveries *</li><li>Access Authorized Documents</li><li>View Work Progress</li><li>Invoices & Payments *</li></ul>
          <em>Continue as Partner</em>
        </button>
        <button type="button" className="zb-command-choice" onClick={async () => {
          try {
            const { ticket } = await api<{ ticket: string }>("/integrations/command-center/ticket", "POST");
            const exchange = await fetch("/command-api/auth/sso", {
              method: "POST", credentials: "include",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: new URLSearchParams({ ticket }),
            });
            if (!exchange.ok) throw new Error("Command Center access denied");
            setWorkspace("command");
          } catch (error) { alert((error as Error).message); }
        }}>
          <span className="zb-choice-icon"><ChartNoAxesCombined size={35} /></span><strong>Command Center</strong>
          <small>Management monitoring for projects, work progress, milestones, contractors and budgets.</small>
          <ul><li>Project Portfolio Overview</li><li>Planned vs Actual Progress</li><li>Discipline & Contractor Monitoring</li><li>Milestones & Work Packages</li><li>Cost and Budget Insights</li><li>Issues & Management Actions</li></ul>
          <em>Open Command Center <ArrowRight size={15} /></em>
        </button>
        <button type="button" className="zb-qa-choice" onClick={() => { window.location.assign("https://zerroqa.flagestrator.com"); }}>
          <span className="zb-choice-icon"><ClipboardCheck size={35} /></span><strong>Zerro-R</strong>
          <small>One platform for inspections, quality assurance and compliance across every engineering discipline.</small>
          <ul><li>Civil & Structural Inspections</li><li>Mechanical & Piping Quality</li><li>Electrical & Instrumentation</li><li>Welding, NDT & Testing</li><li>Inspection Reports & Approvals</li><li>Commissioning & Quality Records</li></ul>
          <em>Open Zerro-R Inspections <ArrowRight size={15} /></em>
        </button>
      </div>
      <p className="zb-workspace-disclaimer">Your access and menu options depend on your role and company permissions. Some external partner workflows are not yet connected. Command Center access requires configured secure login.</p>
      <button type="button" className="zb-workspace-logout" onClick={async () => { try { await api("/auth/logout", "POST"); setCsrf(""); setSession(null); } catch (e) { alert((e as Error).message); } }}>Sign out</button>
    </div>
  </div>;
  if (workspace === "command") return <CommandCenterWorkspace onExit={async () => {
    try { await fetch("/command-api/auth/logout", { method: "POST", credentials: "include" }); }
    finally { setWorkspace("choose"); }
  }} />;
  const admin = session.user.organization_admin;
  async function logout() {
    try {
      await api("/auth/logout", "POST");
      setCsrf("");
      setSession(null);
      setWorkspace("choose");
      setSelected(null);
      setNav("home");
    } catch (e) {
      alert((e as Error).message);
    }
  }
  const canContracts = admin || session.memberships.some(x => x.scope === "ALL" && (x.permissions?.includes("contracts.view_summary") || x.permissions?.includes("contracts.manage_draft") || x.permissions?.includes("financials.view")));
  const canFinancials = admin || session.memberships.some(x => x.scope === "ALL" && (x.permissions?.includes("financials.view") || x.permissions?.includes("financials.manage")));
  const canPlanning = admin || session.memberships.some((item) => item.permissions?.includes("planning.view") || item.permissions?.includes("planning.manage"));
  const canProcurement =
    admin || session.memberships.some((item) => item.permissions?.includes("procurement.view"));
  const canEquipment = canPlanning;
  const canStores = admin || session.memberships.some(item => item.permissions?.includes("procurement.master.edit") || item.permissions?.includes("procurement.stock.edit"));
  const canConstruction =
    admin || session.memberships.some((item) => item.permissions?.includes("construction.view"));
  const canQuality =
    admin || session.memberships.some((item) => item.permissions?.includes("quality.view"));
  const canHse =
    admin || session.memberships.some((item) => item.permissions?.includes("hse.view"));
  const canHr =
    admin || session.memberships.some((item) => item.permissions?.includes("hr.view"));
  const canManpower =
    admin || session.memberships.some((item) => item.permissions?.includes("manpower.view"));
  const canDrawings =
    admin ||
    session.memberships.some(
      (item) =>
        item.permissions?.includes("drawings.view") ||
        item.permissions?.includes("transmittals.issue"),
    );
  function openModule(destination: string, projectId: number | null) {
    if (projectId) setHomeProject(projectId);
    setNavOpen(false);
    if (!destination) return;
    if (destination.startsWith("soon:")) {
      setPlaceholderName(destination.slice(5));
      setNav("placeholder");
      setSelected(null);
      return;
    }
    if (destination === "projects") {
      setNav("projects");
      setSelected(projectId);
      return;
    }
    setNav(destination);
    setSelected(null);
  }
  function go(key: string) {
    if (key === "switch-workspace") { setWorkspace("choose"); return; }
    if (key.startsWith("soon:")) { setPlaceholderName(key.slice(5)); setNav("placeholder"); } else setNav(key === "manpower" && !canManpower && canHr ? "hr" : key);
    setSelected(null);
    setNavOpen(false);
  }
  const entries: [string, string, LucideIcon][] = workspace === "partner" ? [
    ["partner", "Home", Home], ["soon:My Profile", "My Profile", Users], ["procurement", "RFQs & Tenders", ShoppingCart], ["soon:Quotations", "Quotations", FileText], ["partner-pos", "Purchase Orders", ShoppingCart], ["partner-planning", "Planning", CalendarDays], ["partner-contracts", "My Contracts", ScrollText], ["partner-deliveries", "Deliveries", Truck], ["partner-material-requests", "Material Requests", ListChecks], ["partner-material-handovers", "Material Receipts", Truck], ["partner-material-returns", "Material Returns", Truck], ["drawings", "Documents", FileText], ["soon:Invoices & Payments", "Invoices & Payments", Wallet], ["quality", "Quality & Inspections", ShieldCheck], ["construction", "Work Progress", HardHat], ["notifications", "Messages", Bell], ["help", "Support", HelpCircle], ["switch-workspace", "Switch workspace", Users],
  ] : [
    ["home", "Home", Home], ["projects", "Project Details", Building2], ["drawings", "Engineering", FileText], ["procurement", "Procurement", ShoppingCart], ["construction", "Construction", HardHat], ["quality", "Quality", ShieldCheck], ["safety", "Safety", AlertTriangle], ["planning", "Planning", CalendarDays], ["progress", "Progress", ChartNoAxesCombined], ["financials", "Financials", Wallet], ["contracts", "Contracts", ScrollText], ["manpower", "HR & Manpower", Users], ["stores", "Store & Inventory", Warehouse], ["equipment", "Equipment & Tools", Wrench], ["soon:Commissioning & Handover", "Commissioning & Handover", ClipboardCheck], ["notifications", "Reports & Analytics", Bell], ["settings", "Administration", Settings], ["switch-workspace", "Switch workspace", Building2],
  ];
  return (
    <div className={`shell${nav === "home" || nav === "favorites" || nav === "partner" ? " shell-home" : ""}${navOpen ? " nav-open" : ""}`}>
      <button className="nav-toggle" type="button" aria-label="Open menu" onClick={() => setNavOpen((open) => !open)}>
        Menu
      </button>
      <Sidebar entries={entries} nav={nav === "hr" ? "manpower" : nav} unread={unread} onNavigate={go} />

      <main>
        {nav === "partner" ? (
          <PartnerHome session={session} onOpen={openModule} onNotifications={() => setNav("notifications")} />
        ) : nav === "home" || nav === "favorites" ? (
          <ReferenceHome session={session} onOpen={openModule} onNotifications={() => setNav("notifications")} />
        ) : (
          <>
            <header>
              <div>
                <span className="eyebrow">ZERROBUILD</span>
                <h1>
                  {selected && nav === "projects"
                    ? "Project workspace"
                    : nav === "projects"
                      ? "Your projects"
                      : nav === "drawings"
                        ? "Drawings"
                        : nav === "procurement"
                          ? "Procurement"
                          : nav === "requests"
                            ? "Requirements & Requests"
                            : nav === "construction"
                              ? "Construction"
                              : nav === "quality"
                                ? "Quality"
                                : nav === "safety"
                                  ? "Safety / HSE"
                                  : nav === "hr"
                                    ? "HR & Workforce"
                                    : nav === "manpower"
                                      ? "Manpower"
                                      : nav === "equipment"
                                        ? "Equipment & Tools"
                                        : nav === "stores"
                                        ? "Store & Inventory"
                                        : nav === "planning" || nav === "partner-planning"
                                          ? "Planning"
                                          : nav === "progress"
                                            ? "Progress"
                                            : nav === "contracts" || nav === "partner-contracts"
                                              ? "Contracts"
                                              : nav === "financials"
                                                ? "Financials"
                                                : nav === "users"
                                                  ? "People & access"
                                                  : nav === "companies"
                                                    ? "Participating companies"
                                                    : nav === "inbox"
                                                      ? "My approvals"
                                                      : nav === "tasks"
                                                        ? "My tasks"
                                                        : nav === "notifications"
                                                          ? "Notifications"
                                                          : nav === "help"
                                                            ? "Help"
                                                            : nav === "settings"
                                                              ? "Settings"
                                                              : nav === "approval-levels"
                                                                ? "Approval levels"
                                                                : nav === "partner-pos"
                                                                  ? "Purchase orders"
                                                                  : nav === "placeholder"
                                                                    ? placeholderName
                                                                    : "Audit history"}
                </h1>
              </div>
              <div className="identity">
                <div className="avatar">{session.user.name.slice(0, 1)}</div>
                <div>
                  {session.user.name}
                  <small>{admin ? "Organization Admin" : "Project member"}</small>
                </div>
                <button className="logout" onClick={() => void logout()}>
                  <LogOut size={17} />
                  Sign out
                </button>
              </div>
            </header>
            <div className="content">
              {nav === "projects" ? (
                selected ? (
                  <ProjectDetails
                    id={selected}
                    session={session}
                    catalog={catalog}
                    startInEdit={editingProject}
                    back={() => {
                      setSelected(null);
                      setEditingProject(false);
                    }}
                    refreshSession={refresh}
                  />
                ) : (
                  <Projects
                    session={session}
                    catalog={catalog}
                    select={(id, edit) => {
                      setEditingProject(!!edit);
                      setSelected(id);
                    }}
                    refreshSession={refresh}
                  />
                )
              ) : nav === "users" && admin ? (
                <UsersPage catalog={catalog} />
              ) : nav === "companies" && admin ? (
                <CompaniesPage />
              ) : nav === "audit" && admin ? (
                <AuditPage />
              ) : nav === "drawings" && canDrawings ? (
                <DrawingsHome session={session} catalog={catalog} initialProjectId={homeProject} />
              ) : nav === "partner-contracts" && workspace === "partner" ? (
                <PartnerContracts />
              ) : nav === "partner-pos" && workspace === "partner" ? (
                <PartnerPurchaseOrders initialProjectId={homeProject} />
              ) : nav === "partner-material-requests" && workspace === "partner" ? (
                <PartnerMaterialRequests initialProjectId={homeProject} />
              ) : nav === "partner-material-handovers" && workspace === "partner" ? (
                <PartnerMaterialHandovers initialProjectId={homeProject} />
              ) : nav === "partner-material-returns" && workspace === "partner" ? (
                <PartnerMaterialReturns initialProjectId={homeProject} />
              ) : nav === "partner-deliveries" && workspace === "partner" ? (
                <PartnerDeliveries initialProjectId={homeProject} />
              ) : nav === "partner-planning" && workspace === "partner" ? (
                <PartnerPlanning initialProjectId={homeProject} />
              ) : nav === "procurement" && canProcurement ? (
                <ProcurementHome session={session} catalog={catalog} initialProjectId={homeProject} />
              ) : nav === "stores" && workspace === "internal" && canStores ? (
                <StoresHome session={session} initialProjectId={homeProject} />
              ) : nav === "requests" && canProcurement ? (
                <RequirementsHome session={session} initialProjectId={homeProject} />
              ) : nav === "equipment" && workspace === "internal" && canEquipment ? (
                <EquipmentHome session={session} initialProjectId={homeProject} />
              ) : nav === "planning" && workspace === "internal" && canPlanning ? (
                <PlanningHome session={session} initialProjectId={homeProject} />
              ) : nav === "progress" && workspace === "internal" && canPlanning ? (
                <ProgressMonitoringHome session={session} initialProjectId={homeProject} />
              ) : nav === "contracts" && workspace === "internal" && canContracts ? (
                <ContractsHome session={session} initialProjectId={homeProject} />
              ) : nav === "financials" && workspace === "internal" && canFinancials ? (
                <FinancialsHome session={session} initialProjectId={homeProject} />
              ) : nav === "construction" && canConstruction ? (
                <ConstructionHome session={session} initialProjectId={homeProject} />
              ) : nav === "quality" && canQuality ? (
                <QualityHome session={session} initialProjectId={homeProject} />
              ) : nav === "safety" && canHse ? (
                <HseHome session={session} initialProjectId={homeProject} />
              ) : (nav === "hr" && canHr) || (nav === "manpower" && canManpower) ? (
                <>
                  {canHr && canManpower ? (
                    <div className="proc-nav">
                      <button type="button" className={`proc-tab tone-wlist${nav === "hr" ? " is-on" : ""}`} aria-pressed={nav === "hr"} onClick={() => setNav("hr")}>
                        <IdCard size={14} strokeWidth={2.4} />
                        <span>HR</span>
                      </button>
                      <button type="button" className={`proc-tab tone-wcrew${nav === "manpower" ? " is-on" : ""}`} aria-pressed={nav === "manpower"} onClick={() => setNav("manpower")}>
                        <UsersRound size={14} strokeWidth={2.4} />
                        <span>Manpower</span>
                      </button>
                    </div>
                  ) : null}
                  {nav === "hr" ? (
                    <HrHome key="hr" session={session} initialProjectId={homeProject} />
                  ) : (
                    <ManpowerHome key="manpower" session={session} initialProjectId={homeProject} />
                  )}
                </>
              ) : nav === "inbox" ? (
                <InboxPage
                  openProject={(id) => {
                    setNav("projects");
                    setSelected(id);
                  }}
                />
              ) : nav === "tasks" ? (
                <MyTasksPage />
              ) : nav === "notifications" ? (
                <NotificationsPage
                  openProject={(id) => {
                    setNav("projects");
                    setSelected(id);
                  }}
                  onChange={() =>
                    void api<{ unread: number }>("/notifications/unread-count")
                      .then((row) => setUnread(row.unread))
                      .catch(() => setUnread(0))
                  }
                />
              ) : nav === "help" ? (
                <HelpPage />
              ) : nav === "placeholder" ? (
                <ModulePlaceholder name={placeholderName} onHome={() => go("home")} />
              ) : nav === "settings" ? (
                <SettingsPage
                  session={session}
                  onSignOut={() => void logout()}
                  onOpen={(destination) => {
                    setApprovalTarget(null);
                    setNav(destination);
                  }}
                />
              ) : nav === "approval-levels" && admin ? (
                <ApprovalLevelsPage
                  key={approvalTarget ? `${approvalTarget.projectId}:${approvalTarget.recordType}:${approvalTarget.disciplineId}` : "settings"}
                  disciplines={catalog.disciplines}
                  initial={approvalTarget}
                />
              ) : (
                <div>Access denied</div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
function Projects({
  session,
  catalog,
  select,
  refreshSession,
}: {
  session: Session;
  catalog: Catalog;
  select: (id: number, edit?: boolean) => void;
  refreshSession: () => Promise<void>;
}) {
  const [items, setItems] = useState<Project[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(0),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [clientId, setClientId] = useState(""),
    [disciplineId, setDisciplineId] = useState(""),
    [clients, setClients] = useState<{ id: number; name: string }[]>([]),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(true),
    [creating, setCreating] = useState(false);
  async function load() {
    setBusy(true);
    try {
      const r = await api<Page<Project>>(
        `/projects?offset=${page * 12}&limit=12&search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}&client_id=${clientId || 0}&discipline_id=${disciplineId || 0}`,
      );
      setItems(r.items);
      setTotal(r.total);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void load();
  }, [page, search, status, clientId, disciplineId]);
  useEffect(() => {
    void api<{ clients: { id: number; name: string }[] }>("/projects/filters")
      .then((row) => setClients(row.clients))
      .catch(() => setClients([]));
  }, []);
  if (creating)
    return (
      <ProjectForm
        initial={{ ...blank }}
        catalog={catalog}
        admin={session.user.organization_admin}
        commercial={session.user.organization_admin}
        cancel={() => setCreating(false)}
        saved={async () => {
          setCreating(false);
          setNotice("Project saved.");
          await refreshSession();
          await load();
        }}
      />
    );
  return (
    <>
      <div className="intro">
        <div>
          <h2>Build a clear project foundation</h2>
          <p>
            Set up your site, assign disciplines and connect the right teams.
          </p>
        </div>
        {session.user.organization_admin && (
          <button className="primary" onClick={() => setCreating(true)}>
            <Plus size={17} />
            New project
          </button>
        )}
      </div>
      <div className="toolbar">
        <input
          aria-label="Search projects"
          placeholder="Search project code or name…"
          value={search}
          onChange={(e) => {
            setPage(0);
            setSearch(e.target.value);
          }}
        />
        <select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => {
            setPage(0);
            setStatus(e.target.value);
          }}
        >
          <option value="">All statuses</option>
          {[
            "Draft",
            "Planned",
            "Active",
            "On Hold",
            "Completed",
            "Cancelled",
          ].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <select
          aria-label="Filter by client"
          value={clientId}
          onChange={(e) => {
            setPage(0);
            setClientId(e.target.value);
          }}
        >
          <option value="">All clients</option>
          {clients.map((client) => (
            <option key={client.id} value={client.id}>
              {client.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by discipline"
          value={disciplineId}
          onChange={(e) => {
            setPage(0);
            setDisciplineId(e.target.value);
          }}
        >
          <option value="">All disciplines</option>
          {catalog.disciplines.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <span>{total} accessible projects</span>
      </div>
      <Err text={error} />
      {notice ? <div className="success">{notice}</div> : null}
      {busy ? (
        <p>Loading projects…</p>
      ) : items.length ? (
        <table className="register">
          <thead>
            <tr>
              <th>Project code</th>
              <th>Project name</th>
              <th>Client</th>
              <th>Site location</th>
              <th>Project manager</th>
              <th>Planned start</th>
              <th>Planned completion</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((p) => {
              const editable =
                session.user.organization_admin ||
                session.memberships.some(
                  (item) =>
                    item.project_id === p.id &&
                    item.permissions?.includes("projects.edit"),
                );
              return (
                <tr key={p.id}>
                  <td>{p.code}</td>
                  <td>{p.name}</td>
                  <td>{p.client_name || "—"}</td>
                  <td>
                    {[p.site_name, p.city, p.state].filter(Boolean).join(", ") ||
                      "—"}
                  </td>
                  <td>{p.lead_pm_name || "—"}</td>
                  <td>{p.planned_start || "—"}</td>
                  <td>{p.planned_finish || "—"}</td>
                  <td>
                    <Badge text={p.status} />
                  </td>
                  <td className="actions">
                    <button onClick={() => select(p.id!)}>View</button>
                    {editable ? (
                      <button onClick={() => select(p.id!, true)}>Edit</button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <div className="empty">
          <FolderKanban size={40} />
          <h3>
            {session.user.organization_admin
              ? "Create your first project"
              : "No projects assigned"}
          </h3>
          <p>
            {session.user.organization_admin
              ? "Start with a draft and complete the details as your team is assigned."
              : "Ask your administrator to assign a project and role."}
          </p>
        </div>
      )}
      <Pager page={page} total={total} size={12} setPage={setPage} />
    </>
  );
}
function Pager({
  page,
  total,
  size,
  setPage,
}: {
  page: number;
  total: number;
  size: number;
  setPage: (p: number) => void;
}) {
  return (
    <div className="pager">
      <button disabled={page === 0} onClick={() => setPage(page - 1)}>
        Previous
      </button>
      <span>Page {page + 1}</span>
      <button
        disabled={(page + 1) * size >= total}
        onClick={() => setPage(page + 1)}
      >
        Next
      </button>
    </div>
  );
}
function ProjectForm({
  initial,
  catalog,
  admin,
  commercial,
  cancel,
  saved,
}: {
  initial: Project;
  catalog: Catalog;
  admin: boolean;
  commercial: boolean;
  cancel: () => void;
  saved: () => Promise<void>;
}) {
  const [p, setP] = useState<Project>(initial),
    [companies, setCompanies] = useState<Company[]>([]),
    [users, setUsers] = useState<User[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [tab, setTab] = useState("Overview"),
    [dirty, setDirty] = useState(false);
  useEffect(() => {
    if (admin)
      void (async () => {
        try {
          setCompanies(await allPages<Company>("/companies"));
          setUsers(await allPages<User>("/users"));
        } catch (e) {
          setError((e as Error).message);
        }
      })();
  }, [admin]);
  useEffect(() => {
    function warn(e: BeforeUnloadEvent) {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function set<K extends keyof Project>(k: K, v: Project[K]) {
    setDirty(true);
    setP({ ...p, [k]: v });
  }
  function leave() {
    if (!dirty || confirm("Discard unsaved changes?")) cancel();
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body: Record<string, unknown> = {
        code: p.code.trim(),
        name: p.name,
        description: p.description,
        project_type: p.project_type,
        status: p.status,
        site_name: p.site_name,
        address: p.address,
        country: p.country,
        state: p.state,
        city: p.city,
        postal_code: p.postal_code,
        timezone: p.timezone,
        latitude: p.latitude,
        longitude: p.longitude,
        planned_start: p.planned_start,
        planned_finish: p.planned_finish,
        actual_start: p.actual_start,
        actual_finish: p.actual_finish,
        hold_reason: p.hold_reason,
        cancellation_reason: p.cancellation_reason,
        client_company_id: p.client_company_id,
        main_contractor_company_id: p.main_contractor_company_id ?? null,
        pmc_company_id: p.pmc_company_id ?? null,
        subcontractor_ids: p.subcontractor_ids ?? [],
        lead_pm_id: p.lead_pm_id,
        discipline_ids: p.discipline_ids,
        disciplines: p.discipline_ids.map((id) => ({
          discipline_id: id,
          scope_description:
            p.disciplines?.find((row) => row.discipline_id === id)?.scope_description ||
            "",
          active: true,
        })),
      };
      if (commercial) {
        body.contract_number = p.contract_number || "";
        body.contract_date = p.contract_date || null;
        body.contract_value = p.contract_value || null;
        body.currency = p.contract_value ? p.currency || "INR" : p.currency || "";
      }
      if (p.id) body.version = p.version;
      await api(p.id ? `/projects/${p.id}` : "/projects", p.id ? "PUT" : "POST", body);
      setDirty(false);
      await saved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const text = (
    key: keyof Project,
    label: string,
    required = false,
    disabled = false,
  ) => (
    <Field label={label}>
      <input
        required={required}
        disabled={disabled}
        value={String(p[key] ?? "")}
        onChange={(e) => set(key, e.target.value as never)}
      />
    </Field>
  );
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{p.id ? "Edit project" : "Create project"}</h2>
          <p className="muted">
            Drafts can be saved before all setup fields are complete.
          </p>
        </div>
        <button type="button" onClick={leave}>
          Cancel
        </button>
      </div>
      <div className="tabs">
        {[
          "Overview",
          "Companies & Team",
          "Schedule",
          "Areas & Disciplines",
          "Documents",
        ].map((t) => (
          <button
            type="button"
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <form onSubmit={submit}>
        <div hidden={tab !== "Overview"}>
          <div className="form-grid">
            {text("code", "Project code *", true, !admin)}
            {text("name", "Project name *", true)}
            <Field label="Project type *">
              <select
                value={p.project_type}
                onChange={(e) => set("project_type", e.target.value)}
              >
                {[
                  "Industrial Plant",
                  "Refinery",
                  "Power Plant",
                  "Infrastructure",
                  "Other",
                ].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </Field>
            <Field label="Status">
              <select disabled value={p.status}>
                {[
                  "Draft",
                  "Planned",
                  "Active",
                  "On Hold",
                  "Completed",
                  "Cancelled",
                ].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </Field>
            <Field label="Description">
              <textarea
                value={p.description}
                onChange={(e) => set("description", e.target.value)}
              />
            </Field>
            {text("site_name", "Site name")}
            {text("country", "Country")}
            {text("state", "State / region")}
            {text("city", "District / city")}
            {text("postal_code", "Postal code")}
            {text("timezone", "Project timezone")}
            <Field label="Address">
              <textarea
                value={p.address}
                onChange={(e) => set("address", e.target.value)}
              />
            </Field>
            {(["latitude", "longitude"] as const).map((k) => (
              <Field key={k} label={k === "latitude" ? "Latitude" : "Longitude"}>
                <input
                  type="number"
                  step="any"
                  min={k === "latitude" ? -90 : -180}
                  max={k === "latitude" ? 90 : 180}
                  value={p[k] ?? ""}
                  onChange={(e) =>
                    set(k, e.target.value ? Number(e.target.value) : null)
                  }
                />
              </Field>
            ))}
          </div>
          {commercial ? (
            <div className="form-grid">
              <h3>Commercial</h3>
              {text("contract_number", "Contract / PO number")}
              <Field label="Contract date">
                <input
                  type="date"
                  value={p.contract_date ?? ""}
                  onChange={(e) => set("contract_date", e.target.value || null)}
                />
              </Field>
              <Field label="Contract value">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={p.contract_value ?? ""}
                  onChange={(e) => set("contract_value", e.target.value || null)}
                />
              </Field>
              <Field label="Currency">
                <select
                  value={p.currency || "INR"}
                  onChange={(e) => set("currency", e.target.value)}
                >
                  {["INR", "USD", "EUR", "GBP", "AED", "SAR"].map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </Field>
            </div>
          ) : (
            <p className="note">Commercial information is hidden for this role.</p>
          )}
        </div>
        <div hidden={tab !== "Companies & Team"}>
          {admin ? (
            <>
              <div className="form-grid">
                <Field label="Owner / client">
                  <select
                    value={p.client_company_id ?? ""}
                    onChange={(e) =>
                      set("client_company_id", Number(e.target.value) || null)
                    }
                  >
                    <option value="">Select client</option>
                    {companies
                      .filter((c) => c.active)
                      .map((c) => (
                        <option value={c.id} key={c.id}>
                          {c.name}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label="Main contractor">
                  <select
                    value={p.main_contractor_company_id ?? ""}
                    onChange={(e) =>
                      set(
                        "main_contractor_company_id",
                        Number(e.target.value) || null,
                      )
                    }
                  >
                    <option value="">None</option>
                    {companies
                      .filter((c) => c.active)
                      .map((c) => (
                        <option value={c.id} key={c.id}>
                          {c.name}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label="PMC / consultant">
                  <select
                    value={p.pmc_company_id ?? ""}
                    onChange={(e) =>
                      set("pmc_company_id", Number(e.target.value) || null)
                    }
                  >
                    <option value="">None</option>
                    {companies
                      .filter((c) => c.active)
                      .map((c) => (
                        <option value={c.id} key={c.id}>
                          {c.name}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label="Lead project manager">
                  <select
                    value={p.lead_pm_id ?? ""}
                    onChange={(e) =>
                      set("lead_pm_id", Number(e.target.value) || null)
                    }
                  >
                    <option value="">Select project manager</option>
                    {users
                      .filter((u) => u.active && u.company_id)
                      .map((u) => (
                        <option value={u.id} key={u.id}>
                          {u.name}
                        </option>
                      ))}
                  </select>
                </Field>
              </div>
              <h3>Subcontractors</h3>
              <div className="checks">
                {companies
                  .filter((c) => c.active)
                  .map((c) => (
                    <label key={c.id}>
                      <input
                        type="checkbox"
                        checked={(p.subcontractor_ids || []).includes(c.id)}
                        onChange={(e) =>
                          set(
                            "subcontractor_ids",
                            e.target.checked
                              ? [...(p.subcontractor_ids || []), c.id]
                              : (p.subcontractor_ids || []).filter((id) => id !== c.id),
                          )
                        }
                      />
                      {c.name}
                    </label>
                  ))}
              </div>
            </>
          ) : (
            <p className="note">
              Company participation and role assignments are controlled by your
              organization administrator.
            </p>
          )}
          <p className="note">
            Saving a lead project manager creates that Project Manager membership.
            Replacing the lead does not remove the previous manager. A Planned or
            Active project needs one designated lead.
          </p>
          {p.id && admin ? (
            <MembershipsPage
              pid={p.id}
              catalog={catalog}
              enabled={p.discipline_ids}
              refreshed={async () => undefined}
            />
          ) : null}
        </div>
        <div className="form-grid" hidden={tab !== "Schedule"}>
          {(
            [
              ["planned_start", "Planned start date"],
              ["planned_finish", "Planned completion date"],
              ["actual_start", "Actual start date"],
              ["actual_finish", "Actual completion date"],
            ] as const
          ).map(([key, label]) => (
            <Field key={key} label={label}>
              <input
                type="date"
                value={p[key] ?? ""}
                onChange={(e) => set(key, e.target.value || null)}
              />
            </Field>
          ))}
          {p.status === "On Hold" ? text("hold_reason", "Hold reason *", true) : null}
          {p.status === "Cancelled"
            ? text("cancellation_reason", "Cancellation reason *", true)
            : null}
        </div>
        <div hidden={tab !== "Areas & Disciplines"}>
          <h3>Disciplines</h3>
          {catalog.disciplines.map((d) => (
            <div key={d.id}>
              <label>
                <input
                  type="checkbox"
                  disabled={!admin}
                  checked={p.discipline_ids.includes(d.id)}
                  onChange={(e) =>
                    set(
                      "discipline_ids",
                      e.target.checked
                        ? [...p.discipline_ids, d.id]
                        : p.discipline_ids.filter((x) => x !== d.id),
                    )
                  }
                />
                {d.name}
              </label>
              {p.discipline_ids.includes(d.id) ? (
                <Field label={`${d.name} scope`}>
                  <textarea
                    disabled={!admin}
                    value={
                      p.disciplines?.find((row) => row.discipline_id === d.id)
                        ?.scope_description || ""
                    }
                    onChange={(e) => {
                      const rows = p.disciplines || [];
                      const next = rows.some((row) => row.discipline_id === d.id)
                        ? rows.map((row) =>
                          row.discipline_id === d.id
                            ? { ...row, scope_description: e.target.value, active: true }
                            : row,
                        )
                        : [
                          ...rows,
                          {
                            discipline_id: d.id,
                            scope_description: e.target.value,
                            active: true,
                          },
                        ];
                      set("disciplines", next);
                    }}
                  />
                </Field>
              ) : null}
            </div>
          ))}
          <p className="note">
            Planned and Active projects need at least one enabled discipline.
            Progress is calculated from execution modules later and is not edited here.
          </p>
          {p.id ? (
            <AreasPage pid={p.id} canEdit={admin || true} />
          ) : (
            <p className="note">Save the draft before adding units, areas, and blocks.</p>
          )}
        </div>
        <div hidden={tab !== "Documents"}>
          {p.id ? (
            <AttachmentsPanel
              pid={p.id}
              canUpload
              canDelete={admin}
              canCommercial={commercial}
            />
          ) : (
            <p className="note">
              Save the project first. Documents are uploaded after the record exists.
            </p>
          )}
        </div>
        <Err text={error} />
        <div className="form-actions">
          <button type="button" onClick={leave}>
            Cancel
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Saving…" : "Save project"}
          </button>
        </div>
      </form>
    </section>
  );
}
async function allPages<T>(path: string): Promise<T[]> {
  let result: T[] = [];
  let offset = 0;
  while (true) {
    const p = await api<Page<T>>(`${path}?offset=${offset}&limit=100`);
    result = result.concat(p.items);
    offset += p.items.length;
    if (offset >= p.total || !p.items.length) return result;
  }
}
function ProjectDetails({
  id,
  session,
  catalog,
  startInEdit,
  back,
  refreshSession,
}: {
  id: number;
  session: Session;
  catalog: Catalog;
  startInEdit?: boolean;
  back: () => void;
  refreshSession: () => Promise<void>;
}) {
  const [p, setP] = useState<Project | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [tab, setTab] = useState("Overview"),
    [edit, setEdit] = useState(!!startInEdit);
  const isAdmin = session.user.organization_admin,
    canEdit =
      isAdmin ||
      session.memberships.some(
        (m) => m.project_id === id && m.permissions?.includes("projects.edit"),
      );
  async function load() {
    try {
      setP(await api<Project>(`/projects/${id}`));
      setError("");
    } catch (e) {
      setP(null);
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [id]);
  if (error)
    return (
      <>
        <button onClick={back}>Back to projects</button>
        <Err text={error} />
      </>
    );
  if (!p) return <p>Loading project…</p>;
  if (edit)
    return (
      <ProjectForm
        initial={p}
        catalog={catalog}
        admin={isAdmin}
        commercial={
          isAdmin ||
          session.memberships.some(
            (item) =>
              item.project_id === id &&
              item.permissions?.includes("projects.commercial.edit"),
          )
        }
        cancel={() => setEdit(false)}
        saved={async () => {
          setEdit(false);
          setNotice("Project saved.");
          await refreshSession();
          await load();
        }}
      />
    );
  return (
    <>
      <button className="back" onClick={back}>
        ← All projects
      </button>
      <div className="intro">
        <div>
          <span className="code">{p.code}</span>
          <h2>{p.name}</h2>
          <p>{p.description || "Scope description pending"}</p>
        </div>
        <div className="inline">
          <Badge text={p.status} />
          {canEdit && (
            <button className="primary" onClick={() => setEdit(true)}>
              Edit details
            </button>
          )}
        </div>
      </div>
      {notice ? <div className="success">{notice}</div> : null}
      <div className="tabs">
        {[
          "Overview",
          "Companies & Team",
          "Contacts",
          "Schedule",
          "Areas & Disciplines",
          "Documents",
          "History",
          ...(isAdmin ||
            session.memberships.some(
              (item) => item.project_id === id && item.permissions?.includes("drawings.view"),
            )
            ? ["Drawings"]
            : []),
          "Reviews",
          "Tasks",
        ].map((t) => (
          <button
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "Overview" ? (
        <>
          <div className="overview-grid">
            <section className="panel">
              <MapPin />
              <h3>Site & location</h3>
              <p>{p.site_name || "Not entered"}</p>
              <p>
                {[p.address, p.city, p.state, p.country]
                  .filter(Boolean)
                  .join(", ")}
              </p>
              <small>{p.timezone}</small>
            </section>
            <section className="panel">
              <FolderKanban />
              <h3>Schedule</h3>
              <dl>
                <dt>Planned start</dt>
                <dd>{p.planned_start || "Pending"}</dd>
                <dt>Planned completion</dt>
                <dd>{p.planned_finish || "Pending"}</dd>
                <dt>Actual start</dt>
                <dd>{p.actual_start || "Not started"}</dd>
                <dt>Actual completion</dt>
                <dd>{p.actual_finish || "Pending"}</dd>
              </dl>
              {p.status === "On Hold" ? <p>Hold reason: {p.hold_reason}</p> : null}
              {p.status === "Cancelled" ? (
                <p>Cancellation reason: {p.cancellation_reason}</p>
              ) : null}
            </section>
            <section className="panel">
              <CheckCircle2 />
              <h3>Enabled disciplines</h3>
              <div className="disciplines">
                {p.discipline_ids.map((d) => (
                  <span key={d}>
                    {catalog.disciplines.find((x) => x.id === d)?.name}
                    {p.disciplines?.find((row) => row.discipline_id === d)?.scope_description
                      ? ` — ${p.disciplines?.find((row) => row.discipline_id === d)?.scope_description}`
                      : ""}
                  </span>
                ))}
              </div>
              <p className="muted">
                Record version {p.version}. Project manager: {p.lead_pm_name || "Not assigned"}
              </p>
            </section>
          </div>
          {p.contract_number !== undefined ? (
            <section className="panel">
              <h3>Commercial</h3>
              <p>Contract / PO: {p.contract_number || "Not entered"}</p>
              <p>Contract date: {p.contract_date || "Not entered"}</p>
              <p>
                Value: {p.contract_value ? `${p.currency || "INR"} ${p.contract_value}` : "Not entered"}
              </p>
            </section>
          ) : null}
          <div className="note">
            Overall progress is not edited here. It will be calculated from execution modules.
          </div>
          {isAdmin && <StatusPanel project={p} reload={load} />}
        </>
      ) : tab === "Companies & Team" ? (
        <>
          <section className="panel">
            <h3>Assigned companies</h3>
            <p>Client: {p.client_name || "Not set"}</p>
            <p className="muted">
              People on this tab have project access. A contact is stored separately and cannot approve.
            </p>
          </section>
          {isAdmin ? <ParticipantsPage pid={id} /> : null}
          <MembershipsPage
            pid={id}
            catalog={catalog}
            enabled={p.discipline_ids}
            refreshed={refreshSession}
            manage={isAdmin}
          />
        </>
      ) : tab === "Contacts" ? (
        <ContactsPanel
          pid={id}
          canEdit={
            isAdmin ||
            session.memberships.some(
              (item) =>
                item.project_id === id &&
                item.permissions?.includes("projects.contact.edit"),
            )
          }
        />
      ) : tab === "Schedule" ? (
        <section className="panel">
          <h3>Schedule</h3>
          <p>Planned start: {p.planned_start || "Pending"}</p>
          <p>Planned completion: {p.planned_finish || "Pending"}</p>
          <p>Actual start: {p.actual_start || "Not started"}</p>
          <p>Actual completion: {p.actual_finish || "Pending"}</p>
        </section>
      ) : tab === "Areas & Disciplines" ? (
        <>
          <section className="panel">
            <h3>Disciplines</h3>
            {p.discipline_ids.length ? (
              p.discipline_ids.map((d) => (
                <p key={d}>
                  {catalog.disciplines.find((x) => x.id === d)?.name}
                  {p.disciplines?.find((row) => row.discipline_id === d)?.scope_description
                    ? ` — ${p.disciplines.find((row) => row.discipline_id === d)?.scope_description}`
                    : ""}
                </p>
              ))
            ) : (
              <p className="muted">No disciplines enabled yet.</p>
            )}
          </section>
          <AreasPage pid={id} canEdit={canEdit} />
        </>
      ) : tab === "Documents" ? (
        <AttachmentsPanel
          pid={id}
          canUpload={canEdit}
          canDelete={canEdit}
          canCommercial={
            isAdmin ||
            session.memberships.some(
              (item) =>
                item.project_id === id &&
                item.permissions?.includes("projects.commercial.view"),
            )
          }
        />
      ) : tab === "Drawings" ? (
        <EngineeringBoard pid={id} session={session} catalog={catalog} />
      ) : tab === "Reviews" ? (
        <ReviewsPanel
          pid={id}
          session={session}
          reloadProject={load}
          canSubmit={canEdit}
        />
      ) : tab === "Tasks" ? (
        <TasksPanel pid={id} admin={isAdmin} />
      ) : tab === "History" ? (
        <HistoryPanel pid={id} />
      ) : null}
    </>
  );
}

const CONTACT_FUNCTIONS = [
  "Client",
  "PMC",
  "Project manager",
  "Discipline",
  "Procurement",
  "Stores",
  "Site",
  "Safety",
  "Other",
];

type ProjectContact = {
  id: number;
  name: string;
  function: string;
  company_id: number | null;
  company_name: string;
  user_id: number | null;
  user_name: string;
  phone: string | null;
  email: string | null;
  details_visible: boolean;
  note: string;
  active: boolean;
  version: number;
  approver: boolean;
};

function ContactsPanel({ pid, canEdit }: { pid: number; canEdit: boolean }) {
  const blank = {
    id: 0,
    name: "",
    function: "Client",
    company_id: 0,
    user_id: 0,
    phone: "",
    email: "",
    note: "",
    active: true,
    version: 1,
  };
  const [rows, setRows] = useState<ProjectContact[]>([]),
    [companies, setCompanies] = useState<Participant[]>([]),
    [members, setMembers] = useState<Membership[]>([]),
    [form, setForm] = useState(blank),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function load() {
    try {
      setRows(await api<ProjectContact[]>(`/projects/${pid}/contacts`));
      setCompanies(await api<Participant[]>(`/projects/${pid}/companies`));
      setMembers(await api<Membership[]>(`/projects/${pid}/memberships`));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [pid]);
  const people = [
    ...new Map(
      members
        .filter((row) => row.active !== false && row.user_id)
        .map((row) => [row.user_id, row.name || "Member"]),
    ),
  ];
  async function save(e: FormEvent) {
    e.preventDefault();
    const body = {
      name: form.name,
      function: form.function,
      company_id: form.company_id || null,
      user_id: form.user_id || null,
      phone: form.phone,
      email: form.email,
      note: form.note,
      active: form.active,
      version: form.version,
    };
    try {
      if (form.id) {
        await api(`/projects/${pid}/contacts/${form.id}`, "PUT", body);
        setNotice("Contact updated. This does not change who can approve.");
      } else {
        await api(`/projects/${pid}/contacts`, "POST", {
          name: body.name,
          function: body.function,
          company_id: body.company_id,
          user_id: body.user_id,
          phone: body.phone,
          email: body.email,
          note: body.note,
        });
        setNotice("Contact saved. This person cannot approve from this entry.");
      }
      setForm(blank);
      setError("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  function edit(row: ProjectContact) {
    setForm({
      id: row.id,
      name: row.name,
      function: row.function,
      company_id: row.company_id || 0,
      user_id: row.user_id || 0,
      phone: row.phone || "",
      email: row.email || "",
      note: row.note,
      active: row.active,
      version: row.version,
    });
    setNotice("");
  }
  return (
    <section className="panel">
      <div className="contact-head">
        <span className="contact-mark">
          <Contact />
        </span>
        <div>
          <h3>Contacts</h3>
          <p className="muted">
            A contact is a directory entry by function. It does not grant login, membership, or approval.
          </p>
        </div>
      </div>
      {notice ? <div className="success">{notice}</div> : null}
      <Err text={error} />
      {canEdit ? (
        <form className="contact-form" onSubmit={(e) => void save(e)}>
          <label>
            Name
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </label>
          <label>
            Function
            <select
              value={form.function}
              onChange={(e) => setForm({ ...form, function: e.target.value })}
            >
              {CONTACT_FUNCTIONS.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Company
            <select
              value={form.company_id}
              onChange={(e) => setForm({ ...form, company_id: Number(e.target.value) })}
            >
              <option value={0}>No company</option>
              {companies
                .filter((row) => row.active !== false)
                .map((row) => (
                  <option key={row.company_id} value={row.company_id}>
                    {row.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Project member
            <select
              value={form.user_id}
              onChange={(e) => setForm({ ...form, user_id: Number(e.target.value) })}
            >
              <option value={0}>No login link</option>
              {people.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Phone
            <input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </label>
          <label>
            Email
            <input
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </label>
          <label className="wide">
            Note
            <input
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
            />
          </label>
          <div className="inline">
            <button className="primary" type="submit">
              {form.id ? "Save contact" : "Add contact"}
            </button>
            {form.id ? (
              <button type="button" onClick={() => setForm(blank)}>
                Cancel edit
              </button>
            ) : null}
          </div>
          <p className="muted wide">
            Linking a project member only shows their name here. It does not add them to an approval route.
          </p>
        </form>
      ) : null}
      <div className="contact-grid">
        {rows.map((row) => (
          <article key={row.id} className={`contact-card ${functionClass(row.function)}`}>
            <header>
              <span className={`fn-chip ${functionClass(row.function)}`}>{row.function}</span>
              <span className={row.active ? "state-active" : "state-inactive"}>
                {row.active ? "Active" : "Inactive"}
              </span>
            </header>
            <h4>{row.name}</h4>
            <p>{row.company_name || "No company"}</p>
            {row.user_name ? <p>Linked login: {row.user_name}</p> : <p>No login link</p>}
            {row.details_visible ? (
              <p className="contact-lines">
                <Phone /> {row.phone || "No phone"}
                <Mail /> {row.email || "No email"}
              </p>
            ) : (
              <p className="muted">Phone and email stay hidden on this login.</p>
            )}
            {row.note ? <p>{row.note}</p> : null}
            <p className={row.approver ? "state-also" : "state-clear"}>
              {row.approver
                ? "Also named on a saved approval route. This contact does not grant that."
                : "Not an approver"}
            </p>
            {canEdit ? (
              <div className="inline">
                <button type="button" onClick={() => edit(row)}>
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() =>
                    void api(`/projects/${pid}/contacts/${row.id}`, "PUT", {
                      name: row.name,
                      function: row.function,
                      company_id: row.company_id,
                      user_id: row.user_id,
                      phone: row.phone || "",
                      email: row.email || "",
                      note: row.note,
                      active: !row.active,
                      version: row.version,
                    })
                      .then(() => {
                        setNotice(
                          row.active
                            ? "Contact deactivated. The entry stays in the directory."
                            : "Contact reactivated. Approval routes are unchanged.",
                        );
                        return load();
                      })
                      .catch((err) => setError((err as Error).message))
                  }
                >
                  {row.active ? "Deactivate" : "Reactivate"}
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </div>
      {rows.length === 0 ? <p className="muted">No contacts saved for this project.</p> : null}
    </section>
  );
}

function functionClass(name: string) {
  return "fn-" + name.toLowerCase().replace(/[^a-z]+/g, "-");
}

function CompaniesPage() {
  const [items, setItems] = useState<Company[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(0),
    [name, setName] = useState(""),
    [drafts, setDrafts] = useState<Record<number, string>>({}),
    [kind, setKind] = useState("Contractor"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function load() {
    try {
      const r = await api<Page<Company>>(
        `/companies?offset=${page * 20}&limit=20`,
      );
      setItems(r.items);
      setTotal(r.total);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [page]);
  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/companies", "POST", { name, company_type: kind });
      setName("");
      setError("");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>Company register</h2>
      <p className="muted">
        Create companies before adding their users and project participation.
      </p>
      <form className="toolbar" onSubmit={add}>
        <input
          required
          placeholder="Company name"
          aria-label="Company name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <select
          aria-label="Company type"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          {[
            "Owner",
            "Main Contractor",
            "Subcontractor",
            "PMC",
            "Contractor",
            "Vendor",
            "Supplier",
          ].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <button className="primary" disabled={busy}>
          Add company
        </button>
      </form>
      <Err text={error} />
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.id}>
              <td>
                <input
                  aria-label={`Company ${c.name}`}
                  value={drafts[c.id] ?? c.name}
                  onChange={(e) =>
                    setDrafts({ ...drafts, [c.id]: e.target.value })
                  }
                />
              </td>
              <td>{c.company_type}</td>
              <td>{c.active ? "Active" : "Inactive"}</td>
              <td>
                <button
                  onClick={() =>
                    void api(`/companies/${c.id}`, "PUT", {
                      name: drafts[c.id] ?? c.name,
                      company_type: c.company_type,
                      active: c.active,
                      version: c.version,
                    })
                      .then(load)
                      .catch((err) => setError((err as Error).message))
                  }
                >
                  Save
                </button>
                <button
                  onClick={() =>
                    void api(`/companies/${c.id}`, "PUT", {
                      name: c.name,
                      company_type: c.company_type,
                      active: !c.active,
                      version: c.version,
                    })
                      .then(load)
                      .catch((err) => setError((err as Error).message))
                  }
                >
                  {c.active ? "Deactivate" : "Activate"}
                </button>
                <button
                  onClick={() => {
                    if (!window.confirm(`Delete company "${c.name}"? This cannot be undone.`)) return;
                    void api(`/companies/${c.id}`, "DELETE")
                      .then(() => {
                        setError("");
                        return load();
                      })
                      .catch((err) => setError((err as Error).message));
                  }}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager page={page} total={total} size={20} setPage={setPage} />
    </section>
  );
}
const participationTypes = [
  "Owner",
  "Main Contractor",
  "Subcontractor",
  "PMC",
  "Contractor",
];
function participationFor(company?: Company) {
  return company && participationTypes.includes(company.company_type)
    ? company.company_type
    : "Contractor";
}
function UsersPage({ catalog }: { catalog: Catalog }) {
  const [items, setItems] = useState<User[]>([]),
    [companies, setCompanies] = useState<Company[]>([]),
    [projects, setProjects] = useState<Project[]>([]),
    [assignments, setAssignments] = useState<
      Record<number, { label: string; role: string; active: boolean }[]>
    >({}),
    [participants, setParticipants] = useState<Participant[]>([]),
    [assignFor, setAssignFor] = useState<number | null>(null),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [show, setShow] = useState(false),
    [names, setNames] = useState<Record<number, string>>({});
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    company_id: null as number | null,
    organization_admin: false,
  });
  const [roleForm, setRoleForm] = useState({
    project_id: 0,
    role_id: 0,
    scope: "ALL",
    discipline_ids: [] as number[],
    participation_type: "Contractor",
  });
  async function load() {
    try {
      const r = await api<Page<User>>(`/users?offset=${page * 20}&limit=20`);
      setItems(r.items);
      setTotal(r.total);
      setCompanies(await allPages<Company>("/companies"));
      const projectList = await allPages<Project>("/projects");
      setProjects(projectList);
      const grouped: Record<
        number,
        { label: string; role: string; active: boolean }[]
      > = {};
      for (const project of projectList) {
        if (!project.id) continue;
        const members = await api<Membership[]>(
          `/projects/${project.id}/memberships`,
        );
        for (const member of members) {
          if (!member.user_id) continue;
          const row = {
            label: `${project.code} · ${project.name}`,
            role: member.role,
            active: member.active !== false,
          };
          grouped[member.user_id] = [...(grouped[member.user_id] ?? []), row];
        }
      }
      setAssignments(grouped);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [page]);
  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/users", "POST", form);
      setForm({
        name: "",
        email: "",
        password: "",
        company_id: null,
        organization_admin: false,
      });
      setShow(false);
      setError("");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function toggle(u: User, key: "active" | "organization_admin") {
    if (!confirm(`Change ${key.replace("_", " ")} for ${u.name}?`)) return;
    try {
      await api(`/users/${u.id}`, "PUT", {
        name: u.name,
        active: key === "active" ? !u.active : u.active,
        organization_admin:
          key === "organization_admin"
            ? !u.organization_admin
            : u.organization_admin,
      });
      await load();
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function chooseProject(projectId: number, user: User) {
    const company = companies.find((c) => c.id === user.company_id);
    setRoleForm((current) => ({
      ...current,
      project_id: projectId,
      discipline_ids: [],
      participation_type: participationFor(company),
    }));
    if (!projectId) {
      setParticipants([]);
      return;
    }
    try {
      setParticipants(
        await api<Participant[]>(`/projects/${projectId}/companies`),
      );
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function assign(user: User, e: FormEvent) {
    e.preventDefault();
    if (!user.company_id) {
      setError("This account has no employing company, so a role cannot be assigned.");
      return;
    }
    if (!roleForm.project_id || !roleForm.role_id) {
      setError("Choose a project and a role.");
      return;
    }
    if (roleForm.scope === "SELECTED" && roleForm.discipline_ids.length === 0) {
      setError("Select at least one enabled discipline, or choose all enabled disciplines.");
      return;
    }
    setBusy(true);
    try {
      const current = await api<Participant[]>(
        `/projects/${roleForm.project_id}/companies`,
      );
      if (!current.some((p) => p.company_id === user.company_id)) {
        await api(`/projects/${roleForm.project_id}/companies`, "POST", {
          company_id: user.company_id,
          participation_type: roleForm.participation_type,
        });
      }
      await api(`/projects/${roleForm.project_id}/memberships`, "POST", {
        user_id: user.id,
        role_id: roleForm.role_id,
        company_id: user.company_id,
        scope: roleForm.scope,
        discipline_ids:
          roleForm.scope === "ALL" ? [] : roleForm.discipline_ids,
        active: true,
      });
      setAssignFor(null);
      setError("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>People & access</h2>
          <p className="muted">
            Create the account, then assign a project role. Organization Admin
            only manages setup; it is not a project role.
          </p>
        </div>
        <button className="primary" onClick={() => setShow(!show)}>
          <Plus size={16} />
          Create user
        </button>
      </div>
      <Err text={error} />
      {show && (
        <form onSubmit={add}>
          <div className="form-grid">
            <Field label="Full name">
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </Field>
            <Field label="Email">
              <input
                required
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </Field>
            <Field label="Initial password (12+ characters)">
              <input
                required
                minLength={12}
                maxLength={128}
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </Field>
            <Field label="Employing company">
              <select
                required
                value={form.company_id ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    company_id: Number(e.target.value) || null,
                  })
                }
              >
                <option value="">Select company</option>
                {companies
                  .filter((c) => c.active)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
              </select>
            </Field>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={form.organization_admin}
              onChange={(e) =>
                setForm({ ...form, organization_admin: e.target.checked })
              }
            />
            Organization Admin
          </label>
          <button disabled={busy} className="primary">
            Create account
          </button>
        </form>
      )}
      <table>
        <thead>
          <tr>
            <th>Person</th>
            <th>Company</th>
            <th>Account</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((u) => (
            <tr key={u.id}>
              <td>
                <input
                  aria-label={`Name for ${u.email}`}
                  value={names[u.id] ?? u.name}
                  onChange={(e) => setNames({ ...names, [u.id]: e.target.value })}
                />
                <small>{u.email}</small>
              </td>
              <td>
                {companies.find((c) => c.id === u.company_id)?.name ||
                  "Unassigned"}
              </td>
              <td>
                {u.organization_admin ? "Organization Admin" : "User"}
                <small>{u.active ? "Active" : "Inactive"}</small>
              </td>
              <td>
                <div className="inline">
                  <button
                    onClick={() =>
                      void api(`/users/${u.id}`, "PUT", {
                        name: names[u.id] ?? u.name,
                        active: u.active,
                        organization_admin: u.organization_admin,
                        ...(u.company_id ? { company_id: u.company_id } : {}),
                      })
                        .then(load)
                        .catch((err) => setError((err as Error).message))
                    }
                  >
                    Save profile
                  </button>
                  <button onClick={() => void toggle(u, "active")}>
                    {u.active ? "Deactivate" : "Activate"}
                  </button>
                  <button onClick={() => void toggle(u, "organization_admin")}>
                    {u.organization_admin ? "Remove admin" : "Make admin"}
                  </button>
                  <button
                    type="button"
                    className="primary"
                    onClick={() => {
                      const opening = assignFor !== u.id;
                      setAssignFor(opening ? u.id : null);
                      setParticipants([]);
                      setRoleForm({
                        project_id: 0,
                        role_id: 0,
                        scope: "ALL",
                        discipline_ids: [],
                        participation_type: participationFor(
                          companies.find((c) => c.id === u.company_id),
                        ),
                      });
                    }}
                  >
                    Assign role
                  </button>
                </div>
                <small>
                  {(assignments[u.id] ?? [])
                    .filter((a) => a.active)
                    .map((a) => `${a.role} on ${a.label}`)
                    .join("; ") || "No project role"}
                </small>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {items
        .filter((u) => u.id === assignFor)
        .map((user) => {
          const project = projects.find((p) => p.id === roleForm.project_id);
          const onProject = participants.some(
            (p) => p.company_id === user.company_id,
          );
          return (
            <form key={user.id} onSubmit={(e) => void assign(user, e)}>
              <h3>Assign a project role to {user.name}</h3>
              {projects.length === 0 ? (
                <div className="note">
                  Create a project first. A role is assigned on a project, not
                  on the account by itself.
                </div>
              ) : !user.company_id ? (
                <div className="note">
                  This account has no employing company. Create the user again
                  with a company before assigning a role.
                </div>
              ) : (
                <>
                  <div className="form-grid">
                    <Field label="Project">
                      <select
                        required
                        value={roleForm.project_id || ""}
                        onChange={(e) =>
                          void chooseProject(Number(e.target.value), user)
                        }
                      >
                        <option value="">Choose project</option>
                        {projects.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.code} · {p.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Role">
                      <select
                        required
                        value={roleForm.role_id || ""}
                        onChange={(e) =>
                          setRoleForm({
                            ...roleForm,
                            role_id: Number(e.target.value),
                          })
                        }
                      >
                        <option value="">Choose role</option>
                        {catalog.roles.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Discipline scope">
                      <select
                        value={roleForm.scope}
                        onChange={(e) =>
                          setRoleForm({
                            ...roleForm,
                            scope: e.target.value,
                            discipline_ids: [],
                          })
                        }
                      >
                        <option value="ALL">All enabled disciplines</option>
                        <option value="SELECTED">Selected disciplines</option>
                      </select>
                    </Field>
                    {roleForm.project_id > 0 && !onProject && (
                      <Field label="Add company to this project as">
                        <select
                          value={roleForm.participation_type}
                          onChange={(e) =>
                            setRoleForm({
                              ...roleForm,
                              participation_type: e.target.value,
                            })
                          }
                        >
                          {participationTypes.map((kind) => (
                            <option key={kind}>{kind}</option>
                          ))}
                        </select>
                      </Field>
                    )}
                  </div>
                  {roleForm.scope === "SELECTED" && (
                    <div className="checks">
                      {(project?.discipline_ids.length ?? 0) === 0 && (
                        <p className="muted">
                          This project has no enabled disciplines. Choose all
                          enabled disciplines, or enable them on the project
                          first.
                        </p>
                      )}
                      {catalog.disciplines
                        .filter((d) => project?.discipline_ids.includes(d.id))
                        .map((d) => (
                          <label key={d.id}>
                            <input
                              type="checkbox"
                              checked={roleForm.discipline_ids.includes(d.id)}
                              onChange={(e) =>
                                setRoleForm({
                                  ...roleForm,
                                  discipline_ids: e.target.checked
                                    ? [...roleForm.discipline_ids, d.id]
                                    : roleForm.discipline_ids.filter(
                                      (id) => id !== d.id,
                                    ),
                                })
                              }
                            />
                            {d.name}
                          </label>
                        ))}
                    </div>
                  )}
                  <button className="primary" disabled={busy}>
                    Save role
                  </button>
                </>
              )}
            </form>
          );
        })}
      <Pager page={page} total={total} size={20} setPage={setPage} />
    </section>
  );
}
function ParticipantsPage({ pid }: { pid: number }) {
  const [items, setItems] = useState<Participant[]>([]),
    [companies, setCompanies] = useState<Company[]>([]),
    [cid, setCid] = useState(""),
    [kind, setKind] = useState("Subcontractor"),
    [error, setError] = useState("");
  async function load() {
    try {
      setItems(await api<Participant[]>(`/projects/${pid}/companies`));
      setCompanies(await allPages<Company>("/companies"));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [pid]);
  async function add(e: FormEvent) {
    e.preventDefault();
    try {
      await api(`/projects/${pid}/companies`, "POST", {
        company_id: Number(cid),
        participation_type: kind,
      });
      await load();
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <section className="panel">
      <h2>Project companies</h2>
      <form className="toolbar" onSubmit={add}>
        <select
          required
          aria-label="Company"
          value={cid}
          onChange={(e) => setCid(e.target.value)}
        >
          <option value="">Choose company</option>
          {companies
            .filter(
              (c) => c.active && !items.some((p) => p.company_id === c.id),
            )
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
        </select>
        <select
          aria-label="Participation type"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          {[
            "Owner",
            "Main Contractor",
            "Subcontractor",
            "PMC",
            "Contractor",
          ].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <button className="primary">Add participant</button>
      </form>
      <Err text={error} />
      <table>
        <thead>
          <tr>
            <th>Company</th>
            <th>Participation</th>
          </tr>
        </thead>
        <tbody>
          {items.map((x) => (
            <tr key={x.id}>
              <td>{x.name}</td>
              <td>
                {x.participation_type}
                <small>{x.active === false ? "Inactive" : "Active"}</small>
              </td>
              <td>
                <button
                  onClick={() =>
                    void api(`/projects/${pid}/companies/${x.id}`, "PUT", {
                      participation_type: x.participation_type,
                      active: x.active === false,
                      version: x.version,
                    })
                      .then(load)
                      .catch((err) => setError((err as Error).message))
                  }
                >
                  {x.active === false ? "Reactivate" : "Deactivate"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
function MembershipsPage({
  pid,
  catalog,
  enabled,
  refreshed,
  manage = true,
}: {
  pid: number;
  catalog: Catalog;
  enabled: number[];
  refreshed: () => Promise<void>;
  manage?: boolean;
}) {
  const [items, setItems] = useState<Membership[]>([]),
    [users, setUsers] = useState<User[]>([]),
    [companies, setCompanies] = useState<Participant[]>([]),
    [error, setError] = useState("");
  const [form, setForm] = useState({
    user_id: 0,
    role_id: 0,
    company_id: 0,
    scope: "ALL",
    discipline_ids: [] as number[],
    active: true,
  });
  async function load() {
    try {
      setItems(await api<Membership[]>(`/projects/${pid}/memberships`));
      setCompanies(await api<Participant[]>(`/projects/${pid}/companies`));
      if (manage) setUsers(await allPages<User>("/users"));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [pid]);
  async function add(e: FormEvent) {
    e.preventDefault();
    try {
      await api(`/projects/${pid}/memberships`, "POST", form);
      await load();
      await refreshed();
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function revoke(mid: number) {
    if (!confirm("Deactivate this assignment?")) return;
    try {
      await api(`/projects/${pid}/memberships/${mid}`, "DELETE");
      await load();
      await refreshed();
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <section className="panel">
      <h2>Project access assignments</h2>
      <p className="muted">
        Assignments use the project role system. Each row records the user, role,
        participating company, discipline scope, and active status.
      </p>
      {manage && companies.length === 0 && (
        <div className="note">
          Add at least one company on the Companies tab before assigning a
          role.
        </div>
      )}
      {manage ? (
        <form onSubmit={add}>
          <div className="form-grid">
            <Field label="User">
              <select
                required
                value={form.user_id || ""}
                onChange={(e) =>
                  setForm({ ...form, user_id: Number(e.target.value) })
                }
              >
                <option value="">Choose active user</option>
                {users
                  .filter((u) => u.active)
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Role">
              <select
                required
                value={form.role_id || ""}
                onChange={(e) =>
                  setForm({ ...form, role_id: Number(e.target.value) })
                }
              >
                <option value="">Choose role</option>
                {catalog.roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Participating company">
              <select
                required
                value={form.company_id || ""}
                onChange={(e) =>
                  setForm({ ...form, company_id: Number(e.target.value) })
                }
              >
                <option value="">Choose participant</option>
                {companies
                  .filter((c) => c.active !== false)
                  .map((c) => (
                    <option key={c.id} value={c.company_id}>
                      {c.name}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Discipline scope">
              <select
                value={form.scope}
                onChange={(e) =>
                  setForm({ ...form, scope: e.target.value, discipline_ids: [] })
                }
              >
                <option value="SELECTED">Selected disciplines</option>
                <option value="ALL">All enabled disciplines</option>
              </select>
            </Field>
          </div>
          {form.scope === "SELECTED" && (
            <div className="checks">
              {catalog.disciplines
                .filter((d) => enabled.includes(d.id))
                .map((d) => (
                  <label key={d.id}>
                    <input
                      type="checkbox"
                      checked={form.discipline_ids.includes(d.id)}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          discipline_ids: e.target.checked
                            ? [...form.discipline_ids, d.id]
                            : form.discipline_ids.filter((x) => x !== d.id),
                        })
                      }
                    />
                    {d.name}
                  </label>
                ))}
            </div>
          )}
          <button className="primary">Create assignment</button>
        </form>
      ) : null}
      <Err text={error} />
      <table>
        <thead>
          <tr>
            <th>User</th>
            <th>Role</th>
            <th>Company</th>
            <th>Scope</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((m) => (
            <tr key={m.id}>
              <td>{m.name}</td>
              <td>{m.role}</td>
              <td>
                {companies.find((c) => c.company_id === m.company_id)?.name}
              </td>
              <td>
                {m.scope === "ALL"
                  ? "All enabled"
                  : m.discipline_ids
                    .map(
                      (d) =>
                        catalog.disciplines.find((x) => x.id === d)?.name,
                    )
                    .join(", ")}
              </td>
              <td>{m.active ? "Active" : "Inactive"}</td>
              <td>
                {manage && m.active && (
                  <button onClick={() => void revoke(m.id)}>Deactivate</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
function AreasPage({ pid, canEdit }: { pid: number; canEdit: boolean }) {
  const [items, setItems] = useState<Area[]>([]),
    [names, setNames] = useState<Record<number, string>>({}),
    [error, setError] = useState(""),
    [form, setForm] = useState({
      code: "",
      name: "",
      area_type: "Unit",
      parent_id: null as number | null,
      description: "",
    });
  async function load() {
    try {
      setItems(await api<Area[]>(`/projects/${pid}/areas`));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [pid]);
  async function add(e: FormEvent) {
    e.preventDefault();
    try {
      await api(`/projects/${pid}/areas`, "POST", form);
      setForm({ ...form, code: "", name: "" });
      setError("");
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <section className="panel">
      <h2>Unit → Area → Block</h2>
      {canEdit && (
        <form className="toolbar" onSubmit={add}>
          <input
            required
            aria-label="Area code"
            placeholder="Code"
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value })}
          />
          <input
            required
            aria-label="Area name"
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <select
            aria-label="Area type"
            value={form.area_type}
            onChange={(e) =>
              setForm({ ...form, area_type: e.target.value, parent_id: null })
            }
          >
            {["Unit", "Area", "Block"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          {form.area_type !== "Unit" && (
            <select
              required
              aria-label="Parent location"
              value={form.parent_id ?? ""}
              onChange={(e) =>
                setForm({ ...form, parent_id: Number(e.target.value) || null })
              }
            >
              <option value="">Choose parent</option>
              {items
                .filter(
                  (a) =>
                    a.active !== false &&
                    a.area_type ===
                    (form.area_type === "Area" ? "Unit" : "Area"),
                )
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} · {a.name}
                  </option>
                ))}
            </select>
          )}
          <button className="primary">Add location</button>
        </form>
      )}
      <Err text={error} />
      <table>
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Type</th>
            <th>Parent</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.id}>
              <td>{a.code}</td>
              <td>
                <input
                  aria-label={`Location ${a.code}`}
                  value={names[a.id] ?? a.name}
                  onChange={(e) => setNames({ ...names, [a.id]: e.target.value })}
                />
              </td>
              <td>{a.area_type}</td>
              <td>{items.find((p) => p.id === a.parent_id)?.name || "—"}</td>
              <td>{a.active === false ? "Inactive" : "Active"}</td>
              {canEdit && (
                <td>
                  <button
                    onClick={() => {
                      void api(`/projects/${pid}/areas/${a.id}`, "PUT", {
                        code: a.code,
                        name: names[a.id] ?? a.name,
                        description: a.description,
                        active: a.active !== false,
                        version: a.version,
                      })
                        .then(load)
                        .catch((err) => setError((err as Error).message));
                    }}
                  >
                    Rename
                  </button>
                  <button
                    onClick={() =>
                      void api(`/projects/${pid}/areas/${a.id}`, "PUT", {
                        code: a.code,
                        name: a.name,
                        description: a.description,
                        active: a.active === false,
                        version: a.version,
                      })
                        .then(load)
                        .catch((err) => setError((err as Error).message))
                    }
                  >
                    {a.active === false ? "Reactivate" : "Deactivate"}
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {!items.length && (
        <p className="muted">No project locations have been added.</p>
      )}
    </section>
  );
}
function AuditPage() {
  const [items, setItems] = useState<AuditEvent[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(0),
    [error, setError] = useState("");
  useEffect(() => {
    void api<Page<AuditEvent>>(`/audit?offset=${page * 30}&limit=30`)
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e) => setError(e.message));
  }, [page]);
  return (
    <section className="panel">
      <h2>Organization audit trail</h2>
      <Err text={error} />
      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Actor ID</th>
            <th>Action</th>
            <th>Record</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {items.map((x) => (
            <tr key={x.id}>
              <td>{new Date(x.created_at).toLocaleString()}</td>
              <td>{x.actor_id}</td>
              <td>{x.action}</td>
              <td>
                {x.resource} #{x.resource_id}
              </td>
              <td>
                <details>
                  <summary>View</summary>
                  <pre>{JSON.stringify(x.details, null, 2)}</pre>
                </details>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager page={page} total={total} size={30} setPage={setPage} />
    </section>
  );
}
