from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from app.domains.commercial_financials.phase9_command_center_feed import build_finance_proposal_snapshot


def row(**kwargs):
    return SimpleNamespace(id=1, source_movement_line_id=10, proposal_revision=1,
        organization_id=7, project_id=12, status='Approved', approved_by=2,
        approved_at=datetime.now(timezone.utc), **kwargs)


def test_approved_is_never_accounted_posting():
    d=build_finance_proposal_snapshot(organization_id=7, project_id=12, rows=[row()])
    assert d['status_counts']=={'Approved':1}
    assert d['gl_posted_verified'] is False
    assert d['complete_history'] is False
    assert 'amount' not in d['proposal_records'][0]


def test_scoped_records_and_bounded():
    with pytest.raises(ValueError): build_finance_proposal_snapshot(organization_id=7, project_id=13, rows=[row()])
    with pytest.raises(ValueError): build_finance_proposal_snapshot(organization_id=7, project_id=12, rows=[row()]*201)


def test_invalid_approval_evidence():
    x=row();x.approved_at=None
    with pytest.raises(ValueError): build_finance_proposal_snapshot(organization_id=7, project_id=12, rows=[x])
