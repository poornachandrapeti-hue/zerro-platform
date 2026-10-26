"""Scheduling allocation conflict rules; no implied HR/equipment authorization."""
from datetime import datetime

def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    if start_a >= end_a or start_b >= end_b:
        raise ValueError('Allocation end must be after start')
    if (start_a.tzinfo is None) != (start_b.tzinfo is None):
        raise ValueError('Timezone awareness must match')
    return start_a < end_b and start_b < end_a

def conflict_ids(candidate, existing):
    """Same organization/resource identity across projects; cancelled entries excluded."""
    return [entry.id for entry in existing if entry.status not in ('Cancelled','Returned','Released')
            and entry.organization_id == candidate.organization_id
            and entry.resource_type == candidate.resource_type
            and entry.resource_ref == candidate.resource_ref
            and overlaps(candidate.starts_at,candidate.ends_at,entry.starts_at,entry.ends_at)]
