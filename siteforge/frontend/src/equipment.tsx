import { useEffect, useState } from "react";
import { Activity, BookOpen, CalendarClock, CalendarRange, KeyRound, LayoutDashboard, Receipt, ShieldCheck, Wrench, type LucideIcon } from "lucide-react";
import { api } from "./api";
import { EquipmentOperations } from "./equipment-operations";
import { EquipmentManagement } from "./equipment-management";
import type { Page, Project, Session } from "./types";

type Asset = { id:number;asset_code:string;name:string;equipment_type:string;status:string;inspection_valid_through:string|null;inspection_review_status:string|null;inspection_evidence_ref:string|null;operational_condition?:string|null;ownership_type?:string|null;location_id?:number|null };
type Tab = "Register"|"Availability"|"Allocations"|"Usage"|"Maintenance"|"Compliance"|"Custody"|"Hire Tracking"|"Dashboard";
const tabs:Tab[] = ["Dashboard","Register","Availability","Allocations","Usage","Maintenance","Compliance","Custody","Hire Tracking"];
const TAB_ICON:Record<Tab,LucideIcon> = {Register:BookOpen,Availability:CalendarRange,Allocations:CalendarClock,Usage:Activity,Maintenance:Wrench,Compliance:ShieldCheck,Custody:KeyRound,"Hire Tracking":Receipt,Dashboard:LayoutDashboard};
const TAB_TONE:Record<Tab,string> = {Register:"tone-eqreg",Availability:"tone-eqavail",Allocations:"tone-eqalloc",Usage:"tone-equse",Maintenance:"tone-eqmaint",Compliance:"tone-eqcomp",Custody:"tone-eqcust","Hire Tracking":"tone-eqhire",Dashboard:"tone-eqdash"};
function slug(value:string){return value.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'')}
function Pill({value}:{value:string}){return <span className={`state-pill state-${slug(value)}`}>{value}</span>}

/** Embedded equipment workspace: reuses Planning's canonical equipment register.
 *  No stock, contract, GL, or compliance status is inferred from missing endpoints. */
