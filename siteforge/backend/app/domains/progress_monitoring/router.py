"""Read-only integrated Progress dashboard. All numbers remain source-owned.

Never infer weighted project totals from incomplete or unapproved schemes.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User, Membership, Role
from app.domains.planning_reporting.workspace_router import access
from app.domains.planning_reporting.workspace_models import PlanningPublication, PlanningPeriodTarget
from app.domains.planning_reporting.actuals_router import actual_progress
from .rollup import calculate_construction_rollups
from .stage_models import ProgressStageScheme
from .stage_scheme import calculate_overall

router = APIRouter(prefix='/api/projects/{pid}/progress',tags=['Progress Monitoring'])

def progress_scope(db: Session, user: User, pid: int):
    """Enforce internal membership and SELECTED-company/discipline scopes in Progress.

    Existing Planning privileges are the migration-safe fallback until explicit
    Progress role grants are configured. No partner-only membership is accepted.
    """
    access(db, user, pid)
    if user.organization_admin:
        return {'all': True, 'companies': set(), 'disciplines': set()}
    memberships = db.query(Membership).filter_by(
        project_id=pid, user_id=user.id, active=True).all()
    permitted = []
    for membership in memberships:
        role = db.get(Role, membership.role_id)
        grants = set(role.permissions or []) if role else set()
        if 'planning.partner.view' in grants:
            continue
        if grants.intersection({'planning.view', 'planning.manage'}):
            permitted.append(membership)
    if not permitted:
        raise HTTPException(403, 'Internal Planning view permission required')
    if any(m.scope == 'ALL' for m in permitted):
        return {'all': True, 'companies': set(), 'disciplines': set()}
    return {'all': False,
            'companies': {m.company_id for m in permitted},
            'disciplines': {int(d) for m in permitted for d in (m.discipline_ids or [])},
            'pairs': [(m.company_id, {int(d) for d in (m.discipline_ids or [])}) for m in permitted]}


def permitted_activity(a, scope):
    if scope['all']:
        return True
    # A SELECTED membership gives a company and optionally discipline restrictions.
    # Don't grant visibility to records without an authoritative company assignment.
    return (a.get('company_id') is not None and any(
        a['company_id'] == company and (not disciplines or a.get('discipline_id') in disciplines)
        for company, disciplines in scope['pairs']))


@router.get('/dashboard')
def dashboard(pid:int, publication_id:int|None=None, company_id:int|None=None, discipline_id:int|None=None, user:User=Depends(authenticated),db:Session=Depends(get_db)):
    # Reuse exact internal Planning membership/organization boundary, not combined partner grants.
    scope=progress_scope(db,user,pid)
    query=db.query(PlanningPublication).filter_by(project_id=pid,organization_id=user.organization_id,status='Approved')
    if publication_id is not None:
        query=query.filter_by(id=publication_id)
    else:
        query=query.filter_by(is_current=True)
    pub=query.order_by(PlanningPublication.id.desc()).first()
    now=datetime.now(timezone.utc)
    result={'visibility':'project' if scope['all'] else 'assigned company/discipline',
            'filters':{'company_id':company_id,'discipline_id':discipline_id},
            'project_id':pid,'data_date':now.date().isoformat(),'retrieved_at':now.isoformat(),
            'scope':'Internal membership-scoped source records',
            'measure':'Supervisor-Verified Execution','overall_percent':None,
            'overall_note':'Overall project % requires an approved cross-stage scheme; not inferred from construction only.',
            'stages':{'engineering':{'percent':None,'status':'No verified cross-stage integration'},
                      'procurement':{'percent':None,'status':'No verified cross-stage integration'},
                      'construction':{'percent':None,'status':'Awaiting approved baseline'},
                      'quality':{'percent':None,'status':'Readiness indicator, not earned progress'},
                      'commissioning':{'percent':None,'status':'Source not yet integrated'},
                      'financials':{'percent':None,'status':'Restricted; not physical progress'}},
            'publication':None,'planned':[], 'actuals':[], 'exceptions':[],
            'calculation_method':'Planning approved leaf activity weights; separate source-owned reported, verified and QA-accepted measures',
            'construction_measures':{'reported_percent':None,'verified_percent':None,'accepted_percent':None},
            'source_freshness':now.isoformat(), 'historical_actuals_available':False,
            'cross_stage_scheme':None,'stage_earning_evidence':{}}
    if pub is None:
        result['exceptions'].append('No current approved Planning baseline available; percentages remain unavailable.')
        return result
    result['publication']={'id':pub.id,'schedule_id':pub.schedule_id,'revision':pub.revision,'status':pub.status}
    if scope['all'] and company_id is None and discipline_id is None:
        stage_scheme=db.query(ProgressStageScheme).filter_by(organization_id=user.organization_id,project_id=pid,status='Approved',planning_publication_id=pub.id).order_by(ProgressStageScheme.version.desc()).first()
        if stage_scheme:
            result['cross_stage_scheme']={'id':stage_scheme.id,'version':stage_scheme.version,'weights':stage_scheme.weights,'approval_reference':stage_scheme.approval_reference}

    actuals=actual_progress(pid,pub.schedule_id,user,db)
    all_rows=actuals['activities']
    rows=[a for a in all_rows if permitted_activity(a,scope)
          and (company_id is None or a.get('company_id')==company_id)
          and (discipline_id is None or a.get('discipline_id')==discipline_id)]
    targets=db.query(PlanningPeriodTarget).filter_by(organization_id=user.organization_id,project_id=pid,publication_id=pub.id).all()
    weighted_rows=[]
    for a in rows:
        m=a.get('measurement') or {}
        weighted_rows.append(a)
        result['actuals'].append({'activity_id':a['activity_id'],'code':a['activity_code'],'name':a['activity_name'],
            'wbs_id':a['wbs_id'],'discipline_id':a['discipline_id'],'company_id':a['company_id'],
            'link_status':a['link_status'],'source':a.get('source'),'unit':m.get('unit'),
            'scope_quantity':m.get('scope_quantity'),'reported_quantity':m.get('reported_quantity'),
            'verified_quantity':m.get('verified_quantity'),'accepted_quantity':m.get('accepted_quantity'),
            'reported_percent':m.get('reported_percent'),'verified_percent':m.get('verified_percent'),
            'accepted_percent':m.get('accepted_percent')})
        if a['link_status']!='linked':
            result['exceptions'].append(f"{a['activity_code']}: {a['link_status']}")
    calc=calculate_construction_rollups(weighted_rows, targets,
        full_scope=scope['all'] and company_id is None and discipline_id is None)
    result['construction_measures']=calc['measures']
    result['exceptions'].extend(calc['errors'])
    valid=calc['valid_scheme'] and calc['measures']['verified_percent'] is not None
    weight_by_activity=calc['weights']
    if valid:
        result['stages']['construction']={'percent':calc['measures']['verified_percent'],
            'status':'Approved Planning-weighted supervisor-verified construction progress (not cross-stage)'}
    else:
        result['stages']['construction']['status']='Weighted verified total unavailable; review approved weights and source exceptions'
    # Approved cumulative targets are plotted as published, without inventing daily points.
    periods=sorted({t.period_end for t in targets})
    for period in periods:
        current={}
        for row in targets:
            if row.period_end<=period and (row.activity_id not in current or row.period_end>current[row.activity_id].period_end):
                current[row.activity_id]=row
        if valid and set(current)==set(weight_by_activity):
            pct=sum(current[i].cumulative_percent*weight_by_activity[i] for i in current)/10000
            result['planned'].append({'period_end':period.isoformat(),'planned_percent':round(pct,2)})
    # Diagnostic checks operate only on visible rows; never reveal hidden activity counts.
    seen_sources = set()
    for a in result['actuals']:
        code = a['code']
        measured = a['scope_quantity']
        reported, verified, accepted = (a[k] for k in ('reported_quantity','verified_quantity','accepted_quantity'))
        try:
            scope_qty = float(measured) if measured is not None else None
            measures = [(k, float(v)) for k,v in (('reported',reported),('verified',verified),('accepted',accepted)) if v is not None]
            if scope_qty is None or scope_qty <= 0:
                result['exceptions'].append(f'{code}: approved measurement scope missing or zero')
            for label, qty in measures:
                if qty < 0 or (scope_qty is not None and qty > scope_qty):
                    result['exceptions'].append(f'{code}: {label} quantity outside approved scope')
            if dict(measures).get('accepted', 0) > dict(measures).get('verified', 0):
                result['exceptions'].append(f'{code}: accepted quantity exceeds verified quantity')
        except (ValueError, TypeError):
            result['exceptions'].append(f'{code}: invalid numeric measurement')
        source = a.get('source')
        # Source mapping may be a structured payload. Only hash usable scalar identifiers.
        if source is not None and isinstance(source, (str,int)):
            if source in seen_sources:
                result['exceptions'].append(f'{code}: duplicate source reference in visible records')
            seen_sources.add(source)
    if result['cross_stage_scheme']:
        # Import lazily: the milestone policy router imports progress_scope from this module.
        from .milestone_policy_router import earned as source_earned
        scheme = result['cross_stage_scheme']
        inputs = {}
        for stage in scheme['weights']:
            if stage == 'construction':
                if valid:
                    inputs[stage] = {'percent':calc['measures']['verified_percent'], 'status':'approved_earned_progress'}
                else:
                    inputs[stage] = {'percent':None, 'status':'unavailable'}
                result['stage_earning_evidence'][stage] = {
                    'status':inputs[stage]['status'], 'baseline_id':pub.id,
                    'measurement':'Supervisor-verified, approved Planning-weighted execution',
                    'percent':inputs[stage]['percent'], 'errors':calc['errors']}
            elif stage in ('engineering','procurement'):
                # Reuse authoritative source evidence, QCI, allocations, and baseline guards.
                evidence=source_earned(pid,stage,user,db)
                matching=(evidence.get('planning_publication_id')==pub.id)
                good=(matching and evidence.get('policy_status')=='APPROVED_EARNED_PROGRESS'
                      and evidence.get('earned_percent') is not None)
                inputs[stage]={'percent':evidence['earned_percent'] if good else None,
                               'status':'approved_earned_progress' if good else 'unavailable'}
                result['stage_earning_evidence'][stage]={
                    'status':inputs[stage]['status'], 'baseline_id':evidence.get('planning_publication_id'),
                    'policy_version':evidence.get('policy_version'),
                    'percent':inputs[stage]['percent'],
                    'errors':evidence.get('errors',[]) + ([] if matching else ['Stage baseline does not match the approved cross-stage scheme'])}
                result['stages'][stage]={
                    'percent':inputs[stage]['percent'],
                    'status':'Approved source-earned progress' if good else 'Approved source-earned progress unavailable'}
            else:
                inputs[stage]={'percent':None,'status':'unavailable'}
                result['stage_earning_evidence'][stage]={
                    'status':'unavailable','percent':None,
                    'errors':['Approved commissioning earning source is not integrated']}
        overall=calculate_overall(scheme['weights'], inputs,scheme_approved=True,
                                  full_scope=scope['all'] and company_id is None and discipline_id is None,
                                  baseline_matches=all(e.get('baseline_id',pub.id)==pub.id for e in result['stage_earning_evidence'].values()))
        result['overall_percent']=overall['percent']
        result['overall_note']='; '.join(overall['errors']) if overall['errors'] else 'Approved EPCC stage-weighted earned progress'
    result['exceptions']=list(dict.fromkeys(result['exceptions']))
    return result
