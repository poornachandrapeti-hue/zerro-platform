"""Rules for controlled equipment confirmation, independent of database access."""
from datetime import timezone

def can_confirm(asset, allocation, confirmation_at=None):
    if allocation.resource_type != 'Equipment' or allocation.resource_ref != f'equipment:{asset.id}':
        return False, 'Allocation must reference registered equipment'
    if asset.organization_id != allocation.organization_id:
        return False, 'Equipment belongs to another organization'
    if getattr(asset,'inspection_review_status',None) != 'Verified':
        return False, 'Independently reviewed inspection evidence required'
    if asset.status != 'Active':
        return False, 'Equipment is not active'
    if not asset.inspection_evidence_ref or not asset.inspection_valid_through:
        return False, 'Inspection evidence and validity required'
    end_day=allocation.ends_at.astimezone(timezone.utc).date()
    if asset.inspection_valid_through < end_day:
        return False, 'Inspection expires before reservation ends'
    if allocation.status != 'Reviewed':
        return False, 'Planning review required before equipment confirmation'
    return True, None
