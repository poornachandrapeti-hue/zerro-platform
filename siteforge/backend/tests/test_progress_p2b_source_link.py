from types import SimpleNamespace as R
from app.domains.progress_monitoring.p2b_source_link import verify_source_link


def records():
    report = R(id=1, organization_id=2, project_id=3, status='Approved')
    line = R(id=4, report_id=1, activity_id=5, quantity='10', rework=False, reverses_line_id=None)
    inspection = R(id=6, organization_id=2, project_id=3, activity_id=5,
                   status='Approved', outcome='Partially Accepted', accepted_quantity='4')
    link = {'report_id': 1, 'progress_line_id': 4, 'inspection_request_id': 6,
            'binding_verified_by': 7, 'binding_evidence_ref': 'review/7'}
    return dict(report=report, line=line, inspection=inspection, link=link,
                organization_id=2, project_id=3)


def test_valid_source_link_is_not_billing_or_progress_certification():
    result = verify_source_link(**records())
    assert result['linked'] and result['accepted_quantity'] == '4'
    assert not result['progress_earned'] and not result['billing_certified']


def test_unapproved_construction_rejected():
    v = records(); v['report'].status = 'Pending Review'
    assert not verify_source_link(**v)['linked']


def test_unapproved_qa_rejected():
    v = records(); v['inspection'].status = 'Pending Review'
    assert not verify_source_link(**v)['linked']


def test_rejected_outcome_rejected():
    v = records(); v['inspection'].outcome = 'Rejected'
    assert not verify_source_link(**v)['linked']


def test_cross_project_rejected():
    v = records(); v['inspection'].project_id = 99
    assert not verify_source_link(**v)['linked']


def test_activity_mismatch_rejected():
    v = records(); v['line'].activity_id = 88
    assert not verify_source_link(**v)['linked']


def test_unverified_binding_rejected():
    v = records(); v['link']['binding_evidence_ref'] = ''
    assert not verify_source_link(**v)['linked']


def test_missing_binding_rejected():
    v = records(); v['link'] = None
    assert not verify_source_link(**v)['linked']


def test_excess_quantity_rejected():
    v = records(); v['inspection'].accepted_quantity = '12'
    assert not verify_source_link(**v)['linked']


def test_negative_quantity_rejected():
    v = records(); v['inspection'].accepted_quantity = '-1'
    assert not verify_source_link(**v)['linked']


def test_reversal_rejected():
    v = records(); v['line'].reverses_line_id = 2
    assert not verify_source_link(**v)['linked']


def test_nan_rejected():
    v = records(); v['inspection'].accepted_quantity = 'NaN'
    assert not verify_source_link(**v)['linked']
