import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { BadgeCheck, BellRing, CalendarDays, CalendarRange, ClipboardList, Cog, FileSpreadsheet, Gauge, Layers, LifeBuoy, ListChecks, ListTodo, Plus, RefreshCw, Search, Timer, TrendingUp, Users, UsersRound, Waypoints } from 'lucide-react';
import { api } from './api';
import type { Project, Page, Session } from './types';

type WBS = {id:number;code:string;name:string;parent_id:number|null;active:boolean};
type Calendar = {id:number;code:string;name:string;timezone:string;working_days:number[];shift_start:string;shift_end:string;version:number};
type Schedule = {id:number;name:string;kind:string;version:string;data_date:string;status:string;calendar_id:number};
type Activity = {id:number;code:string;name:string;activity_type:string;wbs_id:number;duration_hours:number|null;planned_start:string|null;planned_finish:string|null};
const today = new Date().toISOString().slice(0,10);
type Tab = 'wbs'|'calendars'|'schedules'|'activities'|'gantt'|'approvals'|'progress'|'curves'|'lookahead'|'resources'|'recovery'|'alerts'|'reports'|'forecast'|'allocations'|'equipment'|'partner-reviews';
const TABS: {key:Tab;label:string;icon:LucideIcon;tone:string}[] = [
  {key:'wbs',label:'WBS',icon:Layers,tone:'tone-pwbs'},
  {key:'calendars',label:'Calendars',icon:CalendarDays,tone:'tone-pcal'},
  {key:'schedules',label:'Schedules',icon:ListTodo,tone:'tone-psched'},
  {key:'activities',label:'Activities',icon:ListChecks,tone:'tone-pact'},
  {key:'gantt',label:'Gantt & CPM',icon:Waypoints,tone:'tone-pgantt'},
  {key:'approvals',label:'Baselines & Approvals',icon:BadgeCheck,tone:'tone-pappr'},
  {key:'progress',label:'Actual Progress',icon:TrendingUp,tone:'tone-pprog'},
  {key:'curves',label:'S-Curves',icon:Gauge,tone:'tone-pcurve'},
  {key:'lookahead',label:'Look-Ahead',icon:CalendarRange,tone:'tone-plook'},
  {key:'resources',label:'Resources',icon:UsersRound,tone:'tone-pres'},
  {key:'recovery',label:'Recovery',icon:LifeBuoy,tone:'tone-precov'},
  {key:'alerts',label:'Alerts',icon:BellRing,tone:'tone-palert'},
  {key:'reports',label:'Reports & Imports',icon:FileSpreadsheet,tone:'tone-preport'},
  {key:'forecast',label:'Forecast Preview',icon:Timer,tone:'tone-pfore'},
  {key:'allocations',label:'Resource Allocations',icon:ClipboardList,tone:'tone-palloc'},
  {key:'equipment',label:'Equipment Register',icon:Cog,tone:'tone-pequip'},
  {key:'partner-reviews',label:'Partner Commitments',icon:Users,tone:'tone-ppartner'},
];
export function PlanningHome({session, initialProjectId}:{session:Session;initialProjectId:number|null}) {
  const [projects,setProjects]=useState<Project[]>([]);
  const [project,setProject]=useState<number|null>(initialProjectId);
  const [tab,setTab]=useState<Tab>('wbs');
  const [query,setQuery]=useState('');
  const [statusFilter,setStatusFilter]=useState('');
  const [wbs,setWbs]=useState<WBS[]>([]);
  const [calendars,setCalendars]=useState<Calendar[]>([]);
  const [schedules,setSchedules]=useState<Schedule[]>([]);
  const [activities,setActivities]=useState<Activity[]>([]);
  const [schedule,setSchedule]=useState<number|null>(null);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [busy,setBusy]=useState(false);
  const canManage=session.user.organization_admin || session.memberships.some(m => m.project_id===project && m.permissions?.includes('planning.manage'));
  const canView=session.user.organization_admin || session.memberships.some(m => m.project_id===project && (m.permissions?.includes('planning.view') || m.permissions?.includes('planning.manage')));
  const base=`/projects/${project}/planning`;
  useEffect(()=>{void api<Page<Project>>('/projects?limit=100').then(x=>setProjects(x.items)).catch(e=>setError(e.message));},[]);
  useEffect(()=>{if(initialProjectId) setProject(initialProjectId);},[initialProjectId]);
  async function reload(){
    if(!project || !canView) return;
    setBusy(true);setError('');
    try{
      const [w,c,s]=await Promise.all([api<WBS[]>(base+'/wbs'),api<Calendar[]>(base+'/calendars'),api<Schedule[]>(base+'/schedules')]);
      setWbs(w);setCalendars(c);setSchedules(s);
      if(schedule && !s.some(x=>x.id===schedule)) setSchedule(null);
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  useEffect(()=>{setWbs([]);setCalendars([]);setSchedules([]);setActivities([]);setSchedule(null);if(project && canView)void reload();},[project,canView]);
  useEffect(()=>{setActivities([]);if(schedule && project && canView)void api<Activity[]>(base+`/schedules/${schedule}/activities`).then(setActivities).catch(e=>setError(e.message));},[schedule,project,canView]);
  async function submit(path:string,body:object){setBusy(true);setError('');setNotice('');try{await api(path,'POST',body);setNotice('Saved successfully');await reload();if(schedule) setActivities(await api<Activity[]>(base+`/schedules/${schedule}/activities`));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  function field(name:string,label:string,required=true,type='text'){return <label>{label}<input name={name} type={type} required={required}/></label>}
  const select=(name:string,label:string,rows:{id:number;name:string}[])=> <label>{label}<select name={name} required><option value="">Select</option>{rows.map(x=><option value={x.id} key={x.id}>{x.name}</option>)}</select></label>;
  const submitForm=(fn:(data:FormData)=>object,path:string)=>(e:React.FormEvent<HTMLFormElement>)=>{e.preventDefault();void submit(path,fn(new FormData(e.currentTarget)));e.currentTarget.reset();};
  const needle=query.trim().toLowerCase();
  const matches=(...values:(string|number|null|undefined)[])=>!needle||values.some(v=>String(v??'').toLowerCase().includes(needle));
  const shownWbs=wbs.filter(x=>matches(x.code,x.name));
  const shownCalendars=calendars.filter(c=>matches(c.code,c.name,c.timezone));
  const shownSchedules=schedules.filter(s=>(!statusFilter||s.status===statusFilter)&&matches(s.name,s.kind,s.version));
  const shownActivities=activities.filter(a=>matches(a.code,a.name,a.activity_type));
  const scheduleStatuses=[...new Set(schedules.map(s=>s.status))];
  const search=(label:string)=><label className="mp-search"><Search size={15}/><input aria-label={label} placeholder={label} value={query} onChange={e=>setQuery(e.target.value)}/></label>;
  return <section className="panel">
    <h2>Planning & Project Controls</h2>
    <p className="muted">WBS, calendars, scheduling, Gantt and baseline approvals</p>
    <div className="toolbar">
      <select aria-label="Project" value={project||''} onChange={e=>setProject(Number(e.target.value)||null)}><option value="">Choose project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}</select>
      <button type="button" onClick={()=>void reload()} disabled={busy||!project}><RefreshCw size={15}/> Refresh</button>
    </div>
    {error && <div role="alert" className="error">{error}</div>}
    {notice && <div role="status" className="success">{notice}</div>}
    {!project ? <p className="muted">Select a project to start planning.</p> : !canView ? <p className="muted">You do not have Planning access for this project.</p> : <>
      <div className="proc-nav">{TABS.map(({key,label,icon:Icon,tone})=><button type="button" key={key} className={`proc-tab ${tone}${tab===key?' is-on':''}`} aria-pressed={tab===key} onClick={()=>{setTab(key);setQuery('');setStatusFilter('');}}><Icon size={14} strokeWidth={2.4}/><span>{label}</span></button>)}</div>
      {tab==='wbs' && <section>
        <div className="hr-toolbar"><h3 className="section-mark"><Layers size={18} strokeWidth={2.4}/> Work Breakdown Structure</h3>{search('Search WBS code or name')}</div>
        {canManage && <form className="contact-form plan-form" onSubmit={submitForm(f=>({code:String(f.get('code')),name:String(f.get('name')),parent_id:Number(f.get('parent_id'))||null}),base+'/wbs')}>{field('code','WBS code')}{field('name','WBS name')}<label>Parent WBS<select name="parent_id"><option value="">Root</option>{wbs.map(x=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label><button className="primary" disabled={busy}><Plus size={14}/> Add WBS</button></form>}
        {shownWbs.length ? <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Code</th><th>Name</th><th>Parent</th><th>Status</th></tr></thead><tbody>{shownWbs.map(x=><tr key={x.id}><td>{x.code}</td><td>{x.name}</td><td>{wbs.find(y=>y.id===x.parent_id)?.code||'—'}</td><td>{x.active?'Active':'Inactive'}</td></tr>)}</tbody></table></div> : <p className="muted">{wbs.length?'No WBS node matches this search.':'No WBS nodes yet.'}</p>}
      </section>}
      {tab==='calendars' && <section>
        <div className="hr-toolbar"><h3 className="section-mark"><CalendarDays size={18} strokeWidth={2.4}/> Working Calendars</h3>{search('Search calendar code, name or timezone')}</div>
        {canManage && <form className="contact-form plan-form" onSubmit={submitForm(f=>({code:String(f.get('code')),name:String(f.get('name')),timezone:String(f.get('timezone')),working_days:[0,1,2,3,4,5],shift_start:String(f.get('shift_start')),shift_end:String(f.get('shift_end')),holidays:[]}),base+'/calendars')}>{field('code','Calendar code')}{field('name','Calendar name')}<label>Timezone<input name="timezone" defaultValue={projects.find(p=>p.id===project)?.timezone||'Asia/Kolkata'}/></label><label>Shift start<input name="shift_start" type="time" defaultValue="08:00"/></label><label>Shift end<input name="shift_end" type="time" defaultValue="17:00"/></label><button className="primary" disabled={busy}><Plus size={14}/> Add calendar</button></form>}
        <p className="muted">Initial calendar form uses Monday–Saturday; full holiday, shift and calendar-version editing is a later milestone.</p>
        {shownCalendars.length ? <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Code</th><th>Name</th><th>Timezone</th><th>Shift</th><th>Version</th></tr></thead><tbody>{shownCalendars.map(c=><tr key={c.id}><td>{c.code}</td><td>{c.name}</td><td>{c.timezone}</td><td>{c.shift_start}–{c.shift_end}</td><td>v{c.version}</td></tr>)}</tbody></table></div> : <p className="muted">{calendars.length?'No calendar matches this search.':'No calendars yet.'}</p>}
      </section>}
      {tab==='schedules' && <section>
        <div className="hr-toolbar"><h3 className="section-mark"><ListTodo size={18} strokeWidth={2.4}/> Schedule Register</h3>{search('Search schedule name, type or version')}<select aria-label="Filter by status" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option value="">All statuses</option>{scheduleStatuses.map(s=><option key={s} value={s}>{s}</option>)}</select></div>
        {canManage && <form className="contact-form plan-form" onSubmit={submitForm(f=>({name:String(f.get('name')),kind:String(f.get('kind')),version:String(f.get('version')),data_date:String(f.get('data_date')),calendar_id:Number(f.get('calendar_id'))}),base+'/schedules')}>{field('name','Schedule name')}<label>Type<select name="kind">{['Integrated','Detailed','Recovery','Scenario'].map(x=><option key={x}>{x}</option>)}</select></label>{field('version','Version')}<label>Data date<input type="date" name="data_date" required defaultValue={today}/></label>{select('calendar_id','Calendar',calendars)}<button className="primary" disabled={busy||!calendars.length}><Plus size={14}/> Create draft</button></form>}
        {shownSchedules.length ? <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Name</th><th>Type</th><th>Version</th><th>Data Date</th><th>Status</th></tr></thead><tbody>{shownSchedules.map(s=><tr key={s.id}><td>{s.name}</td><td>{s.kind}</td><td>{s.version}</td><td>{s.data_date}</td><td>{s.status}</td></tr>)}</tbody></table></div> : <p className="muted">{schedules.length?'No schedule matches these filters.':'No schedules yet.'}</p>}
      </section>}
      {tab==='activities' && <section>
        <div className="hr-toolbar"><h3 className="section-mark"><ListChecks size={18} strokeWidth={2.4}/> Schedule Activities</h3><select aria-label="Schedule" value={schedule||''} onChange={e=>setSchedule(Number(e.target.value)||null)}><option value="">Choose a schedule</option>{schedules.map(s=><option value={s.id} key={s.id}>{s.name} · {s.version} ({s.status})</option>)}</select>{search('Search activity code, name or type')}</div>
        {canManage && schedule && schedules.find(s=>s.id===schedule)?.status==='Draft' && <form className="contact-form plan-form" onSubmit={submitForm(f=>({code:String(f.get('code')),name:String(f.get('name')),wbs_id:Number(f.get('wbs_id')),calendar_id:Number(f.get('calendar_id')),company_id:Number(f.get('company_id')),activity_type:String(f.get('activity_type')),duration_hours:Number(f.get('duration_hours'))||null,progress_method:'Quantity',source_type:String(f.get('source_id')||'').trim()?'construction_activity':null,source_id:String(f.get('source_id')||'').trim()||null}),base+`/schedules/${schedule}/activities`)}>{field('code','Activity code')}{field('name','Activity name')}{select('wbs_id','WBS',wbs)}{select('calendar_id','Calendar',calendars)}{field('company_id','Participating company ID',true,'number')}<label>Type<select name="activity_type"><option>Task</option><option>Milestone</option></select></label>{field('duration_hours','Duration (hours)',false,'number')}{field('source_id','Construction Activity ID (optional)',false,'number')}<button className="primary" disabled={busy}><Plus size={14}/> Add activity</button></form>}
        {!schedule ? <p className="muted">Choose a schedule to see its activities.</p> : shownActivities.length ? <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Code</th><th>Name</th><th>Type</th><th>WBS</th><th>Duration</th></tr></thead><tbody>{shownActivities.map(a=><tr key={a.id}><td>{a.code}</td><td>{a.name}</td><td>{a.activity_type}</td><td>{wbs.find(w=>w.id===a.wbs_id)?.code||a.wbs_id}</td><td>{a.duration_hours??'—'}</td></tr>)}</tbody></table></div> : <p className="muted">{activities.length?'No activity matches this search.':'No activities in this schedule yet.'}</p>}
      </section>}
      {tab==='approvals' && <PlanningApprovals base={base} schedules={schedules} canManage={canManage} isAdmin={session.user.organization_admin} onChange={reload}/> }
      {tab==='lookahead' && <PlanningLookahead base={base} canManage={canManage} schedules={schedules} activities={activities} schedule={schedule} setSchedule={setSchedule}/>}
      {tab==='partner-reviews' && <PartnerCommitmentReviews projectId={project} canManage={canManage}/> }
      {tab==='equipment' && <PlanningEquipment base={base} canManage={canManage}/> }
      {tab==='allocations' && <PlanningAllocations base={base} schedules={schedules} canManage={canManage}/> }
      {tab==='resources' && <PlanningResources base={base} schedules={schedules} activities={activities} canManage={canManage} schedule={schedule} setSchedule={setSchedule}/>}
      {tab==='reports' && <PlanningReports base={base} canManage={canManage} schedules={schedules}/> }
      {tab==='alerts' && <PlanningAlerts base={base} canManage={canManage} isAdmin={session.user.organization_admin} userId={session.user.id}/>}
      {tab==='recovery' && <PlanningRecovery base={base} schedules={schedules} canManage={canManage} isAdmin={session.user.organization_admin}/>}
      {tab==='curves' && <PlanningCurves base={base} canManage={canManage}/> }
      {tab==='progress' && <PlanningActualProgress base={base} schedule={schedule} setSchedule={setSchedule} schedules={schedules}/> }
      {tab==='forecast' && <PlanningForecast base={base} schedules={schedules} canManage={canManage}/> }
      {tab==='gantt' && <PlanningGantt base={base} schedule={schedule} setSchedule={setSchedule} schedules={schedules} canManage={canManage}/> }
      <p className="muted">Draft activity dates are input references, not calculated critical-path dates. Approved baseline revisions remain controlled by the separate approval API. No source actuals are manually changed here.</p>
    </>}
  </section>;
}


type CPMActivity = {id:number;code:string;name:string;activity_type:string;duration_hours:number;start:string;finish:string;total_float_hours:number;critical:boolean};
type Dep = {id:number;predecessor_id:number;successor_id:number;relation:string;lag_hours:number};
type CPM = {activities:CPMActivity[];dependencies:Dep[];project_finish:string|null;data_date:string;calculation_basis:string};
function PlanningGantt({base,schedule,setSchedule,schedules,canManage}:{base:string;schedule:number|null;setSchedule:(id:number|null)=>void;schedules:Schedule[];canManage:boolean}) {
  const [result,setResult]=useState<CPM|null>(null);
  const [err,setErr]=useState('');
  const [busy,setBusy]=useState(false);
  const draft=schedules.find(x=>x.id===schedule)?.status==='Draft';
  const endpoint=base+`/schedules/${schedule}`;
  async function refresh(){if(!schedule)return;setBusy(true);setErr('');setResult(null);try{setResult(await api<CPM>(endpoint+'/calculate'));}catch(e){setErr((e as Error).message);}finally{setBusy(false);}}
  useEffect(()=>{setResult(null);setErr('');if(schedule)void refresh();},[schedule,base]);
  async function add(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const data=new FormData(form);setErr('');setBusy(true);try{
    await api(endpoint+'/dependencies','POST',{predecessor_id:Number(data.get('predecessor_id')),successor_id:Number(data.get('successor_id')),relation:String(data.get('relation')),lag_hours:Number(data.get('lag_hours')||0)});
    form.reset();await refresh();
  }catch(ex){setErr((ex as Error).message);}finally{setBusy(false);}}
  async function remove(id:number){setBusy(true);setErr('');try{await api(endpoint+`/dependencies/${id}`,'DELETE');await refresh();}catch(ex){setErr((ex as Error).message);}finally{setBusy(false);}}
  const list=result?.activities||[];
  const startMs=list.length?Math.min(...list.map(a=>new Date(a.start).getTime())):0;
  const endMs=list.length?Math.max(...list.map(a=>new Date(a.finish).getTime())):0;
  const range=Math.max(1,endMs-startMs);
  const style:React.CSSProperties={background:'#fff',border:'1px solid #dce4ed',borderRadius:12,padding:18,marginBottom:16};
  return <section style={style}>
    <h2 style={{marginTop:0}}>Scheduling Engine & Gantt</h2>
    <p style={{color:'#52657d'}}>Draft CPM dates from assigned working calendars, dependencies and nonnegative lag. This is a calculation preview, not an approved baseline.</p>
    <div style={{display:'flex',gap:12,alignItems:'center',flexWrap:'wrap',marginBottom:14}}><label>Schedule <select value={schedule||''} onChange={e=>setSchedule(Number(e.target.value)||null)}><option value="">Choose schedule</option>{schedules.map(s=><option key={s.id} value={s.id}>{s.name} · {s.version} ({s.status})</option>)}</select></label><button type="button" disabled={!schedule||busy} onClick={()=>void refresh()}><RefreshCw size={14}/> Recalculate</button></div>
    {err&&<p role="alert" style={{color:'#9b2c20',background:'#fff0ed',padding:10,borderRadius:8}}>{err}</p>}
    {schedule&&<>
      {canManage&&draft&&list.length>1&&<form onSubmit={add} style={{display:'flex',gap:9,flexWrap:'wrap',alignItems:'end',background:'#f3f7fb',padding:12,borderRadius:9}}>
        <label>Predecessor<select name="predecessor_id" required>{list.map(a=><option value={a.id} key={a.id}>{a.code}</option>)}</select></label>
        <label>Successor<select name="successor_id" required>{list.map(a=><option value={a.id} key={a.id}>{a.code}</option>)}</select></label>
        <label>Relationship<select name="relation">{['FS','SS','FF','SF'].map(r=><option key={r}>{r}</option>)}</select></label>
        <label>Lag hours<input name="lag_hours" type="number" min="0" defaultValue="0" style={{width:85}}/></label>
        <button disabled={busy} type="submit"><Plus size={14}/> Add dependency</button>
      </form>}
      <div style={{marginTop:16,overflowX:'auto'}}>
        <div style={{minWidth:680}}>
          <div style={{display:'grid',gridTemplateColumns:'230px 1fr 75px',gap:12,fontWeight:700,fontSize:13,padding:'8px 0',borderBottom:'1px solid #dde6ef'}}><span>Activity</span><span>Calculated timeline · {result?.data_date||'—'} data date</span><span>Float (h)</span></div>
          {list.map(a=>{const left=((new Date(a.start).getTime()-startMs)/range)*100;const width=Math.max(a.activity_type==='Milestone'?0.6:1,((new Date(a.finish).getTime()-new Date(a.start).getTime())/range)*100);return <div key={a.id} style={{display:'grid',gridTemplateColumns:'230px 1fr 75px',gap:12,alignItems:'center',padding:'10px 0',borderBottom:'1px solid #edf0f4'}}>
            <span style={{fontSize:12}}><strong>{a.code}</strong> {a.name}<span style={{display:'block',color:'#5c6d80'}}>{a.start.slice(0,16)} → {a.finish.slice(0,16)}</span></span>
            <div style={{height:23,position:'relative',borderRadius:4,background:'repeating-linear-gradient(90deg,#f6f8fb,#f6f8fb 1px,#e9eff5 2px,#f6f8fb 10%)'}} title={a.start+' → '+a.finish}>
              <div style={{position:'absolute',left:`${left}%`,width:`${Math.min(width,100-left)}%`,height:16,top:3,background:a.critical?'#c05c42':'#317b9b',borderRadius:a.activity_type==='Milestone'?0:4,transform:a.activity_type==='Milestone'?'rotate(45deg) scale(.65)':'none'}}/>
            </div><span style={{fontSize:12,fontWeight:a.critical?700:400,color:a.critical?'#b34c36':'#43566b'}}>{a.critical?'Critical':a.total_float_hours}</span>
          </div>})}
          {!busy&&!list.length&&<p>No schedule activities or calculation available.</p>}
        </div>
      </div>
      <h3>Dependencies</h3>
      {(result?.dependencies||[]).map(d=><div key={d.id} style={{display:'flex',gap:10,alignItems:'center',padding:'6px 0',borderBottom:'1px solid #eef2f5'}}><span>{list.find(a=>a.id===d.predecessor_id)?.code} → {list.find(a=>a.id===d.successor_id)?.code} · {d.relation} · {d.lag_hours}h lag</span>{canManage&&draft&&<button type="button" disabled={busy} onClick={()=>void remove(d.id)}>Remove</button>}</div>)}
      {result&&<p style={{fontSize:12,color:'#607184'}}>Calculated finish: {result.project_finish?.replace('T',' ')||'—'}. Critical means zero calculated total float, not merely overdue. Calendar-time and resource constraints are not resource-leveled; verify before publication.</p>}
    </>}
  </section>;
}


type Publication = {id:number;schedule_id:number;revision:string;status:string;reason:string;submitted_by:number;submitted_at:string;reviewed_by:number|null;decision_note:string|null;is_current:boolean};
function PlanningApprovals({base,schedules,canManage,isAdmin,onChange}:{base:string;schedules:Schedule[];canManage:boolean;isAdmin:boolean;onChange:()=>Promise<void>}) {
  const [rows,setRows]=useState<Publication[]>([]);
  const [err,setErr]=useState('');
  const [busy,setBusy]=useState(false);
  const [revision,setRevision]=useState('');
  const [reason,setReason]=useState('');
  const [scheduleId,setScheduleId]=useState('');
  const [note,setNote]=useState('');
  async function load(){try{setRows(await api<Publication[]>(base+'/publications'));}catch(e){setErr((e as Error).message);}}
  useEffect(()=>{setRows([]);setErr('');void load();},[base]);
  async function action(path:string,body:object){setBusy(true);setErr('');try{await api(path,'POST',body);await load();await onChange();}catch(e){setErr((e as Error).message);}finally{setBusy(false);}}
  return <section style={{background:'#fff',padding:20,border:'1px solid #dce4ed',borderRadius:12}}>
    <h2>Schedule Baselines & Approvals</h2>
    <p style={{color:'#52657d'}}>Submission freezes a calculated snapshot. A different organization administrator reviews and publishes it. Approved records are read-only.</p>
    {err&&<p role="alert" style={{color:'#b42318'}}>{err}</p>}
    {canManage&&<form onSubmit={e=>{e.preventDefault();void action(base+`/schedules/${scheduleId}/publications`,{revision,reason});}} style={{display:'flex',gap:10,flexWrap:'wrap',alignItems:'end',marginBottom:20}}>
      <label>Draft schedule <select required value={scheduleId} onChange={e=>setScheduleId(e.target.value)}><option value="">Select draft</option>{schedules.filter(s=>s.status==='Draft'&&s.kind!=='Scenario').map(s=><option value={s.id} key={s.id}>{s.name} · {s.version}</option>)}</select></label>
      <label>Revision <input required value={revision} maxLength={80} onChange={e=>setRevision(e.target.value)} placeholder="BL-001"/></label>
      <label>Submission reason <input required minLength={8} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Initial project baseline"/></label>
      <button disabled={busy||!scheduleId}>Submit for review</button>
    </form>}
    {isAdmin&&<label style={{display:'block',marginBottom:12}}>Review decision note <input value={note} minLength={5} onChange={e=>setNote(e.target.value)} placeholder="Approval or return reason" style={{marginLeft:8,minWidth:260}}/></label>}
    <div style={{overflowX:'auto'}}><table style={{width:'100%'}}><thead><tr><th>Revision</th><th>Schedule</th><th>Status</th><th>Current</th><th>Submitted</th><th>Decision</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.revision}</td><td>{schedules.find(x=>x.id===r.schedule_id)?.name||r.schedule_id}</td><td>{r.status}</td><td>{r.is_current?'Yes':'—'}</td><td>{r.submitted_at?.slice(0,10)}</td><td>{isAdmin&&r.status==='Pending Review'?<span style={{display:'flex',gap:8}}><button disabled={busy||note.trim().length<5} onClick={()=>void action(base+`/publications/${r.id}/approve`,{note})}>Approve</button><button disabled={busy||note.trim().length<5} onClick={()=>void action(base+`/publications/${r.id}/return`,{note})}>Return</button></span>:r.decision_note||'—'}</td></tr>)}</tbody></table></div>
    {!rows.length&&<p>No schedule publications yet.</p>}
    <button type="button" disabled={busy} onClick={()=>void load()}>Refresh publications</button>
  </section>;
}


type LiveMeasure = {method:string;scope_quantity:string|null;unit:string;reported_quantity:string|null;verified_quantity:string|null;accepted_quantity:string|null;reported_percent:string|null;verified_percent:string|null;accepted_percent:string|null};
type LiveRow = {activity_id:number;activity_code:string;activity_name:string;link_status:string;source:{construction_activity_id:number;package_id:number}|null;measurement:LiveMeasure|null};
type LiveProgress = {schedule_id:number;schedule_version:string;data_date:string;retrieved_at:string;basis:string;actuals_as_of_data_date:boolean;planned_curve_available:boolean;historical_s_curve_available:boolean;rollup_percent:null;link_counts:Record<string,number>;activities:LiveRow[]};
function PlanningActualProgress({base,schedule,setSchedule,schedules}:{base:string;schedule:number|null;setSchedule:(value:number|null)=>void;schedules:Schedule[]}){
  const [data,setData]=useState<LiveProgress|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{
    let alive=true;
    setData(null);setError('');
    if(!schedule)return;
    setLoading(true);
    void api<LiveProgress>(base+`/schedules/${schedule}/actual-progress`).then(d=>{if(alive)setData(d);}).catch(e=>{if(alive)setError((e as Error).message);}).finally(()=>{if(alive)setLoading(false);});
    return()=>{alive=false;};
  },[base,schedule]);
  const card:React.CSSProperties={background:'white',border:'1px solid #dce4ed',borderRadius:12,padding:18,marginBottom:16};
  return <section style={card}>
    <h2>Execution Actuals · Source Verified</h2>
    <p style={{color:'#52657d'}}>Read-only Construction measurements linked by explicit source type and activity ID. Reported, verified and QA accepted values are separate.</p>
    <label>Schedule <select value={schedule||''} onChange={e=>setSchedule(Number(e.target.value)||null)}><option value="">Choose schedule</option>{schedules.map(s=><option value={s.id} key={s.id}>{s.name} · {s.version}</option>)}</select></label>
    {loading&&<p>Loading current source measures…</p>}
    {error&&<p role="alert" style={{color:'#a53025'}}>{error}</p>}
    {data&&<>
      <p style={{color:'#52657d',fontSize:13}}>Schedule version: {data.schedule_version} · Reporting data date: {data.data_date} · Source read: {data.retrieved_at}</p>
      <p style={{background:'#fff8e8',padding:12,borderRadius:8,fontSize:13}}>{data.basis}. This tab displays current measures only. Use S-Curves for separately registered approved targets and point-in-time verified captures; no combined percentage is inferred here.</p>
      <div style={{display:'flex',gap:12,flexWrap:'wrap',margin:'14px 0'}}>{Object.entries(data.link_counts).map(([k,v])=><span key={k} style={{background:'#eff4f8',padding:'7px 11px',borderRadius:8,fontSize:13}}>{k.replaceAll('_',' ')}: <strong>{v}</strong></span>)}</div>
      <div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse',minWidth:780,fontSize:13}}><thead><tr>{['Activity','Source status','Method / Unit','Reported','Verified','QA Accepted','Verified %'].map(x=><th key={x} style={{padding:9,textAlign:'left',borderBottom:'1px solid #dae3eb'}}>{x}</th>)}</tr></thead><tbody>{data.activities.map(r=><tr key={r.activity_id}><td style={{padding:9,borderBottom:'1px solid #edf1f5'}}><strong>{r.activity_code}</strong><div>{r.activity_name}</div></td><td>{r.link_status.replaceAll('_',' ')}</td><td>{r.measurement ? `${r.measurement.method} / ${r.measurement.unit||'weight'}`:'—'}</td><td>{r.measurement?.reported_quantity??'—'}</td><td>{r.measurement?.verified_quantity??'—'}</td><td>{r.measurement?.accepted_quantity??'—'}</td><td>{r.measurement?.verified_percent!=null?`${r.measurement.verified_percent}%`:'—'}</td></tr>)}</tbody></table></div>
      {!data.activities.length&&<p>No activities are registered for this schedule.</p>}
      <p style={{fontSize:12,color:'#52657d'}}>Mapping uses Planning Activity source_type = construction_activity and source_id = Construction Activity ID. Mapping editing, weighted rollups and historical snapshots are upcoming work.</p>
    </>}
  </section>;
}


type CurveResult={publication_id:number;revision:string;plan_status:string;observed_status:string;disclaimer:string;planned:{date:string;planned_percent:number}[];observed:{date:string;verified_percent:number|null;measured_weight_basis_points:number;capture_id:number}[]};
function PlanningCurves({base,canManage}:{base:string;canManage:boolean}){
  const [publications,setPublications]=useState<Publication[]>([]);
  const [publication,setPublication]=useState<number|null>(null);
  const [data,setData]=useState<CurveResult|null>(null);
  const [err,setErr]=useState('');
  const [busy,setBusy]=useState(false);
  const [targets,setTargets]=useState('');
  useEffect(()=>{let mounted=true;setPublications([]);setPublication(null);void api<Publication[]>(base+'/publications').then(r=>{if(mounted)setPublications(r.filter(x=>x.status==='Approved'));}).catch(e=>{if(mounted)setErr((e as Error).message);});return()=>{mounted=false;};},[base]);
  async function reload(id:number){setBusy(true);setData(null);setErr('');try{setData(await api<CurveResult>(base+`/publications/${id}/progress-curves`));}catch(e){setErr((e as Error).message);}finally{setBusy(false);}}
  async function importTargets(){if(!publication)return;setBusy(true);setErr('');try{const parsed=JSON.parse(targets);if(!Array.isArray(parsed))throw Error('Enter a JSON array of targets');await api(base+`/publications/${publication}/period-targets`,'POST',{targets:parsed});await reload(publication);}catch(e){setErr((e as Error).message);}finally{setBusy(false);}}
  async function capture(){if(!publication)return;setBusy(true);setErr('');try{await api(base+`/publications/${publication}/capture-progress`,'POST',{});await reload(publication);}catch(e){setErr((e as Error).message);}finally{setBusy(false);}}
  const dated=[...(data?.planned||[]).map(x=>({time:new Date(x.date).getTime(),percent:x.planned_percent,series:'plan'})),...(data?.observed||[]).filter(x=>x.verified_percent!==null).map(x=>({time:new Date(x.date).getTime(),percent:x.verified_percent as number,series:'actual'}))];
  const min=dated.length?Math.min(...dated.map(x=>x.time)):0;const max=dated.length?Math.max(...dated.map(x=>x.time)):0;
  const x=(time:number)=>44+((time-min)/Math.max(86400000,max-min))*710;
  const y=(percent:number)=>230-percent*1.9;
  const pathFor=(series:string)=>dated.filter(x=>x.series===series).sort((a,b)=>a.time-b.time).map((p,i)=>`${i===0?'M':'L'} ${x(p.time)} ${y(p.percent)}`).join(' ');
  return <section style={{background:'#fff',padding:20,border:'1px solid #dce4ed',borderRadius:12}}>
    <h2>Approved Targets & Progress Captures</h2>
    <p style={{color:'#52657d'}}>Cumulative approved targets are shown separately from verified source measurements captured on a known date. Missing measurements are not interpolated.</p>
    <label>Approved baseline <select value={publication||''} onChange={e=>{const id=Number(e.target.value)||null;setPublication(id);setData(null);if(id)void reload(id);}}><option value="">Choose approved revision</option>{publications.map(p=><option value={p.id} key={p.id}>{p.revision} · schedule {p.schedule_id}{p.is_current?' (current)':''}</option>)}</select></label>
    {err&&<p role="alert" style={{color:'#a53025'}}>{err}</p>}
    {publication&&<div style={{display:'flex',gap:10,margin:'14px 0'}}><button disabled={busy} onClick={()=>void reload(publication)}>Refresh</button>{canManage&&<button disabled={busy||data?.plan_status!=='approved_explicit_targets'} onClick={()=>void capture()}>Capture verified progress now</button>}</div>}
    {data&&<>
      <p style={{fontSize:13,color:'#54677d'}}>Baseline revision: {data.revision} · Targets: {data.plan_status.replaceAll('_',' ')} · Observations: {data.observed_status.replaceAll('_',' ')}</p>
      <div style={{overflowX:'auto',border:'1px solid #e0e8ef',borderRadius:8,padding:12}}><svg viewBox="0 0 800 270" role="img" aria-label="Planned progress and recorded verified progress percentage" style={{width:'100%',minWidth:480}}>
        {[0,25,50,75,100].map(n=><g key={n}><line x1="44" x2="754" y1={y(n)} y2={y(n)} stroke="#e2eaf1"/><text x="6" y={y(n)+4} fontSize="12" fill="#607184">{n}%</text></g>)}
        {data.planned.length>0&&<path d={pathFor('plan')} fill="none" stroke="#2b7299" strokeWidth="3"/>}
        {data.observed.length>0&&<path d={pathFor('actual')} fill="none" stroke="#b97930" strokeWidth="3"/>}
        {dated.filter(p=>p.series==='actual').map((p,i)=><circle key={i} cx={x(p.time)} cy={y(p.percent)} r="4" fill="#b97930"/>)}
        <text x="45" y="255" fontSize="12" fill="#607184">{min?new Date(min).toLocaleDateString():'No dates'}</text><text x="650" y="255" fontSize="12" fill="#607184">{max?new Date(max).toLocaleDateString():''}</text>
      </svg></div>
      <p style={{fontSize:13}}><span style={{color:'#2b7299'}}>■</span> Approved planned cumulative % &nbsp; <span style={{color:'#b97930'}}>■</span> Verified captured %</p>
      <p style={{fontSize:12,color:'#63758a'}}>{data.disclaimer}</p>
      {data.observed.some(x=>x.verified_percent===null)&&<p style={{background:'#fff5e6',padding:10}}>One or more progress captures have incomplete source coverage; no overall percentage is reported for those dates.</p>}
      <table style={{width:'100%',fontSize:13}}><thead><tr><th>Capture time</th><th>Verified progress</th><th>Weighted coverage</th></tr></thead><tbody>{data.observed.map(x=><tr key={x.capture_id}><td>{x.date}</td><td>{x.verified_percent===null?'Unavailable':`${x.verified_percent.toFixed(2)}%`}</td><td>{(x.measured_weight_basis_points/100).toFixed(2)}%</td></tr>)}</tbody></table>
    </>}
    {canManage&&publication&&data?.plan_status==='not_available'&&<div style={{marginTop:20,borderTop:'1px solid #dae3eb',paddingTop:14}}><h3>Register approved period targets</h3>
      <p style={{fontSize:13}}>Upload explicit activity-level period targets and weights once for this approved revision. All approved leaf activities must be included, and activity weights must total 10,000 basis points. Targets cannot be overwritten after submission.</p>
      <textarea value={targets} onChange={e=>setTargets(e.target.value)} rows={6} style={{width:'100%',fontFamily:'monospace',padding:10}} placeholder={'[{"activity_id":123,"period_end":"2026-11-30","cumulative_percent":50,"weight_basis_points":10000}]'}/>
      <button disabled={busy||!targets.trim()} onClick={()=>void importTargets()}>Validate and freeze targets</button>
    </div>}
  </section>;
}


type Ahead={id:number;code:string;schedule_id:number;horizon:string;start_date:string;end_date:string;status:string};
type LiveReadiness={item_id:number;status:string;source:string;package_id:number|null;release_state?:string;note:string;checks:{type:string;classification:string;state:string;reason:string;owner:string}[]};
type AheadItem={id:number;activity_id:number;target_date:string;target_quantity:number|null;target_unit:string|null;owner_id:number;commitment:string;readiness:string;blocker:string;achieved_quantity:number|null;variance_reason:string};
function PlanningLookahead({base,canManage,schedules,activities,schedule,setSchedule}:{base:string;canManage:boolean;schedules:Schedule[];activities:Activity[];schedule:number|null;setSchedule:(id:number|null)=>void}){
 const [plans,setPlans]=useState<Ahead[]>([]);const [chosen,setChosen]=useState<number|null>(null);const [items,setItems]=useState<AheadItem[]>([]);const [live,setLive]=useState<LiveReadiness[]>([]);const [liveAt,setLiveAt]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 async function reload(){try{setPlans(await api<Ahead[]>(base+'/lookaheads'));}catch(e){setError((e as Error).message);}}
 useEffect(()=>{setChosen(null);setItems([]);setPlans([]);void reload();},[base]);
 useEffect(()=>{setItems([]);setLive([]);setLiveAt('');if(chosen)void api<AheadItem[]>(base+`/lookaheads/${chosen}/items`).then(setItems).catch(e=>setError((e as Error).message));},[base,chosen]);
 async function refreshLive(){if(!chosen)return;setBusy(true);try{const r=await api<{items:LiveReadiness[];retrieved_at:string}>(base+`/lookaheads/${chosen}/live-readiness`);setLive(r.items);setLiveAt(r.retrieved_at);}catch(e){setLive([]);setError((e as Error).message);}finally{setBusy(false);}}
 async function post(path:string,body:object,method:'POST'|'PATCH'='POST'){setBusy(true);setError('');try{await api(path,method,body);await reload();if(chosen)setItems(await api<AheadItem[]>(base+`/lookaheads/${chosen}/items`));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const selected=plans.find(p=>p.id===chosen);
 const inputStyle:React.CSSProperties={padding:9,border:'1px solid #bac8d6',borderRadius:7};
 return <section style={{padding:20,background:'white',border:'1px solid #dce4ed',borderRadius:12}}><h2>Look-Ahead & Workfront Readiness</h2><p>Plan execution targets and commitments. Readiness is advisory; Construction, HSE and QA releases remain authoritative.</p>
 {error&&<p role="alert" style={{color:'#a53025'}}>{error}</p>}
 {canManage&&<form style={{display:'flex',flexWrap:'wrap',gap:10,marginBottom:14}} onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void post(base+'/lookaheads',{code:String(f.get('code')),schedule_id:Number(f.get('schedule_id')),horizon:String(f.get('horizon')),start_date:String(f.get('start_date'))});}}><input name="code" placeholder="Plan code" required style={inputStyle}/><select name="schedule_id" required style={inputStyle} onChange={e=>setSchedule(Number(e.target.value)||null)}><option value="">Schedule</option>{schedules.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select><select name="horizon" style={inputStyle}><option>7-day</option><option>14-day</option><option>monthly</option></select><input name="start_date" type="date" required defaultValue={today} style={inputStyle}/><button disabled={busy}>Create look-ahead</button></form>}
 <label>Look-ahead <select style={inputStyle} value={chosen||''} onChange={e=>{const id=Number(e.target.value)||null;setChosen(id);const p=plans.find(x=>x.id===id);if(p)setSchedule(p.schedule_id);}}><option value="">Select</option>{plans.map(p=><option key={p.id} value={p.id}>{p.code} · {p.horizon} · {p.status} ({p.start_date}–{p.end_date})</option>)}</select></label>
 {selected&&<><p>Window: {selected.start_date} to {selected.end_date} · Status: {selected.status}</p><div style={{marginBottom:12}}><button type="button" disabled={busy} onClick={()=>void refreshLive()}>Refresh source readiness</button> {liveAt&&<small>Checked: {new Date(liveAt).toLocaleString()}</small>}<p style={{fontSize:12,color:'#52677d'}}>Live indicators are advisory only; they do not authorize Construction, Quality or HSE work.</p></div>
 {canManage&&selected.status==='Draft'&&<form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void post(base+`/lookaheads/${chosen}/items`,{activity_id:Number(f.get('activity_id')),target_date:String(f.get('target_date')),target_quantity:f.get('target_quantity')?Number(f.get('target_quantity')):null,target_unit:String(f.get('target_unit')||'')||null,owner_id:Number(f.get('owner_id'))});}} style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:15}}><select name="activity_id" required style={inputStyle}><option value="">Activity</option>{activities.map(a=><option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</select><input type="date" name="target_date" min={selected.start_date} max={selected.end_date} required style={inputStyle}/><input name="target_quantity" type="number" min="0" placeholder="Target quantity" style={inputStyle}/><input name="target_unit" placeholder="Unit e.g. m3" style={inputStyle}/><input name="owner_id" type="number" min="1" required placeholder="Project member user ID" style={inputStyle}/><button disabled={busy}>Add target</button></form>}
 <div style={{overflowX:'auto'}}><table style={{width:'100%',minWidth:800}}><thead><tr><th>Activity</th><th>Target</th><th>Owner</th><th>Manual readiness</th><th>Live source readiness</th><th>Commitment</th><th>Blocker</th><th>Review</th></tr></thead><tbody>{items.map(item=><tr key={item.id}><td>{activities.find(a=>a.id===item.activity_id)?.code||item.activity_id}</td><td>{item.target_date} · {item.target_quantity??'—'} {item.target_unit||''}</td><td>{item.owner_id}</td><td>{item.readiness}</td><td>{(()=>{const r=live.find(x=>x.item_id===item.id);return r?<details><summary>{r.status} ({r.source})</summary><div style={{maxWidth:360,fontSize:12}}>{r.note}{r.checks.map((c,i)=><p key={i}><b>{c.type}: {c.state}</b> — {c.reason}</p>)}</div></details>:'Not checked';})()}</td><td>{item.commitment}</td><td>{item.blocker||'—'}</td><td>{canManage?<button disabled={busy} onClick={()=>{const readiness=window.prompt('Readiness: Unknown, Ready, At Risk, Blocked',item.readiness);if(!readiness)return;const commitment=window.prompt('Commitment: Pending, Committed, Declined, Completed',item.commitment);if(!commitment)return;const blocker=window.prompt('Blocker / missing prerequisite',item.blocker)||'';void post(base+`/lookaheads/${chosen}/items/${item.id}`,{readiness,commitment,blocker,readiness_notes:'',resolution_owner_id:null,resolution_due:null,achieved_quantity:item.achieved_quantity,variance_reason:item.variance_reason},'PATCH');}}>Review</button>:'Read-only'}</td></tr>)}</tbody></table></div>
 {canManage&&selected.status==='Draft'&&<button disabled={busy||items.length===0} onClick={()=>void post(base+`/lookaheads/${chosen}/publish`,{})}>Publish commitments</button>}
 </>}
 </section>;
}


