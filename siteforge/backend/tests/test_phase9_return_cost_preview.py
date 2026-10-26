import pytest
from app.domains.commercial_financials.phase9_return_cost_preview import preview_issue_return_reversals


def preview(returns, **overrides):
    args = dict(issue_id=42, issued_quantity='3', original_issue_amount='1.00', currency='INR', returns=returns)
    args.update(overrides)
    return preview_issue_return_reversals(**args)


def test_split_returns_round_without_duplicating_cents():
    result = preview([{'return_id': 1, 'issue_id': 42, 'quantity': '1'},
                      {'return_id': 2, 'issue_id': 42, 'quantity': '1'},
                      {'return_id': 3, 'issue_id': 42, 'quantity': '1'}])
    assert [r['unposted_reversal_amount'] for r in result['returns']] == ['0.33', '0.34', '0.33']
    assert result['total_unposted_reversal_amount'] == '1.00'
    assert result['unreversed_issue_amount'] == '0.00'
    assert result['journal_posting_verified'] is False


def test_partial_return_uses_original_issue_cost_not_current_rate():
    result = preview([{'return_id': 9, 'issue_id': 42, 'quantity': '1.5'}], original_issue_amount='30.00')
    assert result['total_unposted_reversal_amount'] == '15.00'
    assert result['remaining_issued_quantity'] == '1.5'


@pytest.mark.parametrize('returns,kwargs', [
    ([{'return_id': 1, 'issue_id': 42, 'quantity': '4'}], {}),
    ([{'return_id': 1, 'issue_id': 42, 'quantity': '2'}, {'return_id': 2, 'issue_id': 42, 'quantity': '2'}], {}),
    ([{'return_id': 1, 'issue_id': 41, 'quantity': '1'}], {}),
    ([{'return_id': 1, 'issue_id': 42, 'quantity': '1'}, {'return_id': 1, 'issue_id': 42, 'quantity': '1'}], {}),
    ([{'return_id': True, 'issue_id': 42, 'quantity': '1'}], {}),
    ([{'return_id': 1, 'issue_id': 42, 'quantity': 'NaN'}], {}),
    ([{'return_id': 1, 'issue_id': 42, 'quantity': '-1'}], {}),
    ([{'return_id': 1, 'issue_id': 42, 'quantity': '1'}], {'original_issue_amount': '1.001'}),
    ([{'return_id': 1, 'issue_id': 42, 'quantity': '1'}], {'currency': 'inr'}),
    ([{'return_id': 1, 'issue_id': 42, 'quantity': '1'}], {'issue_id': True}),
    ([], {}),
])
def test_fail_closed(returns, kwargs):
    with pytest.raises(ValueError):
        preview(returns, **kwargs)
