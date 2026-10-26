from copy import deepcopy
from app.domains.progress_monitoring.p3c1b_verification_attestation import validate_quantity_attestation


def records():
    baseline = dict(status='APPROVED_QUANTITY_FOUND',approved_planning_quantity='100',baseline_revision_id=9,construction_activity_id=14,unit='m3')
    construction = dict(status='SOURCE_READBACK_ONLY',organization_id=1,project_id=2,activity_id=14,construction_line_id=7,report_id=5,unit='m3',reported_quantity='80',qa_accepted_quantity='50')
    att = dict(verification_id=88,verification_reference='IV-01',verified_at='2026-10-27T00:00:00Z',source_revision=1,status='Approved',verifier_user_id=31,proposer_user_id=30,organization_id=1,project_id=2,activity_id=14,construction_line_id=7,report_id=5,baseline_revision_id=9,unit='m3',verified_quantity='65')
    return baseline,construction,att


def run(b=None,c=None,a=None):
    inputs=records()
    return validate_quantity_attestation(baseline=inputs[0] if b is None else b,construction=inputs[1] if c is None else c,attestation=inputs[2] if a is None else a)


def test_valid_nonpublishing():
    result=run()
    assert result['valid'] and result['construction_verified_quantity']=='65'
    assert result['earned_percent'] is None and result['billing_eligible_quantity'] is None and result['published'] is False


def test_absent_attestation_blocks():
    assert not run(a={})['valid']


def test_unapproved_baseline_blocks():
    b,c,a=records();b['status']='BASELINE_AMBIGUOUS';assert not run(b=b)['valid']


def test_unscoped_construction_blocks():
    b,c,a=records();c['status']='OTHER';assert not run(c=c)['valid']


def test_pending_verification_blocks():
    b,c,a=records();a['status']='Pending';assert not run(a=a)['valid']


def test_self_approval_blocks():
    b,c,a=records();a['verifier_user_id']=30;assert not run(a=a)['valid']


def test_wrong_project_blocks():
    b,c,a=records();a['project_id']=3;assert not run(a=a)['valid']


def test_wrong_line_blocks():
    b,c,a=records();a['construction_line_id']=77;assert not run(a=a)['valid']


def test_wrong_baseline_revision_blocks():
    b,c,a=records();a['baseline_revision_id']=12;assert not run(a=a)['valid']


def test_wrong_activity_mapping_blocks():
    b,c,a=records();b['construction_activity_id']=100;assert not run(b=b)['valid']


def test_wrong_unit_blocks():
    b,c,a=records();a['unit']='kg';assert not run(a=a)['valid']


def test_over_verified_blocks():
    b,c,a=records();a['verified_quantity']='81';assert not run(a=a)['valid']


def test_more_accepted_than_verified_blocks():
    b,c,a=records();a['verified_quantity']='45';assert not run(a=a)['valid']


def test_reported_above_baseline_blocks():
    b,c,a=records();c['reported_quantity']='101';assert not run(c=c)['valid']


def test_nonfinite_or_negative_blocks():
    b,c,a=records();a['verified_quantity']='NaN';assert not run(a=a)['valid']
    a['verified_quantity']='-1';assert not run(a=a)['valid']


def test_missing_provenance_blocks():
    b,c,a=records();a['verification_reference']='';assert not run(a=a)['valid']


def test_missing_verifier_blocks():
    b,c,a=records();a['verifier_user_id']=None;assert not run(a=a)['valid']


def test_qa_accepted_zero_allowed():
    b,c,a=records();c['qa_accepted_quantity']='0';assert run(c=c)['valid']
