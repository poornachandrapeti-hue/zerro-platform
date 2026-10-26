from types import SimpleNamespace as R
from app.domains.stores_inventory.phase8_cross_module_audit import cross_module_audit_rows


def req(**kwargs):
    values = dict(id=1, status='Approved', requirement_line_id=10,
                  work_package_id=20, planning_wbs_id=30, item_id=40, base_unit='EA')
    values.update(kwargs)
    return R(**values)


def test_no_evidence_does_not_create_financial_authority():
    row = cross_module_audit_rows([req()], [], [], [], [])[0]
    assert 'NO_ISSUE_HANDOVER' in row['exceptions']
    assert 'MISSING_CONTRACT_REFERENCE' in row['exceptions']
    assert not row['billing_certified'] and not row['finance_posting_created']


def test_verified_internal_usage_does_not_attest_external_inspection():
    h = R(id=11, material_request_id=1, stock_posting_line_id=50, status='Acknowledged')
    u = R(id=12, handover_id=11, status='Verified', item_id=40, work_package_id=20, unit='EA')
    row = cross_module_audit_rows([req()], [h], [], [u], [])[0]
    assert row['handovers'][0]['qa_verified_usage_ids'] == [12]
    assert 'EXTERNAL_ZERROR_INSPECTION_NOT_ATTESTED' in row['exceptions']
    assert not row['external_inspection_verified']


def test_scope_mismatch_and_return_without_posting_flagged():
    h = R(id=11, material_request_id=1, stock_posting_line_id=50, status='Acknowledged')
    u = R(id=12, handover_id=11, status='Pending QA', item_id=99, work_package_id=20, unit='EA')
    r = R(id=13, handover_id=11, status='Accepted', stock_posting_id=None)
    row = cross_module_audit_rows([req()], [h], [r], [u], [])[0]
    assert 'USAGE_SCOPE_MISMATCH' in row['exceptions']
    assert 'RETURN_POSTING_REVIEW_REQUIRED' in row['exceptions']
    assert 'USAGE_QA_REVIEW_REQUIRED' in row['exceptions']


def test_empty_window():
    assert cross_module_audit_rows([], [], [], [], []) == []
