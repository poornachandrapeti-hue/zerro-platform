"""P3C1F-C: fail-closed project attachment readback for site evidence candidates.

Call only after existing authenticated progress project permission checks.
No quantity authority or certification is inferred from a project file.
"""
from dataclasses import dataclass
import hashlib
import hmac


class EvidenceCandidateError(ValueError):
    pass


@dataclass(frozen=True)
class AttachmentCandidate:
    project_file_id: int
    stored_file_id: int
    organization_id: int
    project_id: int
    sha256: str
    size: int
    attachment_integrity_verified: bool
    physical_measurement_authenticated: bool = False
    eligible_for_publication: bool = False
    eligible_for_billing: bool = False


def read_project_attachment_candidate(db, *, organization_id: int, project_id: int,
                                      project_file_id: int, authorized: bool) -> AttachmentCandidate:
    """Read existing canonical storage metadata and verify bytes within server-side storage.

    `authorized` MUST be computed by the server-side RBAC/project/company scope layer.
    Forbids substituting a client-provided file checksum or document status.
    """
    if not authorized:
        raise EvidenceCandidateError('Not authorized for project evidence readback')
    if any(not isinstance(x, int) or isinstance(x, bool) or x <= 0
           for x in (organization_id, project_id, project_file_id)):
        raise EvidenceCandidateError('Invalid project evidence scope')

    from app.domains.engineering_documents.models import ProjectFile, StoredFile
    from app.domains.engineering_documents.files import read_file

    link = db.get(ProjectFile, project_file_id)
    if link is None or link.project_id != project_id or link.active is not True:
        raise EvidenceCandidateError('Project attachment is missing or inactive')
    record = db.get(StoredFile, link.file_id)
    if record is None or record.organization_id != organization_id:
        raise EvidenceCandidateError('Attachment organization mismatch')
    if record.scan_status != 'available':
        raise EvidenceCandidateError('Attachment is not available')
    if not isinstance(record.sha256, str) or len(record.sha256) != 64:
        raise EvidenceCandidateError('Invalid stored digest')
    if not isinstance(record.size, int) or record.size <= 0:
        raise EvidenceCandidateError('Invalid file size')
    if record.storage_name != record.sha256:
        raise EvidenceCandidateError('Unexpected storage identity')

    try:
        payload = read_file(record)
    except Exception as exc:
        raise EvidenceCandidateError('Unable to access stored attachment') from exc
    if len(payload) != record.size or not hmac.compare_digest(
        hashlib.sha256(payload).hexdigest(), record.sha256.lower()
    ):
        raise EvidenceCandidateError('Stored attachment digest or size mismatch')
    return AttachmentCandidate(
        project_file_id=link.id, stored_file_id=record.id,
        organization_id=record.organization_id, project_id=link.project_id,
        sha256=record.sha256.lower(), size=record.size,
        attachment_integrity_verified=True,
    )
