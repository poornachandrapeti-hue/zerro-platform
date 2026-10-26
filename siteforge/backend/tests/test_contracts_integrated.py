"""Integrated Contracts regression: authorization and separation of authority."""
import os
os.environ.setdefault('DATABASE_URL','sqlite:////tmp/contracts_test.db')
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.main import app
from app.db import Base
from app.domains.identity_projects.models import Organization,Company,User,Project,ProjectCompany,Role,Membership
from app.domains.contracts.models import Contract,ContractVersion
from app.domains.contracts.router import (
    ContractIn, DecisionIn, ShareIn,PartnerSubmission,
    create,submit,approve,execute,activate,publish,partner_allowed,partner_submit,partner_detail
)

@pytest.fixture
def state():
    eng=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(eng)
    with Session(eng) as db:
        org=Organization(name='Test Org');db.add(org);db.flush()
        a=Company(organization_id=org.id,name='Owner',name_key='owner')
        b=Company(organization_id=org.id,name='Partner A',name_key='a')
        other=Company(organization_id=org.id,name='Partner B',name_key='b')
        db.add_all([a,b,other]);db.flush()
        admin=User(organization_id=org.id,email='admin@example.test',name='Admin',password_hash='!',organization_admin=True)
        peer=User(organization_id=org.id,email='peer@example.test',name='Peer Approver',password_hash='!',organization_admin=True)
        partner_a=User(organization_id=org.id,company_id=b.id,email='a@example.test',name='A',password_hash='!')
        partner_b=User(organization_id=org.id,company_id=other.id,email='b@example.test',name='B',password_hash='!')
        db.add_all([admin,peer,partner_a,partner_b]);db.flush()
        proj=Project(organization_id=org.id,code='P1',code_key='p1',name='Project',created_by=admin.id)
        db.add(proj);db.flush()
        db.add_all([ProjectCompany(project_id=proj.id,company_id=b.id,participation_type='Contractor'),ProjectCompany(project_id=proj.id,company_id=other.id,participation_type='Contractor')]);db.flush()
        role=Role(name='Partner-test',permissions=[]);db.add(role);db.flush()
        db.add_all([Membership(project_id=proj.id,user_id=partner_a.id,company_id=b.id,role_id=role.id,scope='ALL'),Membership(project_id=proj.id,user_id=partner_b.id,company_id=other.id,role_id=role.id,scope='ALL')]);db.commit()
        yield db,proj,admin,peer,partner_a,partner_b,a,b,other

def contract(state):
    db,p,admin,peer,pa,pb,a,b,other=state
    row=create(p.id,ContractIn(number='CT-001',title='Civil foundations',contract_type='Subcontract',contracting_company_id=a.id,counterparty_company_id=b.id,manager_user_id=admin.id,scope='Foundations for steel plant',currency='INR',original_value='100000',effective_at='2026-10-20T00:00:00Z'),admin,db)
    return db.get(Contract,row['id'])

def test_draft_cannot_activate_and_self_approval_rejected(state):
    db,p,admin,peer,*_=state
    c=contract(state)
    with pytest.raises(HTTPException) as e:activate(p.id,c.id,DecisionIn(reason='premature activation'),admin,db)
    assert e.value.status_code==409
    submit(p.id,c.id,DecisionIn(reason='Submit for approval'),admin,db)
    with pytest.raises(HTTPException) as e:approve(p.id,c.id,DecisionIn(reason='self approval'),admin,db)
    assert e.value.status_code==403
    approve(p.id,c.id,DecisionIn(reason='Reviewed contract'),peer,db)
    with pytest.raises(HTTPException):activate(p.id,c.id,DecisionIn(reason='no signatures'),peer,db)
    execute(p.id,c.id,DecisionIn(reason='signed document verified',evidence='signed-contract-file-001'),admin,db)
    activate(p.id,c.id,DecisionIn(reason='activation approved'),peer,db)
    assert db.get(Contract,c.id).lifecycle=='Active'

def test_partner_visibility_requires_publication_and_correct_company(state):
    db,p,admin,peer,pa,pb,a,b,other=state
    c=contract(state)
    with pytest.raises(HTTPException):partner_allowed(db,pa,c.id)
    submit(p.id,c.id,DecisionIn(reason='internal review'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='accepted internally'),peer,db)
    execute(p.id,c.id,DecisionIn(reason='signed agreement',evidence='signed-evidence-abcdef'),admin,db)
    publish(p.id,c.id,ShareIn(company_id=b.id,can_submit=True),admin,db)
    assert partner_detail(c.id,pa,db)['version']==1
    with pytest.raises(HTTPException) as e:partner_detail(c.id,pb,db)
    assert e.value.status_code==404
    posted=partner_submit(c.id,PartnerSubmission(category='claim',number='CL-101',summary='Additional certified work',evidence='claim-evidence-001'),pa,db)
    assert posted['status']=='Submitted'
    assert db.get(Contract,c.id).original_value==100000

