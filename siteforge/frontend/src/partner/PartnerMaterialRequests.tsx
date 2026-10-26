import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";

type Project = { project_id:number;code:string;name:string };
type Package = {id:number;code:string;name:string};
type Source = {requirement_line_id:number;requirement:string; item_id:number;quantity:string;unit:string;work_package_ids:number[]};
type AllocationStatus = {request_id:number;request_status:string;approved_quantity:string|null;allocated_quantity:string;active_reserved_quantity:string;consumed_by_issue:string;released_quantity:string;unallocated_quantity:string;allocations:{status:string;allocated_quantity:string;remaining_quantity:string;released_quantity:string;consumed_by_issue:string}[];note:string};
type Request = {id:number;request_key:string;requirement_line_id:number; quantity:string;unit:string;status:string;required_date:string};
export function PartnerMaterialRequests({initialProjectId}:{initialProjectId:number|null}) {
 const [projects,setProjects]=useState<Project[]>([]),[pid,setPid]=useState<number|null>(null);
 const [packages,setPackages]=useState<Package[]>([]),[sources,setSources]=useState<Source[]>([]),[rows,setRows]=useState<Request[]>([]);
 const [key,setKey]=useState(""),[line,setLine]=useState(0),[pkg,setPkg]=useState(0),[qty,setQty]=useState(""),[date,setDate]=useState(""),[reason,setReason]=useState("");
 const [allocation,setAllocation]=useState<AllocationStatus|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
 useEffect(()=>{void api<{items:Project[]}>("/partner/projects").then(x=>{setProjects(x.items);setPid(x.items.find(y=>y.project_id===initialProjectId)?.project_id??x.items[0]?.project_id??null)}).catch(e=>setError((e as Error).message))},[initialProjectId]);
 async function refresh(project:number){try{const [s,r]=await Promise.all([api<{work_packages:Package[];requirements:Source[]}>(`/partner/projects/${project}/stores/issue-request-sources`),api<Request[]>(`/partner/projects/${project}/stores/material-requests`)]);setPackages(s.work_packages);setSources(s.requirements);setRows(r);}catch(e){setError((e as Error).message);setSources([]);setRows([])}}
 useEffect(()=>{setPackages([]);setSources([]);setRows([]);setLine(0);setPkg(0);if(pid)void refresh(pid)},[pid]);
 const selected=sources.find(x=>x.requirement_line_id===line);
 async function create(e:FormEvent){e.preventDefault();if(!pid||!line||!pkg||busy)return;setBusy(true);setError("");setMessage("");try{await api(`/partner/projects/${pid}/stores/material-requests`,"POST",{request_key:key,requirement_line_id:line,work_package_id:pkg,quantity:qty,required_date:date,reason});setMessage("Draft issue request created. Submit it for independent internal approval; no stock has been reserved.");setKey("");setQty("");setReason("");await refresh(pid)}catch(ex){setError((ex as Error).message)}finally{setBusy(false)}}
 async function viewAllocation(id:number){if(!pid)return;setError("");setAllocation(null);try{setAllocation(await api<AllocationStatus>(`/partner/projects/${pid}/stores/material-requests/${id}/allocations`))}catch(e){setError((e as Error).message)}}
 async function submit(id:number){if(!pid||busy)return;setBusy(true);setError("");try{await api(`/partner/projects/${pid}/stores/material-requests/${id}/submit`,"POST",{});setMessage("Request submitted for internal review.");await refresh(pid)}catch(ex){setError((ex as Error).message)}finally{setBusy(false)}}
 return <section className="panel"><h2>My material issue requests</h2><p className="muted">Request release of material against an approved requirement assigned to your company and released work package. This does not purchase material, reserve stock, or confirm issue.</p>
 {projects.length>1&&<label>Project <select value={pid??""} onChange={e=>setPid(Number(e.target.value))}>{projects.map(x=><option key={x.project_id} value={x.project_id}>{x.code} — {x.name}</option>)}</select></label>}
 {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}
 <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Request</th><th>Requirement line</th><th>Quantity</th><th>Required date</th><th>Status</th><th>Action</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.request_key}</td><td>#{r.requirement_line_id}</td><td>{r.quantity} {r.unit}</td><td>{r.required_date}</td><td>{r.status}</td><td><button type="button" onClick={()=>void viewAllocation(r.id)}>Allocation status</button> {r.status==='Draft'&&<button type="button" disabled={busy} onClick={()=>void submit(r.id)}>Submit for approval</button>}</td></tr>)}</tbody></table></div>
 {allocation&&<div className="panel" style={{marginTop:12,padding:12}}><h3>Allocation status — request #{allocation.request_id}</h3><p>Reserved: {allocation.active_reserved_quantity} · Issued against reservation: {allocation.consumed_by_issue} · Released: {allocation.released_quantity} · Unallocated: {allocation.unallocated_quantity}. None of these confirms installation.</p><table className="mp-table"><thead><tr><th>Quantity</th><th>Remaining</th><th>Status</th></tr></thead><tbody>{allocation.allocations.map((a,i)=><tr key={i}><td>{a.allocated_quantity}</td><td>{a.remaining_quantity}</td><td>{a.status}</td></tr>)}</tbody></table><button type="button" onClick={()=>setAllocation(null)}>Close</button></div>}
 {pid&&<form onSubmit={create} style={{display:"grid",gap:12,maxWidth:800,marginTop:20}}><h3>New issue request</h3>
 <label>Request number <input required value={key} maxLength={120} onChange={e=>setKey(e.target.value)}/></label>
 <label>Approved requirement line <select required value={line} onChange={e=>{setLine(Number(e.target.value));setPkg(0)}}><option value={0}>Select approved requirement</option>{sources.map(s=><option key={s.requirement_line_id} value={s.requirement_line_id}>{s.requirement} / line #{s.requirement_line_id} — item #{s.item_id} ({s.quantity} {s.unit})</option>)}</select></label>
 <label>Assigned work package <select required value={pkg} onChange={e=>setPkg(Number(e.target.value))}><option value={0}>Select released work package</option>{packages.filter(p=>selected?.work_package_ids.includes(p.id)).map(p=><option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}</select></label>
 <label>Quantity ({selected?.unit||'stock unit'}) <input required type="number" min="0.001" step="0.001" max={selected?.quantity} value={qty} onChange={e=>setQty(e.target.value)}/></label>
 <label>Required date <input required type="date" value={date} onChange={e=>setDate(e.target.value)}/></label>
 <label>Reason <textarea value={reason} onChange={e=>setReason(e.target.value)} maxLength={2000}/></label>
 <button className="btn" type="submit" disabled={!line||!pkg||busy}>{busy?'Saving...':'Create draft issue request'}</button>
 {!sources.length&&<p className="muted">No approved requirements linked to your company's released work packages.</p>}
 </form>}
 </section>;
}
