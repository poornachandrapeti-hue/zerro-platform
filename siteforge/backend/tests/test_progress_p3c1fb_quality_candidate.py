from types import SimpleNamespace as R
import pytest
from app.domains.progress_monitoring.p3c1fb_quality_candidate import inspect_quality_candidate, read_quality_candidate


def req(**changes):
    payload = dict(id=12, organization_id=1, project_id=2, activity_id=3,
        status='Approved', outcome='Accepted', accepted_quantity='7.5',
        requester_id=51, inspector_id=52, version=2)
    payload.update(changes)
    return R(**payload)


def call(request=None, results=None):
    return inspect_quality_candidate(request=request or req(), results=results or [],
                                     organization_id=1, project_id=2, activity_id=3)


def test_approved_candidate_stays_non_authoritative():
    r = call()
    assert r['candidate_only'] and not r['authority_verified']
    assert not r['published'] and not r['billing_certified']
    assert 'physical_measurement_evidence_not_authenticated' in r['blockers']

@pytest.mark.parametrize('field,value', [('organization_id',9),('project_id',9),('activity_id',9)])
def test_scope_rejected(field,value):
    with pytest.raises(PermissionError): call(req(**{field:value}))

@pytest.mark.parametrize('field,value,code', [
    ('status','Draft','qa_request_not_approved'),
    ('outcome','Rejected','qa_outcome_not_accepted'),
    ('accepted_quantity',None,'qa_accepted_quantity_missing_or_invalid'),
    ('accepted_quantity','NaN','qa_accepted_quantity_missing_or_invalid'),
    ('inspector_id',51,'qa_inspector_not_independent'),
])
def test_invalid_source_blocks(field,value,code):
    assert code in call(req(**{field:value}))['blockers']

def test_failed_checklist_blocks():
    assert 'failed_quality_checklist_item' in call(results=[R(result='Fail')])['blockers']

def test_readback_requires_server_authorization():
    with pytest.raises(PermissionError):
        read_quality_candidate(session=None, inspection_id=12, organization_id=1,
                               project_id=2, activity_id=3)

def test_accepted_qty_preserves_decimal():
    assert call()['accepted_quantity']=='7.5'