type ResourceDemand={id:number;schedule_id:number;activity_id:number;period_start:string;period_end:string;resource_type:string;resource_name:string;demand_quantity:number;demand_unit:string;confirmed_capacity:number|null;capacity_source:string|null;shortfall:number|null;capacity_status:string};
function PlanningResources({base,schedules,activities,canManage,schedule,setSchedule}:{base:string;schedules:Schedule[];activities:Activity[];canManage:boolean;schedule:number|null;setSchedule:(v:number|null)=>void}){
 const [rows,setRows]=useState<ResourceDemand[]>([]);const [error,setError]=useState('');const [loading,setLoading]=useState(false);
 useEffect(()=>{setRows([]);setError('');if(!schedule)return;void api<ResourceDemand[]>(base+`/resource-demands?schedule_id=${schedule}`).then(setRows).catch(e=>setError(e.message));},[base,schedule]);
 async function save(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!schedule)return;setLoading(true);setError('');const f=new FormData(e.currentTarget);try{await api(base+'/resource-demands','POST',{schedule_id:schedule,activity_id:Number(f.get('activity_id')),period_start:f.get('period_start'),period_end:f.get('period_end'),resource_type:f.get('resource_type'),resource_name:f.get('resource_name'),demand_quantity:Number(f.get('demand_quantity')),demand_unit:f.get('demand_unit'),confirmed_capacity:f.get('confirmed_capacity')!==''?Number(f.get('confirmed_capacity')):null,capacity_source:String(f.get('capacity_source')||'')||null});setRows(await api<ResourceDemand[]>(base+`/resource-demands?schedule_id=${schedule}`));e.currentTarget.reset();}catch(err){setError((err as Error).message);}finally{setLoading(false);}}
 return <section style={{padding:20,background:'#fff',border:'1px solid #dce4ed',borderRadius:12}}><h2>Resource Demand & Capacity</h2><p>Demand is planned here. Capacity values require a traceable source; no HR or Equipment system capacity is inferred.</p><label>Schedule <select value={schedule||''} onChange={e=>setSchedule(Number(e.target.value)||null)}><option value="">Choose schedule</option>{schedules.map(x=><option key={x.id} value={x.id}>{x.name} ({x.version})</option>)}</select></label>{error&&<p role="alert">{error}</p>}
 {canManage&&schedule&&<form onSubmit={save} style={{display:'flex',flexWrap:'wrap',gap:9,margin:'14px 0'}}><select name="activity_id" required><option value="">Activity</option>{activities.map(a=><option key={a.id} value={a.id}>{a.code}</option>)}</select><select name="resource_type"><option>Workforce</option><option>Equipment</option></select><input name="resource_name" placeholder="Trade / equipment type" required/><input name="period_start" type="date" required/><input name="period_end" type="date" required/><input name="demand_quantity" type="number" min="0" placeholder="Demand" required/><select name="demand_unit"><option>headcount</option><option>person-hours</option><option>units</option><option>equipment-hours</option></select><input name="confirmed_capacity" type="number" min="0" placeholder="Confirmed capacity (optional)"/><input name="capacity_source" placeholder="Capacity evidence/reference"/><button disabled={loading}>Add demand</button></form>}
 <div style={{overflowX:'auto'}}><table style={{minWidth:850,width:'100%'}}><thead><tr><th>Resource</th><th>Activity</th><th>Period</th><th>Demand</th><th>Confirmed capacity</th><th>Shortfall</th><th>Source</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.resource_type}: {r.resource_name}</td><td>{activities.find(a=>a.id===r.activity_id)?.code||r.activity_id}</td><td>{r.period_start} → {r.period_end}</td><td>{r.demand_quantity} {r.demand_unit}</td><td>{r.confirmed_capacity??'Unavailable'}</td><td>{r.shortfall??'Unavailable'}</td><td>{r.capacity_source||'Not connected'}</td></tr>)}</tbody></table></div>{!rows.length&&<p>No resource demands recorded.</p>}</section>
}
type RecoveryScenario={id:number;code:string;title:string;reason:string;proposed_changes:string;schedule_impact_days:number|null;required_reviews:string[];status:string};
function PlanningRecovery({base,schedules,canManage,isAdmin}:{base:string;schedules:Schedule[];canManage:boolean;isAdmin:boolean}){
 const [rows,setRows]=useState<RecoveryScenario[]>([]);const [error,setError]=useState('');const [loading,setLoading]=useState(false);
 const [selected,setSelected]=useState<number|null>(null);const [history,setHistory]=useState<{reviews:{id:number;department:string;decision:string;comment:string}[];events:{id:number;action:string;next_status:string;comment:string}[]}|null>(null);
 async function loadHistory(id:number){setSelected(id);setHistory(await api(base+`/recovery-scenarios/${id}/history`));}
 async function decide(id:number,action:string,department?:string){const comment=(action==='return'||action==='review_reject')?(window.prompt('Reason for returning or rejecting')||''):'';if((action==='return'||action==='review_reject')&&!comment.trim())return;setLoading(true);setError('');try{await api(base+`/recovery-scenarios/${id}/decision`,'POST',{action,department:department||null,comment});setRows(await api<RecoveryScenario[]>(base+'/recovery-scenarios'));await loadHistory(id);}catch(e){setError((e as Error).message);}finally{setLoading(false);}}
 useEffect(()=>{setRows([]);setError('');void api<RecoveryScenario[]>(base+'/recovery-scenarios').then(setRows).catch(e=>setError(e.message));},[base]);
 async function save(e:React.FormEvent<HTMLFormElement>){e.preventDefault();setLoading(true);setError('');const f=new FormData(e.currentTarget);try{await api(base+'/recovery-scenarios','POST',{schedule_id:Number(f.get('schedule_id')),code:f.get('code'),title:f.get('title'),reason:f.get('reason'),proposed_changes:f.get('proposed_changes'),schedule_impact_days:f.get('schedule_impact_days')!==''?Number(f.get('schedule_impact_days')):null,resource_impact:String(f.get('resource_impact')||''),cost_impact_reference:String(f.get('cost_impact_reference')||'')||null,required_reviews:Array.from(f.getAll('required_reviews')).map(String)});setRows(await api<RecoveryScenario[]>(base+'/recovery-scenarios'));e.currentTarget.reset();}catch(err){setError((err as Error).message);}finally{setLoading(false);}}
 return <section style={{padding:20,background:'#fff',border:'1px solid #dce4ed',borderRadius:12}}><h2>Recovery Scenarios</h2><p>Draft proposals only; impact days are planner estimates, not CPM results. No schedule publication, baseline change, cost approval or safety override is performed.</p>{error&&<p role="alert">{error}</p>}
 {canManage&&<form onSubmit={save} style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:10,marginBottom:20}}><select name="schedule_id" required><option value="">Schedule</option>{schedules.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select><input name="code" placeholder="Scenario code" required/><input name="title" placeholder="Scenario title" required/><textarea name="reason" placeholder="Reason" required/><textarea name="proposed_changes" placeholder="Proposed recovery actions" required/><input name="schedule_impact_days" type="number" placeholder="Estimated days impact (optional)"/><input name="resource_impact" placeholder="Resource impact"/><input name="cost_impact_reference" placeholder="Cost reference"/><label>Required department reviews <select multiple name="required_reviews" style={{minHeight:105}}><option>Engineering</option><option>Construction</option><option>QA</option><option>HSE</option><option>Contracts</option><option>Financials</option><option>Project Manager</option></select></label><button disabled={loading}>Save draft scenario</button></form>}
 <table style={{width:'100%'}}><thead><tr><th>Code</th><th>Proposal</th><th>Estimated schedule impact</th><th>Status</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.code}</td><td><strong>{r.title}</strong><p>{r.proposed_changes}</p></td><td>{r.schedule_impact_days===null?'Not estimated':`${r.schedule_impact_days} days`}</td><td>{r.status}<div style={{display:"flex",flexWrap:"wrap",gap:5,marginTop:5}}><button type="button" onClick={()=>void loadHistory(r.id)}>History</button>{canManage&&(r.status==='Draft'||r.status==='Returned')&&<button disabled={loading} type="button" onClick={()=>void decide(r.id,'submit')}>Submit</button>}{isAdmin&&r.status==='Pending Review'&&<><button disabled={loading} type="button" onClick={()=>void decide(r.id,'approve')}>Approve proposal</button><button disabled={loading} type="button" onClick={()=>void decide(r.id,'return')}>Return</button>{(r.required_reviews||[]).map(d=><span key={d}><button disabled={loading} type="button" onClick={()=>void decide(r.id,'review_approve',d)}>Approve {d}</button><button disabled={loading} type="button" onClick={()=>void decide(r.id,'review_reject',d)}>Reject {d}</button></span>)}</>}</div></td></tr>)}</tbody></table>{!rows.length&&<p>No recovery scenarios recorded.</p>}{selected!==null&&history&&<aside style={{padding:12,marginTop:12,background:"#f1f5f9"}}><strong>Scenario #{selected} history</strong><ul>{history.events.map(e=><li key={e.id}>{e.action} → {e.next_status} {e.comment}</li>)}{history.reviews.map(r=><li key={`r${r.id}`}>{r.department}: {r.decision} {r.comment}</li>)}</ul><p>Approval is a proposal decision only. It does not change an approved schedule, cost, QA or HSE authorization.</p></aside>}</section>
}


