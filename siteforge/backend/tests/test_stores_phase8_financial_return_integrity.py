from types import SimpleNamespace as R
from app.domains.stores_inventory.phase8_financial_reconciliation import financial_reference_rows


def req():
    return R(id=1, status='Approved', requirement_line_id=10, work_package_id=2,
             planning_wbs_id=3, item_id=4, base_unit='KG')


def handover():
    return R(id=8, material_request_id=1, stock_posting_line_id=21, status='Acknowledged')


def build(returns):
    return financial_reference_rows([req()], [handover()], returns, [])[0]


def test_qa_accepted_not_posted_does_not_create_finance_entitlement():
    row = build([R(id=9, handover_id=8, status='QA Accepted', stock_posting_id=None)])
    assert row['return_exceptions'][0]['code'] == 'return_not_posted'
    assert row['handovers'][0]['return_posting_id'] is None
    assert row['valuation_verified'] is False
    assert row['finance_posting_created'] is False


def test_return_posting_is_only_unverified_reference():
    row = build([R(id=9, handover_id=8, status='Stock Posted', stock_posting_id=55)])
    assert row['return_exceptions'][0]['code'] == 'posted_return_ledger_unverified'
    assert row['handovers'][0]['return_posting_id'] == 55
    assert row['recovery_authorized'] is False


def test_duplicate_return_refs_not_silently_collapsed():
    row = build([R(id=9, handover_id=8, status='Submitted', stock_posting_id=None),
                 R(id=10, handover_id=8, status='QA Accepted', stock_posting_id=None)])
    assert row['handovers'][0]['return_reference_count'] == 2
    assert row['handovers'][0]['return_id'] is None
    assert any(e['code'] == 'duplicate_return_reference' for e in row['return_exceptions'])


def test_other_handover_return_is_not_attributed():
    row = build([R(id=10, handover_id=999, status='Stock Posted', stock_posting_id=78)])
    assert row['handovers'][0]['return_id'] is None
    assert row['return_exceptions'] == []


def test_no_return_still_requires_finance_authority():
    row = build([])
    assert row['return_exceptions'] == []
    assert row['readiness'] == 'Blocked'
