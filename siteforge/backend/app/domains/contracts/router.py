"""Contract authority APIs: separate internal vs external permissions and approval states."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hmac
import csv
import io
from fastapi.responses import StreamingResponse, Response
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.config import settings
from app.domains.identity_projects.security import authenticated
from app.domains.identity_projects.models import User, Project, Company, Membership, ProjectCompany, Role
from .models import Contract, ContractVersion, ContractBoq, ContractRecord, ContractPartnerShare, ContractAudit, ContractLegacyMap, ContractApprovalDecision, ContractReviewStage, ContractSigningAuthority, ContractSigningDelegation, ContractAmendment, ContractModuleDelivery, ContractConsumerProjection, ContractFinanceLink, ContractScopeItem, ContractTermVersion, ContractObligation, ContractClaim, ContractCorrespondence, ContractSecurityInstrument, ContractSecurityEvent, ContractCloseoutCheck, ContractWarranty, ContractPartnerDocument, ContractProcurementLink

from app.domains.commercial_financials.models import FinanceContract
from app.domains.supply_chain.models import PurchaseOrder, Vendor
from app.domains.engineering_documents.models import StoredFile
from app.domains.engineering_documents.files import read_file

router=APIRouter(prefix='/api/projects/{pid}/contracts',tags=['Contracts'])
partner=APIRouter(prefix='/api/partner/contracts',tags=['Partner Contracts'])
VALID_TYPES={'Client','Subcontract','Service','Framework','Other'}
CATEGORIES={'obligation','claim','variation','notice','correspondence','security','closeout','warranty','responsibility','review','execution','term'}

def project_guard(db,user,pid,permission='contracts.view_summary'):
    project=db.get(Project,pid)
    if not project or project.organization_id != user.organization_id:raise HTTPException(404,'Project not found')
    if not user.active:raise HTTPException(403,'Inactive account')
    if user.organization_admin:return project
    for m in db.query(Membership).filter_by(project_id=pid,user_id=user.id,active=True).all():
        role=db.get(Role,m.role_id)
        perms=set(role.permissions or []) if role else set()
        # Existing Financials roles can only read summary; no implicit contract mutation.
        fallback=(permission=='contracts.view_summary' and 'financials.view' in perms)
        if m.scope=='ALL' and (permission in perms or fallback):return project
    raise HTTPException(403,'Contract permission and full project scope required')

def can_commercial(db,user,pid):
    if user.organization_admin:return True
    for m in db.query(Membership).filter_by(project_id=pid,user_id=user.id,active=True).all():
        role=db.get(Role,m.role_id)
        perms=set(role.permissions or []) if role else set()
        if m.scope=='ALL' and ('contracts.view_commercial' in perms or 'financials.manage' in perms):return True
    return False

def get_contract(db,user,pid,cid,permission='contracts.view_summary'):
    project_guard(db,user,pid,permission)
    c=db.query(Contract).filter_by(id=cid,organization_id=user.organization_id,project_id=pid).one_or_none()
    if not c:raise HTTPException(404,'Contract not found')
    return c

def save(db):
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Duplicate record or invalid reference')

def audit(db,c,user,action,detail=None):db.add(ContractAudit(contract_id=c.id,actor_id=user.id,action=action,detail=detail or {}))

def out(c,commercial=False):
    x={'id':c.id,'project_id':c.project_id,'number':c.number,'title':c.title,'contract_type':c.contract_type,'contracting_company_id':c.contracting_company_id,'counterparty_company_id':c.counterparty_company_id,'manager_user_id':c.manager_user_id,'scope':c.scope,'lifecycle':c.lifecycle,'approval_state':c.approval_state,'current_version':c.current_version,'published_version':c.published_version,'effective_at':c.effective_at,'expires_at':c.expires_at}
    if commercial:x.update(currency=c.currency,original_value=str(c.original_value) if c.original_value is not None else None)
    return x

class ContractIn(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    title:str=Field(min_length=3,max_length=240)
    contract_type:str
    contracting_company_id:int
    counterparty_company_id:int
    manager_user_id:int
    scope:str=Field(min_length=5,max_length=15000)
    currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$')
    original_value:Decimal|None=Field(default=None,ge=0,max_digits=20,decimal_places=2)
    effective_at:datetime|None=None
    expires_at:datetime|None=None

@router.get('')
def listing(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    project_guard(db,user,pid)
    return [out(c,can_commercial(db,user,pid)) for c in db.query(Contract).filter_by(project_id=pid,organization_id=user.organization_id).order_by(Contract.id.desc()).limit(250)]

@router.post('',status_code=201)
def create(pid:int,body:ContractIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    project_guard(db,user,pid,'contracts.manage_draft')
    if body.contract_type not in VALID_TYPES:raise HTTPException(422,'Invalid contract type')
    if body.contracting_company_id==body.counterparty_company_id:raise HTTPException(422,'Two distinct parties required')
    for co in (body.contracting_company_id,body.counterparty_company_id):
        company=db.get(Company,co)
        if not company or company.organization_id!=user.organization_id or not company.active:raise HTTPException(422,'Company outside organization')
    manager=db.get(User,body.manager_user_id)
    if not manager or manager.organization_id!=user.organization_id or not manager.active:raise HTTPException(422,'Invalid manager')
    c=Contract(organization_id=user.organization_id,project_id=pid,created_by=user.id,**body.model_dump())
    db.add(c);db.flush()
    db.add(ContractVersion(contract_id=c.id,version=1,snapshot=body.model_dump(mode='json'),reason='Initial draft',created_by=user.id))
    audit(db,c,user,'created');save(db)
    return out(c,True)

# Import is preview-only: no contract/company/project/user is created by this route.
IMPORT_FIELDS = ('number','title','contract_type','contracting_company_id','counterparty_company_id',
                 'manager_user_id','scope','currency','original_value')

def validate_contract_import_row(raw, row_number, company_ids, manager_ids, existing_numbers):
    errors=[]
    values={k:str(raw.get(k,'') or '').strip() for k in IMPORT_FIELDS}
    if not values['number']:errors.append('number is required')
    if len(values['number'])>80:errors.append('number exceeds 80 characters')
    if len(values['title'])<3 or len(values['title'])>240:errors.append('title must contain 3-240 characters')
    if values['contract_type'] not in VALID_TYPES:errors.append('contract_type is not recognized')
    if len(values['scope'])<5:errors.append('scope must contain at least 5 characters')
    for key,ids in (('contracting_company_id',company_ids),('counterparty_company_id',company_ids),('manager_user_id',manager_ids)):
        try: parsed=int(values[key]);assert parsed in ids
        except (ValueError,AssertionError):errors.append(f'{key} must reference an existing authorized record')
    if values['contracting_company_id']==values['counterparty_company_id']:
        errors.append('contracting company and counterparty must differ')
    currency=values['currency'];amount=values['original_value']
    if currency and (len(currency)!=3 or not currency.isalpha() or currency!=currency.upper()):
        errors.append('currency must use an uppercase three-letter code')
    if bool(currency)!=bool(amount):errors.append('currency and original_value must be provided together')
    if amount:
        try:
            parsed=Decimal(amount)
            if not parsed.is_finite() or parsed<0 or parsed.as_tuple().exponent<-2 or parsed>=10**18:
                raise ValueError()
        except (ValueError,ArithmeticError):errors.append('original_value must be a nonnegative finite amount with two decimals or fewer')
    if values['number'] in existing_numbers:errors.append('contract number already exists')
    return {'row':row_number,'values':values,'errors':errors,'valid':not errors}

@router.post('/import-preview')
def import_preview(pid:int,body:dict,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    project_guard(db,user,pid,'contracts.manage_draft')
    rows=body.get('rows')
    if not isinstance(rows,list) or not 1<=len(rows)<=500 or any(not isinstance(r,dict) for r in rows):
        raise HTTPException(422,'Supply 1-500 spreadsheet-mapped row objects')
    companies={x.id for x in db.query(Company).filter_by(organization_id=user.organization_id,active=True).all()}
    managers={x.id for x in db.query(User).filter_by(organization_id=user.organization_id,active=True).all()}
    existing={x.number for x in db.query(Contract).filter_by(organization_id=user.organization_id).all()}
    result=[];seen=set()
    for i,row in enumerate(rows,2):
        item=validate_contract_import_row(row,i,companies,managers,existing)
        number=item['values']['number']
        if number in seen:item['errors'].append('duplicate number in import batch');item['valid']=False
        if number:seen.add(number)
        result.append(item)
    return {'dry_run':True,'created':0,'valid_rows':sum(x['valid'] for x in result),'rows':result}

@router.get('/export.csv')
def export_contracts_csv(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    project_guard(db,user,pid,'contracts.view_summary')
    commercial=can_commercial(db,user,pid)
    columns=['number','title','contract_type','lifecycle','approval_state','current_version']
    if commercial:columns+=['currency','original_value']
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=columns);writer.writeheader()
    for c in db.query(Contract).filter_by(organization_id=user.organization_id,project_id=pid).order_by(Contract.id).all():
        data=out(c,commercial)
        # A spreadsheet must not interpret untrusted text as executable formulas.
        safe={k: ("'"+str(data[k]) if isinstance(data.get(k),str) and data[k].lstrip().startswith(('=','+','-','@')) else data.get(k)) for k in columns}
        writer.writerow(safe)
    return StreamingResponse(iter([output.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="contracts.csv"'})

@router.get('/{cid:int}')
def detail(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    return out(get_contract(db,user,pid,cid),can_commercial(db,user,pid))

class VersionIn(BaseModel):
    reason:str=Field(min_length=8,max_length=2000)
    scope:str=Field(min_length=5,max_length=15000)
    effective_at:datetime|None=None
    expires_at:datetime|None=None

@router.post('/{cid}/versions')
def revise(pid:int,cid:int,body:VersionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_terms')
    if c.lifecycle not in {'Draft','Under Internal Review','Under Counterparty Review'}:raise HTTPException(409,'Controlled terms require an amendment after execution')
    old=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    if old.state=='Effective':raise HTTPException(409,'Effective version immutable')
    c.current_version+=1;c.approval_state='Draft';c.scope=body.scope;c.effective_at=body.effective_at;c.expires_at=body.expires_at
    snapshot=dict(old.snapshot);snapshot.update(body.model_dump(mode='json'))
    next_version=ContractVersion(contract_id=c.id,version=c.current_version,snapshot=snapshot,reason=body.reason,created_by=user.id)
    db.add(next_version);db.flush()
    copied=carry_forward_boq(db,c.id,old.id,next_version.id)
    audit(db,c,user,'new_version',{'version':c.current_version,'reason':body.reason,'boq_rows_copied':copied});save(db)
    return out(c,True)

@router.get('/{cid}/versions')
def versions(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid)
    return [{'id':v.id,'version':v.version,'state':v.state,'reason':v.reason,'created_at':v.created_at} for v in db.query(ContractVersion).filter_by(contract_id=c.id).order_by(ContractVersion.version)]

def carry_forward_boq(db: Session, contract_id: int, prior_version_id: int, next_version_id: int) -> int:
    """Copy BOQ values by value, never reparent prior version's immutable rows."""
    original = db.query(ContractBoq).filter_by(contract_id=contract_id, version_id=prior_version_id).all()
    for line in original:
        db.add(ContractBoq(contract_id=contract_id, version_id=next_version_id,
            code=line.code, description=line.description, unit=line.unit,
            quantity=line.quantity, rate=line.rate, currency=line.currency,
            pricing_type=line.pricing_type))
    return len(original)

class BoqIn(BaseModel):
    code:str=Field(min_length=1,max_length=80)
    description:str=Field(min_length=3,max_length=2000)
    unit:str=Field(min_length=1,max_length=40)
    quantity:Decimal=Field(ge=0,max_digits=20,decimal_places=4)
    rate:Decimal=Field(ge=0,max_digits=20,decimal_places=2)
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    pricing_type:str='Quantity'

