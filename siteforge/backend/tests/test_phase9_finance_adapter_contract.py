from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.domains.commercial_financials.movement_journal_proposals import build_approved_handoff
from app.domains.commercial_financials.phase9_finance_adapter_contract import (
    prepare_finance_submission, inspect_after_external_submission,
)


def handoff():
    p = SimpleNamespace(id=41, organization_id=2, project_id=3, proposal_revision=1,
                        source_movement_line_id=6, currency='USD', description='Material issue',
                        lines=[{'cost_code_id': 7, 'debit': '12.00', 'credit': '0.00'},
                               {'cost_code_id': 8, 'debit': '0.00', 'credit': '12.00'}],
                        status='Approved', approved_by=11,
                        approved_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    return build_approved_handoff(p)


def evidence():
    return dict(organization_id=2, project_id=3, source_movement_line_id=6,
                currency='USD', status='FINANCE_VERIFIED',
                costing_policy_approved=True, source_movement_posted=True,
                movement_cost='12.00')


def test_preparation_requires_evidence():
    result = prepare_finance_submission(handoff(), actor_id=22, source_evidence=None)
    assert result['submission_prepared'] is False
    assert result['gl_posted'] is False
    assert 'authoritative_valued_source_required' in result['reasons']


def test_preparation_rejects_same_approver():
    result = prepare_finance_submission(handoff(), actor_id=11, source_evidence=evidence())
    assert result['submission_prepared'] is False
    assert 'independent_posting_actor_required' in result['reasons']


def test_preparation_preserves_key_and_integrity():
    h = handoff()
    result = prepare_finance_submission(h, actor_id=22, source_evidence=evidence())
    assert result['submission_prepared'] is True
    assert result['idempotency_key'] == h['idempotency_key']
    assert result['payload_sha256'] == h['payload_sha256']
    assert result['posting_status'] == 'NOT_POSTED'
    assert result['gl_posted'] is False


def test_missing_adapter_fails_closed():
    result = inspect_after_external_submission(handoff(), adapter=None)
    assert result['matches_handoff'] is False
    assert result['journal_posting_verified'] is False
    assert result['gl_posted'] is False
    assert 'finance_ledger_adapter_not_configured' in result['reasons']


def test_matching_readback_cannot_self_certify():
    h = handoff()
    p = h['journal_proposal']
    class FakeAdapter:
        def fetch_by_idempotency_key(self, *, organization_id, project_id, idempotency_key):
            assert (organization_id, project_id, idempotency_key) == (2, 3, h['idempotency_key'])
            return [{**{k: p[k] for k in ('organization_id', 'project_id', 'proposal_id',
                       'proposal_revision', 'source_movement_line_id', 'currency')},
                     'idempotency_key': h['idempotency_key'],
                     'payload_sha256': h['payload_sha256'], 'status': 'POSTED',
                     'posted_at': '2026-10-26T09:00:00Z', 'posted_by': 22,
                     'external_journal_id': 'EXT-1', 'total_debit': '12.00',
                     'total_credit': '12.00'}]
    result = inspect_after_external_submission(h, adapter=FakeAdapter())
    assert result['matches_handoff'] is True
    assert result['journal_posting_verified'] is False
    assert result['gl_posted'] is False
