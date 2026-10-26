from types import SimpleNamespace as R
from app.domains.stores_inventory.phase8_financial_reconciliation import financial_reference_rows


def test_explicit_contract_reference_does_not_establish_recovery():
    req = R(id=1, status='Approved', requirement_line_id=12, work_package_id=5,
            planning_wbs_id=4, item_id=3, base_unit='EA')
    handover = R(id=2, material_request_id=1, stock_posting_line_id=8, status='Acknowledged')
    returned = R(id=7, handover_id=2, status='Accepted', stock_posting_id=None)
    link = R(material_request_id=1, contract_id=10, obligation_id=11)
    row = financial_reference_rows([req], [handover], [returned], [link])[0]
    assert row['contract_reference_only'] is True
    assert row['recovery_authorized'] is False and row['finance_posting_created'] is False
    assert row['handovers'][0]['return_posting_id'] is None


def test_missing_contract_and_handover_are_blocked():
    req = R(id=1, status='Pending', requirement_line_id=None, work_package_id=5,
            planning_wbs_id=None, item_id=3, base_unit='EA')
    row = financial_reference_rows([req], [], [], [])[0]
    assert row['readiness'] == 'Blocked'
    assert row['contract_id'] is None
    assert len(row['blockers']) >= 5


def test_scoped_window_does_not_invent_finance_values():
    assert financial_reference_rows([], [], [], []) == []
