from copy import deepcopy
from app.domains.progress_monitoring.p3c1f_evidence_authority import assess_site_evidence


def fixtures():
    v = dict(status='Approved', verification_reference='V-123', proposer_user_id=10, reviewer_user_id=11,
             verified_quantity='40.000', organization_id=1, project_id=2, report_id=3, progress_line_id=4,
             activity_id=5, source_revision='R2', unit='m3')
    e = dict(authority_verified=True, status='Approved', revoked=False, immutable_document_id='doc-1',
             revision='2', content_digest='sha256:abc', organization_id=1, project_id=2, report_id=3,
             progress_line_id=4, activity_id=5, verification_reference='V-123', source_revision='R2',
             unit='m3', measured_quantity='40.000', measured_by_user_id=12)
    return v,e


def check(v=None,e=None):
    bv,be=fixtures()
    return assess_site_evidence(verification=bv if v is None else v, evidence=be if e is None else e)


def test_matching_evidence_ready_but_unpublished():
    r=check(); assert r['evidence_authority_valid'] and not r['published'] and not r['billing_certified'] and r['earned_progress'] is None


def test_absent_evidence_blocks():
    assert 'authoritative_evidence_not_resolved' in check(e={})['blockers']


def test_string_reference_alone_blocks():
    assert not check(e={'verification_reference':'V-123'})['evidence_authority_valid']


def test_untrusted_authority_blocks():
    v,e=fixtures();e['authority_verified']=False;assert not check(v,e)['evidence_authority_valid']


def test_rejected_evidence_blocks():
    v,e=fixtures();e['status']='Pending';assert not check(v,e)['evidence_authority_valid']


def test_revocation_unknown_blocks():
    v,e=fixtures();del e['revoked'];assert not check(v,e)['evidence_authority_valid']


def test_revoked_blocks():
    v,e=fixtures();e['revoked']=True;assert not check(v,e)['evidence_authority_valid']


def test_cross_project_blocks():
    v,e=fixtures();e['project_id']=99;assert not check(v,e)['evidence_authority_valid']


def test_cross_line_blocks():
    v,e=fixtures();e['progress_line_id']=99;assert not check(v,e)['evidence_authority_valid']


def test_wrong_revision_blocks():
    v,e=fixtures();e['source_revision']='R1';assert not check(v,e)['evidence_authority_valid']


def test_missing_digest_blocks():
    v,e=fixtures();e['content_digest']='';assert not check(v,e)['evidence_authority_valid']


def test_missing_document_id_blocks():
    v,e=fixtures();e['immutable_document_id']='';assert not check(v,e)['evidence_authority_valid']


def test_insufficient_quantity_blocks():
    v,e=fixtures();e['measured_quantity']='39.99';assert not check(v,e)['evidence_authority_valid']


def test_nonfinite_quantity_blocks():
    v,e=fixtures();e['measured_quantity']='NaN';assert not check(v,e)['evidence_authority_valid']


def test_self_measured_blocks():
    v,e=fixtures();e['measured_by_user_id']=10;assert not check(v,e)['evidence_authority_valid']


def test_self_review_blocks():
    v,e=fixtures();v['reviewer_user_id']=10;assert not check(v,e)['evidence_authority_valid']


def test_unapproved_verification_blocks():
    v,e=fixtures();v['status']='Proposed';assert not check(v,e)['evidence_authority_valid']


def test_missing_source_identity_blocks():
    v,e=fixtures();del v['activity_id'];assert not check(v,e)['evidence_authority_valid']
