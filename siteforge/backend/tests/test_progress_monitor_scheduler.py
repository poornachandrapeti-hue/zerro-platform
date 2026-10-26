from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from app.domains.progress_monitoring.monitor import due_for_scan

def test_disabled_policy_never_scans():
    assert not due_for_scan(SimpleNamespace(enabled=False,last_scanned_at=None),datetime.now(timezone.utc))

def test_due_hourly():
    now=datetime.now(timezone.utc)
    assert due_for_scan(SimpleNamespace(enabled=True,last_scanned_at=None),now)
    assert not due_for_scan(SimpleNamespace(enabled=True,last_scanned_at=now-timedelta(minutes=15)),now)
    assert due_for_scan(SimpleNamespace(enabled=True,last_scanned_at=now-timedelta(hours=2)),now)
