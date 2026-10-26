from types import SimpleNamespace
from unittest.mock import MagicMock
from app.domains.contracts.closeout_source_checks import quality_blockers

def _query_with_rows(rows):
    q = MagicMock()
    q.filter_by.return_value.filter.return_value.all.return_value = rows
    q.filter_by.return_value.filter.return_value.filter.return_value.all.return_value = rows
    return q


def test_project_quality_blockers_do_not_certify_acceptance():
    db = MagicMock()
    db.query.side_effect = [_query_with_rows([SimpleNamespace(id=1, status='Active')]),
                            _query_with_rows([SimpleNamespace(id=2, status='Open')]),
                            _query_with_rows([SimpleNamespace(id=3, status='Pending Verification')])]
    result = quality_blockers(db, 12, 34)
    assert result['acceptance_verified'] is False
    assert result['blocker_count'] == 3
    assert {r['source'] for r in result['blockers']} == {'quality_holds','quality_punches','quality_ncrs'}


def test_absence_of_blockers_never_means_qa_acceptance():
    db = MagicMock()
    db.query.side_effect = [_query_with_rows([]), _query_with_rows([]), _query_with_rows([])]
    result = quality_blockers(db, 12, 34)
    assert result['blocker_count'] == 0
    assert result['acceptance_verified'] is False
