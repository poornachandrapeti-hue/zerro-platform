import pytest
from app.domains.progress_monitoring.p5b3_reconciliation import (reconcile_certifications,command_center_status,ReconciliationError)

BASE=dict(organization_id=1,project_id=2,contract_id=3,boq_line_id=4,approved_boq_quantity='100',qa_accepted_quantity='60',authorized=True,server_revalidated=True)
def row(i=10,q='25',**kw):
    r=dict(organization_id=1,project_id=2,contract_id=3,boq_line_id=4,certification_id=i,quantity=q,status='Posted',unit='m3',server_authorized=True)
    r.update(kw);return r

def check(rows,**kw):return reconcile_certifications(**(BASE|kw),certification_rows=rows)
def test_empty(): assert check([])['remaining_candidate_quantity']=='60'
def test_certified(): assert check([row()])['remaining_candidate_quantity']=='35'
def test_decimal():assert check([row(q='0.25')])['previously_certified_quantity']=='0.25'
def test_two_rows(): assert check([row(),row(11,'10')])['remaining_candidate_quantity']=='25'
def test_not_billable():assert check([row()])['billing_certified'] is False
@pytest.mark.parametrize('rows',[[row(),row()],[row(status='Draft')],[row(revoked=True)],[row(project_id=9)],[row(server_authorized=False)],[row(quantity='NaN')],[row(quantity='-1')],[row(quantity='70')],[row(unit='')],[row(certification_id=None)]])
def test_rejected_rows(rows):
    with pytest.raises(ReconciliationError):check(rows)
def test_untrusted():
    with pytest.raises(ReconciliationError):check([],authorized=False)
def test_qa_exceeds_boq():
    with pytest.raises(ReconciliationError):check([],qa_accepted_quantity='101')
def test_dashboard():
    d=command_center_status(organization_id=1,project_id=2,published_snapshot=dict(organization_id=1,project_id=2,status='Published',publication_persisted=True,snapshot_id=5),reconciliation=check([]),authorized=True,evidence_current=True)
    assert d['earned_progress'] is None and d['billing_certified'] is False
def test_dashboard_unpublished():
    with pytest.raises(ReconciliationError):command_center_status(organization_id=1,project_id=2,published_snapshot=dict(organization_id=1,project_id=2,status='Draft',publication_persisted=True),reconciliation=check([]),authorized=True,evidence_current=True)
