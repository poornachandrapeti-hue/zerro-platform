from pathlib import Path
from fastapi import HTTPException
from app.domains.stores_inventory.scrap_disposal import (
    ScrapProposalIn, ScrapReviewIn, ScrapDisposalEvidenceIn, _require_classification,
    router,
)

def test_classification_validation():
    for name in ('Damaged','Obsolete','Expired','Unserviceable','SurplusScrap'):
        _require_classification(name)
    try:
        _require_classification('AvailableForIssue')
    except HTTPException as error:
        assert error.status_code == 422
    else:
        raise AssertionError('invalid classification allowed')

def test_input_contract():
    item=ScrapProposalIn(reference='SCR-001',receipt_lot_id=5,quantity='2.000',classification='Damaged',reason='Damaged in storage',evidence='Photo ref 1')
    assert str(item.quantity)=='2.000'
    assert ScrapReviewIn(version=1,decision='Reject',evidence='Review note').version==1
    assert ScrapDisposalEvidenceIn(version=1,disposal_reference='DS-001',evidence='Signed manifest').version==1

def test_stock_writes_absent_and_routes_present():
    source=Path(__file__).resolve().parents[1]/'app/domains/stores_inventory/scrap_disposal.py'
    text=source.read_text()
    assert 'StockPosting(' not in text and 'StockBalance(' not in text
    routes={r.path for r in router.routes}
    assert '/api/projects/{pid}/stores/scrap-cases' in routes
    assert '/api/projects/{pid}/stores/scrap-cases/{sid}/review' in routes
    assert '/api/projects/{pid}/stores/scrap-cases/{sid}/disposal-evidence' in routes
