from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from app.domains.contracts.router import obligation_alert_candidates


def obj(i, due_at, status='Not Started'):
    return SimpleNamespace(id=i, contract_id=100, number=f'OB-{i}', due_at=due_at,
        status=status, owner_user_id=21, responsible_company_id=3)


def test_alert_queue_respects_unresolved_overdue_and_closed():
    now=datetime(2026,10,21,tzinfo=timezone.utc)
    rows=[obj(1,None),obj(2,now-timedelta(days=1)),obj(3,now+timedelta(days=2)),
        obj(4,now+timedelta(days=30)),obj(5,now-timedelta(days=1),'Accepted')]
    data=obligation_alert_candidates(rows,now,7)
    assert [(v['obligation_id'],v['kind']) for v in data]==[(1,'unresolved'),(2,'overdue'),(3,'upcoming')]


def test_alert_queue_excludes_waived_and_cancelled():
    now=datetime(2026,10,21,tzinfo=timezone.utc)
    assert obligation_alert_candidates([obj(1,None,'Waived'),obj(2,now,'Cancelled')],now,7)==[]