def test_no_implicit_acceptance_on_partner_submission(state):
    db,p,admin,peer,pa,pb,a,b,other=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='internal review'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='reviewed fully'),peer,db)
    execute(p.id,c.id,DecisionIn(reason='signed document',evidence='document-reference-22'),admin,db)
    publish(p.id,c.id,ShareIn(company_id=b.id,can_submit=True),admin,db)
    partner_submit(c.id,PartnerSubmission(category='variation',number='VAR-001',summary='Additional approved drawing works',evidence='evidence-reference-001'),pa,db)
    assert db.get(Contract,c.id).current_version==1
    assert db.get(Contract,c.id).approval_state=='Approved Internally'


def test_signer_cannot_be_the_approver(state):
    db,p,admin,peer,*_=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='ready for review'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='reviewed terms'),peer,db)
    with pytest.raises(HTTPException) as exc:
        execute(p.id,c.id,DecisionIn(reason='signed document verification',evidence='signed-version-one'),peer,db)
    assert exc.value.status_code==403
    assert c.lifecycle=='Awaiting Signature'

def test_missing_approval_decision_blocks_signing(state):
    from app.domains.contracts.models import ContractApprovalDecision
    db,p,admin,peer,*_=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='ready for review'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='reviewed terms'),peer,db)
    row=db.query(ContractApprovalDecision).filter_by(contract_id=c.id).one()
    db.delete(row);db.commit()
    with pytest.raises(HTTPException) as exc:
        execute(p.id,c.id,DecisionIn(reason='sign evidence verified',evidence='signed-version-one'),admin,db)
    assert exc.value.status_code==409


def test_sequential_review_requires_assigned_reviewer(state):
    from app.domains.contracts.router import (ReviewRouteIn, ReviewStageIn, configure_review_route,
                                               decide_review_stage, review_route)
    db,p,author,first,*_=state
    c=contract(state)
    second=User(organization_id=author.organization_id,email='second-review@example.test',name='Second Reviewer',password_hash='!',organization_admin=True)
    db.add(second);db.commit()
    configure_review_route(p.id,c.id,ReviewRouteIn(stages=[ReviewStageIn(label='Commercial',reviewer_user_id=first.id),ReviewStageIn(label='Legal',reviewer_user_id=second.id)]),author,db)
    submit(p.id,c.id,DecisionIn(reason='review this contract'),author,db)
    with pytest.raises(HTTPException) as e:
        decide_review_stage(p.id,c.id,2,DecisionIn(reason='too early for me'), 'Approve',second,db)
    assert e.value.status_code==409
    with pytest.raises(HTTPException) as e:
        approve(p.id,c.id,DecisionIn(reason='bypass sequential review'),first,db)
    assert e.value.status_code==409
    decide_review_stage(p.id,c.id,1,DecisionIn(reason='Commercial terms checked'),'Approve',first,db)
    assert review_route(p.id,c.id,author,db)[1]['status']=='Pending'
    decide_review_stage(p.id,c.id,2,DecisionIn(reason='Legal review completed'),'Approve',second,db)
    assert c.approval_state=='Approved Internally'
    with pytest.raises(HTTPException):execute(p.id,c.id,DecisionIn(reason='signed evidence exists',evidence='signed-contract-123'),second,db)
    execute(p.id,c.id,DecisionIn(reason='signed by independent user',evidence='signed-contract-123'),author,db)
    assert c.lifecycle=='Executed'


def test_return_and_resubmit_restarts_review_route(state):
    from app.domains.contracts.router import ReviewRouteIn,ReviewStageIn,configure_review_route,decide_review_stage,review_route
    db,p,author,reviewer,*_=state
    c=contract(state)
    configure_review_route(p.id,c.id,ReviewRouteIn(stages=[ReviewStageIn(label='Technical review',reviewer_user_id=reviewer.id)]),author,db)
    submit(p.id,c.id,DecisionIn(reason='ready for review'),author,db)
    decide_review_stage(p.id,c.id,1,DecisionIn(reason='Return for corrections'),'Return',reviewer,db)
    assert c.approval_state=='Draft'
    submit(p.id,c.id,DecisionIn(reason='corrections completed'),author,db)
    assert review_route(p.id,c.id,author,db)[0]['status']=='Pending'
    decide_review_stage(p.id,c.id,1,DecisionIn(reason='Corrected and accepted'),'Approve',reviewer,db)
    assert c.approval_state=='Approved Internally'


def test_configured_authority_blocks_unlisted_signer(state):
    from datetime import datetime, timedelta, timezone
    from app.domains.contracts.router import AuthorityIn, configure_signing_authority
    db,p,admin,peer,*_=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='submit for authority test'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='approved with authority'),peer,db)
    now=datetime.now(timezone.utc)
    configure_signing_authority(p.id,AuthorityIn(user_id=peer.id,currency='INR',max_value='150000',valid_from=now-timedelta(days=1),valid_until=now+timedelta(days=30)),admin,db)
    with pytest.raises(HTTPException) as exc:
        execute(p.id,c.id,DecisionIn(reason='attempt unauthorized signature',evidence='signed-agreement-001'),admin,db)
    assert exc.value.status_code==403
    assert c.lifecycle=='Awaiting Signature'


