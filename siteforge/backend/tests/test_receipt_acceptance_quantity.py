import pytest
from app.domains.commercial_financials.receipt_acceptance_quantity import verify_receipt_acceptance_ceiling

def row(i, q, rid=7):
    return {'id': i, 'quantity': q, 'goods_receipt_line_id': rid}

def test_partial_acceptance():
    result = verify_receipt_acceptance_ceiling(receipt_line_id=7, received_quantity='10.000', accepted_lines=[row(1,'3'),row(2,'4')])
    assert result['remaining_unaccepted_quantity'] == '3.000'
    assert result['movement_valuation_verified'] is False

def test_exact_acceptance():
    assert verify_receipt_acceptance_ceiling(receipt_line_id=7, received_quantity=10, accepted_lines=[row(1,10)])['accepted_quantity'] == '10'

@pytest.mark.parametrize('received,lines', [
    (10, [row(1,7),row(2,4)]), (10,[row(1,6),row(1,2)]),
    (10,[row(1,1,8)]), (10,[]), (10,[row(1,'NaN')]),
    (0,[row(1,1)]), (10,[row(1,-1)]), (10,[row(True,1)]),
    (10,[row(1,float('inf'))]),
])
def test_bad_evidence_fails_closed(received,lines):
    with pytest.raises(ValueError):
        verify_receipt_acceptance_ceiling(receipt_line_id=7, received_quantity=received, accepted_lines=lines)
