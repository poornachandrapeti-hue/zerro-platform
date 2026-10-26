from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.material_returns import ensure_return_not_consumed

@pytest.mark.parametrize('issued,prior,proposed,usage', [
    ('10','0','4','6'), ('10','2','3','5'), ('7.000','1.000','3.000','3.000')])
def test_return_can_use_exact_remainder(issued,prior,proposed,usage):
    ensure_return_not_consumed(issued,prior,proposed,usage)

@pytest.mark.parametrize('issued,prior,proposed,usage', [
    ('10','0','5','6'), ('10','2','3','6'), ('5','0','1','NaN'), ('5','0','-1','0')])
def test_return_blocked_when_reserved_for_usage_or_invalid(issued,prior,proposed,usage):
    with pytest.raises(HTTPException) as exc:
        ensure_return_not_consumed(issued,prior,proposed,usage)
    assert exc.value.status_code == 409


def test_qa_queue_is_separately_authorized_and_pending_only():
    from app.domains.stores_inventory import construction_material_usage as module
    import inspect
    src=inspect.getsource(module.list_usage_qa_queue)
    assert "'quality.edit'" in src
    assert "status == 'Pending QA'" in src
    assert 'submitted_by != u.id' in src


def test_return_posting_checks_usage_before_stock_save():
    from app.domains.stores_inventory import material_returns as module
    import inspect
    src=inspect.getsource(module.post_qa_accepted_return)
    assert src.index('ensure_return_not_consumed(') < src.index('stock._save(')
    assert 'with_for_update()' in src
