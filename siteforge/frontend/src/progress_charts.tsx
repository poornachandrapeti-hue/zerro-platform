import {useEffect,useState} from 'react';
import {BellRing,Download,History,LineChart as LineChartIcon} from 'lucide-react';
import {api} from './api';
import {CartesianGrid,Line,LineChart,ReferenceDot,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';

const slug=(value:string)=>value.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'');
export function Pill({value}:{value:string}){return <span className={`state-pill state-${slug(value)}`}>{value}</span>}

type Point={period_end:string;planned_percent:number};
type Input={visibility:string;data_date:string;source_freshness:string;planned:Point[];historical_actuals_available:boolean;stages:Record<string,{percent:number|null;status:string}>;actuals:{code:string;name:string;verified_percent:string|null;reported_percent:string|null;accepted_percent:string|null;unit:string|null;scope_quantity:string|null}[];exceptions:string[];publication:{revision:string}|null;measure:string};
const csvCell=(v:unknown)=>'"'+String(v??'').replace(/"/g,'""')+'"';
export function downloadCsv(name:string,rows:(string|number|null|undefined)[][]){
  const csv='\uFEFF'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export function ProgressAnalytics({data,project}:{data:Input;project:number}){
  const [showTable,setShowTable]=useState(false);
  const [observations,setObservations]=useState<{data_date:string;verified_percent:number;publication_id:number;baseline_version:string}[]>([]);
  const [alerts,setAlerts]=useState<{type:string;severity:string;message:string}[]>([]);
  const [historyNote,setHistoryNote]=useState('');
  const [alertRegister,setAlertRegister]=useState<{id:number;type:string;severity:string;message:string;state:string}[]>([]);
  const [warningThreshold,setWarningThreshold]=useState('5');
  const [criticalThreshold,setCriticalThreshold]=useState('10');
  const [alertStatus,setAlertStatus]=useState('');
  const [capturing,setCapturing]=useState(false);
  const publicationId=(data.publication as {id?:number}|null)?.id;
  const loadHistory=()=>{
    if(data.visibility!=='project'){setObservations([]);setAlerts([]);return;}
    void api<{observations:typeof observations}>(`/projects/${project}/progress/history`).then(x=>setObservations(x.observations)).catch(()=>setHistoryNote('Historical observations unavailable or restricted.'));
    void api<{alerts:typeof alerts}>(`/projects/${project}/progress/alerts`).then(x=>setAlerts(x.alerts)).catch(()=>setAlerts([]));
    void api<{items:typeof alertRegister}>(`/projects/${project}/progress/alerts/register`).then(x=>setAlertRegister(x.items)).catch(()=>setAlertRegister([]));
    void api<{warning_pp:number;critical_pp:number}>(`/projects/${project}/progress/alerts/settings`).then(x=>{setWarningThreshold(String(x.warning_pp));setCriticalThreshold(String(x.critical_pp));}).catch(()=>{});
  };
  useEffect(()=>{loadHistory();},[project,data.source_freshness,data.visibility]);
  const capture=async()=>{
    setCapturing(true);setHistoryNote('');
    try{await api(`/projects/${project}/progress/history/capture`,'POST');setHistoryNote('Today’s verified observation captured.');loadHistory();}
    catch(e){setHistoryNote((e as Error).message)}finally{setCapturing(false)}
  };
  const alertAction=async (endpoint:string,method:'POST'|'PUT'='POST',body?:object)=>{
    try { await api(`/projects/${project}/progress/alerts/${endpoint}`,method,body);setAlertStatus('Saved. Alert register refreshed.');loadHistory(); }
    catch(e){setAlertStatus((e as Error).message)}
  };
  const planned=data.planned.filter(p=>Number.isFinite(p.planned_percent)&&p.planned_percent>=0&&p.planned_percent<=100);
  const actual=data.stages.construction?.percent;
  const current=actual!=null&&Number.isFinite(actual)?actual:null;
  const canExport=data.actuals.length>0;
  const exportActivities=()=>downloadCsv(`project-${project}-progress-activities-${data.data_date}.csv`,[
    ['Project','Data date','Baseline','Measurement','Code','Activity','Unit','Scope quantity','Reported %','Verified %','Accepted %'],
    ...data.actuals.map(a=>[project,data.data_date,data.publication?.revision??'N/A',data.measure,a.code,a.name,a.unit,a.scope_quantity,a.reported_percent,a.verified_percent,a.accepted_percent])
  ]);
  const exportTargets=()=>downloadCsv(`project-${project}-approved-targets-${data.data_date}.csv`,[
    ['Project','Baseline','Period end','Cumulative planned %'],...planned.map(x=>[project,data.publication?.revision??'N/A',x.period_end,x.planned_percent])]);
  return <section className="panel">
    <h3 className="section-mark"><LineChartIcon size={18} strokeWidth={2.4}/> Planned vs verified progress</h3>
    <p className="muted">Approved Planning cumulative target curve (percentage) · {data.measure} · Data date {data.data_date} · Baseline {data.publication?.revision??'N/A'}. Source refresh {new Date(data.source_freshness).toLocaleString()}.</p>
    {data.visibility!=='project'?<p className="muted">Project-level target curve withheld for company/discipline-restricted viewers.</p>:planned.length>0?<div style={{width:'100%',height:300,minWidth:0}} role="img" aria-label="Approved cumulative planned progress chart">
      <ResponsiveContainer width="100%" height="100%"><LineChart data={planned} margin={{top:16,right:30,left:0,bottom:12}}>
        <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="period_end" tick={{fontSize:11}}/><YAxis domain={[0,100]} unit="%" tick={{fontSize:11}}/>
        <Tooltip formatter={v=>`${v}%`} /><Line dataKey="planned_percent" name="Approved planned" stroke="#2563eb" strokeWidth={2} dot/>
      </LineChart></ResponsiveContainer></div>:<p className="muted">Approved planned points unavailable for this measurement and scope.</p>}
    {data.visibility==='project' && <>
      <h4 className="section-mark"><History size={16} strokeWidth={2.4}/> Historical actual verified S-curve</h4>
      <p className="muted">Observed values only, captured on their actual recording dates. Values from different approved baselines are not joined into a misleading single curve.</p>
      {observations.filter(o=>o.publication_id===publicationId).length>0?<div style={{width:'100%',height:260}}>
        <ResponsiveContainer width="100%" height="100%"><LineChart data={observations.filter(o=>o.publication_id===publicationId)} margin={{top:12,right:25,bottom:12,left:0}}>
          <CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="data_date"/><YAxis domain={[0,100]} unit="%"/><Tooltip/>
          <Line type="linear" dataKey="verified_percent" name="Captured verified %" stroke="#059669" strokeWidth={2} connectNulls={false}/>
        </LineChart></ResponsiveContainer>
      </div>:<p className="muted">No verified historical observations captured for this approved baseline yet.</p>}
      <div className="toolbar"><button type="button" className="tone-submit" disabled={capturing||current==null||data.exceptions.length>0} onClick={capture}>{capturing?'Capturing…':'Capture verified observation (Planning manager)'}</button></div>
      {historyNote&&<p className="note-card" role="status">{historyNote}</p>}
      <h4 className="section-mark"><BellRing size={16} strokeWidth={2.4}/> Progress alert indicators</h4>
      <p className="muted">Configurable threshold warnings and on-demand alert register. Acknowledgements and escalations are recorded, but no email, scheduled checks or recipient delivery are enabled.</p>
      {alerts.length? <div className="mp-table-wrap"><table className="mp-table"><tbody>{alerts.map((a,i)=><tr key={i}><td>{a.type.replace(/_/g,' ')}</td><td><Pill value={a.severity}/></td><td>{a.message}</td></tr>)}</tbody></table></div>:<p className="note-card note-good">No current progress warnings returned.</p>}
      <div className="toolbar" style={{flexWrap:'wrap',alignItems:'center'}}>
        <label>Warning gap (pp) <input style={{width:74}} type="number" min="0.1" max="100" step="0.5" value={warningThreshold} onChange={e=>setWarningThreshold(e.target.value)}/></label>
        <label>Critical gap (pp) <input style={{width:74}} type="number" min="0.1" max="100" step="0.5" value={criticalThreshold} onChange={e=>setCriticalThreshold(e.target.value)}/></label>
        <button type="button" className="tone-note" onClick={()=>void alertAction('settings','PUT',{warning_pp:Number(warningThreshold),critical_pp:Number(criticalThreshold)})}>Save thresholds (Planning manager)</button>
        <button type="button" className="tone-submit" onClick={()=>void alertAction('evaluate')}>Evaluate and record alerts</button>
      </div>
      {alertStatus&&<p className="note-card" role="status">{alertStatus}</p>}
      <h4>Recorded alert register</h4>
      {alertRegister.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Type</th><th>Severity</th><th>Message</th><th>Status</th><th>Actions</th></tr></thead><tbody>{alertRegister.map(item=><tr key={item.id}><td>{item.type.replace(/_/g,' ')}</td><td><Pill value={item.severity}/></td><td>{item.message}</td><td><Pill value={item.state}/></td><td><div className="fin-actions"><button type="button" className="tone-approve" disabled={item.state!=='Open'} onClick={()=>void alertAction(`register/${item.id}/acknowledge`)}>Acknowledge</button><button type="button" className="tone-return" disabled={item.state==='Escalated'} onClick={()=>void alertAction(`register/${item.id}/escalate`)}>Escalate</button></div></td></tr>)}</tbody></table></div>:<p className="muted">No evaluated alerts in the register yet.</p>}
    </>}
    <p className="note-card">Current verified construction: <strong>{current==null?'N/A':`${current.toFixed(2)}%`}</strong> as of {data.data_date}. This is a single current observation, not a historical actual S-curve. Historical observations appear above only after explicitly captured, validated source measurements.</p>
    <div className="toolbar" style={{flexWrap:'wrap'}}>
      <button type="button" onClick={()=>setShowTable(x=>!x)}>{showTable?'Hide':'Show'} approved target values</button>
      {data.visibility==='project'&&<button type="button" className="tone-note" disabled={!planned.length} onClick={exportTargets}><Download size={14}/> Export planned targets CSV</button>}
      <button type="button" className="tone-note" disabled={!canExport} onClick={exportActivities}><Download size={14}/> Export visible activities CSV</button>
    </div>
    {showTable&&<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Period ending</th><th>Approved planned %</th></tr></thead><tbody>{data.visibility==='project'?planned.map(p=><tr key={p.period_end}><td>{p.period_end}</td><td>{p.planned_percent.toFixed(2)}%</td></tr>):<tr><td colSpan={2}>Restricted</td></tr>}</tbody></table></div>}
    <p className="muted">CSV exports contain only records returned under current server permissions. No missing value is treated as 0 and no billed or paid amount is used as physical progress.</p>
  </section>;
}
