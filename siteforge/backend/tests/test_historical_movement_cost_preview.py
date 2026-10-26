from datetime import datetime, timezone, timedelta
import pytest
from app.domains.commercial_financials.historical_movement_cost_preview import preview_historical_issue

T = datetime(2026, 1, 1, tzinfo=timezone.utc)
def event(i, kind, qty, rid=10, **extra):
    return dict(id=i, kind=kind, quantity=str(qty), receipt_line_id=rid, material_id=1,
                unit='KG', warehouse_id=1, organization_id=2, project_id=3,
                occurred_at=T + timedelta(seconds=i), **extra)
def run(events, costs=None, issue=4, method='FIFO'):
    return preview_historical_issue(organization_id=2, project_id=3, events=events,
       issue_event_id=issue, verified_unit_costs=costs if costs is not None else {10:'50',11:'80'},
       method=method, currency='INR')

def base():
    return [event(1,'RECEIPT',10),event(2,'RECEIPT',20,11),event(3,'ISSUE',4),event(4,'ISSUE',15,11)]

def test_fifo_uses_as_of_balances():
    result=run(base())
    assert result['unposted_amount']=='1020.00' # 6*50+9*80
    assert result['financial_authority_verified'] is False
    assert result['journal_posting_verified'] is False

def test_average_uses_as_of_balances():
    result=run(base(),method='WEIGHTED_AVERAGE')
    assert result['unposted_amount']=='1096.15' # (6*50+20*80)/26 * 15

def test_return_restores_original_receipt_layer():
    events=[event(1,'RECEIPT',10),event(2,'ISSUE',6),event(3,'RETURN',2,source_issue_event_id=2),event(4,'ISSUE',6)]
    assert run(events,costs={10:'50'})['unposted_amount']=='300.00'

@pytest.mark.parametrize('events,costs,issue', [
    (base(),{10:'50'},4),
    (base(),{10:'50',11:'80',12:'100'},4),
    (base(),{10:'NaN',11:'80'},4),
    (base(),{10:'50',11:'-1'},4),
    (base(),{10:'50',11:'80'},55),
    (base(),{10:'50',11:'80'},1),
    ([event(1,'RECEIPT',10), event(4,'ISSUE',11)],{10:'50'},4),
    ([event(1,'RECEIPT',10), event(4,'ISSUE',5),event(5,'ISSUE',20)],{10:'50'},4),
    ([event(1,'RECEIPT',10),dict(event(4,'ISSUE',4),project_id=99)],{10:'50'},4),
])
def test_reject_bad_evidence(events,costs,issue):
    with pytest.raises((ValueError, TypeError)):
        run(events,costs=costs,issue=issue)


def test_fifo_does_not_conflate_physical_lot_with_costing_layers():
    # Physically sourced entirely from receipt 11; costing FIFO draws from 10 and 11.
    result = run(base())
    assert result['physical_receipt_line_id'] == 11
    assert result['physical_lot_in_eligible_layers'] is True
    assert result['costing_vs_physical_lot'] == 'DIFFERENT_LAYER_BASIS'
    assert result['movement_valuation_verified'] is False

def test_single_layer_fifo_same_basis():
    events = [event(1, 'RECEIPT', 10), event(4, 'ISSUE', 4)]
    result = run(events, costs={10:'50'})
    assert result['costing_vs_physical_lot'] == 'SAME_LAYER_BASIS'

def test_weighted_average_not_misrepresented_as_physical_lot_match():
    result = run(base(), method='WEIGHTED_AVERAGE')
    assert result['costing_vs_physical_lot'] == 'NOT_COMPARABLE_WEIGHTED_AVERAGE'
