"""E7B2: project-scoped read-only authority checks for equipment integrations.

No stock deduction, contract modification, hire billing or GL posting takes place here.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .equipment_router import equipment_access
from .workspace_models import PlanningEquipmentAsset
from .equipment_e7_authority_readback import (
    read_hire_contract_authority, read_spares_request_authority,
)

router = APIRouter(
    prefix='/api/projects/{pid}/planning/equipment-assets/{asset_id}/authority',
    tags=['Equipment Authority Readback'],
)


def _authorized_asset(db, user, pid, asset_id):
    equipment_access(db, user, pid)
    asset = db.get(PlanningEquipmentAsset, asset_id)
    if (asset is None or asset.organization_id != user.organization_id
            or asset.project_id != pid):
        raise HTTPException(404, 'Equipment not found for project')
    return asset


@router.get('/hire-contracts/{contract_id}')
def verify_hire_contract(
    pid: int, asset_id: int, contract_id: int,
    user: User = Depends(authenticated), db: Session = Depends(get_db),
):
    asset = _authorized_asset(db, user, pid, asset_id)
    if asset.ownership_type != 'Hired':
        raise HTTPException(409, 'Only hired equipment can verify a hire contract')
    authority = read_hire_contract_authority(
        db, contract_id=contract_id, org_id=user.organization_id, project_id=pid,
    )
    if not asset.hire_contract_ref or asset.hire_contract_ref != authority['reference']:
        raise HTTPException(409, 'Asset hire reference does not match approved contract')
    return {
        'equipment_asset_id': asset.id, 'project_id': pid,
        'authority': authority, 'handoff_created': False, 'finance_posted': False,
    }


@router.get('/spare-requests/{request_id}')
def verify_spares_request(
    pid: int, asset_id: int, request_id: int,
    user: User = Depends(authenticated), db: Session = Depends(get_db),
):
    asset = _authorized_asset(db, user, pid, asset_id)
    authority = read_spares_request_authority(
        db, request_id=request_id, org_id=user.organization_id, project_id=pid,
    )
    return {
        'equipment_asset_id': asset.id, 'project_id': pid,
        'authority': authority, 'handoff_created': False,
        'stock_posted': False, 'finance_posted': False,
    }
