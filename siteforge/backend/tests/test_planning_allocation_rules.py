from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from app.domains.planning_reporting.allocation_rules import overlaps,conflict_ids

def dt(hour):return datetime(2026,10,18,hour,tzinfo=timezone.utc)

def test_adjacent_not_conflict():assert not overlaps(dt(8),dt(10),dt(10),dt(12))
def test_overlap():assert overlaps(dt(8),dt(11),dt(10),dt(12))
def test_containment():assert overlaps(dt(8),dt(14),dt(10),dt(11))
def test_invalid_dates():
    try:overlaps(dt(10),dt(8),dt(10),dt(12))
    except ValueError:return
    assert False

def test_scope_and_cancelled():
    base=dict(organization_id=1,project_id=1,resource_type='Equipment',resource_ref='CRANE-1',starts_at=dt(8),ends_at=dt(12))
    candidate=SimpleNamespace(**base)
    other=SimpleNamespace(**dict(base,id=1,status='Proposed'))
    cancelled=SimpleNamespace(**dict(base,id=2,status='Cancelled'))
    other_project=SimpleNamespace(**dict(base,id=3,status='Proposed',project_id=2))
    assert conflict_ids(candidate,[other,cancelled,other_project])==[1,3]


def test_returned_and_other_organization_not_blocked():
    base=dict(organization_id=1,project_id=1,resource_type='Workforce',resource_ref='crew:7',starts_at=dt(8),ends_at=dt(12))
    candidate=SimpleNamespace(**base)
    returned=SimpleNamespace(**dict(base,id=10,status='Returned'))
    external=SimpleNamespace(**dict(base,id=11,status='Proposed',organization_id=2))
    assert conflict_ids(candidate,[returned,external])==[]
