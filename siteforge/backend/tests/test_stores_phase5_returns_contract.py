from decimal import Decimal
from pathlib import Path
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.material_returns import validate_return_quantity, ReturnRequestIn, ReturnReceiptIn, ReturnQAIn

def test_return_cannot_exceed_received():
    with pytest.raises(HTTPException) as exc:
        validate_return_quantity(Decimal('3'),Decimal('4'))
    assert exc.value.status_code == 422

def test_return_rejects_zero_and_nonfinite():
    for x in ['0','-1','NaN','Infinity']:
        with pytest.raises(HTTPException):
            validate_return_quantity(Decimal('3'), Decimal(x))

def test_return_allows_partial():
    assert validate_return_quantity('5.000','2.500') is None

def test_return_request_condition_is_limited():
    with pytest.raises(Exception):
        ReturnRequestIn(handover_id=1,quantity=1,condition='Scrap',reason='Material surplus')

def test_receipt_requires_evidence():
    with pytest.raises(Exception):
        ReturnReceiptIn(version=1,received_quantity=1,evidence='x')

def test_qa_disposition_is_controlled():
    with pytest.raises(Exception):
        ReturnQAIn(version=1,decision='Released to Stock',evidence='Reviewed OK')

def test_never_posts_inventory():
    root=Path(__file__).resolve().parents[1]
    source=(root/'app/domains/stores_inventory/material_returns.py').read_text()
    assert 'StockPosting(' not in source and 'StockBalance(' not in source
    assert "'quality.edit'" in source

def test_partner_route_is_company_scoped():
    root=Path(__file__).resolve().parents[1]
    source=(root/'app/domains/partner_portal/material_issue_requests.py').read_text()
    assert "@router.post('/material-returns'" in source
    assert 'StoresMaterialRequest.requester_company_id == company.id' in source