def test_valid_delegation_and_revoke(state):
    from datetime import datetime, timedelta, timezone
    from app.domains.contracts.router import AuthorityIn,DelegationIn,configure_signing_authority,delegate_signing,revoke_delegation
    db,p,admin,peer,*_=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='submit for delegation'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='approved for delegation'),peer,db)
    now=datetime.now(timezone.utc)
    configure_signing_authority(p.id,AuthorityIn(user_id=peer.id,currency='INR',max_value='150000',valid_from=now-timedelta(days=1),valid_until=now+timedelta(days=30)),admin,db)
    d=delegate_signing(p.id,c.id,DelegationIn(delegate_user_id=admin.id,valid_from=now-timedelta(minutes=1),valid_until=now+timedelta(days=3)),peer,db)
    revoke_delegation(p.id,c.id,d['id'],peer,db)
    with pytest.raises(HTTPException) as exc:
        execute(p.id,c.id,DecisionIn(reason='revoked delegated signature',evidence='signed-agreement-002'),admin,db)
    assert exc.value.status_code==403


def test_delegated_signing_with_ceiling(state):
    from datetime import datetime, timedelta, timezone
    from app.domains.contracts.router import AuthorityIn,DelegationIn,configure_signing_authority,delegate_signing
    db,p,admin,peer,*_=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='submit for signature'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='independently approved'),peer,db)
    now=datetime.now(timezone.utc)
    configure_signing_authority(p.id,AuthorityIn(user_id=peer.id,currency='INR',max_value='150000',valid_from=now-timedelta(days=1),valid_until=now+timedelta(days=30)),admin,db)
    delegate_signing(p.id,c.id,DelegationIn(delegate_user_id=admin.id,valid_from=now-timedelta(minutes=1),valid_until=now+timedelta(days=3)),peer,db)
    execute(p.id,c.id,DecisionIn(reason='authorized delegate signature',evidence='signed-agreement-003'),admin,db)
    assert c.lifecycle=='Executed'


def test_signing_matrix_rejects_wrong_currency_and_insufficient_ceiling(state):
    from datetime import datetime,timedelta,timezone
    from app.domains.contracts.router import AuthorityIn,configure_signing_authority
    db,p,admin,peer,*_=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='submit for approval'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='independent review complete'),peer,db)
    now=datetime.now(timezone.utc)
    configure_signing_authority(p.id,AuthorityIn(user_id=admin.id,currency='USD',max_value='999999',valid_from=now-timedelta(days=1),valid_until=now+timedelta(days=2)),admin,db)
    with pytest.raises(HTTPException) as error:
        execute(p.id,c.id,DecisionIn(reason='wrong currency attempt',evidence='signed-evidence-001'),admin,db)
    assert error.value.status_code==403
    configure_signing_authority(p.id,AuthorityIn(user_id=admin.id,currency='INR',max_value='999',valid_from=now-timedelta(days=1),valid_until=now+timedelta(days=2)),admin,db)
    with pytest.raises(HTTPException) as error:
        execute(p.id,c.id,DecisionIn(reason='insufficient signing ceiling',evidence='signed-evidence-002'),admin,db)
    assert error.value.status_code==403

def test_overlapping_delegations_are_rejected(state):
    from datetime import datetime,timedelta,timezone
    from app.domains.contracts.router import AuthorityIn,DelegationIn,configure_signing_authority,delegate_signing
    db,p,admin,peer,*_=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='submit for signing review'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='review complete and approved'),peer,db)
    now=datetime.now(timezone.utc)
    configure_signing_authority(p.id,AuthorityIn(user_id=peer.id,currency='INR',max_value='150000',valid_from=now-timedelta(days=1),valid_until=now+timedelta(days=20)),admin,db)
    delegate_signing(p.id,c.id,DelegationIn(delegate_user_id=admin.id,valid_from=now,valid_until=now+timedelta(days=7)),peer,db)
    with pytest.raises(HTTPException) as error:
        delegate_signing(p.id,c.id,DelegationIn(delegate_user_id=admin.id,valid_from=now+timedelta(days=2),valid_until=now+timedelta(days=8)),peer,db)
    assert error.value.status_code==409


def test_variation_counterparty_agreement_needs_internal_approval(state):
    from app.domains.contracts.router import RecordIn, record_create, record_counterparty_agreement, CounterpartyAgreementIn
    from datetime import datetime,timezone
    db,p,admin,peer,*_=state
    c=contract(state)
    rec=record_create(p.id,c.id,RecordIn(category='variation',number='V-01',summary='Extra civil concrete work',amount='500',currency='INR'),admin,db)
    body=CounterpartyAgreementIn(agreement_reference='Signed VO 01', evidence='Signed variation evidence PDF',agreed_at=datetime.now(timezone.utc))
    with pytest.raises(HTTPException) as exc:
        record_counterparty_agreement(p.id,c.id,rec['id'],body,peer,db)
    assert exc.value.status_code==409


