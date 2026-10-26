import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, ClipboardCheck, Gauge, Layers, LayoutDashboard, LineChart as LineChartIcon, ListChecks, RefreshCw, TrendingUp, ShieldCheck, Package, FileText, HardHat, Users, type LucideIcon } from 'lucide-react';
import { api } from './api';
import { ProgressReports } from './progress_reports';
import { Pill, ProgressAnalytics } from './progress_charts';
import type { Page, Project, Session } from './types';

type Measure = {percent:number|null;status:string};
type Actual = {activity_id:number;code:string;name:string;wbs_id:number|null;discipline_id:number|null;company_id:number|null;link_status:string;unit:string|null;scope_quantity:string|null;reported_quantity:string|null;verified_quantity:string|null;accepted_quantity:string|null;reported_percent:string|null;verified_percent:string|null;accepted_percent:string|null};
type StageEvidence={status:string;baseline_id?:number;policy_version?:number|null;percent:number|null;errors?:string[]};
type Dashboard = {stage_earning_evidence?:Record<string,StageEvidence>;cross_stage_scheme?:{id:number;version:number;weights:Record<string,number>;approval_reference?:string}|null;construction_measures?:{reported_percent:number|null;verified_percent:number|null;accepted_percent:number|null};visibility:'project'|'assigned company/discipline';filters:{company_id:number|null;discipline_id:number|null};project_id:number;data_date:string;retrieved_at:string;measure:string;overall_percent:number|null;overall_note:string;stages:Record<string,Measure>;publication:{id:number;revision:string;status:string}|null;planned:{period_end:string;planned_percent:number}[];actuals:Actual[];exceptions:string[];calculation_method:string;source_freshness:string;historical_actuals_available:boolean};
type ReadinessResult={status:'available'|'restricted'|'error'|'loading'; metrics:{label:string;value:string|number}[];source:string};
const readinessSources=[
  {key:'engineering',label:'Engineering drawing readiness',path:'engineering-dashboard',icon:FileText,
   values:(x:Record<string,unknown>)=>{const t=(x.totals||{}) as Record<string,unknown>;return ['total','approved','released','overdue'].filter(k=>typeof t[k]==='number').map(k=>({label:k.replaceAll('_',' '),value:Number(t[k])}));}},
  {key:'procurement',label:'Procurement & stores readiness',path:'procurement/dashboard',icon:Package,
   values:(x:Record<string,unknown>)=>[['open_requirements','Open requirements'],['approved_lines_not_ordered','Approved lines not ordered'],['orders_awaiting_receipt','Orders awaiting receipt'],['stock_on_hand','Stock items on hand']].filter(([k])=>typeof x[k]==='number').map(([k,label])=>({label,value:Number(x[k])}))},
  {key:'quality',label:'Quality restrictions',path:'quality/dashboard',icon:ShieldCheck,
   values:(x:Record<string,unknown>)=>[['open_ncrs','Open NCRs'],['active_holds','Active quality holds'],['pending_reviews','Pending inspections/reviews'],['blocking_punches','Blocking punch items']].filter(([k])=>typeof x[k]==='number').map(([k,label])=>({label,value:Number(x[k])}))},
  {key:'hse',label:'HSE restrictions',path:'hse/dashboard',icon:HardHat,
   values:(x:Record<string,unknown>)=>[['blocked_work','Blocked workfronts'],['active_holds','Active safety holds'],['overdue_actions','Overdue safety actions'],['eligibility_gaps','Eligibility gaps']].filter(([k])=>typeof x[k]==='number').map(([k,label])=>({label,value:Number(x[k])}))},
  {key:'manpower',label:'Manpower availability (last 7 days)',path:'manpower/summary',icon:Users,
   values:(x:Record<string,unknown>)=>[['planned_hours','Planned hours'],['attended_hours','Attended hours'],['short_today','Today shortfall'],['alert_total','Workforce alerts']].filter(([k])=>typeof x[k]==='number').map(([k,label])=>({label,value:Number(x[k])}))},
];
function ProgressReadiness({project,refresh}:{project:number;refresh:number}){
  const [sources,setSources]=useState<Record<string,ReadinessResult>>({});
  useEffect(()=>{
    let cancelled=false;
    setSources({});
    for(const source of readinessSources){
      // Source endpoints enforce the module-specific permissions and return 403/404 when inaccessible.
      // Never bypass those permissions in Progress or merge inaccessible totals.
      void api<Record<string,unknown>>(`/projects/${project}/${source.path}`).then(value=>{
        if(!cancelled)setSources(prev=>({...prev,[source.key]:{status:'available',metrics:source.values(value),source:source.path}}));
      }).catch((error:unknown)=>{
        const msg=String(error);
        if(!cancelled)setSources(prev=>({...prev,[source.key]:{status:/403|401|permission|forbidden|not authorized/i.test(msg)?'restricted':'error',metrics:[],source:source.path}}));
      });
    }
    return()=>{cancelled=true};
  },[project,refresh]);
  return <section className="panel">
    <h3 className="section-mark"><Gauge size={18} strokeWidth={2.4}/> Cross-module readiness &amp; constraints</h3>
    <p className="muted">Live source-owned indicators only; counts, hours and readiness are <strong>not</strong> earned physical progress. Each source enforces its own permissions. No restricted totals are displayed.</p>
    <div className="contact-grid">
      {readinessSources.map(source=>{
        const state=sources[source.key];const Icon=source.icon;
        return <div key={source.key} className={`contact-card pg-ready pg-ready-${source.key}`}>
          <h4 className="section-mark"><Icon size={16} strokeWidth={2.4}/> {source.label}</h4>
          {!state?<p className="muted">Loading authorized source…</p>:state.status==='restricted'?<p className="note-card note-alert">Restricted — source module access required</p>:state.status==='error'?<p className="note-card note-bad">Source unavailable — check integration</p>:state.metrics.length?<ul className="fact-row">{state.metrics.map(m=><li key={m.label} className="fact"><strong>{m.label}</strong><em>{m.value}</em></li>)}</ul>:<p className="muted">Source connected; no supported indicators returned</p>}
        </div>;
      })}
    </div>
  </section>;
}
const TABS=['Dashboard','EPCC stages','Readiness','Planned vs actual','Activities','Data quality','Reports'] as const;
type Tab=(typeof TABS)[number];
const TAB_ICON:Record<Tab,LucideIcon>={Dashboard:LayoutDashboard,'EPCC stages':Layers,Readiness:Gauge,'Planned vs actual':LineChartIcon,Activities:ListChecks,'Data quality':AlertTriangle,Reports:FileText};
const TAB_TONE:Record<Tab,string>={Dashboard:'tone-gdash','EPCC stages':'tone-gstage',Readiness:'tone-gready','Planned vs actual':'tone-gcurve',Activities:'tone-gact','Data quality':'tone-gquality',Reports:'tone-greport'};
export function ProgressMonitoringHome({session,initialProjectId}:{session:Session;initialProjectId:number|null}) {
  const [projects,setProjects]=useState<Project[]>([]);
  const [project,setProject]=useState<number|null>(initialProjectId);
  const [data,setData]=useState<Dashboard|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [query,setQuery]=useState('');
  const [refresh,setRefresh]=useState(0);
  const [companyFilter,setCompanyFilter]=useState('');
  const [disciplineFilter,setDisciplineFilter]=useState('');
  const canView=session.user.organization_admin || session.memberships.some(m=>m.project_id===project && (m.permissions?.includes('planning.view')||m.permissions?.includes('planning.manage')));
  useEffect(()=>{void api<Page<Project>>('/projects?limit=100').then(x=>setProjects(x.items)).catch(e=>setError((e as Error).message));},[]);
  useEffect(()=>{setProject(initialProjectId)},[initialProjectId]);
  useEffect(()=>{setData(null);setCompanyFilter('');setDisciplineFilter('');if(project && canView)void load(project,'','')},[project,canView]);
  async function load(id:number,company=companyFilter,discipline=disciplineFilter){setBusy(true);setError('');try{const params=new URLSearchParams();if(company)params.set('company_id',company);if(discipline)params.set('discipline_id',discipline);const suffix=params.toString();setData(await api<Dashboard>(`/projects/${id}/progress/dashboard${suffix?'?'+suffix:''}`))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  const fmt=(v:number|string|null|undefined)=>v==null?'N/A':String(v);
  const pct=(v:number|null)=>v==null?'N/A':`${v.toFixed(2)}%`;
  const companies=Array.from(new Set(data?.actuals.map(a=>a.company_id).filter((id):id is number=>id!=null)??[])).sort((a,b)=>a-b);
  const disciplines=Array.from(new Set(data?.actuals.map(a=>a.discipline_id).filter((id):id is number=>id!=null)??[])).sort((a,b)=>a-b);
  const items=data?.actuals.filter(a=>`${a.code} ${a.name} ${a.link_status}`.toLowerCase().includes(query.toLowerCase()))??[];
  const [tab,setTab]=useState<Tab>('Dashboard');
  const stageEntries=data?Object.entries(data.stages):[];
  const measureLabel=(k:'reported_percent'|'verified_percent'|'accepted_percent')=>k==='reported_percent'?'Reported execution':k==='verified_percent'?'Supervisor-verified':'QA-accepted';
  const dashCards:{label:string;value:string|number;tone:string;icon:LucideIcon;tab:Tab}[]=data?[
    {label:'Overall progress',value:pct(data.overall_percent),tone:'stock',icon:TrendingUp,tab:'EPCC stages'},
    {label:'Reported execution',value:pct(data.construction_measures?.reported_percent??null),tone:'receipt',icon:Activity,tab:'EPCC stages'},
    {label:'Supervisor-verified',value:pct(data.construction_measures?.verified_percent??null),tone:'order',icon:CheckCircle2,tab:'EPCC stages'},
    {label:'QA-accepted',value:pct(data.construction_measures?.accepted_percent??null),tone:'po',icon:ShieldCheck,tab:'EPCC stages'},
    {label:'Linked activities',value:data.actuals.length,tone:'quote',icon:ListChecks,tab:'Activities'},
    {label:'Approved period targets',value:data.planned.length,tone:'invoice',icon:ClipboardCheck,tab:'Planned vs actual'},
    {label:'Data-quality exceptions',value:data.exceptions.length,tone:data.exceptions.length?'impact':'quiet',icon:AlertTriangle,tab:'Data quality'},
  ]:[];
  return <>
    <h2 className="section-mark"><TrendingUp size={21} strokeWidth={2.4}/> Progress Monitoring &amp; Reporting</h2>
    <p className="muted">Source-linked, read-only progress monitoring · Planning baselines remain authoritative</p>
    <div className="toolbar"><label>Project <select value={project??''} onChange={e=>setProject(Number(e.target.value)||null)}><option value="">Select project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}</select></label><button type="button" className="tone-note" onClick={()=>{if(project){setRefresh(n=>n+1);void load(project)}}} disabled={!project||busy}><RefreshCw size={15}/> Refresh sources</button></div>
    {error&&<p role="alert" className="error">{error}</p>}
    {!project?<p className="note-card">Select a project to monitor progress.</p>:!canView?<p className="note-card note-alert">Planning view access is required for this internal Progress dashboard.</p>:data&&<>
      <div className="proc-nav">{TABS.map(name=>{const Icon=TAB_ICON[name];return <button key={name} type="button" className={`proc-tab ${TAB_TONE[name]}${tab===name?' is-on':''}`} aria-pressed={tab===name} onClick={()=>setTab(name)}><Icon size={14} strokeWidth={2.4}/><span>{name}</span></button>})}</div>

      {tab==='Dashboard'&&<section className="panel">
        <h3 className="section-mark"><LayoutDashboard size={18} strokeWidth={2.4}/> Dashboard</h3>
        <ul className="fact-row">
          <li className="fact"><strong>Data date</strong><em>{data.data_date}</em></li>
          <li className="fact"><strong>Measurement</strong><em>{data.measure}</em></li>
          <li className={`fact ${data.publication?'good':'warn'}`}><strong>Baseline</strong><em>{data.publication?.revision??'Not approved'}</em></li>
          <li className="fact hold"><strong>Source refresh</strong><em>{new Date(data.source_freshness).toLocaleString()}</em></li>
        </ul>
        <div className="dash-grid">{dashCards.map(c=>{const Icon=c.icon;return <button key={c.label} type="button" className={`dash-card ${c.tone}`} onClick={()=>setTab(c.tab)}><span className="dash-mark"><Icon size={15} strokeWidth={2.4}/></span><strong>{c.value}</strong><span className="dash-label">{c.label}</span></button>})}</div>
        <p className="note-card">{data.overall_note}</p>
        <p className="muted">The dashboard is live. Submitted reporting snapshots are stored separately and do not change when underlying source records are edited.</p>
      </section>}

      {tab==='EPCC stages'&&<section className="panel">
        <h3 className="section-mark"><Layers size={18} strokeWidth={2.4}/> EPCC stages &amp; construction measures</h3>
        <h4>Approved weighted construction</h4>
        <ul className="fact-row">{(['reported_percent','verified_percent','accepted_percent'] as const).map(k=><li key={k} className={`fact ${k==='accepted_percent'?'good':k==='verified_percent'?'hold':''}`}><strong>{measureLabel(k)}</strong><em>{pct(data.construction_measures?.[k]??null)}</em></li>)}</ul>
        <h4>Stage progress</h4>
        <ul className="fact-row">{stageEntries.map(([name,value])=><li key={name} className="fact"><strong>{name.replace(/^./,m=>m.toUpperCase())}</strong><em>{pct(value.percent)}</em> <Pill value={value.status}/></li>)}</ul>
        {data.cross_stage_scheme&&<>
          <h4>Approved EPCC measurement traceability</h4>
          <p className="muted">Scheme version {data.cross_stage_scheme.version} · Weight basis: 10,000 basis points · All stages must have approved earned progress on the same baseline. Readiness counts do not qualify.</p>
          <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Stage</th><th>Weight</th><th>Approved earned</th><th>Policy version</th><th>Eligibility</th></tr></thead><tbody>
            {Object.entries(data.cross_stage_scheme.weights).map(([stage,weight])=>{const e=data.stage_earning_evidence?.[stage];return <tr key={stage}><td><strong>{stage}</strong></td><td>{(weight/100).toFixed(2)}%</td><td>{pct(e?.percent??null)}</td><td>{e?.policy_version??'Planning scheme'}</td><td>{e?.status==='approved_earned_progress'?<Pill value="Approved"/>:<span className="state-pill state-pending">{e?.errors?.join('; ')||'Unavailable'}</span>}</td></tr>})}
          </tbody></table></div>
        </>}
      </section>}

      {tab==='Readiness'&&(data.visibility==='project'?<ProgressReadiness project={project} refresh={refresh}/>:<section className="panel"><h3 className="section-mark"><Gauge size={18} strokeWidth={2.4}/> Cross-module readiness &amp; constraints</h3><p className="note-card note-alert">Cross-module project-wide readiness cards are hidden for scoped memberships, pending source-specific company/discipline aggregation.</p></section>)}

      {tab==='Planned vs actual'&&<>
        <ProgressAnalytics data={data} project={project}/>
        <section className="panel">
          <h3 className="section-mark"><ClipboardCheck size={18} strokeWidth={2.4}/> Approved period targets</h3>
          {data.planned.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Period end</th><th>Planned progress</th></tr></thead><tbody>{data.planned.map(x=><tr key={x.period_end}><td>{x.period_end}</td><td>{pct(x.planned_percent)}</td></tr>)}</tbody></table></div>:<p className="note-card note-alert">An approved, complete period-target scheme is required before a planned curve can be shown.</p>}
        </section>
      </>}

      {tab==='Activities'&&<section className="panel">
        <h3 className="section-mark"><ListChecks size={18} strokeWidth={2.4}/> Construction · source activity measurements</h3>
        <p className="muted">Reported, verified and QA-accepted are separate measures. Billing/certification is not calculated here.</p>
        <p className="muted">Server-enforced visibility: {data.visibility}. Filters are applied before activity results are returned. Project-wide totals remain N/A for filtered or limited scopes.</p>
        <div className="toolbar" style={{flexWrap:'wrap'}}>
          <label>Company ID <select value={companyFilter} onChange={e=>setCompanyFilter(e.target.value)}><option value="">All authorized</option>{companies.map(id=><option value={id} key={id}>{id}</option>)}</select></label>
          <label>Discipline ID <select value={disciplineFilter} onChange={e=>setDisciplineFilter(e.target.value)}><option value="">All authorized</option>{disciplines.map(id=><option value={id} key={id}>{id}</option>)}</select></label>
          <button type="button" className="primary" disabled={busy} onClick={()=>{if(project)void load(project)}}>Apply filters</button>
          <button type="button" disabled={busy} onClick={()=>{setCompanyFilter('');setDisciplineFilter('');if(project)void load(project,'','')}}>Reset</button>
        </div>
        <div className="toolbar"><input aria-label="Search activities" placeholder="Search code, name or exception" value={query} onChange={e=>setQuery(e.target.value)}/><span>{items.length} activities</span></div>
        <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Activity</th><th>Status</th><th>Scope</th><th>Reported</th><th>Verified</th><th>Accepted</th><th>Verified %</th></tr></thead><tbody>{items.map(a=><tr key={a.activity_id}><td><strong>{a.code}</strong><div>{a.name}</div></td><td><Pill value={a.link_status}/></td><td>{fmt(a.scope_quantity)} {a.unit??''}</td><td>{fmt(a.reported_quantity)}</td><td>{fmt(a.verified_quantity)}</td><td>{fmt(a.accepted_quantity)}</td><td>{fmt(a.verified_percent)}</td></tr>)}</tbody></table></div>
        {!items.length&&<p className="muted">No linked activities match. Check approved Planning source mappings.</p>}
      </section>}

      {tab==='Data quality'&&<section className="panel">
        <h3 className="section-mark"><AlertTriangle size={18} strokeWidth={2.4}/> Source quality &amp; blockers</h3>
        <p className="muted">{data.exceptions.length} visible data-quality exceptions. Correct source records in their authoritative modules; Progress does not override approvals or quantities.</p>
        {data.exceptions.length?data.exceptions.map((e,i)=><p key={i} className="note-card note-alert">{e}</p>):<p className="note-card note-good">No source-mapping exceptions detected in this snapshot.</p>}
      </section>}

      {tab==='Reports'&&<ProgressReports project={project} userId={session.user.id} canPrepare={session.user.organization_admin||session.memberships.some(m=>m.project_id===project&&m.permissions?.includes('planning.manage'))}/>}
    </>}
  </>;
}
