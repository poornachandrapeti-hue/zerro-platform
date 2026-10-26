"""Static database contract assertions; integration tests follow in P2C2B."""
from app.domains.progress_monitoring.p2c2_link_models import ProgressEvidenceLink, ProgressEvidenceLinkEvent


def test_links_have_explicit_authoritative_sources():
    cols = ProgressEvidenceLink.__table__.columns.keys()
    for key in ('organization_id','project_id','report_id','progress_line_id','inspection_request_id','binding_evidence_ref','accepted_quantity'):
        assert key in cols


def test_link_is_not_a_progress_ledger():
    cols = ProgressEvidenceLink.__table__.columns.keys()
    assert 'earned_quantity' not in cols
    assert 'billing_amount' not in cols


def test_link_has_independent_review_fields():
    cols = ProgressEvidenceLink.__table__.columns.keys()
    assert {'created_by','reviewed_by','review_note','reviewed_at','status','version'} <= set(cols)


def test_audit_has_actor_and_action():
    assert {'link_id','actor_id','action','created_at','project_id'} <= set(ProgressEvidenceLinkEvent.__table__.columns.keys())


def test_source_pair_unique():
    assert any(getattr(c,'name',None) == 'uq_progress_evidence_pair' for c in ProgressEvidenceLink.__table__.constraints)
