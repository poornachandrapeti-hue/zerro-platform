from app.domains.commercial_financials.gl_readback_contract import inspect_finance_ledger_readback


def sample():
    payload = dict(organization_id=1,project_id=2,proposal_id=3,proposal_revision=1,
                   source_movement_line_id=4,currency='INR',balanced_total='125.00')
    h = {'posting_status':'NOT_POSTED','idempotency_key':'finance-proposal:1:2:3:1',
         'payload_sha256':'sha', 'journal_proposal':payload}
    r = {**payload,'idempotency_key':h['idempotency_key'], 'payload_sha256':'sha',
         'status':'POSTED','posted_at':'2026-10-26T08:00:00Z','posted_by':10,
         'external_journal_id':'GL-1','total_debit':'125.00','total_credit':'125.00'}
    return h,r

class Adapter:
    def __init__(self, receipts):self.receipts=receipts;self.calls=[]
    def fetch_by_idempotency_key(self, **kwargs):self.calls.append(kwargs);return self.receipts


def test_unconfigured_fails_closed():
    h,_=sample(); r=inspect_finance_ledger_readback(h)
    assert not r['matches_handoff'] and not r['journal_posting_verified']
    assert 'finance_ledger_adapter_not_configured' in r['reasons']


def test_one_matching_still_not_certified():
    h,receipt=sample(); a=Adapter([receipt]); r=inspect_finance_ledger_readback(h,a)
    assert r['matches_handoff'] and not r['journal_posting_verified']
    assert a.calls == [dict(organization_id=1,project_id=2,idempotency_key=h['idempotency_key'])]


def test_duplicates_are_blocked():
    h,r=sample(); result=inspect_finance_ledger_readback(h,Adapter([r,r]))
    assert 'ambiguous_finance_ledger_postings' in result['reasons']


def test_missing_journal_blocked():
    h,_=sample(); assert 'finance_journal_not_found' in inspect_finance_ledger_readback(h,Adapter([]))['reasons']


def test_mismatched_ledger_blocked():
    h,r=sample(); r['project_id']=99
    assert not inspect_finance_ledger_readback(h,Adapter([r]))['matches_handoff']


def test_adapter_failure_redacted():
    class Broken:
        def fetch_by_idempotency_key(self,**kwargs):raise RuntimeError('secret token')
    h,_=sample(); out=inspect_finance_ledger_readback(h,Broken())
    assert out['reasons']==['finance_ledger_readback_failed'] and 'secret' not in str(out)


def test_invalid_scope_not_queried():
    h,_=sample();h['journal_proposal']['organization_id']=True;a=Adapter([])
    assert 'invalid_scope' in inspect_finance_ledger_readback(h,a)['reasons']
    assert not a.calls
