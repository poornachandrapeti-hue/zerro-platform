"""Rules for controlled equipment confirmation, independent of database access."""
from datetime import timezone

def can_confirm(asset, allocation, confirmation_at=None):
    if allocation.resource_type != 'Equipment' or allocation.resource_ref != f'equipment:{asset.id}':
        return False, 'Allocation must reference registered equipment'
    # Invalid or timezone-ambiguous bookings cannot be approved even when
    # the planning allocation was created by an older client or import.
    if (allocation.starts_at is None or allocation.ends_at is None
            or allocation.starts_at.tzinfo is None or allocation.ends_at.tzinfo is None
            or allocation.starts_at.utcoffset() is None or allocation.ends_at.utcoffset() is None
            or allocation.ends_at <= allocation.starts_at):
        return False, 'Equipment allocation requires a valid timezone-aware time window'
    if asset.organization_id != allocation.organization_id:
        return False, 'Equipment belongs to another organization'
    if getattr(asset,'inspection_review_status',None) != 'Verified':
        return False, 'Independently reviewed inspection evidence required'
    if asset.status != 'Active':
        return False, 'Equipment is not active'
    if getattr(asset,'operating_condition','Unknown') in ('Restricted','UnderRepair','Unserviceable'):
        return False, 'Equipment operating condition prohibits allocation'
    if getattr(asset,'tracking_mode','Individual') == 'QuantityManaged':
        return False, 'Quantity-managed tool pools require E3 quantity booking controls'
    if not asset.inspection_evidence_ref or not asset.inspection_valid_through:
        return False, 'Inspection evidence and validity required'
    end_day=allocation.ends_at.astimezone(timezone.utc).date()
    if asset.inspection_valid_through < end_day:
        return False, 'Inspection expires before reservation ends'
    if allocation.status != 'Reviewed':
        return False, 'Planning review required before equipment confirmation'
    return True, None