type PlanningAlertRow={id:number;title:string;description:string;trigger_type:string;severity:string;owner_id:number|null;status:string;first_detected_at:string;last_detected_at:string;resolution_note:string};
function PlanningAlerts({base,canManage,isAdmin,userId}:{base:string;canManage:boolean;isAdmin:boolean;userId:number}){
  const [rows,setRows]=useState<PlanningAlertRow[]>([]);
  const [busy,setBusy]=useState(false);const [err,setErr]=useState('');
  async function reload(){try{setErr('');setRows(await api<PlanningAlertRow[]>(base+'/alerts'));}catch(e){setErr((e as Error).message);}}
  useEffect(()=>{setRows([]);void reload();},[base]);
  async function evaluate(){setBusy(true);try{await api(base+'/alerts/evaluate','POST',{});await reload();}catch(e){setErr((e as Error).message);}finally{setBusy(false);}}
  async function decide(row:PlanningAlertRow,action:'acknowledge'|'resolve'){
    const note=action==='resolve'?window.prompt('Resolution note (required)')||'':'';
    if(action==='resolve'&&!note.trim())return;
    setBusy(true);try{await api(base+`/alerts/${row.id}/decision`,'POST',{action,note});await reload();}catch(e){setErr((e as Error).message);}finally{setBusy(false);}
  }
  return <section style={{background:'#fff',padding:20,border:'1px solid #dce4ed',borderRadius:12}}>
    <h2>Planning Alerts & Escalation Register</h2><p>Persistent on-demand alerts for confirmed resource shortfalls, overdue look-ahead blockers and old pending recovery reviews. No automatic notifications are active.</p>
    {canManage&&<button disabled={busy} onClick={()=>void evaluate()}>Evaluate current risks</button>}
    <button disabled={busy} onClick={()=>void reload()} style={{marginLeft:10}}>Refresh</button>
    {err&&<p role="alert" style={{color:'#b42318'}}>{err}</p>}
    <div style={{overflowX:'auto',marginTop:16}}><table style={{width:'100%'}}><thead><tr><th>Alert</th><th>Severity</th><th>Owner ID</th><th>Status</th><th>Last detected</th><th>Action</th></tr></thead><tbody>
    {rows.map(r=><tr key={r.id}><td><strong>{r.title}</strong><p style={{fontSize:12}}>{r.description}</p></td><td>{r.severity}</td><td>{r.owner_id??'Unassigned'}</td><td>{r.status}</td><td>{String(r.last_detected_at).slice(0,16)}</td><td>{canManage&&(isAdmin||r.owner_id===userId)&&r.status!=='Resolved'&&<div style={{display:'flex',gap:6}}>{r.status==='Open'&&<button disabled={busy} onClick={()=>void decide(r,'acknowledge')}>Acknowledge</button>}<button disabled={busy} onClick={()=>void decide(r,'resolve')}>Resolve</button></div>}</td></tr>)}
    </tbody></table></div>{!rows.length&&<p>No recorded planning alerts.</p>}
  </section>;
}


