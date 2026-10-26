"""E3 pure custody invariants. All monetary/spare movements belong to Stores/Finance."""
from datetime import date
from fastapi import HTTPException


def available_quantity(total: int, movements) -> int:
    """Compute balance from immutable Issue/Return records, not mutable quantity counters."""
    issued=sum(m.quantity for m in movements if m.action=='Issue')
    returned=sum(m.quantity for m in movements if m.action=='Return')
    if returned > issued:
        raise HTTPException(409,'Recorded returns exceed issued quantity')
    return total-issued+returned


def validate_issue(asset, quantity: int, allocation=None, today=None):
    today=today or date.today()
    if asset.status!='Active' or asset.operating_condition!='Serviceable':
        raise HTTPException(409,'Inactive or restricted equipment cannot be issued')
    if asset.demobilized_on and asset.demobilized_on<=today:
        raise HTTPException(409,'Demobilized equipment cannot be issued')
    if asset.inspection_review_status!='Verified' or not asset.inspection_valid_through or asset.inspection_valid_through<today:
        raise HTTPException(409,'Current independently verified inspection required')
    if asset.tracking_mode=='Individual':
        if quantity!=1 or allocation is None or allocation.status!='EquipmentConfirmed':
            raise HTTPException(409,'Individual equipment requires a confirmed Planning allocation')
        if allocation.resource_ref!=f'equipment:{asset.id}' or allocation.resource_type!='Equipment':
            raise HTTPException(409,'Allocation asset mismatch')
    elif asset.tracking_mode!='QuantityManaged':
        raise HTTPException(409,'Unrecognized equipment tracking mode')


def validate_return(issue, previous_returns, quantity: int, asset_id: int, project_id: int):
    if issue.action!='Issue' or issue.asset_id!=asset_id or issue.project_id!=project_id:
        raise HTTPException(409,'Original issue does not match asset and project')
    already=sum(r.quantity for r in previous_returns if r.action=='Return' and r.parent_issue_id==issue.id)
    if quantity>issue.quantity-already:
        raise HTTPException(409,'Return exceeds outstanding custody quantity')
    return issue.quantity-already-quantity
