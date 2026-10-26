import {useEffect,useState,type FormEvent} from 'react';
import {api} from '../api';
type Project={project_id:number;code:string;name:string};
type Handover={id:number;handover_reference:string;received_quantity:string|null;status:string};
type ReturnRow={id:number;handover_id:number;requested_quantity:string;received_quantity:string|null;condition:string;reason:string;status:string;qa_decision:string|null;qa_evidence:string|null};
export function PartnerMaterialReturns({initialProjectId}:{initialProjectId:number|null}){
 const [projects,setProjects]=useState<Project[]>([]),[pid,setPid]=useState<number|null>(null),[handovers,setHandovers]=useState<Handover[]>([]),[rows,setRows]=useState<ReturnRow[]>([]);
 const [selected,setSelected]=useState(''),[quantity,setQuantity]=useState(''),[condition,setCondition]=useState('Unused'),[reason,setReason]=useState('');
 const [error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{void api<{items:Project[]}>('/partner/projects').then(x=>{setProjects(x.items);setPid(x.items.find(p=>p.project_id===initialProjectId)?.project_id??x.items[0]?.project_id??null)}).catch(e=>setError((e as Error).message))},[initialProjectId]);
 async function refresh(project:number){setError('');try{const [h,r]=await Promise.all([api<{records:Handover[]}>(`/partner/projects/${project}/stores/material-handovers`),api<{records:ReturnRow[]}>(`/partner/projects/${project}/stores/material-returns`)]);setHandovers(h.records);setRows(r.records)}catch(e){setError((e as Error).message);setHandovers([]);setRows([])}}
 useEffect(()=>{setHandovers([]);setRows([]);setSelected('');if(pid)void refresh(pid)},[pid]);
 const eligible=handovers.filter(h=>(h.status==='Acknowledged'||h.status==='Resolved')&&h.received_quantity&&Number(h.received_quantity)>0&&!rows.some(r=>r.handover_id===h.id));
 async function submit(e:FormEvent){e.preventDefault();if(!pid||!selected||busy)return;setBusy(true);setError('');setMessage('');try{await api(`/partner/projects/${pid}/stores/material-returns`,'POST',{handover_id:Number(selected),quantity,condition,reason});setMessage('Return request submitted for Stores verification and independent QA disposition. No inventory was posted.');setSelected('');setQuantity('');setReason('');await refresh(pid)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="panel"><h2>Material Returns</h2><p className="muted">Return unused, surplus, or damaged materials previously acknowledged against your own material handovers. This records custody only and does not increase available stock.</p>
 {projects.length>1&&<label>Project <select value={pid??''} onChange={e=>setPid(Number(e.target.value))}>{projects.map(p=><option key={p.project_id} value={p.project_id}>{p.code} — {p.name}</option>)}</select></label>}
 {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}
 <button type="button" onClick={()=>pid&&void refresh(pid)}>Refresh returns</button>
 <form onSubmit={submit} style={{display:'grid',gap:10,maxWidth:650,marginTop:16}}><h3>Request return to Stores</h3>
 <label>Eligible material handover <select required value={selected} onChange={e=>{setSelected(e.target.value);setQuantity('')}}><option value="">Choose acknowledged handover</option>{eligible.map(h=><option key={h.id} value={h.id}>{h.handover_reference} — received {h.received_quantity}</option>)}</select></label>
 <label>Return quantity <input required type="number" min="0.001" step="0.001" max={eligible.find(h=>String(h.id)===selected)?.received_quantity||undefined} value={quantity} onChange={e=>setQuantity(e.target.value)}/></label>
 <label>Condition <select value={condition} onChange={e=>setCondition(e.target.value)}><option>Unused</option><option>Damaged</option><option>Surplus</option></select></label>
 <label>Reason / custody evidence <textarea minLength={3} maxLength={4000} required value={reason} onChange={e=>setReason(e.target.value)}/></label>
 <button className="btn" type="submit" disabled={busy||!selected}>{busy?'Submitting...':'Submit return request'}</button></form>
 <h3 style={{marginTop:22}}>My submitted returns</h3><div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Return ID</th><th>Handover</th><th>Requested</th><th>Stores received</th><th>Condition</th><th>Status</th><th>QA decision</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.id}</td><td>{handovers.find(h=>h.id===r.handover_id)?.handover_reference??r.handover_id}</td><td>{r.requested_quantity}</td><td>{r.received_quantity??'—'}</td><td>{r.condition}</td><td>{r.status}</td><td>{r.qa_decision??'Pending'}{r.qa_evidence&&<small> · {r.qa_evidence}</small>}</td></tr>)}</tbody></table></div>{rows.length===0&&<p className="muted">No material returns yet.</p>}
 </section>
}
