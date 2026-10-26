"""Financial cost codes and versioned budget workflow (Phase 31.1)."""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.domains.identity_projects.models import User, Project, Role, Membership, Discipline
from app.domains.identity_projects.security import authenticated
from .models import FinanceCostCode, FinanceBudget, FinanceBillLine, FinanceBillDecision

router=APIRouter(prefix='/api/projects/{pid}/financials',tags=['Financials'])
CATEGORIES={'Materials','Equipment Purchase','Equipment Hire','Subcontract Work','Direct Labour','Engineering','Site Overheads','Logistics','Testing and Inspection','Other'}

def guard(db:Session,user:User,pid:int,permission:str,discipline_id:int|None=None):
    project=db.get(Project,pid)
    if not project or project.organization_id != user.organization_id: raise HTTPException(404,'Project not found')
    if not user.active: raise HTTPException(403,'User inactive')
    if user.organization_admin: return
    for m in db.query(Membership).filter_by(project_id=pid,user_id=user.id,active=True).all():
        role=db.get(Role,m.role_id)
        perms=set(role.permissions or []) if role else set()
        if 'planning.partner.view' in perms or permission not in perms: continue
        if m.scope=='ALL': return
        if discipline_id is not None and m.company_id is not None and discipline_id in (m.discipline_ids or []):
            # Financial rows don't yet have a source company assignment. Fail closed.
            continue
    raise HTTPException(403,f'{permission} permission with full project scope required')

def commit(db,row):
    db.add(row)
    try: db.commit();db.refresh(row)
    except IntegrityError: db.rollback();raise HTTPException(409,'Duplicate financial code or invalid reference')
    return row

def code_out(c):return {'id':c.id,'code':c.code,'description':c.description,'category':c.category,'discipline_id':c.discipline_id}
def budget_out(b):return {'id':b.id,'code':b.code,'revision':b.revision,'cost_code_id':b.cost_code_id,'description':b.description,'currency':b.currency,'proposed_amount':str(b.proposed_amount),'forecast_remaining':str(b.forecast_remaining) if b.forecast_remaining is not None else None,'status':b.status,'submitted_by':b.submitted_by,'approved_by':b.approved_by,'approved_at':b.approved_at.isoformat() if b.approved_at else None,'decision_reason':b.decision_reason}

class CostCodeIn(BaseModel):
    code:str=Field(min_length=1,max_length=80)
    description:str=Field(min_length=1,max_length=240)
    category:str
    discipline_id:int|None=None