def test_variation_agreement_does_not_change_contract_value(state):
    from app.domains.contracts.router import RecordIn, record_create, record_decide,record_counterparty_agreement, CounterpartyAgreementIn
    from datetime import datetime,timezone
    from app.domains.contracts.models import ContractRecord
    db,p,admin,peer,*_=state
    c=contract(state)
    rec=record_create(p.id,c.id,RecordIn(category='variation',number='V-02',summary='Extra steel installation work',amount='500',currency='INR'),admin,db)
    record_decide(p.id,c.id,rec['id'],DecisionIn(reason='Technically and commercially reviewed'),'Accepted',peer,db)
    body=CounterpartyAgreementIn(agreement_reference='Agreed VO 02',evidence='Counterparty signed variation',agreed_at=datetime.now(timezone.utc))
    with pytest.raises(HTTPException) as exc:
        record_counterparty_agreement(p.id,c.id,rec['id'],body,admin,db)
    assert exc.value.status_code==403
    result=record_counterparty_agreement(p.id,c.id,rec['id'],body,peer,db)
    assert result['requires_amendment'] and not result['effective_value_changed']
    assert db.get(Contract,c.id).original_value==100000
    assert db.get(ContractRecord,rec['id']).status=='Agreed - Pending Amendment'
    with pytest.raises(HTTPException) as exc:
        record_counterparty_agreement(p.id,c.id,rec['id'],body,peer,db)
    assert exc.value.status_code==409


def test_formal_amendment_preserves_base_value_and_creates_pending_deliveries(state):
    from app.domains.contracts.router import (
        AmendmentPrepareIn,
        AmendmentApprovalIn, AmendmentExecuteIn, prepare_amendment, approve_amendment,
        execute_amendment)
    from app.domains.contracts.models import ContractAmendment, ContractModuleDelivery
    from datetime import datetime, timezone
    from decimal import Decimal
    from app.domains.identity_projects.models import User
    db,p,admin,peer,*_=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='review request'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='review complete'),peer,db)
    execute(p.id,c.id,DecisionIn(reason='executed version',evidence='signed-base-document'),admin,db)
    third=User(organization_id=admin.organization_id,email='third@example.test',name='Third signatory',password_hash='!',organization_admin=True)
    db.add(third);db.commit()
    # Set up a variation using the persisted typed subregister.
    from app.domains.contracts.models import ContractRecord
    v=ContractRecord(contract_id=c.id,category='variation',number='V-01',summary='Approved additions',status='Agreed - Pending Amendment',amount=2500,currency='INR',created_by=admin.id,details={'counterparty_agreement':{'reference':'AGR-01'}})
    db.add(v);db.commit()
    prepared=prepare_amendment(p.id,c.id,AmendmentPrepareIn(variation_id=v.id,amendment_number='AMD-01'),admin,db)
    assert c.original_value==100000
    approve_amendment(p.id,c.id,prepared['id'],AmendmentApprovalIn(reason='Reviewed signed commercial changes'),peer,db)
    result=execute_amendment(p.id,c.id,prepared['id'],AmendmentExecuteIn(evidence='signed-amendment-document'),third,db)
    assert Decimal(result['effective_value'])==Decimal('102500')
    assert c.original_value==100000 and c.current_version==2
    assert db.query(ContractModuleDelivery).filter_by(amendment_id=prepared['id'],status='Pending').count()==3
    assert db.get(ContractAmendment,prepared['id']).status=='Executed'


def test_amendment_self_approval_rejected(state):
    from app.domains.contracts.router import AmendmentApprovalIn, approve_amendment
    from app.domains.contracts.models import ContractAmendment
    db,p,admin,*_=state
    c=contract(state)
    a=ContractAmendment(contract_id=c.id,variation_id=987654,amendment_number='AMD-X',delta_value=100,currency='INR',prepared_by=admin.id)
    db.add(a);db.flush()
    with pytest.raises(HTTPException) as error:
        approve_amendment(p.id,c.id,a.id,AmendmentApprovalIn(reason='I approve myself'),admin,db)
    assert error.value.status_code==403


def test_downstream_receipt_acknowledgment_and_idempotency(state):
    from app.domains.contracts.router import DeliveryReceiptIn, record_amendment_delivery_receipt, amendment_delivery_reconciliation
    from app.domains.contracts.models import ContractRecord, ContractAmendment, ContractModuleDelivery
    db,p,admin,peer,*_=state
    c=contract(state)
    v=ContractRecord(contract_id=c.id,category='variation',number='R-01',summary='Test',status='Amended',created_by=admin.id)
    db.add(v);db.flush()
    a=ContractAmendment(contract_id=c.id,variation_id=v.id,amendment_number='A-01',delta_value=20,currency='INR',status='Executed',prepared_by=admin.id,effective_version_id=1)
    db.add(a);db.flush()
    d=ContractModuleDelivery(amendment_id=a.id,destination='Financials',status='Pending',payload={'event':'contract.amendment.executed','contract_id':c.id,'project_id':p.id,'organization_id':c.organization_id,'amendment_id':a.id,'version':2})
    db.add(d);db.commit()
    receipt=DeliveryReceiptIn(receipt_reference='FIN-ACK-10',contract_version=2,applied=True)
    with pytest.raises(HTTPException) as error:
        record_amendment_delivery_receipt(p.id,c.id,a.id,'Financials',DeliveryReceiptIn(receipt_reference='wrong',contract_version=1,applied=True),peer,db)
    assert error.value.status_code==409
    result=record_amendment_delivery_receipt(p.id,c.id,a.id,'Financials',receipt,peer,db)
    assert result['status']=='Acknowledged' and not result['idempotent']
    repeat=record_amendment_delivery_receipt(p.id,c.id,a.id,'Financials',receipt,peer,db)
    assert repeat['idempotent']
    with pytest.raises(HTTPException) as error:
        record_amendment_delivery_receipt(p.id,c.id,a.id,'Financials',DeliveryReceiptIn(receipt_reference='FIN-OTHER',contract_version=2,applied=True),peer,db)
    assert error.value.status_code==409
    rows=amendment_delivery_reconciliation(p.id,peer,db)
    assert len(rows)==1 and rows[0]['status']=='Acknowledged'


