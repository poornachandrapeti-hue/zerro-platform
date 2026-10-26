from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from app.live_permissions import refresh_live_grants

S = SimpleNamespace(command_center_identity_url='http://siteforge_backend:8000', command_center_identity_service_key='test-service-key', command_center_expected_org='12')
SESSION = {'sub':'5','org':'12','role':'VIEWER','grants':[{'code':'OLD','discipline_ids':[],'discipline_names':{},'full_scope':True,'commercial':True}]}

class Response:
    def __init__(self, grants, status=200):
        self.grants=grants
        self.status=status
    def raise_for_status(self):
        import httpx
        if self.status != 200: raise httpx.HTTPStatusError('unavailable',request=httpx.Request('GET','http://localhost'),response=httpx.Response(self.status))
    def json(self): return self.grants

def test_live_grants_replace_expired_entitlements():
    live={'sub':'5','org':'12','role':'VIEWER','grants':[]}
    with patch('app.live_permissions.httpx.get',return_value=Response(live)) as get:
        assert refresh_live_grants(SESSION,S)['grants']==[]
    assert get.call_args.kwargs['follow_redirects'] is False
    assert get.call_args.kwargs['timeout']==2.0

def test_live_grants_reject_different_user():
    with patch('app.live_permissions.httpx.get',return_value=Response({'sub':'6','org':'12','role':'VIEWER','grants':[]})):
        with pytest.raises(HTTPException) as err: refresh_live_grants(SESSION,S)
    assert err.value.status_code==403

def test_live_grants_fail_closed_on_unavailable_authority():
    import httpx
    with patch('app.live_permissions.httpx.get',side_effect=httpx.ConnectError('offline')):
        with pytest.raises(HTTPException) as err: refresh_live_grants(SESSION,S)
    assert err.value.status_code==503

def test_live_grants_fail_closed_without_service_key():
    s=SimpleNamespace(**{**vars(S),'command_center_identity_service_key':''})
    with pytest.raises(HTTPException) as err: refresh_live_grants(SESSION,s)
    assert err.value.status_code==503
