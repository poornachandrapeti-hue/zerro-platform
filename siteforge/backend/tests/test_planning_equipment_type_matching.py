from datetime import datetime, timedelta, timezone, date
from types import SimpleNamespace as R
from app.domains.planning_reporting.resource_capacity import equipment_demand_evidence
S=datetime(2026,10,20,8,tzinfo=timezone.utc)
E=S+timedelta(hours=8)
def a(i): return R(activity_id=7,resource_type='Equipment',status='EquipmentConfirmed',resource_ref=f'equipment:{i}',starts_at=S,ends_at=E)
def asset(i,t,review='Verified',expiry=date(2026,10,21)):
    return R(id=i,equipment_type=t,status='Active',inspection_review_status=review,inspection_valid_through=expiry)
def d(t,q=1): return R(id=1,activity_id=7,resource_type='Equipment',resource_name=t,demand_quantity=q,demand_unit='units')
def result(allocs,assets,demand): return equipment_demand_evidence(7,S,E,allocs,[demand],assets=assets)['equipment_demands'][0]
def test_matched_type():
    r=result([a(1),a(2)],[asset(1,'Tower Crane'),asset(2,'Excavator')],d(' tower  crane '))
    assert r['type_matched_eligible_assets']==1 and r['status']=='BOOKING_COUNT_MEETS_DEMAND'
def test_other_asset_type_does_not_count():
    r=result([a(1)],[asset(1,'Excavator')],d('Crane'))
    assert r['booking_gap']==1 and r['status']=='NO_TYPE_MATCHED_CONFIRMED_ASSETS'
def test_inspection_rejected_does_not_count():
    assert result([a(1)],[asset(1,'Crane',review='Rejected')],d('Crane'))['type_matched_eligible_assets']==0
def test_expired_inspection_does_not_count():
    assert result([a(1)],[asset(1,'Crane',expiry=date(2026,10,19))],d('Crane'))['type_matched_eligible_assets']==0
def test_legacy_text_reference_does_not_count():
    old=R(activity_id=7,resource_type='Equipment',status='EquipmentConfirmed',resource_ref='CRANE-1',starts_at=S,ends_at=E)
    assert result([old],[asset(1,'Crane')],d('Crane'))['type_matched_eligible_assets']==0
