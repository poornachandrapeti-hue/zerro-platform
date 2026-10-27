from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace as S
import pytest
from app.domains.progress_monitoring.p5b2_canonical_readbacks import (
    SourceAuthorityError, published_report_readback, contract_boq_readback)

class Result:
    def __init__(self, values): self.values=values
    def scalar_one_or_none(self): return self.values
    def scalars(self): return self
    def all(self): return self.values
class DB:
    def __init__(self,*values): self.values=iter(values)
    def execute(self,query): return Result(next(self.values))

NOW=datetime.now(timezone.utc)
def report(**kw): return S(id=5,organization_id=1,project_id=2,status='Published', published_at=NOW, snapshot={'x':1},source_cutoff=NOW,prepared_by=7,approver_id=8, report_number='P1', revision=1,**kw)
def event(action='publish'): return S(event=action,id=1)
def test_published_report_is_not_billable():
    result=published_report_readback(DB(report(),[event()]),organization_id=1,project_id=2,report_id=5,authorized=True)
    assert result['publication_persisted'] and not result['commercial_review_eligible']
def test_missing_publication_audit_fails():
    with pytest.raises(SourceAuthorityError): published_report_readback(DB(report(),[]),organization_id=1,project_id=2,report_id=5,authorized=True)
def test_unpublished_fails():
    with pytest.raises(SourceAuthorityError): published_report_readback(DB(S(status='Approved',id=5,published_at=None,snapshot={}),[]),organization_id=1,project_id=2,report_id=5,authorized=True)
def test_missing_project_report_fails():
    with pytest.raises(SourceAuthorityError): published_report_readback(DB(None),organization_id=1,project_id=2,report_id=5,authorized=True)
def test_denied_before_db():
    with pytest.raises(SourceAuthorityError): published_report_readback(DB(),organization_id=1,project_id=2,report_id=5,authorized=False)
def test_self_approval_fails():
    r=report();r.approver_id=7
    with pytest.raises(SourceAuthorityError): published_report_readback(DB(r,[event()]),organization_id=1,project_id=2,report_id=5,authorized=True)
def contract(): return S(id=6,published_version=3,lifecycle='Active')
def version(): return S(id=11,contract_id=6,version=3,state='Published')
def boq(): return S(id=12,contract_id=6,version_id=11, code='BOQ-1',unit='m3',quantity=Decimal('100.5000'),currency='INR')
def cargs(): return dict(organization_id=1,project_id=2,contract_id=6,boq_line_id=12,authorized=True)
def test_published_contract_line_is_uncertified():
    result=contract_boq_readback(DB(contract(),version(),boq()),**cargs())
    assert result['approved_quantity']=='100.5000' and result['previously_certified_quantity'] is None
    assert result['commercial_review_eligible'] is False
def test_wrong_contract_line_fails():
    with pytest.raises(SourceAuthorityError): contract_boq_readback(DB(contract(),version(),None),**cargs())
def test_no_published_version_fails():
    c=contract();c.published_version=None
    with pytest.raises(SourceAuthorityError): contract_boq_readback(DB(c),**cargs())
def test_unapproved_contract_version_fails():
    v=version();v.state='Draft'
    with pytest.raises(SourceAuthorityError): contract_boq_readback(DB(contract(),v),**cargs())
def test_contract_scope_not_found_fails():
    with pytest.raises(SourceAuthorityError): contract_boq_readback(DB(None),**cargs())
def test_invalid_ids_fail():
    args=cargs();args['project_id']=0
    with pytest.raises(SourceAuthorityError): contract_boq_readback(DB(),**args)
def test_commercial_denial_prevents_db_read():
    args=cargs();args['authorized']=False
    with pytest.raises(SourceAuthorityError): contract_boq_readback(DB(),**args)
