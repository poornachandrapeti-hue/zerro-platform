"""Financial evidence must reject unsupported categories, malformed currencies, and cross-project access."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.router import financial_evidence_data

class FakeDB:
    def __init__(self, org=42): self.org=org
    def get(self, model, pk): return SimpleNamespace(organization_id=self.org,code='ZSP-001') if pk==3 else None

@pytest.mark.parametrize('category', ['payments','payroll','supplier_bank_accounts','../../all',''])
def test_unsupported_evidence_category_fails_closed(category):
    with pytest.raises(HTTPException) as exc:
        financial_evidence_data(FakeDB(),3,42,category)
    assert exc.value.status_code==422

@pytest.mark.parametrize('currency', ['inr','INR!', 'USD;DROP','EU','1234'])
def test_invalid_currency_fails_closed(currency):
    with pytest.raises(HTTPException) as exc:
        financial_evidence_data(FakeDB(),3,42,'budgets',currency)
    assert exc.value.status_code==422

def test_cross_organization_financial_evidence_denied():
    with pytest.raises(HTTPException) as exc:
        financial_evidence_data(FakeDB(9),3,42,'budgets','INR')
    assert exc.value.status_code==404
