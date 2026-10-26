"""E1 regression: reject invalid equipment reservation windows at the domain gate."""
from datetime import datetime, date, timedelta, timezone
from types import SimpleNamespace as NS
from app.domains.planning_reporting.equipment_rules import can_confirm


def asset():
    return NS(id=10, organization_id=1, status='Active',
              inspection_review_status='Verified', inspection_evidence_ref='INS-10',
              inspection_valid_through=date(2027, 12, 31))


def booking(start=None, end=None):
    start = start if start is not None else datetime(2026, 11, 1, 8, tzinfo=timezone.utc)
    end = end if end is not None else start + timedelta(hours=8)
    return NS(resource_type='Equipment', resource_ref='equipment:10',
              organization_id=1, starts_at=start, ends_at=end, status='Reviewed')


def test_valid_window_still_works():
    assert can_confirm(asset(), booking()) == (True, None)


def test_zero_duration_is_rejected():
    t=datetime(2026, 11, 1, 8, tzinfo=timezone.utc)
    ok, reason=can_confirm(asset(), booking(t,t))
    assert not ok and 'time window' in reason


def test_reversed_window_is_rejected():
    t=datetime(2026, 11, 1, 8, tzinfo=timezone.utc)
    assert not can_confirm(asset(), booking(t,t-timedelta(minutes=1)))[0]


def test_naive_window_is_rejected():
    t=datetime(2026, 11, 1, 8)
    assert not can_confirm(asset(), booking(t,t+timedelta(hours=1)))[0]


def test_cross_organization_still_fails():
    b=booking(); b.organization_id=99
    assert not can_confirm(asset(), b)[0]


def test_expired_inspection_still_fails():
    a=asset(); a.inspection_valid_through=date(2026,10,31)
    assert not can_confirm(a,booking())[0]
