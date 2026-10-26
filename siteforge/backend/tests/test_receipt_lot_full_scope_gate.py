"""Protect the live reconciliation API against partial receipt-lot intake audits."""
from pathlib import Path

SOURCE = (Path(__file__).parents[1] / 'app/domains/commercial_financials/movement_receipt_api.py').read_text()


def test_intake_check_queries_all_receipt_lots_not_issue_subset():
    assert 'all_receipt_lots = (db.query(StoresReceiptLot)' in SOURCE
    assert 'StoresReceiptLot.goods_receipt_line_id.in_(receipt_ids)' in SOURCE
    assert 'for lot in all_receipt_lots' in SOURCE


def test_all_lot_query_is_bounded_and_scoped():
    scope = SOURCE.split('all_receipt_lots = (db.query(StoresReceiptLot)',1)[1].split('for receipt_id in receipt_ids:',1)[0]
    assert 'StoresReceiptLot.organization_id == org' in scope
    assert 'StoresReceiptLot.project_id == pid' in scope
    assert '.limit(5001)' in scope
    assert "raise HTTPException(409, 'Receipt lot intake audit exceeds bounded capacity')" in scope
