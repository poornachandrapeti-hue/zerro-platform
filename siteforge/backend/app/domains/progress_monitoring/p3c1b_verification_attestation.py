"""P3C1B: explicit independent quantity-verification contract (no persistence).

Input MUST be fetched from an approved authoritative verification record by a
trusted repository adapter. Caller-provided JSON is never sufficient proof.
Results are non-publishable previews and must not be used by Billing/Finance.
"""
from decimal import Decimal, InvalidOperation


def _quantity(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def validate_quantity_attestation(*, baseline, construction, attestation):
    """Validate source-supplied records, returning a fail-closed measurement input.

    Baseline: result of P3C1 resolve_baseline_activity.
    Construction: P3B scoped construction evidence projection.
    Attestation: independently fetched persisted verification record; expected
      fields: verification_id, organization_id, project_id, activity_id,
      construction_line_id, report_id, baseline_revision_id, unit,
      verified_quantity, status, verifier_user_id, proposer_user_id,
      verification_reference, verified_at, source_revision.
    No claim is made that such a source table currently exists.
    """
    errors = []
    if not isinstance(baseline, dict) or baseline.get('status') != 'APPROVED_QUANTITY_FOUND':
        errors.append('Unambiguous approved Planning baseline required')
    if not isinstance(construction, dict) or construction.get('status') != 'SOURCE_READBACK_ONLY':
        errors.append('Scoped Construction source readback required')
    if not isinstance(attestation, dict):
        errors.append('Persisted independent verification attestation required')
    if errors:
        return _result(errors)

    for field in ('verification_id', 'verification_reference', 'verified_at', 'source_revision'):
        if not attestation.get(field):
            errors.append(f'Attestation {field} required')
    if attestation.get('status') != 'Approved':
        errors.append('Independent verification must be approved')
    if not attestation.get('verifier_user_id') or not attestation.get('proposer_user_id'):
        errors.append('Verification actor IDs required')
    elif attestation['verifier_user_id'] == attestation['proposer_user_id']:
        errors.append('Self verification prohibited')

    for key in ('organization_id', 'project_id', 'activity_id', 'construction_line_id', 'report_id'):
        if attestation.get(key) != construction.get(key):
            errors.append(f'Attestation {key} does not match Construction source')
    if attestation.get('baseline_revision_id') != baseline.get('baseline_revision_id'):
        errors.append('Attestation references a different baseline revision')
    if attestation.get('unit') != baseline.get('unit') or attestation.get('unit') != construction.get('unit'):
        errors.append('Measurement unit mismatch')
    if str(baseline.get('construction_activity_id')) != str(construction.get('activity_id')):
        errors.append('Planning-to-Construction activity mapping mismatch')

    approved = _quantity(baseline.get('approved_planning_quantity'))
    reported = _quantity(construction.get('reported_quantity'))
    verified = _quantity(attestation.get('verified_quantity'))
    accepted = _quantity(construction.get('qa_accepted_quantity'))
    if approved is None or approved <= 0 or reported is None or verified is None or accepted is None:
        errors.append('Finite approved, reported, verified and QA accepted quantities required')
    else:
        if reported > approved:
            errors.append('Reported quantity exceeds approved Planning quantity')
        if verified > reported:
            errors.append('Verified quantity exceeds reported quantity')
        if accepted > verified:
            errors.append('QA accepted quantity exceeds independently verified quantity')
        if verified > approved:
            errors.append('Verified quantity exceeds approved Planning quantity')

    if errors:
        return _result(list(dict.fromkeys(errors)))
    return {
        **_result([]),
        'status': 'VALIDATED_UNPUBLISHED_VERIFICATION_INPUT',
        'approved_planning_quantity': str(approved),
        'reported_quantity': str(reported),
        'construction_verified_quantity': str(verified),
        'qa_accepted_quantity': str(accepted),
        'baseline_revision_id': baseline['baseline_revision_id'],
        'verification_id': attestation['verification_id'],
        'verification_reference': attestation['verification_reference'],
        'source_revision': attestation['source_revision'],
        'project_id': construction['project_id'],
        'activity_id': construction['activity_id'],
        'construction_line_id': construction['construction_line_id'],
        'unit': baseline['unit'],
    }


def _result(errors):
    return {
        'valid': not errors,
        'errors': errors,
        'status': 'VERIFICATION_BLOCKED' if errors else 'VALIDATED_UNPUBLISHED_VERIFICATION_INPUT',
        'approved_planning_quantity': None,
        'reported_quantity': None,
        'construction_verified_quantity': None,
        'qa_accepted_quantity': None,
        'earned_percent': None,
        'billing_eligible_quantity': None,
        'published': False,
    }
