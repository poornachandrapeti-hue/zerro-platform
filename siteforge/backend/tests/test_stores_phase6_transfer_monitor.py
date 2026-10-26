from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from fastapi import HTTPException
from app.domains.stores_inventory.transfer_monitor import summarize_transfers


def record(**kwargs):
    attrs=dict(id=1,reference='T-1',project_id=10,destination_project_id=11,
      source_warehouse_id=1,destination_warehouse_id=2,item_id=7,status='In Transit',
      discrepancy_status='Not Required',custody_confirmed_by=None,
      created_at=datetime(2026,10,20,tzinfo=timezone.utc))
    attrs.update(kwargs)
    return SimpleNamespace(**attrs)


def test_monitor_age_and_no_stock_claim():
    result=summarize_transfers([record()],as_of=datetime(2026,10,23,tzinfo=timezone.utc))
    assert result['counts']['overdue_in_transit']==1
    assert result['records'][0]['inventory_posted'] is False
    assert result['inventory_verified'] is False
    assert result['aging_basis']=='request_created_at_proxy_not_dispatch_time'


def test_monitor_discrepancy_and_custody():
    result=summarize_transfers([record(status='Discrepancy',discrepancy_status='Escalated')],as_of=datetime(2026,10,23,tzinfo=timezone.utc))
    assert result['counts']['open_discrepancy']==1
    assert result['counts']['pending_custody_confirmation']==1
    assert result['counts'].get('overdue_in_transit',0)==0


def test_monitor_threshold_bounds():
    try: summarize_transfers([],overdue_hours=0)
    except HTTPException as exc: assert exc.status_code==422
    else: assert False
