"""Phase 8 planning demand and date exceptions; advisory, never physical stock availability."""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.domains.identity_projects.models import User
from app.domains.identity_projects.security import authenticated
from app.domains.construction.models import WorkPackage
from .models import StoresMaterialRequest
from .material_requests import _project, linked_procurement_commitments, material_readiness_blockers, schedule_alignment
from .allocation_lifecycle import request_summary

router = APIRouter(prefix='/api/projects/{pid}/stores', tags=['Stores Phase 8 Planning'])


def planning_exception_flags(*, required_date, planned_start, request_status, allocation_blockers, po_commitments, today):
    """Schedule/administrative exceptions only: never state actual stock shortage or ETA certainty."""
    flags = []
    if request_status != 'Approved':
        flags.append('STORES_REQUEST_NOT_APPROVED')
    if planned_start is None:
        flags.append('WORK_PACKAGE_START_NOT_PLANNED')
    elif required_date > planned_start:
        flags.append('MATERIAL_REQUIRED_AFTER_WORK_PACKAGE_START')
    if required_date < today:
        flags.append('MATERIAL_REQUIRED_DATE_PASSED')
    if not po_commitments:
        flags.append('NO_LINKED_PROCUREMENT_COMMITMENT')
    elif all(p.get('promised_date') and p['promised_date'] > required_date.isoformat() for p in po_commitments):
        flags.append('ALL_PO_PROMISES_AFTER_REQUIRED_DATE')
    if 'APPROVED_REQUEST_NOT_FULLY_ALLOCATED' in allocation_blockers:
        flags.append('DEMAND_ALLOCATION_INCOMPLETE')
    return flags


@router.get('/phase8/planning-material-readiness')
def planning_material_readiness(pid: int, work_package_id: int | None = None, limit: int = 200,
                                u: User = Depends(authenticated), db: Session = Depends(get_db)):
    """Project-scoped source of Planning exceptions; no progress, PO delivery or stock certification."""
    _project(db, u, pid, action='stores.requests.view')
    if not 1 <= limit <= 500:
        raise HTTPException(422, 'Limit must be 1–500')
    if work_package_id is not None and work_package_id <= 0:
        raise HTTPException(422, 'Invalid work package ID')
    query = select(StoresMaterialRequest).where(
        StoresMaterialRequest.project_id == pid, StoresMaterialRequest.organization_id == u.organization_id)
    if work_package_id is not None:
        query = query.where(StoresMaterialRequest.work_package_id == work_package_id)
    requests = db.execute(query.order_by(StoresMaterialRequest.required_date, StoresMaterialRequest.id).limit(limit)).scalars().all()
    wp_ids = {r.work_package_id for r in requests if r.work_package_id is not None}
    work_packages = {w.id: w for w in db.execute(select(WorkPackage).where(
        WorkPackage.id.in_(wp_ids), WorkPackage.project_id == pid,
        WorkPackage.organization_id == u.organization_id)).scalars().all()} if wp_ids else {}
    today = date.today()
    rows = []
    for req in requests:
        wp = work_packages.get(req.work_package_id)
        summary = request_summary(db, req) if req.status == 'Approved' else None
        commitments = linked_procurement_commitments(db, pid, u.organization_id, req.requirement_line_id) if req.requirement_line_id else []
        base_flags = material_readiness_blockers(
            demand_quantity=summary['approved_quantity'] if summary else req.requested_quantity,
            active_reserved=summary['active_reserved_quantity'] if summary else 0,
            issued_quantity=summary['consumed_by_issue'] if summary else 0,
            required_date=req.required_date, po_commitments=commitments)
        exceptions = planning_exception_flags(required_date=req.required_date,
            planned_start=wp.planned_start if wp else None, request_status=req.status,
            allocation_blockers=base_flags, po_commitments=commitments, today=today)
        rows.append(dict(material_request_id=req.id, requirement_line_id=req.requirement_line_id,
            work_package_id=req.work_package_id, planning_wbs_id=req.planning_wbs_id,
            work_package_code=wp.code if wp else None, work_package_status=wp.status if wp else None,
            work_package_planned_start=str(wp.planned_start) if wp and wp.planned_start else None,
            required_date=req.required_date.isoformat(), days_until_required=(req.required_date - today).days,
            item_id=req.item_id, unit=req.base_unit, request_status=req.status,
            requested_quantity=str(req.requested_quantity),
            active_reserved_quantity=summary['active_reserved_quantity'] if summary else None,
            issued_quantity=summary['consumed_by_issue'] if summary else None,
            linked_procurement_commitments=commitments,
            schedule_alignment=schedule_alignment(req.required_date, wp.planned_start if wp else None, wp.planned_finish if wp else None),
            planning_exceptions=exceptions, material_readiness_blockers=base_flags,
            physical_stock_readiness='Unverified', actual_delivery_verified=False,
            construction_progress_credited=False))
    return dict(project_id=pid, records=rows, returned_count=len(rows),
        exception_record_count=sum(bool(x['planning_exceptions']) for x in rows),
        as_of=datetime.now(timezone.utc), coverage=f'First {limit} requests sorted by required date; not all-time',
        physical_stock_readiness='Unverified',
        note='Planning exceptions are advisory; procurement promises are not proof of delivery, allocations are not verified physical availability, and no stock/progress/financial posting occurs.')
