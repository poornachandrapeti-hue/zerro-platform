"""Server-side ZerroBuild Stores workload adapter for the separate Command Center.

Never import this into browser code. Keep the service key in Command Center backend env.
The caller MUST authorize its viewer for the requested project *before* invoking fetch.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class StoresFeedError(RuntimeError):
    """An integration failure; never silently convert it to zero workload."""


@dataclass(frozen=True)
class StoresApprovalWorkload:
    organization_id: int
    project_id: int
    as_of: str
    age_seconds: float
    stale: bool
    pending_approval_count: int
    past_required_date_count: int
    partner_origin_pending_count: int
    pending_without_active_task_count: int
    overdue_active_task_count: int
    physical_stock_readiness: str


def validate_payload(payload: Mapping[str, Any], *, organization_id: int,
                     project_id: int, max_age_seconds: int = 300,
                     now: datetime | None = None) -> StoresApprovalWorkload:
    """Reject cross-org/project or malformed feed; signal stale data rather than hide it."""
    if payload.get("organization_id") != organization_id or payload.get("project_id") != project_id:
        raise StoresFeedError("Stores feed scope mismatch")
    if payload.get("source") != "zerrobuild.stores.material_requests" or payload.get("read_only") is not True:
        raise StoresFeedError("Unexpected Stores feed contract")
    try:
        sampled = datetime.fromisoformat(str(payload["as_of"]).replace("Z", "+00:00"))
        if sampled.tzinfo is None:
            raise ValueError("timezone missing")
        reference = now or datetime.now(timezone.utc)
        age = (reference - sampled).total_seconds()
        if age < -60:
            raise StoresFeedError("Stores feed timestamp is in the future")
        fields = ("pending_approval_count", "past_required_date_count", "partner_origin_pending_count",
                  "pending_without_active_task_count", "overdue_active_task_count")
        counts = {}
        for field in fields:
            value = payload[field]
            if type(value) is not int or value < 0:
                raise ValueError(field)
            counts[field] = value
        if counts["partner_origin_pending_count"] > counts["pending_approval_count"]:
            raise ValueError("partner pending > total pending")
        if counts["pending_without_active_task_count"] > counts["pending_approval_count"]:
            raise ValueError("task gap > total pending")
        if payload.get("physical_stock_readiness") != "Unverified":
            raise StoresFeedError("Unsupported physical-stock readiness assertion")
        return StoresApprovalWorkload(organization_id, project_id, sampled.isoformat(),
                                     max(0.0, age), age > max_age_seconds,
                                     **counts, physical_stock_readiness="Unverified")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise StoresFeedError("Invalid Stores approval feed payload") from exc


def fetch_stores_workload(*, base_url: str, service_key: str, organization_id: int,
                          project_id: int, viewer_authorized: bool,
                          max_age_seconds: int = 300,
                          opener: Callable[..., Any] = urlopen) -> StoresApprovalWorkload:
    """Fetch after the Command Center verified live grants and project mapping.

    The explicit viewer_authorized flag is a guard, not a replacement for live-grants lookup.
    """
    if not viewer_authorized:
        raise StoresFeedError("Viewer project grant required")
    if not service_key or not base_url.startswith("https://"):
        raise StoresFeedError("Configured HTTPS source URL and service key required")
    if type(project_id) is not int or project_id <= 0 or type(organization_id) is not int or organization_id <= 0:
        raise StoresFeedError("Valid project and organization identifiers required")
    endpoint = (base_url.rstrip("/") + f"/api/projects/{project_id}/stores/"
                "internal-command-center/approval-workload")
    request = Request(endpoint, headers={"X-ZerroR-Service-Key": service_key,
                                         "Accept": "application/json"}, method="GET")
    try:
        with opener(request, timeout=8) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise StoresFeedError("Stores source feed unavailable") from exc
    if not isinstance(data, dict):
        raise StoresFeedError("Invalid Stores source response")
    return validate_payload(data, organization_id=organization_id,
                            project_id=project_id, max_age_seconds=max_age_seconds)
