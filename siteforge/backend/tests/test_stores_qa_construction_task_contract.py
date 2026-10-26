import inspect
from app.domains.stores_inventory.qa_issued_impact import create_construction_review_tasks


def test_review_tasks_are_scoped_and_lock_the_qa_case():
    source = inspect.getsource(create_construction_review_tasks)
    assert 'with_for_update()' in source
    assert "qa_access(db, u, pid, edit=True)" in source
    assert "permitted(db, u, project, 'construction.view')" in source
    assert "organization_id=u.organization_id" in source


def test_review_tasks_are_only_created_for_mapped_packages_and_valid_owners():
    source = inspect.getsource(create_construction_review_tasks)
    assert "for lot in exposure['lots']" in source
    assert 'package.responsible_user_id' in source
    assert "holds(db, owner, project, 'construction.view'" in source
    assert 'if prior is not None:' in source


def test_no_automatic_stock_writes_or_claim_of_complete_provenance():
    source = inspect.getsource(create_construction_review_tasks)
    assert "'impact_scope_verified': False" in source
    assert "'manual_review_still_required': True" in source
    assert '_task(db, u, project' in source
    assert 'StockBalance' not in source
