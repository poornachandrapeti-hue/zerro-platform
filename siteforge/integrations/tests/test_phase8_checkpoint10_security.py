from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from integrations.command_center.stores_phase8_exceptions import (
    fetch_phase8_exceptions, verify_project_mapping, ExceptionFeedError, _NoRedirect,
)

PARAMS = dict(base_url='https://zerrobuild.flagestrator.com', service_key='example-test-key',
              organization_id=2, project_id=9, viewer_authorized=True)

def test_allowlist_blocks_unlisted_origin_before_network():
    with pytest.raises(ExceptionFeedError, match='allowlisted'):
        fetch_phase8_exceptions(**PARAMS, allowed_origins=frozenset({'https://other.example.org'}),
            opener=lambda *a, **kw: pytest.fail('unexpected network'))

def test_no_redirect_does_not_rewrite_request():
    assert _NoRedirect().redirect_request(object(), None, 302, 'moved', {}, 'https://evil.example') is None

def test_default_transport_is_redirect_safe():
    class FakeOpener:
        def open(self, request, timeout):
            assert timeout == 8
            assert request.full_url.startswith('https://zerrobuild.flagestrator.com')
            raise HTTPError(request.full_url, 302, 'redirect blocked', {}, None)
    with patch('integrations.command_center.stores_phase8_exceptions.build_opener', return_value=FakeOpener()) as builder:
        with pytest.raises(ExceptionFeedError, match='unavailable'):
            fetch_phase8_exceptions(**PARAMS, allowed_origins=frozenset({PARAMS['base_url']}))
        assert any(isinstance(x, _NoRedirect) for x in builder.call_args.args)

@pytest.mark.parametrize('changes', [
    {'viewer_authorized':False}, {'source_organization_id':3}, {'source_project_id':10},
    {'viewer_project_id':True}, {'viewer_organization_id':0},
])
def test_mapping_fails_closed(changes):
    args=dict(viewer_organization_id=2, viewer_project_id=9, source_organization_id=2,
              source_project_id=9, viewer_authorized=True)
    args.update(changes)
    with pytest.raises(ExceptionFeedError, match='mapping'):
        verify_project_mapping(**args)

def test_valid_mapping():
    verify_project_mapping(viewer_organization_id=2, viewer_project_id=9,
                           source_organization_id=2, source_project_id=9, viewer_authorized=True)
