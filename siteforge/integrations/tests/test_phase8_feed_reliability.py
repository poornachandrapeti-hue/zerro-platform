from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import json
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from integrations.command_center.stores_phase8_exceptions import (
    fetch_phase8_exceptions, validate_source_url, classify_feed_health, ExceptionFeedError,
    MAX_FEED_BYTES,
)

NOW = datetime.now(timezone.utc)

@pytest.mark.parametrize('origin', [
    'http://example.com', 'https://localhost', 'https://127.0.0.1',
    'https://user:secret@example.com', 'https://example.com/path',
    'https://example.com?token=abc', 'https://[::1]', 'https://10.1.0.3',
    'https://169.254.169.254', 'https://example.com/#fragment', '',
])
def test_reject_unsafe_source_origin(origin):
    with pytest.raises(ExceptionFeedError):
        validate_source_url(origin)

def test_accept_configured_public_origin():
    assert validate_source_url('https://zerrobuild.flagestrator.com/') == 'https://zerrobuild.flagestrator.com'

class Response:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, max_bytes): return self.data[:max_bytes]

def test_oversize_response_is_unavailable():
    with pytest.raises(ExceptionFeedError, match='unavailable'):
        fetch_phase8_exceptions(base_url='https://example.com', service_key='secret', organization_id=2,
                                project_id=9, viewer_authorized=True,
                                opener=lambda request, timeout: Response(b' '* (MAX_FEED_BYTES + 1)))

def test_malformed_response_is_unavailable():
    with pytest.raises(ExceptionFeedError, match='unavailable'):
        fetch_phase8_exceptions(base_url='https://example.com', service_key='secret', organization_id=2,
                                project_id=9, viewer_authorized=True,
                                opener=lambda request, timeout: Response(b'{bad json'))

def test_health_modes():
    assert classify_feed_health(last_success_at=None, now=NOW)['state'] == 'unavailable'
    assert classify_feed_health(last_success_at=NOW, now=NOW)['state'] == 'healthy'
    assert classify_feed_health(last_success_at=NOW, now=NOW, failure_count=1)['state'] == 'degraded'
    assert classify_feed_health(last_success_at=NOW-timedelta(seconds=301), now=NOW)['state'] == 'stale'
    assert classify_feed_health(last_success_at=NOW+timedelta(minutes=2), now=NOW)['state'] == 'invalid_clock'