@router.post('/{cid}/boq',status_code=201)
def add_boq(pid:int,cid:int,body:BoqIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_terms')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    if v.state!='Draft':raise HTTPException(409,'BOQ version locked')
    if c.currency and body.currency!=c.currency:raise HTTPException(422,'BOQ currency differs from contract')
    if body.pricing_type not in {'Quantity','Milestone','Lump Sum Stage'}:raise HTTPException(422,'Invalid pricing type')
    r=ContractBoq(contract_id=c.id,version_id=v.id,**body.model_dump())
    db.add(r);audit(db,c,user,'boq_added',{'item_code':r.code,'version':v.version});save(db)
    return {'id':r.id,'code':r.code,'version':v.version}

@router.get('/{cid}/boq')
def boq(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid)
    if not can_commercial(db,user,pid):raise HTTPException(403,'Commercial BOQ access required')
    vs={v.id:v.version for v in db.query(ContractVersion).filter_by(contract_id=c.id).all()}
    return [{'id':r.id,'version':vs.get(r.version_id),'code':r.code,'description':r.description,'unit':r.unit,'quantity':str(r.quantity),'rate':str(r.rate),'currency':r.currency,'pricing_type':r.pricing_type} for r in db.query(ContractBoq).filter_by(contract_id=c.id).all()]

class BoqRevisionIn(BaseModel):
    description:str=Field(min_length=3,max_length=2000)
    unit:str=Field(min_length=1,max_length=40)
    quantity:Decimal=Field(ge=0,max_digits=20,decimal_places=4)
    rate:Decimal=Field(ge=0,max_digits=20,decimal_places=2)
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    pricing_type:str='Quantity'
    reason:str=Field(min_length=8,max_length=2000)

@router.put('/{cid}/boq/{line_id}')
def revise_boq_line(pid:int,cid:int,line_id:int,body:BoqRevisionIn,
                    user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Change only the current draft line, never an approved/historical BOQ row."""
    c=get_contract(db,user,pid,cid,'contracts.manage_terms')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).with_for_update().one()
    if v.state!='Draft' or c.lifecycle!='Draft' or c.approval_state!='Draft':
        raise HTTPException(409,'BOQ locked: create an authorized contract revision or amendment')
    line=db.query(ContractBoq).filter_by(id=line_id,contract_id=c.id,version_id=v.id).with_for_update().one_or_none()
    if not line:raise HTTPException(404,'Current draft BOQ line not found')
    if c.currency and body.currency!=c.currency:raise HTTPException(422,'Contract currency mismatch')
    if body.pricing_type not in {'Quantity','Milestone','Lump Sum Stage'}:
        raise HTTPException(422,'Invalid pricing type')
    before={'description':line.description,'unit':line.unit,'quantity':str(line.quantity),
            'rate':str(line.rate),'currency':line.currency,'pricing_type':line.pricing_type}
    for key in ('description','unit','quantity','rate','currency','pricing_type'):
        setattr(line,key,getattr(body,key))
    audit(db,c,user,'boq_line_revised',{'line_id':line.id,'code':line.code,'version':v.version,
        'reason':body.reason,'before':before,'after':{
            'quantity':str(line.quantity),'rate':str(line.rate),'currency':line.currency,
            'unit':line.unit,'pricing_type':line.pricing_type,'description':line.description}})
    save(db)
    return {'id':line.id,'contract_version':v.version,'code':line.code,'rate':str(line.rate),
            'quantity':str(line.quantity),'historical_versions_unchanged':True}

@router.get('/{cid}/integrations/finance-boq-terms')
def finance_boq_terms(pid:int,cid:int,version:int|None=None,
                      user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Approved source terms only; never authorizes billing or changes Finance postings."""
    c=get_contract(db,user,pid,cid,'contracts.view_commercial')
    if not can_commercial(db,user,pid):raise HTTPException(403,'Commercial BOQ access required')
    link=db.query(ContractFinanceLink).filter_by(contract_id=c.id,organization_id=c.organization_id,
        project_id=pid).one_or_none()
    if not link:raise HTTPException(409,'Financials contract link required')
    requested=c.current_version if version is None else version
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=requested).one_or_none()
    if not v:raise HTTPException(404,'Contract version not found')
    if v.state not in {'Effective','Executed'}:
        raise HTTPException(409,'Only executed/effective versions may be consumed by Financials')
    rows=db.query(ContractBoq).filter_by(contract_id=c.id,version_id=v.id).order_by(ContractBoq.code).all()
    return {'source':'Contracts','contract_id':c.id,'finance_contract_id':link.finance_contract_id,
        'contract_version_id':v.id,'version':v.version,'currency':c.currency,
        'read_only':True,'billing_authorized':False,
        'lines':[{'id':r.id,'code':r.code,'description':r.description,'unit':r.unit,
            'quantity':str(r.quantity),'rate':str(r.rate),'currency':r.currency,
            'pricing_type':r.pricing_type} for r in rows]}

class DecisionIn(BaseModel):
    reason:str=Field(min_length=8,max_length=2000)
    evidence:str|None=None

@router.post('/{cid}/submit')
def submit(pid:int,cid:int,body:DecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_draft')
    if c.approval_state!='Draft' or c.lifecycle!='Draft':raise HTTPException(409,'Only fresh drafts may be submitted')
    c.approval_state='Pending Review';c.lifecycle='Under Internal Review'
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one();v.state='In Review'
    stages=db.query(ContractReviewStage).filter_by(version_id=v.id).order_by(ContractReviewStage.step_no).all()
    if stages:
        for stage in stages:
            stage.status='Waiting';stage.decision_by=None;stage.decided_at=None;stage.decision_reason=None
        stages[0].status='Pending'
    audit(db,c,user,'submitted',{'version':c.current_version,'reason':body.reason});save(db);return out(c,True)

class ReviewStageIn(BaseModel):
    label:str=Field(min_length=3,max_length=120)
    reviewer_user_id:int

class ReviewRouteIn(BaseModel):
    stages:list[ReviewStageIn]=Field(min_length=1,max_length=12)

@router.put('/{cid}/review-route')
def configure_review_route(pid:int,cid:int,body:ReviewRouteIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.approve')
    if c.approval_state!='Draft' or c.lifecycle!='Draft':raise HTTPException(409,'Review route may only be configured in draft')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    if v.state!='Draft':raise HTTPException(409,'Version no longer editable')
    if len({x.reviewer_user_id for x in body.stages})!=len(body.stages):raise HTTPException(422,'Duplicate stage reviewer')
    for x in body.stages:
        reviewer=db.get(User,x.reviewer_user_id)
        if not reviewer or not reviewer.active or reviewer.organization_id!=user.organization_id:
            raise HTTPException(422,'Invalid reviewer')
        if reviewer.id in {c.created_by,v.created_by}:raise HTTPException(422,'Document author cannot be stage reviewer')
        # Explicit project-level approve privilege is mandatory for every assigned reviewer.
        project_guard(db,reviewer,pid,'contracts.approve')
    db.query(ContractReviewStage).filter_by(version_id=v.id).delete(synchronize_session=False)
    for i,x in enumerate(body.stages,1):
        db.add(ContractReviewStage(contract_id=c.id,version_id=v.id,step_no=i,label=x.label,reviewer_user_id=x.reviewer_user_id))
    audit(db,c,user,'review_route_configured',{'version':v.version,'stage_count':len(body.stages)})
    save(db)
    return {'contract_id':c.id,'version':v.version,'stages':len(body.stages)}

@router.get('/{cid}/review-route')
def review_route(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid)
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    stages=db.query(ContractReviewStage).filter_by(version_id=v.id).order_by(ContractReviewStage.step_no).all()
    return [{'step_no':x.step_no,'label':x.label,'reviewer_user_id':x.reviewer_user_id,'status':x.status,'decided_at':x.decided_at} for x in stages]

@router.post('/{cid}/review-stage/{step_no}/decide')
def decide_review_stage(pid:int,cid:int,step_no:int,body:DecisionIn,decision:str,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.approve')
    if decision not in {'Approve','Reject','Return'}:raise HTTPException(422,'Invalid stage decision')
    if c.approval_state!='Pending Review':raise HTTPException(409,'Contract not pending review')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    stages=db.query(ContractReviewStage).filter_by(version_id=v.id).order_by(ContractReviewStage.step_no).all()
    current=next((x for x in stages if x.status=='Pending'),None)
    if current is None or current.step_no!=step_no:raise HTTPException(409,'Only current pending stage may be decided')
    if current.reviewer_user_id!=user.id:raise HTTPException(403,'Only assigned reviewer can decide')
    if user.id in {c.created_by,v.created_by}:raise HTTPException(403,'Self approval prohibited')
    current.decision_by=user.id;current.decided_at=datetime.now(timezone.utc);current.decision_reason=body.reason
    if decision=='Approve':
        current.status='Approved'
        following=next((x for x in stages if x.step_no>step_no),None)
        if following:following.status='Pending'
        else:
            db.add(ContractApprovalDecision(contract_id=c.id,version_id=v.id,actor_id=user.id,decision='Approved Internally',reason=body.reason))
            c.approval_state='Approved Internally';c.lifecycle='Awaiting Signature';v.state='Approved Internally'
    else:
        current.status='Rejected' if decision=='Reject' else 'Returned'
        c.approval_state='Draft';c.lifecycle='Draft';v.state='Draft'
    audit(db,c,user,'review_stage_decided',{'version':v.version,'step':step_no,'decision':decision})
    save(db)
    return out(c,True)

@router.post('/{cid}/approve')
def approve(pid:int,cid:int,body:DecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.approve')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    if db.query(ContractReviewStage).filter_by(version_id=v.id).first():
        raise HTTPException(409,'Configured route requires sequential stage decisions')
    if c.approval_state!='Pending Review':raise HTTPException(409,'Not pending review')
    if v.created_by==user.id or c.created_by==user.id:raise HTTPException(403,'Self approval prohibited')
    db.add(ContractApprovalDecision(contract_id=c.id,version_id=v.id,actor_id=user.id,decision='Approved Internally',reason=body.reason))
    c.approval_state='Approved Internally';c.lifecycle='Awaiting Signature';v.state='Approved Internally'
    audit(db,c,user,'internally_approved',{'version':v.version,'reason':body.reason});save(db);return out(c,True)

class AuthorityIn(BaseModel):
    user_id:int
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    max_value:Decimal=Field(ge=0,max_digits=20,decimal_places=2)
    valid_from:datetime
    valid_until:datetime

class DelegationIn(BaseModel):
    delegate_user_id:int
    valid_from:datetime
    valid_until:datetime

def aware(dt):
    if dt.tzinfo is None or dt.utcoffset() is None:raise HTTPException(422,'Timezone-aware dates required')
    return dt.astimezone(timezone.utc)

def stored_utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def signing_authority(db,c,uid,instant):
    for a in db.query(ContractSigningAuthority).filter_by(organization_id=c.organization_id,project_id=c.project_id,user_id=uid).all():
        if a.currency==c.currency and c.original_value is not None and a.max_value>=c.original_value and stored_utc(a.valid_from)<=instant<=stored_utc(a.valid_until):return a
    return None

@router.get('/eligible-users')
def eligible_contract_users(pid:int,kind:str='review',user:User=Depends(authenticated),db:Session=Depends(get_db)):
    if kind not in {'review','sign'}:raise HTTPException(422,'Invalid selection kind')
    permission='contracts.approve' if kind=='review' else 'contracts.sign'
    project_guard(db,user,pid,permission)
    candidates=db.query(User).filter_by(organization_id=user.organization_id,active=True).order_by(User.name).all()
    results=[]
    for candidate in candidates:
        try:project_guard(db,candidate,pid,permission)
        except HTTPException:continue
        results.append({'id':candidate.id,'name':candidate.name})
    return results

@router.get('/{cid}/signing-delegations')
def signing_delegations(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.sign')
    q=db.query(ContractSigningDelegation).filter_by(contract_id=c.id,organization_id=c.organization_id).order_by(ContractSigningDelegation.id.desc())
    rows=q.limit(200).all()
    # Signatories can inspect only delegations involving themselves; administrators see all.
    if not user.organization_admin:rows=[d for d in rows if user.id in {d.delegator_user_id,d.delegate_user_id}]
    return [{'id':d.id,'delegator_user_id':d.delegator_user_id,'delegate_user_id':d.delegate_user_id,
             'valid_from':d.valid_from,'valid_until':d.valid_until,'revoked_at':d.revoked_at,
             'status':('Revoked' if d.revoked_at else 'Expired' if stored_utc(d.valid_until)<datetime.now(timezone.utc) else 'Scheduled' if stored_utc(d.valid_from)>datetime.now(timezone.utc) else 'Active')}
            for d in rows]

@router.post('/signing-authorities')
def configure_signing_authority(pid:int,body:AuthorityIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    project_guard(db,user,pid,'contracts.sign')
    if not user.organization_admin:raise HTTPException(403,'Only organization admin may set signing authority')
    start,end=aware(body.valid_from),aware(body.valid_until)
    if start>=end:raise HTTPException(422,'Invalid authority validity')
    subject=db.get(User,body.user_id)
    if not subject or not subject.active or subject.organization_id!=user.organization_id:raise HTTPException(422,'Invalid signatory')
    project_guard(db,subject,pid,'contracts.sign')
    row=db.query(ContractSigningAuthority).filter_by(project_id=pid,user_id=subject.id,currency=body.currency).one_or_none()
    if not row:
        row=ContractSigningAuthority(organization_id=user.organization_id,project_id=pid,user_id=subject.id,currency=body.currency,created_by=user.id)
        db.add(row)
    row.max_value=body.max_value;row.valid_from=start;row.valid_until=end
    save(db)
    return {'user_id':subject.id,'currency':row.currency,'max_value':str(row.max_value)}

@router.post('/{cid}/signing-delegations')
def delegate_signing(pid:int,cid:int,body:DelegationIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.sign')
    if c.lifecycle!='Awaiting Signature':raise HTTPException(409,'Contract not awaiting signature')
    start,end=aware(body.valid_from),aware(body.valid_until)
    at=datetime.now(timezone.utc)
    if start>=end or end<=at:raise HTTPException(422,'Invalid delegation validity')
    # Delegation must be valid throughout its entire requested period.
    if start<at:start=at
    if user.id==body.delegate_user_id:raise HTTPException(422,'Cannot delegate to self')
    target=db.get(User,body.delegate_user_id)
    if not target or not target.active or target.organization_id!=c.organization_id:raise HTTPException(422,'Invalid delegate')
    project_guard(db,target,pid,'contracts.sign')
    if not signing_authority(db,c,user.id,start) or not signing_authority(db,c,user.id,end):raise HTTPException(403,'Delegator lacks direct authority for the delegation period')
    for prior in db.query(ContractSigningDelegation).filter_by(contract_id=cid,delegator_user_id=user.id,delegate_user_id=target.id,revoked_at=None).all():
        if stored_utc(prior.valid_from)<end and start<stored_utc(prior.valid_until):
            raise HTTPException(409,'An overlapping signing delegation already exists')
    row=ContractSigningDelegation(organization_id=c.organization_id,project_id=pid,contract_id=cid,delegator_user_id=user.id,delegate_user_id=target.id,valid_from=start,valid_until=end)
    db.add(row);audit(db,c,user,'signature_delegated',{'delegate':target.id,'until':end.isoformat()});db.flush();rid=row.id;save(db)
    return {'id':rid,'delegate_user_id':target.id}

@router.post('/{cid}/signing-delegations/{delegation_id}/revoke')
def revoke_delegation(pid:int,cid:int,delegation_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.sign')
    row=db.query(ContractSigningDelegation).filter_by(id=delegation_id,contract_id=c.id,organization_id=c.organization_id).one_or_none()
    if row is None:raise HTTPException(404,'Delegation not found')
    if row.delegator_user_id!=user.id and not user.organization_admin:raise HTTPException(403,'Not delegation owner')
    if row.revoked_at is not None:raise HTTPException(409,'Already revoked')
    row.revoked_at=datetime.now(timezone.utc);audit(db,c,user,'signature_delegation_revoked',{'delegation_id':row.id});save(db)
    return {'revoked':True}

def verify_signing_authority(db,c,user):
    # Backward compatibility until a project's signing matrix is configured.
    if not db.query(ContractSigningAuthority).filter_by(project_id=c.project_id,organization_id=c.organization_id).count():return
    at=datetime.now(timezone.utc)
    if signing_authority(db,c,user.id,at):return
    for d in db.query(ContractSigningDelegation).filter_by(contract_id=c.id,delegate_user_id=user.id,revoked_at=None).all():
        if stored_utc(d.valid_from)<=at<=stored_utc(d.valid_until) and signing_authority(db,c,d.delegator_user_id,at):return
    raise HTTPException(403,'No valid signing authority/delegation for contract amount and currency')


@router.post('/{cid}/execute')
def execute(pid:int,cid:int,body:DecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.sign')
    if c.approval_state!='Approved Internally' or not body.evidence or len(body.evidence.strip())<8:raise HTTPException(422,'Internal approval and signed execution evidence required')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    authorized=db.query(ContractApprovalDecision).filter_by(contract_id=c.id,version_id=v.id,decision='Approved Internally').one_or_none()
    if not authorized or v.state!='Approved Internally':raise HTTPException(409,'Exact contract version lacks recorded internal approval')
    if authorized.actor_id==user.id:raise HTTPException(403,'Approver cannot also execute the same contract version')
    verify_signing_authority(db,c,user)
    c.execution_evidence=body.evidence;c.lifecycle='Executed'
    audit(db,c,user,'executed',{'version':c.current_version,'evidence':body.evidence});save(db);return out(c,True)

@router.post('/{cid}/activate')
def activate(pid:int,cid:int,body:DecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.activate')
    if c.lifecycle!='Executed' or not c.execution_evidence or c.effective_at is None:raise HTTPException(409,'Execution evidence and effective date required')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    c.lifecycle='Active';v.state='Effective'
    audit(db,c,user,'activated',{'version':v.version});save(db);return out(c,True)

class RecordIn(BaseModel):
    category:str
    number:str=Field(min_length=1,max_length=80)
    summary:str=Field(min_length=5,max_length=4000)
    due_at:datetime|None=None
    amount:Decimal|None=Field(default=None,ge=0,max_digits=20,decimal_places=2)
    currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$')
    evidence:str|None=None
    details:dict=Field(default_factory=dict)

@router.post('/{cid}/records',status_code=201)
def record_create(pid:int,cid:int,body:RecordIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    perm='contracts.manage_variations' if body.category in {'variation','claim'} else 'contracts.manage_obligations'
    c=get_contract(db,user,pid,cid,perm)
    if body.category not in CATEGORIES:raise HTTPException(422,'Unsupported record category')
    if body.amount is not None and not body.currency:raise HTTPException(422,'Currency required')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    r=ContractRecord(contract_id=c.id,version_id=v.id,created_by=user.id,**body.model_dump())
    db.add(r);audit(db,c,user,'record_created',{'category':body.category,'number':body.number});save(db)
    return {'id':r.id,'category':r.category,'number':r.number,'status':r.status}

@router.get('/{cid}/records')
def record_list(pid:int,cid:int,category:str|None=None,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid)
    q=db.query(ContractRecord).filter_by(contract_id=c.id)
    if category:q=q.filter_by(category=category)
    return [{'id':r.id,'category':r.category,'number':r.number,'summary':r.summary,'status':r.status,'due_at':r.due_at,'amount':str(r.amount) if r.amount is not None else None,'currency':r.currency,'evidence':r.evidence} for r in q.order_by(ContractRecord.id.desc()).limit(250)]

@router.post('/{cid}/records/{rid}/decide')
def record_decide(pid:int,cid:int,rid:int,body:DecisionIn,decision:str,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.approve')
    r=db.query(ContractRecord).filter_by(id=rid,contract_id=c.id).one_or_none()
    if not r:raise HTTPException(404,'Record not found')
    if r.created_by==user.id:raise HTTPException(403,'Self approval prohibited')
    if r.status not in {'Draft','Submitted'}:raise HTTPException(409,'Record already decided')
    if decision not in {'Accepted','Rejected','Returned'}:raise HTTPException(422,'Invalid decision')
    if r.category in {'variation','claim'} and decision=='Accepted':
        # Internal acceptance does NOT make a commercial amendment effective.
        r.status='Approved Internally'
    else:r.status=decision
    audit(db,c,user,'record_decided',{'record_id':r.id,'decision':r.status,'reason':body.reason});save(db)
    return {'id':r.id,'status':r.status}

class CounterpartyAgreementIn(BaseModel):
    agreement_reference: str = Field(min_length=3, max_length=120)
    evidence: str = Field(min_length=8, max_length=4000)
    agreed_at: datetime

@router.post('/{cid}/variations/{rid}/counterparty-agreement')
def record_counterparty_agreement(pid:int,cid:int,rid:int,body:CounterpartyAgreementIn,
                                  user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Record documentary agreement, without altering effective contract/Finance values."""
    c=get_contract(db,user,pid,cid,'contracts.manage_variations')
    r=db.query(ContractRecord).filter_by(id=rid,contract_id=c.id,category='variation').with_for_update().one_or_none()
    if not r:raise HTTPException(404,'Variation not found')
    if r.status!='Approved Internally':raise HTTPException(409,'Internal variation approval required')
    if r.created_by==user.id:raise HTTPException(403,'Originator cannot attest counterparty agreement')
    if r.currency and c.currency and r.currency!=c.currency:
        raise HTTPException(422,'Variation currency differs from contract')
    if body.agreed_at.tzinfo is None or body.agreed_at.utcoffset() is None:
        raise HTTPException(422,'Agreement date must include timezone')
    if body.agreed_at.astimezone(timezone.utc)>datetime.now(timezone.utc):
        raise HTTPException(422,'Agreement date cannot be in the future')
    detail=dict(r.details or {})
    if detail.get('counterparty_agreement'):
        raise HTTPException(409,'Counterparty agreement already recorded')
    detail['counterparty_agreement']={
        'reference':body.agreement_reference,'evidence':body.evidence,
        'agreed_at':body.agreed_at.astimezone(timezone.utc).isoformat(),
        'recorded_by':user.id,'contract_version':c.current_version}
    r.details=detail
    r.status='Agreed - Pending Amendment'
    audit(db,c,user,'variation_counterparty_agreed',{'record_id':r.id,
          'reference':body.agreement_reference,'contract_version':c.current_version})
    save(db)
    return {'id':r.id,'status':r.status,'effective_value_changed':False,
            'requires_amendment':True}


class AmendmentPrepareIn(BaseModel):
    variation_id:int
    amendment_number:str=Field(min_length=3,max_length=80)

class AmendmentApprovalIn(BaseModel):
    reason:str=Field(min_length=8,max_length=2000)

class AmendmentExecuteIn(BaseModel):
    evidence:str=Field(min_length=8,max_length=4000)

@router.get('/{cid}/amendments')
def list_amendments(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.view_summary')
    rows=db.query(ContractAmendment).filter_by(contract_id=c.id).order_by(ContractAmendment.id).all()
    commercial=can_commercial(db,user,pid)
    return [{'id':a.id,'number':a.amendment_number,'status':a.status,
             'variation_id':a.variation_id,'version_id':a.effective_version_id,
             **({'delta_value':str(a.delta_value),'currency':a.currency} if commercial else {})}
            for a in rows]

@router.post('/{cid}/amendments',status_code=201)
def prepare_amendment(pid:int,cid:int,body:AmendmentPrepareIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_variations')
    if c.lifecycle not in {'Executed','Active'}:raise HTTPException(409,'Only executed contracts may be amended')
    v=db.query(ContractRecord).filter_by(id=body.variation_id,contract_id=c.id,category='variation').with_for_update().one_or_none()
    if not v or v.status!='Agreed - Pending Amendment' or not (v.details or {}).get('counterparty_agreement'):
        raise HTTPException(409,'Variation needs recorded counterparty agreement')
    if v.amount is None or not c.currency or v.currency!=c.currency:raise HTTPException(422,'Variation amount and contract currency required')
    if db.query(ContractAmendment).filter_by(variation_id=v.id).first():raise HTTPException(409,'Variation already linked to amendment')
    a=ContractAmendment(contract_id=c.id,variation_id=v.id,amendment_number=body.amendment_number,
                        delta_value=v.amount,currency=c.currency,prepared_by=user.id)
    db.add(a);db.flush();aid=a.id
    audit(db,c,user,'amendment_prepared',{'id':aid,'variation_id':v.id});save(db)
    return {'id':aid,'status':'Draft','effective_value_changed':False}

@router.post('/{cid}/amendments/{aid}/approve')
def approve_amendment(pid:int,cid:int,aid:int,body:AmendmentApprovalIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.approve')
    a=db.query(ContractAmendment).filter_by(id=aid,contract_id=c.id).with_for_update().one_or_none()
    if not a:raise HTTPException(404,'Amendment not found')
    if a.status!='Draft':raise HTTPException(409,'Amendment not awaiting approval')
    if a.prepared_by==user.id:raise HTTPException(403,'Self approval prohibited')
    a.status='Approved Internally';a.approved_by=user.id;a.approval_reason=body.reason
    audit(db,c,user,'amendment_approved',{'id':aid});save(db)
    return {'id':aid,'status':a.status,'effective_value_changed':False}

@router.post('/{cid}/amendments/{aid}/execute')
def execute_amendment(pid:int,cid:int,aid:int,body:AmendmentExecuteIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.sign')
    # Serializes updates across all amendments for a contract.
    c=db.query(Contract).filter_by(id=c.id,project_id=pid,organization_id=user.organization_id).with_for_update().one()
    a=db.query(ContractAmendment).filter_by(id=aid,contract_id=c.id).with_for_update().one_or_none()
    if not a:raise HTTPException(404,'Amendment not found')
    if c.lifecycle not in {'Executed','Active'} or a.status!='Approved Internally':raise HTTPException(409,'Amendment not ready for execution')
    if user.id in {a.prepared_by,a.approved_by}:raise HTTPException(403,'Segregation of duties required')
    verify_signing_authority(db,c,user)
    if a.currency!=c.currency or c.original_value is None:raise HTTPException(422,'Contract monetary basis missing')
    current=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    prior=Decimal(str((current.snapshot or {}).get('effective_value',c.original_value)))
    revised=prior+a.delta_value
    if revised<0:raise HTTPException(422,'Amendment would produce negative effective contract value')
    version_no=c.current_version+1
    snapshot=dict(current.snapshot or {})
    snapshot.update({'effective_value':str(revised),'currency':c.currency,'amendment_id':a.id,'prior_version':c.current_version})
    new_version=ContractVersion(contract_id=c.id,version=version_no,snapshot=snapshot,
                  state='Effective',reason=f'Executed amendment {a.amendment_number}',created_by=user.id)
    db.add(new_version);db.flush()
    copied=carry_forward_boq(db,c.id,current.id,new_version.id)
    a.status='Executed';a.executed_by=user.id;a.execution_evidence=body.evidence
    a.effective_version_id=new_version.id;a.effective_at=datetime.now(timezone.utc)
    c.current_version=version_no;c.published_version=version_no
    v=db.query(ContractRecord).filter_by(id=a.variation_id,contract_id=c.id).one()
    v.status='Amended'
    # Transactional module outbox: no claim of downstream application until acknowledged.
    payload={'event':'contract.amendment.executed','contract_id':c.id,'project_id':pid,
      'organization_id':c.organization_id,'amendment_id':a.id,'version':version_no,
      'currency':c.currency,'delta_value':str(a.delta_value),'effective_value':str(revised)}
    for destination in ('Financials','Planning','Command Center'):
        db.add(ContractModuleDelivery(amendment_id=a.id,destination=destination,payload=payload,status='Pending'))
    audit(db,c,user,'amendment_executed',{'id':a.id,'version':version_no,'pending_destinations':['Financials','Planning','Command Center'],'boq_rows_copied':copied})
    save(db)
    return {'id':a.id,'status':a.status,'current_version':version_no,'effective_value':str(revised),
            'destinations_pending':['Financials','Planning','Command Center']}

@router.get('/{cid}/amendments/{aid}/deliveries')
def amendment_deliveries(pid:int,cid:int,aid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.view_commercial')
    if not db.query(ContractAmendment).filter_by(id=aid,contract_id=c.id).first():raise HTTPException(404,'Amendment not found')
    return [{'destination':d.destination,'status':d.status,'receipt_reference':d.receipt_reference,
             'acknowledged_at':d.acknowledged_at} for d in db.query(ContractModuleDelivery).filter_by(amendment_id=aid)]

class DeliveryReceiptIn(BaseModel):
    receipt_reference: str = Field(min_length=3, max_length=160)
    contract_version: int = Field(ge=1)
    applied: bool
    failure_reason: str | None = Field(default=None, max_length=2000)


@router.post('/{cid}/amendments/{aid}/deliveries/{destination}/receipt')
def record_amendment_delivery_receipt(pid: int, cid: int, aid: int, destination: str,
        body: DeliveryReceiptIn, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Record a confirmed downstream receipt; never apply Financials/Planning changes here."""
    if destination not in {'Financials', 'Planning', 'Command Center'}:
        raise HTTPException(422, 'Unknown integration destination')
    # A dedicated permission prevents an ordinary contract editor from spoofing an acknowledgment.
    c = get_contract(db, user, pid, cid, 'contracts.integration_ack')
    a = db.query(ContractAmendment).filter_by(id=aid, contract_id=c.id).one_or_none()
    if not a or a.status != 'Executed' or not a.effective_version_id:
        raise HTTPException(409, 'Executed amendment not found')
    row = db.query(ContractModuleDelivery).filter_by(amendment_id=aid, destination=destination).with_for_update().one_or_none()
    if not row:
        raise HTTPException(404, 'Delivery not found')
    event = row.payload or {}
    if event.get('event') != 'contract.amendment.executed' or event.get('contract_id') != c.id or event.get('project_id') != pid or event.get('organization_id') != c.organization_id or event.get('amendment_id') != aid or event.get('version') != body.contract_version:
        raise HTTPException(409, 'Receipt does not match immutable amendment event')
    if row.status == 'Acknowledged':
        if body.applied and row.receipt_reference == body.receipt_reference:
            return {'destination': destination, 'status': 'Acknowledged', 'idempotent': True}
        raise HTTPException(409, 'Delivery already acknowledged by a different receipt')
    if body.applied:
        row.status = 'Acknowledged'
        row.acknowledged_at = datetime.now(timezone.utc)
        row.acknowledged_by = user.id
        row.receipt_reference = body.receipt_reference
    else:
        if not body.failure_reason:
            raise HTTPException(422, 'Failure reason required when downstream did not apply event')
        row.status = 'Failed'
        row.receipt_reference = body.receipt_reference
    audit(db, c, user, 'amendment_delivery_receipt', {
        'amendment_id': aid, 'destination': destination, 'status': row.status,
        'receipt_reference': body.receipt_reference, 'failure_reason': body.failure_reason if not body.applied else None})
    save(db)
    return {'destination': destination, 'status': row.status, 'idempotent': False}


@router.post('/{cid}/amendments/{aid}/consume/{destination}')
def consume_contract_amendment(pid: int, cid: int, aid: int, destination: str,
        user: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Receive an executed version into a scoped module projection, then acknowledge atomically.

    This is NOT a financial posting or a Planning baseline change. Such actions
    require their module-specific approval flows and independently verified links.
    """
    if destination not in {'Financials', 'Planning'}:
        raise HTTPException(422, 'Only Financials or Planning may consume')
    c = get_contract(db, user, pid, cid, 'contracts.integration_ack')
    a = db.query(ContractAmendment).filter_by(id=aid, contract_id=cid).one_or_none()
    if not a or a.status != 'Executed' or not a.effective_version_id:
        raise HTTPException(409, 'Amendment not executed')
    d = (db.query(ContractModuleDelivery)
         .filter_by(amendment_id=aid, destination=destination)
         .with_for_update().one_or_none())
    if d is None:
        raise HTTPException(404, 'Destination delivery does not exist')
    event = d.payload or {}
    if any((event.get(k) != value) for k, value in {
        'event': 'contract.amendment.executed', 'contract_id': cid,
        'project_id': pid, 'organization_id': c.organization_id,
        'amendment_id': aid
    }.items()):
        raise HTTPException(409, 'Event scope or identity mismatch')
    effective_version = db.query(ContractVersion).filter_by(id=a.effective_version_id,contract_id=cid).one_or_none()
    if not effective_version or event.get('version') != effective_version.version:
        raise HTTPException(409, 'Effective version mismatch')
    existing = (db.query(ContractConsumerProjection)
                .filter_by(amendment_id=aid,destination=destination).one_or_none())
    if existing:
        if existing.payload != event or existing.contract_version != effective_version.version:
            raise HTTPException(409, 'Conflicting previously consumed event')
        if d.status != 'Acknowledged':
            raise HTTPException(409, 'Projection exists but receipt requires reconciliation')
        return {'destination': destination, 'status': 'Acknowledged', 'idempotent': True,
                'receipt_reference': d.receipt_reference}
    if d.status == 'Acknowledged':
        raise HTTPException(409, 'Previously acknowledged without a projection; manual reconciliation required')
    projection = ContractConsumerProjection(organization_id=c.organization_id,project_id=pid,
        contract_id=cid,amendment_id=aid,destination=destination,
        contract_version=effective_version.version,payload=event,received_by=user.id)
    db.add(projection)
    receipt = f'contracts-consumer:{destination.lower()}:{aid}:v{effective_version.version}'
    d.status = 'Acknowledged'; d.receipt_reference = receipt
    d.acknowledged_by = user.id; d.acknowledged_at = datetime.now(timezone.utc)
    audit(db,c,user,'amendment_consumed',{'amendment_id':aid,'destination':destination,
          'contract_version':effective_version.version,'receipt_reference':receipt})
    save(db)
    return {'destination': destination, 'status': 'Acknowledged', 'idempotent': False,
            'receipt_reference': receipt, 'financial_posting_created': False,
            'planning_baseline_changed': False}


class FinanceLinkIn(BaseModel):
    finance_contract_id: int = Field(gt=0)


def finance_contract_effective_value(db: Session, contract: Contract):
    version = db.query(ContractVersion).filter_by(
        contract_id=contract.id, version=contract.current_version).one_or_none()
    if not version:
        raise HTTPException(409, 'Authoritative contract version missing')
    raw = (version.snapshot or {}).get('effective_value')
    if raw is None:
        raw = contract.original_value
    if raw is None:
        raise HTTPException(409, 'Contract has no verified monetary value')
    try:
        return Decimal(str(raw))
    except Exception:
        raise HTTPException(409, 'Invalid authoritative effective value')


@router.post('/{cid}/integrations/finance-link')
def create_finance_link(pid: int, cid: int, body: FinanceLinkIn,
        user: User = Depends(authenticated), db: Session = Depends(get_db)):
    c = get_contract(db, user, pid, cid, 'contracts.view_commercial')
    project_guard(db,user,pid,'contracts.integration_ack')
    legacy = db.query(FinanceContract).filter_by(id=body.finance_contract_id,
        organization_id=c.organization_id, project_id=pid).one_or_none()
    if not legacy:
        raise HTTPException(404, 'Financials contract not found in project')
    if (legacy.number != c.number or legacy.counterparty_company_id != c.counterparty_company_id
        or legacy.currency != c.currency or legacy.contract_type != c.contract_type):
        raise HTTPException(409, 'Financials contract identity, counterparty, currency, or type mismatch')
    if c.original_value is None or legacy.original_value != c.original_value:
        raise HTTPException(409, 'Original values do not reconcile')
    prior = db.query(ContractFinanceLink).filter_by(contract_id=cid).one_or_none()
    other = db.query(ContractFinanceLink).filter_by(finance_contract_id=legacy.id).one_or_none()
    if prior or other:
        if prior and prior.finance_contract_id == legacy.id and other and other.contract_id == cid:
            return {'contract_id':cid,'finance_contract_id':legacy.id,'idempotent':True}
        raise HTTPException(409, 'One of the contracts is already linked elsewhere')
    db.add(ContractFinanceLink(organization_id=c.organization_id, project_id=pid,
        contract_id=cid, finance_contract_id=legacy.id, linked_by=user.id))
    audit(db,c,user,'finance_contract_linked',{'finance_contract_id':legacy.id})
    save(db)
    return {'contract_id':cid,'finance_contract_id':legacy.id,'idempotent':False}


@router.get('/{cid}/integrations/finance-effective-value')
def read_finance_effective_value(pid: int,cid: int,
        user: User = Depends(authenticated), db: Session = Depends(get_db)):
    c = get_contract(db,user,pid,cid,'contracts.view_commercial')
    link = db.query(ContractFinanceLink).filter_by(contract_id=cid,
        organization_id=c.organization_id,project_id=pid).one_or_none()
    if not link:
        return {'contract_id':cid,'linked':False,'sync_status':'Unlinked'}
    legacy = db.query(FinanceContract).filter_by(id=link.finance_contract_id,
        organization_id=c.organization_id,project_id=pid).one_or_none()
    if not legacy:
        raise HTTPException(409,'Linked Financials record missing')
    effective=finance_contract_effective_value(db,c)
    pending=db.query(ContractModuleDelivery).join(ContractAmendment,
        ContractModuleDelivery.amendment_id==ContractAmendment.id).filter(
        ContractAmendment.contract_id==cid,ContractModuleDelivery.destination=='Financials',
        ContractModuleDelivery.status!='Acknowledged').count()
    return {'contract_id':cid,'finance_contract_id':legacy.id,'linked':True,
        'currency':c.currency,'original_value':str(c.original_value),
        'approved_effective_value':str(effective),
        'legacy_finance_original_value':str(legacy.original_value),
        'pending_financials_deliveries':pending,
        'sync_status':'Pending acknowledgment' if pending else 'Receipts reconciled',
        'billing_records_modified':False,'legacy_original_value_modified':False}


class ProcurementLinkIn(BaseModel):
    purchase_order_id: int = Field(gt=0)


@router.post('/{cid}/integrations/procurement-links')
def link_procurement_po(pid: int, cid: int, body: ProcurementLinkIn,
        user: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Link an existing issued PO; never approve, issue, or change procurement records."""
    c = get_contract(db, user, pid, cid, 'contracts.view_commercial')
    project_guard(db, user, pid, 'contracts.integration_ack')
    if c.lifecycle not in {'Executed', 'Active', 'Completed', 'Closed'}:
        raise HTTPException(409, 'A governing contract must be executed')
    po = db.query(PurchaseOrder).filter_by(id=body.purchase_order_id,
        organization_id=c.organization_id, project_id=pid).one_or_none()
    if not po:
        raise HTTPException(404, 'Purchase order not found in project')
    if po.status in {'Draft', 'Cancelled'} or not po.issue_date:
        raise HTTPException(409, 'Only issued, non-cancelled POs can be linked')
    vendor = db.query(Vendor).filter_by(id=po.vendor_id, organization_id=c.organization_id).one_or_none()
    if not vendor or vendor.company_id != c.counterparty_company_id:
        raise HTTPException(409, 'PO vendor does not match contract counterparty')
    if po.currency != c.currency:
        raise HTTPException(409, 'PO and governing contract currencies differ')
    version = db.query(ContractVersion).filter_by(contract_id=cid,
        version=c.current_version).one_or_none()
    if not version or c.lifecycle not in {'Executed', 'Active', 'Completed', 'Closed'}:
        raise HTTPException(409, 'Effective governing version unavailable')
    previous = db.query(ContractProcurementLink).filter_by(purchase_order_id=po.id).one_or_none()
    if previous:
        if previous.contract_id==cid and previous.contract_version_id==version.id:
            return {'linked': True, 'idempotent': True, 'purchase_order_id': po.id,
                    'contract_id': cid, 'contract_version_id': version.id}
        raise HTTPException(409, 'PO is already linked to a different contract/version')
    db.add(ContractProcurementLink(organization_id=c.organization_id, project_id=pid,
        contract_id=cid, contract_version_id=version.id, purchase_order_id=po.id, linked_by=user.id))
    audit(db, c, user, 'procurement_governing_agreement_linked',
          {'purchase_order_id': po.id, 'contract_version_id': version.id})
    save(db)
    return {'linked': True, 'idempotent': False, 'purchase_order_id': po.id,
            'contract_id': cid, 'contract_version_id': version.id,
            'purchase_order_modified': False}


@router.get('/{cid}/integrations/procurement-links')
def list_procurement_links(pid: int, cid: int,
        user: User = Depends(authenticated), db: Session = Depends(get_db)):
    c = get_contract(db, user, pid, cid, 'contracts.view_commercial')
    links = db.query(ContractProcurementLink).filter_by(organization_id=c.organization_id,
        project_id=pid, contract_id=cid).all()
    return [{'purchase_order_id': r.purchase_order_id,
             'contract_version_id': r.contract_version_id, 'linked_at': r.linked_at}
            for r in links]


@router.get('/integrations/consumer-projections')
def consumer_projections(pid: int, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    project_guard(db,user,pid,'contracts.view_commercial')
    rows = db.query(ContractConsumerProjection).filter_by(organization_id=user.organization_id,
        project_id=pid).order_by(ContractConsumerProjection.id.desc()).limit(250).all()
    return [{'contract_id':r.contract_id,'amendment_id':r.amendment_id,
        'destination':r.destination,'version':r.contract_version,
        'received_at':r.received_at} for r in rows]


@router.get('/integrations/reconciliation')
def amendment_delivery_reconciliation(pid: int, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Report outstanding delivery status without claiming downstream application."""
    project_guard(db, user, pid, 'contracts.view_commercial')
    rows = (db.query(ContractModuleDelivery, ContractAmendment, Contract)
            .join(ContractAmendment, ContractModuleDelivery.amendment_id == ContractAmendment.id)
            .join(Contract, ContractAmendment.contract_id == Contract.id)
            .filter(Contract.project_id == pid, Contract.organization_id == user.organization_id)
            .order_by(ContractModuleDelivery.id).all())
    return [{'contract_id': c.id, 'amendment_id': a.id, 'destination': d.destination,
             'status': d.status, 'version': (d.payload or {}).get('version'),
             'receipt_reference': d.receipt_reference}
            for d, a, c in rows]


class ShareIn(BaseModel):
    company_id:int
    can_submit:bool=False

@router.post('/{cid}/partner-shares')
def publish(pid:int,cid:int,body:ShareIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_sharing')
    if c.lifecycle not in {'Executed','Active'}:raise HTTPException(409,'Only executed versions may be shared')
    if body.company_id!=c.counterparty_company_id:raise HTTPException(422,'Only the contract counterparty is eligible')
    p=db.query(ProjectCompany).filter_by(project_id=pid,company_id=body.company_id,active=True).one_or_none()
    if not p:raise HTTPException(403,'Company not active in project')
    s=db.query(ContractPartnerShare).filter_by(contract_id=c.id,company_id=body.company_id).one_or_none()
    if s:s.published_version=c.current_version;s.active=True;s.can_submit=body.can_submit
    else:s=ContractPartnerShare(contract_id=c.id,company_id=body.company_id,published_version=c.current_version,can_submit=body.can_submit,shared_by=user.id);db.add(s)
    c.published_version=c.current_version
    audit(db,c,user,'partner_published',{'company_id':body.company_id,'version':c.current_version});save(db)
    return {'contract_id':c.id,'published_version':c.published_version,'partner_company_id':body.company_id}

@router.post('/{cid}/partner-shares/{company_id}/revoke')
def revoke(pid:int,cid:int,company_id:int,body:DecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_sharing')
    s=db.query(ContractPartnerShare).filter_by(contract_id=c.id,company_id=company_id,active=True).one_or_none()
    if not s:raise HTTPException(404,'No active share')
    s.active=False;audit(db,c,user,'partner_revoked',{'company_id':company_id,'reason':body.reason});save(db)
    return {'revoked':True}

def partner_scope(db,user):
    if not user.active or user.organization_admin or not user.company_id:raise HTTPException(403,'Partner identity required')
    company=db.get(Company,user.company_id)
    if not company or not company.active or company.organization_id!=user.organization_id:raise HTTPException(403,'Invalid company')
    return company

def partner_allowed(db,user,cid):
    company=partner_scope(db,user)
    c=db.query(Contract).filter_by(id=cid,organization_id=user.organization_id,counterparty_company_id=company.id).one_or_none()
    if not c:raise HTTPException(404,'Contract unavailable')
    member=db.query(Membership).filter_by(project_id=c.project_id,company_id=company.id,user_id=user.id,active=True).first()
    project_company=db.query(ProjectCompany).filter_by(project_id=c.project_id,company_id=company.id,active=True).first()
    share=db.query(ContractPartnerShare).filter_by(contract_id=cid,company_id=company.id,active=True).one_or_none()
    if not member or not project_company or not share:raise HTTPException(404,'Contract unavailable')
    return c,share

# Document references are never public URLs. The file service MUST reauthorize
# each byte transfer against this ledger and the current partner membership.
ALLOWED_PARTNER_DOC_CLASSES={'agreement','scope','deliverable','correspondence','notice','evidence','insurance'}
class PartnerDocumentPublish(BaseModel):
    company_id:int
    document_key:str=Field(min_length=2,max_length=160,pattern=r'^[A-Za-z0-9_.-]+$')
    revision:int=Field(ge=1)
    display_name:str=Field(min_length=2,max_length=240)
    document_class:str
    private_storage_key:str=Field(min_length=4,max_length=500)
    content_sha256:str=Field(pattern=r'^[a-fA-F0-9]{64}$')
    expires_at:datetime|None=None

def _partner_stored_file(db, organization_id, storage_key, expected_sha256):
    if not storage_key.startswith('stored-file:') or not storage_key[12:].isdigit():
        raise HTTPException(422,'Document must reference a private stored-file upload')
    stored=db.get(StoredFile,int(storage_key[12:]))
    if (not stored or stored.organization_id!=organization_id
            or stored.scan_status!='available'
            or not hmac.compare_digest(stored.sha256.lower(),expected_sha256.lower())):
        raise HTTPException(404,'Private document unavailable')
    return stored

@router.post('/{cid}/partner-documents',status_code=201)
def partner_document_publish(pid:int,cid:int,body:PartnerDocumentPublish,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_sharing')
    if body.company_id!=c.counterparty_company_id:raise HTTPException(403,'Not contract counterparty')
    share=db.query(ContractPartnerShare).filter_by(contract_id=cid,company_id=body.company_id,active=True).one_or_none()
    if not share:raise HTTPException(409,'Publish contract share before documents')
    if body.document_class not in ALLOWED_PARTNER_DOC_CLASSES:raise HTTPException(422,'Document class is not shareable')
    if body.expires_at is not None:
        if body.expires_at.tzinfo is None or body.expires_at<=datetime.now(timezone.utc):raise HTTPException(422,'Invalid expiry')
    # Storage key must identify a PRIVATE verified upload, not a URL or filesystem path.
    if '://' in body.private_storage_key or body.private_storage_key.startswith('/') or '..' in body.private_storage_key:
        raise HTTPException(422,'Private storage key required')
    # Only publish an actual private upload owned by this organization. The
    # key is a typed database reference, never an unvalidated filesystem path.
    stored=_partner_stored_file(db,c.organization_id,body.private_storage_key,body.content_sha256)
    ver=db.query(ContractVersion).filter_by(contract_id=cid,version=share.published_version).one_or_none()
    if not ver:raise HTTPException(409,'Published version unavailable')
    existing=db.query(ContractPartnerDocument).filter_by(contract_id=cid,company_id=body.company_id,document_key=body.document_key,revision=body.revision).one_or_none()
    if existing:raise HTTPException(409,'Immutable document revision already exists')
    doc=ContractPartnerDocument(contract_id=cid,company_id=body.company_id,contract_version_id=ver.id,
        document_key=body.document_key,revision=body.revision,display_name=body.display_name,
        document_class=body.document_class,private_storage_key=body.private_storage_key,
        content_sha256=body.content_sha256.lower(),published_by=user.id,expires_at=body.expires_at)
    db.add(doc);db.flush();doc_id=doc.id
    audit(db,c,user,'partner_document_published',{'document_id':doc_id,'version':share.published_version});save(db)
    return {'id':doc_id,'revision':body.revision}

def partner_document_guard(db,user,cid,document_id):
    c,share=partner_allowed(db,user,cid)
    doc=db.query(ContractPartnerDocument).filter_by(id=document_id,contract_id=cid,company_id=share.company_id,revoked_at=None).one_or_none()
    if not doc or (doc.expires_at and doc.expires_at.replace(tzinfo=doc.expires_at.tzinfo or timezone.utc)<=datetime.now(timezone.utc)):
        raise HTTPException(404,'Document unavailable')
    v=db.get(ContractVersion,doc.contract_version_id)
    if not v or v.contract_id!=cid or v.version!=share.published_version:raise HTTPException(404,'Document version unavailable')
    return doc

@partner.get('/{cid}/documents')
def partner_documents(cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,share=partner_allowed(db,user,cid)
    docs=db.query(ContractPartnerDocument).filter_by(contract_id=cid,company_id=share.company_id,revoked_at=None).all()
    result=[]
    for d in docs:
        try: partner_document_guard(db,user,cid,d.id)
        except HTTPException:continue
        result.append({'id':d.id,'document_key':d.document_key,'revision':d.revision,'title':d.display_name,'class':d.document_class})
    return result

@partner.get('/{cid}/documents/{document_id}')
def partner_document_detail(cid:int,document_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    doc=partner_document_guard(db,user,cid,document_id)
    # Deliberately never return private_storage_key or a reusable download URL.
    return {'id':doc.id,'title':doc.display_name,'revision':doc.revision,'sha256':doc.content_sha256,'download_status':'authorized_download_endpoint'}

@partner.get('/{cid}/documents/{document_id}/download')
def partner_document_download(cid:int,document_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    # Re-evaluate contract/share/company/version/expiry/revocation for EACH request.
    c,share=partner_allowed(db,user,cid)
    doc=partner_document_guard(db,user,cid,document_id)
    stored=_partner_stored_file(db,c.organization_id,doc.private_storage_key,doc.content_sha256)
    content=read_file(stored)
    # Reject disk corruption or out-of-band file replacement.
    import hashlib
    if not hmac.compare_digest(hashlib.sha256(content).hexdigest(),doc.content_sha256.lower()):
        raise HTTPException(409,'Document integrity check failed')
    name=(stored.original_name or 'document').replace('"','').replace('\r','').replace('\n','')
    audit(db,c,user,'partner_document_downloaded',{'document_id':doc.id,'file_id':stored.id})
    save(db)
    return Response(content=content,media_type=stored.content_type,headers={
        'Content-Disposition':f'attachment; filename="{name}"',
        'Cache-Control':'no-store, private',
        'X-Content-Type-Options':'nosniff',
    })

@router.post('/{cid}/partner-documents/{document_id}/revoke')
def partner_document_revoke(pid:int,cid:int,document_id:int,body:DecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_sharing')
    doc=db.query(ContractPartnerDocument).filter_by(id=document_id,contract_id=cid,revoked_at=None).one_or_none()
    if not doc:raise HTTPException(404,'Document unavailable')
    doc.revoked_at=datetime.now(timezone.utc)
    audit(db,c,user,'partner_document_revoked',{'document_id':document_id,'reason':body.reason});save(db)
    return {'revoked':True}

@partner.get('')
def partner_list(user:User=Depends(authenticated),db:Session=Depends(get_db)):
    company=partner_scope(db,user)
    shares=db.query(ContractPartnerShare).filter_by(company_id=company.id,active=True).limit(200)
    result=[]
    for sh in shares:
        try:c,_=partner_allowed(db,user,sh.contract_id)
        except HTTPException:continue
        result.append({'id':c.id,'number':c.number,'title':c.title,'status':c.lifecycle,'version':sh.published_version})
    return result

@partner.get('/{cid}')
def partner_detail(cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,share=partner_allowed(db,user,cid)
    return {'id':c.id,'number':c.number,'title':c.title,'scope':c.scope,'status':c.lifecycle,'version':share.published_version,'can_submit':share.can_submit}

class PartnerSubmission(BaseModel):
    category:str
    number:str=Field(min_length=2,max_length=80)
    summary:str=Field(min_length=8,max_length=4000)
    evidence:str=Field(min_length=8,max_length=2000)

@partner.post('/{cid}/submissions',status_code=201)
def partner_submit(cid:int,body:PartnerSubmission,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,share=partner_allowed(db,user,cid)
    if not share.can_submit:raise HTTPException(403,'Submission not granted')
    if body.category not in {'notice','claim','variation','obligation','security','correspondence'}:raise HTTPException(422,'Unsupported partner submission')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=share.published_version).one()
    r=ContractRecord(contract_id=c.id,version_id=v.id,category=body.category,number=body.number,summary=body.summary,status='Submitted',evidence=body.evidence,details={'source':'partner','company_id':user.company_id},created_by=user.id)
    db.add(r);audit(db,c,user,'partner_submitted',{'category':body.category,'number':body.number});save(db)
    return {'id':r.id,'status':r.status,'contract_id':c.id}

@partner.get('/{cid}/submissions')
def partner_submissions(cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,_=partner_allowed(db,user,cid)
    rows=db.query(ContractRecord).filter_by(contract_id=c.id).all()
    return [{'number':r.number,'category':r.category,'status':r.status,'summary':r.summary} for r in rows if (r.details or {}).get('source')=='partner' and (r.details or {}).get('company_id')==user.company_id]

@router.get('/intelligence')
def intelligence(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    project_guard(db,user,pid)
    cs=db.query(Contract).filter_by(organization_id=user.organization_id,project_id=pid).all()
    statuses={}; values={}; proposed={}; overdue=0
    now=datetime.now(timezone.utc)
    for c in cs:
        statuses[c.lifecycle]=statuses.get(c.lifecycle,0)+1
        if c.lifecycle in {'Executed','Active','Completed','Closed'} and c.currency and c.original_value is not None:
            values[c.currency]=values.get(c.currency,Decimal('0'))+c.original_value
        for r in db.query(ContractRecord).filter_by(contract_id=c.id).all():
            if r.category in {'variation','claim'} and r.status not in {'Accepted','Rejected'} and r.currency and r.amount is not None:
                proposed[r.currency]=proposed.get(r.currency,Decimal('0'))+r.amount
            if r.category=='obligation' and r.due_at and r.due_at<now and r.status not in {'Accepted','Waived','Cancelled'}:overdue+=1
    return {'source':'ZerroBuild Contracts','as_of':now.isoformat(),'project_id':pid,'read_only':True,'contracts_by_status':statuses,'executed_base_value_by_currency':{k:str(v) for k,v in values.items()},'proposed_exposure_by_currency':{k:str(v) for k,v in proposed.items()},'overdue_obligations':overdue,'effective_amendments_verified':False,'reconciliation_complete':False}

@router.get('/internal-intelligence')
def internal_intelligence(pid:int,request:Request,db:Session=Depends(get_db)):
    expected=settings.command_center_identity_service_key
    if not expected or not hmac.compare_digest(request.headers.get('X-ZerroR-Service-Key',''),expected):raise HTTPException(403,'Internal service key required')
    p=db.get(Project,pid)
    if not p:raise HTTPException(404,'Project not found')
    from .intelligence import build_intelligence
    cs=db.query(Contract).filter_by(project_id=pid,organization_id=p.organization_id).all()
    contract_ids=[c.id for c in cs]
    if not contract_ids:
        return build_intelligence(pid,[],[],[],[],[],[])
    amendments=db.query(ContractAmendment).filter(ContractAmendment.contract_id.in_(contract_ids)).all()
    obligations=db.query(ContractObligation).filter(ContractObligation.project_id==pid,ContractObligation.organization_id==p.organization_id,ContractObligation.contract_id.in_(contract_ids)).all()
    claims=db.query(ContractClaim).filter(ContractClaim.project_id==pid,ContractClaim.organization_id==p.organization_id,ContractClaim.contract_id.in_(contract_ids)).all()
    securities=db.query(ContractSecurityInstrument).filter(ContractSecurityInstrument.project_id==pid,ContractSecurityInstrument.organization_id==p.organization_id,ContractSecurityInstrument.contract_id.in_(contract_ids)).all()
    amendment_ids=[a.id for a in amendments]
    deliveries=db.query(ContractModuleDelivery).filter(ContractModuleDelivery.amendment_id.in_(amendment_ids)).all() if amendment_ids else []
    return build_intelligence(pid,cs,amendments,obligations,claims,securities,deliveries)


# Requirement sections 4–6: structured, version-bound scope and commercial terms.
SCOPE_TYPES = {'Included Scope','Exclusion','Deliverable','Interface Responsibility',
               'Client Supplied','Contractor Supplied','Required Approval',
               'Acceptance/Handover','Reporting Requirement'}
TERM_KEYS = {'pricing_basis','milestone_payment_schedule','billing_frequency',
             'invoice_submission','payment_due_rule','advance_recovery',
             'retention_release','approved_deductions','tax_references',
             'warranty_defects','security_requirements','insurance_requirements'}

class ScopeItemIn(BaseModel):
    item_code:str=Field(min_length=1,max_length=80)
    item_type:str
    description:str=Field(min_length=3,max_length=5000)
    responsible_company_id:int|None=None
    responsible_user_id:int|None=None
    reviewer_user_id:int|None=None
    due_at:datetime|None=None
    required_evidence:str|None=Field(default=None,max_length=3000)

class TermVersionIn(BaseModel):
    term_key:str
    clause_reference:str|None=Field(default=None,max_length=120)
    value:dict

def editable_contract_version(db,c):
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    if c.lifecycle != 'Draft' or v.state != 'Draft':
        raise HTTPException(409,'Contract version locked; use controlled amendment process')
    return v

def verify_party_assignment(db,c,company_id,user_id):
    if company_id is not None:
        company=db.get(Company,company_id)
        if not company or company.organization_id!=c.organization_id or not company.active:
            raise HTTPException(422,'Assigned company not in organization')
    if user_id is not None:
        actor=db.get(User,user_id)
        if not actor or actor.organization_id!=c.organization_id or not actor.active:
            raise HTTPException(422,'Assigned user not in organization')
        # A project assignment is required; a contractual responsibility does not grant access.
        if not db.query(Membership).filter_by(project_id=c.project_id,user_id=user_id,active=True).first():
            raise HTTPException(422,'Assigned user lacks active project membership')

@router.post('/{cid}/scope-items',status_code=201)
def add_scope_item(pid:int,cid:int,body:ScopeItemIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_terms')
    v=editable_contract_version(db,c)
    if body.item_type not in SCOPE_TYPES:raise HTTPException(422,'Unsupported scope type')
    verify_party_assignment(db,c,body.responsible_company_id,body.responsible_user_id)
    verify_party_assignment(db,c,None,body.reviewer_user_id)
    x=ContractScopeItem(contract_id=c.id,version_id=v.id,created_by=user.id,**body.model_dump())
    db.add(x);audit(db,c,user,'scope_item_added',{'code':body.item_code,'version':v.version})
    db.flush();out_id=x.id;save(db)
    return {'id':out_id,'item_code':body.item_code,'version':v.version}

@router.get('/{cid}/scope-items')
def list_scope_items(pid:int,cid:int,version:int|None=None,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid)
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=version or c.current_version).one_or_none()
    if not v:raise HTTPException(404,'Version not found')
    return [{'id':x.id,'item_code':x.item_code,'item_type':x.item_type,
             'description':x.description,'responsible_company_id':x.responsible_company_id,
             'responsible_user_id':x.responsible_user_id,'reviewer_user_id':x.reviewer_user_id,
             'due_at':x.due_at,'required_evidence':x.required_evidence}
            for x in db.query(ContractScopeItem).filter_by(version_id=v.id).order_by(ContractScopeItem.id).all()]

@router.post('/{cid}/commercial-terms',status_code=201)
def add_commercial_term(pid:int,cid:int,body:TermVersionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_terms')
    v=editable_contract_version(db,c)
    if body.term_key not in TERM_KEYS:raise HTTPException(422,'Unsupported commercial term')
    if not body.value:raise HTTPException(422,'Structured value required')
    x=ContractTermVersion(contract_id=c.id,version_id=v.id,created_by=user.id,**body.model_dump())
    db.add(x);audit(db,c,user,'commercial_term_added',{'key':body.term_key,'version':v.version})
    db.flush();out_id=x.id;save(db)
    return {'id':out_id,'term_key':body.term_key,'version':v.version}

@router.get('/{cid}/commercial-terms')
def list_commercial_terms(pid:int,cid:int,version:int|None=None,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.view_commercial')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=version or c.current_version).one_or_none()
    if not v:raise HTTPException(404,'Version not found')
    return [{'id':x.id,'term_key':x.term_key,'clause_reference':x.clause_reference,'value':x.value}
            for x in db.query(ContractTermVersion).filter_by(version_id=v.id).order_by(ContractTermVersion.id).all()]


# CM0110 — Dedicated contractual obligations, distinct from generic tasks.
OBLIGATION_STATES={'Not Started','In Progress','Submitted','Accepted','Overdue','Waived','Cancelled'}

def obligation_datetime(value):
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise HTTPException(422,'Timezone-aware obligation dates required')
    return value.astimezone(timezone.utc) if value else None

def obligation_due(trigger_at,days):
    # Never invent a trigger date or due date from free-text clauses.
    return obligation_datetime(trigger_at)+timedelta(days=days) if trigger_at is not None and days is not None else None

def obligation_view(o):
    current=datetime.now(timezone.utc)
    overdue=bool(o.due_at and obligation_datetime(o.due_at)<current and o.status not in {'Accepted','Waived','Cancelled'})
    return {'id':o.id,'number':o.number,'contract_id':o.contract_id,'version_id':o.version_id,'clause_reference':o.clause_reference,
        'description':o.description,'responsible_company_id':o.responsible_company_id,'owner_user_id':o.owner_user_id,
        'trigger_name':o.trigger_name,'trigger_at':o.trigger_at,'due_days':o.due_days,'due_at':o.due_at,
        'deadline_unresolved':o.due_at is None,'overdue':overdue,'status':o.status,'required_evidence':o.required_evidence,
        'acceptance_required':o.acceptance_required,'evidence':o.evidence,'decision_evidence':o.decision_evidence}

class ObligationIn(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    description:str=Field(min_length=5,max_length=4000)
    clause_reference:str|None=Field(default=None,max_length=120)
    responsible_company_id:int
    owner_user_id:int
    trigger_name:str|None=Field(default=None,max_length=120)
    trigger_at:datetime|None=None
    due_days:int|None=Field(default=None,ge=0,le=36500)
    required_evidence:str|None=None
    acceptance_required:bool=True

@router.post('/{cid}/obligations',status_code=201)
def obligation_create(pid:int,cid:int,body:ObligationIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_obligations')
    if (body.trigger_at is not None or body.due_days is not None) and not body.trigger_name:
        raise HTTPException(422,'Trigger name required for computed deadline')
    if body.trigger_at is None and body.due_days is not None and not body.trigger_name:
        raise HTTPException(422,'Trigger name required')
    if body.responsible_company_id not in {c.contracting_company_id,c.counterparty_company_id}:
        raise HTTPException(422,'Responsible company must be a party to the contract')
    owner=db.get(User,body.owner_user_id)
    if not owner or not owner.active or owner.organization_id!=c.organization_id:
        raise HTTPException(422,'Invalid obligation owner')
    project_guard(db,owner,pid,'contracts.view_summary')
    version=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    data=body.model_dump();data['trigger_at']=obligation_datetime(body.trigger_at)
    data['due_at']=obligation_due(body.trigger_at,body.due_days)
    o=ContractObligation(organization_id=c.organization_id,project_id=pid,contract_id=cid,version_id=version.id,
        created_by=user.id,**data)
    db.add(o);audit(db,c,user,'obligation_created',{'number':body.number,'deadline_unresolved':data['due_at'] is None})
    db.flush();oid=o.id;save(db)
    return {'id':oid,'number':body.number,'due_at':data['due_at']}

@router.get('/{cid}/obligations')
def obligation_list(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid)
    return [obligation_view(o) for o in db.query(ContractObligation).filter_by(contract_id=c.id,organization_id=c.organization_id).order_by(ContractObligation.id).limit(500)]

class ObligationTriggerIn(BaseModel):
    trigger_at:datetime
    evidence:str=Field(min_length=4,max_length=4000)

@router.post('/{cid}/obligations/{oid}/trigger')
def obligation_trigger(pid:int,cid:int,oid:int,body:ObligationTriggerIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_obligations')
    o=db.query(ContractObligation).filter_by(id=oid,contract_id=c.id,organization_id=c.organization_id).one_or_none()
    if not o:raise HTTPException(404,'Obligation not found')
    if o.trigger_at is not None or o.status in {'Accepted','Waived','Cancelled'}:raise HTTPException(409,'Trigger is not editable')
    if not o.trigger_name:raise HTTPException(409,'No configured trigger')
    o.trigger_at=obligation_datetime(body.trigger_at);o.due_at=obligation_due(o.trigger_at,o.due_days)
    audit(db,c,user,'obligation_trigger_recorded',{'obligation_id':o.id,'evidence':body.evidence,'due_at':str(o.due_at)})
    save(db);return obligation_view(o)

class ObligationEvidenceIn(BaseModel):
    evidence:str=Field(min_length=4,max_length=4000)

@router.post('/{cid}/obligations/{oid}/submit')
def obligation_submit(pid:int,cid:int,oid:int,body:ObligationEvidenceIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_obligations')
    o=db.query(ContractObligation).filter_by(id=oid,contract_id=c.id,organization_id=c.organization_id).one_or_none()
    if not o:raise HTTPException(404,'Obligation not found')
    if o.owner_user_id!=user.id and not user.organization_admin:raise HTTPException(403,'Assigned owner required')
    if o.status not in {'Not Started','In Progress','Overdue'}:raise HTTPException(409,'Invalid submission state')
    o.evidence=body.evidence;o.status='Submitted'
    audit(db,c,user,'obligation_submitted',{'obligation_id':o.id});save(db)
    return obligation_view(o)

class ObligationDecisionIn(BaseModel):
    decision:str
    reason:str=Field(min_length=4,max_length=4000)
    evidence:str=Field(min_length=4,max_length=4000)

@router.post('/{cid}/obligations/{oid}/decide')
def obligation_decide(pid:int,cid:int,oid:int,body:ObligationDecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.approve')
    o=db.query(ContractObligation).filter_by(id=oid,contract_id=c.id,organization_id=c.organization_id).one_or_none()
    if not o:raise HTTPException(404,'Obligation not found')
    if o.created_by==user.id or o.owner_user_id==user.id:raise HTTPException(403,'Self acceptance/waiver prohibited')
    if body.decision not in {'Accepted','Waived','Returned','Cancelled'}:raise HTTPException(422,'Invalid decision')
    if body.decision=='Accepted' and o.status!='Submitted':raise HTTPException(409,'Submit evidence before acceptance')
    if body.decision=='Returned' and o.status!='Submitted':raise HTTPException(409,'Only submitted obligations can be returned')
    if o.status in {'Accepted','Waived','Cancelled'}:raise HTTPException(409,'Obligation already closed')
    o.status='In Progress' if body.decision=='Returned' else body.decision
    o.decision_evidence=body.evidence;o.decided_by=user.id;o.decided_at=datetime.now(timezone.utc)
    audit(db,c,user,'obligation_decided',{'obligation_id':o.id,'decision':body.decision,'reason':body.reason,'evidence':body.evidence})
    save(db);return obligation_view(o)


# CM0111: Project-scoped obligation reminder/escalation queue.
# Read-only candidates: a sender must use host notification service and record delivery.
@router.get('/obligation-alerts')
def obligation_alerts(pid:int,within_days:int=7,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    project_guard(db,user,pid,'contracts.view_summary')
    if within_days<0 or within_days>90:raise HTTPException(422,'within_days must be 0..90')
    now_at=datetime.now(timezone.utc)
    obligations=db.query(ContractObligation).filter_by(organization_id=user.organization_id,project_id=pid).all()
    events=obligation_alert_candidates(obligations,now_at,within_days)
    return {'as_of':now_at,'window_days':within_days,'alerts':events,
        'counts':{kind:sum(1 for e in events if e['kind']==kind) for kind in ('overdue','upcoming','unresolved')},
        'delivery_state':'not_dispatched'}

def obligation_alert_candidates(obligations,now_at,within_days):
    upper=now_at+timedelta(days=within_days)
    events=[]
    for o in obligations:
        if o.status in {'Accepted','Waived','Cancelled'}:continue
        if o.due_at is None:
            events.append({'obligation_id':o.id,'contract_id':o.contract_id,'number':o.number,'kind':'unresolved',
                'due_at':None,'owner_user_id':o.owner_user_id,'responsible_company_id':o.responsible_company_id})
            continue
        due=obligation_datetime(o.due_at)
        if due>upper:continue
        kind='overdue' if due<now_at else 'upcoming'
        events.append({'obligation_id':o.id,'contract_id':o.contract_id,'number':o.number,'kind':kind,
            'due_at':due,'owner_user_id':o.owner_user_id,'responsible_company_id':o.responsible_company_id})
    return events


# CM0114: Claims and EOT are distinct from variations and formal amendments.
CLAIM_TYPES={'Additional Work','Quantity Change','Design Change','Delay/EOT','Disruption','Cost Claim','Other'}

class ClaimCreateIn(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    category:str
    description:str=Field(min_length=8,max_length=4000)
    event_at:datetime
    clause_reference:str|None=Field(default=None,max_length=160)
    source_reference:str|None=None
    notice_required:bool=False
    notice_due_at:datetime|None=None
    submission_due_at:datetime|None=None
    requested_amount:Decimal|None=Field(default=None,ge=0,max_digits=20,decimal_places=2)
    currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$')
    requested_eot_days:int|None=Field(default=None,ge=0)
    calculation_evidence:str|None=None
    owner_user_id:int

def claim_out(c):
    return {'id':c.id,'number':c.number,'category':c.category,'status':c.status,
            'description':c.description,'event_at':c.event_at,'notice_required':c.notice_required,
            'notice_due_at':c.notice_due_at,'notice_sent_at':c.notice_sent_at,
            'submission_due_at':c.submission_due_at,'requested_amount':str(c.requested_amount) if c.requested_amount is not None else None,
            'currency':c.currency,'requested_eot_days':c.requested_eot_days,
            'agreed_amount':str(c.agreed_amount) if c.agreed_amount is not None else None,
            'agreed_eot_days':c.agreed_eot_days,'owner_user_id':c.owner_user_id,
            'counterparty_response':c.counterparty_response}

def claim_guard(db,user,pid,cid,claim_id,permission):
    contract=get_contract(db,user,pid,cid,permission)
    claim=db.query(ContractClaim).filter_by(id=claim_id,contract_id=contract.id,organization_id=contract.organization_id,project_id=pid).with_for_update().one_or_none()
    if claim is None:raise HTTPException(404,'Claim not found')
    return contract,claim

@router.post('/{cid}/claims',status_code=201)
def create_claim(pid:int,cid:int,body:ClaimCreateIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_variations')
    if body.category not in CLAIM_TYPES:raise HTTPException(422,'Unsupported claim category')
    if (body.requested_amount is None)!=(body.currency is None):raise HTTPException(422,'Amount and currency must both be supplied')
    if body.requested_amount is not None and c.currency!=body.currency:raise HTTPException(422,'Contract currency mismatch')
    owner=db.get(User,body.owner_user_id)
    if owner is None or not owner.active or owner.organization_id!=c.organization_id:raise HTTPException(422,'Invalid claim owner')
    project_guard(db,owner,pid,'contracts.manage_variations')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    row=ContractClaim(organization_id=c.organization_id,project_id=pid,contract_id=c.id,version_id=v.id,
                      created_by=user.id,**body.model_dump())
    db.add(row);db.flush();audit(db,c,user,'claim_drafted',{'claim_id':row.id,'number':row.number});result=claim_out(row);save(db)
    return result

@router.get('/{cid}/claims')
def list_claims(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.view_commercial')
    rows=db.query(ContractClaim).filter_by(contract_id=c.id,organization_id=c.organization_id,project_id=pid).order_by(ContractClaim.id.desc()).limit(250)
    return [claim_out(r) for r in rows]

class ClaimNoticeIn(BaseModel):
    sent_at:datetime
    evidence:str=Field(min_length=8,max_length=4000)

@router.post('/{cid}/claims/{claim_id}/notice')
def record_claim_notice(pid:int,cid:int,claim_id:int,body:ClaimNoticeIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,q=claim_guard(db,user,pid,cid,claim_id,'contracts.manage_variations')
    if q.status!='Draft':raise HTTPException(409,'Claim no longer in draft')
    if q.notice_sent_at is not None:raise HTTPException(409,'Notice already recorded')
    if not q.notice_required:raise HTTPException(409,'Notice not required')
    q.notice_sent_at=body.sent_at;q.notice_evidence=body.evidence;q.updated_at=datetime.now(timezone.utc)
    audit(db,c,user,'claim_notice_recorded',{'claim_id':q.id,'sent_at':body.sent_at.isoformat()});save(db)
    return claim_out(q)

class ClaimEvidenceIn(BaseModel):
    evidence:str=Field(min_length=8,max_length=4000)

@router.post('/{cid}/claims/{claim_id}/submit')
def submit_claim(pid:int,cid:int,claim_id:int,body:ClaimEvidenceIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,q=claim_guard(db,user,pid,cid,claim_id,'contracts.manage_variations')
    if q.status!='Draft':raise HTTPException(409,'Claim already submitted')
    if q.notice_required and (not q.notice_sent_at or not q.notice_evidence):raise HTTPException(409,'Required notice evidence missing')
    if q.requested_amount is None and q.requested_eot_days is None:raise HTTPException(422,'Amount or EOT requested required')
    q.submission_evidence=body.evidence;q.status='Submitted';q.updated_at=datetime.now(timezone.utc)
    audit(db,c,user,'claim_submitted',{'claim_id':q.id});save(db)
    return claim_out(q)

class ClaimDecisionIn(BaseModel):
    decision:str
    evidence:str=Field(min_length=8,max_length=4000)
    counterparty_response:str|None=None
    agreed_amount:Decimal|None=Field(default=None,ge=0,max_digits=20,decimal_places=2)
    agreed_eot_days:int|None=Field(default=None,ge=0)

@router.post('/{cid}/claims/{claim_id}/decision')
def decide_claim(pid:int,cid:int,claim_id:int,body:ClaimDecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,q=claim_guard(db,user,pid,cid,claim_id,'contracts.approve')
    if q.created_by==user.id or q.owner_user_id==user.id:raise HTTPException(403,'Self approval prohibited')
    if q.status not in {'Submitted','Under Review','Disputed'}:raise HTTPException(409,'Claim not eligible for decision')
    if body.decision not in {'Under Review','Agreed','Disputed','Rejected'}:raise HTTPException(422,'Invalid claim decision')
    if body.decision=='Agreed' and body.agreed_amount is None and body.agreed_eot_days is None:raise HTTPException(422,'Agreed impact required')
    q.status=body.decision;q.counterparty_response=body.counterparty_response
    q.decision_evidence=body.evidence
    if body.decision=='Agreed':q.agreed_amount=body.agreed_amount;q.agreed_eot_days=body.agreed_eot_days
    q.updated_at=datetime.now(timezone.utc)
    audit(db,c,user,'claim_decision',{'claim_id':q.id,'decision':q.status,'reason':body.evidence});save(db)
    return claim_out(q)

@router.post('/{cid}/claims/{claim_id}/withdraw')
def withdraw_claim(pid:int,cid:int,claim_id:int,body:ClaimEvidenceIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,q=claim_guard(db,user,pid,cid,claim_id,'contracts.manage_variations')
    if q.status not in {'Draft','Submitted','Under Review','Disputed'}:raise HTTPException(409,'Cannot withdraw decided claim')
    if q.owner_user_id!=user.id and q.created_by!=user.id and not user.organization_admin:raise HTTPException(403,'Only claim owner or creator may withdraw')
    q.status='Withdrawn';q.updated_at=datetime.now(timezone.utc)
    audit(db,c,user,'claim_withdrawn',{'claim_id':q.id,'reason':body.evidence});save(db)
    return claim_out(q)


# CM0115: controlled contractual correspondence
CORRESPONDENCE_CATEGORIES={'Letter','Notice','Instruction','Meeting Decision','Clarification Request','Response'}
class CorrespondenceCreateIn(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    category:str
    subject:str=Field(min_length=3,max_length=240)
    content:str=Field(min_length=3,max_length=20000)
    sender_company_id:int
    recipient_company_id:int
    linked_claim_id:int|None=None
    response_due_at:datetime|None=None

class CorrespondenceEvidenceIn(BaseModel):
    evidence:str=Field(min_length=8,max_length=4000)

class CorrespondenceIssueIn(BaseModel):
    delivery_method:str=Field(min_length=2,max_length=80)
    dispatch_reference:str=Field(min_length=2,max_length=240)
    dispatch_evidence:str=Field(min_length=8,max_length=4000)
    issued_at:datetime

class CorrespondenceReceiptIn(BaseModel):
    received_at:datetime
    evidence:str=Field(min_length=8,max_length=4000)

def correspondence_view(row):
    return {'id':row.id,'number':row.number,'category':row.category,'subject':row.subject,
            'sender_company_id':row.sender_company_id,'recipient_company_id':row.recipient_company_id,
            'linked_claim_id':row.linked_claim_id,'response_due_at':row.response_due_at,
            'status':row.status,'approved_at':row.approved_at,'issue_at':row.issue_at,
            'delivery_method':row.delivery_method,'dispatch_reference':row.dispatch_reference,
            'receipt_at':row.receipt_at}

def correspondence_guard(db,user,pid,cid,item_id,permission):
    c=get_contract(db,user,pid,cid,permission)
    item=db.query(ContractCorrespondence).filter_by(id=item_id,contract_id=c.id,project_id=pid,organization_id=c.organization_id).with_for_update().one_or_none()
    if item is None:raise HTTPException(404,'Correspondence not found')
    return c,item

@router.post('/{cid}/correspondence-ledger',status_code=201)
def create_correspondence(pid:int,cid:int,body:CorrespondenceCreateIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_draft')
    if body.category not in CORRESPONDENCE_CATEGORIES:raise HTTPException(422,'Unsupported correspondence category')
    if body.sender_company_id not in (c.contracting_company_id,c.counterparty_company_id) or body.recipient_company_id not in (c.contracting_company_id,c.counterparty_company_id) or body.sender_company_id==body.recipient_company_id:
        raise HTTPException(422,'Invalid contract parties')
    if body.linked_claim_id is not None:
        q=db.query(ContractClaim).filter_by(id=body.linked_claim_id,contract_id=c.id,organization_id=c.organization_id,project_id=pid).one_or_none()
        if not q:raise HTTPException(422,'Claim not found in contract')
    v=db.query(ContractVersion).filter_by(contract_id=c.id,version=c.current_version).one()
    row=ContractCorrespondence(organization_id=c.organization_id,project_id=pid,contract_id=c.id,version_id=v.id,created_by=user.id,**body.model_dump())
    db.add(row);db.flush();audit(db,c,user,'correspondence_drafted',{'correspondence_id':row.id});result=correspondence_view(row);save(db)
    return result

@router.get('/{cid}/correspondence-ledger')
def list_correspondence(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.view_summary')
    rows=db.query(ContractCorrespondence).filter_by(contract_id=c.id,organization_id=c.organization_id,project_id=pid).order_by(ContractCorrespondence.id.desc()).limit(250)
    return [correspondence_view(x) for x in rows]

@router.post('/{cid}/correspondence-ledger/{item_id}/approve')
def approve_correspondence(pid:int,cid:int,item_id:int,body:CorrespondenceEvidenceIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,row=correspondence_guard(db,user,pid,cid,item_id,'contracts.approve')
    if row.status!='Draft':raise HTTPException(409,'Correspondence not in draft')
    if row.created_by==user.id:raise HTTPException(403,'Cannot approve own correspondence')
    row.status='Approved for Issue';row.approved_by=user.id;row.approved_at=datetime.now(timezone.utc);row.approval_evidence=body.evidence
    audit(db,c,user,'correspondence_approved',{'correspondence_id':row.id});save(db)
    return correspondence_view(row)

@router.post('/{cid}/correspondence-ledger/{item_id}/issue')
def issue_correspondence(pid:int,cid:int,item_id:int,body:CorrespondenceIssueIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,row=correspondence_guard(db,user,pid,cid,item_id,'contracts.issue_notice')
    if row.status!='Approved for Issue':raise HTTPException(409,'Correspondence must be approved for issue')
    if row.created_by==user.id or row.approved_by==user.id:raise HTTPException(403,'Issue requires separate authorized actor')
    issued=aware(body.issued_at)
    if issued>datetime.now(timezone.utc)+timedelta(minutes=5):raise HTTPException(422,'Future dispatch date')
    row.status='Issued';row.issue_at=issued;row.delivery_method=body.delivery_method
    row.dispatch_reference=body.dispatch_reference;row.dispatch_evidence=body.dispatch_evidence
    audit(db,c,user,'correspondence_issued',{'correspondence_id':row.id,'dispatch_reference':body.dispatch_reference});save(db)
    return correspondence_view(row)

@router.post('/{cid}/correspondence-ledger/{item_id}/receipt')
def record_correspondence_receipt(pid:int,cid:int,item_id:int,body:CorrespondenceReceiptIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,row=correspondence_guard(db,user,pid,cid,item_id,'contracts.issue_notice')
    if row.status!='Issued' or row.receipt_at is not None:raise HTTPException(409,'Receipt requires issued correspondence')
    received=aware(body.received_at)
    if received<aware(row.issue_at):raise HTTPException(422,'Receipt predates issue')
    row.receipt_at=received;row.receipt_evidence=body.evidence
    audit(db,c,user,'correspondence_receipt_recorded',{'correspondence_id':row.id});save(db)
    return correspondence_view(row)


# CM0116 — securities and insurance. All operations remain internal and project-scoped.
SECURITY_TYPES={'Bank Guarantee','Performance Bond','Advance Guarantee','Retention Guarantee','Insurance','Other'}

class SecurityCreateIn(BaseModel):
    instrument_type:str
    issuer:str=Field(min_length=1,max_length=240)
    reference_number:str=Field(min_length=1,max_length=120)
    amount:Decimal=Field(ge=0,max_digits=20,decimal_places=2)
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    issue_at:datetime
    expires_at:datetime
    required_valid_until:datetime|None=None
    renewal_owner_id:int
    release_conditions:str=Field(min_length=1)
    evidence_ref:str=Field(min_length=1)

class SecurityRenewIn(BaseModel):
    expires_at:datetime
    evidence_ref:str=Field(min_length=1)

class SecurityReleaseIn(BaseModel):
    evidence_ref:str=Field(min_length=1)


def security_out(x):
    return {'id':x.id,'instrument_type':x.instrument_type,'issuer':x.issuer,
        'reference_number':x.reference_number,'amount':str(x.amount),'currency':x.currency,
        'issue_at':x.issue_at,'expires_at':x.expires_at,'required_valid_until':x.required_valid_until,
        'renewal_owner_id':x.renewal_owner_id,'release_conditions':x.release_conditions,
        'evidence_ref':x.evidence_ref,'status':x.status}


def security_guard(db,user,pid,cid,sid,permission='contracts.manage_terms'):
    c=get_contract(db,user,pid,cid,permission)
    item=db.query(ContractSecurityInstrument).filter_by(id=sid,contract_id=c.id,
        organization_id=c.organization_id,project_id=pid).with_for_update().one_or_none()
    if item is None:raise HTTPException(404,'Instrument not found')
    return c,item

@router.post('/{cid}/security-instruments',status_code=201)
def create_security(pid:int,cid:int,body:SecurityCreateIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_terms')
    if body.instrument_type not in SECURITY_TYPES:raise HTTPException(422,'Invalid instrument type')
    start,end=aware(body.issue_at),aware(body.expires_at)
    required=aware(body.required_valid_until) if body.required_valid_until else None
    if start>=end:raise HTTPException(422,'Expiry must follow issue date')
    owner=db.get(User,body.renewal_owner_id)
    if owner is None or not owner.active or owner.organization_id!=c.organization_id:
        raise HTTPException(422,'Invalid renewal owner')
    project_guard(db,owner,pid,'contracts.view_summary')
    row=ContractSecurityInstrument(organization_id=c.organization_id,project_id=pid,
       contract_id=cid,created_by=user.id,**{**body.model_dump(), 'issue_at':start,
       'expires_at':end,'required_valid_until':required})
    db.add(row);db.flush();audit(db,c,user,'security_created',{'instrument_id':row.id});result=security_out(row);save(db)
    return result

@router.get('/{cid}/security-instruments')
def list_securities(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.view_commercial')
    return [security_out(x) for x in db.query(ContractSecurityInstrument).filter_by(
        contract_id=c.id,project_id=pid,organization_id=c.organization_id).order_by(ContractSecurityInstrument.id.desc()).limit(250)]

@router.post('/{cid}/security-instruments/{sid}/renew')
def renew_security(pid:int,cid:int,sid:int,body:SecurityRenewIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,row=security_guard(db,user,pid,cid,sid)
    if row.status!='Active':raise HTTPException(409,'Instrument not active')
    expiry=aware(body.expires_at)
    if expiry<=aware(row.expires_at):raise HTTPException(422,'Renewal must extend expiry')
    old=row.expires_at;row.expires_at=expiry
    db.add(ContractSecurityEvent(instrument_id=sid,event_type='Renewed',old_expiry=old,new_expiry=expiry,
        evidence_ref=body.evidence_ref,actor_id=user.id))
    audit(db,c,user,'security_renewed',{'instrument_id':sid});result=security_out(row);save(db)
    return result

@router.post('/{cid}/security-instruments/{sid}/release')
def release_security(pid:int,cid:int,sid:int,body:SecurityReleaseIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c,row=security_guard(db,user,pid,cid,sid,'contracts.approve')
    if row.status!='Active':raise HTTPException(409,'Instrument not active')
    if row.created_by==user.id:raise HTTPException(403,'Release requires separate approver')
    row.status='Released'
    db.add(ContractSecurityEvent(instrument_id=sid,event_type='Released',old_expiry=row.expires_at,
        new_expiry=None,evidence_ref=body.evidence_ref,actor_id=user.id))
    audit(db,c,user,'security_released',{'instrument_id':sid});result=security_out(row);save(db)
    return result

@router.get('/{cid}/security-instruments/{sid}/history')
def security_history(pid:int,cid:int,sid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    _,row=security_guard(db,user,pid,cid,sid,'contracts.view_commercial')
    return [{'type':x.event_type,'old_expiry':x.old_expiry,'new_expiry':x.new_expiry,
        'evidence_ref':x.evidence_ref,'actor_id':x.actor_id,'recorded_at':x.recorded_at}
        for x in db.query(ContractSecurityEvent).filter_by(instrument_id=row.id).order_by(ContractSecurityEvent.id)]

@router.get('/security-expiry-queue')
def security_expiry_queue(pid:int,days:int=30,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    project_guard(db,user,pid,'contracts.view_commercial')
    if not 1<=days<=365:raise HTTPException(422,'days out of range')
    now_at=datetime.now(timezone.utc);cutoff=now_at+timedelta(days=days)
    rows=db.query(ContractSecurityInstrument).filter_by(organization_id=user.organization_id,project_id=pid,status='Active').all()
    return [{'instrument_id':r.id,'contract_id':r.contract_id,'expiry_at':r.expires_at,
       'renewal_owner_id':r.renewal_owner_id,'severity':'Expired' if aware(r.expires_at)<now_at else 'Upcoming'}
       for r in rows if aware(r.expires_at)<=cutoff]


# CM0117 closeout gate. Source-system confirmation is recorded as evidence;
# actual Financials/QA/Commissioning integration is a separate acceptance gate.
CLOSEOUT_TYPES={
 'scope_completion','qa_acceptance','commissioning_handover','final_measurement',
 'finance_settlement','claims_resolution','document_handover','security_retention',
 'warranty_assignment'
}
CLOSEOUT_SOURCES={'qa_acceptance':'QA','commissioning_handover':'Commissioning',
 'finance_settlement':'Financials','final_measurement':'Construction'}

class CloseoutCheckIn(BaseModel):
    check_type:str
    source_record_ref:str=Field(min_length=1,max_length=500)
    evidence_ref:str=Field(min_length=1,max_length=1000)

class CloseoutDecisionIn(BaseModel):
    reason:str=Field(min_length=5,max_length=1000)

class WarrantyIn(BaseModel):
    description:str=Field(min_length=5,max_length=2000)
    owner_id:int
    due_at:datetime|None=None

class WarrantyCloseIn(BaseModel):
    evidence_ref:str=Field(min_length=1,max_length=1000)

def closeout_blockers(db,c):
    checks=db.query(ContractCloseoutCheck).filter_by(contract_id=c.id,organization_id=c.organization_id).all()
    statuses={x.check_type:x.status for x in checks}
    # External checks are fail-closed until a trusted source adapter with provenance exists.
    # Never accept a legacy/manual status='Verified' as external proof.
    blocks=['check:'+x for x in sorted(CLOSEOUT_TYPES)
            if x in CLOSEOUT_SOURCES or statuses.get(x)!='Verified']
    obligations=db.query(ContractObligation).filter_by(contract_id=c.id,organization_id=c.organization_id).all()
    blocks += ['obligation:'+str(x.id) for x in obligations if x.status not in ('Accepted','Waived','Cancelled')]
    securities=db.query(ContractSecurityInstrument).filter_by(contract_id=c.id,organization_id=c.organization_id).all()
    blocks += ['security:'+str(x.id) for x in securities if x.status=='Active']
    return blocks

@router.get('/{cid}/closeout-readiness')
def get_closeout_readiness(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid)
    blocks=closeout_blockers(db,c)
    return {'contract_id':cid,'lifecycle':c.lifecycle,'ready':not blocks,'blockers':blocks}

@router.get('/{cid}/closeout-source-verification')
def closeout_source_verification(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Fail-closed status for authoritative checks, without trusting manually entered references.

    This is a diagnostic read endpoint, NOT a source verification operation.
    When reliable Financials/QA/Construction/Commissioning adapters are available,
    they must verify records server-side before advancing any check to Verified.
    """
    c=get_contract(db,user,pid,cid)
    rows={r.check_type:r for r in db.query(ContractCloseoutCheck).filter_by(
        contract_id=c.id,organization_id=c.organization_id).all()}
    response=[]
    for name,source in sorted(CLOSEOUT_SOURCES.items()):
        row=rows.get(name)
        verified=False  # No registered trusted source adapter: never trust legacy/manual 'Verified' flags
        response.append({'check_type':name,'source_system':source,
            'recorded_evidence':bool(row and row.evidence_ref),
            'source_record_ref':row.source_record_ref if row else None,
            'source_verified':verified,
            'status':('Verified' if verified else 'Verification Required'),
            'blocking':not verified})
    return {'contract_id':cid,'source_verification_complete':all(not x['blocking'] for x in response),
            'checks':response,'policy':'fail_closed'}

@router.get('/{cid}/closeout-quality-blockers')
def closeout_quality_blockers(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    """Read live, tenant-scoped QA blockers; never certify QA closeout."""
    c=get_contract(db,user,pid,cid)
    from app.domains.contracts.closeout_source_checks import quality_blockers
    return {'contract_id':cid, **quality_blockers(db,c.organization_id,pid)}

@router.get('/{cid}/closeout-checks')
def list_closeout_checks(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid)
    return [{'check_type':x.check_type,'status':x.status,'source_system':x.source_system,
      'source_record_ref':x.source_record_ref,'evidence_ref':x.evidence_ref,'verified_at':x.verified_at}
      for x in db.query(ContractCloseoutCheck).filter_by(contract_id=c.id,organization_id=c.organization_id).all()]

@router.post('/{cid}/closeout-checks')
def verify_closeout_check(pid:int,cid:int,body:CloseoutCheckIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.close')
    if c.lifecycle in ('Closed','Terminated','Cancelled'):raise HTTPException(409,'Contract not eligible')
    if body.check_type not in CLOSEOUT_TYPES:raise HTTPException(422,'Unsupported closeout check')
    row=db.query(ContractCloseoutCheck).filter_by(contract_id=cid,check_type=body.check_type).one_or_none()
    if row and row.status=='Verified':raise HTTPException(409,'Check already verified')
    if row is None:
        row=ContractCloseoutCheck(organization_id=c.organization_id,project_id=pid,contract_id=cid,check_type=body.check_type)
        db.add(row)
    # External source references are evidence submissions, not authoritative verification.
    # Keep the closeout gate closed until a trusted source-system adapter verifies them.
    row.status='Evidence Recorded' if body.check_type in CLOSEOUT_SOURCES else 'Verified'
    row.source_system=CLOSEOUT_SOURCES.get(body.check_type,'Contracts')
    row.source_record_ref=body.source_record_ref;row.evidence_ref=body.evidence_ref
    row.verified_by=None if body.check_type in CLOSEOUT_SOURCES else user.id
    row.verified_at=None if body.check_type in CLOSEOUT_SOURCES else datetime.now(timezone.utc)
    audit(db,c,user,'closeout_evidence_recorded',{'check_type':body.check_type,'source_ref':body.source_record_ref})
    save(db)
    return {'check_type':body.check_type,'status':row.status,'source_verified_live':False,
            'verification_required':body.check_type in CLOSEOUT_SOURCES}

@router.post('/{cid}/closeout')
def close_contract(pid:int,cid:int,body:CloseoutDecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.close')
    if c.lifecycle!='Completed':raise HTTPException(409,'Contract must be Completed before closure')
    blockers=closeout_blockers(db,c)
    if blockers:raise HTTPException(409,'Unresolved closeout blockers: '+', '.join(blockers[:15]))
    c.lifecycle='Closed';c.updated_at=datetime.now(timezone.utc)
    audit(db,c,user,'contract_closed',{'reason':body.reason});save(db)
    return {'contract_id':cid,'lifecycle':'Closed'}

@router.post('/{cid}/warranties',status_code=201)
def add_warranty(pid:int,cid:int,body:WarrantyIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_obligations')
    owner=db.get(User,body.owner_id)
    if not owner or not owner.active or owner.organization_id!=c.organization_id:raise HTTPException(422,'Invalid owner')
    project_guard(db,owner,pid)
    due=aware(body.due_at) if body.due_at else None
    row=ContractWarranty(organization_id=c.organization_id,project_id=pid,contract_id=cid,
       description=body.description,owner_id=body.owner_id,due_at=due,created_by=user.id)
    db.add(row);db.flush();rid=row.id
    audit(db,c,user,'warranty_created',{'warranty_id':rid});save(db)
    return {'id':rid,'status':'Open'}

@router.get('/{cid}/warranties')
def list_warranties(pid:int,cid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid)
    return [{'id':x.id,'description':x.description,'owner_id':x.owner_id,'due_at':x.due_at,
      'status':x.status,'evidence_ref':x.evidence_ref} for x in db.query(ContractWarranty)
      .filter_by(contract_id=cid,organization_id=c.organization_id).order_by(ContractWarranty.id).all()]

@router.post('/{cid}/warranties/{wid}/complete')
def complete_warranty(pid:int,cid:int,wid:int,body:WarrantyCloseIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    c=get_contract(db,user,pid,cid,'contracts.manage_obligations')
    row=db.query(ContractWarranty).filter_by(id=wid,contract_id=cid,organization_id=c.organization_id).one_or_none()
    if row is None:raise HTTPException(404,'Warranty not found')
    if row.status!='Open':raise HTTPException(409,'Warranty already completed')
    if row.owner_id!=user.id and not user.organization_admin:raise HTTPException(403,'Not warranty owner')
    row.status='Completed';row.evidence_ref=body.evidence_ref
    audit(db,c,user,'warranty_completed',{'warranty_id':wid});save(db)
    return {'id':wid,'status':'Completed'}
