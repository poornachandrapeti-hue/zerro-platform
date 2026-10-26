import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { ArrowLeft, BadgeCheck, BellRing, ClipboardList, FileSpreadsheet, FileText, GitBranch, Layers, Link2, ListChecks, PenLine, Plus, RefreshCw, ScrollText, Search, Waypoints } from 'lucide-react';
import { api, downloadFile } from './api';
import type { Page, Project, Session } from './types';
import { ContractWorkflowPanels } from './contractWorkflowPanels';

type C = {id:number;number:string;title:string;contract_type:string;scope:string;lifecycle:string;approval_state:string;current_version:number;counterparty_company_id:number;contracting_company_id:number;currency?:string;original_value?:string};
type Stage={step_no:number;label:string;reviewer_user_id:number;status:string;decided_at:string|null};
type EligibleUser={id:number;name:string};
type Delegation={id:number;delegator_user_id:number;delegate_user_id:number;valid_from:string;valid_until:string;revoked_at:string|null;status:string};
type Obligation={id:number;number:string;description:string;status:string;owner_user_id:number;trigger_name:string|null;trigger_at:string|null;due_days:number|null;due_at:string|null;deadline_unresolved:boolean;overdue:boolean;evidence:string|null;required_evidence:string|null};
type ObligationAlert={obligation_id:number;contract_id:number;number:string;kind:string;due_at:string|null;owner_user_id:number};
type ObligationQueue={as_of:string;window_days:number;counts:Record<string,number>;alerts:ObligationAlert[]};
type ScopeItem={id:number;item_code:string;item_type:string;description:string;responsible_company_id:number|null;responsible_user_id:number|null;reviewer_user_id:number|null;due_at:string|null;required_evidence:string|null};
type CommercialTerm={id:number;term_key:string;clause_reference:string|null;value:Record<string,unknown>};
type Intelligence={contracts_by_status?:Record<string,number>;executed_base_value_by_currency?:Record<string,string>;proposed_exposure_by_currency?:Record<string,string>;overdue_obligations?:number};
type Amendment={id:number;number:string;status:string;variation_id:number;version_id:number|null;delta_value?:string;currency?:string};
type Delivery={destination:string;status:string;receipt_reference:string|null;acknowledged_at:string|null};
type FinanceValue={linked:boolean;sync_status:string;finance_contract_id?:number;currency?:string;original_value?:string;approved_effective_value?:string;legacy_finance_original_value?:string;pending_financials_deliveries?:number};
type FinanceContract={id:number;number:string;contract_type:string;currency:string;original_value:string;status:string};
type ProcurementLink={purchase_order_id:number;contract_version_id:number;linked_at:string};
type PurchaseOrder={id:number;number:string;status:string;company:string;currency:string;issue_date:string};
type Projection={contract_id:number;amendment_id:number;destination:string;version:number;received_at:string};
type Reconciliation={contract_id:number;amendment_id:number;destination:string;status:string;version:number|null;receipt_reference:string|null};
const SCOPE_TYPES=['Included Scope','Exclusion','Deliverable','Interface Responsibility','Client Supplied','Contractor Supplied','Required Approval','Acceptance/Handover','Reporting Requirement'];
const TERM_KEYS=['pricing_basis','milestone_payment_schedule','billing_frequency','invoice_submission','payment_due_rule','advance_recovery','retention_release','approved_deductions','tax_references','warranty_defects','security_requirements','insurance_requirements'];
type ImportPreview={dry_run:boolean;created:number;valid_rows:number;rows:Array<{row:number;values:Record<string,string>;errors:string[];valid:boolean}>};
type R={id:number;category:string;number:string;summary:string;status:string;due_at:string|null;amount?:string|null;currency?:string|null};
type Tab='register'|'alerts'|'integrations'|'transfer'|'authority';
type ContractTab='overview'|'scope'|'obligations'|'workflows'|'amendments'|'links'|'records';
type TabDef<T extends string>={key:T;label:string;icon:LucideIcon;tone:string};
const TABS:TabDef<Tab>[]=[
  {key:'register',label:'Contract Register',icon:ScrollText,tone:'tone-kreg'},
  {key:'alerts',label:'Obligation Alerts',icon:BellRing,tone:'tone-kalert'},
  {key:'integrations',label:'Integrations',icon:Waypoints,tone:'tone-kint'},
  {key:'transfer',label:'Import & Export',icon:FileSpreadsheet,tone:'tone-kio'},
  {key:'authority',label:'Signing Authority',icon:PenLine,tone:'tone-ksign'},
];
const CONTRACT_TABS:TabDef<ContractTab>[]=[
  {key:'overview',label:'Overview & Approval',icon:BadgeCheck,tone:'tone-kover'},
  {key:'scope',label:'Scope & Terms',icon:Layers,tone:'tone-kscope'},
  {key:'obligations',label:'Obligations',icon:ListChecks,tone:'tone-kobl'},
  {key:'workflows',label:'Claims, Notices & Closeout',icon:ClipboardList,tone:'tone-kflow'},
  {key:'amendments',label:'Variations & Amendments',icon:GitBranch,tone:'tone-kamend'},
  {key:'links',label:'Finance & Procurement Links',icon:Link2,tone:'tone-klink'},
  {key:'records',label:'Contract Records',icon:FileText,tone:'tone-krec'},
];
const EFFECTIVE=['Executed','Active','Completed','Closed'];
const money=(values?:Record<string,string>)=>{const rows=Object.entries(values||{});return rows.length?rows.map(([c,v])=>`${c} ${v}`).join(' · '):'—'};
const when=(value:string|null|undefined)=>value?new Date(value).toLocaleString():'—';
function TabBar<T extends string>({tabs,value,onChange}:{tabs:TabDef<T>[];value:T;onChange:(key:T)=>void}){
  return <div className="proc-nav">{tabs.map(({key,label,icon:Icon,tone})=><button type="button" key={key} className={`proc-tab ${tone}${value===key?' is-on':''}`} aria-pressed={value===key} onClick={()=>onChange(key)}><Icon size={14} strokeWidth={2.4}/><span>{label}</span></button>)}</div>;
}
function Heading({icon:Icon,children}:{icon:LucideIcon;children:React.ReactNode}){
  return <h3 className="section-mark"><Icon size={18} strokeWidth={2.4}/> {children}</h3>;
}

