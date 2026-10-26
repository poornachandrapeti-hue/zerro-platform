"""E4 maintenance transition rules. Equipment remains authority for operational holds."""
from datetime import date
from fastapi import HTTPException

OPEN_STATES = frozenset({'Reported', 'InRepair', 'RepairComplete'})

def start_work_order(asset, kind, due_on=None):
    if getattr(asset, 'tracking_mode', 'Individual') != 'Individual':
        raise HTTPException(409, 'Quantity-managed tools require an individually identified maintenance item')
    if asset.status != 'Active':
        raise HTTPException(409, 'Equipment asset is inactive')
    if asset.operating_condition in {'UnderRepair', 'Restricted', 'Unserviceable'}:
        raise HTTPException(409, 'Equipment is already held or unavailable')
    if kind not in {'Preventive', 'Breakdown'}:
        raise HTTPException(422, 'Invalid maintenance type')
    if kind == 'Preventive' and due_on is None:
        raise HTTPException(422, 'Preventive work requires due date')

def advance_work_order(order, target, actor_id, evidence_ref):
    current = order.status
    allowed = {'Reported': 'InRepair', 'InRepair': 'RepairComplete', 'RepairComplete': 'Released'}
    if allowed.get(current) != target:
        raise HTTPException(409, 'Invalid maintenance transition')
    if not evidence_ref or len(evidence_ref.strip()) < 3:
        raise HTTPException(422, 'Transition evidence required')
    if target == 'Released' and actor_id in {order.created_by, order.repair_completed_by}:
        raise HTTPException(403, 'Independent maintenance release verification required')
    if target == 'Released' and not order.repair_evidence_ref:
        raise HTTPException(409, 'Repair completion evidence missing')
    return target

def may_start_equipment(asset, orders):
    if asset.operating_condition != 'Serviceable':
        return False
    return not any(order.status in OPEN_STATES for order in orders)
