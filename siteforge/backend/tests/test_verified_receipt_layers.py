import pytest
from app.domains.commercial_financials.verified_receipt_layers import consolidate_receipt_layers

R=[{'id':10,'quantity':'10','currency':'INR'}]
A=[{'receipt_line_id':10,'allocation_id':1,'quantity':'10','unit_cost':'50','currency':'INR','independently_approved':True}]
L=[{'receipt_line_id':10,'batch_id':3,'amount':'20','currency':'INR','independently_approved':True}]

def calculate(r=R,a=A,l=L):return consolidate_receipt_layers(receipts=r,invoice_allocations=a,landed_allocations=l)

def test_complete_preview():
    row=calculate()[0]
    assert row['combined_receipt_cost_preview']=='520'
    assert row['unit_cost_preview']=='52'
    assert row['movement_valuation_verified'] is False

def test_partial_blocked():
    row=calculate(a=[dict(A[0],quantity='8')])[0]
    assert row['combined_receipt_cost_preview'] is None
    assert row['status']=='INCOMPLETE_INVOICE_ALLOCATION'

@pytest.mark.parametrize('field,value', [('quantity','11'),('unit_cost','NaN'),('currency','USD'),('independently_approved',False)])
def test_invalid_invoice(field,value):
    with pytest.raises(ValueError):calculate(a=[dict(A[0],**{field:value})])

def test_duplicate_invoice():
    with pytest.raises(ValueError):calculate(a=A+A)

def test_unapproved_landed():
    with pytest.raises(ValueError):calculate(l=[dict(L[0],independently_approved=False)])

def test_duplicate_landed():
    with pytest.raises(ValueError):calculate(l=L+L)

def test_empty_receipts():
    with pytest.raises(ValueError):calculate(r=[])
