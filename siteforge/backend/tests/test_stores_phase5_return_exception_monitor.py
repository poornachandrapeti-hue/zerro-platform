from types import SimpleNamespace
from app.domains.stores_inventory.material_returns import summarize_return_exceptions


def _r(i, status, location=None, posting=None):
    return SimpleNamespace(id=i, handover_id=100+i, status=status,
                           return_location_id=location, stock_posting_id=posting)


def test_summary_classifies_custody_and_qa_states():
    rows = [_r(1, 'Submitted'), _r(2, 'Awaiting QA'), _r(3, 'QA Quarantined'),
            _r(4, 'QA Rejected'), _r(5, 'QA Accepted'),
            _r(6, 'QA Accepted', location=12), _r(7, 'Stock Posted', location=12, posting=60)]
    result = summarize_return_exceptions(rows)
    assert result['total_records'] == 7
    assert set(result['counts'].values()) == {1}
    assert result['ledger_reconciled'] is False
    assert result['physical_stock_readiness'] == 'Unverified'
    assert len(result['exceptions']) == 7


def test_unknown_status_never_assumed_ready():
    result = summarize_return_exceptions([_r(9, 'Mysterious')])
    assert result['exceptions'][0]['exception_code'] == 'unknown_state'
    assert sum(result['counts'].values()) == 0
    assert result['physical_stock_readiness'] == 'Unverified'


def test_posting_does_not_imply_verified_stock():
    result = summarize_return_exceptions([_r(1, 'QA Accepted', posting=55)])
    assert result['counts']['posted_unverified'] == 1
    assert not result['ledger_reconciled']
