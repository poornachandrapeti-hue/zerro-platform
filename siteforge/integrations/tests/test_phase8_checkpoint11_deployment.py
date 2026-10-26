import json
import pytest
from integrations.command_center.phase8_deployment import get_deployment_config, deployment_smoke, main
from integrations.command_center.stores_phase8_exceptions import ExceptionFeedError

ENV = {'ZERROBUILD_FEED_ORIGIN':'https://zerrobuild.example.com',
       'ZERROBUILD_FEED_ALLOWED_ORIGINS':'https://zerrobuild.example.com',
       'ZERROR_INTERNAL_SERVICE_KEY':'123456789012345678901234567890'}

def test_preflight_valid(capsys):
    assert main(['--preflight'], ENV) == 0
    output = capsys.readouterr().out
    assert '123456789012345678901234567890' not in output
    assert json.loads(output)['network_tested'] is False

@pytest.mark.parametrize('changes', [
    {'ZERROBUILD_FEED_ORIGIN': 'http://zerrobuild.example.com'},
    {'ZERROBUILD_FEED_ORIGIN': 'https://localhost'},
    {'ZERROBUILD_FEED_ALLOWED_ORIGINS': ''},
    {'ZERROBUILD_FEED_ALLOWED_ORIGINS': 'https://other.example.com'},
    {'ZERROBUILD_FEED_ALLOWED_ORIGINS': 'https://zerrobuild.example.com,https://zerrobuild.example.com'},
    {'ZERROR_INTERNAL_SERVICE_KEY':''},
])
def test_invalid_preflight(changes):
    with pytest.raises(ExceptionFeedError): get_deployment_config({**ENV, **changes})

def test_smoke_reuses_real_validator(monkeypatch):
    def fake_fetch(**kwargs):
        assert kwargs['allowed_origins'] == frozenset({'https://zerrobuild.example.com'})
        assert kwargs['viewer_authorized'] is True
        return {'project_id':3, 'organization_id':2, 'as_of':'2026-10-24T00:00:00+00:00','record_count':4}
    monkeypatch.setattr('integrations.command_center.phase8_deployment.fetch_phase8_exceptions', fake_fetch)
    result = deployment_smoke(env=ENV, organization_id=2, project_id=3)
    assert result['viewer_rbac_tested'] is False
    assert result['authority'] == 'read_only_unverified'

def test_smoke_rejects_missing_ids():
    with pytest.raises(SystemExit): main(['--smoke'], ENV)
