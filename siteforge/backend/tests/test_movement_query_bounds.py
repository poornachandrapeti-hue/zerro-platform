import pytest
from app.domains.commercial_financials.movement_query_bounds import (
    MAX_ISSUE_LOT_ALLOCATIONS, MAX_ACCEPTANCE_POSTINGS_PER_RECEIPT,
    require_complete_bounded_rows,
)


def test_allows_complete_empty_and_exact_boundary():
    assert require_complete_bounded_rows([], 2, 'a') == []
    assert require_complete_bounded_rows([1, 2], 2, 'a') == [1, 2]


def test_rejects_incomplete_bounded_evidence():
    with pytest.raises(ValueError, match='exceeds bounded evidence capacity'):
        require_complete_bounded_rows([1, 2, 3], 2, 'receipt postings')


@pytest.mark.parametrize('limit', [0, -1, True, None, '10'])
def test_rejects_invalid_limit(limit):
    with pytest.raises(ValueError, match='Invalid bounded evidence limit'):
        require_complete_bounded_rows([], limit, 'lot')


@pytest.mark.parametrize('rows', [None, {}, (x for x in range(3))])
def test_rejects_non_materialized_rows(rows):
    with pytest.raises(ValueError, match='Expected materialized evidence rows'):
        require_complete_bounded_rows(rows, 2, 'lot')


def test_explicit_upper_limits():
    assert MAX_ISSUE_LOT_ALLOCATIONS == 256
    assert MAX_ACCEPTANCE_POSTINGS_PER_RECEIPT == 512