type PlanningOverview={generated_at:string;approved_baseline:{revision:string;id:number}|null;schedules:{id:number;name:string;status:string;version:string;total:number;tasks:number;milestones:number;source_linked:number}[];curves:{planned:{date:string;planned_percent:number}[];observed:{date:string;verified_percent:number|null;measured_weight_basis_points:number}[]}|null;warning:string|null;basis:string};
type ImportPreview={total_rows:number;valid_rows:number;error_count:number;errors:{row:number;activity_code:string;errors:string[]}[];preview_only:boolean;written:number};
function PlanningReports({base,canManage,schedules}:{base:string;canManage:boolean;schedules:Schedule[]}){
  const [report,setReport]=useState<PlanningOverview|null>(null);
  const [err,setErr]=useState('');
  const [schedule,setSchedule]=useState('');
  const [csv,setCsv]=useState('');
  const [excelBase64,setExcelBase64]=useState('');
  const [excelName,setExcelName]=useState('');
  const [excelPreview,setExcelPreview]=useState<ImportPreview & {sha256:string}|null>(null);
  const [excelResult,setExcelResult]=useState('');
  const [bulkKind,setBulkKind]=useState<'dependencies'|'calendars'>('dependencies');
  const [bulkWorkbook,setBulkWorkbook]=useState('');
  const [bulkPreview,setBulkPreview]=useState<ImportPreview & {sha256:string}|null>(null);
  const [bulkStatus,setBulkStatus]=useState('');

  const [preview,setPreview]=useState<ImportPreview|null>(null);
  const [busy,setBusy]=useState(false);
  useEffect(()=>{let live=true;setReport(null);setErr('');void api<PlanningOverview>(base+'/reports/overview').then(r=>{if(live)setReport(r);}).catch(e=>{if(live)setErr((e as Error).message)});return()=>{live=false}},[base]);
  function downloadCsv(filename:string,lines:(string|number|null)[][]){
    const quote=(x:string|number|null)=>'"'+String(x??'').replaceAll('"','""')+'"';
    const text=lines.map(line=>line.map(quote).join(',')).join('\r\n')+'\r\n';
    const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));
    const a=document.createElement('a');a.href=url;a.download=filename;a.click();URL.revokeObjectURL(url);
  }
  async function validate(){if(!schedule||!csv.trim())return;setBusy(true);setErr('');setPreview(null);try{setPreview(await api<ImportPreview>(base+'/imports/activities/preview','POST',{schedule_id:Number(schedule),csv_text:csv}));}catch(e){setErr((e as Error).message)}finally{setBusy(false)}}
  function downloadBase64(filename:string,encoded:string){
    const binary=atob(encoded);const bytes=new Uint8Array(binary.length);
    for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
    const url=URL.createObjectURL(new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}));
    const anchor=document.createElement('a');anchor.href=url;anchor.download=filename;anchor.click();URL.revokeObjectURL(url);
  }
  async function selectExcel(file:File|null){
    setExcelPreview(null);setExcelResult('');setExcelBase64('');setExcelName(file?.name||'');
    if(!file)return;
    if(!file.name.toLowerCase().endsWith('.xlsx')||file.size>2_000_000){setErr('Choose an .xlsx workbook not exceeding 2 MB');return;}
    try{const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
      for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
      setExcelBase64(btoa(binary));setErr('');
    }catch(e){setErr((e as Error).message)}
  }
  async function previewExcel(){if(!schedule||!excelBase64)return;setBusy(true);setErr('');setExcelPreview(null);setExcelResult('');
    try{const result=await api<ImportPreview & {sha256:string}>(base+'/imports/activities/excel-preview','POST',{schedule_id:Number(schedule),workbook_base64:excelBase64});setExcelPreview(result)}
    catch(e){setErr((e as Error).message)}finally{setBusy(false)}
  }
  async function confirmExcel(){if(!schedule||!excelBase64||!excelPreview||excelPreview.error_count)return;
    if(!window.confirm(`Import ${excelPreview.valid_rows} activities into the selected DRAFT schedule?`))return;
    setBusy(true);setErr('');
    try{const result=await api<{written:number}>(base+'/imports/activities/excel-confirm','POST',{schedule_id:Number(schedule),workbook_base64:excelBase64,preview_sha256:excelPreview.sha256});setExcelResult(`${result.written} activities imported`);setExcelPreview(null);setExcelBase64('');}
    catch(e){setErr((e as Error).message);setExcelPreview(null)}finally{setBusy(false)}
  }
  return <section style={{background:'#fff',padding:20,border:'1px solid #dce4ed',borderRadius:12}}>
    <h2>Planning Reports & Activity Import Preview</h2>
    <p>All figures use current authorized project data. Approved targets and verified captures retain separate reporting bases; missing values remain unavailable.</p>
    {err&&<p role="alert" style={{color:'#a53025'}}>{err}</p>}
    {report&&<><p><strong>Approved baseline:</strong> {report.approved_baseline?.revision||'Unavailable'} · <strong>Report generated:</strong> {report.generated_at}</p>
      {report.warning&&<p style={{color:'#8c5519'}}>{report.warning}</p>}
      <table style={{width:'100%',marginBottom:15}}><thead><tr><th>Schedule</th><th>Version</th><th>Status</th><th>Activities</th><th>Source mapped</th></tr></thead><tbody>{report.schedules.map(x=><tr key={x.id}><td>{x.name}</td><td>{x.version}</td><td>{x.status}</td><td>{x.total}</td><td>{x.source_linked}</td></tr>)}</tbody></table>
      <button onClick={()=>downloadCsv('planning-schedules.csv',[['Schedule ID','Schedule','Version','Status','Activities','Tasks','Milestones','Source Mapped'],...report.schedules.map(x=>[x.id,x.name,x.version,x.status,x.total,x.tasks,x.milestones,x.source_linked])])}>Export schedule summary CSV</button>
      {report.curves&&<button style={{marginLeft:10}} onClick={()=>downloadCsv('planning-baseline-curves.csv',[['Record type','Date','Percentage','Measured weight basis points'],...report.curves!.planned.map(x=>['Approved target',x.date,x.planned_percent,'']),...report.curves!.observed.map(x=>['Verified snapshot',x.date,x.verified_percent,x.measured_weight_basis_points])])}>Export planned and actual CSV</button>}
      <p style={{fontSize:12,color:'#64748b'}}>Command Center sync is not included in this reporting release. CSV exports reflect only the authorized project returned by this API.</p></>}
    <hr/><h3>Excel (.xlsx) activity import</h3>
    <p>Download the template, fill existing WBS codes, company IDs and calendar codes. Preview every row before confirming. Only Draft schedules can be changed.</p>
    <button disabled={busy} onClick={()=>void api<{filename:string;workbook_base64:string}>(base+'/imports/activities/excel-template').then(r=>downloadBase64(r.filename,r.workbook_base64)).catch(e=>setErr((e as Error).message))}>Download Excel template</button>
    {canManage&&<div style={{display:'grid',gap:9,marginTop:12,maxWidth:680}}>
      <select aria-label="Excel target draft schedule" value={schedule} onChange={e=>{setSchedule(e.target.value);setExcelPreview(null);setExcelResult('')}}><option value="">Select Draft schedule</option>{schedules.filter(x=>x.status==='Draft').map(x=><option key={x.id} value={x.id}>{x.name} — {x.version}</option>)}</select>
      <input aria-label="Activity Excel workbook" type="file" accept=".xlsx" onChange={e=>void selectExcel(e.target.files?.[0]||null)}/>
      <button disabled={busy||!schedule||!excelBase64} onClick={()=>void previewExcel()}>Preview Excel import (no changes)</button>
      {excelPreview&&<div><strong>{excelName}:</strong> {excelPreview.valid_rows} valid / {excelPreview.total_rows} rows; {excelPreview.error_count} errors.
        {excelPreview.errors.map((e,i)=><p key={i} style={{color:'#a53025'}}>Row {e.row}: {e.errors.join('; ')}</p>)}
        {excelPreview.error_count===0&&<button disabled={busy} onClick={()=>void confirmExcel()}>Confirm import into Draft schedule</button>}</div>}
      {excelResult&&<p role="status" style={{color:'#166a40'}}>{excelResult}</p>}
    </div>}
    <hr/><h3>Dependency & Calendar Excel Imports</h3>
    <p>Dependency imports validate the entire draft schedule network, including cycles. Calendar imports create new calendars only and never overwrite existing versions.</p>
    <select aria-label="Bulk import type" value={bulkKind} onChange={e=>{setBulkKind(e.target.value as 'dependencies'|'calendars');setBulkPreview(null);setBulkWorkbook('');setBulkStatus('')}}>
      <option value="dependencies">Schedule dependencies</option><option value="calendars">New project calendars</option>
    </select>
    <button disabled={busy} style={{marginLeft:10}} onClick={()=>void api<{filename:string;workbook_base64:string}>(base+`/imports/${bulkKind}/excel-template`).then(r=>downloadBase64(r.filename,r.workbook_base64)).catch(e=>setErr((e as Error).message))}>Download template</button>
    {canManage&&<div style={{display:'grid',gap:9,maxWidth:680,marginTop:12}}>
      {bulkKind==='dependencies'&&<select aria-label="Dependency target draft schedule" value={schedule} onChange={e=>{setSchedule(e.target.value);setBulkPreview(null)}}><option value="">Choose draft schedule</option>{schedules.filter(x=>x.status==='Draft').map(x=><option key={x.id} value={x.id}>{x.name} — {x.version}</option>)}</select>}
      <input aria-label="Dependency or calendar Excel workbook" type="file" accept=".xlsx" onChange={async e=>{setBulkPreview(null);setBulkStatus('');setBulkWorkbook('');const file=e.target.files?.[0];if(!file)return;if(file.size>2_000_000){setErr('Maximum workbook size is 2 MB');return}const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));setBulkWorkbook(btoa(binary));}}/>
      <button disabled={busy||!bulkWorkbook||(bulkKind==='dependencies'&&!schedule)} onClick={async()=>{setBusy(true);setErr('');setBulkPreview(null);try{setBulkPreview(await api<ImportPreview & {sha256:string}>(base+`/imports/${bulkKind}/excel-preview`,'POST',{workbook_base64:bulkWorkbook,schedule_id:bulkKind==='dependencies'?Number(schedule):null}));}catch(e){setErr((e as Error).message)}finally{setBusy(false)}}}>Validate and preview (no changes)</button>
      {bulkPreview&&<div role="status">{bulkPreview.valid_rows} valid rows; {bulkPreview.error_count} errors.
        {bulkPreview.errors.map((e,i)=><p key={i} style={{color:'#a53025'}}>Row {e.row}: {e.errors.join('; ')}</p>)}
        {bulkPreview.error_count===0&&<button disabled={busy} onClick={async()=>{if(!window.confirm(`Import ${bulkPreview.valid_rows} ${bulkKind} now?`))return;setBusy(true);setErr('');try{const result=await api<{written:number}>(base+`/imports/${bulkKind}/excel-confirm`,'POST',{workbook_base64:bulkWorkbook,schedule_id:bulkKind==='dependencies'?Number(schedule):null,preview_sha256:bulkPreview.sha256});setBulkStatus(`${result.written} ${bulkKind} imported`);setBulkPreview(null);setBulkWorkbook('')}catch(e){setErr((e as Error).message);setBulkPreview(null)}finally{setBusy(false)}}}>Confirm import</button>}
      </div>}
      {bulkStatus&&<p style={{color:'#166a40'}}>{bulkStatus}</p>}
    </div>}
    <hr/><h3>Activity CSV import — validate only</h3>
    <button onClick={()=>downloadCsv('planning-activity-template.csv',[['activity_code','activity_name','wbs_code','activity_type','duration_hours','source_type','source_id'],['CV-100','Foundation excavation','CIV','Task',40,'','']])}>Download activity CSV template</button>
    {canManage&&<><p style={{fontSize:13}}>Select a draft schedule, paste activity CSV data and validate duplicates, WBS references and activity types. This preview never writes schedule records.</p>
      <select aria-label="Target draft schedule" value={schedule} onChange={e=>{setSchedule(e.target.value);setPreview(null)}}><option value="">Choose draft schedule</option>{schedules.filter(x=>x.status==='Draft').map(x=><option value={x.id} key={x.id}>{x.name} / {x.version}</option>)}</select>
      <textarea aria-label="Activity CSV input" value={csv} onChange={e=>setCsv(e.target.value)} placeholder="Paste CSV including headers" rows={6} style={{display:'block',width:'100%',marginTop:10}}/>
      <button disabled={busy||!schedule||!csv.trim()} onClick={()=>void validate()}>Validate CSV (no import)</button>
      {preview&&<div><p>{preview.valid_rows} valid / {preview.total_rows} rows · {preview.error_count} errors · {preview.written} records written</p>{preview.errors.map((x,i)=><p key={i} style={{color:'#a53025'}}>Row {x.row} ({x.activity_code}): {x.errors.join('; ')}</p>)}</div>}</>}
  </section>;
}


