"""Phase 5: mandatory canonical-demand authorization for physical lot issue.

Caller holds the reservation row lock. This module does not post inventory and
must be invoked before any ledger mutation. Existing stock/QA gates still apply.
"""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from app.domains.supply_chain.models import MaterialRequirement, RequirementLine
from app.domains.construction.models import WorkPackage, WorkPackageRequirement
from .models import StoresMaterialRequest


def require_issue_authorization(db, *, project, organization_id, reservation, item_id, unit, amount):
    if reservation is None or reservation.material_request_id is None:
        raise HTTPException(409, 'Physical issue requires an approved Stores issue request allocation')
    request = db.execute(select(StoresMaterialRequest).where(
        StoresMaterialRequest.id == reservation.material_request_id,
        StoresMaterialRequest.project_id == project.id,
        StoresMaterialRequest.organization_id == organization_id)).scalar_one_or_none()
    if not request or request.status != 'Approved' or not request.requirement_line_id:
        raise HTTPException(409, 'Source Stores issue request is no longer approved')
    if (request.item_id != item_id or request.base_unit != unit or
            reservation.requirement_line_id != request.requirement_line_id or
            reservation.work_package_id != request.work_package_id or
            reservation.planning_wbs_id != request.planning_wbs_id):
        raise HTTPException(409, 'Reservation no longer matches approved issue request scope')
    line = db.execute(select(RequirementLine).where(
        RequirementLine.id == request.requirement_line_id)).scalar_one_or_none()
    parent = db.get(MaterialRequirement, line.requirement_id) if line else None
    if (not line or line.item_id != item_id or line.unit != unit or not parent or
            parent.project_id != project.id or parent.organization_id != organization_id or
            parent.status != 'Approved' or parent.impact_state == 'Review required'):
        raise HTTPException(409, 'Canonical Procurement requirement is not eligible for issue')
    if request.requester_company_id is not None:
        if parent.company_id != request.requester_company_id or not request.work_package_id:
            raise HTTPException(409, 'Contractor demand assignment has changed')
        wp = db.execute(select(WorkPackage).where(
            WorkPackage.id == request.work_package_id,
            WorkPackage.project_id == project.id,
            WorkPackage.organization_id == organization_id,
            WorkPackage.company_id == request.requester_company_id)).scalar_one_or_none()
        if not wp or wp.release_state != 'Released' or wp.status in ('Cancelled', 'On Hold'):
            raise HTTPException(409, 'Contractor work package is not released')
        linked = db.execute(select(WorkPackageRequirement.id).where(
            WorkPackageRequirement.package_id == wp.id,
            WorkPackageRequirement.requirement_id == parent.id)).first()
        if not linked:
            raise HTTPException(409, 'Canonical requirement is not linked to contractor work package')
    # Fail closed if the approved source line was remapped after allocation.
    if line.planning_wbs_id is not None and line.planning_wbs_id != request.planning_wbs_id:
        raise HTTPException(409, 'Canonical requirement WBS scope changed after allocation')
    qty = Decimal(str(amount))
    remaining = Decimal(str(reservation.remaining_quantity))
    if not qty.is_finite() or qty <= 0 or not remaining.is_finite() or remaining < 0:
        raise HTTPException(409, 'Invalid issue or allocation quantity')
    if qty > remaining:
        raise HTTPException(409, 'Issue exceeds approved allocation remaining quantity')
    return request
