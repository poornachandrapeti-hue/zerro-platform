"""Equipment E7B3: record verified authority references, never post to Stores/Finance."""
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from .equipment_e7_authority_api import _authorized_asset
from .equipment_e7_authority_readback import read_hire_contract_authority, read_spares_request_authority
from .equipment_e7_handoff_records import EquipmentAuthorityHandoff

router = APIRouter(prefix='/api/projects/{pid}/planning/equipment-assets/{asset_id}/authority-handoffs',
                   tags=['Equipment Authority Handoffs'])


class HandoffInput(BaseModel):
    authority_kind: str = Field(pattern='^(HireContract|StoresSpareRequest)$')
    authority_id: int = Field(gt=0)
    request_key: str = Field(min_length=8, max_length=100)
    evidence_ref: str = Field(min_length=3, max_length=240)


def snapshot_json(value):
    """Freeze readback evidence as JSON rather than mutating the source domains."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): snapshot_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [snapshot_json(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise HTTPException(409, 'Unsupported authority evidence value')


def _matches(row, pid, asset_id, body):
    return (row.project_id == pid and row.asset_id == asset_id and
            row.authority_kind == body.authority_kind and row.authority_id == body.authority_id and
            row.evidence_ref == body.evidence_ref)


def _response(row):
    return {'handoff_id': row.id, 'asset_id': row.asset_id, 'project_id': row.project_id,
            'authority_kind': row.authority_kind, 'authority_id': row.authority_id,
            'request_key': row.request_key, 'evidence_ref': row.evidence_ref,
            'authority_snapshot': row.authority_snapshot, 'recorded_by': row.created_by,
            'handoff_recorded': True, 'stock_posted': False, 'hire_billed': False,
            'finance_posted': False}


@router.post('', status_code=201)
def record_authority_handoff(pid: int, asset_id: int, body: HandoffInput,
                             user: User = Depends(authenticated), db: Session = Depends(get_db)):
    asset = _authorized_asset(db, user, pid, asset_id)
    key = body.request_key.strip()
    if key != body.request_key or not key:
        raise HTTPException(422, 'Request key must be normalized')
    evidence = body.evidence_ref.strip()
    if evidence != body.evidence_ref or not evidence:
        raise HTTPException(422, 'Evidence reference must be normalized')

    existing = db.query(EquipmentAuthorityHandoff).filter_by(
        organization_id=user.organization_id, request_key=key).one_or_none()
    if existing:
        if not _matches(existing, pid, asset_id, body):
            raise HTTPException(409, 'Idempotency key already used for a different handoff')
        return _response(existing)

    if body.authority_kind == 'HireContract':
        if asset.ownership_type != 'Hired':
            raise HTTPException(409, 'Only hired equipment may reference hire contracts')
        authority = read_hire_contract_authority(db, contract_id=body.authority_id,
                  org_id=user.organization_id, project_id=pid)
        if not asset.hire_contract_ref or asset.hire_contract_ref != authority['reference']:
            raise HTTPException(409, 'Asset hire reference does not match approved contract')
    else:
        authority = read_spares_request_authority(db, request_id=body.authority_id,
                  org_id=user.organization_id, project_id=pid)

    record = EquipmentAuthorityHandoff(
        organization_id=user.organization_id, project_id=pid, asset_id=asset_id,
        authority_kind=body.authority_kind, authority_id=body.authority_id,
        request_key=key, evidence_ref=evidence, authority_snapshot=snapshot_json(authority),
        created_by=user.id)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = db.query(EquipmentAuthorityHandoff).filter_by(
            organization_id=user.organization_id, request_key=key).one_or_none()
        if duplicate and _matches(duplicate, pid, asset_id, body):
            return _response(duplicate)
        raise HTTPException(409, 'Concurrent or conflicting handoff request')
    db.refresh(record)
    return _response(record)


@router.get('/{handoff_id}')
def get_authority_handoff(pid: int, asset_id: int, handoff_id: int,
                          user: User = Depends(authenticated), db: Session = Depends(get_db)):
    _authorized_asset(db, user, pid, asset_id)
    row = db.query(EquipmentAuthorityHandoff).filter_by(
        id=handoff_id, organization_id=user.organization_id,
        project_id=pid, asset_id=asset_id).one_or_none()
    if row is None:
        raise HTTPException(404, 'Handoff not found for equipment and project')
    return _response(row)
