import pytest
from app.domains.commercial_financials.receipt_lot_acceptance_coverage import verify_lot_acceptance_coverage


def lot(i, q, receipt=10):
    return {'id': i, 'goods_receipt_line_id': receipt, 'quantity': q}


def test_exact():
    result = verify_lot_acceptance_coverage(receipt_line_id=10, accepted_quantity='10', lots=[lot(1,'4'), lot(2,'6')])
    assert result['unassigned_accepted_quantity'] == '0'
    assert result['free_stock_verified'] is False


def test_partial():
    result = verify_lot_acceptance_coverage(receipt_line_id=10, accepted_quantity='9.5', lots=[lot(1,'3')])
    assert result['unassigned_accepted_quantity'] == '6.5'


@pytest.mark.parametrize('accepted,lots', [
    ('5', [lot(1,'6')]), ('10',[lot(1,'8'),lot(2,'4')]),
    ('10',[lot(1,'2'),lot(1,'3')]),('10',[lot(1,'2',99)]),
    ('10',[]), ('NaN',[lot(1,1)]), ('10',[lot(1,'Infinity')]),
    ('10',[lot(True,'3')]),('10',[lot(1,-1)]),
])
def test_reject(accepted,lots):
    with pytest.raises(ValueError):
        verify_lot_acceptance_coverage(receipt_line_id=10,accepted_quantity=accepted,lots=lots)
