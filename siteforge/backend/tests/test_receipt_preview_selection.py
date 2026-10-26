import pytest
from app.domains.commercial_financials.receipt_preview_selection import select_receipt_previews


def test_selects_only_requested_receipt_costs_in_stable_order():
    rows = [{'receipt_line_id': 3}, {'receipt_line_id': 2}, {'receipt_line_id': 1}]
    assert [r['receipt_line_id'] for r in select_receipt_previews(rows, {1, 3})] == [1, 3]


def test_missing_receipt_remains_missing_for_incomplete_evidence_classification():
    assert select_receipt_previews([{'receipt_line_id': 1}], {1, 2}) == [{'receipt_line_id': 1}]


def test_duplicate_requested_receipt_is_rejected():
    with pytest.raises(ValueError, match='Ambiguous duplicate'):
        select_receipt_previews([{'receipt_line_id': 1, 'status': 'A'}, {'receipt_line_id': 1, 'status': 'B'}], {1})


@pytest.mark.parametrize('row', [None, {}, {'receipt_line_id': '2'}, {'receipt_line_id': 0}, {'receipt_line_id': True}])
def test_invalid_source_rows_fail_closed(row):
    with pytest.raises(ValueError):
        select_receipt_previews([row], {2})


def test_duplicate_unrelated_receipt_is_not_used_in_selected_movement():
    rows = [{'receipt_line_id': 1}, {'receipt_line_id': 2}, {'receipt_line_id': 2}]
    assert select_receipt_previews(rows, {1}) == [{'receipt_line_id': 1}]
