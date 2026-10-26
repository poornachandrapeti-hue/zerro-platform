"""Conservative HR crew-shift verification; never implies attendance or HSE clearance."""
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo

def crew_shift_eligibility(allocation, crew, shift, project_timezone="UTC"):
    if allocation.resource_type != 'Workforce' or allocation.resource_ref != f'crew:{crew.id}':
        return False, 'Source-linked crew allocation required'
    if allocation.status != 'Reviewed':
        return False, 'Independent Planning review required'
    if not crew.active or crew.project_id != allocation.project_id:
        return False, 'Crew inactive or outside allocation project'
    if not shift or not shift.active or crew.shift_id != shift.id or shift.project_id != allocation.project_id:
        return False, 'Active project crew shift required'
    if allocation.starts_at.tzinfo is None or allocation.ends_at.tzinfo is None:
        return False, 'Timezone-aware allocation required'
    if allocation.starts_at >= allocation.ends_at:
        return False, 'Invalid interval'
    # Do not attempt to interpret overlapping DST/overnight shifts using an unspecified project timezone.
    # Compare local wall times from the allocation's explicit timezone.
    local_start=allocation.starts_at.astimezone(ZoneInfo(project_timezone))
    local_end=allocation.ends_at.astimezone(ZoneInfo(project_timezone))
    day=local_start.date()
    start=datetime.combine(day,shift.start_time,tzinfo=local_start.tzinfo)
    end=datetime.combine(day,shift.end_time,tzinfo=local_start.tzinfo)
    if end<=start:end+=timedelta(days=1)
    if not (start<=local_start and local_end<=end):
        return False, 'Allocation falls outside assigned shift window'
    if crew.effective_from>day or (crew.effective_to and crew.effective_to<day):
        return False, 'Crew not effective on shift date'
    if shift.effective_from>day or (shift.effective_to and shift.effective_to<day):
        return False, 'Shift not effective on allocation date'
    return True,'Crew-shift alignment verified; attendance and headcount not verified'
