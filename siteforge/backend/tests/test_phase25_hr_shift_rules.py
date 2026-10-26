from datetime import datetime,date,time,timezone
from types import SimpleNamespace
from app.domains.planning_reporting.hr_allocation_rules import crew_shift_eligibility

def make(start='2026-10-20T08:00:00+00:00',end='2026-10-20T16:00:00+00:00',shift_start=time(8),shift_end=time(16)):
    a=SimpleNamespace(resource_type='Workforce',resource_ref='crew:4',status='Reviewed',project_id=9,starts_at=datetime.fromisoformat(start),ends_at=datetime.fromisoformat(end))
    c=SimpleNamespace(id=4,active=True,project_id=9,shift_id=2,effective_from=date(2026,1,1),effective_to=None)
    s=SimpleNamespace(id=2,active=True,project_id=9,start_time=shift_start,end_time=shift_end,effective_from=date(2026,1,1),effective_to=None)
    return a,c,s

def test_valid_shift():assert crew_shift_eligibility(*make())[0]
def test_outside_shift():assert not crew_shift_eligibility(*make(end='2026-10-20T17:00:00+00:00'))[0]
def test_unreviewed():
    a,c,s=make();a.status='Proposed';assert not crew_shift_eligibility(a,c,s)[0]
def test_overnight():assert crew_shift_eligibility(*make('2026-10-20T22:00:00+00:00','2026-10-21T05:00:00+00:00',time(22),time(6)))[0]
def test_inactive_crew():
    a,c,s=make();c.active=False;assert not crew_shift_eligibility(a,c,s)[0]

def test_project_timezone_conversion():
    a,c,s=make('2026-10-20T02:30:00+00:00','2026-10-20T10:30:00+00:00')
    assert crew_shift_eligibility(a,c,s,'Asia/Kolkata')[0]

def test_wrong_project_timezone():
    a,c,s=make('2026-10-20T02:30:00+00:00','2026-10-20T10:30:00+00:00')
    assert not crew_shift_eligibility(a,c,s,'UTC')[0]