@router.get('/cost-codes')
def cost_codes(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [code_out(x) for x in db.query(FinanceCostCode).filter_by(project_id=pid,organization_id=user.organization_id).order_by(FinanceCostCode.code).all()]

@router.post('/cost-codes',status_code=201)
def create_cost_code(pid:int,body:CostCodeIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    if body.category not in CATEGORIES: raise HTTPException(422,'Unknown cost category')
    if body.discipline_id is not None and not db.get(Discipline,body.discipline_id):raise HTTPException(422,'Invalid discipline')
    row=commit(db,FinanceCostCode(organization_id=user.organization_id,project_id=pid,**body.model_dump()))
    return code_out(row)

class BudgetIn(BaseModel):
    code:str=Field(min_length=1,max_length=80)
    cost_code_id:int
    description:str=Field(min_length=1,max_length=240)
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    proposed_amount:Decimal=Field(ge=0,max_digits=20,decimal_places=2)
    forecast_remaining:Decimal|None=Field(default=None,ge=0,max_digits=20,decimal_places=2)

@router.get('/budgets')
def list_budgets(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [budget_out(b) for b in db.query(FinanceBudget).filter_by(project_id=pid,organization_id=user.organization_id).order_by(FinanceBudget.code,FinanceBudget.revision).all()]

@router.post('/budgets',status_code=201)
def create_budget(pid:int,body:BudgetIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    c=db.query(FinanceCostCode).filter_by(id=body.cost_code_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not c:raise HTTPException(422,'Cost code outside project')
    previous=db.query(FinanceBudget).filter_by(project_id=pid,code=body.code).order_by(FinanceBudget.revision.desc()).first()
    if previous and previous.status not in {'Approved','Rejected','Returned'}:raise HTTPException(409,'Resolve existing revision before proposing another')
    b=commit(db,FinanceBudget(organization_id=user.organization_id,project_id=pid,revision=previous.revision+1 if previous else 1,created_by=user.id,**body.model_dump()))
    return budget_out(b)

@router.post('/budgets/{budget_id}/submit')
def submit_budget(pid:int,budget_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    b=db.query(FinanceBudget).filter_by(id=budget_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not b:raise HTTPException(404,'Budget not found')
    if b.status!='Draft':raise HTTPException(409,'Only draft budgets can be submitted')
    b.status='Pending Review';b.submitted_by=user.id;commit(db,b)
    return budget_out(b)

class Decision(BaseModel):
    reason:str=Field(min_length=3,max_length=1000)

@router.post('/budgets/{budget_id}/approve')
def approve_budget(pid:int,budget_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    b=db.query(FinanceBudget).filter_by(id=budget_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not b:raise HTTPException(404,'Budget not found')
    if b.status!='Pending Review':raise HTTPException(409,'Budget not pending review')
    if user.id in {b.created_by,b.submitted_by}:raise HTTPException(403,'Self-approval prohibited')
    b.status='Approved';b.approved_by=user.id;b.approved_at=datetime.now(timezone.utc);b.decision_reason=body.reason;commit(db,b)
    return budget_out(b)

@router.get('/summary')
def summary(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    rows=db.query(FinanceBudget).filter_by(project_id=pid,organization_id=user.organization_id,status='Approved').order_by(FinanceBudget.revision.desc()).all()
    latest={}
    for b in rows: latest.setdefault(b.code,b)
    currencies=sorted({b.currency for b in latest.values()})
    totals={cc:str(sum((b.proposed_amount for b in latest.values() if b.currency==cc),Decimal('0.00'))) for cc in currencies}
    return {'project_id':pid,'data_source':'ZerroBuild approved financial budgets','read_only':True,'policy':'Posted invoices, certified subcontract bills, and approved expenses recognize cost; not integrated in Phase 31.1','approved_budget_by_currency':totals,'recognized_actual_cost':None,'open_commitments':None,'estimate_at_completion':None,'forecast_variance':None,'client_certified_value':None,'payments':None,'receivables':None,'status':'Budget foundation only — actuals unavailable','budget_revisions':[budget_out(b) for b in latest.values()]}


# Internal service-to-service read-only financial summary. UI caller cannot supply
# arbitrary organization: it is checked against the project master.
from fastapi import Request
from app.config import settings
import hmac
@router.get('/internal-summary')
def internal_summary(pid:int,request:Request,db:Session=Depends(get_db)):
    key=request.headers.get('X-ZerroR-Service-Key','')
    expected=settings.command_center_identity_service_key
    if not expected or not hmac.compare_digest(key,expected):raise HTTPException(403,'Internal service key required')
    project=db.get(Project,pid)
    if not project:raise HTTPException(404,'Project not found')
    rows=db.query(FinanceBudget).filter_by(project_id=pid,organization_id=project.organization_id,status='Approved').order_by(FinanceBudget.revision.desc()).all()
    latest={}
    for b in rows:latest.setdefault(b.code,b)
    currencies=sorted({b.currency for b in latest.values()})
    return {'project_code':project.code,'project_id':pid,'read_only':True,'approved_budget_by_currency':{cc:str(sum((b.proposed_amount for b in latest.values() if b.currency==cc),Decimal('0.00'))) for cc in currencies},'recognized_actual_cost':None,'open_commitments':None,'estimate_at_completion':None,'forecast_variance':None,'payments':None,'receivables':None,'source':'ZerroBuild approved financial budgets','status':'Actual cost and settlement integrations pending'}


# Phase 31.2: Procurement is the source of truth; Finance owns only mappings/postings.
from . import procurement_integration as procurement_finance

@router.get('/procurement-monitoring')
def procurement_monitoring(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return procurement_finance.overview(db,pid,user.organization_id)

@router.post('/procurement/orders/{po_id}/cost-code',status_code=201)
def allocate_purchase_order(pid:int,po_id:int,body:procurement_finance.AllocationIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    return procurement_finance.assign(db,pid,user.organization_id,user.id,po_id,body.cost_code_id)

@router.get('/procurement/invoices/{invoice_id}/receipt-match')
def supplier_invoice_receipt_match(pid:int,invoice_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    from app.domains.supply_chain.models import VendorInvoice, PurchaseOrder
    invoice=db.query(VendorInvoice).filter_by(id=invoice_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not invoice:raise HTTPException(404,'Supplier invoice not found')
    po=db.query(PurchaseOrder).filter_by(id=invoice.purchase_order_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not po:raise HTTPException(409,'Invoice purchase order not found in project')
    result=procurement_finance.receipt_match(db,po,invoice)
    return {'invoice_id':invoice_id,'purchase_order_id':po.id,'status':'Matched','basis':'PO rate and cumulative line quantities compared with posted goods receipts and previously Finance-posted invoices',**result}

@router.post('/procurement/invoices/{invoice_id}/post',status_code=201)
def post_supplier_invoice(pid:int,invoice_id:int,body:procurement_finance.PostingIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    return procurement_finance.post(db,pid,user.organization_id,user.id,invoice_id,body.verification_note)

@router.get('/internal-procurement-monitoring')
def internal_procurement_monitoring(pid:int,request:Request,db:Session=Depends(get_db)):
    key=request.headers.get('X-ZerroR-Service-Key','')
    expected=settings.command_center_identity_service_key
    if not expected or not hmac.compare_digest(key,expected):raise HTTPException(403,'Internal service key required')
    project=db.get(Project,pid)
    if not project:raise HTTPException(404,'Project not found')
    return procurement_finance.overview(db,pid,project.organization_id)


# Phase 31.3: contract-specific BOQ and source-evidenced certification.
from .models import FinanceContract, FinanceBoqLine, FinanceMeasurement, FinanceSubcontractBill
from app.domains.construction.models import ConstructionActivity
from app.domains.construction.progress import activity_measures
from app.domains.identity_projects.models import Company
from sqlalchemy import func

class ContractInput(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    contract_type:str
    counterparty_company_id:int
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    original_value:Decimal=Field(ge=0,max_digits=20,decimal_places=2)

def contract_dict(x):
    return {'id':x.id,'number':x.number,'contract_type':x.contract_type,'counterparty_company_id':x.counterparty_company_id,'currency':x.currency,'original_value':str(x.original_value),'status':x.status}

@router.get('/contracts')
def contracts_list(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [contract_dict(x) for x in db.query(FinanceContract).filter_by(project_id=pid,organization_id=user.organization_id).order_by(FinanceContract.id).all()]

@router.post('/contracts',status_code=201)
def contracts_create(pid:int,body:ContractInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    if body.contract_type not in {'Client Revenue','Subcontractor Work','Services','Other'}:raise HTTPException(422,'Unsupported contract type')
    company=db.get(Company,body.counterparty_company_id)
    if not company or company.organization_id!=user.organization_id:raise HTTPException(422,'Counterparty not in organization')
    return contract_dict(commit(db,FinanceContract(project_id=pid,organization_id=user.organization_id,created_by=user.id,**body.model_dump())))

@router.post('/contracts/{contract_id}/approve')
def contracts_approve(pid:int,contract_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    c=db.query(FinanceContract).filter_by(id=contract_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not c:raise HTTPException(404,'Contract not found')
    if c.status!='Draft':raise HTTPException(409,'Only draft contracts may be approved')
    if c.created_by==user.id:raise HTTPException(403,'Self-approval prohibited')
    c.status='Approved'
    return contract_dict(commit(db,c))

class BoqInput(BaseModel):
    code:str=Field(min_length=1,max_length=80)
    description:str=Field(min_length=1,max_length=240)
    activity_id:int
    quantity:Decimal=Field(gt=0,max_digits=18,decimal_places=3)
    unit_rate:Decimal=Field(ge=0,max_digits=20,decimal_places=2)

def boq_dict(x):return {'id':x.id,'contract_id':x.contract_id,'code':x.code,'description':x.description,'activity_id':x.activity_id,'quantity':str(x.quantity),'unit':x.unit,'unit_rate':str(x.unit_rate)}

@router.get('/contracts/{contract_id}/boq')
def boq_list(pid:int,contract_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    contract=db.query(FinanceContract).filter_by(id=contract_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not contract:raise HTTPException(404,'Contract not found')
    return [boq_dict(x) for x in db.query(FinanceBoqLine).filter_by(project_id=pid,contract_id=contract_id).order_by(FinanceBoqLine.id).all()]

@router.post('/contracts/{contract_id}/boq',status_code=201)
def boq_create(pid:int,contract_id:int,body:BoqInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    contract=db.query(FinanceContract).filter_by(id=contract_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not contract:raise HTTPException(404,'Contract not found')
    if contract.status!='Draft':raise HTTPException(409,'BOQ edits require a draft contract or approved variation')
    activity=db.query(ConstructionActivity).filter_by(id=body.activity_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not activity or activity.measurement_method!='Quantity':raise HTTPException(422,'BOQ requires a quantity-based construction activity in this project')
    if activity.company_id != contract.counterparty_company_id and contract.contract_type=='Subcontractor Work':raise HTTPException(422,'Contract company does not own construction activity')
    return boq_dict(commit(db,FinanceBoqLine(project_id=pid,contract_id=contract_id,unit=activity.unit,created_by=user.id,**body.model_dump())))

class MeasurementInput(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    boq_line_id:int
    claimed_quantity:Decimal=Field(gt=0,max_digits=18,decimal_places=3)
    evidence_note:str=Field(min_length=8,max_length=2000)

def measurement_dict(x):
    return {'id':x.id,'number':x.number,'contract_id':x.contract_id,'boq_line_id':x.boq_line_id,'claimed_quantity':str(x.claimed_quantity),'certified_quantity':str(x.certified_quantity),'unit_rate_snapshot':str(x.unit_rate_snapshot),'status':x.status,'evidence_note':x.evidence_note,'certified_by':x.certified_by,'certified_at':x.certified_at.isoformat() if x.certified_at else None}

@router.get('/measurements')
def measurement_list(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [measurement_dict(x) for x in db.query(FinanceMeasurement).filter_by(project_id=pid).order_by(FinanceMeasurement.id).all()]

@router.post('/measurements',status_code=201)
def measurement_create(pid:int,body:MeasurementInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    line=db.query(FinanceBoqLine).filter_by(id=body.boq_line_id,project_id=pid).one_or_none()
    if not line:raise HTTPException(422,'BOQ line outside project')
    contract=db.query(FinanceContract).filter_by(id=line.contract_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not contract or contract.status!='Approved':raise HTTPException(409,'Approved contract required')
    return measurement_dict(commit(db,FinanceMeasurement(project_id=pid,contract_id=contract.id,boq_line_id=line.id,number=body.number,claimed_quantity=body.claimed_quantity,unit_rate_snapshot=line.unit_rate,evidence_note=body.evidence_note,created_by=user.id,status='Draft',certified_quantity=0)))

def allowed_certification_amount(db,line):
    """Use Construction's accepted quantity, never its verified-only quantity."""
    activity=db.query(ConstructionActivity).filter_by(id=line.activity_id,project_id=line.project_id).one_or_none()
    if not activity or activity.measurement_method!='Quantity' or activity.unit!=line.unit:
        raise HTTPException(422,'Source activity missing or unit/method mismatch')
    measures=activity_measures(db,activity)
    accepted=measures.get('accepted_quantity')
    if accepted is None:raise HTTPException(409,'QA-accepted quantity evidence not available')
    verified=measures.get('verified_quantity')
    if verified is None:raise HTTPException(409,'Approved construction quantity unavailable')
    return max(Decimal('0'),min(Decimal(str(accepted)),Decimal(str(verified)),Decimal(str(line.quantity))))

@router.post('/measurements/{measurement_id}/certify')
def measurement_certify(pid:int,measurement_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    # Serialize competing certifications for the same BOQ using a row lock.
    m=db.query(FinanceMeasurement).filter_by(id=measurement_id,project_id=pid).with_for_update().one_or_none()
    if not m:raise HTTPException(404,'Measurement not found')
    if m.status!='Draft':raise HTTPException(409,'Measurement is already processed')
    if m.created_by==user.id:raise HTTPException(403,'Self-approval prohibited')
    line=db.query(FinanceBoqLine).filter_by(id=m.boq_line_id,project_id=pid).with_for_update().one_or_none()
    contract=db.query(FinanceContract).filter_by(id=m.contract_id,project_id=pid,organization_id=user.organization_id).one_or_none()
    if not line or not contract or contract.status!='Approved':raise HTTPException(409,'Approved contractual entitlement required')
    maximum=allowed_certification_amount(db,line)
    previously=db.query(func.coalesce(func.sum(FinanceMeasurement.certified_quantity),0)).filter(FinanceMeasurement.boq_line_id==line.id,FinanceMeasurement.status=='Certified').scalar()
    remaining=maximum-Decimal(str(previously))
    if m.claimed_quantity>remaining:raise HTTPException(409,f'Claim exceeds remaining QA-accepted and contracted quantity ({remaining})')
    m.status='Certified';m.certified_quantity=m.claimed_quantity;m.certified_by=user.id;m.certified_at=datetime.now(timezone.utc)
    m.evidence_note=m.evidence_note+' | Certification: '+body.reason
    return measurement_dict(commit(db,m))

class BillInput(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    measurement_id:int

@router.get('/subcontract-bills')
def subcontract_bills(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [{'id':b.id,'number':b.number,'measurement_id':b.measurement_id,'contract_id':b.contract_id,'gross_value':str(b.gross_value),'net_payable':str(b.net_payable),'status':b.status} for b in db.query(FinanceSubcontractBill).filter_by(project_id=pid).all()]

@router.post('/subcontract-bills',status_code=201)
def subcontract_bill_create(pid:int,body:BillInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    m=db.query(FinanceMeasurement).filter_by(id=body.measurement_id,project_id=pid,status='Certified').one_or_none()
    if not m:raise HTTPException(409,'Certified measurement required')
    c=db.query(FinanceContract).filter_by(id=m.contract_id,project_id=pid,organization_id=user.organization_id,contract_type='Subcontractor Work',status='Approved').one_or_none()
    if not c:raise HTTPException(422,'Approved subcontract contract required')
    existing=db.query(FinanceSubcontractBill).filter_by(measurement_id=m.id).first()
    if existing:raise HTTPException(409,'Certified measurement already linked to a bill')
    total=(m.certified_quantity*m.unit_rate_snapshot).quantize(Decimal('0.01'))
    b=commit(db,FinanceSubcontractBill(project_id=pid,contract_id=c.id,measurement_id=m.id,number=body.number,gross_value=total,net_payable=total,status='Draft',created_by=user.id))
    commit(db,FinanceBillLine(bill_id=b.id,measurement_id=m.id,value_snapshot=total))
    return {'id':b.id,'number':b.number,'gross_value':str(b.gross_value),'status':b.status,'note':'Draft only: not an approved bill, cost posting or payment'}


# Phase 31.3 extension. Construction/QA remain owners of evidence; only posted bills recognize cost.
from .models import FinanceContract, FinanceSubcontractBill, FinanceMeasurement

class BillDeductions(BaseModel):
    retention_amount:Decimal=Field(default=Decimal('0.00'),ge=0,max_digits=20,decimal_places=2)
    advance_recovery_amount:Decimal=Field(default=Decimal('0.00'),ge=0,max_digits=20,decimal_places=2)
    other_deduction_amount:Decimal=Field(default=Decimal('0.00'),ge=0,max_digits=20,decimal_places=2)
    reason:str=Field(min_length=8,max_length=1000)

def calculate_bill_payable(gross:Decimal,retention:Decimal,advance:Decimal,other:Decimal)->Decimal:
    if any(v<0 for v in (gross,retention,advance,other)) or retention+advance+other>gross:
        raise HTTPException(422,'Invalid deductions: total deductions exceed gross or amounts are negative')
    return (gross-retention-advance-other).quantize(Decimal('0.01'))

def validate_ra_balance_posting(advance_recovery:Decimal,retention:Decimal,advance_available:Decimal)->None:
    """Check gross-deduction eligibility independently of ledger I/O."""
    if advance_recovery<0 or retention<0 or advance_available<0:
        raise HTTPException(422,'Invalid balance amounts')
    if advance_recovery>advance_available:
        raise HTTPException(409,'Advance recovery exceeds remaining subcontractor advance')

def bill_details(db,b):
    lines=db.query(FinanceBillLine).filter_by(bill_id=b.id).order_by(FinanceBillLine.id).all()
    return {'id':b.id,'number':b.number,'contract_id':b.contract_id,'status':b.status,
       'gross_value':str(b.gross_value),'net_payable':str(b.net_payable),
       'retention_amount':str(b.retention_amount),'advance_recovery_amount':str(b.advance_recovery_amount),'other_deduction_amount':str(b.other_deduction_amount),
       'lines':[{'measurement_id':x.measurement_id,'amount':str(x.value_snapshot)} for x in lines],
       'posted_at':b.posted_at.isoformat() if b.posted_at else None}

def bill_record_decision(db,b,user,action,reason):
    db.add(FinanceBillDecision(bill_id=b.id,actor_id=user.id,action=action,reason=reason))
    db.add(b)
    db.commit();db.refresh(b)
    return bill_details(db,b)

def locked_bill(db,pid,bill_id,org_id):
    b=db.query(FinanceSubcontractBill).filter_by(id=bill_id,project_id=pid).with_for_update().one_or_none()
    if not b:raise HTTPException(404,'Bill not found')
    if not db.query(FinanceContract).filter_by(id=b.contract_id,project_id=pid,organization_id=org_id).one_or_none():raise HTTPException(404,'Contract not found')
    return b

class BillLineInput(BaseModel):
    measurement_id:int

@router.post('/subcontract-bills/{bill_id}/lines')
def bill_add_line(pid:int,bill_id:int,body:BillLineInput,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    b=locked_bill(db,pid,bill_id,user.organization_id)
    if b.status!='Draft':raise HTTPException(409,'Only draft bills can be edited')
    m=db.query(FinanceMeasurement).filter_by(id=body.measurement_id,project_id=pid,contract_id=b.contract_id,status='Certified').one_or_none()
    if not m:raise HTTPException(409,'Certified measurement in same contract required')
    if db.query(FinanceBillLine).filter_by(measurement_id=m.id).first():raise HTTPException(409,'Measurement already billed')
    val=(m.certified_quantity*m.unit_rate_snapshot).quantize(Decimal('0.01'))
    db.add(FinanceBillLine(bill_id=b.id,measurement_id=m.id,value_snapshot=val))
    b.gross_value+=val;b.net_payable=calculate_bill_payable(b.gross_value,b.retention_amount,b.advance_recovery_amount,b.other_deduction_amount)
    db.commit();db.refresh(b)
    return bill_details(db,b)

@router.post('/subcontract-bills/{bill_id}/deductions')
def bill_deductions(pid:int,bill_id:int,body:BillDeductions,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    b=locked_bill(db,pid,bill_id,user.organization_id)
    if b.status!='Draft':raise HTTPException(409,'Deductions frozen after submission')
    # Explicit amounts only; tax rules/advance ledger reconciliation to follow.
    net=calculate_bill_payable(b.gross_value,body.retention_amount,body.advance_recovery_amount,body.other_deduction_amount)
    b.retention_amount=body.retention_amount;b.advance_recovery_amount=body.advance_recovery_amount;b.other_deduction_amount=body.other_deduction_amount;b.net_payable=net
    return bill_record_decision(db,b,user,'Deductions Set',body.reason)

BILL_TRANSITIONS={
    'submit':('Draft','Pending Technical Review','financials.manage'),
    'technical-approve':('Pending Technical Review','Pending Commercial Review','financials.approve'),
    'commercial-approve':('Pending Commercial Review','Pending Approval','financials.approve'),
    'post':('Pending Approval','Posted','financials.approve'),
}

def next_bill_status(status:str,action:str)->str:
    spec=BILL_TRANSITIONS.get(action)
    if not spec or status!=spec[0]:raise HTTPException(409,'Invalid RA bill review transition')
    return spec[1]

@router.post('/subcontract-bills/{bill_id}/actions/{action}')
def bill_action(pid:int,bill_id:int,action:str,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    if action not in BILL_TRANSITIONS:raise HTTPException(404,'Unknown bill action')
    guard(db,user,pid,BILL_TRANSITIONS[action][2])
    b=locked_bill(db,pid,bill_id,user.organization_id)
    next_status=next_bill_status(b.status,action)
    if action!='submit':
        if b.created_by==user.id:raise HTTPException(403,'Bill creator cannot approve or post own bill')
        previous=db.query(FinanceBillDecision).filter_by(bill_id=b.id,actor_id=user.id).filter(FinanceBillDecision.action.in_(['technical-approve','commercial-approve','post'])).first()
        if previous:raise HTTPException(403,'Separate reviewers required for each approval stage')
    if action=='post':
        if not db.query(FinanceBillLine).filter_by(bill_id=b.id).first():raise HTTPException(409,'Cannot post an empty bill')
        # Link contractual RA-bill deductions to the source balance ledger *in the
        # same transaction* as bill posting. A failed recovery aborts posting.
        # Lock the contract, serializing posting with manual balance movements.
        contract=db.query(FinanceContract).filter_by(id=b.contract_id,project_id=pid,status='Approved').with_for_update().one_or_none()
        if not contract:raise HTTPException(409,'Approved contract required for posting')
        for balance_type,movement,amount,suffix in (
            ('Subcontractor Advance','Decrease',Decimal(str(b.advance_recovery_amount)),'advance-recovery'),
            ('Retention Held','Increase',Decimal(str(b.retention_amount)),'retention-held'),
        ):
            if amount<=0:continue
            reference=f'RA-BILL:{b.id}:{suffix}'
            if db.query(FinanceBalanceEntry).filter_by(project_id=pid,reference=reference).first():
                raise HTTPException(409,'RA bill balance movement already exists')
            if movement=='Decrease':
                ledger=db.query(FinanceBalanceEntry).filter_by(project_id=pid,contract_id=b.contract_id,balance_type=balance_type,currency=contract.currency).all()
                validate_ra_balance_posting(amount,Decimal(str(b.retention_amount)),remaining_balance(ledger))
            db.add(FinanceBalanceEntry(project_id=pid,contract_id=b.contract_id,reference=reference,
                balance_type=balance_type,movement=movement,currency=contract.currency,amount=amount,
                evidence_reference=f'Posted RA bill {b.number}; technical/commercial approvals and deduction evidence',recorded_by=user.id))
        enforce_open_financial_period(db,pid,contract.currency,datetime.now(timezone.utc))
        b.posted_at=datetime.now(timezone.utc);b.posted_by=user.id
    b.status=next_status
    return bill_record_decision(db,b,user,action,body.reason)

@router.get('/subcontract-bills/{bill_id}/details')
def get_bill_details(pid:int,bill_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    b=locked_bill(db,pid,bill_id,user.organization_id)
    return bill_details(db,b)

@router.get('/subcontract-bills-posted-summary')
def posted_bill_summary(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    bills=db.query(FinanceSubcontractBill).filter_by(project_id=pid,status='Posted').all()
    grouped={}
    for b in bills:
        contract=db.query(FinanceContract).filter_by(id=b.contract_id,project_id=pid,organization_id=user.organization_id).one_or_none()
        if contract:grouped[contract.currency]=grouped.get(contract.currency,Decimal('0'))+b.gross_value
    return {'source':'Finance posted subcontract RA bills','read_only':True,'posted_gross_cost_by_currency':{k:str(v) for k,v in grouped.items()},'payments':None,'settlement_status':'Unavailable; payment allocations not yet implemented'}


# Phase 31.4 — source-linked client claims, explicit certification and external collections.
from .models import FinanceClientClaim, FinanceClientClaimLine, FinanceClientCollection, FinanceClientClaimDecision
from datetime import date

class ClientClaimIn(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    contract_id:int
    billing_period:str=Field(min_length=3,max_length=40)
    measurement_ids:list[int]=Field(min_length=1)
    evidence_reference:str=Field(min_length=8,max_length=2000)

class ClientClaimDecisionIn(BaseModel):
    reason:str=Field(min_length=8,max_length=2000)
    certified_value:Decimal|None=Field(default=None,ge=0,max_digits=20,decimal_places=2)
    due_date:datetime|None=None

class ClientCollectionIn(BaseModel):
    amount:Decimal=Field(gt=0,max_digits=20,decimal_places=2)
    received_at:datetime
    transaction_reference:str=Field(min_length=4,max_length=120)
    evidence_reference:str=Field(min_length=8,max_length=2000)

def client_claim_out(db,c):
    collected=sum((x.amount for x in db.query(FinanceClientCollection).filter_by(claim_id=c.id).all()),Decimal('0'))
    return {'id':c.id,'number':c.number,'contract_id':c.contract_id,'billing_period':c.billing_period,'currency':c.currency,'claimed_value':str(c.amount),'certified_value':str(c.certified_value),'collected_value':str(collected),'outstanding':str(max(Decimal('0'),c.certified_value-collected)),'status':c.status,'due_date':c.due_date.isoformat() if c.due_date else None,'evidence_reference':c.evidence_reference}

@router.get('/client-claims')
def client_claims_list(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [client_claim_out(db,c) for c in db.query(FinanceClientClaim).filter_by(project_id=pid).order_by(FinanceClientClaim.id.desc()).all()]

@router.post('/client-claims',status_code=201)
def client_claim_create(pid:int,body:ClientClaimIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    contract=db.query(FinanceContract).filter_by(id=body.contract_id,project_id=pid,organization_id=user.organization_id,contract_type='Client Revenue',status='Approved').one_or_none()
    if not contract:raise HTTPException(422,'Approved Client Revenue contract required')
    if len(body.measurement_ids)!=len(set(body.measurement_ids)):raise HTTPException(422,'Duplicate measurements in claim')
    measurements=db.query(FinanceMeasurement).filter(FinanceMeasurement.id.in_(body.measurement_ids),FinanceMeasurement.project_id==pid,FinanceMeasurement.contract_id==contract.id,FinanceMeasurement.status=='Certified').all()
    if len(measurements)!=len(body.measurement_ids):raise HTTPException(422,'All lines must be certified measurements of this client contract')
    used=db.query(FinanceClientClaimLine).filter(FinanceClientClaimLine.measurement_id.in_(body.measurement_ids)).first()
    if used:raise HTTPException(409,'Measurement already included in another client claim')
    total=sum((m.certified_quantity*m.unit_rate_snapshot for m in measurements),Decimal('0')).quantize(Decimal('0.01'))
    if total<=0:raise HTTPException(422,'Claim value must be positive')
    c=FinanceClientClaim(project_id=pid,contract_id=contract.id,number=body.number,billing_period=body.billing_period,amount=total,certified_value=Decimal('0'),currency=contract.currency,status='Draft',evidence_reference=body.evidence_reference,created_by=user.id)
    db.add(c)
    try:
        db.flush()
        for m in measurements:db.add(FinanceClientClaimLine(claim_id=c.id,measurement_id=m.id,value_snapshot=(m.certified_quantity*m.unit_rate_snapshot).quantize(Decimal('0.01'))))
        db.commit();db.refresh(c)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Claim or measurement already exists')
    return client_claim_out(db,c)

@router.post('/client-claims/{claim_id}/submit')
def client_claim_submit(pid:int,claim_id:int,body:ClientClaimDecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    c=db.query(FinanceClientClaim).filter_by(id=claim_id,project_id=pid).with_for_update().one_or_none()
    if not c:raise HTTPException(404,'Claim not found')
    if c.status!='Draft':raise HTTPException(409,'Only draft claims can be submitted')
    c.status='Submitted'
    db.add(FinanceClientClaimDecision(claim_id=c.id,actor_id=user.id,action='Submitted',note=body.reason))
    db.commit();db.refresh(c);return client_claim_out(db,c)

@router.post('/client-claims/{claim_id}/certify')
def client_claim_certify(pid:int,claim_id:int,body:ClientClaimDecisionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    c=db.query(FinanceClientClaim).filter_by(id=claim_id,project_id=pid).with_for_update().one_or_none()
    if not c:raise HTTPException(404,'Claim not found')
    if c.status!='Submitted':raise HTTPException(409,'Only submitted claims may be certified')
    if c.created_by==user.id:raise HTTPException(403,'Self certification prohibited')
    if body.certified_value is None:raise HTTPException(422,'Explicit client-certified value required')
    if body.certified_value>c.amount:raise HTTPException(422,'Certification above claim requires approved variation')
    if body.certified_value<=0:raise HTTPException(422,'Positive client certification required')
    c.certified_value=body.certified_value;c.status='Certified' if body.certified_value==c.amount else 'Partially Certified'
    c.due_date=body.due_date
    c.certified_by=user.id;c.certified_at=datetime.now(timezone.utc)
    db.add(FinanceClientClaimDecision(claim_id=c.id,actor_id=user.id,action=c.status,note=body.reason))
    db.commit();db.refresh(c);return client_claim_out(db,c)

@router.post('/client-claims/{claim_id}/collections',status_code=201)
def record_client_collection(pid:int,claim_id:int,body:ClientCollectionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    c=db.query(FinanceClientClaim).filter_by(id=claim_id,project_id=pid).with_for_update().one_or_none()
    if not c:raise HTTPException(404,'Claim not found')
    if c.status not in {'Certified','Partially Certified'}:raise HTTPException(409,'Client certification required before allocating collection')
    paid=sum((x.amount for x in db.query(FinanceClientCollection).filter_by(claim_id=c.id).all()),Decimal('0'))
    if body.amount>c.certified_value-paid:raise HTTPException(422,'Collection exceeds outstanding certified receivable')
    enforce_open_financial_period(db,pid,c.currency,body.received_at)
    record=FinanceClientCollection(project_id=pid,claim_id=c.id,amount=body.amount,currency=c.currency,received_at=body.received_at,transaction_reference=body.transaction_reference,evidence_reference=body.evidence_reference,recorded_by=user.id)
    commit(db,record)
    return client_claim_out(db,c)

@router.get('/client-receivables-summary')
def client_receivables_summary(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return client_receivables_data(db,pid)

def client_receivables_data(db,pid):
    summary={}
    for c in db.query(FinanceClientClaim).filter_by(project_id=pid).all():
        if c.status not in {'Certified','Partially Certified'}:continue
        s=summary.setdefault(c.currency,{'client_certified_value':Decimal('0'),'collections':Decimal('0'),'receivables_outstanding':Decimal('0')})
        paid=sum((r.amount for r in db.query(FinanceClientCollection).filter_by(claim_id=c.id).all()),Decimal('0'))
        s['client_certified_value']+=c.certified_value;s['collections']+=paid;s['receivables_outstanding']+=c.certified_value-paid
    return {'by_currency':{cur:{k:str(v) for k,v in val.items()} for cur,val in summary.items()},'basis':'Explicit client certification; externally recorded collections. Draft claims excluded. Not a general ledger.'}


# Phase 31.5: source-linked direct expenses, variation exposure and controlled balances.
from .models import FinanceDirectExpense, FinanceVariation, FinanceBalanceEntry, FinanceContract
from sqlalchemy import func

def _positive_money(value:Decimal):
    if not value.is_finite() or value <= 0 or value.as_tuple().exponent < -2:
        raise HTTPException(422,'Amount must be positive with at most two decimal places')
    return value

def _finance_record(x):
    return {k: (str(getattr(x,k)) if isinstance(getattr(x,k),Decimal) else getattr(x,k)) for k in ('id','project_id','status','number','amount','currency') if hasattr(x,k)}

class ExpenseIn(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    cost_code_id:int
    source_reference:str=Field(min_length=3,max_length=160)
    description:str=Field(min_length=5,max_length=1000)
    currency:str=Field(min_length=3,max_length=3)
    amount:Decimal
    evidence_reference:str=Field(min_length=8,max_length=1000)

@router.get('/direct-expenses')
def list_direct_expenses(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [_finance_record(x) for x in db.query(FinanceDirectExpense).filter_by(project_id=pid).order_by(FinanceDirectExpense.id.desc()).all()]

@router.post('/direct-expenses',status_code=201)
def create_direct_expense(pid:int,body:ExpenseIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    _positive_money(body.amount)
    if not db.query(FinanceCostCode).filter_by(id=body.cost_code_id,project_id=pid).first():raise HTTPException(422,'Cost code does not belong to project')
    row=FinanceDirectExpense(project_id=pid,created_by=user.id,status='Draft',**body.model_dump())
    return _finance_record(commit(db,row))

@router.post('/direct-expenses/{expense_id}/submit')
def submit_direct_expense(pid:int,expense_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    row=db.query(FinanceDirectExpense).filter_by(id=expense_id,project_id=pid).one_or_none()
    if not row:raise HTTPException(404,'Expense not found')
    if row.status!='Draft':raise HTTPException(409,'Only drafts can be submitted')
    row.status='Pending Review';return _finance_record(commit(db,row))

@router.post('/direct-expenses/{expense_id}/approve')
def approve_direct_expense(pid:int,expense_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    row=db.query(FinanceDirectExpense).filter_by(id=expense_id,project_id=pid).one_or_none()
    if not row:raise HTTPException(404,'Expense not found')
    if row.status!='Pending Review':raise HTTPException(409,'Expense not submitted')
    if row.created_by==user.id:raise HTTPException(403,'Self-approval prohibited')
    enforce_open_financial_period(db,pid,row.currency,datetime.now(timezone.utc))
    row.status='Posted';row.approved_by=user.id;row.approved_at=datetime.now(timezone.utc)
    return _finance_record(commit(db,row))

class VariationIn(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    contract_id:int
    description:str=Field(min_length=5,max_length=1000)
    cost_impact:Decimal=Decimal('0')
    revenue_impact:Decimal=Decimal('0')
    currency:str=Field(min_length=3,max_length=3)
    evidence_reference:str=Field(min_length=8,max_length=1000)

def _variation_out(x):
    return {'id':x.id,'number':x.number,'contract_id':x.contract_id,'description':x.description,'cost_impact':str(x.cost_impact),'revenue_impact':str(x.revenue_impact),'currency':x.currency,'status':x.status}

@router.get('/variations')
def list_variations(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [_variation_out(x) for x in db.query(FinanceVariation).filter_by(project_id=pid).order_by(FinanceVariation.id.desc()).all()]

@router.post('/variations',status_code=201)
def create_variation(pid:int,body:VariationIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    contract=db.query(FinanceContract).filter_by(id=body.contract_id,project_id=pid,status='Approved').one_or_none()
    if not contract:raise HTTPException(422,'Approved contract required')
    if body.currency!=contract.currency:raise HTTPException(422,'Variation currency must equal contract currency')
    for v in (body.cost_impact,body.revenue_impact):
        if not v.is_finite() or v.as_tuple().exponent < -2:raise HTTPException(422,'Invalid monetary impact')
    return _variation_out(commit(db,FinanceVariation(project_id=pid,created_by=user.id,status='Draft',**body.model_dump())))

@router.post('/variations/{variation_id}/submit')
def submit_variation(pid:int,variation_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    row=db.query(FinanceVariation).filter_by(id=variation_id,project_id=pid).one_or_none()
    if not row:raise HTTPException(404,'Variation not found')
    if row.status!='Draft':raise HTTPException(409,'Variation not draft')
    row.status='Under Review';return _variation_out(commit(db,row))

@router.post('/variations/{variation_id}/approve')
def approve_variation(pid:int,variation_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    row=db.query(FinanceVariation).filter_by(id=variation_id,project_id=pid).one_or_none()
    if not row:raise HTTPException(404,'Variation not found')
    if row.status!='Under Review':raise HTTPException(409,'Variation not submitted')
    if row.created_by==user.id:raise HTTPException(403,'Self-approval prohibited')
    row.status='Approved';row.approved_by=user.id;row.approved_at=datetime.now(timezone.utc)
    # Deliberately does NOT mutate approved contract, BOQ or budget.
    return _variation_out(commit(db,row))

BALANCE_TYPES={'Supplier Advance','Subcontractor Advance','Client Advance','Retention Held','Retention Receivable'}

def remaining_balance(entries):
    amount=sum((Decimal(str(e.amount)) if e.movement=='Increase' else -Decimal(str(e.amount)) for e in entries),Decimal('0.00'))
    if amount<0:raise ValueError('Invalid balance history')
    return amount

class BalanceEntryIn(BaseModel):
    contract_id:int
    reference:str=Field(min_length=3,max_length=120)
    balance_type:str
    movement:str
    amount:Decimal
    evidence_reference:str=Field(min_length=8,max_length=1000)

@router.get('/balances')
def balance_summary(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    rows=db.query(FinanceBalanceEntry).filter_by(project_id=pid).all()
    keys=sorted(set((e.contract_id,e.balance_type,e.currency) for e in rows))
    return {'balances':[{'contract_id':cid,'balance_type':typ,'currency':cc,'remaining':str(remaining_balance([e for e in rows if (e.contract_id,e.balance_type,e.currency)==(cid,typ,cc)]))} for cid,typ,cc in keys], 'source':'Approved explicit advance/retention movements; no bank execution'}

@router.post('/balances',status_code=201)
def record_balance_movement(pid:int,body:BalanceEntryIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    _positive_money(body.amount)
    if body.balance_type not in BALANCE_TYPES or body.movement not in {'Increase','Decrease'}:raise HTTPException(422,'Invalid balance movement')
    contract=db.query(FinanceContract).filter_by(id=body.contract_id,project_id=pid,status='Approved').one_or_none()
    if not contract:raise HTTPException(422,'Approved project contract required')
    # Serialize competing postings for this contract in PostgreSQL.
    contract=db.query(FinanceContract).filter_by(id=body.contract_id,project_id=pid).with_for_update().one()
    rows=db.query(FinanceBalanceEntry).filter_by(project_id=pid,contract_id=body.contract_id,balance_type=body.balance_type,currency=contract.currency).all()
    current=remaining_balance(rows)
    if body.movement=='Decrease' and body.amount>current:raise HTTPException(409,'Cannot release or recover more than outstanding balance')
    data=body.model_dump(exclude={'contract_id'})
    row=FinanceBalanceEntry(project_id=pid,contract_id=contract.id,currency=contract.currency,recorded_by=user.id,**data)
    return {'id':commit(db,row).id,'remaining':str(current+(body.amount if body.movement=='Increase' else -body.amount))}

@router.get('/subcontract-bills/{bill_id}/balance-reconciliation')
def bill_balance_reconciliation(pid:int,bill_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    bill=db.query(FinanceSubcontractBill).filter_by(id=bill_id,project_id=pid).one_or_none()
    if not bill:raise HTTPException(404,'Bill not found')
    entries=db.query(FinanceBalanceEntry).filter_by(project_id=pid,contract_id=bill.contract_id).all()
    linked=[e for e in entries if e.reference in {f'RA-BILL:{bill.id}:advance-recovery',f'RA-BILL:{bill.id}:retention-held'}]
    return {'bill_id':bill.id,'bill_number':bill.number,'status':bill.status,
        'advance_recovery_amount':str(bill.advance_recovery_amount),
        'retention_amount':str(bill.retention_amount),
        'ledger_entries':[{'reference':e.reference,'balance_type':e.balance_type,'movement':e.movement,
            'amount':str(e.amount),'currency':e.currency,'recorded_at':e.recorded_at.isoformat() if e.recorded_at else None} for e in linked],
        'reconciled':bill.status=='Posted' and (Decimal(str(bill.advance_recovery_amount))==sum((Decimal(str(e.amount)) for e in linked if e.balance_type=='Subcontractor Advance' and e.movement=='Decrease'),Decimal('0')))
            and (Decimal(str(bill.retention_amount))==sum((Decimal(str(e.amount)) for e in linked if e.balance_type=='Retention Held' and e.movement=='Increase'),Decimal('0'))),
        'policy':'Bill deductions change net payable; ledger recovery/retention does not create a new cost or bank payment'}

@router.get('/phase31-5-summary')
def phase315_summary(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    expenses=db.query(FinanceDirectExpense).filter_by(project_id=pid,status='Posted').all()
    variations=db.query(FinanceVariation).filter_by(project_id=pid,status='Under Review').all()
    cc=sorted(set([x.currency for x in expenses]+[x.currency for x in variations]))
    return {'read_only':True,'actual_direct_expenses_by_currency':{c:str(sum((x.amount for x in expenses if x.currency==c),Decimal('0.00'))) for c in cc},'unapproved_variation_exposure_by_currency':{c:str(sum((x.cost_impact for x in variations if x.currency==c),Decimal('0.00'))) for c in cc},'policy':'Posted direct expenses recognize cost; variations not in budgets/contracts until amendment; balance movements are not recognized cost or bank payments'}

@router.get('/internal-phase31-5-summary')
def internal_phase315_summary(pid:int,request:Request,db:Session=Depends(get_db)):
    """Service-authenticated finance source for Command Center; never client-supplied aggregates."""
    key=request.headers.get('X-ZerroR-Service-Key','')
    expected=settings.command_center_identity_service_key
    if not expected or not hmac.compare_digest(key,expected):raise HTTPException(403,'Internal service key required')
    project=db.get(Project,pid)
    if not project:raise HTTPException(404,'Project not found')
    expenses=db.query(FinanceDirectExpense).filter_by(project_id=pid,status='Posted').all()
    variations=db.query(FinanceVariation).filter_by(project_id=pid,status='Under Review').all()
    currencies=sorted(set([e.currency for e in expenses]+[v.currency for v in variations]))
    return {'project_id':pid,'organization_id':project.organization_id,'read_only':True,
            'source':'ZerroBuild Financials',
            'posted_direct_expense_cost_by_currency':{c:str(sum((e.amount for e in expenses if e.currency==c),Decimal('0.00'))) for c in currencies},
            'unapproved_variation_cost_exposure_by_currency':{c:str(sum((v.cost_impact for v in variations if v.currency==c),Decimal('0.00'))) for c in currencies},
            'note':'Do not sum direct expenses twice with other cost ledgers; variation exposure is not approved budget or contract value.'}


# Phase 31.6 — approved payment requests and evidence-backed, externally executed payments.
from .models import FinancePaymentRequest, FinancePaymentRecord

class PaymentRequestIn(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    bill_id:int
    amount:Decimal=Field(gt=0,max_digits=20,decimal_places=2)
    evidence_reference:str=Field(min_length=8,max_length=1000)
    due_date:datetime|None=None

class PaymentRecordIn(BaseModel):
    amount:Decimal=Field(gt=0,max_digits=20,decimal_places=2)
    paid_at:datetime
    transaction_reference:str=Field(min_length=4,max_length=160)
    evidence_reference:str=Field(min_length=8,max_length=1000)

def payment_remaining(approved:Decimal, previously_paid:Decimal, reserved:Decimal=Decimal('0')):
    """Amounts are all in the SAME currency; do not mix ledger purposes."""
    value=approved-previously_paid-reserved
    if value<0:raise ValueError('Payment requests/records exceed approved payable')
    return value

def _payment_out(db,p):
    paid=sum((x.amount for x in active_finance_payments(db, FinancePaymentRecord, pid, 'subcontract', payment_request_id=p.id)),Decimal('0'))
    return {'id':p.id,'number':p.number,'bill_id':p.bill_id,'amount':str(p.amount),'currency':p.currency,'status':p.status,'paid':str(paid),'unpaid':str(p.amount-paid),'due_date':p.due_date.isoformat() if p.due_date else None}

@router.get('/payment-requests')
def payment_requests(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [_payment_out(db,p) for p in db.query(FinancePaymentRequest).filter_by(project_id=pid).order_by(FinancePaymentRequest.id.desc()).all()]

@router.post('/payment-requests',status_code=201)
def create_payment_request(pid:int,body:PaymentRequestIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    bill=locked_bill(db,pid,body.bill_id,user.organization_id)
    if bill.status!='Posted':raise HTTPException(409,'Only posted RA bills are payable')
    contract=db.query(FinanceContract).filter_by(id=bill.contract_id,project_id=pid).one()
    active=db.query(FinancePaymentRequest).filter(FinancePaymentRequest.bill_id==bill.id,FinancePaymentRequest.status.in_(['Draft','Pending Review','Approved'])).all()
    existing_paid=sum((rec.amount for req in db.query(FinancePaymentRequest).filter_by(bill_id=bill.id).all() for rec in active_finance_payments(db, FinancePaymentRecord, pid, 'subcontract', payment_request_id=req.id)),Decimal('0'))
    reserved=sum((req.amount-sum((rec.amount for rec in active_finance_payments(db, FinancePaymentRecord, pid, 'subcontract', payment_request_id=req.id)),Decimal('0')) for req in active),Decimal('0'))
    if body.amount>payment_remaining(bill.net_payable,existing_paid,reserved):raise HTTPException(409,'Payment request exceeds unallocated net payable')
    p=commit(db,FinancePaymentRequest(project_id=pid,bill_id=bill.id,number=body.number,amount=body.amount,currency=contract.currency,due_date=body.due_date,evidence_reference=body.evidence_reference,created_by=user.id))
    return _payment_out(db,p)

@router.post('/payment-requests/{request_id}/submit')
def submit_payment_request(pid:int,request_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    p=db.query(FinancePaymentRequest).filter_by(id=request_id,project_id=pid).with_for_update().one_or_none()
    if not p:raise HTTPException(404,'Payment request not found')
    if p.status!='Draft':raise HTTPException(409,'Only draft request can be submitted')
    p.status='Pending Review';return _payment_out(db,commit(db,p))


# Phase 31.10: project-scoped monetary approval limits. When no limits have been
# configured for this project/type, legacy approval behavior remains enabled.
# A production policy should require complete authority setup before activation.
from .models import FinancePaymentApprovalLimit, FinanceAuthorityAudit, FinancePaymentDecisionAudit, FinanceApprovalPolicy, FinanceApprovalPolicyAudit

class PaymentApprovalLimitIn(BaseModel):
    user_id:int
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    payment_type:str
    maximum_amount:Decimal=Field(ge=0,max_digits=20,decimal_places=2)
    active:bool=True
    reason:str=Field(min_length=3,max_length=1000)

def enforce_payment_authority(db:Session,pid:int,user_id:int,currency:str,amount:Decimal,payment_type:str):
    if payment_type not in {'subcontract', 'supplier'}:
        raise HTTPException(422,'Unknown payment type')
    policies=db.query(FinancePaymentApprovalLimit).filter_by(project_id=pid,payment_type=payment_type).all()
    if not policies:
        strict=db.query(FinanceApprovalPolicy).filter_by(project_id=pid,payment_type=payment_type).one_or_none()
        if strict and strict.require_configured_authority:
            raise HTTPException(403,'Mandatory payment authority has not been configured')
        return 'legacy_unconfigured' 
    match=next((x for x in policies if x.user_id==user_id and x.currency==currency and x.active),None)
    if match is None:
        raise HTTPException(403,'No active payment approval authority for this currency')
    if amount>match.maximum_amount:
        raise HTTPException(403,'Payment amount exceeds configured approval authority')
    return 'configured'

@router.get('/payment-approval-limits')
def list_payment_approval_limits(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    return [{'id':x.id,'user_id':x.user_id,'currency':x.currency,'payment_type':x.payment_type,'maximum_amount':str(x.maximum_amount),'active':x.active} for x in db.query(FinancePaymentApprovalLimit).filter_by(project_id=pid).all()]

@router.post('/payment-approval-limits',status_code=201)
def upsert_payment_approval_limit(pid:int,body:PaymentApprovalLimitIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    guard(db,user,pid,'financials.approve')
    if body.payment_type not in {'subcontract','supplier'}:raise HTTPException(422,'Unknown payment type')
    target=db.get(User,body.user_id)
    if not target or not target.active or target.organization_id!=user.organization_id:raise HTTPException(422,'Approver outside organization or inactive')
    if body.user_id==user.id:raise HTTPException(403,'Cannot configure own approval authority')
    # Approver must possess the project-wide financial approval permission.
    guard(db,target,pid,'financials.approve')
    row=db.query(FinancePaymentApprovalLimit).filter_by(project_id=pid,user_id=body.user_id,currency=body.currency,payment_type=body.payment_type).with_for_update().one_or_none()
    if row is None:
        row=FinancePaymentApprovalLimit(project_id=pid,user_id=body.user_id,currency=body.currency,payment_type=body.payment_type,configured_by=user.id)
    prev_amount = row.maximum_amount if row.id is not None else None
    prev_active = row.active if row.id is not None else None
    row.maximum_amount=body.maximum_amount
    row.active=body.active
    row.configured_by=user.id
    row.configured_at=datetime.now(timezone.utc)
    # Authority update and immutable audit evidence commit atomically.
    db.add(row)
    db.flush()
    db.add(FinanceAuthorityAudit(project_id=pid,authority_id=row.id,target_user_id=body.user_id,
        changed_by=user.id,currency=body.currency,payment_type=body.payment_type,
        previous_amount=prev_amount,new_amount=body.maximum_amount,previous_active=prev_active,
        new_active=body.active,reason=body.reason))
    try: db.commit();db.refresh(row)
    except IntegrityError: db.rollback();raise HTTPException(409,'Duplicate authority or invalid reference')
    return {'id':row.id,'user_id':row.user_id,'currency':row.currency,'payment_type':row.payment_type,'maximum_amount':str(row.maximum_amount),'active':row.active}

@router.post('/payment-requests/{request_id}/approve')
def approve_payment_request(pid:int,request_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    p=db.query(FinancePaymentRequest).filter_by(id=request_id,project_id=pid).with_for_update().one_or_none()
    if not p:raise HTTPException(404,'Payment request not found')
    if p.status!='Pending Review':raise HTTPException(409,'Request not pending review')
    if p.created_by==user.id:raise HTTPException(403,'Self approval prohibited')
    authority_mode=enforce_payment_authority(db,pid,user.id,p.currency,p.amount,'subcontract')
    db.add(FinancePaymentDecisionAudit(project_id=pid,payment_type='subcontract',request_id=p.id,
        decision='Approved',actor_id=user.id,request_amount=p.amount,currency=p.currency,
        authority_mode=authority_mode,reason=body.reason))
    p.status='Approved';p.approved_at=datetime.now(timezone.utc);p.approved_by=user.id
    return _payment_out(db,commit(db,p))

@router.post('/payment-requests/{request_id}/records',status_code=201)
def record_external_payment(pid:int,request_id:int,body:PaymentRecordIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    p=db.query(FinancePaymentRequest).filter_by(id=request_id,project_id=pid).with_for_update().one_or_none()
    if not p:raise HTTPException(404,'Payment request not found')
    if p.status!='Approved':raise HTTPException(409,'Approved payment request required')
    already=sum((x.amount for x in active_finance_payments(db, FinancePaymentRecord, pid, 'subcontract', payment_request_id=p.id)),Decimal('0'))
    if body.amount>payment_remaining(p.amount,already):raise HTTPException(409,'Payment exceeds approved request balance')
    enforce_open_financial_period(db,pid,p.currency,body.paid_at)
    record=FinancePaymentRecord(project_id=pid,payment_request_id=p.id,amount=body.amount,currency=p.currency,paid_at=body.paid_at,transaction_reference=body.transaction_reference,evidence_reference=body.evidence_reference,recorded_by=user.id)
    commit(db,record)
    return _payment_out(db,p)

def settlement_data(db,pid:int):
    bills=db.query(FinanceSubcontractBill).filter_by(project_id=pid,status='Posted').all()
    requests=db.query(FinancePaymentRequest).filter_by(project_id=pid).all()
    records=active_finance_payments(db, FinancePaymentRecord, pid, 'subcontract')
    collections=db.query(FinanceClientCollection).filter_by(project_id=pid).all()
    contracts={x.id:x for x in db.query(FinanceContract).filter_by(project_id=pid).all()}
    totals={}
    def add(currency,key,amount):
        entry=totals.setdefault(currency,{'posted_net_payable':Decimal('0'),'recorded_payments':Decimal('0'),'outstanding_payables':Decimal('0'),'recorded_collections':Decimal('0'),'net_recorded_cash_flow':Decimal('0')})
        entry[key]+=amount
    for b in bills:
        if b.contract_id in contracts:add(contracts[b.contract_id].currency,'posted_net_payable',b.net_payable)
    for rec in records:add(rec.currency,'recorded_payments',rec.amount)
    for rec in collections:add(rec.currency,'recorded_collections',rec.amount)
    for val in totals.values():
        val['outstanding_payables']=val['posted_net_payable']-val['recorded_payments']
        val['net_recorded_cash_flow']=val['recorded_collections']-val['recorded_payments']
    return {'read_only':True,'by_currency':{c:{k:str(v) for k,v in val.items()} for c,val in sorted(totals.items())},'payment_request_count':len(requests),'basis':'Posted subcontract net payable, external recorded payments, recorded client collections. No bank transfer executed. Not full enterprise cash flow.'}

@router.get('/settlement-summary')
def settlement_summary(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return settlement_data(db,pid)

@router.get('/internal-settlement-summary')
def internal_settlement_summary(pid:int,request:Request,db:Session=Depends(get_db)):
    key=request.headers.get('X-ZerroR-Service-Key','')
    expected=settings.command_center_identity_service_key
    if not expected or not hmac.compare_digest(key,expected):raise HTTPException(403,'Internal service key required')
    project=db.get(Project,pid)
    if not project:raise HTTPException(404,'Project not found')
    return {'project_id':pid,'organization_id':project.organization_id,**settlement_data(db,pid)}



# Phase 31.9: Procurement invoice stays source-owned; finance controls settlement only.
from .models import FinanceSupplierPaymentRequest, FinanceSupplierPaymentRecord, FinanceSupplierInvoicePosting
from .models import FinanceSettlementReversal

def active_finance_payments(db, model, pid:int, payment_type:str, **filters):
    """Exclude fully reversed external settlement records from financial balances."""
    reversed_ids = db.query(FinanceSettlementReversal.payment_record_id).filter_by(
        project_id=pid, payment_type=payment_type
    )
    return db.query(model).filter_by(project_id=pid, **filters).filter(~model.id.in_(reversed_ids)).all()


class SupplierPaymentRequestIn(BaseModel):
    number:str=Field(min_length=1,max_length=80)
    invoice_posting_id:int
    amount:Decimal=Field(gt=0,max_digits=20,decimal_places=2)
    evidence_reference:str=Field(min_length=8,max_length=1000)
    due_date:datetime|None=None

def supplier_request_out(db,p):
    paid=sum((rec.amount for rec in active_finance_payments(db, FinanceSupplierPaymentRecord, pid, 'supplier', request_id=p.id)),Decimal('0'))
    return {'id':p.id,'number':p.number,'invoice_posting_id':p.invoice_posting_id,'amount':str(p.amount),'currency':p.currency,'status':p.status,'paid':str(paid),'remaining':str(p.amount-paid),'due_date':p.due_date.isoformat() if p.due_date else None}

def supplier_settlement_totals(db,pid):
    posted=db.query(FinanceSupplierInvoicePosting).filter_by(project_id=pid).all()
    paid=active_finance_payments(db, FinanceSupplierPaymentRecord, pid, 'supplier')
    totals={}
    for item in posted:
        entry=totals.setdefault(item.currency,{'posted_supplier_liability':Decimal('0'),'recorded_supplier_payments':Decimal('0')})
        entry['posted_supplier_liability']+=item.amount
    for item in paid:
        entry=totals.setdefault(item.currency,{'posted_supplier_liability':Decimal('0'),'recorded_supplier_payments':Decimal('0')})
        entry['recorded_supplier_payments']+=item.amount
    for entry in totals.values():entry['outstanding_supplier_payable']=entry['posted_supplier_liability']-entry['recorded_supplier_payments']
    return {cc:{k:str(v) for k,v in val.items()} for cc,val in sorted(totals.items())}

@router.get('/supplier-payment-requests')
def supplier_payment_requests(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return [supplier_request_out(db,p) for p in db.query(FinanceSupplierPaymentRequest).filter_by(project_id=pid).order_by(FinanceSupplierPaymentRequest.id.desc()).all()]

@router.post('/supplier-payment-requests',status_code=201)
def create_supplier_payment_request(pid:int,body:SupplierPaymentRequestIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    posting=db.query(FinanceSupplierInvoicePosting).filter_by(id=body.invoice_posting_id,project_id=pid,organization_id=user.organization_id).with_for_update().one_or_none()
    if not posting:raise HTTPException(404,'Finance-posted supplier invoice not found')
    prior=db.query(FinanceSupplierPaymentRequest).filter_by(project_id=pid,invoice_posting_id=posting.id).all()
    reserved=sum((q.amount for q in prior if q.status in ('Draft','Pending Review','Approved')),Decimal('0'))
    inactive_paid=sum((v.amount for q in prior if q.status not in ('Draft','Pending Review','Approved') for v in active_finance_payments(db, FinanceSupplierPaymentRecord, pid, 'supplier', request_id=q.id)),Decimal('0'))
    # Active reservations include their prior partial payments; inactive requests reserve only recorded settlements.
    if body.amount>payment_remaining(posting.amount,reserved,inactive_paid):
        raise HTTPException(409,'Supplier payment exceeds unallocated posted invoice balance')
    p=commit(db,FinanceSupplierPaymentRequest(project_id=pid,invoice_posting_id=posting.id,number=body.number,amount=body.amount,currency=posting.currency,due_date=body.due_date,evidence_reference=body.evidence_reference,created_by=user.id))
    return supplier_request_out(db,p)

@router.post('/supplier-payment-requests/{request_id}/submit')
def submit_supplier_payment_request(pid:int,request_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    p=db.query(FinanceSupplierPaymentRequest).filter_by(project_id=pid,id=request_id).with_for_update().one_or_none()
    if not p:raise HTTPException(404,'Request not found')
    if p.status!='Draft':raise HTTPException(409,'Draft required')
    p.status='Pending Review';return supplier_request_out(db,commit(db,p))

@router.post('/supplier-payment-requests/{request_id}/approve')
def approve_supplier_payment_request(pid:int,request_id:int,body:Decision,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    p=db.query(FinanceSupplierPaymentRequest).filter_by(project_id=pid,id=request_id).with_for_update().one_or_none()
    if not p:raise HTTPException(404,'Request not found')
    if p.status!='Pending Review':raise HTTPException(409,'Pending review required')
    if p.created_by==user.id:raise HTTPException(403,'Self approval prohibited')
    authority_mode=enforce_payment_authority(db,pid,user.id,p.currency,p.amount,'supplier')
    db.add(FinancePaymentDecisionAudit(project_id=pid,payment_type='supplier',request_id=p.id,
        decision='Approved',actor_id=user.id,request_amount=p.amount,currency=p.currency,
        authority_mode=authority_mode,reason=body.reason))
    p.status='Approved';p.approved_by=user.id;p.approved_at=datetime.now(timezone.utc)
    return supplier_request_out(db,commit(db,p))

@router.post('/supplier-payment-requests/{request_id}/records',status_code=201)
def record_supplier_payment(pid:int,request_id:int,body:PaymentRecordIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    p=db.query(FinanceSupplierPaymentRequest).filter_by(project_id=pid,id=request_id).with_for_update().one_or_none()
    if not p:raise HTTPException(404,'Request not found')
    if p.status!='Approved':raise HTTPException(409,'Approved request required')
    paid=sum((v.amount for v in active_finance_payments(db, FinanceSupplierPaymentRecord, pid, 'supplier', request_id=p.id)),Decimal('0'))
    if body.amount>payment_remaining(p.amount,paid):raise HTTPException(409,'Payment exceeds approved request')
    # Separate unique index protects recorded external reference idempotency.
    enforce_open_financial_period(db,pid,p.currency,body.paid_at)
    commit(db,FinanceSupplierPaymentRecord(project_id=pid,request_id=p.id,amount=body.amount,currency=p.currency,paid_at=body.paid_at,transaction_reference=body.transaction_reference,evidence_reference=body.evidence_reference,recorded_by=user.id))
    return supplier_request_out(db,p)

@router.get('/supplier-settlement-summary')
def supplier_settlement_summary(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return {'read_only':True,'by_currency':supplier_settlement_totals(db,pid),'basis':'Posted Procurement supplier invoices and separately evidenced external payments; payments do not recognize cost'}

# Phase 31.12: compensating settlement reversals; external bank movement is not executed here.
class SettlementReversalIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1500)
    evidence_reference: str = Field(min_length=8, max_length=1000)

@router.post('/settlement-reversals/{payment_type}/{record_id}', status_code=201)
def reverse_settlement(pid:int, payment_type:str, record_id:int, body:SettlementReversalIn,
                       user:User=Depends(authenticated), db:Session=Depends(get_db)):
    guard(db, user, pid, 'financials.approve')
    if payment_type not in {'supplier', 'subcontract'}:
        raise HTTPException(422, 'Unsupported payment category')
    cls = FinanceSupplierPaymentRecord if payment_type == 'supplier' else FinancePaymentRecord
    # Serialize reversals for the same payment; unique database constraint also protects races.
    payment=db.query(cls).filter_by(id=record_id,project_id=pid).with_for_update().one_or_none()
    if payment is None: raise HTTPException(404, 'Recorded payment not found')
    prior=db.query(FinanceSettlementReversal).filter_by(project_id=pid,payment_type=payment_type,payment_record_id=record_id).one_or_none()
    if prior: raise HTTPException(409, 'Payment already reversed')
    entry=FinanceSettlementReversal(project_id=pid,payment_type=payment_type,payment_record_id=record_id,
        original_amount=payment.amount,currency=payment.currency,reason=body.reason,
        evidence_reference=body.evidence_reference,reversed_by=user.id)
    commit(db,entry)
    return {'id':entry.id,'payment_type':payment_type,'payment_record_id':record_id,
            'reversed_amount':str(entry.original_amount),'currency':entry.currency,'status':'Reversed'}

@router.get('/settlement-reversals')
def list_settlement_reversals(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    items=db.query(FinanceSettlementReversal).filter_by(project_id=pid).order_by(FinanceSettlementReversal.id.desc()).all()
    return [{'id':x.id,'payment_type':x.payment_type,'payment_record_id':x.payment_record_id,
             'reversed_amount':str(x.original_amount),'currency':x.currency,'reason':x.reason,
             'evidence_reference':x.evidence_reference,'reversed_by':x.reversed_by,
             'reversed_at':x.reversed_at.isoformat() if x.reversed_at else None} for x in items]

# Phase 31.7: authoritative, currency-separated financial intelligence.
# This endpoint intentionally does not manufacture EAC, forecasts or supplier payments.
from datetime import datetime, timezone
from .procurement_integration import overview as procurement_overview

def financial_intelligence_data(db:Session, pid:int, organization_id:int):
    project=db.get(Project,pid)
    if not project or project.organization_id!=organization_id:
        raise HTTPException(404,'Project not found')
    approved=db.query(FinanceBudget).filter_by(project_id=pid,organization_id=organization_id,status='Approved').order_by(FinanceBudget.revision.desc()).all()
    budget_latest={}
    for b in approved:budget_latest.setdefault(b.code,b)
    procurement=procurement_overview(db,pid,organization_id)
    bills=db.query(FinanceSubcontractBill).filter_by(project_id=pid,status='Posted').all()
    direct=db.query(FinanceDirectExpense).filter_by(project_id=pid,status='Posted').all()
    variation=db.query(FinanceVariation).filter_by(project_id=pid,status='Under Review').all()
    claims=client_receivables_data(db,pid)['by_currency']
    settlement=settlement_data(db,pid)['by_currency']
    totals={}
    def slot(cc):
        return totals.setdefault(cc,{'approved_budget':Decimal('0'),'approved_po_commitments':Decimal('0'),'open_po_commitments':Decimal('0'),'posted_supplier_cost':Decimal('0'),'posted_subcontract_cost':Decimal('0'),'posted_direct_expenses':Decimal('0'),'client_certified_value':Decimal('0'),'collections':Decimal('0'),'receivables_outstanding':Decimal('0'),'subcontract_net_payable':Decimal('0'),'subcontract_payments':Decimal('0'),'subcontract_outstanding_payable':Decimal('0'),'unapproved_variation_exposure':Decimal('0'),'supplier_payments':Decimal('0'),'supplier_outstanding_payable':Decimal('0')})
    for b in budget_latest.values():slot(b.currency)['approved_budget']+=b.proposed_amount
    for cc,v in procurement['by_currency'].items():
        t=slot(cc)
        for dest,src in [('approved_po_commitments','approved_commitments'),('open_po_commitments','open_commitments'),('posted_supplier_cost','recognized_actual_cost')]:t[dest]+=Decimal(v[src])
    for b in bills:
        contract=db.query(FinanceContract).filter_by(id=b.contract_id,project_id=pid,organization_id=organization_id).one_or_none()
        if contract:slot(contract.currency)['posted_subcontract_cost']+=b.gross_value
    for e in direct:slot(e.currency)['posted_direct_expenses']+=e.amount
    for v in variation:slot(v.currency)['unapproved_variation_exposure']+=v.cost_impact
    for cc,v in claims.items():
        t=slot(cc)
        for key in ('client_certified_value','collections','receivables_outstanding'):t[key]+=Decimal(v[key])
    for cc,v in settlement.items():
        t=slot(cc)
        # use names provided by settlement_data, never interpret payment as additional cost
        mapping={'subcontract_net_payable':('posted_net_payable','net_payable'), 'subcontract_payments':('recorded_payments','payments'), 'subcontract_outstanding_payable':('outstanding_payables','outstanding_payable','unpaid_payable')}
        for dest,aliases in mapping.items():
            for alias in aliases:
                if alias in v:
                    t[dest]+=Decimal(v[alias]);break
    for cc,val in supplier_settlement_totals(db,pid).items():
        slot(cc)['supplier_payments']+=Decimal(val['recorded_supplier_payments'])
        slot(cc)['supplier_outstanding_payable']+=Decimal(val['outstanding_supplier_payable'])
    # Forecast input belongs to the latest approved budget revision. A complete
    # remaining-cost forecast must cover every approved budget line in a currency;
    # otherwise reporting EAC would mislead the project manager.
    by_currency_budgets={}
    for b in budget_latest.values():
        by_currency_budgets.setdefault(b.currency,[]).append(b)
    for cc,row in totals.items():
        row['recognized_actual_cost']=row['posted_supplier_cost']+row['posted_subcontract_cost']+row['posted_direct_expenses']
        lines=by_currency_budgets.get(cc,[])
        complete=bool(lines) and all(b.forecast_remaining is not None for b in lines)
        row['forecast_coverage'] = f"{sum(b.forecast_remaining is not None for b in lines)}/{len(lines)}" if lines else '0/0'
        row['forecast_remaining_cost']=sum((b.forecast_remaining for b in lines),Decimal('0')) if complete else None
        row['estimate_at_completion']=row['recognized_actual_cost']+row['forecast_remaining_cost'] if complete else None
        row['forecast_variance']=row['approved_budget']-row['estimate_at_completion'] if complete else None
    # Payable aging uses approved payment requests only. This is NOT aging of
    # every supplier or subcontract liability, since not every bill has a due date.
    now=datetime.now(timezone.utc)
    requests=db.query(FinancePaymentRequest).filter_by(project_id=pid,status='Approved').all()
    payments=active_finance_payments(db, FinancePaymentRecord, pid, 'subcontract')
    paid_by_request={}
    for rec in payments:
        paid_by_request[rec.payment_request_id]=paid_by_request.get(rec.payment_request_id,Decimal('0'))+rec.amount
    aging={}
    alerts=[]
    for req in requests:
        due=req.due_date
        if not due:continue
        remaining=max(Decimal('0'),req.amount-paid_by_request.get(req.id,Decimal('0')))
        if not remaining:continue
        if due.tzinfo is None:due=due.replace(tzinfo=timezone.utc)
        days=(now.date()-due.date()).days
        bucket='not_due' if days<=0 else ('1_30' if days<=30 else '31_60' if days<=60 else '61_90' if days<=90 else 'over_90')
        entry=aging.setdefault(req.currency,{'not_due':Decimal('0'),'1_30':Decimal('0'),'31_60':Decimal('0'),'61_90':Decimal('0'),'over_90':Decimal('0')})
        entry[bucket]+=remaining
        if days>0:
            alerts.append({'kind':'overdue_payment_request','request_id':req.id,'number':req.number,'currency':req.currency,'amount':str(remaining),'days_overdue':days})
    for cc,row in totals.items():
        if row['forecast_variance'] is not None and row['forecast_variance']<0:
            alerts.append({'kind':'forecast_over_budget','currency':cc,'amount':str(-row['forecast_variance'])})

    # Phase 31.17: only dated, certified, outstanding receivables can be aged.
    from .financial_aging import receivables_aging_and_cash_forecast
    certified_claims=db.query(FinanceClientClaim).filter_by(project_id=pid).all()
    active_claims=[c for c in certified_claims if c.status in {'Certified','Partially Certified'}]
    collections_by_claim={}
    for c in active_claims:
        collections_by_claim[c.id]=sum((x.amount for x in db.query(FinanceClientCollection).filter_by(claim_id=c.id).all()),Decimal('0'))
    receivables_aging,receivable_alerts,forecast_inflows,undated_count=receivables_aging_and_cash_forecast(active_claims,collections_by_claim,now)
    forecast_outflows={}
    for req in requests:
        if not req.due_date:continue
        remaining=max(Decimal('0'),req.amount-paid_by_request.get(req.id,Decimal('0')))
        if remaining<=0:continue
        key=req.due_date.date().isoformat()
        forecast_outflows.setdefault(req.currency,{})[key]=forecast_outflows.setdefault(req.currency,{}).get(key,Decimal('0'))+remaining
    alerts.extend(receivable_alerts)
    if undated_count:
        alerts.append({'kind':'receivables_missing_due_date','count':undated_count})
    cash_forecast={'basis':'Expected receipts from dated certified receivables and approved subcontract payment requests only. Excludes undated items, supplier payment requests, unapproved claims, and opening cash; not a forecast cash balance.',
        'expected_inflows_by_currency_date':{cc:{date:str(v) for date,v in sorted(rows.items())} for cc,rows in forecast_inflows.items()},
        'expected_outflows_by_currency_date':{cc:{date:str(v) for date,v in sorted(rows.items())} for cc,rows in forecast_outflows.items()},
        'complete':False,'opening_cash_balance':None}
    # Null forecasts are deliberate; never coerce an unavailable number to zero.
    return {'project_id':pid,'project_code':project.code,'read_only':True,'generated_at':datetime.now(timezone.utc).isoformat(),
        'source':'ZerroBuild Financials + Procurement source invoices + certified client claims',
        'basis':'Recognized cost = posted supplier invoices + gross posted subcontract work + posted direct expenses. PO commitments, client claims, payments, and retention are not additional costs.',
        'currencies':{cc:{key:(str(val) if isinstance(val,Decimal) else val) for key,val in row.items()} for cc,row in sorted(totals.items())},
        'estimate_at_completion':None,'forecast_variance':None,'cash_flow_forecast':cash_forecast,
        'payment_request_aging_by_currency':{cc:{k:str(v) for k,v in buckets.items()} for cc,buckets in sorted(aging.items())},
        'alerts':alerts,'alerts_basis':'Derived in-app exceptions only; notification delivery and escalation are not implemented.',
        'receivables_aging':receivables_aging,
        'unmapped_purchase_order_count':procurement['unmapped_purchase_order_count'],
        'limitations':['EAC per currency is available only when all approved budget lines have a remaining-cost forecast; forecast inputs must include outstanding commitments and expected uncommitted cost','Supplier settlement supported for finance-posted Procurement invoices; full accruals, client due dates, and multi-currency conversions not included','Records are source-linked in owning modules; enterprise source drill-down is not yet complete']}

# Phase 31.18: read-only, project-scoped financial source evidence.
# This deliberately excludes payment account details and personal payroll data.
FINANCIAL_EVIDENCE_TYPES = {'budgets', 'supplier_cost', 'subcontract_cost', 'direct_expenses', 'client_claims'}

def financial_evidence_data(db:Session, pid:int, organization_id:int, category:str, currency:str|None=None):
    if category not in FINANCIAL_EVIDENCE_TYPES:
        raise HTTPException(422, 'Unsupported evidence category')
    if currency is not None and (len(currency)!=3 or not currency.isalpha() or currency.upper()!=currency):
        raise HTTPException(422, 'Invalid currency')
    project=db.get(Project,pid)
    if not project or project.organization_id!=organization_id:
        raise HTTPException(404, 'Project not found')
    records=[]
    if category=='budgets':
        rows=db.query(FinanceBudget).filter_by(project_id=pid,organization_id=organization_id,status='Approved').order_by(FinanceBudget.code,FinanceBudget.revision.desc()).all()
        latest={}
        for row in rows: latest.setdefault(row.code,row)
        records=[{'source_type':'finance_budget','source_id':row.id,'reference':row.code,'revision':row.revision,'status':row.status,'currency':row.currency,'amount':str(row.proposed_amount),'description':row.description,'approved_at':row.approved_at.isoformat() if row.approved_at else None} for row in latest.values()]
    elif category=='supplier_cost':
        rows=db.query(FinanceSupplierInvoicePosting).filter_by(project_id=pid,organization_id=organization_id).order_by(FinanceSupplierInvoicePosting.id.desc()).all()
        records=[{'source_type':'procurement_vendor_invoice','source_id':row.vendor_invoice_id,'posting_id':row.id,'reference':str(row.vendor_invoice_id),'status':'Posted','currency':row.currency,'amount':str(row.amount),'purchase_order_id':row.purchase_order_id,'cost_code_id':row.cost_code_id,'posted_at':row.posted_at.isoformat() if row.posted_at else None} for row in rows]
    elif category=='subcontract_cost':
        rows=db.query(FinanceSubcontractBill).filter_by(project_id=pid,status='Posted').order_by(FinanceSubcontractBill.id.desc()).all()
        for row in rows:
            contract=db.query(FinanceContract).filter_by(id=row.contract_id,project_id=pid,organization_id=organization_id).one_or_none()
            if contract: records.append({'source_type':'finance_subcontract_bill','source_id':row.id,'reference':row.number,'status':row.status,'currency':contract.currency,'amount':str(row.gross_value),'contract_id':contract.id,'posted_at':row.posted_at.isoformat() if row.posted_at else None})
    elif category=='direct_expenses':
        rows=db.query(FinanceDirectExpense).filter_by(project_id=pid,status='Posted').order_by(FinanceDirectExpense.id.desc()).all()
        records=[{'source_type':'finance_direct_expense','source_id':row.id,'reference':str(row.id),'status':row.status,'currency':row.currency,'amount':str(row.amount)} for row in rows]
    elif category=='client_claims':
        rows=db.query(FinanceClientClaim).filter_by(project_id=pid).order_by(FinanceClientClaim.id.desc()).all()
        records=[{'source_type':'finance_client_claim','source_id':row.id,'reference':row.number,'status':row.status,'currency':row.currency,'amount':str(row.certified_value),'contract_id':row.contract_id,'certified_at':row.certified_at.isoformat() if row.certified_at else None} for row in rows if row.status in {'Certified','Partially Certified'}]
    filtered=[r for r in records if currency is None or r['currency']==currency]
    # Source ids remain stable; the response is capped to protect response size.
    return {'project_code':project.code,'read_only':True,'category':category,'currency':currency,'total_records':len(filtered),'truncated':len(filtered)>100,'rows':filtered[:100], 'basis':'Owning ZerroBuild records only; no manually entered Command Center values'}

@router.get('/internal-financial-evidence')
def internal_financial_evidence(pid:int,request:Request,category:str,currency:str|None=None,db:Session=Depends(get_db)):
    key=request.headers.get('X-ZerroR-Service-Key','')
    expected=settings.command_center_identity_service_key
    if not expected or not hmac.compare_digest(key,expected): raise HTTPException(403,'Internal service key required')
    project=db.get(Project,pid)
    if not project:raise HTTPException(404,'Project not found')
    return financial_evidence_data(db,pid,project.organization_id,category,currency)

@router.get('/financial-evidence')
def financial_evidence(pid:int,category:str,currency:str|None=None,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return financial_evidence_data(db,pid,user.organization_id,category,currency)

@router.get('/internal-financial-intelligence')
def internal_financial_intelligence(pid:int,request:Request,db:Session=Depends(get_db)):
    key=request.headers.get('X-ZerroR-Service-Key','')
    expected=settings.command_center_identity_service_key
    if not expected or not hmac.compare_digest(key,expected):raise HTTPException(403,'Internal service key required')
    project=db.get(Project,pid)
    if not project:raise HTTPException(404,'Project not found')
    return financial_intelligence_data(db,pid,project.organization_id)

@router.get('/financial-intelligence')
def financial_intelligence(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    return financial_intelligence_data(db,pid,user.organization_id)


@router.get('/approval-audit')
def approval_audit(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    changes=db.query(FinanceAuthorityAudit).filter_by(project_id=pid).order_by(FinanceAuthorityAudit.id.desc()).limit(500).all()
    decisions=db.query(FinancePaymentDecisionAudit).filter_by(project_id=pid).order_by(FinancePaymentDecisionAudit.id.desc()).limit(500).all()
    return {'read_only':True, 'authority_changes':[{'id':x.id,'authority_id':x.authority_id,
        'target_user_id':x.target_user_id,'changed_by':x.changed_by,'currency':x.currency,
        'payment_type':x.payment_type,'previous_amount':str(x.previous_amount) if x.previous_amount is not None else None,
        'new_amount':str(x.new_amount),'previous_active':x.previous_active,'new_active':x.new_active,
        'reason':x.reason,'changed_at':x.changed_at.isoformat()} for x in changes],
        'payment_decisions':[{'id':x.id,'payment_type':x.payment_type,'request_id':x.request_id,
        'decision':x.decision,'actor_id':x.actor_id,'request_amount':str(x.request_amount),
        'currency':x.currency,'authority_mode':x.authority_mode,'reason':x.reason,
        'decided_at':x.decided_at.isoformat()} for x in decisions]}


# Phase 31.15 — controlled monthly close and reopen. All dates are UTC.
from datetime import date
from .models import FinancePeriod, FinancePeriodDecision

def financial_period_start(value:datetime)->datetime:
    if value.tzinfo is None:
        raise HTTPException(422,'Timezone-aware financial posting date required')
    utc=value.astimezone(timezone.utc)
    return datetime(utc.year,utc.month,1,tzinfo=timezone.utc)

def enforce_open_financial_period(db:Session,pid:int,currency:str,when:datetime):
    """Block dated financial posting into a closed period (rechecked in the write transaction)."""
    start=financial_period_start(when)
    row=(db.query(FinancePeriod).filter_by(project_id=pid,currency=currency,period_start=start)
         .with_for_update().one_or_none())
    if row and row.status=='Closed':
        raise HTTPException(409,'Financial period is closed: request controlled reopening')

class PeriodActionIn(BaseModel):
    reason:str=Field(min_length=10,max_length=1500)

@router.get('/periods')
def financial_periods(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    periods=db.query(FinancePeriod).filter_by(project_id=pid).order_by(FinancePeriod.period_start.desc()).all()
    return [{'id':p.id,'currency':p.currency,'period_start':p.period_start.date().isoformat(),
             'status':p.status,'closed_by':p.closed_by,'closed_at':p.closed_at} for p in periods]

@router.post('/periods/{currency}/{year}/{month}/close')
def close_financial_period(pid:int,currency:str,year:int,month:int,body:PeriodActionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    if not (currency.isalpha() and len(currency)==3):raise HTTPException(422,'Three-letter currency required')
    try: start=datetime(year,month,1,tzinfo=timezone.utc)
    except ValueError:raise HTTPException(422,'Invalid reporting month')
    if start>datetime.now(timezone.utc):raise HTTPException(409,'Future period cannot be closed')
    period=(db.query(FinancePeriod).filter_by(project_id=pid,currency=currency.upper(),period_start=start)
            .with_for_update().one_or_none())
    if period and period.status=='Closed':raise HTTPException(409,'Period already closed')
    if not period:
        period=FinancePeriod(project_id=pid,currency=currency.upper(),period_start=start,status='Closed')
        db.add(period);db.flush()
    period.status='Closed';period.closed_by=user.id;period.closed_at=datetime.now(timezone.utc)
    db.add(FinancePeriodDecision(period_id=period.id,project_id=pid,action='Close',reason=body.reason,actor_id=user.id))
    db.commit()
    return {'id':period.id,'status':'Closed','currency':period.currency,'period_start':start.date().isoformat()}

@router.post('/periods/{period_id}/reopen')
def reopen_financial_period(pid:int,period_id:int,body:PeriodActionIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    period=(db.query(FinancePeriod).filter_by(id=period_id,project_id=pid).with_for_update().one_or_none())
    if not period:raise HTTPException(404,'Period not found')
    if period.status!='Closed':raise HTTPException(409,'Only closed periods can be reopened')
    period.status='Open'
    db.add(FinancePeriodDecision(period_id=period.id,project_id=pid,action='Reopen',reason=body.reason,actor_id=user.id))
    db.commit()
    return {'id':period.id,'status':'Open'}

@router.get('/periods/{period_id}/audit')
def financial_period_audit(pid:int,period_id:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.view')
    if not db.query(FinancePeriod).filter_by(id=period_id,project_id=pid).first():raise HTTPException(404,'Period not found')
    rows=db.query(FinancePeriodDecision).filter_by(project_id=pid,period_id=period_id).order_by(FinancePeriodDecision.id).all()
    return [{'action':r.action,'reason':r.reason,'actor_id':r.actor_id,'recorded_at':r.recorded_at} for r in rows]


# Phase 31.16: project-level strict authority switch and derived overdue approval queue.
class ApprovalPolicyIn(BaseModel):
    payment_type:str
    require_configured_authority:bool
    overdue_after_hours:int=Field(ge=1,le=720)
    reason:str=Field(min_length=5,max_length=1000)

@router.get('/approval-policies')
def get_approval_policies(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    return [{'payment_type':r.payment_type,'require_configured_authority':r.require_configured_authority,'overdue_after_hours':r.overdue_after_hours} for r in db.query(FinanceApprovalPolicy).filter_by(project_id=pid).all()]

@router.put('/approval-policies')
def put_approval_policy(pid:int,body:ApprovalPolicyIn,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.manage')
    guard(db,user,pid,'financials.approve')
    if body.payment_type not in {'supplier','subcontract'}:raise HTTPException(422,'Unknown payment type')
    row=db.query(FinanceApprovalPolicy).filter_by(project_id=pid,payment_type=body.payment_type).with_for_update().one_or_none()
    if row is None:row=FinanceApprovalPolicy(project_id=pid,payment_type=body.payment_type,changed_by=user.id)
    old={'require_configured_authority':row.require_configured_authority,'overdue_after_hours':row.overdue_after_hours} if row.id else None
    row.require_configured_authority=body.require_configured_authority
    row.overdue_after_hours=body.overdue_after_hours
    row.changed_by=user.id;row.changed_at=datetime.now(timezone.utc)
    db.add(row)
    db.flush()
    # Reuse existing immutable authority audit table to preserve who changed controls.
    # No payment-limit row exists for policy changes, so retain a distinct dedicated audit.
    db.add(FinanceApprovalPolicyAudit(project_id=pid,payment_type=body.payment_type,actor_id=user.id,
         previous_policy=old,new_policy={'require_configured_authority':body.require_configured_authority,'overdue_after_hours':body.overdue_after_hours},reason=body.reason))
    db.commit();db.refresh(row)
    return {'payment_type':row.payment_type,'require_configured_authority':row.require_configured_authority,'overdue_after_hours':row.overdue_after_hours}

@router.get('/approval-policies/audit')
def approval_policy_audit(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    return [{'payment_type':r.payment_type,'actor_id':r.actor_id,'previous_policy':r.previous_policy,'new_policy':r.new_policy,'reason':r.reason,'changed_at':r.changed_at.isoformat()} for r in db.query(FinanceApprovalPolicyAudit).filter_by(project_id=pid).order_by(FinanceApprovalPolicyAudit.id.desc()).limit(200).all()]

@router.get('/pending-payment-approvals')
def pending_finance_approvals(pid:int,user:User=Depends(authenticated),db:Session=Depends(get_db)):
    guard(db,user,pid,'financials.approve')
    now=datetime.now(timezone.utc)
    configured={r.payment_type:r for r in db.query(FinanceApprovalPolicy).filter_by(project_id=pid).all()}
    rows=[]
    for kind,model in [('supplier',FinanceSupplierPaymentRequest),('subcontract',FinancePaymentRequest)]:
        policy=configured.get(kind)
        limit=policy.overdue_after_hours if policy else 48
        for r in db.query(model).filter_by(project_id=pid,status='Pending Review').all():
            # Existing models don't expose a submitted timestamp. Use record creation if present.
            since=getattr(r,'created_at',None)
            if since and since.tzinfo is None:since=since.replace(tzinfo=timezone.utc)
            hours=max(0,int((now-since).total_seconds()//3600)) if since else None
            rows.append({'payment_type':kind,'request_id':r.id,'number':r.number,'currency':r.currency,
                         'amount':str(r.amount),'hours_pending':hours,
                         'overdue':hours is not None and hours>=limit,
                         'aging_status':'unknown' if hours is None else 'overdue' if hours>=limit else 'within_target'})
    return {'read_only':True,'items':rows,'warning':'No automated notification delivery. Requests with no timestamp have unknown aging.'}
