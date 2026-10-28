import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BookOpen, CircleHelp, LayoutDashboard, PowerOff, Receipt, ShieldCheck, Wrench, type LucideIcon } from "lucide-react";
import { api } from "./api";

export type ManagementTab = "Maintenance" | "Compliance" | "Hire Tracking" | "Dashboard";
const TAB_ICON:Record<ManagementTab,LucideIcon>={Maintenance:Wrench,Compliance:ShieldCheck,"Hire Tracking":Receipt,Dashboard:LayoutDashboard};
type OpenTab = "Register" | "Maintenance";
type Asset = { id:number;asset_code:string;name:string;status:string;operational_condition?:string|null;ownership_type?:string|null };
type Maintenance = { id:number;kind:string;status:string;title:string;due_on?:string|null;created_by?:number|null;released_by?:number|null };
type Evidence = { id:number;kind:string;status:string;required?:boolean;valid_through?:string|null;evidence_ref?:string|null };
type Hold = { id:number;status:string;reason:string };
type Compliance = { compliance_eligible:boolean;reason?:string|null;evidence:Evidence[];holds:Hold[];basis?:string };
type Master = { asset?:Record<string,unknown>; hire_contract_ref?:string|null;ownership_type?:string|null;[key:string]:unknown };
type Handoff = { handoff_id:number;asset_id:number;project_id:number;authority_kind?:string;authority_id?:number;handoff_recorded?:boolean;[key:string]:unknown };
const value=(v:unknown)=>v===null||v===undefined||v===""?"—":String(v);
function Table({head,rows}:{head:string[];rows:string[][]}){return <div className="hr-table-wrap"><table><thead><tr>{head.map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{r.map((v,j)=><td key={j}>{v}</td>)}</tr>)}</tbody></table>{rows.length===0&&<p className="muted">No verified records returned.</p>}</div>}
/** Authoritative evidence readback only. Equipment does not post Stores or Finance transactions. */
export function EquipmentManagement({project,tab,assets,onOpen}:{project:number;tab:ManagementTab;assets:Asset[];onOpen?:(tab:OpenTab)=>void}){
  const [assetId,setAssetId]=useState(0);
  const [handoffId,setHandoffId]=useState("");
  const [revision,setRevision]=useState(0);
  const [orders,setOrders]=useState<Maintenance[]>([]);
  const [compliance,setCompliance]=useState<Compliance|null>(null);
  const [master,setMaster]=useState<Master|null>(null);
  const [handoff,setHandoff]=useState<Handoff|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  useEffect(()=>{setAssetId(0);setHandoffId("");},[project]);
  useEffect(()=>{
    let live=true;setOrders([]);setCompliance(null);setMaster(null);setHandoff(null);setError("");
    if(tab==="Dashboard"||!assetId||!project)return;
    if(tab==="Hire Tracking"&&handoffId!==""&&!/^[1-9]\d*$/.test(handoffId)){setError("Enter a positive handoff ID.");return;}
    const prefix=`/projects/${project}/planning/equipment-assets/${assetId}`;
    setLoading(true);
    (async()=>{
      if(tab==="Maintenance"){
        const r=await api<{items:Maintenance[]}>(`${prefix}/maintenance`);
        if(live)setOrders(r.items||[]);
      }else if(tab==="Compliance"){
        const r=await api<Compliance>(`${prefix}/compliance-status`);
        if(live)setCompliance(r);
      }else if(tab==="Hire Tracking"){
        const m=await api<Master>(`${prefix}/master`);
        if(live)setMaster(m);
        if(handoffId){
          const h=await api<Handoff>(`${prefix}/authority-handoffs/${Number(handoffId)}`);
          if(live){if(h.asset_id!==assetId||h.project_id!==project)throw new Error("Handoff scope mismatch");setHandoff(h);}
        }
      }
    })().catch(e=>{if(live)setError(e instanceof Error?e.message:String(e))}).finally(()=>{if(live)setLoading(false)});
    return()=>{live=false};
  },[project,assetId,tab,handoffId,revision]);
  const selected=assets.find(a=>a.id===assetId);
  const counts=useMemo(()=>({total:assets.length,inactive:assets.filter(a=>a.status.toLowerCase()!=="active").length,restricted:assets.filter(a=>a.operational_condition&&a.operational_condition.toLowerCase()!=="serviceable").length,unknown:assets.filter(a=>!a.operational_condition).length}),[assets]);
  const TabIcon=TAB_ICON[tab];
  const dashCards:{label:string;value:number;tone:string;icon:LucideIcon;tab:OpenTab}[]=[
    {label:"Registered assets",value:counts.total,tone:"po",icon:BookOpen,tab:"Register"},
    {label:"Not active",value:counts.inactive,tone:"wait",icon:PowerOff,tab:"Register"},
    {label:"Non-serviceable condition",value:counts.restricted,tone:"impact",icon:AlertTriangle,tab:"Maintenance"},
    {label:"Condition not recorded",value:counts.unknown,tone:"order",icon:CircleHelp,tab:"Register"},
  ];
  return <section>
    <h3 className="section-mark"><TabIcon size={18} strokeWidth={2.4}/> {tab}</h3>
    <p className="muted">Project-scoped evidence from existing Equipment APIs. No inferred bookings, statutory certification, billable amounts, or Finance postings.</p>
    {tab==="Dashboard"?<>
      <div className="dash-grid eq-dash-grid">{dashCards.map(c=>{const Icon=c.icon;return <button key={c.label} type="button" className={`dash-card ${c.tone}`} onClick={()=>onOpen?.(c.tab)}><span className="dash-mark"><Icon size={15} strokeWidth={2.4}/></span><strong>{c.value}</strong><span className="dash-label">{c.label}</span></button>})}</div>
      <p className="muted">Counts are derived only from the loaded equipment register. They do not certify availability, utilization, maintenance compliance or hire costs. Project register refresh is available on the Register tab.</p>
      <Table head={["Asset", "Name", "Register status", "Condition", "Ownership"]} rows={assets.map(a=>[a.asset_code,a.name,a.status,value(a.operational_condition),value(a.ownership_type)])}/>
    </>:<>
      <div className="contact-form">
        <label>Equipment <select value={assetId} onChange={e=>{setAssetId(Number(e.target.value));setHandoffId("")}}><option value={0}>Select equipment</option>{assets.map(a=><option key={a.id} value={a.id}>{a.asset_code} — {a.name}</option>)}</select></label>
        {tab==="Hire Tracking"&&<label>Existing handoff ID <input aria-label="Existing handoff ID" value={handoffId} onChange={e=>setHandoffId(e.target.value)} placeholder="Optional" inputMode="numeric"/></label>}
        <button type="button" disabled={loading} onClick={()=>setRevision(n=>n+1)}>Refresh</button>
      </div>
      {loading&&<p role="status" className="muted">Loading verified records…</p>}
      {error&&<p role="alert" className="error">{error}</p>}
      {!selected&&<p className="note-card">Select equipment to load its {tab.toLowerCase()} records.</p>}
      {tab==="Maintenance"&&selected&&!loading&&!error&&<>
        <p>Maintenance orders are evidence only. A completed repair does not itself provide HSE clearance.</p>
        <Table head={["Order", "Kind", "Title", "Status", "Due", "Released by"]} rows={orders.map(o=>[String(o.id),o.kind,o.title,o.status,value(o.due_on),value(o.released_by)])}/>
      </>}
      {tab==="Compliance"&&compliance&&<>
        <p><strong>Internal compliance rule:</strong> {compliance.compliance_eligible?"Eligible":"Restricted / evidence incomplete"}. {value(compliance.reason)}</p>
        <p className="muted">{compliance.basis||"Internal workflow evidence; not external certification verification."}</p>
        <h4>Inspection and certification evidence</h4>
        <Table head={["Record", "Kind", "Review", "Valid through", "Evidence ref"]} rows={(compliance.evidence||[]).map(e=>[String(e.id),e.kind,e.status,value(e.valid_through),value(e.evidence_ref)])}/>
        <h4>Safety holds</h4><Table head={["Hold", "Status", "Reason"]} rows={(compliance.holds||[]).map(h=>[String(h.id),h.status,h.reason])}/>
      </>}
      {tab==="Hire Tracking"&&master&&<>
        <p><strong>Register ownership:</strong> {value(master.ownership_type??master.asset?.ownership_type??selected?.ownership_type)}. <strong>Hire reference:</strong> {value(master.hire_contract_ref??master.asset?.hire_contract_ref)}.</p>
        <p>References are not approved hire invoices or Finance-posted costs. Enter an existing audited handoff ID for verified source tracing.</p>
        {handoff&&<Table head={["Handoff", "Project", "Asset", "Kind", "Status", "Source ID"]} rows={[[value(handoff.handoff_id),value(handoff.project_id),value(handoff.asset_id),value(handoff.authority_kind),handoff.handoff_recorded?"Recorded":"Unverified",value(handoff.authority_id)]]}/>}
      </>}
    </>}
  </section>;
}
