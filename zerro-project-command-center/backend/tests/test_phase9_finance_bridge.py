from datetime import datetime, timedelta, timezone
import pytest
from app.routers.phase9_finance import validate_finance_snapshot


def sample():
    return {'source':'zerrobuild.financials.phase9_proposal_monitor','schema_version':1,
        'organization_id':7,'project_id':12,'as_of':datetime.now(timezone.utc).isoformat(),
        'read_only':True,'delivery_mode':'poll_snapshot','complete_history':False,
        'gl_posted_verified':False,'inventory_valuation_certified':False,'billing_certified':False,
        'record_count':1,'status_counts':{'Approved':1},'proposal_records':[{'proposal_id':1,
        'source_movement_line_id':3,'proposal_revision':1,'status':'Approved'}]}


def test_monitor_remains_unposted():
    result=validate_finance_snapshot(sample(),7,12)
    assert result['gl_posted_verified'] is False
    assert result['status_counts']=={'Approved':1}


@pytest.mark.parametrize('changes',[
    {'organization_id':8},{'project_id':13},{'complete_history':True},
    {'gl_posted_verified':True},{'inventory_valuation_certified':True},
    {'billing_certified':True},{'read_only':False},
    {'record_count':2},{'status_counts':{'Approved':2}},
    {'as_of':(datetime.now(timezone.utc)-timedelta(minutes=9)).isoformat()},
])
def test_reject_unsafe_snapshot(changes):
    with pytest.raises(ValueError):validate_finance_snapshot({**sample(),**changes},7,12)


def test_duplicate_ids_rejected():
    s=sample();s['proposal_records']*=2;s['record_count']=2;s['status_counts']={'Approved':2}
    with pytest.raises(ValueError):validate_finance_snapshot(s,7,12)