type ProductivityResult = {schedule_id:number;current_source_retrieved_at:string;historical_as_of_reconciliation:boolean;requires_planner_review:boolean;activities:Array<{activity_id:number;activity_code:string;status:string;reason?:string;unit?:string;remaining_quantity?:number;verified_quantity_current?:number;productivity_units_per_hour?:number;recommended_remaining_hours?:number;completed_from_current_measurement?:boolean;basis?:string}>};
type ProductivityHistory = {data_date:string;window_days:number;basis:string;activities:Array<{activity_id:number;activity_code:string;status:string;reason?:string;unit?:string;observed_days?:number;net_verified_quantity?:number;net_quantity_per_observed_day?:number;sample_coverage?:string;confidence_note?:string;daily?:Array<{date:string;net_quantity:number}>}>};
type LaborProductivity = {basis:string;activities:Array<{activity_id:number;activity_code:string;status:string;reason?:string;unit?:string;net_eligible_quantity?:number;productive_labor_hours?:number;idle_labor_hours?:number;quantity_per_productive_labor_hour?:number;coverage?:string}>};
type EquipmentProductivity = {basis:string;activities:Array<{activity_id:number;activity_code:string;status:string;reason?:string;unit?:string;net_eligible_quantity?:number;allocated_equipment_hours?:number;quantity_per_equipment_hour?:number;coverage?:string}>};
type AvailabilityEvidence = {data_date:string;equipment_availability:string;confirmed_shift_capacity:boolean;resource_demands:Array<{demand_id:number;resource_name:string;demand_quantity:number;demand_unit:string;planning_capacity_value:number|null;capacity_evidence_status:string;covers_data_date:boolean}>;workforce_mobilization:Array<{company_id:number;discipline_id:number|null;mobilized_personnel_count:number;capacity_status:string}>};
type ResourceScenarioResult = {activities:Array<{activity_id:number;activity_code:string;status:string;reason?:string;unit?:string;remaining_quantity?:number;estimated_working_days?:number;limiting_resource?:string;labor_capacity_per_day?:number;equipment_capacity_per_day?:number}>};
type ForecastRevision = {id:number;revision:number;status:string;data_date:string;forecast_finish:string|null;basis:string};
type ForecastResult = {project_finish:string|null;data_date:string;basis:string;remaining_activity_count:number;completed_activity_ids:number[];assumptions:string[];activities:Array<{id:number;code:string;name:string;start:string;finish:string;critical:boolean;total_float_hours:number}>};
function PlanningForecast({base,schedules,canManage}:{base:string;schedules:Schedule[];canManage:boolean}) {
  const [selected,setSelected]=useState('');
  const [dataDate,setDataDate]=useState(today);
  const [rows,setRows]=useState<Activity[]>([]);
  const [inputs,setInputs]=useState<Record<number,{completed:boolean;remaining_hours:number}>>({});
  const [output,setOutput]=useState<ForecastResult|null>(null);
  const [coverageResult,setCoverageResult]=useState<{note:string;activities:Array<{activity_id:number;coverage:Record<string,{status:string;confirmed_booking_count:number}>;resource_demand_evidence:{equipment_demands:Array<{demand_id:number;resource_name:string;demand_quantity:number;demand_unit:string;distinct_fully_booked_assets:number;type_matched_eligible_assets:number;booking_gap:number|null;status:string}>}}>}|null>(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);
  const [revisions,setRevisions]=useState<ForecastRevision[]>([]);
  const [notice,setNotice]=useState('');
  const [rates,setRates]=useState<Record<number,{rate:string;unit:string}>>({});
  const [recommendations,setRecommendations]=useState<ProductivityResult|null>(null);
  const [chosen,setChosen]=useState<Record<number,boolean>>({});
  const [recommendationBusy,setRecommendationBusy]=useState(false);
  const [reviewNote,setReviewNote]=useState('');
  const [history,setHistory]=useState<ProductivityHistory|null>(null);
  const [historyBusy,setHistoryBusy]=useState(false);
  const [labor,setLabor]=useState<LaborProductivity|null>(null);
  const [laborBusy,setLaborBusy]=useState(false);
  const [equipment,setEquipment]=useState<EquipmentProductivity|null>(null);
  const [equipmentBusy,setEquipmentBusy]=useState(false);
  const [resourceInputs,setResourceInputs]=useState<Record<number,{unit:string;laborRate:string;workers:string;laborHours:string;equipmentRate:string;equipmentCount:string;equipmentHours:string}>>({});
  const [resourceResult,setResourceResult]=useState<ResourceScenarioResult|null>(null);
  const [resourceBusy,setResourceBusy]=useState(false);
  const [availability,setAvailability]=useState<AvailabilityEvidence|null>(null);
  const [availabilityBusy,setAvailabilityBusy]=useState(false);
  async function checkResourceEvidence(){
    setAvailabilityBusy(true);setAvailability(null);setError('');
    try{setAvailability(await api<AvailabilityEvidence>(base+`/schedules/${selected}/resource-availability-evidence?data_date=${encodeURIComponent(dataDate)}`));}
    catch(e){setError((e as Error).message)}finally{setAvailabilityBusy(false)}
  }

  async function calculateResourceScenarios(){
    setResourceBusy(true);setError('');setResourceResult(null);
    try {
      const payload=rows.filter(r=>resourceInputs[r.id]?.unit?.trim()).map(r=>{
        const x=resourceInputs[r.id];
        const num=(v:string)=>v?.trim()?Number(v):null;
        return {activity_id:r.id,quantity_unit:x.unit.trim(),labor_rate:num(x.laborRate),workers:num(x.workers),labor_hours_per_worker_day:num(x.laborHours),equipment_rate:num(x.equipmentRate),equipment_count:num(x.equipmentCount),equipment_hours_per_unit_day:num(x.equipmentHours)};
      });
      if(!payload.length)throw new Error('Enter a source quantity unit for at least one activity.');
      setResourceResult(await api<ResourceScenarioResult>(base+`/schedules/${selected}/resource-scenario-preview`,'POST',{activities:payload}));
    }catch(e){setError((e as Error).message)}finally{setResourceBusy(false)}
  }

  async function loadEquipment(){
    setEquipmentBusy(true);setError('');setEquipment(null);
    try{setEquipment(await api<EquipmentProductivity>(base+`/schedules/${selected}/equipment-productivity?data_date=${encodeURIComponent(dataDate)}&window_days=${historyWindow}`));}
    catch(e){setError((e as Error).message)}finally{setEquipmentBusy(false)}
  }

  async function loadLabor(){
    setLaborBusy(true);setError('');setLabor(null);
    try{setLabor(await api<LaborProductivity>(base+`/schedules/${selected}/labor-productivity?data_date=${encodeURIComponent(dataDate)}&window_days=${historyWindow}`))}
    catch(e){setError((e as Error).message)}finally{setLaborBusy(false)}
  }

  const [historyWindow,setHistoryWindow]=useState(28);
  async function loadHistory(){
    setHistoryBusy(true);setError('');setHistory(null);
    try{
      setHistory(await api<ProductivityHistory>(base+`/schedules/${selected}/productivity-history?data_date=${encodeURIComponent(dataDate)}&window_days=${historyWindow}`));
    }catch(e){setError((e as Error).message)}finally{setHistoryBusy(false)}
  }
  async function calculateRecommendations(){
    setRecommendationBusy(true);setError('');setRecommendations(null);setChosen({});setReviewNote('');
    try{
      const requested=rows.filter(r=>rates[r.id]?.rate?.trim() && rates[r.id]?.unit?.trim());
      if(!requested.length)throw new Error('Enter a positive productivity rate and matching quantity unit for at least one activity.');
      if(requested.some(r=>!Number.isFinite(Number(rates[r.id].rate))||Number(rates[r.id].rate)<=0))throw new Error('All submitted productivity rates must be greater than zero.');
      const result=await api<ProductivityResult>(base+`/schedules/${selected}/remaining-duration-recommendations`,'POST',{
        activities:requested.map(r=>({activity_id:r.id,productivity_units_per_hour:Number(rates[r.id].rate),quantity_unit:rates[r.id].unit.trim()}))
      });
      setRecommendations(result);
    }catch(e){setError((e as Error).message)}finally{setRecommendationBusy(false)}
  }
  function applySelectedRecommendations(){
    if(!recommendations)return;
    const accepted=recommendations.activities.filter(r=>chosen[r.activity_id]&&r.status==='recommendation'&&Number.isFinite(r.recommended_remaining_hours));
    if(!accepted.length){setError('Select one or more valid recommendations before applying.');return}
    setInputs(current=>{
      const updated={...current};
      for(const r of accepted){
        updated[r.activity_id]={completed:false,remaining_hours:r.recommended_remaining_hours!};
      }
      return updated;
    });
    setOutput(null);
    setReviewNote(`${accepted.length} recommendation(s) copied into UNSAVED forecast inputs. Review all activities and the reporting date, recalculate, then save a new draft revision if appropriate. Current measurements are not historical as-of data-date evidence.`);
    setRecommendations(null);setChosen({});
  }
  async function refreshRevisions(){if(!selected)return;try{setRevisions(await api<ForecastRevision[]>(base+`/schedules/${selected}/forecast-revisions`))}catch(e){setError((e as Error).message)}}
  useEffect(()=>{
    setCoverageResult(null);setOutput(null);setRows([]);setInputs({});setError('');setRevisions([]);setNotice('');setRates({});setRecommendations(null);setChosen({});setReviewNote('');setHistory(null);
    if (!selected) return;
    let active=true;
    void api<ForecastRevision[]>(base+`/schedules/${selected}/forecast-revisions`).then(items=>{if(active)setRevisions(items)}).catch(e=>{if(active)setError((e as Error).message)});
    void api<Activity[]>(base+`/schedules/${selected}/activities`).then(items=>{
      if(!active)return;
      setRows(items);
      setInputs(Object.fromEntries(items.map(a=>[a.id,{completed:false,remaining_hours:a.activity_type==='Milestone'?0:(a.duration_hours??0)}])));
    }).catch(e=>{if(active)setError((e as Error).message)});
    return ()=>{active=false};
  },[selected,base]);
  async function calculatePreview(){
    setLoading(true);setError('');setOutput(null);setCoverageResult(null);
    try {
      const payload={data_date:dataDate,activities:rows.map(r=>({activity_id:r.id,...inputs[r.id]}))};
      const res=await api<ForecastResult>(base+`/schedules/${selected}/forecast-preview`,'POST',payload);
      setOutput(res);
    }catch(e){setError((e as Error).message)}finally{setLoading(false)}
  }
  async function inspectResourceCoverage(){
    if(!selected||!output)return;
    if(!output.activities.some(a=>new Date(a.finish).getTime()>new Date(a.start).getTime())){setError("No positive-duration activities to check; milestones have no reservation window.");return;}
    setLoading(true);setError('');setCoverageResult(null);
    try{
      const response=await api<{note:string;activities:Array<{activity_id:number;coverage:Record<string,{status:string;confirmed_booking_count:number}>;resource_demand_evidence:{equipment_demands:Array<{demand_id:number;resource_name:string;demand_quantity:number;demand_unit:string;distinct_fully_booked_assets:number;type_matched_eligible_assets:number;booking_gap:number|null;status:string}>}}>}>(base+`/schedules/${selected}/resource-coverage-preview`,'POST',{
        activities:output.activities.filter(a=>new Date(a.finish).getTime()>new Date(a.start).getTime()).map(a=>({activity_id:a.id,starts_at:a.start,ends_at:a.finish}))
      });
      setCoverageResult(response);
    }catch(e){setError((e as Error).message)}finally{setLoading(false)}
  }
  async function saveRevision(){
    setLoading(true);setError('');setNotice('');
    try {
      const payload={data_date:dataDate,activities:rows.map(r=>({activity_id:r.id,...inputs[r.id]}))};
      const item=await api<{id:number;revision:number}>(base+`/schedules/${selected}/forecast-revisions`,'POST',payload);
      setNotice(`Forecast revision ${item.revision} saved as draft. Submit it for independent review.`);
      await refreshRevisions();
    }catch(e){setError((e as Error).message)}finally{setLoading(false)}
  }
  async function decideRevision(id:number,action:string){
    setLoading(true);setError('');setNotice('');
    try{
      await api(base+`/schedules/${selected}/forecast-revisions/${id}/decision`,'POST',{action,note:''});
      setNotice(`Forecast ${action} action recorded.`);await refreshRevisions();
    }catch(e){setError((e as Error).message)}finally{setLoading(false)}
  }
  return <section style={{background:'#fff',border:'1px solid #dce4ed',borderRadius:12,padding:18,marginBottom:16}}>
    <h2>Current Schedule Forecast — Preview</h2>
    <p style={{color:'#52657d'}}>Planner-entered assumptions only. This does not alter the approved baseline, actuals, or contract dates.</p>
    <div style={{display:'flex',gap:12,flexWrap:'wrap',marginBottom:16}}>
      <label>Schedule <select value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Select schedule</option>{schedules.map(s=><option value={s.id} key={s.id}>{s.name} · {s.version}</option>)}</select></label>
      <label>Reporting data date <input type="date" value={dataDate} onChange={e=>{setDataDate(e.target.value);setReviewNote('');setHistory(null);setLabor(null);setEquipment(null);}}/></label>
    </div>
    {!!rows.length && <div style={{overflowX:'auto'}}><table style={{width:'100%'}}><thead><tr><th>Activity</th><th>Completed (assumed)</th><th>Remaining hours</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.code} — {r.name}</td><td><input type="checkbox" checked={inputs[r.id]?.completed||false} onChange={e=>setInputs(o=>({...o,[r.id]:{...o[r.id],completed:e.target.checked}}))}/></td><td><input type="number" min="0" step="0.5" disabled={inputs[r.id]?.completed||r.activity_type==='Milestone'} value={inputs[r.id]?.remaining_hours??0} onChange={e=>setInputs(o=>({...o,[r.id]:{...o[r.id],remaining_hours:Number(e.target.value)}}))} style={{maxWidth:120}}/></td></tr>)}</tbody></table></div>}
    {!!rows.length && <div style={{border:'1px solid #cbd7e5',borderRadius:10,padding:14,marginTop:16,background:'#f7fafc'}}>
      <h3 style={{marginTop:0}}>Historical productivity — observed daily output</h3>
      <p style={{fontSize:13,color:'#52657d'}}>Read-only trend of quantities from currently approved Construction reports, grouped by their work dates. It is not a historical approval-as-of reconstruction, working-hours rate, or forecast probability.</p>
      <label>Observation window <select value={historyWindow} onChange={e=>{setHistoryWindow(Number(e.target.value));setHistory(null);setLabor(null)}}><option value={14}>14 days</option><option value={28}>28 days</option><option value={56}>56 days</option><option value={90}>90 days</option></select></label>
      <button type="button" disabled={historyBusy||!selected} onClick={()=>void loadHistory()} style={{marginLeft:12,padding:10}}>{historyBusy?'Loading…':'Analyze verified daily output'}</button>
      <button type="button" disabled={laborBusy||!selected} onClick={()=>void loadLabor()} style={{marginLeft:12,padding:10}}>{laborBusy?'Loading labor…':'Analyze activity-booked labor hours'}</button>
      <button type="button" disabled={equipmentBusy||!selected} onClick={()=>void loadEquipment()} style={{marginLeft:12,padding:10}}>{equipmentBusy?'Loading equipment…':'Analyze activity-booked equipment hours'}</button>
      {equipment&&<><p style={{fontSize:12,color:'#52657d'}}>{equipment.basis}. Equipment classes, utilization and staffing are not verified.</p><div style={{overflowX:'auto'}}><table style={{width:'100%'}}><thead><tr><th>Activity</th><th>Eligible quantity</th><th>Allocated equipment hours</th><th>Quantity / equipment-hour</th><th>Evidence</th></tr></thead><tbody>{equipment.activities.map(a=><tr key={a.activity_id}><td>{a.activity_code}</td><td>{a.net_eligible_quantity===undefined?'—':`${a.net_eligible_quantity} ${a.unit||''}`}</td><td>{a.allocated_equipment_hours??'—'}</td><td>{a.quantity_per_equipment_hour===undefined?'—':`${a.quantity_per_equipment_hour} ${a.unit||''}/equipment-hour`}</td><td>{a.status==='observed'?(a.coverage==='broader_sample'?'Broader observed sample':'Limited observed sample'):(a.reason||'Unavailable')}</td></tr>)}</tbody></table></div></>}
      {labor&&<><p style={{fontSize:12,color:'#52657d'}}>{labor.basis}. This is not HR attendance, elapsed schedule hours, or a historical approval-as-of snapshot.</p><div style={{overflowX:'auto'}}><table style={{width:'100%'}}><thead><tr><th>Activity</th><th>Eligible quantity</th><th>Productive labor hours</th><th>Idle labor hours</th><th>Quantity / labor-hour</th><th>Evidence</th></tr></thead><tbody>{labor.activities.map(a=><tr key={a.activity_id}><td>{a.activity_code}</td><td>{a.net_eligible_quantity===undefined?'—':`${a.net_eligible_quantity} ${a.unit||''}`}</td><td>{a.productive_labor_hours??'—'}</td><td>{a.idle_labor_hours??'—'}</td><td>{a.quantity_per_productive_labor_hour===undefined?'—':`${a.quantity_per_productive_labor_hour} ${a.unit||''}/labor-hour`}</td><td>{a.status==='observed'?(a.coverage==='broader_sample'?'Broader observed sample':'Limited observed sample'):(a.reason||'Unavailable')}</td></tr>)}</tbody></table></div></>}
      {history&&<><p style={{fontSize:12,color:'#52657d'}}>{history.basis}</p><div style={{overflowX:'auto'}}><table style={{width:'100%'}}><thead><tr><th>Activity</th><th>Observed days</th><th>Net approved-now quantity</th><th>Per observed day</th><th>Evidence coverage</th></tr></thead><tbody>{history.activities.map(h=><tr key={h.activity_id}><td>{h.activity_code}</td><td>{h.observed_days??'—'}</td><td>{h.net_verified_quantity===undefined?'—':`${h.net_verified_quantity} ${h.unit??''}`}</td><td>{h.net_quantity_per_observed_day===undefined?'—':`${h.net_quantity_per_observed_day} ${h.unit??''}/observed day`}</td><td>{h.status==='observed'?(h.sample_coverage==='broader_sample'?'Broader sample':'Limited sample'):(h.reason||'Unavailable')}</td></tr>)}</tbody></table></div></>}
    </div>}
    {canManage && !!rows.length && <div style={{border:'1px solid #cbd7e5',borderRadius:10,padding:14,marginTop:16,background:'#f7fafc'}}>
      <h3 style={{marginTop:0}}>Productivity-based remaining-duration review</h3>
      <p style={{fontSize:13,color:'#52657d'}}>Enter a productivity rate and quantity unit matching the linked Construction record (for example, MT or m³). Only current verified quantities are available. Recommendations are estimates, never verified elapsed durations or automatic progress updates.</p>
      <div style={{overflowX:'auto'}}><table style={{width:'100%'}}><thead><tr><th>Activity</th><th>Units per hour</th><th>Quantity unit</th></tr></thead><tbody>{rows.filter(r=>r.activity_type!=='Milestone').map(r=><tr key={r.id}><td>{r.code} — {r.name}</td><td><input aria-label={`Productivity rate for ${r.code}`} type="number" min="0.000001" step="any" value={rates[r.id]?.rate??''} placeholder="e.g. 5" onChange={e=>{setRates(o=>({...o,[r.id]:{...o[r.id],rate:e.target.value}}));setRecommendations(null);setChosen({});}} style={{maxWidth:130}}/></td><td><input aria-label={`Quantity unit for ${r.code}`} value={rates[r.id]?.unit??''} placeholder="Exact source unit" onChange={e=>{setRates(o=>({...o,[r.id]:{...o[r.id],unit:e.target.value}}));setRecommendations(null);setChosen({});}} style={{maxWidth:155}}/></td></tr>)}</tbody></table></div>
      <button type="button" disabled={recommendationBusy||loading||!selected} onClick={()=>void calculateRecommendations()} style={{padding:10,marginTop:12}}>{recommendationBusy?'Checking…':'Get current-source recommendations'}</button>
      {recommendations&&<div style={{marginTop:16}}><p style={{fontSize:12,color:'#52657d'}}>Source retrieved: {recommendations.current_source_retrieved_at} · Not reconstructed as of forecast data date · Select individually to apply to unsaved inputs.</p><div style={{overflowX:'auto'}}><table style={{width:'100%'}}><thead><tr><th>Use</th><th>Activity</th><th>Remaining quantity</th><th>Recommendation</th><th>Current input</th><th>Availability</th></tr></thead><tbody>{recommendations.activities.map(r=><tr key={r.activity_id}><td><input type="checkbox" aria-label={`Accept recommendation for ${r.activity_code}`} disabled={r.status!=='recommendation'||!Number.isFinite(r.recommended_remaining_hours)} checked={!!chosen[r.activity_id]} onChange={e=>setChosen(o=>({...o,[r.activity_id]:e.target.checked}))}/></td><td>{r.activity_code}</td><td>{r.remaining_quantity===undefined?'—':`${r.remaining_quantity} ${r.unit??''}`}</td><td>{r.recommended_remaining_hours===undefined?'—':`${r.recommended_remaining_hours} working hours`}</td><td>{inputs[r.activity_id]?.remaining_hours??'—'} hours</td><td>{r.status==='recommendation'?'Review estimate':r.reason||'Unavailable'}</td></tr>)}</tbody></table></div><button type="button" disabled={!Object.values(chosen).some(Boolean)} onClick={applySelectedRecommendations} style={{marginTop:12,padding:10}}>Apply selected to unsaved forecast inputs</button></div>}
      {reviewNote&&<p role="status" style={{color:'#1b5b3e'}}>{reviewNote}</p>}
    </div>}
    {canManage && !!rows.length && <div style={{border:'1px solid #cbd7e5',borderRadius:10,padding:14,marginTop:16,background:'#f7fafc'}}>
      <h3>Resource-based schedule scenario — planner assumptions</h3>
      <p style={{fontSize:13,color:'#52657d'}}>Enter at least one complete labor or equipment constraint. Rates are quantity per productive labor-hour or equipment-hour; allocated capacity is a scenario assumption, not confirmed availability. This does not update the forecast or calculate dependency-aware finish dates.</p>
      <div style={{overflowX:'auto'}}><table style={{width:'100%'}}><thead><tr><th>Activity</th><th>Source unit</th><th>Qty/labor-hr</th><th>Workers</th><th>Hours/worker/day</th><th>Qty/equipment-hr</th><th>Equipment units</th><th>Hours/unit/day</th></tr></thead><tbody>{rows.filter(r=>r.activity_type!=='Milestone').map(r=>{
        const v=resourceInputs[r.id]||{unit:'',laborRate:'',workers:'',laborHours:'',equipmentRate:'',equipmentCount:'',equipmentHours:''};
        return <tr key={r.id}><td>{r.code}</td>{(['unit','laborRate','workers','laborHours','equipmentRate','equipmentCount','equipmentHours'] as const).map(key=><td key={key}><input aria-label={`${key} for ${r.code}`} type={key==='unit'?'text':'number'} min={key==='unit'?undefined:'0.000001'} step={key==='unit'?undefined:'any'} value={v[key]} style={{width:key==='unit'?78:95}} onChange={e=>{setResourceInputs(o=>({...o,[r.id]:{...v,[key]:e.target.value}}));setResourceResult(null)}}/></td>)}</tr>;
      })}</tbody></table></div>
      <button type="button" disabled={resourceBusy||!selected} onClick={()=>void calculateResourceScenarios()} style={{padding:10,marginTop:12}}>{resourceBusy?'Calculating…':'Preview resource constraints'}</button>
      <div style={{marginTop:14}}><button type="button" disabled={!selected||availabilityBusy||!canManage} onClick={checkResourceEvidence}>{availabilityBusy?'Checking…':'Review resource availability evidence'}</button>
        <p style={{fontSize:12,color:'#52657d'}}>HR mobilization is indicative only, not confirmed shift availability. Planning references are not independent capacity verification.</p>
        {availability&&<div style={{overflowX:'auto'}}><strong>Resource evidence as of {availability.data_date}</strong><table><thead><tr><th>Resource</th><th>Demand</th><th>Planning capacity</th><th>Evidence status</th></tr></thead><tbody>{availability.resource_demands.map(r=><tr key={r.demand_id}><td>{r.resource_name}</td><td>{r.demand_quantity} {r.demand_unit}</td><td>{r.planning_capacity_value??'Unavailable'}</td><td>{r.capacity_evidence_status}{r.covers_data_date?'':' (outside period)'}</td></tr>)}</tbody></table><p>Mobilized HR personnel (not available crew): {availability.workforce_mobilization.reduce((total,r)=>total+r.mobilized_personnel_count,0)} across listed company/discipline groups. Equipment availability: not verified. Resource-constrained schedule calculations remain disabled.</p></div>}
      </div>
      {resourceResult&&<div style={{overflowX:'auto',marginTop:12}}><table style={{width:'100%'}}><thead><tr><th>Activity</th><th>Remaining</th><th>Labor/day</th><th>Equipment/day</th><th>Limiting resource</th><th>Estimated working days</th></tr></thead><tbody>{resourceResult.activities.map(a=><tr key={a.activity_id}><td>{a.activity_code}</td><td>{a.remaining_quantity===undefined?'—':`${a.remaining_quantity} ${a.unit}`}</td><td>{a.labor_capacity_per_day??'—'}</td><td>{a.equipment_capacity_per_day??'—'}</td><td>{a.limiting_resource??'—'}</td><td>{a.status==='scenario'?a.estimated_working_days:(a.reason||'Unavailable')}</td></tr>)}</tbody></table><p style={{fontSize:12,color:'#52657d'}}>Working-day estimates exclude scheduling dependencies, actual calendar allocation, downtime and verified future availability. No changes saved.</p></div>}
    </div>}
    {canManage && !!rows.length && <button disabled={loading} onClick={()=>void calculatePreview()} style={{marginTop:14,padding:10}}>{loading?'Calculating…':'Calculate current forecast'}</button>}
    {error && <p role="alert" style={{color:'#ae352a'}}>{error}</p>}
    {canManage && !!rows.length && <button disabled={loading} type="button" onClick={()=>void saveRevision()} style={{margin:10,padding:10}}>Save forecast revision</button>}
    {notice && <p role="status">{notice}</p>}
    {!!revisions.length && <div style={{marginTop:16}}><h3>Saved forecast revisions</h3><p style={{color:'#52657d'}}>Approved forecasts remain planner estimates, not verified actuals or contract amendments.</p><div style={{overflowX:'auto'}}><table style={{width:'100%'}}><thead><tr><th>Revision</th><th>Data date</th><th>Finish</th><th>Status</th><th>Actions</th></tr></thead><tbody>{revisions.map(r=><tr key={r.id}><td>{r.revision}</td><td>{r.data_date}</td><td>{r.forecast_finish??'N/A'}</td><td>{r.status}</td><td>{canManage && r.status==='Draft' ? <button disabled={loading} onClick={()=>void decideRevision(r.id,'submit')}>Submit</button> : canManage && r.status==='Pending Review' ? <><button disabled={loading} onClick={()=>void decideRevision(r.id,'approve')}>Approve*</button><button disabled={loading} onClick={()=>void decideRevision(r.id,'return')}>Return*</button></> : '—'}</td></tr>)}</tbody></table></div><p style={{fontSize:12}}>*Only a different organization administrator may approve or return a submitted revision.</p></div>}
    {output && output.activities.length>0 && <div style={{marginTop:16,padding:14,border:'1px solid #dce4ed',borderRadius:10}}>
      <h3>Resource reservation coverage (Phase 27)</h3>
      <p>Check whether equipment bookings and HR-confirmed crew reservations cover the forecast activity windows. This is not resource-leveled CPM or verified future headcount.</p>
      <button type="button" disabled={loading} onClick={()=>void inspectResourceCoverage()}>Check confirmed booking coverage</button>
      {coverageResult && <><p>{coverageResult.note}</p><table style={{width:'100%'}}><thead><tr><th>Activity</th><th>HR booking</th><th>Equipment booking</th><th>Equipment demand evidence</th></tr></thead><tbody>{coverageResult.activities.map(r=><tr key={r.activity_id}><td>{rows.find(a=>a.id===r.activity_id)?.code||r.activity_id}</td><td>{r.coverage.workforce?.status||'Unavailable'}</td><td>{r.coverage.equipment?.status||'Unavailable'}</td><td>{r.resource_demand_evidence.equipment_demands.length?r.resource_demand_evidence.equipment_demands.map(d=>`${d.resource_name}: ${d.type_matched_eligible_assets}/${d.demand_quantity} ${d.demand_unit} (${d.status})`).join('; '):'No equipment unit demand registered'}</td></tr>)}</tbody></table></>}
    </div>}
    {output && <div style={{marginTop:18}}><h3>Forecast finish: {output.project_finish?new Date(output.project_finish).toLocaleString():'No unfinished activities'}</h3><p>Remaining: {output.remaining_activity_count} activities · Completed assumptions: {output.completed_activity_ids.length}</p><table style={{width:'100%'}}><thead><tr><th>Activity</th><th>Forecast start</th><th>Forecast finish</th><th>Float (h)</th><th>Critical</th></tr></thead><tbody>{output.activities.map(a=><tr key={a.id}><td>{a.code}</td><td>{a.start}</td><td>{a.finish}</td><td>{a.total_float_hours}</td><td>{a.critical?'Yes':'No'}</td></tr>)}</tbody></table><ul>{output.assumptions.map((a,i)=><li key={i}>{a}</li>)}</ul></div>}
  </section>;
}


