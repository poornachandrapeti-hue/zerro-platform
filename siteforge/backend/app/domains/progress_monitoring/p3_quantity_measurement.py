"""P3A: source-grounded per-leaf quantity measures; pure preview, never billing.

Caller must use authoritative approved WBS target and audited, current QA links.
This module does not fetch source records or authorize users. Fail closed on
missing or ambiguous evidence. No progress snapshots or ledgers are written.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MEASURES = ('reported_percent', 'verified_percent', 'accepted_percent')


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        d = Decimal(str(value))
        return d if d.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def calculate_leaf_quantities(*, planned_quantity, unit, reported_quantity,
                              verified_quantity, approved_evidence_links,
                              project_id, activity_id, construction_line_id):
    """Validate one Planning leaf; links are trusted only after DB readback.

    approved_evidence_links must be the CURRENT active approved evidence links,
    retrieved through scoped DB queries; each supplies link_id, organization /
    project/activity/line ids, state, accepted_quantity, reviewer_user_id,
    proposer_user_id and qa_inspection_id. Incomplete data makes output unknown.
    """
    errors = []
    plan = _number(planned_quantity)
    reported = _number(reported_quantity)
    verified = _number(verified_quantity)
    if not isinstance(unit, str) or not unit.strip():
        errors.append('Approved measurement unit required')
    if plan is None or plan <= 0:
        errors.append('Approved planned quantity must be positive')
    if any(x is None or x < 0 for x in (reported, verified)):
        errors.append('Reported and verified quantities must be finite and nonnegative')
    if plan is not None and verified is not None and verified > plan:
        errors.append('Verified quantity exceeds approved Planning quantity')
    if plan is not None and reported is not None and reported > plan:
        errors.append('Reported quantity exceeds approved Planning quantity')
    if verified is not None and reported is not None and verified > reported:
        errors.append('Verified quantity exceeds reported quantity')
    if project_id is None or activity_id is None or construction_line_id is None:
        errors.append('Canonical project, activity and Construction line identifiers required')
    if approved_evidence_links is None:
        errors.append('Authoritative approved QA links unavailable')
        approved_evidence_links = []
    if not isinstance(approved_evidence_links, (list, tuple)):
        errors.append('Approved QA link collection must be a list')
        approved_evidence_links = []
    accepted = Decimal(0)
    seen_links, seen_inspections = set(), set()
    for link in approved_evidence_links:
        if not isinstance(link, dict):
            errors.append('Invalid QA link'); continue
        lid, inspection = link.get('link_id'), link.get('qa_inspection_id')
        if lid is None or lid in seen_links or inspection is None or inspection in seen_inspections:
            errors.append('Duplicate or missing QA link / inspection identifier')
        seen_links.add(lid);seen_inspections.add(inspection)
        if any(link.get(key) != expected for key, expected in (
            ('project_id', project_id), ('activity_id', activity_id),
            ('construction_line_id', construction_line_id))):
            errors.append('QA link does not match canonical Planning and Construction scope')
        if link.get('state') != 'Approved':
            errors.append('Non-approved QA evidence cannot earn accepted progress')
        if not link.get('reviewer_user_id') or link.get('reviewer_user_id') == link.get('proposer_user_id'):
            errors.append('QA evidence requires independent reviewer')
        q = _number(link.get('accepted_quantity'))
        if q is None or q <= 0:
            errors.append('Approved QA link quantity must be positive')
        else:
            accepted += q
    if verified is not None and accepted > verified:
        errors.append('QA accepted quantity exceeds Construction verified quantity')
    if plan is not None and accepted > plan:
        errors.append('QA accepted quantity exceeds Planning quantity')
    errors = list(dict.fromkeys(errors))
    percentages = {m: None for m in MEASURES}
    if not errors:
        for label, q in zip(MEASURES, (reported, verified, accepted)):
            percentages[label] = float((q / plan * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    return {
        'valid': not errors, 'errors': errors, 'unit': unit,
        'planned_quantity': str(plan) if plan is not None else None,
        'reported_quantity': str(reported) if reported is not None else None,
        'verified_quantity': str(verified) if verified is not None else None,
        'qa_accepted_quantity': str(accepted) if not errors else None,
        'measurement': percentages,
        'earned_percent': None,
        'billing_eligible_quantity': None,
        'status': 'UNPUBLISHED_MEASUREMENT_PREVIEW',
    }
