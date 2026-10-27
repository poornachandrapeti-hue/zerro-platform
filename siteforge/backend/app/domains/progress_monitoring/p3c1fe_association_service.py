"""Fail-closed association state transitions. Use server-fetched, scoped source evidence.

Service-only: no new HTTP routes. Caller must authenticate and authorize actor.
Caller owns transaction commit. DB source locks are obtained for approval.
"""
from datetime import datetime, timezone
import re
from sqlalchemy import select, text
from .p3c1fe_association_models import ProgressInspectionAttachmentLink as Link, ProgressInspectionAttachmentEvent as Event

class AssociationViolation(ValueError):
    pass

def _positive(*ids):
    return all(type(v) is int and v > 0 for v in ids)

def check_source(source, *, organization_id, project_id, activity_id, inspection_id, line_id, file_id, stored_file_id, digest):
    """`source` is a trusted server-side readback, never a user request body."""
    if not isinstance(source, dict) or source.get('server_verified') is not True:
        raise AssociationViolation('Server-verified QA/document readback required')
    fields = dict(organization_id=organization_id,project_id=project_id,activity_id=activity_id,
                  inspection_id=inspection_id,progress_line_id=line_id,project_file_id=file_id,stored_file_id=stored_file_id)
    if any(source.get(k)!=v for k,v in fields.items()):
        raise AssociationViolation('Source scope or identity mismatch')
    if source.get('qa_status')!='Approved' or source.get('qa_outcome') not in ('Accepted','Partially Accepted'):
        raise AssociationViolation('QA approval missing')
    if source.get('attachment_integrity_verified') is not True or source.get('digest')!=digest:
        raise AssociationViolation('File integrity mismatch')
    if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest):
        raise AssociationViolation('Invalid canonical SHA-256')

def propose(db, *, actor_id, authorized, source, organization_id, project_id, activity_id,
            inspection_id, progress_line_id, project_file_id, stored_file_id, content_digest):
    if authorized is not True or not _positive(actor_id, organization_id,project_id,activity_id,inspection_id,
                              progress_line_id,project_file_id,stored_file_id):
        raise AssociationViolation('Unauthorized or invalid identity')
    check_source(source,organization_id=organization_id,project_id=project_id,activity_id=activity_id,
                 inspection_id=inspection_id,line_id=progress_line_id,file_id=project_file_id,
                 stored_file_id=stored_file_id,digest=content_digest)
    record=Link(organization_id=organization_id,project_id=project_id,activity_id=activity_id,
                inspection_id=inspection_id,progress_line_id=progress_line_id,project_file_id=project_file_id,
                stored_file_id=stored_file_id,content_digest=content_digest,proposer_user_id=actor_id,
                status='Proposed',version=1)
    db.add(record);db.flush()
    db.add(Event(link_id=record.id,organization_id=organization_id,project_id=project_id,
                 action='Proposed',actor_user_id=actor_id))
    return record

def decide(db, *, link_id, actor_id, organization_id, project_id, authorized, expected_version,
           action, source=None, note=''):
    if authorized is not True or not _positive(link_id,actor_id,organization_id,project_id,expected_version):
        raise AssociationViolation('Unauthorized or invalid decision')
    if action not in ('Approved','Rejected','Revoked'):
        raise AssociationViolation('Unknown action')
    record=db.execute(select(Link).where(Link.id==link_id,Link.organization_id==organization_id,
                Link.project_id==project_id).with_for_update()).scalar_one_or_none()
    if record is None:raise AssociationViolation('Association missing in project')
    if record.version!=expected_version:raise AssociationViolation('Stale version')
    if actor_id==record.proposer_user_id:raise AssociationViolation('Self review forbidden')
    if action in ('Approved','Rejected') and record.status!='Proposed':
        raise AssociationViolation('Proposal no longer pending')
    if action=='Revoked' and record.status!='Approved':
        raise AssociationViolation('Only active approval can be revoked')
    if action=='Approved':
        # Serialize approval decisions for this project, including zero-existing-row races.
        # PostgreSQL transaction-scoped advisory lock; no lock survives commit/rollback.
        db.execute(text('SELECT pg_advisory_xact_lock(:namespace, :project)'),
                   {'namespace': 34127, 'project': project_id})
        check_source(source,organization_id=record.organization_id,project_id=record.project_id,
            activity_id=record.activity_id,inspection_id=record.inspection_id,line_id=record.progress_line_id,
            file_id=record.project_file_id,stored_file_id=record.stored_file_id,digest=record.content_digest)
        # Source rows rechecked by trusted adapter inside same transaction.
        # Prevent concurrent approvals from sharing inspection/line or file evidence.
        siblings=db.execute(select(Link.id).where(Link.organization_id==organization_id,
           Link.project_id==project_id,Link.id!=record.id,Link.status=='Approved',
           (Link.inspection_id==record.inspection_id)|(Link.project_file_id==record.project_file_id)).with_for_update()).first()
        if siblings:raise AssociationViolation('Conflicting approved association')
    record.status=action;record.reviewer_user_id=actor_id;record.review_note=str(note)[:2000]
    record.reviewed_at=datetime.now(timezone.utc);record.version+=1
    db.add(Event(link_id=record.id,organization_id=organization_id,project_id=project_id,
                 action=action,actor_user_id=actor_id,note=record.review_note))
    db.flush()
    return record
