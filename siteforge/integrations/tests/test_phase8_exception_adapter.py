import sys
from pathlib import Path
from datetime import datetime, timezone
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from integrations.command_center.stores_phase8_exceptions import validate_exception_snapshot, fetch_phase8_exceptions, ExceptionFeedError

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
def sample():
    return dict(source='zerrobuild.stores.phase8_cross_module_audit',schema_version=1, project_id=9,organization_id=2,
                as_of=NOW.isoformat(),read_only=True,complete_history=False,billing_certified=False,
                financials_authority_verified=False,external_inspection_verified=False,delivery_mode='poll_snapshot',
                record_count=2,exception_counts={'MISSING':1},
                exception_records=[dict(material_request_id=4,work_package_id=8,exception_codes=['MISSING'],review_state='Requires Review')],coverage='Latest 2')
def test_valid():
    result=validate_exception_snapshot(sample(),project_id=9,organization_id=2,now=NOW)
    assert result['exception_counts']=={'MISSING':1}
@pytest.mark.parametrize('key,value', [('organization_id',3),('project_id',10),('billing_certified',True),('complete_history',True),('external_inspection_verified',True),('record_count',True),('read_only',False)])
def test_reject_invalid_authority_scope(key,value):
    payload=sample();payload[key]=value
    with pytest.raises(ExceptionFeedError): validate_exception_snapshot(payload,project_id=9,organization_id=2,now=NOW)
def test_reject_stale():
    with pytest.raises(ExceptionFeedError): validate_exception_snapshot(sample(),project_id=9,organization_id=2)
def test_reject_count_mismatch():
    payload=sample();payload['exception_counts']={'MISSING':2}
    with pytest.raises(ExceptionFeedError):validate_exception_snapshot(payload,project_id=9,organization_id=2,now=NOW)
def test_authorization_precedes_network():
    with pytest.raises(ExceptionFeedError):fetch_phase8_exceptions(base_url='https://example.com',service_key='secret',organization_id=2,project_id=9,viewer_authorized=False,opener=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network called')))
