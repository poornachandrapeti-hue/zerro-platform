"""Draft creation must honor the same movement evidence gate as approval."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials import movement_journal_proposals as proposals
from tests.test_finance_journal_proposal_source_recheck import scenario

@pytest.mark.parametrize('changes', [
    {'quantity': '0'}, {'quantity': 'NaN'},
    {'org': 9}, {'code_project': 21}, {'kind':'Receipt'},
])
def test_draft_creation_cannot_bypass_source_validation(monkeypatch, changes):
    monkeypatch.setattr(proposals, 'guard', lambda *args: None)
    db, _ = scenario(**changes)
    body = proposals.NewProposal(
        source_movement_line_id=5, currency='INR', description='Sample journal proposal',
        lines=[proposals.JournalLine(cost_code_id=4,debit='15'),
               proposals.JournalLine(cost_code_id=4,credit='15')])
    with pytest.raises(HTTPException) as exc:
        proposals.create_proposal(20,body,SimpleNamespace(id=10,organization_id=7),db)
    assert exc.value.status_code in (409,422)
