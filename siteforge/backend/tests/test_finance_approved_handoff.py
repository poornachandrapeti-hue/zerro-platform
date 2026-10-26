from datetime import datetime, timezone
from types import SimpleNamespace
from fastapi import HTTPException
import pytest
from app.domains.commercial_financials.movement_journal_proposals import build_approved_handoff


def proposal(**updates):
    d = dict(id=7, organization_id=2, project_id=3, proposal_revision=1,
             source_movement_line_id=19, currency='INR', description='Stock issue',
             status='Approved', approved_by=22,
             approved_at=datetime(2026,10,26,tzinfo=timezone.utc),
             lines=[{'cost_code_id':9,'debit':'100.00','credit':'0'},
                    {'cost_code_id':10,'debit':'0','credit':'100.00'}])
    d.update(updates)
    return SimpleNamespace(**d)

def test_handoff_deterministic_and_unposted():
    first=build_approved_handoff(proposal())
    assert first==build_approved_handoff(proposal())
    assert first['posting_status']=='NOT_POSTED'
    assert first['movement_valuation_certified'] is False
    assert first['journal_proposal']['balanced_total']=='100.00'
    assert len(first['payload_sha256'])==64

def test_changed_lines_change_digest():
    a=build_approved_handoff(proposal())
    b=build_approved_handoff(proposal(lines=[{'cost_code_id':9,'debit':'110','credit':'0'},{'cost_code_id':10,'debit':'0','credit':'110'}]))
    assert a['payload_sha256']!=b['payload_sha256']

@pytest.mark.parametrize('fields', [dict(status='Pending Review'), dict(approved_by=None),dict(approved_at=None)])
def test_unapproved_rejected(fields):
    with pytest.raises(HTTPException) as exc:build_approved_handoff(proposal(**fields))
    assert exc.value.status_code==409

def test_corrupt_stored_lines_rejected():
    with pytest.raises(HTTPException):build_approved_handoff(proposal(lines=[{'broken':'value'}]))

def test_unbalanced_lines_rejected():
    with pytest.raises(HTTPException):build_approved_handoff(proposal(lines=[{'cost_code_id':9,'debit':'100','credit':'0'},{'cost_code_id':10,'debit':'0','credit':'90'}]))
