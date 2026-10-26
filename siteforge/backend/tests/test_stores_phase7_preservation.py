from datetime import date
from app.domains.stores_inventory.preservation import risk_status, CONDITIONS

def test_preservation_risk_expiry_precedence():
    assert risk_status(date(2026,10,23), date(2026,10,20), 'Good', date(2026,10,24)) == 'Expired'

def test_preservation_quarantine():
    assert risk_status(date(2026,10,25), None, 'Quarantined', date(2026,10,24)) == 'Quarantined'

def test_preservation_overdue():
    assert risk_status(date(2026,10,23), None, 'Good', date(2026,10,24)) == 'Overdue'

def test_preservation_due_today():
    assert risk_status(date(2026,10,24), None, 'Good', date(2026,10,24)) == 'Due Today'

def test_preservation_is_not_inventory_posting():
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/preservation.py'
    text = source.read_text()
    assert 'StockBalance(' not in text and 'StockPosting(' not in text
    assert CONDITIONS == {'Good', 'Attention', 'Quarantined'}
