import { useEffect, useMemo, useState } from "react";
import { Bell, Search, ClipboardCheck, FileText, Handshake, HardHat, Package, Receipt, ShieldCheck, ShoppingCart, Truck, Users } from "lucide-react";
import { api } from "../api";
import type { Page, Project, Session } from "../types";

type PartnerNotification = { id: number; title: string; body: string; project_id: number | null; read: boolean; created_at: string };
type PartnerRole = "vendor" | "supplier" | "contractor";
type Action = { name: string; details: string; permission: string; destination: string; icon: typeof FileText };
const ACTIONS: Record<PartnerRole, Action[]> = {
  vendor: [
    { name: "Procurement & RFQs", details: "Review RFQs, orders and quotations", permission: "procurement.view", destination: "procurement", icon: ShoppingCart },
    { name: "Engineering documents", details: "View authorized drawings and revisions", permission: "drawings.view", destination: "drawings", icon: FileText },
    { name: "Material requirements", details: "Review requirements and changes", permission: "procurement.view", destination: "requests", icon: Package },
    { name: "Quality records", details: "View quality workflows", permission: "quality.view", destination: "quality", icon: ShieldCheck },
  ],
  supplier: [
    { name: "Purchase orders", details: "Review authorized purchase orders", permission: "procurement.view", destination: "procurement", icon: ShoppingCart },
    { name: "Material requirements", details: "View material demand", permission: "procurement.view", destination: "requests", icon: Package },
    { name: "Engineering documents", details: "View drawing revisions", permission: "drawings.view", destination: "drawings", icon: FileText },
    { name: "Quality records", details: "View available inspection records", permission: "quality.view", destination: "quality", icon: ClipboardCheck },
  ],
  contractor: [
    { name: "Work packages & progress", details: "Manage assigned project work", permission: "construction.view", destination: "construction", icon: HardHat },
    { name: "Engineering drawings", details: "View drawings and revision records", permission: "drawings.view", destination: "drawings", icon: FileText },
    { name: "Quality & inspections", details: "Access inspection workflows", permission: "quality.view", destination: "quality", icon: ClipboardCheck },
    { name: "Manpower", details: "Access workforce planning", permission: "manpower.view", destination: "manpower", icon: Users },
    { name: "Safety", details: "View HSE information", permission: "hse.view", destination: "safety", icon: ShieldCheck },
  ],
};

