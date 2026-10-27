"""P3C1F-A: fail-closed authority gate for site quantity-verification evidence.

Inputs must be obtained from authenticated, scoped canonical readbacks, NOT request JSON.
This function does not retrieve documents, authenticate users, certify billing, or write data.
Missing independent evidence remains blocked until an approved source adapter exists.
"""
from decimal import Decimal, InvalidOperation
from typing import Mapping, Any

APPROVED = frozenset({'Approved'})


def _pos(value: Any) -> Decimal | None:
    try:
        v = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None
    return v if v.is_finite() and v > 0 else None


def assess_site_evidence(*, verification: Mapping[str, Any], evidence: Mapping[str, Any] | None) -> dict:
    """Assess a server-resolved evidence record against a persisted verification.

    The caller MUST separately authorize project/document access and verify the
    evidence comes from an approved authoritative repository (not user-submitted JSON).
    """
    reasons = []
    if verification.get('status') != 'Approved':
        reasons.append('verification_not_approved')
    if not verification.get('verification_reference'):
        reasons.append('missing_verification_reference')
    proposer = verification.get('proposer_user_id')
    reviewer = verification.get('reviewer_user_id')
    if proposer is None or reviewer is None or str(proposer) == str(reviewer):
        reasons.append('verification_not_independently_reviewed')
    vqty = _pos(verification.get('verified_quantity'))
    if vqty is None:
        reasons.append('invalid_verification_quantity')

    if not evidence:
        reasons.append('authoritative_evidence_not_resolved')
    else:
        if evidence.get('authority_verified') is not True:
            reasons.append('evidence_authority_not_verified')
        if evidence.get('status') not in APPROVED:
            reasons.append('evidence_not_approved')
        if evidence.get('revoked') is not False:
            reasons.append('evidence_revocation_unknown_or_true')
        if not evidence.get('immutable_document_id') or not evidence.get('revision'):
            reasons.append('missing_immutable_evidence_identity')
        if not evidence.get('content_digest'):
            reasons.append('missing_evidence_digest')
        for key in ('organization_id', 'project_id', 'report_id', 'progress_line_id', 'activity_id'):
            if verification.get(key) is None or str(verification.get(key)) != str(evidence.get(key)):
                reasons.append('evidence_' + key + '_mismatch')
        if str(verification.get('verification_reference')) != str(evidence.get('verification_reference')):
            reasons.append('evidence_reference_mismatch')
        if str(verification.get('source_revision')) != str(evidence.get('source_revision')):
            reasons.append('evidence_source_revision_mismatch')
        if verification.get('unit') != evidence.get('unit'):
            reasons.append('evidence_unit_mismatch')
        eqty = _pos(evidence.get('measured_quantity'))
        if eqty is None or vqty is None or eqty < vqty:
            reasons.append('insufficient_independently_measured_quantity')
        if evidence.get('measured_by_user_id') is None or str(evidence.get('measured_by_user_id')) == str(proposer):
            reasons.append('evidence_measurement_not_independent')
    ready = not reasons
    return {
        'evidence_authority_valid': ready,
        'blockers': sorted(set(reasons)),
        'published': False,
        'billing_certified': False,
        'earned_progress': None,
    }
