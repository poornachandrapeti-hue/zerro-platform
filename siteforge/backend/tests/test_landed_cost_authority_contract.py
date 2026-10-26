"""Focused contract tests; live DB migration/authorization tests remain pending."""
import pytest
from pydantic import ValidationError
from app.domains.commercial_financials.landed_cost_authority import NewBatch, CATEGORIES, serialize
from app.domains.commercial_financials.models import FinanceLandedCostBatch, FinanceLandedCostReceiptLink

def good(**patch):
    data=dict(document_ref='FRT-001',source_document='Freight Invoice 001',category='FREIGHT',currency='INR',amount='150.25',goods_receipt_line_ids=[3,4])
    data.update(patch)
    return data

def test_positive_money_and_cent_precision():
    for amount in ['0','-1','1.001']:
        with pytest.raises(ValidationError):NewBatch(**good(amount=amount))

def test_currency_and_receipts_required():
    for patch in [dict(currency='USD1'),dict(goods_receipt_line_ids=[]),dict(document_ref='a')]:
        with pytest.raises(ValidationError):NewBatch(**good(**patch))

def test_explicit_charge_categories():
    assert {'FREIGHT','INSURANCE','HANDLING','TRANSPORT'} <= CATEGORIES

def test_models_do_not_create_stock_or_journal_entries():
    assert FinanceLandedCostBatch.__tablename__ == 'finance_landed_cost_batches'
    assert FinanceLandedCostReceiptLink.__tablename__ == 'finance_landed_cost_receipt_links'
    assert not any(col.name in {'stock_posting_id','journal_entry_id'} for col in FinanceLandedCostBatch.__table__.columns)