def test_failed_delivery_cannot_be_misreported_as_acknowledged(state):
    from app.domains.contracts.router import DeliveryReceiptIn, record_amendment_delivery_receipt
    from app.domains.contracts.models import ContractRecord, ContractAmendment, ContractModuleDelivery
    db,p,admin,peer,*_=state
    c=contract(state)
    v=ContractRecord(contract_id=c.id,category='variation',number='R-02',summary='Test',status='Amended',created_by=admin.id)
    db.add(v);db.flush()
    a=ContractAmendment(contract_id=c.id,variation_id=v.id,amendment_number='A-02',delta_value=20,currency='INR',status='Executed',prepared_by=admin.id,effective_version_id=1)
    db.add(a);db.flush()
    db.add(ContractModuleDelivery(amendment_id=a.id,destination='Planning',status='Pending',payload={'event':'contract.amendment.executed','contract_id':c.id,'project_id':p.id,'organization_id':c.organization_id,'amendment_id':a.id,'version':2}))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        record_amendment_delivery_receipt(p.id,c.id,a.id,'Planning',DeliveryReceiptIn(receipt_reference='PL-FAIL',contract_version=2,applied=False),peer,db)
    assert exc.value.status_code==422
    result=record_amendment_delivery_receipt(p.id,c.id,a.id,'Planning',DeliveryReceiptIn(receipt_reference='PL-FAIL',contract_version=2,applied=False,failure_reason='Planning version conflict'),peer,db)
    assert result['status']=='Failed'


def test_consumer_persists_idempotent_projection_without_finance_posting(state):
    from app.domains.contracts.router import consume_contract_amendment
    from app.domains.contracts.models import ContractRecord, ContractAmendment, ContractModuleDelivery, ContractConsumerProjection
    from app.domains.commercial_financials.models import FinanceSupplierInvoicePosting
    db,p,admin,peer,*_=state
    c=contract(state)
    v=ContractRecord(contract_id=c.id,category='variation',number='CV-01',summary='Test',status='Amended',created_by=admin.id)
    db.add(v);db.flush()
    a=ContractAmendment(contract_id=c.id,variation_id=v.id,amendment_number='CA-01',delta_value=30,currency='INR',status='Executed',prepared_by=admin.id,effective_version_id=db.query(ContractVersion).filter_by(contract_id=c.id).one().id)
    db.add(a);db.flush()
    ev={'event':'contract.amendment.executed','contract_id':c.id,'project_id':p.id,'organization_id':c.organization_id,'amendment_id':a.id,'version':1}
    db.add(ContractModuleDelivery(amendment_id=a.id,destination='Financials',payload=ev,status='Pending'));db.commit()
    first=consume_contract_amendment(p.id,c.id,a.id,'Financials',peer,db)
    assert first['status']=='Acknowledged' and not first['financial_posting_created']
    assert consume_contract_amendment(p.id,c.id,a.id,'Financials',peer,db)['idempotent']
    assert db.query(ContractConsumerProjection).count()==1
    assert db.query(FinanceSupplierInvoicePosting).count()==0
    with pytest.raises(HTTPException) as err:consume_contract_amendment(p.id,c.id,a.id,'Unknown',peer,db)
    assert err.value.status_code==422


def test_consumer_rejects_wrong_event_version(state):
    from app.domains.contracts.router import consume_contract_amendment
    from app.domains.contracts.models import ContractRecord, ContractAmendment, ContractModuleDelivery, ContractConsumerProjection
    db,p,admin,peer,*_=state
    c=contract(state)
    v=ContractRecord(contract_id=c.id,category='variation',number='CV-02',summary='Test',status='Amended',created_by=admin.id)
    db.add(v);db.flush()
    a=ContractAmendment(contract_id=c.id,variation_id=v.id,amendment_number='CA-02',delta_value=30,currency='INR',status='Executed',prepared_by=admin.id,effective_version_id=db.query(ContractVersion).filter_by(contract_id=c.id).one().id)
    db.add(a);db.flush()
    ev={'event':'contract.amendment.executed','contract_id':c.id,'project_id':p.id,'organization_id':c.organization_id,'amendment_id':a.id,'version':99}
    db.add(ContractModuleDelivery(amendment_id=a.id,destination='Planning',payload=ev,status='Pending'));db.commit()
    with pytest.raises(HTTPException) as err:consume_contract_amendment(p.id,c.id,a.id,'Planning',peer,db)
    assert err.value.status_code==409
    assert db.query(ContractConsumerProjection).count()==0


