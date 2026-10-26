"""Read-only, conservative headcount evidence for crew allocations."""
from datetime import date


def capacity_counts(members, deployments, personnel, attendance):
    """Inputs are indexed by personnel id. Count each person at most once.

    attendance maps personnel id to (sheet_status, attendance_status).
    Missing HR evidence never becomes confirmed availability.
    """
    eligible=set()
    for m in members:
        d=deployments.get(m.personnel_id)
        p=personnel.get(m.personnel_id)
        if not d or not p or p.status != 'Active' or d.status != 'Mobilized':
            continue
        eligible.add(m.personnel_id)
    present=sum(1 for person_id in eligible if attendance.get(person_id) in (
        ('Approved','Present'),('Approved','Partial Attendance')))
    absent=sum(1 for person_id in eligible if attendance.get(person_id) in (
        ('Approved','Absent'),('Approved','On Leave'),('Approved','Weekly Off/Holiday')))
    return {'eligible_assignment_count':len(eligible), 'approved_attended_count':present,
            'approved_unavailable_count':absent,
            'attendance_unverified_count':len(eligible)-present-absent}
