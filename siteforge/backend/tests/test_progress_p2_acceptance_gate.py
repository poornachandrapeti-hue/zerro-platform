from copy import deepcopy
from app.domains.progress_monitoring.p2_acceptance_gate import evaluate_qa_acceptance


BASE = dict(organization_id=1, project_id=2, activity_id=3, report_id=10,
            status='Approved', verified_quantity='12.000', verifier_id=7)
INS = dict(organization_id=1, project_id=2, activity_id=3, construction_report_id=10,
           inspection_id='QA-100', status='Approved', accepted_quantity='4.000',
           reviewer_id=8, inspection_evidence_id='DOC-5')


def result(c=None, docs=None):
    return evaluate_qa_acceptance(c if c is not None else deepcopy(BASE),
                                  docs if docs is not None else [deepcopy(INS)],
                                  organization_id=1, project_id=2)


def test_valid_independently_approved_qa_evidence():
    r = result()
    assert r['eligible'] and r['accepted_quantity'] == '4.000'
    assert r['accepted_percent'] is None and not r['billing_certified']


def test_construction_approval_alone_not_qa_acceptance():
    assert not result(docs=[])['eligible']


def test_pending_or_rejected_qa_cannot_earn_acceptance():
    for status in ('Pending', 'Rejected'):
        assert not result(docs=[dict(INS, status=status)])['eligible']


def test_mismatched_project_or_activity_rejected():
    for field in ('organization_id', 'project_id', 'activity_id', 'construction_report_id'):
        assert not result(docs=[dict(INS, **{field:999})])['eligible']


def test_quantity_never_exceeds_verified():
    assert not result(docs=[dict(INS, accepted_quantity='13')])['eligible']


def test_duplicate_inspections_rejected():
    assert not result(docs=[INS, INS])['eligible']


def test_independent_review_required():
    assert not result(docs=[dict(INS, reviewer_id=7)])['eligible']


def test_missing_evidence_rejected():
    assert not result(docs=[dict(INS, inspection_evidence_id=None)])['eligible']


def test_bad_numeric_values_fail_closed():
    for qty in ('nan', '-1', 'Infinity', 'oops', None, True):
        assert not result(docs=[dict(INS, accepted_quantity=qty)])['eligible']


def test_multiple_distinct_accepted_inspections_add_without_certification():
    second = dict(INS, inspection_id='QA-101', accepted_quantity='3.0')
    r = result(docs=[INS, second])
    assert r['eligible'] and r['accepted_quantity'] == '7.000' and not r['billing_certified']


def test_unverified_report_rejected():
    assert not result(c=dict(BASE, status='Pending Review'))['eligible']
