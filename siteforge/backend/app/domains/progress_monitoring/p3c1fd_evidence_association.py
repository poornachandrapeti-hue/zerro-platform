"""P3C1F-D: fail-closed QA inspection ↔ project attachment association gate.

Pure validation only; NO claim of authoritative linkage unless a trusted, persisted
association can be read independently of the API caller. Does not write progress,
certify billing, or change the QA/document canonical ledgers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class InspectionAttachmentAssociation:
    """Projection from an authorized, server-side persisted association readback.

    `trusted_persisted_record` is only set by a server adapter after checking an
    actual association record and caller scope. Never accept it from request JSON.
    """
    organization_id: int
    project_id: int
    activity_id: int
    inspection_id: int
    progress_line_id: int
    project_file_id: int
    stored_file_id: int
    content_digest: str
    association_status: str
    reviewer_user_id: int | None
    uploader_user_id: int | None
    trusted_persisted_record: bool = False
    revoked: bool | None = None


def _same_positive(a: Any, b: Any) -> bool:
    return type(a) is int and type(b) is int and a > 0 and a == b


def evaluate_association(*, verification: Mapping[str, Any],
                         qa_candidate: Mapping[str, Any],
                         attachment: Any,
                         association: InspectionAttachmentAssociation | None,
                         authorized: bool) -> dict:
    """Evaluate an association resolved by authenticated server-side readbacks.

    A successful attachment checksum and an approved QA result are necessary but
    not sufficient. Without a real reviewed association the result fails closed.
    """
    blockers: list[str] = []
    if authorized is not True:
        blockers.append('project_document_qa_permission_required')
    if verification.get('status') != 'Approved':
        blockers.append('quantity_verification_not_approved')
    if qa_candidate.get('quality_status') != 'Approved' or qa_candidate.get('quality_outcome') not in ('Accepted', 'Partially Accepted'):
        blockers.append('qa_not_accepted')
    if qa_candidate.get('candidate_only') is not True:
        blockers.append('qa_readback_contract_invalid')
    if getattr(attachment, 'attachment_integrity_verified', None) is not True:
        blockers.append('attachment_integrity_not_verified')
    for key in ('organization_id', 'project_id', 'activity_id'):
        if not _same_positive(verification.get(key), qa_candidate.get(key)):
            blockers.append('qa_' + key + '_mismatch')
    for key in ('organization_id', 'project_id'):
        if not _same_positive(verification.get(key), getattr(attachment, key, None)):
            blockers.append('attachment_' + key + '_mismatch')
    if association is None:
        blockers.append('reviewed_inspection_attachment_association_missing')
    else:
        if association.trusted_persisted_record is not True:
            blockers.append('association_not_server_verified')
        if association.association_status != 'Approved' or association.revoked is not False:
            blockers.append('association_not_active_and_approved')
        for key in ('organization_id', 'project_id', 'activity_id'):
            if not _same_positive(verification.get(key), getattr(association, key)):
                blockers.append('association_' + key + '_mismatch')
        if not _same_positive(qa_candidate.get('source_id'), association.inspection_id):
            blockers.append('association_inspection_mismatch')
        if not _same_positive(verification.get('progress_line_id'), association.progress_line_id):
            blockers.append('association_progress_line_mismatch')
        if not _same_positive(getattr(attachment, 'project_file_id', None), association.project_file_id):
            blockers.append('association_project_file_mismatch')
        if not _same_positive(getattr(attachment, 'stored_file_id', None), association.stored_file_id):
            blockers.append('association_stored_file_mismatch')
        if (not isinstance(association.content_digest, str)
                or association.content_digest.lower() != getattr(attachment, 'sha256', None)):
            blockers.append('association_digest_mismatch')
        if (association.reviewer_user_id is None or association.uploader_user_id is None
                or association.reviewer_user_id == association.uploader_user_id):
            blockers.append('association_review_not_independent')
    ready = not blockers
    return {
        'association_valid': ready,
        'blockers': sorted(set(blockers)),
        'authoritative_measurement_authenticated': False,
        'published': False,
        'billing_certified': False,
        'earned_progress': None,
    }
