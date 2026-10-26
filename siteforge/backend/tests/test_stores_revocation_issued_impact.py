from decimal import Decimal
from app.domains.stores_inventory.qa_issued_impact import summarize_exposure


def test_only_posted_mapped_movements_aggregated():
    result = summarize_exposure([(4, 'Issue', Decimal('2.5'), 11, 21),
                                 (4, 'Return', Decimal('1'), 12, 21),
                                 (4, 'Issue', Decimal('3'), 13, 22)])
    assert result[4]['attributed_issued'] == '5.5'
    assert result[4]['attributed_returned'] == '1'
    assert result[4]['posting_ids'] == [11, 12, 13]
    assert result[4]['work_package_ids'] == [21, 22]


def test_no_unmapped_inference_or_missing_work_package():
    assert summarize_exposure([]) == {}
    result = summarize_exposure([(3, 'Accept', 10, 8, None), (3, 'Issue', 2, 9, None)])
    assert result[3]['attributed_issued'] == '2'
    assert result[3]['work_package_ids'] == []


def test_api_is_read_only_and_scoped():
    import inspect
    from app.domains.stores_inventory.qa_issued_impact import revocation_impact
    source = inspect.getsource(revocation_impact)
    assert 'qa_access(db, u, pid)' in source
    assert 'organization_id=u.organization_id' in source
    assert "StockPosting.status == 'Posted'" in source
    assert 'db.commit(' not in source