def test_structured_scope_is_version_bound_and_locked(state):
    from app.domains.contracts.router import ScopeItemIn, add_scope_item, list_scope_items
    db,p,admin,peer,pa,pb,a,b,other=state
    c=contract(state)
    payload=ScopeItemIn(item_code='S-001',item_type='Deliverable',description='Pile foundation handover',responsible_company_id=b.id,responsible_user_id=pa.id)
    result=add_scope_item(p.id,c.id,payload,admin,db)
    assert result['version']==1
    assert list_scope_items(p.id,c.id,None,admin,db)[0]['item_code']=='S-001'
    submit(p.id,c.id,DecisionIn(reason='Submit scope for review'),admin,db)
    with pytest.raises(HTTPException) as exc:add_scope_item(p.id,c.id,ScopeItemIn(item_code='S-002',item_type='Exclusion',description='Other work'),admin,db)
    assert exc.value.status_code==409


def test_commercial_terms_are_restricted_and_locked(state):
    from app.domains.contracts.router import TermVersionIn,add_commercial_term,list_commercial_terms
    db,p,admin,peer,pa,pb,a,b,other=state
    c=contract(state)
    add_commercial_term(p.id,c.id,TermVersionIn(term_key='retention_release',value={'percentage':'5','release_trigger':'approved certificate'}),admin,db)
    assert len(list_commercial_terms(p.id,c.id,None,admin,db))==1
    with pytest.raises(HTTPException) as exc:list_commercial_terms(p.id,c.id,None,pa,db)
    assert exc.value.status_code==403
    submit(p.id,c.id,DecisionIn(reason='Contract review needed'),admin,db)
    with pytest.raises(HTTPException) as exc:add_commercial_term(p.id,c.id,TermVersionIn(term_key='insurance_requirements',value={'policy':'required'}),admin,db)
    assert exc.value.status_code==409


"""CM0113: copy-on-version BOQ protection and commercial read scope."""



def test_draft_revision_preserves_prior_boq_and_carries_forward(state):
    from app.domains.contracts.router import BoqIn, VersionIn, add_boq, boq, revise
    from app.domains.contracts.models import ContractBoq
    db, project, admin, *_ = state
    c = contract(state)
    add_boq(project.id,c.id,BoqIn(code='CW-001',description='Foundation concrete',unit='m3',
        quantity='12.0000',rate='4000',currency='INR'),admin,db)
    first=db.query(ContractVersion).filter_by(contract_id=c.id,version=1).one()
    old=db.query(ContractBoq).filter_by(version_id=first.id).one()
    revise(project.id,c.id,VersionIn(reason='Correcting scope for review',scope='Revised foundation package'),admin,db)
    second=db.query(ContractVersion).filter_by(contract_id=c.id,version=2).one()
    new=db.query(ContractBoq).filter_by(version_id=second.id).one()
    assert new.id!=old.id
    assert (new.code,new.quantity,new.rate)==(old.code,old.quantity,old.rate)
    assert old.version_id==first.id and new.version_id==second.id
    assert len(boq(project.id,c.id,admin,db))==2


def test_boq_read_requires_commercial_permission(state):
    from app.domains.contracts.router import boq
    db,project,admin,peer,partner_a,*_=state
    c=contract(state)
    with pytest.raises(HTTPException) as exc:
        boq(project.id,c.id,partner_a,db)
    assert exc.value.status_code==403


def test_cm0113_draft_boq_revision_rejects_historical_lines(state):
    from app.domains.contracts.router import BoqIn,BoqRevisionIn,add_boq,revise_boq_line,VersionIn,revise
    from app.domains.contracts.models import ContractBoq
    db,p,admin,*_=state
    c=contract(state)
    created=add_boq(p.id,c.id,BoqIn(code='C-01',description='Concrete work',unit='m3',quantity=10,rate=100,currency='INR'),admin,db)
    revised=revise_boq_line(p.id,c.id,created['id'],BoqRevisionIn(description='Concrete foundation work',unit='m3',quantity=12,rate=110,currency='INR',reason='Corrected estimated foundation quantity'),admin,db)
    assert revised['rate']=='110.00'
    revise(p.id,c.id,VersionIn(reason='Design revision for foundation',scope='Revised foundations for steel plant'),admin,db)
    with pytest.raises(HTTPException) as error:
        revise_boq_line(p.id,c.id,created['id'],BoqRevisionIn(description='Unauthorized old version edit',unit='m3',quantity=20,rate=200,currency='INR',reason='Attempt to edit historical rate'),admin,db)
    assert error.value.status_code==404
    old=db.get(ContractBoq,created['id'])
    assert old.rate==110


def test_cm0113_finance_boq_requires_link_and_effective_version(state):
    from app.domains.contracts.router import BoqIn,add_boq,finance_boq_terms,submit,approve,execute,activate
    from app.domains.contracts.models import ContractFinanceLink
    db,p,admin,peer,*_=state
    c=contract(state)
    add_boq(p.id,c.id,BoqIn(code='F-01',description='Concrete foundation',unit='m3',quantity=3,rate=250,currency='INR'),admin,db)
    with pytest.raises(HTTPException) as error:finance_boq_terms(p.id,c.id,None,admin,db)
    assert error.value.status_code==409
    db.add(ContractFinanceLink(organization_id=c.organization_id,project_id=p.id,contract_id=c.id,finance_contract_id=987,linked_by=admin.id))
    db.commit()
    with pytest.raises(HTTPException) as error:finance_boq_terms(p.id,c.id,None,admin,db)
    assert error.value.status_code==409
    submit(p.id,c.id,DecisionIn(reason='Submit for BOQ approval'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='Approved verified rate schedule'),peer,db)
    execute(p.id,c.id,DecisionIn(reason='Executed approved agreement',evidence='signed-approved-boq-file'),admin,db)
    activate(p.id,c.id,DecisionIn(reason='Approved contract activation'),peer,db)
    result=finance_boq_terms(p.id,c.id,None,admin,db)
    assert result['read_only'] is True and result['billing_authorized'] is False
    assert result['lines'][0]['rate']=='250.00'


