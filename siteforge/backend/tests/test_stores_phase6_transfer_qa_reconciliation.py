from types import SimpleNamespace as S
from app.domains.stores_inventory.transfer_qa_reconciliation import reconcile_transfer_pair, DestinationQAReviewIn
import pytest
from pydantic import ValidationError

def fixtures():
    transfer = S(id=1, quantity=5, item_id=17, project_id=8, organization_id=10, source_warehouse_id=11, destination_warehouse_id=12)
    lineage = S(id=2, status='Posted', source_posting_id=21, destination_posting_id=22, source_receipt_lot_id=30)
    destination = S(lineage_id=2, source_receipt_lot_id=30, item_id=17, destination_warehouse_id=12, quantity=5, status='PostedPendingQA')
    out = S(id=21,kind='TransferOut',status='Posted',source_posting_id=None,project_id=8,organization_id=10,warehouse_id=11)
    incoming = S(id=22,kind='TransferIn',status='Posted',source_posting_id=21,project_id=8,organization_id=10,warehouse_id=12)
    out_line = S(id=50,quantity=5,item_id=17,unit='Nos',source_line_id=None)
    in_line = S(id=51,quantity=5,item_id=17,unit='Nos',source_line_id=50)
    return transfer,lineage,destination,out,incoming,[out_line],[in_line]

def test_paired_posting_balanced_but_not_qa_released():
    r = reconcile_transfer_pair(*fixtures())
    assert r['balanced'] is True and r['available_for_issue'] is False

def test_pair_rejects_wrong_source_link():
    rows = fixtures(); rows[4].source_posting_id=999
    assert 'TRANSFER_POSTING_LINK_MISMATCH' in reconcile_transfer_pair(*rows)['blockers']

def test_pair_rejects_mismatched_quantity():
    rows = fixtures(); rows[6][0].quantity=4
    assert 'TRANSFER_POSTING_QUANTITY_OR_ITEM_MISMATCH' in reconcile_transfer_pair(*rows)['blockers']

def test_pair_rejects_wrong_project():
    rows = fixtures(); rows[4].project_id=99
    assert 'TRANSFER_POSTING_SCOPE_MISMATCH' in reconcile_transfer_pair(*rows)['blockers']

def test_pair_rejects_missing_lineage():
    rows = list(fixtures()); rows[1]=None
    assert not reconcile_transfer_pair(*rows)['balanced']

def test_qa_hold_cannot_mark_accepted():
    with pytest.raises(ValidationError):
        DestinationQAReviewIn(decision='Accepted',evidence='approved')
