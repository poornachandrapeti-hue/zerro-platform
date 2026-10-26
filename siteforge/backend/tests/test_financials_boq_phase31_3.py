"""Focused Phase 31.3 isolation tests; database-backed workflow tests still required."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from app.domains.commercial_financials.router import allowed_certification_amount, ContractInput, BoqInput


def test_invalid_contract_currency_rejected():
    with pytest.raises(Exception):
        ContractInput(number='C-1',contract_type='Subcontractor Work',counterparty_company_id=2,currency='IN',original_value='50')


def test_negative_boq_quantity_rejected():
    with pytest.raises(Exception):
        BoqInput(code='CV-1',description='Excavation',activity_id=3,quantity='-1',unit_rate='450')


def test_certification_cannot_exceed_qa_or_execution(monkeypatch):
    line=SimpleNamespace(activity_id=42,project_id=1,unit='m3',quantity=Decimal('2500'))
    activity=SimpleNamespace(id=42,measurement_method='Quantity',unit='m3')
    db=MagicMock()
    db.query.return_value.filter_by.return_value.one_or_none.return_value=activity
    monkeypatch.setattr('app.domains.commercial_financials.router.activity_measures',lambda *_:{'accepted_quantity':'500.000','verified_quantity':'450.000'})
    assert allowed_certification_amount(db,line)==Decimal('450.000')


def test_certification_missing_acceptance_fails_closed(monkeypatch):
    line=SimpleNamespace(activity_id=42,project_id=1,unit='m3',quantity=Decimal('2500'))
    db=MagicMock()
    db.query.return_value.filter_by.return_value.one_or_none.return_value=SimpleNamespace(id=42,measurement_method='Quantity',unit='m3')
    monkeypatch.setattr('app.domains.commercial_financials.router.activity_measures',lambda *_:{'accepted_quantity':None,'verified_quantity':'500.000'})
    with pytest.raises(HTTPException) as e:allowed_certification_amount(db,line)
    assert e.value.status_code==409