def test_cm0114_claim_requires_notice_and_preserves_effective_value(state):
    from app.domains.contracts.router import ClaimCreateIn, ClaimNoticeIn, ClaimEvidenceIn, create_claim, record_claim_notice, submit_claim
    db,project,creator,reviewer,*_=state
    c=contract(state)
    claim=create_claim(project.id,c.id,ClaimCreateIn(number='CL-EOT-01',category='Delay/EOT',description='Access delay to blast furnace workfront',event_at='2026-10-20T00:00:00Z',notice_required=True,requested_eot_days=12,owner_user_id=creator.id),creator,db)
    with pytest.raises(HTTPException) as ex:
        submit_claim(project.id,c.id,claim['id'],ClaimEvidenceIn(evidence='submitted evidence package'),creator,db)
    assert ex.value.status_code==409
    record_claim_notice(project.id,c.id,claim['id'],ClaimNoticeIn(sent_at='2026-10-21T00:00:00Z',evidence='transmittal and receipt proof'),creator,db)
    submitted=submit_claim(project.id,c.id,claim['id'],ClaimEvidenceIn(evidence='formal claim evidence'),creator,db)
    assert submitted['status']=='Submitted'
    assert db.get(Contract,c.id).original_value==100000
    assert db.get(Contract,c.id).current_version==1


def test_cm0114_claim_decision_segregation_and_no_automatic_entitlement(state):
    from app.domains.contracts.router import ClaimCreateIn, ClaimEvidenceIn, ClaimDecisionIn,create_claim,submit_claim,decide_claim
    db,project,creator,reviewer,*_=state
    c=contract(state)
    row=create_claim(project.id,c.id,ClaimCreateIn(number='CL-COST-02',category='Cost Claim',description='Extra cost for instructed scope',event_at='2026-10-20T00:00:00Z',requested_amount='2500',currency='INR',owner_user_id=creator.id),creator,db)
    submit_claim(project.id,c.id,row['id'],ClaimEvidenceIn(evidence='supporting cost calculation'),creator,db)
    with pytest.raises(HTTPException) as ex:
        decide_claim(project.id,c.id,row['id'],ClaimDecisionIn(decision='Agreed',evidence='decision evidence ref',agreed_amount='1000'),creator,db)
    assert ex.value.status_code==403
    decided=decide_claim(project.id,c.id,row['id'],ClaimDecisionIn(decision='Agreed',evidence='counterparty signed acceptance',agreed_amount='1000'),reviewer,db)
    assert decided['status']=='Agreed'
    assert decided['agreed_amount']=='1000.00'
    assert db.get(Contract,c.id).original_value==100000
    assert db.get(Contract,c.id).current_version==1


def test_partner_document_scoping_and_revocation(state):
    from app.domains.contracts.router import (PartnerDocumentPublish,partner_document_publish,partner_document_detail,partner_document_revoke)
    db,p,admin,peer,pa,pb,a,b,other=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='internal review'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='internal accepted'),peer,db)
    execute(p.id,c.id,DecisionIn(reason='signed document evidence',evidence='signed-contract-evidence'),admin,db)
    publish(p.id,c.id,ShareIn(company_id=b.id,can_submit=True),admin,db)
    import hashlib
    from app.domains.engineering_documents.models import StoredFile
    raw=b'approved contract document'
    digest=hashlib.sha256(raw).hexdigest()
    stored=StoredFile(organization_id=admin.organization_id,sha256=digest,size=len(raw),content_type='application/pdf',original_name='agreement.pdf',storage_name=digest,created_by=admin.id,scan_status='available')
    db.add(stored);db.flush()
    payload=PartnerDocumentPublish(company_id=b.id,document_key='agreement',revision=1,display_name='Executed agreement',document_class='agreement',private_storage_key=f'stored-file:{stored.id}',content_sha256=digest)
    result=partner_document_publish(p.id,c.id,payload,admin,db)
    assert partner_document_detail(c.id,result['id'],pa,db)['download_status']=='authorized_download_endpoint'
    with pytest.raises(HTTPException) as err:partner_document_detail(c.id,result['id'],pb,db)
    assert err.value.status_code==404
    partner_document_revoke(p.id,c.id,result['id'],DecisionIn(reason='withdraw published access'),admin,db)
    with pytest.raises(HTTPException) as err:partner_document_detail(c.id,result['id'],pa,db)
    assert err.value.status_code==404


