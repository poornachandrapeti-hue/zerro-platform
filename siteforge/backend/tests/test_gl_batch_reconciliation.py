import pytest
from app.domains.commercial_financials.gl_batch_reconciliation import reconcile_handoff_batch


def example(n):
    payload = dict(organization_id=1,project_id=2,proposal_id=n,proposal_revision=1,
        source_movement_line_id=n,currency='INR',balanced_total='125.00')
    h = {'posting_status':'NOT_POSTED','idempotency_key':f'finance-proposal:1:2:{n}:1',
         'payload_sha256':f'sha{n}','journal_proposal':payload}
    r = {**payload,'idempotency_key':h['idempotency_key'],
         'payload_sha256':h['payload_sha256'],'status':'POSTED',
         'posted_at':'2026-10-26T08:00:00Z','posted_by':10,
         'external_journal_id':f'GL-{n}','total_debit':'125.00','total_credit':'125.00'}
    return h,r

class Adapter:
    def __init__(self, receipts): self.receipts=receipts; self.calls=[]
    def fetch_by_idempotency_key(self, **kwargs):
        self.calls.append(kwargs)
        return self.receipts.get(kwargs['idempotency_key'], [])

def test_valid_readback_remains_uncertified():
    h,r=example(1); result=reconcile_handoff_batch([h],Adapter({h['idempotency_key']:[r]}))
    assert result['matched_readbacks']==1 and result['journal_posting_verified'] is False

def test_duplicate_handoffs_do_not_query():
    h,_=example(1); adapter=Adapter({})
    out=reconcile_handoff_batch([h,h],adapter)
    assert out['exceptions']==2 and not adapter.calls

def test_cross_handoff_reused_external_journal_rejected():
    h1,r1=example(1); h2,r2=example(2); r2['external_journal_id']=r1['external_journal_id']
    adapter=Adapter({h1['idempotency_key']:[r1],h2['idempotency_key']:[r2]})
    out=reconcile_handoff_batch([h1,h2],adapter)
    assert out['exceptions']==2
    assert all(row['reasons']==['duplicate_external_journal_reference'] for row in out['rows'])

def test_missing_provider_fails_closed():
    h,_=example(1); out=reconcile_handoff_batch([h])
    assert out['exceptions']==1 and not out['movement_valuation_certified']

@pytest.mark.parametrize('invalid', [[],[{}],['bad'],[example(1)[0]]*101])
def test_bad_batches_rejected(invalid):
    with pytest.raises(ValueError): reconcile_handoff_batch(invalid)
