"""Phase 9: reject tampered Finance handoffs before contacting a ledger adapter."""
import copy
import hashlib
import json
from app.domains.commercial_financials.phase9_handoff_integrity import validate_approved_handoff
from app.domains.commercial_financials.gl_readback_contract import inspect_finance_ledger_readback


def handoff():
    payload = dict(schema_version=1, organization_id=1, project_id=2, proposal_id=3,
        proposal_revision=1, source_movement_line_id=4, currency='INR',
        description='Stock issue', balanced_total='125.00', finance_approved_by=7,
        finance_approved_at='2026-10-26T08:00:00+00:00',
        lines=[dict(cost_code_id=8, debit='125.00', credit='0.00'),
               dict(cost_code_id=9, debit='0.00', credit='125.00')])
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    return dict(posting_status='NOT_POSTED', idempotency_key='finance-proposal:1:2:3:1',
                payload_sha256=digest, journal_proposal=payload)

class Adapter:
    def __init__(self): self.called = False
    def fetch_by_idempotency_key(self, **kwargs): self.called = True; return []


def test_intact_handoff_passes_integrity_gate():
    assert validate_approved_handoff(handoff()) == []


def test_tampered_total_blocked_before_adapter_call():
    h = handoff(); h['journal_proposal']['balanced_total'] = '999.00'; a = Adapter()
    result = inspect_finance_ledger_readback(h, a)
    assert 'invalid_payload_digest' in result['reasons']
    assert not a.called and not result['journal_posting_verified']


def test_forged_idempotency_key_blocked():
    h = handoff(); h['idempotency_key'] = 'finance-proposal:1:99:3:1'
    assert 'invalid_idempotency_key' in validate_approved_handoff(h)


def test_bad_amount_rejected_even_with_recalculated_digest():
    h=handoff(); h['journal_proposal']['lines'][0]['debit']='NaN'
    h['payload_sha256']=hashlib.sha256(json.dumps(h['journal_proposal'], sort_keys=True,
        separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    assert 'invalid_journal_lines' in validate_approved_handoff(h)


def test_no_adapter_never_claims_posted():
    result=inspect_finance_ledger_readback(handoff())
    assert result['reasons']==['finance_ledger_adapter_not_configured']
    assert not result['journal_posting_verified']