export function ContractsHome({session,initialProjectId}:{session:Session;initialProjectId:number|null}){
  const [projects,setProjects]=useState<Project[]>([]);
  const [project,setProject]=useState<number>(initialProjectId||0);
  const [tab,setTab]=useState<Tab>('register');
  const [contractTab,setContractTab]=useState<ContractTab>('overview');
  const [query,setQuery]=useState('');
  const [stateFilter,setStateFilter]=useState('');
  const [importRows,setImportRows]=useState('');
  const [importPreview,setImportPreview]=useState<ImportPreview|null>(null);
  const [contracts,setContracts]=useState<C[]>([]);
  const [current,setCurrent]=useState<C|null>(null);
  const [records,setRecords]=useState<R[]>([]);
  const [scopeItems,setScopeItems]=useState<ScopeItem[]>([]);
  const [commercialTerms,setCommercialTerms]=useState<CommercialTerm[]>([]);
  const [selectedVersion,setSelectedVersion]=useState<number>(1);
  const [termEntryError,setTermEntryError]=useState('');
  const [obligations,setObligations]=useState<Obligation[]>([]);
  const [alertQueue,setAlertQueue]=useState<ObligationQueue|null>(null);
  const [stages,setStages]=useState<Stage[]>([]);
  const [reviewers,setReviewers]=useState<EligibleUser[]>([]);
  const [signatories,setSignatories]=useState<EligibleUser[]>([]);
  const [delegations,setDelegations]=useState<Delegation[]>([]);
  const [summary,setSummary]=useState<Intelligence|null>(null);
  const [error,setError]=useState('');const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);
  const admin=session.user.organization_admin;
  const permissions=session.memberships.filter(m=>m.project_id===project&&m.scope==='ALL').flatMap(m=>m.permissions||[]);
  const has=(permission:string)=>admin||permissions.includes(permission);
  const canView=has('contracts.view_summary')||has('financials.view');
  const canCreate=has('contracts.manage_draft');
  const canApprove=has('contracts.approve');
  const canSign=has('contracts.sign');
  const canActivate=has('contracts.activate');
  const canShare=has('contracts.manage_sharing');
  const canManage=has('contracts.manage_obligations');
  const canManageTerms=has('contracts.manage_terms');
  const canManageVariations=has('contracts.manage_variations');
  const canViewCommercial=has('contracts.view_commercial');
  const canSeeValues=canViewCommercial||has('financials.manage');
  const canIntegrate=has('contracts.integration_ack');
  const visibleTabs=TABS.filter(t=>(t.key!=='integrations'||canViewCommercial)&&(t.key!=='authority'||admin));
  useEffect(()=>{void api<Page<Project>>('/projects?limit=100').then(x=>{setProjects(x.items);setProject(p=>p||x.items[0]?.id||0)}).catch(e=>setError((e as Error).message));},[]);
  useEffect(()=>{if(initialProjectId)setProject(initialProjectId);},[initialProjectId]);
  function resetContract(){setCurrent(null);setRecords([]);setObligations([]);setStages([]);setDelegations([]);setScopeItems([]);setCommercialTerms([]);setContractTab('overview')}
  async function refresh(id=project){if(!id||!canView)return;setBusy(true);try{
    const rows=await api<C[]>(`/projects/${id}/contracts`);
    setContracts(rows);setError('');
    void api<Intelligence>(`/projects/${id}/contracts/intelligence`).then(setSummary).catch(()=>setSummary(null));
    void api<ObligationQueue>(`/projects/${id}/contracts/obligation-alerts`).then(setAlertQueue).catch(()=>setAlertQueue(null));
    await loadEligible(id);
    if(current){const selected=rows.find(x=>x.id===current.id);setCurrent(selected||null);if(selected){setRecords(await api<R[]>(`/projects/${id}/contracts/${selected.id}/records`));await loadStages(id,selected.id);await loadDelegations(id,selected.id);await loadObligations(id,selected.id);await loadScopeTerms(id,selected.id,selected.current_version);}}
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  useEffect(()=>{setContracts([]);setSummary(null);setAlertQueue(null);setReviewers([]);setSignatories([]);resetContract();void refresh();},[project,canView]);
  async function loadScopeTerms(pid:number,cid:number,version:number){
    setScopeItems(await api<ScopeItem[]>(`/projects/${pid}/contracts/${cid}/scope-items?version=${version}`));
    if(canViewCommercial)setCommercialTerms(await api<CommercialTerm[]>(`/projects/${pid}/contracts/${cid}/commercial-terms?version=${version}`));
    else setCommercialTerms([]);
  }
  async function loadObligations(pid:number,cid:number){setObligations(await api<Obligation[]>(`/projects/${pid}/contracts/${cid}/obligations`));}
  async function loadEligible(pid:number){
    if(canApprove)setReviewers(await api<EligibleUser[]>(`/projects/${pid}/contracts/eligible-users?kind=review`));
    if(canSign)setSignatories(await api<EligibleUser[]>(`/projects/${pid}/contracts/eligible-users?kind=sign`));
  }
  async function loadDelegations(pid:number,cid:number){
    if(canSign) setDelegations(await api<Delegation[]>(`/projects/${pid}/contracts/${cid}/signing-delegations`));
    else setDelegations([]);
  }
  async function loadStages(pid:number,cid:number){setStages(await api<Stage[]>(`/projects/${pid}/contracts/${cid}/review-route`));}
  async function select(c:C){setCurrent(c);setContractTab('overview');setTab('register');try{setRecords(await api<R[]>(`/projects/${project}/contracts/${c.id}/records`));await loadStages(project,c.id);await loadDelegations(project,c.id);await loadObligations(project,c.id);setSelectedVersion(c.current_version);await loadScopeTerms(project,c.id,c.current_version)}catch(e){setError((e as Error).message)}}
  async function action(path:string,body:unknown,method:'POST'|'PUT'='POST'){setBusy(true);setNotice('');try{await api(`/projects/${project}/contracts${path}`,method,body);await refresh();setError('');setNotice('Saved successfully')}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  const needle=query.trim().toLowerCase();
  const shown=contracts.filter(c=>(!stateFilter||c.lifecycle===stateFilter)&&(!needle||[c.number,c.title,c.contract_type,c.lifecycle].some(v=>v.toLowerCase().includes(needle))));
  const lifecycles=[...new Set(contracts.map(c=>c.lifecycle))];
  const contractNumber=(id:number)=>contracts.find(c=>c.id===id)?.number||`#${id}`;
  const cards=[
    {label:'Contracts',value:String(contracts.length),hint:'In this project register',tone:'info'},
    {label:'Effective',value:String(contracts.filter(c=>EFFECTIVE.includes(c.lifecycle)).length),hint:'Executed, active or completed',tone:'good'},
    {label:'In review',value:String(contracts.filter(c=>c.approval_state==='Pending Review'||c.lifecycle==='Awaiting Signature').length),hint:'Pending approval or signature',tone:'warn'},
    {label:'Overdue obligations',value:alertQueue?String(alertQueue.counts.overdue??0):'—',hint:alertQueue?`${alertQueue.counts.upcoming??0} due within ${alertQueue.window_days} days`:'Obligation queue unavailable',tone:alertQueue?.counts.overdue?'bad':'good'},
    ...(canSeeValues?[{label:'Executed value',value:money(summary?.executed_base_value_by_currency),hint:`Proposed exposure: ${money(summary?.proposed_exposure_by_currency)}`,tone:'info'}]:[]),
  ];
  return <section className="panel">
    <h2>Contracts Management</h2>
    <p className="muted">Authoritative contract versions, internal decisions and partner publication · Financial settlement remains in Financials</p>
    <div className="toolbar">
      <select aria-label="Project" value={project||''} onChange={e=>setProject(Number(e.target.value)||0)}><option value="">Choose project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}</select>
      <button type="button" onClick={()=>void refresh()} disabled={busy||!project}><RefreshCw size={15}/> Refresh</button>
    </div>
    {error&&<div role="alert" className="error">{error}</div>}
    {notice&&<div role="status" className="success">{notice}</div>}
    {!project?<p className="muted">Select a project to manage its contracts.</p>:!canView?<p className="muted">You do not have Contracts access for this project. A full-project role with Contracts or Financials view permission is required.</p>:<>
      <div className="mp-week">{cards.map(card=><div key={card.label} className={`mp-week-card is-${card.tone}`}><span>{card.label}</span><strong>{card.value}</strong><small>{card.hint}</small></div>)}</div>
      <TabBar tabs={visibleTabs} value={tab} onChange={key=>{setTab(key);setNotice('')}}/>

      {tab==='register'&&!current&&<section>
        <div className="hr-toolbar"><Heading icon={ScrollText}>Contract Register</Heading>
          <label className="mp-search"><Search size={15}/><input aria-label="Search contracts" placeholder="Search number, title, type or state" value={query} onChange={e=>setQuery(e.target.value)}/></label>
          <select aria-label="Filter by state" value={stateFilter} onChange={e=>setStateFilter(e.target.value)}><option value="">All states</option>{lifecycles.map(s=><option key={s} value={s}>{s}</option>)}</select>
        </div>
        {canCreate&&<details><summary>Create contract draft</summary><form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);void action('',{number:d.get('number'),title:d.get('title'),contract_type:d.get('contract_type'),contracting_company_id:Number(d.get('contracting_company_id')),counterparty_company_id:Number(d.get('counterparty_company_id')),manager_user_id:Number(d.get('manager_user_id')),scope:d.get('scope'),currency:d.get('currency')||null,original_value:d.get('original_value')||null,effective_at:d.get('effective_at')||null})}}>
          <label>Contract number<input name="number" required/></label><label>Title<input name="title" minLength={3} required/></label><label>Type<select name="contract_type">{['Client','Subcontract','Service','Framework','Other'].map(x=><option key={x}>{x}</option>)}</select></label>
          <label>Contracting company ID<input name="contracting_company_id" required type="number" min={1}/></label><label>Counterparty company ID<input name="counterparty_company_id" required type="number" min={1}/></label><label>Contract Manager user ID<input name="manager_user_id" required type="number" min={1}/></label>
          <label className="wide">Scope<input name="scope" minLength={5} required/></label><label>Currency<input name="currency" placeholder="INR" maxLength={3}/></label><label>Original value<input name="original_value" type="number" step="0.01" min={0}/></label><label>Effective from<input name="effective_at" type="datetime-local"/></label>
          <button className="primary" disabled={busy}><Plus size={14}/> Create draft</button>
        </form></details>}
        {shown.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Number</th><th>Title</th><th>Type</th><th>Counterparty</th>{canSeeValues&&<th>Value</th>}<th>State</th><th>Approval</th><th>Version</th><th>Action</th></tr></thead><tbody>{shown.map(c=><tr key={c.id}><td><strong>{c.number}</strong></td><td>{c.title}</td><td>{c.contract_type}</td><td>#{c.counterparty_company_id}</td>{canSeeValues&&<td>{c.original_value?`${c.currency||''} ${c.original_value}`:'—'}</td>}<td>{c.lifecycle}</td><td>{c.approval_state}</td><td>v{c.current_version}</td><td><button type="button" onClick={()=>void select(c)}>Open</button></td></tr>)}</tbody></table></div>:<p className="muted">{contracts.length?'No contract matches these filters.':canCreate?'No contracts yet. Use “Create contract draft” to add the first one.':'No contracts are registered for this project yet.'}</p>}
      </section>}

      {tab==='register'&&current&&<section>
        <div className="hr-toolbar"><button type="button" onClick={resetContract}><ArrowLeft size={15}/> Back to register</button><Heading icon={ScrollText}>{current.number} — {current.title}</Heading></div>
        <p className="muted">{current.contract_type} · {current.lifecycle} · {current.approval_state} · Version {current.current_version}{current.original_value?` · ${current.currency||''} ${current.original_value}`:''}</p>
        <TabBar tabs={CONTRACT_TABS.filter(t=>t.key!=='links'||canViewCommercial)} value={contractTab} onChange={setContractTab}/>

        {contractTab==='overview'&&<section>
          <p>{current.scope}</p>
          <div className="proc-nav">
            {canCreate&&current.lifecycle==='Draft'&&<button className="primary" disabled={busy} onClick={()=>void action(`/${current.id}/submit`,{reason:window.prompt('Review submission rationale (8+ characters)')||'Submitted for internal review'})}>Submit Review</button>}
            {canApprove&&current.approval_state==='Pending Review'&&<button className="primary" disabled={busy} onClick={()=>void action(`/${current.id}/approve`,{reason:window.prompt('Approval reason (8+ characters)')||'Reviewed and approved'})}>Approve Internally</button>}
            {canSign&&current.lifecycle==='Awaiting Signature'&&<button className="primary" disabled={busy} onClick={()=>{const evidence=window.prompt('Signed execution evidence reference');if(evidence)void action(`/${current.id}/execute`,{reason:'Execution evidence verified',evidence})}}>Record Execution</button>}
            {canActivate&&current.lifecycle==='Executed'&&<button className="primary" disabled={busy} onClick={()=>void action(`/${current.id}/activate`,{reason:'Activation prerequisites verified'})}>Activate</button>}
            {canShare&&['Executed','Active'].includes(current.lifecycle)&&<button disabled={busy} onClick={()=>void action(`/${current.id}/partner-shares`,{company_id:current.counterparty_company_id,can_submit:true})}>Publish to Counterparty</button>}
          </div>
          {canApprove&&current.lifecycle==='Draft'&&<details><summary>Configure review hierarchy</summary><p className="muted">Select reviewers in the required order. Each reviewer must hold Contracts Approve permission for this project.</p><form className="contact-form plan-form" onSubmit={async e=>{e.preventDefault();const ids=Array.from(e.currentTarget.querySelector<HTMLSelectElement>('select[name=reviewers]')?.selectedOptions||[]).map(x=>Number(x.value));if(!ids.length||ids.some(x=>!Number.isInteger(x)||x<=0)||new Set(ids).size!==ids.length){setError('Select at least one unique reviewer');return}await action(`/${current.id}/review-route`,{stages:ids.map((reviewer_user_id,i)=>({label:`Stage ${i+1}`,reviewer_user_id}))},'PUT')}}><label className="wide">Ordered reviewers<select name="reviewers" required multiple size={Math.min(7,Math.max(2,reviewers.length))}>{reviewers.map(u=><option key={u.id} value={u.id}>{u.name} (#{u.id})</option>)}</select></label><button className="primary" disabled={busy}>Save review route</button></form></details>}
          {stages.length>0&&<><h4>Review hierarchy — version {current.current_version}</h4><div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Step</th><th>Reviewer</th><th>Status</th><th>Decision</th></tr></thead><tbody>{stages.map(stage=><tr key={stage.step_no}><td>{stage.step_no}: {stage.label}</td><td>{reviewers.find(u=>u.id===stage.reviewer_user_id)?.name||`User ${stage.reviewer_user_id}`}</td><td>{stage.status}</td><td>{canApprove&&stage.status==='Pending'&&<div className="proc-nav">{(['Approve','Return','Reject'] as const).map(decision=><button disabled={busy} key={decision} onClick={()=>{const reason=window.prompt(`${decision} reason (minimum 8 characters)`);if(reason&&reason.trim().length>=8)void action(`/${current.id}/review-stage/${stage.step_no}/decide?decision=${decision}`,{reason});else if(reason!==null)setError('Reason must contain at least 8 characters')}}>{decision}</button>)}</div>}</td></tr>)}</tbody></table></div></>}
          {canSign&&current.lifecycle==='Awaiting Signature'&&<details><summary>Delegate signing authority</summary><p className="muted">Only users holding a valid direct signing authority can delegate. Delegation is contract-specific.</p><form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);void action(`/${current.id}/signing-delegations`,{delegate_user_id:Number(d.get('delegate_user_id')),valid_from:new Date(String(d.get('valid_from'))).toISOString(),valid_until:new Date(String(d.get('valid_until'))).toISOString()})}}><label>Delegate<select name="delegate_user_id" required defaultValue=""><option value="" disabled>Choose project signatory</option>{signatories.map(u=><option key={u.id} value={u.id}>{u.name} (#{u.id})</option>)}</select></label><label>Valid from<input name="valid_from" required type="datetime-local"/></label><label>Valid until<input name="valid_until" required type="datetime-local"/></label><button className="primary" disabled={busy}>Delegate</button></form>
            <h4>Signing delegations</h4><div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Delegator</th><th>Delegate</th><th>Valid until</th><th>Status</th><th>Action</th></tr></thead><tbody>{delegations.map(d=><tr key={d.id}><td>{signatories.find(u=>u.id===d.delegator_user_id)?.name||`User ${d.delegator_user_id}`}</td><td>{signatories.find(u=>u.id===d.delegate_user_id)?.name||`User ${d.delegate_user_id}`}</td><td>{when(d.valid_until)}</td><td>{d.status}</td><td>{!d.revoked_at&&<button disabled={busy} onClick={()=>{if(window.confirm('Revoke this signing delegation?'))void action(`/${current.id}/signing-delegations/${d.id}/revoke`,{})}}>Revoke</button>}</td></tr>)}</tbody></table></div></details>}
        </section>}

        {contractTab==='scope'&&<section aria-label="Scope and responsibility matrix">
          <div className="hr-toolbar"><Heading icon={Layers}>Scope &amp; Responsibility Matrix</Heading><select aria-label="Contract version" value={selectedVersion} onChange={e=>{const next=Number(e.target.value);setSelectedVersion(next);void loadScopeTerms(project,current.id,next).catch(err=>setError((err as Error).message))}}>{Array.from({length:current.current_version},(_,i)=>i+1).map(v=><option key={v} value={v}>Version {v}</option>)}</select></div>
          <p className="muted">Version-bound scope, deliverables and assigned responsibilities. Responsibility does not grant project access.</p>
          {canManageTerms&&current.lifecycle==='Draft'&&selectedVersion===current.current_version&&<details><summary>Add versioned scope or responsibility</summary><form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);const optionalId=(name:string)=>d.get(name)?Number(d.get(name)):null;void action(`/${current.id}/scope-items`,{item_code:d.get('item_code'),item_type:d.get('item_type'),description:d.get('description'),responsible_company_id:optionalId('responsible_company_id'),responsible_user_id:optionalId('responsible_user_id'),reviewer_user_id:optionalId('reviewer_user_id'),due_at:d.get('due_at')?new Date(String(d.get('due_at'))).toISOString():null,required_evidence:d.get('required_evidence')||null})}}>
            <label>Item code<input name="item_code" required maxLength={80}/></label><label>Type<select name="item_type">{SCOPE_TYPES.map(x=><option key={x}>{x}</option>)}</select></label><label className="wide">Description<input name="description" required minLength={3}/></label>
            <label>Responsible company<select name="responsible_company_id" defaultValue=""><option value="">Not assigned</option><option value={current.contracting_company_id}>Contracting company #{current.contracting_company_id}</option><option value={current.counterparty_company_id}>Counterparty #{current.counterparty_company_id}</option></select></label>
            <label>Owner<select name="responsible_user_id" defaultValue=""><option value="">Not assigned</option>{reviewers.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select></label><label>Reviewer<select name="reviewer_user_id" defaultValue=""><option value="">Not assigned</option>{reviewers.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select></label>
            <label>Due at<input type="datetime-local" name="due_at"/></label><label>Required evidence<input name="required_evidence"/></label><button className="primary" disabled={busy}><Plus size={14}/> Add scope entry</button>
          </form></details>}
          {canManageTerms&&(current.lifecycle!=='Draft'||selectedVersion!==current.current_version)&&<p role="status" className="muted">This version is locked. Scope changes require a controlled new draft or amendment.</p>}
          <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Code</th><th>Type</th><th>Description</th><th>Responsible company</th><th>Owner</th><th>Reviewer</th><th>Due</th><th>Evidence</th></tr></thead><tbody>{scopeItems.map(item=><tr key={item.id}><td>{item.item_code}</td><td>{item.item_type}</td><td>{item.description}</td><td>{item.responsible_company_id?`#${item.responsible_company_id}`:'—'}</td><td>{item.responsible_user_id??'—'}</td><td>{item.reviewer_user_id??'—'}</td><td>{item.due_at?when(item.due_at):'Unspecified'}</td><td>{item.required_evidence||'—'}</td></tr>)}{scopeItems.length===0&&<tr><td colSpan={8}>No scope entries for this version.</td></tr>}</tbody></table></div>
          {canViewCommercial&&<>
            <h4>Commercial Terms — Version {selectedVersion}</h4><p className="muted">Structured contractual rules only. Financial settlements and postings remain in Financials.</p>
            {canManageTerms&&current.lifecycle==='Draft'&&selectedVersion===current.current_version&&<details><summary>Add commercial term</summary><form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);try{const parsed:unknown=JSON.parse(String(d.get('value')));if(!parsed||typeof parsed!=='object'||Array.isArray(parsed)||Object.keys(parsed).length===0)throw new Error('Value must be a nonempty JSON object');setTermEntryError('');void action(`/${current.id}/commercial-terms`,{term_key:d.get('term_key'),clause_reference:d.get('clause_reference')||null,value:parsed})}catch(err){setTermEntryError((err as Error).message)}}}><label>Term<select name="term_key">{TERM_KEYS.map(t=><option key={t} value={t}>{t.replaceAll('_',' ')}</option>)}</select></label><label>Clause reference<input name="clause_reference"/></label><label className="wide">Structured term value (JSON object)<textarea name="value" rows={3} required defaultValue={'{"rule":""}'}/></label>{termEntryError&&<p role="alert" className="error">{termEntryError}</p>}<button className="primary" disabled={busy}>Save term</button></form></details>}
            {(current.lifecycle!=='Draft'||selectedVersion!==current.current_version)&&<p role="status" className="muted">Commercial terms are locked for this version.</p>}
            <div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Term</th><th>Clause</th><th>Structured value</th></tr></thead><tbody>{commercialTerms.map(t=><tr key={t.id}><td>{t.term_key.replaceAll('_',' ')}</td><td>{t.clause_reference||'—'}</td><td><code style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(t.value)}</code></td></tr>)}{commercialTerms.length===0&&<tr><td colSpan={3}>No terms recorded for this version.</td></tr>}</tbody></table></div>
          </>}
        </section>}

        {contractTab==='obligations'&&<section aria-label="Contractual obligations">
          <Heading icon={ListChecks}>Contractual Obligations</Heading>
          <p className="muted">Obligations have separate owners, trigger dates and evidence decisions. An unknown deadline is not overdue.</p>
          {canManage&&<details><summary>Add contractual obligation</summary><form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);const triggerAt=String(d.get('trigger_at')||'');void action(`/${current.id}/obligations`,{number:d.get('number'),description:d.get('description'),clause_reference:d.get('clause_reference')||null,responsible_company_id:Number(d.get('responsible_company_id')),owner_user_id:Number(d.get('owner_user_id')),trigger_name:d.get('trigger_name')||null,trigger_at:triggerAt?new Date(triggerAt).toISOString():null,due_days:d.get('due_days')!==''?Number(d.get('due_days')):null,required_evidence:d.get('required_evidence')||null})}}>
            <label>Obligation number<input required name="number"/></label><label className="wide">Description<input required name="description" minLength={5}/></label><label>Clause reference<input name="clause_reference"/></label>
            <label>Responsible company<select name="responsible_company_id" required><option value="">Select</option><option value={current.counterparty_company_id}>Counterparty #{current.counterparty_company_id}</option><option value={current.contracting_company_id}>Contracting company #{current.contracting_company_id}</option></select></label>
            <label>Internal owner (user ID)<input required name="owner_user_id" type="number" min={1}/></label>
            <label>Trigger event<input name="trigger_name"/></label><label>Trigger date/time<input name="trigger_at" type="datetime-local"/></label><label>Days after trigger<input name="due_days" type="number" min={0}/></label>
            <label>Required evidence<input name="required_evidence"/></label><button className="primary" disabled={busy}><Plus size={14}/> Create obligation</button>
          </form></details>}
          {obligations.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Number</th><th>Description</th><th>Owner</th><th>State</th><th>Due</th><th>Action</th></tr></thead><tbody>{obligations.map(o=><tr key={o.id}><td>{o.number}</td><td>{o.description}</td><td>User {o.owner_user_id}</td><td>{o.overdue?'Overdue · ':''}{o.status}</td><td>{o.deadline_unresolved?'Unresolved':when(o.due_at)}</td><td><div className="proc-nav">
            {canManage&&!o.trigger_at&&o.trigger_name&&<button disabled={busy} onClick={()=>{const evidence=window.prompt('Trigger evidence');if(evidence)void action(`/${current.id}/obligations/${o.id}/trigger`,{trigger_at:new Date().toISOString(),evidence})}}>Record trigger</button>}
            {canManage&&['Not Started','In Progress','Overdue'].includes(o.status)&&<button disabled={busy} onClick={()=>{const evidence=window.prompt('Submission evidence reference');if(evidence)void action(`/${current.id}/obligations/${o.id}/submit`,{evidence})}}>Submit evidence</button>}
            {canApprove&&['Submitted','Not Started','In Progress'].includes(o.status)&&<button disabled={busy} onClick={()=>{const decision=window.prompt('Decision: Accepted, Returned, Waived, Cancelled');if(!decision||!['Accepted','Returned','Waived','Cancelled'].includes(decision))return;const reason=window.prompt('Decision rationale');const evidence=window.prompt('Decision evidence');if(reason&&evidence)void action(`/${current.id}/obligations/${o.id}/decide`,{decision,reason,evidence})}}>Review</button>}
          </div></td></tr>)}</tbody></table></div>:<p className="muted">No obligations recorded for this contract.</p>}
        </section>}

        {contractTab==='workflows'&&<ContractWorkflowPanels key={current.id} project={project} contractId={current.id} canDraft={canCreate} canManageVariations={canManageVariations} canIssueNotice={has('contracts.issue_notice')} canApprove={canApprove} canCommercial={canViewCommercial} canManageTerms={canManageTerms} canManageObligations={canManage} canClose={has('contracts.close')} onError={setError}/>}

        {contractTab==='amendments'&&<ContractAmendments key={current.id} project={project} contract={current} records={records} canManageVariations={canManageVariations} canApprove={canApprove} canSign={canSign} canCommercial={canViewCommercial} canIntegrate={canIntegrate} onChanged={()=>void refresh()} onError={setError}/>}

        {contractTab==='links'&&canViewCommercial&&<ContractLinks key={current.id} project={project} contract={current} canIntegrate={canIntegrate} onError={setError}/>}

        {contractTab==='records'&&<section>
          <Heading icon={FileText}>Contract Records</Heading>
          <p className="muted">Variations, claims, notices and other contract records. Internal acceptance of a variation does not change contract value; an executed amendment is required.</p>
          {(canManage||canManageVariations)&&<details><summary>Add contract record</summary><form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);void action(`/${current.id}/records`,{category:d.get('category'),number:d.get('number'),summary:d.get('summary'),evidence:d.get('evidence')||null,due_at:d.get('due_at')||null,amount:d.get('amount')||null,currency:d.get('amount')?(d.get('currency')||current.currency||null):null})}}><label>Category<select name="category">{['obligation','claim','variation','notice','security','correspondence','closeout','warranty','responsibility','term'].map(x=><option key={x}>{x}</option>)}</select></label><label>Reference number<input required name="number"/></label><label className="wide">Description<input name="summary" required minLength={5}/></label><label>Evidence reference<input name="evidence"/></label><label>Due<input name="due_at" type="datetime-local"/></label>{canViewCommercial&&<><label>Amount<input name="amount" type="number" min={0} step="0.01"/></label><label>Currency<input name="currency" maxLength={3} placeholder={current.currency||'INR'}/></label></>}<button className="primary" disabled={busy}><Plus size={14}/> Add record</button></form></details>}
          {records.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Category</th><th>Number</th><th>Summary</th>{canSeeValues&&<th>Amount</th>}<th>Status</th><th>Due</th><th>Action</th></tr></thead><tbody>{records.map(r=><tr key={r.id}><td>{r.category}</td><td>{r.number}</td><td>{r.summary}</td>{canSeeValues&&<td>{r.amount?`${r.currency||''} ${r.amount}`:'—'}</td>}<td>{r.status}</td><td>{r.due_at?when(r.due_at):'Unspecified'}</td><td><div className="proc-nav">
            {canApprove&&['Draft','Submitted'].includes(r.status)&&(['Accepted','Returned','Rejected'] as const).map(decision=><button key={decision} disabled={busy} onClick={()=>{const reason=window.prompt(`${decision} reason (8+ characters)`);if(reason&&reason.trim().length>=8)void action(`/${current.id}/records/${r.id}/decide?decision=${decision}`,{reason});else if(reason!==null)setError('Reason must contain at least 8 characters')}}>{decision==='Accepted'?'Accept':decision==='Returned'?'Return':'Reject'}</button>)}
            {canManageVariations&&r.category==='variation'&&r.status==='Approved Internally'&&<button disabled={busy} onClick={()=>{const agreement_reference=window.prompt('Counterparty agreement reference');const evidence=window.prompt('Agreement evidence (8+ characters)');if(agreement_reference&&evidence)void action(`/${current.id}/variations/${r.id}/counterparty-agreement`,{agreement_reference,evidence,agreed_at:new Date().toISOString()})}}>Record counterparty agreement</button>}
          </div></td></tr>)}</tbody></table></div>:<p className="muted">No records for this contract yet.</p>}
        </section>}
      </section>}

      {tab==='alerts'&&<section>
        <Heading icon={BellRing}>Obligation Alert Queue</Heading>
        <p className="muted">Read-only queue of overdue, upcoming and unresolved obligations. Notifications are not dispatched from here.</p>
        {!alertQueue?<p className="muted">Obligation queue unavailable.</p>:alertQueue.alerts.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Obligation</th><th>Contract</th><th>Kind</th><th>Due</th><th>Owner</th></tr></thead><tbody>{alertQueue.alerts.map(a=><tr key={a.obligation_id}><td>{a.number}</td><td>{contractNumber(a.contract_id)}</td><td>{a.kind}</td><td>{a.due_at?when(a.due_at):'Unresolved'}</td><td>User {a.owner_user_id}</td></tr>)}</tbody></table></div>:<p className="muted">No overdue, upcoming or unresolved obligations in the next {alertQueue.window_days} days.</p>}
      </section>}

      {tab==='integrations'&&canViewCommercial&&<ProjectIntegrations project={project} contractNumber={contractNumber} onError={setError}/>}

      {tab==='transfer'&&<section aria-label="Contract data transfer">
        <Heading icon={FileSpreadsheet}>Contract Import &amp; Export</Heading>
        <p className="muted">Import validation is preview-only. No contracts or master records are created.</p>
        <div className="proc-nav"><button className="primary" disabled={busy} onClick={()=>{void downloadFile(`/projects/${project}/contracts/export.csv`,`contracts-project-${project}.csv`).catch(e=>setError((e as Error).message))}}><FileSpreadsheet size={14}/> Export contract register (CSV)</button></div>
        {canCreate&&<details open><summary>Validate contract import rows</summary>
          <p className="muted">Paste a JSON array of mapped contract rows. Required fields: number, title, contract_type, contracting_company_id, counterparty_company_id, manager_user_id, scope, currency and original_value.</p>
          <textarea aria-label="Mapped import rows (JSON)" value={importRows} onChange={e=>{setImportRows(e.target.value);setImportPreview(null)}} rows={5} style={{width:'100%'}} placeholder={'[{"number":"CON-001","title":"Example agreement","contract_type":"Client","contracting_company_id":1,"counterparty_company_id":2,"manager_user_id":3,"scope":"Civil works","currency":"INR","original_value":"10000"}]'}/>
          <div className="proc-nav"><button className="primary" disabled={busy||!importRows.trim()} onClick={()=>{void (async()=>{setBusy(true);try{const parsed:unknown=JSON.parse(importRows);if(!Array.isArray(parsed))throw new Error('Expected a JSON array of contract rows');const result=await api<ImportPreview>(`/projects/${project}/contracts/import-preview`,'POST',{rows:parsed});setImportPreview(result);setError('')}catch(e){setError((e as Error).message);setImportPreview(null)}finally{setBusy(false)}})()}}>Validate preview</button></div>
          {importPreview&&<><p role="status" className="muted">{importPreview.valid_rows} valid of {importPreview.rows.length}; 0 created (preview only)</p><div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Row</th><th>Contract</th><th>Status</th><th>Validation issues</th></tr></thead><tbody>{importPreview.rows.map(r=><tr key={r.row}><td>{r.row}</td><td>{r.values.number||'—'}</td><td>{r.valid?'Valid':'Invalid'}</td><td>{r.errors.join('; ')||'—'}</td></tr>)}</tbody></table></div></>}
        </details>}
      </section>}

      {tab==='authority'&&admin&&<section>
        <Heading icon={PenLine}>Signing Authority</Heading>
        <p className="muted">Grant a project user authority to sign contracts up to a value limit for a period. Only eligible project signatories are listed.</p>
        <form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);void action('/signing-authorities',{user_id:Number(d.get('user_id')),currency:d.get('currency'),max_value:d.get('max_value'),valid_from:new Date(String(d.get('valid_from'))).toISOString(),valid_until:new Date(String(d.get('valid_until'))).toISOString()})}}><label>Signatory<select name="user_id" required defaultValue=""><option value="" disabled>Choose authorized project user</option>{signatories.map(u=><option key={u.id} value={u.id}>{u.name} (#{u.id})</option>)}</select></label><label>Currency<input name="currency" required pattern="[A-Z]{3}" defaultValue="INR"/></label><label>Maximum value<input name="max_value" type="number" min={0} step="0.01" required/></label><label>Valid from<input name="valid_from" type="datetime-local" required/></label><label>Valid until<input name="valid_until" type="datetime-local" required/></label><button className="primary" disabled={busy}>Save authority</button></form>
        {!signatories.length&&<p className="muted">No project users currently hold Contracts Sign permission.</p>}
      </section>}
    </>}
  </section>;
}

