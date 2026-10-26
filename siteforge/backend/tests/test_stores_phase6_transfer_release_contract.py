from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.transfer_reservation_release import release_policy


def test_pending_intent_release_does_not_require_reserved_balance():
    assert release_policy('PendingActivation', Decimal('10'), Decimal('4')) == Decimal('4')


def test_active_release_requires_reserved_cover():
    assert release_policy('Active', '8', '3', '3') == Decimal('3')
    with pytest.raises(HTTPException) as exc:
        release_policy('Active', '8', '4', '3')
    assert exc.value.status_code == 409


def test_release_rejects_insufficient_remaining_and_inactive():
    for status, remaining, qty in [('Consumed', '10', '1'), ('Active', '2', '3'), ('PendingActivation', '-1', '1')]:
        with pytest.raises(HTTPException):
            release_policy(status, remaining, qty, '10')


def test_default_off_flag_and_router_contract(monkeypatch):
    from app.domains.stores_inventory.transfer_reservation_release import router
    monkeypatch.delenv('STORES_TRANSFER_RESERVATION_RELEASE_ENABLED', raising=False)
    matches = [r for r in router.routes if r.path.endswith('/reservation-intents/{intent_id}/release')]
    assert len(matches) == 1
    assert 'POST' in matches[0].methods