export function PartnerHome({ session, onOpen, onNotifications }: { session: Session; onOpen: (destination: string, projectId: number | null) => void; onNotifications: () => void }) {
  const [role, setRole] = useState<PartnerRole>("vendor");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notifications, setNotifications] = useState<PartnerNotification[]>([]);
  const [unread, setUnread] = useState<number | null>(null);
  const [liveOverview, setLiveOverview] = useState<{purchase_orders: number; quotations: number; work_packages: number} | null>(null);
  const [liveRows, setLiveRows] = useState<{kind: string; items: Array<{id:number;reference:string;status?:string;name?:string}>} | null>(null);
  const [liveError, setLiveError] = useState("");
  useEffect(() => {
    setLiveOverview(null); setLiveRows(null); setLiveError("");
    if (!projectId) return;
    void Promise.all([
      api<{purchase_orders:number; quotations:number;work_packages:number}>(`/partner/projects/${projectId}/overview`),
      api<{kind:string;items:Array<{id:number;reference:string;status?:string;name?:string}>}>(`/partner/projects/${projectId}/transactions?kind=${role === "contractor" ? "work_packages" : "purchase_orders"}`)
    ]).then(([overview, rows]) => {setLiveOverview(overview);setLiveRows(rows);})
      .catch(() => setLiveError("Partner transaction data is unavailable or access is restricted."));
  }, [projectId, role]);
  useEffect(() => {
    void api<Page<Project>>("/projects?limit=100").then((data) => { setProjects(data.items); }).catch(() => setError("Unable to load projects."));
  }, []);
  useEffect(() => {
    void Promise.all([api<PartnerNotification[]>("/notifications"), api<{unread:number}>("/notifications/unread-count")])
      .then(([items,count]) => { setNotifications(items); setUnread(count.unread); })
      .catch(() => { /* An unavailable notification service must not block partner navigation. */ });
  }, []);
  const membership = useMemo(() => session.memberships.filter((m) => !projectId || m.project_id === projectId), [session.memberships, projectId]);
  const permissionSet = useMemo(() => new Set(membership.flatMap((m) => m.permissions ?? [])), [membership]);
  function permitted(permission: string) { return session.user.organization_admin || permissionSet.has(permission); }
  const options = ACTIONS[role];
  const accessible = options.filter((action) => permitted(action.permission));
  const roles: PartnerRole[] = ["vendor", "supplier", "contractor"];
  const open = (destination:string) => onOpen(destination,projectId);
  return <div className="ref-partner">
    <div className="ref-partner-top"><label>▦ <select value={projectId??""} onChange={e=>setProjectId(e.target.value?Number(e.target.value):null)}><option value="">All Projects</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label><div className="ref-partner-search"><Search size={15}/> Search contracts, POs, invoices, documents...</div><button className="ref-bell" type="button" onClick={onNotifications}><Bell size={20}/>{unread? <i>{unread}</i>:null}</button><div className="ref-partner-user"><b>{session.user.name?.slice(0,2).toUpperCase()}</b><span>{session.user.name}<small>{role[0].toUpperCase()+role.slice(1)}</small></span></div></div>
    <div className="ref-partner-main"><div className="ref-partner-left"><section className="ref-partner-hero"><h1>Welcome, {session.user.name}!</h1><p>Manage your contracts, documents, invoices and more —<br/> all in one place.</p></section><div className="ref-partner-role-row"><div className="ref-role-buttons">{roles.map(r=><button type="button" className={role===r?'active '+r:r} key={r} onClick={()=>setRole(r)}><Users size={15}/>{r[0].toUpperCase()+r.slice(1)}</button>)}</div></div>
    {error&&<p role="alert">{error}</p>}
    <div className="ref-partner-stats"><div><FileText/><small>{role==='contractor'?'Work Packages':'Active RFQs'}</small><strong>{liveOverview?(role==='contractor'?liveOverview.work_packages:liveOverview.quotations):'—'}</strong><em>Authorized records</em></div><div><ShoppingCart/><small>Purchase Orders</small><strong>{liveOverview?.purchase_orders??'—'}</strong><em>Project transactions</em></div><div><Truck/><small>Deliveries Pending</small><strong>—</strong><em>Integration pending</em></div><div><Receipt/><small>Outstanding Payments</small><strong>—</strong><em>Billing integration pending</em></div></div>
    <div className="ref-partner-data"><section><h2>Recent Activity <button type="button" onClick={onNotifications}>View All</button></h2>{notifications.slice(0,5).map(n=><div className="ref-partner-event" key={n.id}><FileText size={19}/><span><strong>{n.title}</strong><small>{n.body}</small></span><time>{new Date(n.created_at).toLocaleDateString()}</time></div>)}{!notifications.length&&<p className="ref-empty">No recent activity for this account.</p>}</section><section><h2>Upcoming Deadlines</h2>{liveRows?.items.slice(0,5).map(item=><div className="ref-partner-event" key={item.id}><ClipboardCheck size={19}/><span><strong>{item.reference}</strong><small>{item.status??item.name??'Open record'}</small></span></div>)}{!projectId&&<p className="ref-empty">Select a project to view authorized transactions.</p>}{liveError&&<p className="ref-empty">{liveError}</p>}{projectId&&!liveRows?.items.length&&!liveError&&<p className="ref-empty">No transaction deadlines available.</p>}</section></div>
    </div><aside className="ref-partner-actions"><h2>Quick Actions</h2>{[{label:'Upload Document',to:'drawings',icon:FileText},{label:'Submit Invoice',to:'soon:Partner Invoicing',icon:Receipt},{label:'View Purchase Orders',to:'partner-pos',icon:ShoppingCart},{label:'View Contracts',to:'soon:Contracts',icon:FileText},{label:'Track Deliveries',to:'partner-deliveries',icon:Truck},{label:'Acknowledge Materials',to:'partner-material-handovers',icon:Truck},{label:'Manage Profile',to:'soon:My Profile',icon:Users},{label:'Contact Support',to:'help',icon:ShieldCheck}].map(({label,to,icon:Icon})=><button type="button" key={label} onClick={()=>open(to)}><Icon size={18}/>{label}<b>›</b></button>)}<p className="ref-partner-help">Actions marked as future integrations open an availability notice; they do not submit live transactions.</p></aside></div>
    <div className="ref-partner-notice"><ShieldCheck size={17}/> Project records and navigation remain permission-checked by the server. Partner billing and delivery integrations are not yet complete.</div>
  </div>;
}
