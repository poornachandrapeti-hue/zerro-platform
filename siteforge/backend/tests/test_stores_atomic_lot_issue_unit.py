"""Focused safety checks; NOT a substitute for PostgreSQL concurrency tests."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory'

def test_issue_service_compiles():
    ast.parse((ROOT/'atomic_lot_issue.py').read_text())

def test_issues_disabled_by_default():
    text = (ROOT/'atomic_lot_issue.py').read_text()
    assert "os.getenv('STORES_ATOMIC_LOT_ISSUE_ENABLED', 'false')" in text
    assert 'raise HTTPException(503' in text

def test_ledger_and_allocation_in_one_service():
    content = (ROOT/'atomic_lot_issue.py').read_text()
    assert "stock._save(db, user, project, 'Issue'" in content
    assert 'StoresOutboundLotAllocation(' in content
    assert 'balance.on_hand = _amount(balance.on_hand) - amount' in content
    assert 'db.commit(' not in content

def test_fail_closed_checks_present():
    content = (ROOT/'atomic_lot_issue.py').read_text()
    for required in ('_require_full_coverage(', 'with_for_update()',
                     'quality hold', 'qa_quantity', 'balance.reserved',
                     'lot.expiry_date', 'accepted - issued + returned'):
        assert required.lower() in content.lower()