export function EquipmentHome({session,initialProjectId}:{session:Session;initialProjectId?:number|null}){
  const [project,setProject]=useState<number>(initialProjectId || session.memberships.find(m=>m.project_id)?.project_id || 0);
  const [tab,setTab]=useState<Tab>("Dashboard");
  const [projects,setProjects]=useState<Project[]>([]);
  const [items,setItems]=useState<Asset[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [filter,setFilter]=useState("");
  const canView=session.user.organization_admin||session.memberships.some(m=>m.project_id===project && (m.permissions?.includes("planning.view")||m.permissions?.includes("planning.manage")));
  const canManage=session.user.organization_admin||session.memberships.some(m=>m.project_id===project && m.permissions?.includes("planning.manage"));
  const base=`/projects/${project}/planning`;
  const memberProjectIds=Array.from(new Set(session.memberships.filter(m=>m.project_id).map(m=>m.project_id as number)));
  const projectIds=Array.from(new Set([...memberProjectIds,...projects.map(p=>p.id).filter((id):id is number=>typeof id==="number")]));
  useEffect(()=>{if(initialProjectId)setProject(initialProjectId);setItems([]);setError("");},[initialProjectId]);
  useEffect(()=>{let active=true;api<Page<Project>>("/projects?limit=100").then(r=>{if(active)setProjects(r.items||[])}).catch(()=>{});return()=>{active=false};},[]);
  useEffect(()=>{const first=projects.find(p=>p.id)?.id;if(first)setProject(current=>current||first);},[projects]);
  const projectLabel=(id:number)=>{const p=projects.find(x=>x.id===id);return p?`${p.code} — ${p.name}`:`Project #${id}`};
  useEffect(()=>{
    if(!project||!canView){setItems([]);return;}
    let active=true;setBusy(true);setError("");setItems([]);
    api<{items:Asset[]}>(base+"/equipment-assets").then(r=>{if(active)setItems(r.items||[])}).catch(e=>{if(active)setError(e instanceof Error?e.message:String(e))}).finally(()=>{if(active)setBusy(false)});
    return()=>{active=false};
  },[base,canView,project]);
  async function refresh(){if(!project||!canView)return;setBusy(true);setError("");try{const r=await api<{items:Asset[]}>(base+"/equipment-assets");setItems(r.items||[])}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
  async function create(event:React.FormEvent<HTMLFormElement>){event.preventDefault();if(!canManage)return;const form=event.currentTarget;const fields=new FormData(form);setBusy(true);setError("");setNotice("");try{await api(base+"/equipment-assets","POST",{asset_code:String(fields.get("asset_code")||"").trim(),name:String(fields.get("name")||"").trim(),equipment_type:String(fields.get("equipment_type")||"").trim()});form.reset();setNotice("Equipment registered in the existing Planning register.");await refresh()}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
  const shown=items.filter(x=>`${x.asset_code} ${x.name} ${x.equipment_type}`.toLowerCase().includes(filter.toLowerCase()));
  return <section className="panel">
    <h2>Equipment &amp; Tools</h2>
    <p className="muted">Equipment master and availability authority remain in Planning. Stores owns spare-part stock; Finance owns accounting postings.</p>
    <div className="contact-form">
      <label>Project <select value={project} onChange={e=>setProject(Number(e.target.value))}>
        <option value={0}>Select project</option>
        {projectIds.map(id=><option key={id} value={id}>{projectLabel(id)}</option>)}
        {project>0 && !projectIds.includes(project) && <option value={project}>{projectLabel(project)}</option>}
      </select></label>
    </div>
    <div role="navigation" aria-label="Equipment management screens" className="proc-nav">{tabs.map(t=>{const Icon=TAB_ICON[t];return <button key={t} type="button" className={`proc-tab ${TAB_TONE[t]}${tab===t?" is-on":""}`} aria-pressed={tab===t} aria-current={tab===t?"page":undefined} onClick={()=>setTab(t)}><Icon size={14} strokeWidth={2.4}/><span>{t}</span></button>})}</div>
    {!project?<p className="note-card">Choose a project to view its equipment records.</p>:!canView?<p className="note-card note-alert" role="alert">You do not have Planning equipment access for this project.</p>:<>
      {error&&<p role="alert" className="error">{error}</p>}
      {notice&&<p role="status" className="note-card note-good">{notice}</p>}
      {tab==="Register"?<div><h3 className="section-mark"><BookOpen size={18} strokeWidth={2.4}/> Equipment Register</h3><p className="muted">Uses the canonical Planning equipment register. Inspection review does not prove HSE release or current allocation.</p>
        {canManage&&<form onSubmit={e=>void create(e)} className="contact-form"><input required name="asset_code" placeholder="Asset code"/><input required name="name" placeholder="Equipment description"/><input required name="equipment_type" placeholder="Equipment category"/><button className="primary" disabled={busy}>Register</button></form>}
        <div className="contact-form st-divider"><input aria-label="Search equipment" value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Search code / equipment / category"/><button disabled={busy} onClick={()=>void refresh()}>Refresh</button></div>
        <div className="hr-table-wrap"><table><thead><tr><th>Asset code</th><th>Name</th><th>Type</th><th>Status</th><th>Inspection</th><th>Valid through</th><th>Planning reference</th></tr></thead><tbody>{shown.map(x=><tr key={x.id}><td><strong>{x.asset_code}</strong></td><td>{x.name}</td><td>{x.equipment_type}</td><td><Pill value={x.status}/></td><td><Pill value={x.inspection_review_status||"Unverified"}/></td><td>{x.inspection_valid_through||"—"}</td><td>equipment:{x.id}</td></tr>)}</tbody></table></div>{!busy&&!shown.length&&<p className="muted">No equipment records found.</p>}
      </div>:["Availability","Allocations","Usage","Custody"].includes(tab)?<EquipmentOperations key={`${project}-${tab}`} project={project} tab={tab as "Availability"|"Allocations"|"Usage"|"Custody"} assets={items} />: ["Maintenance","Compliance","Hire Tracking","Dashboard"].includes(tab)?<EquipmentManagement key={`${project}-${tab}`} project={project} tab={tab as "Maintenance"|"Compliance"|"Hire Tracking"|"Dashboard"} assets={items} onOpen={setTab}/>:<div><h3>{tab}</h3>
       <p className="muted">This screen is reserved for authoritative Equipment workflow data. It does not invent {tab.toLowerCase()} values or imply approved transactions.</p>
       {tab==="Availability"&&<p>Confirmed allocation windows, open maintenance holds and valid HSE releases must be reconciled server-side before availability can be shown.</p>}
       {tab==="Allocations"&&<p>Booking confirmation remains under Planning until the integration endpoint and project permissions are verified.</p>}
       {tab==="Usage"&&<p>Equipment hours, meter and fuel records require a verified project-scoped usage feed.</p>}
       {tab==="Maintenance"&&<p>Breakdown holds, repair stages and independent release verification require an authoritative maintenance feed.</p>}
       {tab==="Custody"&&<p>Issue and return balances must come from Equipment custody events, not Stores stock balances.</p>}
       {tab==="Hire Tracking"&&<p>Hire references are not Finance-posted costs; only Contracts/Finance-approved evidence may be displayed.</p>}
       {tab==="Dashboard"&&<p>Utilization and availability KPIs remain unavailable until authoritative operational endpoints are connected.</p>}
       <p><strong>Integration status:</strong> Not connected in E8A; no estimated metrics are displayed.</p>
      </div>}
    </>}
  </section>;
}
