from types import SimpleNamespace as R
from app.domains.planning_reporting.workforce_capacity import capacity_counts

def test_missing_evidence_not_counted():
    assert capacity_counts([R(personnel_id=1)], {}, {}, {})['eligible_assignment_count']==0

def test_active_mobilized_only_and_unique():
    m=[R(personnel_id=1),R(personnel_id=1),R(personnel_id=2)]
    d={1:R(status='Mobilized'),2:R(status='Temporarily Unavailable')}
    p={1:R(status='Active'),2:R(status='Active')}
    result=capacity_counts(m,d,p,{1:('Approved','Present')})
    assert result['eligible_assignment_count']==1
    assert result['approved_attended_count']==1

def test_unapproved_sheet_does_not_count():
    c=capacity_counts([R(personnel_id=1)],{1:R(status='Mobilized')},{1:R(status='Active')},{1:('Pending Review','Present')})
    assert c['attendance_unverified_count']==1 and c['approved_attended_count']==0
