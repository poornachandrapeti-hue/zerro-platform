from copy import deepcopy
import pytest
from app.domains.commercial_financials.phase9_landed_cost_reconciliation import reconcile_landed_cost_batches

B = [{'batch_id': 7, 'amount': '11.01', 'currency': 'INR', 'independently_approved': True},
     {'batch_id': 8, 'amount': '4.00', 'currency': 'INR', 'independently_approved': True}]
A = [{'batch_id': 7, 'receipt_line_id': 11, 'amount': '5.50', 'currency': 'INR'},
     {'batch_id': 7, 'receipt_line_id': 12, 'amount': '5.51', 'currency': 'INR'},
     {'batch_id': 8, 'receipt_line_id': 12, 'amount': '4.00', 'currency': 'INR'}]

def run(b=None, a=None, ids=None):
    return reconcile_landed_cost_batches(batches=B if b is None else b,
        allocations=A if a is None else a, receipt_line_ids=[11,12] if ids is None else ids,currency='INR')

def test_conserves_each_batch_and_keeps_provenance():
    out=run()
    assert out['allocated_total']=='15.01'
    assert out['batch_count']==2
    assert {(x['batch_id'],x['receipt_line_id']) for x in out['allocations']} == {(7,11),(7,12),(8,12)}
    assert not out['journal_posting_verified']
    assert not out['movement_valuation_verified']

def test_order_independent():
    assert run(a=list(reversed(A)),b=list(reversed(B)),ids=[12,11])==run()

@pytest.mark.parametrize('changes',[
    {'a':A[:-1]}, {'a':A+[A[0]]},
    {'a':[dict(A[0],amount='5.49'),*A[1:]]},
    {'a':[dict(A[0],amount='5.501'),*A[1:]]},
    {'a':[dict(A[0],amount='NaN'),*A[1:]]},
    {'a':[dict(A[0],currency='USD'),*A[1:]]},
    {'a':[dict(A[0],receipt_line_id=99),*A[1:]]},
    {'a':[dict(A[0],batch_id=42),*A[1:]]},
    {'b':[dict(B[0],independently_approved=False),B[1]]},
    {'b':[dict(B[0],amount='11.02'),B[1]]},
    {'b':B+[B[0]]}, {'ids':[11,11,12]}, {'ids':[11]},
    {'b':[]}, {'a':[]},
])
def test_fail_closed(changes):
    with pytest.raises(ValueError):run(**changes)