function ContractAmendments({project,contract,records,canManageVariations,canApprove,canSign,canCommercial,canIntegrate,onChanged,onError}:{project:number;contract:C;records:R[];canManageVariations:boolean;canApprove:boolean;canSign:boolean;canCommercial:boolean;canIntegrate:boolean;onChanged:()=>void;onError:(message:string)=>void}){
  const [rows,setRows]=useState<Amendment[]>([]);
  const [open,setOpen]=useState<number|null>(null);
  const [deliveries,setDeliveries]=useState<Delivery[]>([]);
  const [busy,setBusy]=useState(false);
  const base=`/projects/${project}/contracts/${contract.id}`;
  async function load(){try{setRows(await api<Amendment[]>(base+'/amendments'))}catch(e){onError((e as Error).message)}}
  async function loadDeliveries(aid:number){setOpen(aid);try{setDeliveries(await api<Delivery[]>(base+`/amendments/${aid}/deliveries`))}catch(e){setDeliveries([]);onError((e as Error).message)}}
  useEffect(()=>{void load()},[base]);
  async function mutate(path:string,body:unknown){setBusy(true);try{await api(base+path,'POST',body);await load();if(open)await loadDeliveries(open);onChanged();onError('')}catch(e){onError((e as Error).message)}finally{setBusy(false)}}
  const agreed=records.filter(r=>r.category==='variation'&&r.status==='Agreed - Pending Amendment');
  return <section>
    <Heading icon={GitBranch}>Variations &amp; Amendments</Heading>
    <p className="muted">A variation becomes an amendment only after internal approval and recorded counterparty agreement (see Contract Records). An executed amendment creates a new contract version and notifies Financials, Planning and Command Center.</p>
    {canManageVariations&&['Executed','Active'].includes(contract.lifecycle)&&<details><summary>Prepare amendment from agreed variation</summary>{agreed.length?<form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);void mutate('/amendments',{variation_id:Number(d.get('variation_id')),amendment_number:d.get('amendment_number')})}}><label>Agreed variation<select name="variation_id" required>{agreed.map(v=><option key={v.id} value={v.id}>{v.number} — {v.summary}</option>)}</select></label><label>Amendment number<input name="amendment_number" required minLength={3}/></label><button className="primary" disabled={busy}><Plus size={14}/> Prepare amendment</button></form>:<p className="muted">No variation is awaiting amendment. Variations need internal acceptance and recorded counterparty agreement first.</p>}</details>}
    {rows.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Amendment</th><th>Status</th><th>Variation</th>{canCommercial&&<th>Change</th>}<th>Action</th></tr></thead><tbody>{rows.map(a=><tr key={a.id}><td><strong>{a.number}</strong></td><td>{a.status}</td><td>{records.find(r=>r.id===a.variation_id)?.number||`#${a.variation_id}`}</td>{canCommercial&&<td>{a.delta_value?`${a.currency||''} ${a.delta_value}`:'—'}</td>}<td><div className="proc-nav">
      {canApprove&&a.status==='Draft'&&<button disabled={busy} onClick={()=>{const reason=window.prompt('Approval reason (8+ characters)');if(reason&&reason.trim().length>=8)void mutate(`/amendments/${a.id}/approve`,{reason})}}>Approve</button>}
      {canSign&&a.status==='Approved Internally'&&<button disabled={busy} onClick={()=>{const evidence=window.prompt('Signed amendment evidence (8+ characters)');if(evidence&&evidence.trim().length>=8)void mutate(`/amendments/${a.id}/execute`,{evidence})}}>Execute</button>}
      {canCommercial&&a.status==='Executed'&&<button disabled={busy} onClick={()=>void (open===a.id?setOpen(null):loadDeliveries(a.id))}>{open===a.id?'Hide deliveries':'Module deliveries'}</button>}
    </div></td></tr>)}</tbody></table></div>:<p className="muted">No amendments for this contract.</p>}
    {open!==null&&<><h4>Module deliveries — {rows.find(a=>a.id===open)?.number}</h4><div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Destination</th><th>Status</th><th>Receipt</th><th>Acknowledged</th><th>Action</th></tr></thead><tbody>{deliveries.map(d=><tr key={d.destination}><td>{d.destination}</td><td>{d.status}</td><td>{d.receipt_reference||'—'}</td><td>{when(d.acknowledged_at)}</td><td>{canIntegrate&&d.status!=='Acknowledged'&&['Financials','Planning'].includes(d.destination)&&<button disabled={busy} onClick={()=>void mutate(`/amendments/${open}/consume/${d.destination}`,{})}>Receive into {d.destination}</button>}</td></tr>)}</tbody></table></div><p className="muted">Receiving records a read-only projection for the destination module. It does not post to Financials or change a Planning baseline.</p></>}
  </section>;
}

