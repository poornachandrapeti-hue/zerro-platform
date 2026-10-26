from decimal import Decimal
from datetime import date, timedelta
from app.domains.stores_inventory.lot_balance_gate import summarize_ledger


def sample(**kw):
    args=dict(postings=[(10,"Accept",10),(11,"Issue",3),(12,"Return",1)],
        receipt_allocations=[(10,101,10)],
        outbound_allocations=[(11,101,"Issue",3),(12,101,"Return",1)],
        lot_qa={101:(Decimal(10), True, False)}, legacy_on_hand=8,
        legacy_reserved=0,current_lots=[(101,"L1",10,None)])
    args.update(kw)
    return summarize_ledger(**args)


def test_reconciled_never_authorizes_issue():
    result=sample()
    assert result["reconciliation_passed"] and result["provisional_lot_net"] == "8"
    assert result["issue_authorized"] is False and result["available_to_issue"] is None


def test_unattributed_outbound_blocks():
    result=sample(outbound_allocations=[(11,101,"Issue",2),(12,101,"Return",1)])
    assert "POSTING_LOT_COVERAGE_MISMATCH" in result["flags"]


def test_over_return_blocks():
    result=sample(postings=[(10,"Accept",10),(11,"Issue",3),(12,"Return",4)],
      outbound_allocations=[(11,101,"Issue",3),(12,101,"Return",4)],legacy_on_hand=11)
    assert "RETURN_EXCEEDS_ISSUES" in result["flags"]


def test_qa_stale_blocks():
    assert "STALE_OR_MISSING_QA" in sample(lot_qa={101:(10,False,False)})["flags"]


def test_legacy_balance_mismatch_blocks():
    assert "LEGACY_BALANCE_MISMATCH" in sample(legacy_on_hand=9)["flags"]


def test_expiry_blocks():
    assert "EXPIRED_LOT" in sample(current_lots=[(101,"L1",10,date.today()-timedelta(days=1))])["flags"]