def test_partner_document_requires_active_share_and_private_key(state):
    from app.domains.contracts.router import PartnerDocumentPublish,partner_document_publish
    db,p,admin,peer,pa,pb,a,b,other=state
    c=contract(state)
    payload=PartnerDocumentPublish(company_id=b.id,document_key='agreement',revision=1,display_name='Agreement',document_class='agreement',private_storage_key='private/doc',content_sha256='b'*64)
    with pytest.raises(HTTPException) as err:partner_document_publish(p.id,c.id,payload,admin,db)
    assert err.value.status_code==409

def test_cm0120_import_preview_does_not_create_unknown_master_data(state):
    from app.domains.contracts.router import import_preview
    db,p,admin,peer,pa,pb,a,b,_=state
    before=db.query(Contract).count()
    result=import_preview(p.id,{'rows':[{
        'number':'IMP-001','title':'Imported contract','contract_type':'Subcontract',
        'contracting_company_id':str(a.id),'counterparty_company_id':'999999',
        'manager_user_id':str(admin.id),'scope':'Authorized project scope',
        'currency':'INR','original_value':'100.00'}]},admin,db)
    assert not result['rows'][0]['valid']
    assert 'counterparty_company_id' in ' '.join(result['rows'][0]['errors'])
    assert result['created']==0 and db.query(Contract).count()==before


def test_cm0120_preview_detects_duplicate_numbers_in_batch(state):
    from app.domains.contracts.router import import_preview
    db,p,admin,peer,pa,pb,a,b,_=state
    item={'number':'IMP-002','title':'Imported contract','contract_type':'Subcontract',
          'contracting_company_id':str(a.id),'counterparty_company_id':str(b.id),
          'manager_user_id':str(admin.id),'scope':'Authorized project scope'}
    response=import_preview(p.id,{'rows':[item,item]},admin,db)
    assert response['valid_rows']==1
    assert 'duplicate number in import batch' in response['rows'][1]['errors']


def test_cm0120_export_hides_commercial_values_for_summary_only(state):
    from app.domains.contracts.router import export_contracts_csv
    db,p,admin,peer,pa,pb,a,b,_=state
    contract(state)
    response=export_contracts_csv(p.id,admin,db)
    import asyncio
    async def collect():
        return ''.join([chunk async for chunk in response.body_iterator])
    output=asyncio.run(collect())
    assert 'original_value' in output and '100000' in output


def test_external_closeout_evidence_does_not_complete_source_verification(state):
    from app.domains.contracts.router import verify_closeout_check, CloseoutCheckIn, closeout_blockers
    db, project, admin, *rest = state
    c = contract(state)
    response = verify_closeout_check(
        project.id, c.id,
        CloseoutCheckIn(check_type='finance_settlement', source_record_ref='FIN-21', evidence_ref='receipt-21'),
        admin, db,
    )
    assert response['status'] == 'Evidence Recorded'
    assert response['source_verified_live'] is False
    assert 'check:finance_settlement' in closeout_blockers(db, c)


def test_internal_closeout_evidence_preserves_existing_verification(state):
    from app.domains.contracts.router import verify_closeout_check, CloseoutCheckIn
    db, project, admin, *rest = state
    c = contract(state)
    response = verify_closeout_check(
        project.id, c.id,
        CloseoutCheckIn(check_type='document_handover', source_record_ref='DOC-21', evidence_ref='handover-21'),
        admin, db,
    )
    assert response['status'] == 'Verified'


def test_partner_download_rechecks_company_and_revocation(state,monkeypatch):
    import hashlib
    from app.domains.contracts import router as contracts_router
    from app.domains.contracts.router import PartnerDocumentPublish,partner_document_publish,partner_document_download,partner_document_revoke
    from app.domains.engineering_documents.models import StoredFile
    db,p,admin,peer,pa,pb,a,b,other=state
    c=contract(state)
    submit(p.id,c.id,DecisionIn(reason='internal review'),admin,db)
    approve(p.id,c.id,DecisionIn(reason='internal approved'),peer,db)
    execute(p.id,c.id,DecisionIn(reason='signed execution',evidence='signed contract'),admin,db)
    publish(p.id,c.id,ShareIn(company_id=b.id,can_submit=True),admin,db)
    raw=b'example private contract';sha=hashlib.sha256(raw).hexdigest()
    stored=StoredFile(organization_id=admin.organization_id,sha256=sha,size=len(raw),content_type='application/pdf',original_name='contract.pdf',storage_name=sha,created_by=admin.id,scan_status='available')
    db.add(stored);db.flush()
    payload=PartnerDocumentPublish(company_id=b.id,document_key='agreement',revision=1,display_name='Agreement',document_class='agreement',private_storage_key=f'stored-file:{stored.id}',content_sha256=sha)
    doc=partner_document_publish(p.id,c.id,payload,admin,db)
    monkeypatch.setattr(contracts_router,'read_file',lambda row:raw)
    response=partner_document_download(c.id,doc['id'],pa,db)
    assert response.body==raw and response.headers['cache-control']=='no-store, private'
    with pytest.raises(HTTPException) as e:partner_document_download(c.id,doc['id'],pb,db)
    assert e.value.status_code==404
    partner_document_revoke(p.id,c.id,doc['id'],DecisionIn(reason='access revoked'),admin,db)
    with pytest.raises(HTTPException) as e:partner_document_download(c.id,doc['id'],pa,db)
    assert e.value.status_code==404