function ContractLinks({project,contract,canIntegrate,onError}:{project:number;contract:C;canIntegrate:boolean;onError:(message:string)=>void}){
  const [finance,setFinance]=useState<FinanceValue|null>(null);
  const [financeContracts,setFinanceContracts]=useState<FinanceContract[]>([]);
  const [links,setLinks]=useState<ProcurementLink[]>([]);
  const [orders,setOrders]=useState<PurchaseOrder[]>([]);
  const [busy,setBusy]=useState(false);
  const base=`/projects/${project}/contracts/${contract.id}/integrations`;
  const effective=EFFECTIVE.includes(contract.lifecycle);
  async function load(){
    await Promise.all([
      api<FinanceValue>(base+'/finance-effective-value').then(setFinance).catch(e=>{setFinance(null);onError((e as Error).message)}),
      api<ProcurementLink[]>(base+'/procurement-links').then(setLinks).catch(e=>{setLinks([]);onError((e as Error).message)}),
    ]);
    if(canIntegrate){
      void api<FinanceContract[]>(`/projects/${project}/financials/contracts`).then(setFinanceContracts).catch(()=>setFinanceContracts([]));
      void api<PurchaseOrder[]>(`/projects/${project}/procurement/orders`).then(setOrders).catch(()=>setOrders([]));
    }
  }
  useEffect(()=>{void load()},[base,canIntegrate]);
  async function mutate(path:string,body:unknown){setBusy(true);try{await api(base+path,'POST',body);await load();onError('')}catch(e){onError((e as Error).message)}finally{setBusy(false)}}
  const linkable=orders.filter(o=>o.issue_date&&!['Draft','Cancelled'].includes(o.status)&&!links.some(l=>l.purchase_order_id===o.id));
  const matching=financeContracts.filter(f=>f.number===contract.number);
  return <section>
    <Heading icon={Link2}>Financials Link</Heading>
    <p className="muted">Links this contract to its Financials contract so the approved effective value can be reconciled. Billing records and Financials values are never modified from here.</p>
    {finance&&(finance.linked?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Financials contract</th><th>Original value</th><th>Approved effective value</th><th>Financials original value</th><th>Pending deliveries</th><th>Sync status</th></tr></thead><tbody><tr><td>#{finance.finance_contract_id}</td><td>{finance.currency} {finance.original_value}</td><td>{finance.currency} {finance.approved_effective_value}</td><td>{finance.currency} {finance.legacy_finance_original_value}</td><td>{finance.pending_financials_deliveries}</td><td>{finance.sync_status}</td></tr></tbody></table></div>:<p className="muted">Not linked to a Financials contract.</p>)}
    {finance&&!finance.linked&&canIntegrate&&(matching.length?<form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);void mutate('/finance-link',{finance_contract_id:Number(d.get('finance_contract_id'))})}}><label>Financials contract<select name="finance_contract_id" required>{matching.map(f=><option key={f.id} value={f.id}>{f.number} — {f.currency} {f.original_value} ({f.status})</option>)}</select></label><button className="primary" disabled={busy}><Link2 size={14}/> Link to Financials</button></form>:<p className="muted">No Financials contract with number {contract.number} exists in this project. Number, counterparty, currency, type and original value must match to link.</p>)}
    <Heading icon={Link2}>Procurement Purchase Orders</Heading>
    <p className="muted">Issued purchase orders governed by this contract. Linking never approves, issues or changes a purchase order.</p>
    {links.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Purchase order</th><th>Contract version</th><th>Linked</th></tr></thead><tbody>{links.map(l=><tr key={l.purchase_order_id}><td>{orders.find(o=>o.id===l.purchase_order_id)?.number||`#${l.purchase_order_id}`}</td><td>{l.contract_version_id}</td><td>{when(l.linked_at)}</td></tr>)}</tbody></table></div>:<p className="muted">No purchase orders linked.</p>}
    {canIntegrate&&(effective?(linkable.length?<form className="contact-form plan-form" onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);void mutate('/procurement-links',{purchase_order_id:Number(d.get('purchase_order_id'))})}}><label>Issued purchase order<select name="purchase_order_id" required>{linkable.map(o=><option key={o.id} value={o.id}>{o.number} — {o.company} ({o.status})</option>)}</select></label><button className="primary" disabled={busy}><Link2 size={14}/> Link purchase order</button></form>:<p className="muted">No issued, unlinked purchase orders are available. The PO vendor must be the contract counterparty and use the same currency.</p>):<p className="muted">Purchase orders can be linked once the contract is executed.</p>)}
  </section>;
}

