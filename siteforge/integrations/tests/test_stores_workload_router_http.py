"""HTTP-level Stores integration smoke tests with isolated authenticated viewers."""
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "command_center"))
from stores_workload_router import create_stores_workload_router
from stores_approval_feed import StoresApprovalWorkload, StoresFeedError


def payload():
    return StoresApprovalWorkload(
        organization_id=18, project_id=24, as_of=datetime.now(timezone.utc).isoformat(),
        age_seconds=0, stale=False, pending_approval_count=4,
        past_required_date_count=1, partner_origin_pending_count=2,
        pending_without_active_task_count=1, overdue_active_task_count=1,
        physical_stock_readiness="Unverified",
    )


def make_client(*, stale=False, error=False):
    calls = []
    def viewer_scope(request, project_id):
        if request.headers.get("X-Test-User") != "project-member":
            raise HTTPException(401, "Login required")
        if project_id != 24:
            raise HTTPException(403, "Project access denied")
        return 18
    def fetch(**kwargs):
        calls.append(kwargs)
        if error:
            raise StoresFeedError("downstream unavailable")
        from dataclasses import replace
        return replace(payload(), stale=stale)
    app = FastAPI()
    app.include_router(create_stores_workload_router(
        resolve_viewer_scope=viewer_scope,
        zerrobuild_base_url="https://zerrobuild.example",
        service_key="not-exposed-to-browser", fetcher=fetch))
    return TestClient(app), calls


def test_authorized_viewer_scoped_counts_no_cache():
    client, calls = make_client()
    response = client.get("/api/projects/24/stores-approval-workload", headers={"X-Test-User": "project-member"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["physical_stock_readiness"] == "Unverified"
    assert response.json()["pending_approval_count"] == 4
    assert calls[0]["organization_id"] == 18 and calls[0]["project_id"] == 24
    assert "service_key" not in response.text


@pytest.mark.parametrize("project,user,expected", [(24, "outsider", 401), (25, "project-member", 403)])
def test_denied_viewer_never_calls_source(project, user, expected):
    client, calls = make_client()
    response = client.get(f"/api/projects/{project}/stores-approval-workload", headers={"X-Test-User": user})
    assert response.status_code == expected
    assert calls == []


@pytest.mark.parametrize("state", ["stale", "error"])
def test_unavailable_and_stale_do_not_leak_metrics_or_cache(state):
    client, calls = make_client(stale=state == "stale", error=state == "error")
    response = client.get("/api/projects/24/stores-approval-workload", headers={"X-Test-User": "project-member"})
    assert response.status_code == 503
    assert response.headers["cache-control"] == "private, no-store"
    assert "pending_approval_count" not in response.text
    assert "not-exposed-to-browser" not in response.text
    assert len(calls) == 1
