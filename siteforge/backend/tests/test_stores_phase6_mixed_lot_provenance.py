from decimal import Decimal
from app.domains.stores_inventory.mixed_lot_allocation import summarize_provenance


def test_grn_only_balance_diagnostic():
    result = summarize_provenance([('Accept', 10, 1, None, None), ('Issue', 2, 2, None, None)], [], 8, unit='EA')
    assert result['ledger_reconciles'] is True
    assert result['calculated_on_hand'] == '8'
    assert result['issuable'] is False


def test_transferred_stock_never_becomes_reservable():
    result = summarize_provenance([('TransferIn', 5, 50, 49, 100)], [(50, 'QAAcceptedPendingActivation', 5, 'TRANS-5')], 5, unit='EA')
    assert result['ledger_reconciles'] is True
    assert 'TRANSFER_LOT_ALLOCATION_AND_ISSUE_NOT_IMPLEMENTED' in result['blockers']
    assert result['reservable'] is False


def test_transfer_without_lineage_is_blocked():
    result = summarize_provenance([('TransferIn', 5, 50, 49, 100)], [], 5, unit='EA')
    assert 'TRANSFER_DESTINATION_PROVENANCE_MISSING' in result['blockers']
    assert result['ledger_reconciles'] is False


def test_qa_held_transfer_not_eligible():
    result = summarize_provenance([('TransferIn', 5, 50, 49, 100)], [(50, 'Quarantined', 5, 'TRANS-5')], 5, unit='EA')
    assert 'TRANSFER_LOT_NOT_QA_ACCEPTED' in result['blockers']


def test_bad_aggregate_and_orphan_qa_detected():
    result = summarize_provenance([('Accept', Decimal('7'), 1, None, None)], [(75, 'QAAcceptedPendingActivation', 3, 'ORPHAN')], 8, unit='EA')
    assert 'LEDGER_BALANCE_MISMATCH' in result['blockers']
    assert 'ORPHAN_DESTINATION_LOT_OR_INVALID_TRANSFER_IN' in result['blockers']


def test_unknown_movement_fails_closed():
    result = summarize_provenance([('Adjustment', 4, 1, None, None)], [], 0, unit='EA')
    assert 'UNSUPPORTED_POSTING_KIND' in result['blockers']
    assert result['issuable'] is False
