"""P2 construction-to-QA evidence gate; pure validation, no DB writes.

Caller must supply authoritative construction and QA readbacks. This helper never
converts reported or verified work to QA accepted work without a matching,
independently approved inspection. It does not certify billing or progress.
"""
from decimal import Decimal, InvalidOperation


def _quantity(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        val = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None
    return val if val.is_finite() and val >= 0 else None


def evaluate_qa_acceptance(construction, inspections, *, organization_id, project_id):
    """Return bounded accepted-quantity evidence, or fail closed.

    Required construction fields: organization_id, project_id, activity_id,
    report_id, status='Approved', verified_quantity, verifier_id.
    Required inspection fields: organization_id, project_id, activity_id,
    construction_report_id, inspection_id, status='Approved', accepted_quantity,
    reviewer_id, inspection_evidence_id. Rejected/pending inspections do not count.
    """
    reasons = []
    def reject(msg):
        if msg not in reasons:
            reasons.append(msg)

    if not isinstance(construction, dict) or not isinstance(inspections, (list, tuple)):
        return {'eligible': False, 'accepted_quantity': None, 'accepted_percent': None,
                'source_inspection_ids': [], 'billing_certified': False,
                'reasons': ['Invalid authoritative source input']}
    if not organization_id or not project_id:
        reject('Missing project and organization scope')
    for field, expected in [('organization_id', organization_id), ('project_id', project_id)]:
        if construction.get(field) != expected:
            reject('Construction source scope mismatch')
    if not construction.get('report_id') or not construction.get('activity_id'):
        reject('Missing authoritative Construction identifiers')
    if construction.get('status') != 'Approved' or not construction.get('verifier_id'):
        reject('Construction report has not been independently verified')
    verified = _quantity(construction.get('verified_quantity'))
    if verified is None:
        reject('Invalid verified Construction quantity')

    total = Decimal('0')
    seen = set()
    used = []
    for item in inspections:
        if not isinstance(item, dict):
            reject('Malformed QA inspection evidence')
            continue
        if item.get('status') != 'Approved':
            continue
        if (item.get('organization_id') != organization_id or
            item.get('project_id') != project_id or
            item.get('activity_id') != construction.get('activity_id') or
            item.get('construction_report_id') != construction.get('report_id')):
            reject('Approved QA inspection does not match Construction source and project')
            continue
        inspection_id = item.get('inspection_id')
        if not inspection_id or inspection_id in seen:
            reject('Duplicate or missing QA inspection ID')
            continue
        seen.add(inspection_id)
        if not item.get('inspection_evidence_id'):
            reject('Missing authoritative QA acceptance evidence')
        reviewer = item.get('reviewer_id')
        if not reviewer or reviewer == construction.get('verifier_id'):
            reject('Independent QA review evidence missing')
        qty = _quantity(item.get('accepted_quantity'))
        if qty is None:
            reject('Invalid QA accepted quantity')
        else:
            total += qty
        used.append(inspection_id)
    if not used:
        reject('No approved QA acceptance linked to verified Construction report')
    if verified is not None and total > verified:
        reject('QA acceptance exceeds verified Construction quantity')
    if reasons:
        return {'eligible': False, 'accepted_quantity': None, 'accepted_percent': None,
                'source_inspection_ids': [], 'billing_certified': False, 'reasons': reasons}
    # No scope quantity supplied here: accepted percentage remains unavailable.
    return {'eligible': True, 'accepted_quantity': format(total, 'f'),
            'accepted_percent': None, 'source_inspection_ids': used,
            'billing_certified': False, 'reasons': []}
