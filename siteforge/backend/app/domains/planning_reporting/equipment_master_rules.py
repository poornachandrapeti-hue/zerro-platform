"""E2 asset master lifecycle guardrails; never posts stock, custody or finance movements."""
from datetime import date
from fastapi import HTTPException
from .workspace_models import PlanningResourceAllocation

FIELDS=('id','asset_code','name','equipment_type','status','project_id','make','model',
        'serial_number','owner_company','ownership_type','location','custodian_user_id',
        'operating_condition','capacity','operating_specs','mobilized_on',
        'demobilized_on','hire_contract_ref','maintenance_requirements','tracking_mode','quantity')

def master_view(asset):
    result={}
    for field in FIELDS:
        value=getattr(asset,field,None)
        result[field]=value.isoformat() if isinstance(value,date) else value
    return result

def validate_master_transition(asset, changes, db, organization_id):
    """Disallow editing lifecycle-defining attributes while a confirmed booking exists.

    A future E3 custody workflow will own custodian and quantity movements; this update
    intentionally cannot mutate those counters or impersonate an issue/return.
    """
    if asset.organization_id != organization_id:
        raise HTTPException(403,'Equipment is outside organization scope')
    locked={'tracking_mode','quantity','mobilized_on','demobilized_on','operating_condition'}
    altered={key for key in locked if changes.get(key)!=getattr(asset,key)}
    if altered:
        active=db.query(PlanningResourceAllocation).filter_by(
            organization_id=organization_id,resource_type='Equipment',
            resource_ref=f'equipment:{asset.id}',status='EquipmentConfirmed').first()
        if active:
            raise HTTPException(409,'Cannot modify lifecycle state with active equipment allocations')
    if getattr(asset,'tracking_mode','Individual')=='QuantityManaged' and changes.get('quantity') != asset.quantity:
        raise HTTPException(409,'Tool pool quantity changes require E3 custody reconciliation')
    if changes.get('tracking_mode')=='QuantityManaged':
        # Quantity-managed tools cannot be reserved as a unique physical unit yet.
        # E3 will own pool booking, custody and reconciliation.
        active=db.query(PlanningResourceAllocation).filter_by(
            organization_id=organization_id,resource_type='Equipment',
            resource_ref=f'equipment:{asset.id}').first()
        if active:
            raise HTTPException(409,'Cannot switch allocated equipment to quantity-managed mode')
