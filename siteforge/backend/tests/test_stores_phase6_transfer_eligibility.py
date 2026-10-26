from types import SimpleNamespace
from app.domains.stores_inventory.transfer_lot_eligibility import _eligibility


def transfer():
    return SimpleNamespace(id=8, project_id=3, destination_warehouse_id=5, item_id=9)


def test_accepted_lot_still_cannot_issue():
    lot = SimpleNamespace(id=4, status='QAAcceptedPendingActivation', quantity=7)
    result = _eligibility(transfer(), lot, {'balanced': True, 'blockers': []})
    assert result['qa_evidence_accepted'] is True
    assert result['reservable'] is False and result['issuable'] is False
    assert 'TRANSFER_DERIVED_ISSUE_POSTING_NOT_IMPLEMENTED' in result['blockers']


def test_unaccepted_lot_fails_closed():
    lot = SimpleNamespace(id=4, status='Quarantined', quantity=7)
    result = _eligibility(transfer(), lot, {'balanced': False, 'blockers': ['TRANSFER_POSTING_LINK_MISMATCH']})
    assert 'DESTINATION_QA_NOT_ACCEPTED' in result['blockers']
    assert 'TRANSFER_POSTING_LINK_MISMATCH' in result['blockers']
    assert result['physical_stock_readiness'] == 'Unverified'
