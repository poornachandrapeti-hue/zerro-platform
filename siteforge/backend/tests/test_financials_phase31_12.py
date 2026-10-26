from decimal import Decimal
from unittest.mock import MagicMock
from pydantic import ValidationError
from app.domains.commercial_financials.models import FinanceSettlementReversal, FinancePaymentRecord, FinanceSupplierPaymentRecord
from app.domains.commercial_financials.router import SettlementReversalIn, active_finance_payments, router

def test_reversal_requires_reason_and_external_evidence():
    try:
        SettlementReversalIn(reason='short', evidence_reference='ref')
        assert False, 'Invalid reversal should fail'
    except ValidationError:
        pass
    assert SettlementReversalIn(reason='External bank return correction', evidence_reference='BANK-RETURN-0001')

def test_compensating_reversal_unique_and_original_unchanged():
    table=FinanceSettlementReversal.__table__
    assert table.name=='finance_settlement_reversals'
    assert any({'project_id','payment_type','payment_record_id'} == {col.name for col in c.columns}
               for c in table.constraints if hasattr(c,'columns'))
    assert 'original_amount' in table.columns
    assert 'reason' in table.columns

def test_reversal_endpoints_exist():
    paths={(r.path,tuple(sorted(r.methods))) for r in router.routes}
    assert any(path.endswith('/settlement-reversals/{payment_type}/{record_id}') and methods==('POST',) for path,methods in paths)
    assert any(path.endswith('/settlement-reversals') and methods==('GET',) for path,methods in paths)

def test_active_payment_filter_applies_to_both_categories():
    for model,kind in [(FinancePaymentRecord,'subcontract'),(FinanceSupplierPaymentRecord,'supplier')]:
        db=MagicMock()
        active_finance_payments(db,model,7,kind)
        call_args = [c.args[0] for c in db.query.call_args_list]
        assert any(arg is model for arg in call_args)
        assert any(arg is FinanceSettlementReversal.payment_record_id for arg in call_args)
        assert db.query.return_value.filter_by.called