type WorkforceEvidence = {
  allocation_id:number; crew_id:number; shift_id:number|null; shift_start_date:string;
  reservation_status:string; eligible_assignment_count:number;
  approved_attended_count:number; approved_unavailable_count:number;
  attendance_unverified_count:number; future_capacity_confirmed:boolean; evidence_note:string;
};
type Allocation = {id:number;schedule_id:number;activity_id:number;resource_type:string;resource_ref:string;starts_at:string;ends_at:string;status:string;notes:string;review_note?:string};
function PlanningAllocations({base,schedules,canManage}:{base:string;schedules:Schedule[];canManage:boolean}) {
  const [schedule,setSchedule]=useState<number|null>(null);
  const [activities,setActivities]=useState<Activity[]>([]);
  const [items,setItems]=useState<Allocation[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [evidence,setEvidence]=useState<WorkforceEvidence|null>(null);
  const [evidenceLoading,setEvidenceLoading]=useState(false);
  const [evidenceError,setEvidenceError]=useState('');
  const [evidenceId,setEvidenceId]=useState<number|null>(null);
  async function inspectWorkforce(id:number){
    setEvidence(null);setEvidenceId(id);setEvidenceError('');setEvidenceLoading(true);
    try{setEvidence(await api<WorkforceEvidence>(base+`/allocations/${id}/workforce-capacity`));}
    catch(e){setEvidenceError((e as Error).message);}
    finally{setEvidenceLoading(false);}
  }
  async function refresh(){if(!schedule)return;setBusy(true);setError('');try{
    const [response,acts]=await Promise.all([api<{items:Allocation[]}>(base+`/allocations?schedule_id=${schedule}`),api<Activity[]>(base+`/schedules/${schedule}/activities`)]);
    setItems(response.items);setActivities(acts);
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  useEffect(()=>{setItems([]);setActivities([]);setEvidence(null);setEvidenceId(null);setEvidenceError('');if(schedule)void refresh();},[schedule,base]);
  async function add(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const f=e.currentTarget;const v=new FormData(f);setError('');setBusy(true);try{
    await api(base+'/allocations','POST',{schedule_id:schedule,activity_id:Number(v.get('activity_id')),resource_type:String(v.get('resource_type')),resource_ref:String(v.get('resource_ref')).trim(),starts_at:new Date(String(v.get('starts_at'))).toISOString(),ends_at:new Date(String(v.get('ends_at'))).toISOString(),notes:String(v.get('notes')||'')});
    f.reset();await refresh();
  }catch(ex){setError((ex as Error).message);}finally{setBusy(false);}}
  async function cancel(id:number){setBusy(true);setError('');try{await api(base+`/allocations/${id}/cancel`,'POST',{});await refresh();}catch(ex){setError((ex as Error).message);}finally{setBusy(false);}}
  async function review(id:number,decision:'Reviewed'|'Returned'){
    const note=window.prompt('Enter a review reason (at least 5 characters)');
    if(!note||note.trim().length<5)return;
    setBusy(true);setError('');
    try{await api(base+`/allocations/${id}/review`,'POST',{decision,note:note.trim()});await refresh();}
    catch(ex){setError((ex as Error).message);}finally{setBusy(false);}
  }
  async function equipmentDecision(id:number,action:'equipment-confirm'|'equipment-release'|'hr-confirm'|'hr-release'){
    const reason=window.prompt('Enter resource confirmation/release reason (at least 5 characters)');
    if(!reason||reason.trim().length<5)return;
    setBusy(true);setError('');try{await api(base+`/allocations/${id}/${action}`,'POST',{reason:reason.trim()});await refresh()}catch(ex){setError((ex as Error).message)}finally{setBusy(false)}
  }
  return <section style={{background:'white',padding:18,borderRadius:12,border:'1px solid #dce4ed'}}>
    <h2>Resource Allocation Proposals</h2>
    <p style={{color:'#52657d'}}>Planning-only reservations with organization-wide conflict checks and independent review. Reviewed does not mean HR- or Equipment-confirmed. Times must be entered in project-local time and are converted to UTC by the browser.</p>
    <label>Schedule <select value={schedule||''} onChange={e=>setSchedule(Number(e.target.value)||null)}><option value="">Choose schedule</option>{schedules.map(s=><option value={s.id} key={s.id}>{s.name} ({s.version})</option>)}</select></label>
    {error&&<p role="alert" style={{color:'#b42318'}}>{error}</p>}
    {canManage && schedule && <form onSubmit={add} style={{display:'flex',gap:9,flexWrap:'wrap',margin:'16px 0'}}>
      <select name="activity_id" required><option value="">Activity</option>{activities.filter(a=>a.activity_type!=='Summary').map(a=><option value={a.id} key={a.id}>{a.code} — {a.name}</option>)}</select>
      <select name="resource_type"><option>Workforce</option><option>Equipment</option></select>
      <input name="resource_ref" placeholder="Personnel / equipment reference" required maxLength={120}/>
      <label>Start<input name="starts_at" type="datetime-local" required/></label>
      <label>End<input name="ends_at" type="datetime-local" required/></label>
      <input name="notes" placeholder="Notes" maxLength={2000}/>
      <button disabled={busy}>Propose allocation</button>
    </form>}
    {schedule && <button disabled={busy} onClick={()=>void refresh()}>Refresh allocations</button>}
    <div style={{overflowX:'auto'}}><table style={{width:'100%',marginTop:12}}><thead><tr><th>Resource</th><th>Activity</th><th>Start</th><th>End</th><th>Status</th><th>Action</th></tr></thead><tbody>
      {items.map(x=><tr key={x.id}><td>{x.resource_type}: {x.resource_ref}</td><td>{activities.find(a=>a.id===x.activity_id)?.code||x.activity_id}</td><td>{new Date(x.starts_at).toLocaleString()}</td><td>{new Date(x.ends_at).toLocaleString()}</td><td>{x.status}{x.review_note?` — ${x.review_note}`:''}</td><td>{x.status==='Proposed'&&canManage&&<><button disabled={busy} onClick={()=>void review(x.id,'Reviewed')}>Review</button><button disabled={busy} onClick={()=>void review(x.id,'Returned')}>Return</button></>}{x.resource_type==='Workforce'&&x.resource_ref.startsWith('crew:')&&<button type="button" disabled={busy||evidenceLoading} onClick={()=>void inspectWorkforce(x.id)}>HR capacity evidence</button>}{x.resource_type==='Workforce'&&x.status==='Reviewed'&&canManage&&<button disabled={busy} onClick={()=>void equipmentDecision(x.id,'hr-confirm')}>Confirm crew shift (HR)</button>}{x.resource_type==='Workforce'&&x.status==='HRConfirmed'&&canManage&&<button disabled={busy} onClick={()=>void equipmentDecision(x.id,'hr-release')}>Release crew shift (HR)</button>}{x.resource_type==='Equipment'&&x.status==='Reviewed'&&canManage&&<button disabled={busy} onClick={()=>void equipmentDecision(x.id,'equipment-confirm')}>Confirm equipment</button>}{x.resource_type==='Equipment'&&x.status==='EquipmentConfirmed'&&canManage&&<button disabled={busy} onClick={()=>void equipmentDecision(x.id,'equipment-release')}>Release equipment</button>}{!['Cancelled','EquipmentConfirmed','HRConfirmed','Released'].includes(x.status)&&<button disabled={!canManage||busy} onClick={()=>void cancel(x.id)}>Cancel</button>}</td></tr>)}
    </tbody></table></div>
    {!items.length&&<p>No allocation proposals for this schedule.</p>}
    {evidenceId!==null&&<section aria-label="HR workforce capacity evidence" style={{marginTop:18,padding:16,border:'1px solid #dce4ed',borderRadius:10,background:'#f8fafc'}}>
      <div style={{display:'flex',justifyContent:'space-between',gap:12,alignItems:'center'}}><h3 style={{margin:0}}>HR workforce evidence · Allocation #{evidenceId}</h3><button type="button" onClick={()=>{setEvidenceId(null);setEvidence(null);setEvidenceError('')}}>Close</button></div>
      {evidenceLoading&&<p role="status">Loading HR evidence…</p>}
      {evidenceError&&<p role="alert" style={{color:'#b42318'}}>Evidence unavailable: {evidenceError}</p>}
      {evidence&&<>
        <p style={{fontSize:13,color:'#52657d'}}>Crew #{evidence.crew_id} · Shift {evidence.shift_id??'unassigned'} · {evidence.shift_start_date} · Reservation {evidence.reservation_status}</p>
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(160px,1fr))',gap:10}}>
          {([['Eligible mobilized',evidence.eligible_assignment_count],['Approved attended',evidence.approved_attended_count],['Approved unavailable',evidence.approved_unavailable_count],['Attendance unverified',evidence.attendance_unverified_count]] as const).map(([label,value])=><div key={label} style={{background:'white',border:'1px solid #e1e7ee',padding:12,borderRadius:8}}><div style={{fontSize:12,color:'#52657d'}}>{label}</div><strong style={{fontSize:22}}>{value}</strong></div>)}
        </div>
        <p style={{color:'#9a3412',fontWeight:600}}>Future shift capacity: Not confirmed</p>
        <p style={{fontSize:12,color:'#52657d'}}>{evidence.evidence_note}</p>
      </>}
    </section>}
  </section>;
}

type EquipmentAsset={id:number;asset_code:string;name:string;equipment_type:string;status:string;inspection_valid_through:string|null;inspection_evidence_ref:string|null;inspection_review_status:string;inspection_reviewed_by:number|null};
function PlanningEquipment({base,canManage}:{base:string;canManage:boolean}){
  const [items,setItems]=useState<EquipmentAsset[]>([]);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  async function refresh(){setBusy(true);setError('');try{const r=await api<{items:EquipmentAsset[]}>(base+'/equipment-assets');setItems(r.items);}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  useEffect(()=>{void refresh()},[base]);
  async function create(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const v=new FormData(form);setBusy(true);setError('');try{await api(base+'/equipment-assets','POST',{asset_code:String(v.get('asset_code')),name:String(v.get('name')),equipment_type:String(v.get('equipment_type'))});form.reset();await refresh()}catch(ex){setError((ex as Error).message)}finally{setBusy(false)}}
  async function inspect(id:number){const evidence_ref=window.prompt('Inspection evidence reference');if(!evidence_ref)return;const valid_through=window.prompt('Valid through (YYYY-MM-DD)');if(!valid_through)return;setBusy(true);setError('');try{await api(base+`/equipment-assets/${id}/inspection`,'POST',{evidence_ref,valid_through});await refresh()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function review(id:number,decision:'Verified'|'Rejected'){const note=window.prompt('Review justification (at least 5 characters)');if(!note)return;setBusy(true);setError('');try{await api(base+`/equipment-assets/${id}/inspection-review`,'POST',{decision,note});await refresh()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  return <section style={{background:'white',padding:18,borderRadius:12,border:'1px solid #dce4ed'}}><h2>Equipment Register</h2><p>Organization equipment identity and inspection evidence. This is not proof of third-party certification or a confirmed resource assignment.</p>{error&&<p role="alert" style={{color:'#b42318'}}>{error}</p>}{canManage&&<form onSubmit={create} style={{display:'flex',gap:8,flexWrap:'wrap'}}><input name="asset_code" required placeholder="Asset code CRANE-001"/><input name="name" required placeholder="Equipment name"/><input name="equipment_type" required placeholder="Type"/><button disabled={busy}>Register equipment</button></form>}<button disabled={busy} onClick={()=>void refresh()}>Refresh</button><table style={{width:'100%',marginTop:12}}><thead><tr><th>Asset</th><th>Name</th><th>Type</th><th>Inspection valid through</th><th>Review status</th><th>Reservation reference</th><th>Actions</th></tr></thead><tbody>{items.map(x=><tr key={x.id}><td>{x.asset_code}</td><td>{x.name}</td><td>{x.equipment_type}</td><td>{x.inspection_valid_through||'Unverified'}</td><td>{x.inspection_review_status||"Pending"}</td><td>equipment:{x.id}</td><td>{canManage&&<><button disabled={busy} onClick={()=>void inspect(x.id)}>Update evidence</button> {x.inspection_review_status==="Pending"&&<><button disabled={busy} onClick={()=>void review(x.id,"Verified")}>Verify</button> <button disabled={busy} onClick={()=>void review(x.id,"Rejected")}>Reject</button></>}</>}</td></tr>)}</tbody></table></section>
}


/** Internal-only review. Reads an internal API; never reused by the partner workspace. */
function PartnerCommitmentReviews({projectId,canManage}:{projectId:number;canManage:boolean}) {
  type Commitment={id:number;activity_id:number;company_id:number;commitment:string;note:string;status:string;submitted_at:string;expected_date:string|null;review_note:string;submitted_by:number};
  const [items,setItems]=useState<Commitment[]>([]);
  const [notes,setNotes]=useState<Record<number,string>>({});
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const load=async()=>{
    setBusy(true);setError('');
    try {const data=await api<{items:Commitment[]}>(`/projects/${projectId}/partner-planning/internal/commitments`);setItems(data.items);}
    catch(e){setError((e as Error).message);setItems([]);}
    finally{setBusy(false);}
  };
  useEffect(()=>{void load();},[projectId]);
  const review=async(id:number,action:'Accepted'|'Returned')=>{
    setBusy(true);setError('');setNotice('');
    try {
      await api(`/projects/${projectId}/partner-planning/internal/commitments/${id}/review`,'POST',{action,note:notes[id]||''});
      setNotice(`Commitment ${action.toLowerCase()}.`);
      await load();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  };
  return <section style={{background:'#fff',border:'1px solid #dce4ed',borderRadius:12,padding:18}}>
    <h2>Partner Planning Commitments</h2>
    <p style={{color:'#52657d'}}>Review company-submitted commitments. Decisions do not change published schedules or verified progress.</p>
    <button type="button" onClick={()=>void load()} disabled={busy}>Refresh submissions</button>
    {error&&<p role="alert" style={{color:'#a53025'}}>{error}</p>}
    {notice&&<p role="status" style={{color:'#166a40'}}>{notice}</p>}
    <div style={{overflowX:'auto',marginTop:14}}><table style={{width:'100%',minWidth:850}}><thead><tr><th>ID</th><th>Activity ID</th><th>Company ID</th><th>Response</th><th>Expected</th><th>Reason</th><th>Status</th><th>Internal review</th></tr></thead><tbody>
      {items.map(item=><tr key={item.id}><td>{item.id}</td><td>{item.activity_id}</td><td>{item.company_id}</td><td>{item.commitment}</td><td>{item.expected_date||'—'}</td><td style={{maxWidth:200,overflowWrap:'anywhere'}}>{item.note||'—'}</td><td>{item.status}</td><td>{item.status==='Submitted'&&canManage?<div style={{display:'grid',gap:6,minWidth:190}}><input aria-label={`Review note for commitment ${item.id}`} placeholder="Review note / return reason" value={notes[item.id]||''} onChange={e=>setNotes(prev=>({...prev,[item.id]:e.target.value}))}/><div style={{display:'flex',gap:6}}><button disabled={busy} onClick={()=>void review(item.id,'Accepted')}>Accept</button><button disabled={busy||!(notes[item.id]||'').trim()} onClick={()=>void review(item.id,'Returned')}>Return</button></div></div>:item.review_note||'—'}</td></tr>)}
    </tbody></table></div>
    {!items.length&&!busy&&<p>No submissions available.</p>}
  </section>;
}