function ProjectIntegrations({project,contractNumber,onError}:{project:number;contractNumber:(id:number)=>string;onError:(message:string)=>void}){
  const [projections,setProjections]=useState<Projection[]>([]);
  const [reconciliation,setReconciliation]=useState<Reconciliation[]>([]);
  useEffect(()=>{
    void api<Projection[]>(`/projects/${project}/contracts/integrations/consumer-projections`).then(setProjections).catch(e=>onError((e as Error).message));
    void api<Reconciliation[]>(`/projects/${project}/contracts/integrations/reconciliation`).then(setReconciliation).catch(e=>onError((e as Error).message));
  },[project]);
  const pending=reconciliation.filter(r=>r.status!=='Acknowledged').length;
  return <section>
    <Heading icon={Waypoints}>Module Integrations</Heading>
    <p className="muted">Executed amendments are delivered to Financials, Planning and Command Center. Command Center reads the Contracts intelligence summary directly with its service key.</p>
    <div className="mp-week">
      <div className="mp-week-card is-info"><span>Deliveries</span><strong>{reconciliation.length}</strong><small>Amendment events to other modules</small></div>
      <div className={`mp-week-card is-${pending?'warn':'good'}`}><span>Awaiting receipt</span><strong>{pending}</strong><small>Not yet acknowledged downstream</small></div>
      <div className="mp-week-card is-good"><span>Received</span><strong>{projections.length}</strong><small>Consumer projections recorded</small></div>
    </div>
    <h4>Delivery reconciliation</h4>
    {reconciliation.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Contract</th><th>Amendment</th><th>Destination</th><th>Version</th><th>Status</th><th>Receipt</th></tr></thead><tbody>{reconciliation.map(r=><tr key={`${r.amendment_id}-${r.destination}`}><td>{contractNumber(r.contract_id)}</td><td>#{r.amendment_id}</td><td>{r.destination}</td><td>{r.version??'—'}</td><td>{r.status}</td><td>{r.receipt_reference||'—'}</td></tr>)}</tbody></table></div>:<p className="muted">No amendment deliveries yet. Deliveries are created when an amendment is executed.</p>}
    <h4>Consumer projections</h4>
    {projections.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Contract</th><th>Amendment</th><th>Destination</th><th>Version</th><th>Received</th></tr></thead><tbody>{projections.map(p=><tr key={`${p.amendment_id}-${p.destination}`}><td>{contractNumber(p.contract_id)}</td><td>#{p.amendment_id}</td><td>{p.destination}</td><td>{p.version}</td><td>{when(p.received_at)}</td></tr>)}</tbody></table></div>:<p className="muted">No module has received a contract amendment yet.</p>}
  </section>;
}

type PartnerContract = {id:number;number:string;title:string;status:string;version:number};
type PartnerDocument = {id:number;document_key:string;revision:string;title:string;class:string};

export function PartnerContracts(){
  const [contracts,setContracts]=useState<PartnerContract[]>([]);
  const [current,setCurrent]=useState<number|null>(null);
  const [documents,setDocuments]=useState<PartnerDocument[]>([]);
  const [loadingDocuments,setLoadingDocuments]=useState(false);
  const [downloading,setDownloading]=useState<number|null>(null);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  useEffect(()=>{void api<PartnerContract[]>('/partner/contracts').then(setContracts).catch(e=>setError((e as Error).message))},[]);
  useEffect(()=>{
    let active=true;
    setDocuments([]);setError('');
    if(current===null)return;
    setLoadingDocuments(true);
    void api<PartnerDocument[]>(`/partner/contracts/${current}/documents`)
      .then(items=>{if(active)setDocuments(items)})
      .catch(e=>{if(active)setError((e as Error).message)})
      .finally(()=>{if(active)setLoadingDocuments(false)});
    return ()=>{active=false};
  },[current]);
  async function partnerDownload(item:PartnerDocument){
    if(current===null)return;
    setDownloading(item.id);setError('');
    try{
      const safeName=(item.title||`contract-document-${item.id}`).replace(/[\\/:*?"<>|\r\n]/g,'_').slice(0,120);
      await downloadFile(`/partner/contracts/${current}/documents/${item.id}/download`,safeName);
    }catch(e){setError((e as Error).message)}
    finally{setDownloading(null)}
  }
  return <section className="panel">
    <h2>My Contracts</h2><p className="muted">Only contracts explicitly shared with your company appear here. Your submissions require internal review.</p>
    {error&&<div role="alert" className="error">{error}</div>}{notice&&<div role="status" className="success">{notice}</div>}
    {contracts.length?<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Contract</th><th>Title</th><th>Status</th><th>Version</th><th>Action</th></tr></thead><tbody>
      {contracts.map(c=><tr key={c.id}><td><strong>{c.number}</strong></td><td>{c.title}</td><td>{c.status}</td><td>v{c.version}</td><td><button type="button" onClick={()=>{setCurrent(c.id);setNotice('')}} aria-pressed={current===c.id}>Select</button></td></tr>)}
    </tbody></table></div>:<p className="muted">No contracts have been shared with your company yet.</p>}
    {current!==null&&<>
      <Heading icon={FileText}>Published contract documents</Heading>
      <p className="muted">Only currently authorized documents are listed. Each download is checked again against your company's contract access.</p>
      {loadingDocuments?<p role="status" className="muted">Loading documents…</p>:documents.length===0?<p className="muted">No documents are currently available for this contract.</p>:<div className="mp-table-wrap"><table className="mp-table"><thead><tr><th>Document</th><th>Class</th><th>Revision</th><th>Action</th></tr></thead><tbody>{documents.map(item=><tr key={item.id}><td>{item.title}</td><td>{item.class}</td><td>{item.revision}</td><td><button type="button" disabled={downloading!==null} onClick={()=>void partnerDownload(item)}>{downloading===item.id?'Downloading…':'Download'}</button></td></tr>)}</tbody></table></div>}
      <Heading icon={ClipboardList}>Submit to contract {contracts.find(c=>c.id===current)?.number||`#${current}`}</Heading>
      <form className="contact-form plan-form" onSubmit={async e=>{e.preventDefault();const d=new FormData(e.currentTarget);setError('');setNotice('');try{await api(`/partner/contracts/${current}/submissions`,'POST',{category:d.get('category'),number:d.get('number'),summary:d.get('summary'),evidence:d.get('evidence')});setNotice('Submitted for internal review')}catch(err){setError((err as Error).message)}}}>
        <label>Category<select name="category">{['notice','claim','variation','obligation','security','correspondence'].map(x=><option key={x}>{x}</option>)}</select></label><label>Submission reference<input name="number" required minLength={2}/></label><label className="wide">Description<input name="summary" required minLength={8}/></label><label>Evidence reference<input name="evidence" required minLength={8}/></label><button className="primary">Submit for review</button>
      </form>
    </>}
  </section>
}
