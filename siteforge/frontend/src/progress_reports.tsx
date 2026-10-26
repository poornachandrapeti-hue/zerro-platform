import {useCallback,useEffect,useState} from 'react';
import {Download,FilePlus2,FileText,History,RefreshCw} from 'lucide-react';
import {api,fetchBlob} from './api';
import {Pill,downloadCsv} from './progress_charts';
type Report={id:number;report_number:string;revision:number;report_type:string;period_start:string;period_end:string;data_date:string;status:string;prepared_by:number;reviewer_id:number;approver_id:number;commentary:string;reason:string};
type Detail=Report & {snapshot:Record<string,unknown>|null;events:{event:string;actor_id:number;note:string;created_at:string}[]};
export function ProgressReports({project,userId,canPrepare}:{project:number;userId:number;canPrepare:boolean}){
  const [reports,setReports]=useState<Report[]>([]);
  const [selected,setSelected]=useState<Detail|null>(null);
  const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const [form,setForm]=useState({report_number:'',report_type:'Weekly',period_start:'',period_end:'',data_date:'',reviewer_id:'',approver_id:'',commentary:''});
  const [note,setNote]=useState('');
  const [includeActivities,setIncludeActivities]=useState(true);
  const [includeTargets,setIncludeTargets]=useState(true);
  const [includeExceptions,setIncludeExceptions]=useState(true);
  const load=useCallback(async()=>{try{setReports(await api<Report[]>(`/projects/${project}/progress/reports`));}catch(e){setError(String(e));}},[project]);
  const detail=async(id:number)=>{try{setSelected(await api<Detail>(`/projects/${project}/progress/reports/${id}`));}catch(e){setError(String(e));}};
  useEffect(()=>{setSelected(null);void load()},[load]);
  const act=async(action:string,id:number,body?:unknown)=>{setBusy(true);setError('');try{const row=await api<Report>(`/projects/${project}/progress/reports/${id}/${action}`,'POST',body);await load();await detail(action==='revise'?row.id:id);setNote('')}catch(e){setError(String(e))}finally{setBusy(false)}};
  const create=async()=>{setBusy(true);setError('');try{const row=await api<Report>(`/projects/${project}/progress/reports`,'POST',{...form,reviewer_id:Number(form.reviewer_id),approver_id:Number(form.approver_id)});await load();await detail(row.id)}catch(e){setError(String(e))}finally{setBusy(false)}};
  const exportReport=()=>{
    if(!selected?.snapshot)return;
    const snapshot=selected.snapshot;
    const rows:(string|number|null|undefined)[][]=[['Report number','Revision','Status','Data date','Section','Item','Value'],
      [selected.report_number,selected.revision,selected.status,selected.data_date,'Overview','Commentary',selected.commentary]];
    const add=(section:string,item:string,value:unknown)=>rows.push([selected.report_number,selected.revision,selected.status,selected.data_date,section,item,typeof value==='object'?JSON.stringify(value):String(value??'N/A')]);
    add('Overview','Measurement',snapshot.measure);add('Overview','Baseline',JSON.stringify(snapshot.publication??null));
    add('Overview','Source freshness',snapshot.source_freshness);
    if(includeActivities&&Array.isArray(snapshot.actuals))for(const a of snapshot.actuals as Record<string,unknown>[])add('Activities',String(a.code??'Activity'),a);
    if(includeTargets&&Array.isArray(snapshot.planned))for(const t of snapshot.planned as Record<string,unknown>[])add('Planned targets',String(t.period_end??'Period'),t.planned_percent);
    if(includeExceptions&&Array.isArray(snapshot.exceptions))for(const e of snapshot.exceptions)add('Data quality','Exception',e);
    downloadCsv(`progress-report-${selected.id}-revision-${selected.revision}.csv`,rows);
  };
  const exportFormatted=async(format:'xlsx'|'pdf')=>{setBusy(true);setError('');try{
    if(!selected?.snapshot)return;
    const qs=new URLSearchParams();qs.append('sections','summary');
    if(includeActivities)qs.append('sections','activities');
    if(includeTargets)qs.append('sections','targets');
    if(includeExceptions)qs.append('sections','exceptions');
    const blob=await fetchBlob(`/projects/${project}/progress/reports/${selected.id}/export/${format}?${qs.toString()}`);
    const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;
    a.download=`progress-report-${selected.id}-revision-${selected.revision}.${format}`;a.click();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){setError(String(e))}finally{setBusy(false)}};
  return <section className="panel">
    <h3 className="section-mark"><FileText size={18} strokeWidth={2.4}/> Period progress reports</h3>
    <p className="muted">Internal project reporting. Separate preparer, reviewer, and approver. Source totals freeze on submission. Published revisions are read-only; a correction creates a new revision.</p>
    <button type="button" className="tone-note" disabled={busy} onClick={()=>void load()}><RefreshCw size={14}/> Refresh reports</button>
    {error&&<p className="error" role="alert">{error}</p>}
    {canPrepare&&<div className="note-card"><h4 className="section-mark"><FilePlus2 size={16} strokeWidth={2.4}/> Create draft report</h4><div className="contact-form">
      <label>Report number <input value={form.report_number} onChange={e=>setForm({...form,report_number:e.target.value})}/></label>
      <label>Period <select value={form.report_type} onChange={e=>setForm({...form,report_type:e.target.value})}>{['Daily','Weekly','Monthly'].map(x=><option key={x}>{x}</option>)}</select></label>
      {(['period_start','period_end','data_date'] as const).map(k=><label key={k}>{k.replace('_',' ')} <input type="date" value={form[k]} onChange={e=>setForm({...form,[k]:e.target.value})}/></label>)}
      <label>Reviewer user ID <input type="number" min="1" value={form.reviewer_id} onChange={e=>setForm({...form,reviewer_id:e.target.value})}/></label>
      <label>Approver user ID <input type="number" min="1" value={form.approver_id} onChange={e=>setForm({...form,approver_id:e.target.value})}/></label>
      <label className="wide">Commentary <textarea value={form.commentary} onChange={e=>setForm({...form,commentary:e.target.value})}/></label>
      <div><button type="button" className="primary" disabled={busy||!form.report_number||!form.period_start||!form.period_end||!form.data_date||!form.reviewer_id||!form.approver_id} onClick={()=>void create()}>Create draft</button></div>
    </div></div>}
    <div className="mp-table-wrap" style={{marginTop:12}}><table className="mp-table"><thead><tr><th>Report</th><th>Period</th><th>Status</th><th>Action</th></tr></thead><tbody>{reports.map(r=><tr key={r.id}><td><strong>{r.report_number}</strong> · Rev {r.revision}</td><td>{r.report_type}: {r.period_start} – {r.period_end}</td><td><Pill value={r.status}/></td><td><button type="button" className="tone-note" onClick={()=>void detail(r.id)}>Open</button></td></tr>)}</tbody></table></div>
    {reports.length===0&&<p className="muted">No reports yet.</p>}
    {selected&&<div className="note-card" style={{marginTop:12}}><h4 className="section-mark"><FileText size={16} strokeWidth={2.4}/> {selected.report_number} · Revision {selected.revision} <Pill value={selected.status}/></h4>
      <p className="muted">Prepared by user {selected.prepared_by}; reviewer {selected.reviewer_id}; approver {selected.approver_id}. Data date {selected.data_date}.</p>
      <p>{selected.commentary||'No commentary'}</p>
      {selected.snapshot&&<div className="note-card note-good" style={{marginTop:12}}>
        <h4 className="section-mark"><Download size={16} strokeWidth={2.4}/> Saved snapshot and export sections</h4>
        <p className="muted">Export uses the frozen snapshot captured on submission, not current live results. The status and revision identify its approval state.</p>
        <div className="toolbar" style={{flexWrap:'wrap'}}>
          <label><input type="checkbox" checked={includeActivities} onChange={e=>setIncludeActivities(e.target.checked)}/> Activity measures</label>
          <label><input type="checkbox" checked={includeTargets} onChange={e=>setIncludeTargets(e.target.checked)}/> Approved targets</label>
          <label><input type="checkbox" checked={includeExceptions} onChange={e=>setIncludeExceptions(e.target.checked)}/> Data exceptions</label>
          <button type="button" className="tone-note" onClick={exportReport}>Export report CSV</button>
          <button type="button" className="tone-note" disabled={busy} onClick={()=>void exportFormatted('xlsx')}>Export Excel</button>
          <button type="button" className="tone-note" disabled={busy} onClick={()=>void exportFormatted('pdf')}>Export PDF</button>
        </div>
        <p className="muted">Review evidence in authorized source modules. Report approval does not approve operational records.</p>
      </div>}
      <div className="toolbar" style={{flexWrap:'wrap'}}>
        {selected.status==='Draft'&&selected.prepared_by===userId&&canPrepare&&<button className="tone-submit" disabled={busy} onClick={()=>void act('submit',selected.id)}>Submit for review</button>}
        {selected.status==='Pending Review'&&selected.reviewer_id===userId&&<button className="tone-approve" disabled={busy} onClick={()=>void act('review',selected.id,{note})}>Confirm review</button>}
        {selected.status==='Reviewed'&&selected.approver_id===userId&&<button className="tone-approve" disabled={busy} onClick={()=>void act('approve',selected.id)}>Approve</button>}
        {selected.status==='Approved'&&selected.approver_id===userId&&<button className="tone-submit" disabled={busy} onClick={()=>void act('publish',selected.id)}>Publish</button>}
        {(selected.status==='Pending Review'&&selected.reviewer_id===userId||selected.status==='Reviewed'&&selected.approver_id===userId)&&<button className="tone-return" disabled={busy||!note.trim()} onClick={()=>void act('return',selected.id,{note})}>Return with reason</button>}
        {(selected.status==='Published'||selected.status==='Returned')&&canPrepare&&<button className="tone-note" disabled={busy||!note.trim()} onClick={()=>void act('revise',selected.id,{note})}>Create revision</button>}
      </div>
      <label>Review / revision reason <textarea value={note} onChange={e=>setNote(e.target.value)} /></label>
      <h4 className="section-mark"><History size={16} strokeWidth={2.4}/> Audit events</h4><div className="mp-table-wrap"><table className="mp-table"><tbody>{selected.events.map((e,i)=><tr key={i}><td>{e.event}</td><td>User {e.actor_id}</td><td>{e.note}</td><td>{new Date(e.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>
    </div>}
  </section>
}
