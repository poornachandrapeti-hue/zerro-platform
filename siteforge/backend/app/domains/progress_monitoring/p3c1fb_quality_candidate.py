"""P3C1F-B: scoped, read-only Quality inspection candidate readback.

This does NOT authenticate a physical site-measurement file. Never set
`authority_verified=True` or feed this candidate as authoritative evidence
into P3C1F-A. Access authorization is the caller's existing project/QA RBAC.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Any


def _value(obj: Any, name: str) -> Any:
    return getattr(obj, name, None)


def _quantity(value: Any) -> str | None:
    try:
        q = Decimal(str(value))
        return str(q) if q.is_finite() and q >= 0 else None
    except (TypeError, ValueError, InvalidOperation):
        return None


def inspect_quality_candidate(*, request: Any, results: list[Any], organization_id: int,
                              project_id: int, activity_id: int) -> dict:
    """Produce a minimal, non-authoritative projection; reject cross-scope rows."""
    if (str(_value(request, 'organization_id')) != str(organization_id) or
        str(_value(request, 'project_id')) != str(project_id) or
        str(_value(request, 'activity_id')) != str(activity_id)):
        raise PermissionError('QA inspection is outside authorized source scope')
    status = _value(request, 'status')
    outcome = _value(request, 'outcome')
    blockers = []
    if status != 'Approved':
        blockers.append('qa_request_not_approved')
    if outcome not in ('Accepted', 'Partially Accepted'):
        blockers.append('qa_outcome_not_accepted')
    qty = _quantity(_value(request, 'accepted_quantity'))
    if qty is None:
        blockers.append('qa_accepted_quantity_missing_or_invalid')
    if (_value(request, 'requester_id') is None or _value(request, 'inspector_id') is None
        or str(_value(request, 'requester_id')) == str(_value(request, 'inspector_id'))):
        blockers.append('qa_inspector_not_independent')
    if any(_value(r, 'result') == 'Fail' for r in results):
        blockers.append('failed_quality_checklist_item')
    # Even a fully approved request does not prove the existence/content of a
    # digitally immutable, independently measured site-verification document.
    blockers.append('physical_measurement_evidence_not_authenticated')
    return {
        'source_kind': 'quality_construction_request',
        'source_id': _value(request, 'id'),
        'organization_id': organization_id,
        'project_id': project_id,
        'activity_id': activity_id,
        'quality_status': status,
        'quality_outcome': outcome,
        'accepted_quantity': qty,
        'quality_version': _value(request, 'version'),
        'candidate_only': True,
        'authority_verified': False,
        'published': False,
        'billing_certified': False,
        'blockers': sorted(set(blockers)),
    }


def read_quality_candidate(*, session: Any, inspection_id: int,
                           organization_id: int, project_id: int, activity_id: int,
                           authorized: bool = False) -> dict:
    """Internal only. Caller MUST derive `authorized` from server-side QA/project RBAC.

    Do not expose as an HTTP endpoint that accepts `authorized` from a request.
    """
    if authorized is not True:
        raise PermissionError('Project/QA read permission required')
    from app.domains.quality.models import ConstructionRequest, ConstructionResult
    # Full composite scope in the SQL predicate prevents cross-project inspection readback.
    from sqlalchemy import select
    item = session.scalar(select(ConstructionRequest).where(
        ConstructionRequest.id == inspection_id,
        ConstructionRequest.organization_id == organization_id,
        ConstructionRequest.project_id == project_id,
        ConstructionRequest.activity_id == activity_id,
    ))
    if item is None:
        raise LookupError('Inspection not found in authorized scope')
    results = list(session.scalars(select(ConstructionResult).where(
        ConstructionResult.request_id == item.id)).all())
    return inspect_quality_candidate(request=item, results=results,
        organization_id=organization_id, project_id=project_id, activity_id=activity_id)
