from check_finance_migrations import audit
from pathlib import Path

def test_current_revision_graph():
    result = audit(Path(__file__).resolve().parents[1] / 'migrations' / 'versions')
    assert result['ok'], result['errors']
    assert result['heads'] == ['finance_receipt_cost_allocations']

def test_rejects_missing_dependency(tmp_path):
    (tmp_path / 'a.py').write_text("revision='finance_inventory_costing_policy'\ndown_revision='ghost'\n")
    result = audit(tmp_path)
    assert not result['ok']
    assert any('missing parent' in e for e in result['errors'])

def test_rejects_duplicate_revision(tmp_path):
    (tmp_path / 'a.py').write_text("revision='same'\ndown_revision=None\n")
    (tmp_path / 'b.py').write_text("revision='same'\ndown_revision=None\n")
    assert not audit(tmp_path)['ok']
