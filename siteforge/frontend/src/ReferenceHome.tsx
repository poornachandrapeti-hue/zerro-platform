import { useEffect, useState } from 'react';
import { api } from './api';
import type { Page, Project, Session } from './types';
import { Building2, FileText, ShoppingCart, HardHat, ShieldCheck, AlertTriangle, CalendarDays, ChartNoAxesCombined, Wallet, ScrollText, Users, Warehouse, Wrench, Bell, ClipboardCheck, CheckCircle2, Activity, ArrowUpRight, Search } from 'lucide-react';

const FULL_SCOPE_DESTINATIONS = new Set(['financials','contracts']);
const modules = [
 ['Project Details','Projects, Locations','projects',Building2,'orange','projects.view'],
 ['Engineering','Drawings, Revisions','drawings',FileText,'blue','drawings.view'],
 ['Procurement','RFQs, POs, Deliveries','procurement',ShoppingCart,'red','procurement.view'],
 ['Construction','Work Packages','construction',HardHat,'green','construction.view'],
 ['Quality','Inspections, NCRs','quality',ShieldCheck,'blue','quality.view'],
 ['Safety','Observations, Incidents','safety',AlertTriangle,'orange','hse.view'],
 ['Planning','Schedules, Lookahead','planning',CalendarDays,'purple','planning.view|planning.manage'],
 ['Progress','Physical & Financial','progress',ChartNoAxesCombined,'teal','planning.view|planning.manage'],
 ['Financials','Invoices, Payments','financials',Wallet,'orange','financials.view|financials.manage'],
 ['Contracts','Agreements, Variations','contracts',ScrollText,'blue','contracts.view_summary|contracts.manage_draft|financials.view'],
 ['HR & Manpower','Resources, Attendance','manpower',Users,'blue','manpower.view'],
 ['Store & Inventory','Materials, Equipment','stores',Warehouse,'orange',''],
 ['Equipment & Tools','Assets, Maintenance','soon:Equipment & Tools',Wrench,'teal',''],
 ['Commissioning & Handover','Pre-commissioning, Handover','soon:Commissioning & Handover',ClipboardCheck,'green',''],
] as const;
export function ReferenceHome({session,onOpen,onNotifications}:{session:Session;onOpen:(key:string,pid:number|null)=>void;onNotifications:()=>void}) {
 const [projects,setProjects] = useState<Project[]>([]);
 const [pid,setPid] = useState<number|null>(null);
 const [events,setEvents] = useState<{id:number;title:string;body:string;created_at:string}[]>([]);
 const [unread,setUnread] = useState<number|null>(null);
 useEffect(()=>{void api<Page<Project>>('/projects?limit=100').then(r=>{setProjects(r.items);setPid(id=>id??r.items[0]?.id??null)}).catch(()=>{});void api<typeof events>('/notifications').then(setEvents).catch(()=>{});void api<{unread:number}>('/notifications/unread-count').then(r=>setUnread(r.unread)).catch(()=>{});},[]);
 const allowed=(perm:string,dest:string)=> !perm || session.user.organization_admin || session.memberships.some(m=>(!pid||m.project_id===pid)&&(!FULL_SCOPE_DESTINATIONS.has(dest)||m.scope==='ALL')&&perm.split('|').some(p=>m.permissions?.includes(p)));
 const project=projects.find(p=>p.id===pid);
 return <div className="ref-dashboard">
 <div className="ref-topbar"><strong className="ref-topbrand">◆ ZerroBuild</strong><select value={pid??''} onChange={e=>setPid(e.target.value?Number(e.target.value):null)}><option value="">Select project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><div className="ref-search"><Search size={15}/> Search anything (drawings, POs, inspections...)</div><button type="button" onClick={onNotifications} className="ref-bell"><Bell size={18}/>{unread? <i>{unread}</i>:null}</button><div className="ref-person"><b>{session.user.name?.slice(0,2).toUpperCase()}</b><span>{session.user.name}<small>Project Workspace</small></span></div></div>
 <div className="ref-content"><div className="ref-banner"><h1>Welcome, {session.user.name}!</h1><h3>{project?.name??'Your projects'}</h3><p>Monitor project execution, approvals, and performance across all disciplines.</p></div>
 <div className="ref-kpis"><div><Activity/><small>Overall Progress</small><strong>—</strong><em>Connect progress reporting</em></div><div><HardHat/><small>Active Work Packages</small><strong>—</strong><em>Project work register</em></div><div><ClipboardCheck/><small>Pending Approvals</small><strong>—</strong><em>Review your inbox</em></div><div><Wallet/><small>Outstanding Bills</small><strong>—</strong><em>Billing integration pending</em></div></div>
 <div className="ref-bottom"><section className="ref-panel"><h2>Project Modules</h2><div className="ref-module-grid">{modules.map(([name,desc,dest,Icon,tone,permission])=><button key={name} type="button" title={!allowed(permission,dest)?'You do not have permission':name} disabled={!allowed(permission,dest)} onClick={()=>onOpen(dest,pid)}><span className={'ref-module-icon '+tone}><Icon size={23}/></span><strong>{name}</strong><small>{desc}</small></button>)}</div></section><section className="ref-panel ref-activity"><h2>Recent Activity <button onClick={onNotifications}>View All</button></h2>{events.length?events.slice(0,6).map(event=><div className="ref-event" key={event.id}><span><FileText size={17}/></span><div><strong>{event.title}</strong><small>{event.body}</small></div><time>{new Date(event.created_at).toLocaleDateString()}</time></div>):<p className="ref-empty">No recent activity yet.</p>}</section></div></div></div>;
}
