"""P3C1: read-only approved Planning baseline authority and strict quantity provenance.

No quantity inferred from Construction activity or a date-only schedule. Do not
count this projection as independently verified, earned, or billable progress.
"""
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException
from app.domains.planning_reporting.models import PlanningBaseline


def _positive_quantity(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        num = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        return None
    return num if num.is_finite() and num > 0 else None


def resolve_baseline_activity(rows, *, organization_id, project_id, planning_activity_id, construction_activity_id, unit):
    """Select exactly one current approved baseline with explicit source mapping.

    Planning baseline document is currently a JSON schedule artifact. Quantity
    authority is exposed only when an activity contains an exact approved
    quantity + unit + construction source mapping; missing fields fail closed.
    No preference is invented between multiple approved baselines.
    """
    approved = [r for r in rows if r.organization_id == organization_id and
                r.project_id == project_id and r.status == 'approved' and
                r.approved_by is not None and r.approved_at is not None and
                isinstance(r.document, dict) and
                r.document.get('approval_status') == 'approved' and
                r.document.get('approval_reference')]
    if len(approved) != 1:
        return {'status': 'BASELINE_AMBIGUOUS' if approved else 'NO_APPROVED_BASELINE',
                'approved_planning_quantity': None, 'baseline_revision_id': None}
    row = approved[0]
    matches = [item for item in row.document.get('activities', [])
               if isinstance(item, dict) and
               str(item.get('planning_activity_id')) == str(planning_activity_id) and
               str(item.get('construction_activity_id')) == str(construction_activity_id)]
    if len(matches) != 1:
        return {'status': 'SOURCE_MAPPING_MISSING_OR_DUPLICATED',
                'approved_planning_quantity': None, 'baseline_revision_id': row.id}
    item = matches[0]
    quantity = _positive_quantity(item.get('approved_quantity'))
    if quantity is None or not isinstance(unit, str) or item.get('unit') != unit:
        return {'status': 'BASELINE_QUANTITY_OR_UNIT_UNAVAILABLE',
                'approved_planning_quantity': None, 'baseline_revision_id': row.id}
    return {'status': 'APPROVED_QUANTITY_FOUND',
            'approved_planning_quantity': str(quantity),
            'baseline_revision_id': row.id,
            'baseline_revision': row.revision,
            'approval_reference': row.document['approval_reference'],
            'planning_activity_id': planning_activity_id,
            'construction_activity_id': construction_activity_id,
            'unit': unit}


def read_authoritative_baseline(db, user, project_id, *, planning_activity_id, construction_activity_id, unit):
    """Read current project's existing baseline; caller must check Progress scope.

    This method intentionally does not accept quantities provided by the client.
    """
    from .router import progress_scope
    progress_scope(db, user, project_id)
    rows = db.query(PlanningBaseline).filter_by(
        organization_id=user.organization_id, project_id=project_id,
        status='approved').all()
    result = resolve_baseline_activity(rows, organization_id=user.organization_id,
        project_id=project_id, planning_activity_id=planning_activity_id,
        construction_activity_id=construction_activity_id, unit=unit)
    result.update(construction_verified_quantity=None, earned_percent=None,
                  billing_eligible_quantity=None,
                  limitation='Independent Construction quantity attestation is not yet an identified canonical source')
    return result
