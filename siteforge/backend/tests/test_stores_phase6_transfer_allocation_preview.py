from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.transfer_allocation_preview import preview_transfer_lot


def test_qa_accepted_does_not_activate_transfer_lot():
    result = preview_transfer_lot(lot_quantity='10', requested_quantity='3',
        qa_status='QAAcceptedPendingActivation', posted=True, reconciled=True)
    assert result['reservation_allowed'] is False
    assert result['issue_allowed'] is False
    assert 'TRANSFER_DERIVED_RESERVATION_ACTIVATION_PENDING' in result['blockers']
    assert 'LOT_LEVEL_AVAILABLE_QUANTITY_NOT_VERIFIED' in result['blockers']


def test_quarantine_and_missing_posting_explicit():
    result = preview_transfer_lot(lot_quantity='10', requested_quantity='2',
        qa_status='Quarantined', posted=False, reconciled=False)
    assert 'DESTINATION_QA_NOT_ACCEPTED' in result['blockers']
    assert 'PAIRED_TRANSFER_POSTING_MISSING' in result['blockers']
    assert 'WAREHOUSE_LEDGER_NOT_RECONCILED' in result['blockers']


def test_overdraw_and_invalid_quantities_rejected():
    result = preview_transfer_lot(lot_quantity=Decimal('10'), requested_quantity=Decimal('11'),
        qa_status='QAAcceptedPendingActivation', posted=True, reconciled=True, physical_available=10)
    assert 'REQUEST_EXCEEDS_TRANSFER_LOT' in result['blockers']
    assert 'INSUFFICIENT_UNRESERVED_LOT_QUANTITY' in result['blockers']
    for invalid in ('NaN', 'Infinity', '-1', '0'):
        with pytest.raises(HTTPException) as exc:
            preview_transfer_lot(lot_quantity='10', requested_quantity=invalid,
                qa_status='QAAcceptedPendingActivation', posted=True, reconciled=True)
        assert exc.value.status_code == 422
