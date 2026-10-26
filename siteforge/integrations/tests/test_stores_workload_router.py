"""Dependency-injected route contract tests; no network/DB required."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'command_center'))
from stores_workload_router import create_stores_workload_router
from stores_approval_feed import StoresApprovalWorkload


def endpoint(router):
    return next(route.endpoint for route in router.routes if 'stores-approval-workload' in route.path)


def sample(**updates):
    data = dict(organization_id=7, project_id=31, as_of=datetime.now(timezone.utc).isoformat(),
                age_seconds=0, stale=False, pending_approval_count=3, past_required_date_count=1,
                partner_origin_pending_count=2, pending_without_active_task_count=1,
                overdue_active_task_count=0, physical_stock_readiness='Unverified')
    data.update(updates)
    return StoresApprovalWorkload(**data)


def build(authorize, fetch):
    return create_stores_workload_router(resolve_viewer_scope=authorize,
        zerrobuild_base_url='https://zerrobuild.example', service_key='secret-on-server', fetcher=fetch)


def test_denied_viewer_does_not_fetch():
    def deny(_request, _project):
        raise HTTPException(403, 'Access denied')
    fetch = Mock()
    with pytest.raises(HTTPException) as exc:
        endpoint(build(deny, fetch))(31, Mock())
    assert exc.value.status_code == 403
    fetch.assert_not_called()


def test_success_scoped_and_no_cache():
    fetch = Mock(return_value=sample())
    response = endpoint(build(lambda _r, p: 7 if p == 31 else 0, fetch))(31, Mock())
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    assert b'"physical_stock_readiness":"Unverified"' in response.body
    assert b'age_seconds' not in response.body
    assert fetch.call_args.kwargs['organization_id'] == 7
    assert fetch.call_args.kwargs['project_id'] == 31


def test_stale_refused():
    response = endpoint(build(lambda _r, _p: 7, lambda **_: sample(stale=True)))(31, Mock())
    assert response.status_code == 503
    assert b'pending_approval_count' not in response.body


def test_invalid_scope_refused_before_fetch():
    fetch = Mock()
    with pytest.raises(HTTPException) as exc:
        endpoint(build(lambda _r, _p: None, fetch))(31, Mock())
    assert exc.value.status_code == 403
    fetch.assert_not_called()


def test_missing_live_authorization_callback_refused():
    with pytest.raises(ValueError):
        create_stores_workload_router(resolve_viewer_scope=None,
            zerrobuild_base_url='https://zerrobuild.example', service_key='secret')
