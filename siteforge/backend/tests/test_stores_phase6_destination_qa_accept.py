from types import SimpleNamespace as S
from pydantic import ValidationError
import pytest
from app.domains.stores_inventory.transfer_qa_reconciliation import (
    reconcile_transfer_pair, DestinationQAAcceptIn, DestinationQAReviewIn,
)

def sample():
    transfer = S(id=1, quantity=5, item_id=17, project_id=8, organization_id=10,
                 source_warehouse_id=11, destination_warehouse_id=12)
    lineage = S(id=2, status='Posted', source_posting_id=21,
                destination_posting_id=22, source_receipt_lot_id=30)
    dest = S(lineage_id=2, source_receipt_lot_id=30, item_id=17,
             destination_warehouse_id=12, quantity=5, status='QAAcceptedPendingActivation')
    out = S(id=21, kind='TransferOut', status='Posted', source_posting_id=None,
            project_id=8, organization_id=10, warehouse_id=11)
    incoming = S(id=22, kind='TransferIn', status='Posted', source_posting_id=21,
                 project_id=8, organization_id=10, warehouse_id=12)
    a = S(id=50, quantity=5, item_id=17, unit='Nos', source_line_id=None)
    b = S(id=51, quantity=5, item_id=17, unit='Nos', source_line_id=50)
    return transfer, lineage, dest, out, incoming, [a], [b]

def test_accepted_qa_remains_unavailable():
    r = reconcile_transfer_pair(*sample())
    assert r['balanced'] and r['destination_qa_review_complete']
    assert not r['available_for_issue']
    assert 'TRANSFER_DERIVED_LOT_ISSUE_NOT_SUPPORTED' in r['availability_blockers']

def test_missing_lineage_is_rejected_even_when_postings_exist():
    rows = list(sample()); rows[1] = None
    r = reconcile_transfer_pair(*rows)
    assert not r['balanced']

def test_qa_accept_needs_evidence_and_hold_cannot_accept():
    with pytest.raises(ValidationError):
        DestinationQAAcceptIn(evidence='')
    with pytest.raises(ValidationError):
        DestinationQAReviewIn(decision='Accepted', evidence='approved')
