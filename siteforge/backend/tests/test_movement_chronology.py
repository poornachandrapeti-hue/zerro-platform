from datetime import datetime, timedelta, timezone
import pytest
from app.domains.commercial_financials.movement_chronology import verify_receipt_acceptance_precedes_issue

NOW = datetime(2026, 10, 26, 8, tzinfo=timezone.utc)

def test_historical_acceptance_precedes_issue():
    result = verify_receipt_acceptance_precedes_issue(NOW, [(10, NOW - timedelta(hours=1))])
    assert result['status'] == 'ACCEPTANCE_CHRONOLOGY_OK'
    assert not result['movement_valuation_verified']

@pytest.mark.parametrize('issue,events', [
    (NOW, []),
    (NOW, [(10, NOW + timedelta(seconds=1))]),
    (NOW.replace(tzinfo=None), [(10, NOW)]),
    (NOW, [(10, NOW.replace(tzinfo=None))]),
    (NOW, [(0, NOW)]),
    (NOW, [(True, NOW)]),
])
def test_invalid_or_future_acceptance_rejected(issue, events):
    with pytest.raises(ValueError):
        verify_receipt_acceptance_precedes_issue(issue, events)
