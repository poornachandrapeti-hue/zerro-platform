from dataclasses import replace
from types import SimpleNamespace
from app.domains.progress_monitoring.p3c1fd_evidence_association import (
    InspectionAttachmentAssociation, evaluate_association,
)

V = dict(status='Approved', organization_id=1, project_id=2, activity_id=3, progress_line_id=4)
Q = dict(quality_status='Approved', quality_outcome='Accepted', candidate_only=True, source_id=5,
         organization_id=1, project_id=2, activity_id=3)
A = SimpleNamespace(attachment_integrity_verified=True, organization_id=1, project_id=2,
                    project_file_id=6, stored_file_id=7, sha256='a'*64)
L = InspectionAttachmentAssociation(1, 2, 3, 5, 4, 6, 7, 'a'*64, 'Approved', 10, 11, True, False)


def check(**kwargs):
    data = dict(verification=V, qa_candidate=Q, attachment=A, association=L, authorized=True)
    data.update(kwargs)
    return evaluate_association(**data)


def test_happy_path_only_association_valid_not_published():
    result = check()
    assert result['association_valid'] is True
    assert result['published'] is False and result['billing_certified'] is False
    assert result['authoritative_measurement_authenticated'] is False


def test_missing_link_fails_closed():
    assert 'reviewed_inspection_attachment_association_missing' in check(association=None)['blockers']


def test_untrusted_link_fails():
    assert not check(association=replace(L, trusted_persisted_record=False))['association_valid']


def test_cross_project_fails():
    assert not check(qa_candidate={**Q, 'project_id': 22})['association_valid']


def test_inspection_mismatch_fails():
    assert 'association_inspection_mismatch' in check(association=replace(L, inspection_id=99))['blockers']


def test_progress_line_mismatch_fails():
    assert not check(association=replace(L, progress_line_id=22))['association_valid']


def test_attachment_mismatch_fails():
    assert not check(association=replace(L, stored_file_id=22))['association_valid']


def test_digest_mismatch_fails():
    assert not check(association=replace(L, content_digest='b'*64))['association_valid']


def test_revoked_fails():
    assert not check(association=replace(L, revoked=True))['association_valid']


def test_pending_fails():
    assert not check(association=replace(L, association_status='Pending'))['association_valid']


def test_self_review_fails():
    assert not check(association=replace(L, reviewer_user_id=11))['association_valid']


def test_permission_denied_fails():
    assert not check(authorized=False)['association_valid']


def test_qa_not_approved_fails():
    assert not check(qa_candidate={**Q, 'quality_status': 'Draft'})['association_valid']


def test_unverified_attachment_fails():
    attachment = SimpleNamespace(**{**vars(A), 'attachment_integrity_verified': False})
    assert not check(attachment=attachment)['association_valid']


def test_unapproved_verification_fails():
    assert not check(verification={**V, 'status':'Proposed'})['association_valid']
