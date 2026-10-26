import { useEffect, useState } from "react";
import { api } from "./api";
import { EquipmentOperations } from "./equipment-operations";
import { EquipmentManagement } from "./equipment-management";
import type { Session } from "./types";

type Asset = { id:number;asset_code:string;name:string;equipment_type:string;status:string;inspection_valid_through:string|null;inspection_review_status:string|null;inspection_evidence_ref:string|null;operational_condition?:string|null;ownership_type?:string|null;location_id?:number|null };
type Tab = "Register"|"Availability"|"Allocations"|"Usage"|"Maintenance"|"Compliance"|"Custody"|"Hire Tracking"|"Dashboard";
const tabs:Tab[] = ["Register","Availability","Allocations","Usage","Maintenance","Compliance","Custody","Hire Tracking","Dashboard"];

/** Embedded equipment workspace: reuses Planning's canonical equipment register.
 *  No stock, contract, GL, or compliance status is inferred from missing endpoints. */
export function EquipmentHome({session,initialProjectId}:{session:Session;initialProjectId?:number|null}){
  const [project,setProject]=useState<number>(initialProjectId || session.memberships.find(m=>m.project_id)?.project_id || 0);
  const [tab,setTab]=useState<Tab>("Register");
  const [items,setItems]=useState<Asset[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [filter,setFilter]=useState("");
  const canView=session.user.organization_admin||session.memberships.some(m=>m.project_id===project && (m.permissions?.includes("planning.view")||m.permissions?.includes("planning.manage")));
  const canManage=session.user.organization_admin||session.memberships.some(m=>m.project_id===project && m.permissions?.includes("planning.manage"));
  const base=`/projects/${project}/planning`;
  useEffect(()=>{setProject(initialProjectId||0);setItems([]);setError("");},[initialProjectId]);
  useEffect(()=>{
    if(!project||!canView){setItems([]);return;}
    let active=true;setBusy(true);setError("");setItems([]);
    api<{items:Asset[]}>(base+"/equipment-assets").then(r=>{if(active)setItems(r.items||[])}).catch(e=>{if(active)setError(e instanceof Error?e.message:String(e))}).finally(()=>{if(active)setBusy(false)});
    return()=>{active=false};
  },[base,canView,project]);
  async function refresh(){if(!project||!canView)return;setBusy(true);setError("");try{const r=await api<{items:Asset[]}>(base+"/equipment-assets");setItems(r.items||[])}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
  async function create(event:React.FormEvent<HTMLFormElement>){event.preventDefault();if(!canManage)return;const form=event.currentTarget;const fields=new FormData(form);setBusy(true);setError("");setNotice("");try{await api(base+"/equipment-assets","POST",{asset_code:String(fields.get("asset_code")||"").trim(),name:String(fields.get("name")||"").trim(),equipment_type:String(fields.get("equipment_type")||"").trim()});form.reset();setNotice("Equipment registered in the existing Planning register.");await refresh()}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
  const shown=items.filter(x=>`${x.asset_code} ${x.name} ${x.equipment_type}`.toLowerCase().includes(filter.toLowerCase()));
  const card:React.CSSProperties={background:"#fff",border:"1px solid #dce4ed",borderRadius:12,padding:18};
  return <section style={{display:"grid",gap:14}}>
    <div style={card}><h2 style={{marginTop:0}}>Equipment &amp; Tools</h2><p style={{color:"#52657d"}}>Equipment master and availability authority remain in Planning. Stores owns spare-part stock; Finance owns accounting postings.</p>
      <label>Project <select value={project} onChange={e=>setProject(Number(e.target.value))}>
        <option value={0}>Select project</option>
        {Array.from(new Set(session.memberships.filter(m=>m.project_id).map(m=>m.project_id as number))).map(id=><option key={id} value={id}>Project #{id}</option>)}
        {session.user.organization_admin && project>0 && !session.memberships.some(m=>m.project_id===project) && <option value={project}>Project #{project}</option>}
      </select></label>
    </div>
    <nav aria-label="Equipment management screens" style={{display:"flex",flexWrap:"wrap",gap:8}}>{tabs.map(t=><button key={t} type="button" aria-current={tab===t?"page":undefined} onClick={()=>setTab(t)} style={{borderRadius:8,padding:"9px 12px",background:tab===t?"#e8eef6":"#fff",color:"#243850",border:"1px solid #dce4ed",fontWeight:tab===t?700:400}}>{t}</button>)}</nav>
    {!project?<div style={card}>Choose a project to view its equipment records.</div>:!canView?<div style={card} role="alert">You do not have Planning equipment access for this project.</div>:<>
      {error&&<p role="alert" style={{color:"#b42318"}}>{error}</p>}
      {notice&&<p role="status" style={{color:"#166a40"}}>{notice}</p>}
      {tab==="Register"?<div style={card}><h3>Equipment Register</h3><p>Uses the canonical Planning equipment register. Inspection review does not prove HSE release or current allocation.</p>
        {canManage&&<form onSubmit={e=>void create(e)} style={{display:"flex",flexWrap:"wrap",gap:8}}><input required name="asset_code" placeholder="Asset code"/><input required name="name" placeholder="Equipment description"/><input required name="equipment_type" placeholder="Equipment category"/><button disabled={busy}>Register</button></form>}
        <div style={{display:"flex",gap:8,marginTop:12}}><input aria-label="Search equipment" value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Search code / equipment / category"/><button disabled={busy} onClick={()=>void refresh()}>Refresh</button></div>
        <div style={{overflowX:"auto",marginTop:12}}><table style={{width:"100%"}}><thead><tr><th>Asset code</th><th>Name</th><th>Type</th><th>Status</th><th>Inspection</th><th>Valid through</th><th>Planning reference</th></tr></thead><tbody>{shown.map(x=><tr key={x.id}><td>{x.asset_code}</td><td>{x.name}</td><td>{x.equipment_type}</td><td>{x.status}</td><td>{x.inspection_review_status||"Unverified"}</td><td>{x.inspection_valid_through||"—"}</td><td>equipment:{x.id}</td></tr>)}</tbody></table></div>{!busy&&!shown.length&&<p>No equipment records found.</p>}
      </div>:["Availability","Allocations","Usage","Custody"].includes(tab)?<EquipmentOperations key={`${project}-${tab}`} project={project} tab={tab as "Availability"|"Allocations"|"Usage"|"Custody"} assets={items} />: ["Maintenance","Compliance","Hire Tracking","Dashboard"].includes(tab)?<EquipmentManagement key={`${project}-${tab}`} project={project} tab={tab as "Maintenance"|"Compliance"|"Hire Tracking"|"Dashboard"} assets={items}/>:<div style={card}><h3>{tab}</h3>
       <p style={{color:"#52657d"}}>This screen is reserved for authoritative Equipment workflow data. It does not invent {tab.toLowerCase()} values or imply approved transactions.</p>
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
