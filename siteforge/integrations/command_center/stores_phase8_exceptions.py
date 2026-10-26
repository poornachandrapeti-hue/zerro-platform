"""Server-only adapter for Phase 8 Stores exceptions; call after LIVE viewer grant check.

The separate Command Center backend must expose the authorized browser endpoint.
Do not import into frontend or expose the service key.
"""
from __future__ import annotations
from datetime import datetime, timezone
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from typing import Any, Callable
from urllib.parse import urlsplit
import ipaddress
import json

class ExceptionFeedError(RuntimeError):
    pass

MAX_FEED_BYTES = 512 * 1024

class _NoRedirect(HTTPRedirectHandler):
    """Never forward a service key to an upstream redirect destination."""
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _secure_open(request: Request, *, timeout: int):
    return build_opener(_NoRedirect()).open(request, timeout=timeout)


def verify_project_mapping(*, viewer_organization_id: int, viewer_project_id: int,
                           source_organization_id: int, source_project_id: int,
                           viewer_authorized: bool) -> None:
    """Fail closed: Command Center must resolve its live viewer grant and source mapping."""
    fields = (viewer_organization_id, viewer_project_id, source_organization_id, source_project_id)
    if (viewer_authorized is not True or any(type(v) is not int or v <= 0 for v in fields)
            or viewer_organization_id != source_organization_id
            or viewer_project_id != source_project_id):
        raise ExceptionFeedError('Current project grant and matching source mapping required')



def validate_source_url(base_url: str) -> str:
    """Reject accidental insecure/misdirected service destinations (DNS policy belongs to deployment)."""
    try:
        parts = urlsplit(base_url)
        if (parts.scheme != 'https' or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.query or parts.fragment
                or parts.path not in ('', '/') or not parts.netloc):
            raise ValueError('Unexpected origin')
        hostname = parts.hostname
        if hostname.lower() in ('localhost', 'localhost.localdomain') or hostname.endswith('.localhost'):
            raise ValueError('Loopback origin')
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            if not address.is_global:
                raise ValueError('Nonpublic IP origin')
        return parts.geturl().rstrip('/')
    except (ValueError, TypeError) as exc:
        raise ExceptionFeedError('Invalid feed origin configuration') from exc


def classify_feed_health(*, last_success_at: datetime | None, now: datetime | None = None,
                         max_age_seconds: int = 300, failure_count: int = 0) -> dict:
    """Operational signal only; never turns a missing/stale feed into healthy zero counts."""
    current = now or datetime.now(timezone.utc)
    if failure_count < 0 or not isinstance(failure_count, int):
        raise ValueError('Invalid failure count')
    if last_success_at is None:
        return {'state': 'unavailable', 'age_seconds': None, 'failure_count': failure_count}
    if last_success_at.tzinfo is None:
        raise ValueError('Timestamp must be timezone aware')
    age = (current - last_success_at).total_seconds()
    if age < -60:
        return {'state': 'invalid_clock', 'age_seconds': int(age), 'failure_count': failure_count}
    state = 'stale' if age > max_age_seconds else ('degraded' if failure_count else 'healthy')
    return {'state': state, 'age_seconds': max(0, int(age)), 'failure_count': failure_count}


def validate_exception_snapshot(data: Any, *, project_id: int, organization_id: int,
                                max_age_seconds: int = 300, now: datetime | None = None) -> dict:
    if not isinstance(data, dict) or data.get('source') != 'zerrobuild.stores.phase8_cross_module_audit' or data.get('schema_version') != 1:
        raise ExceptionFeedError('Invalid source contract')
    if type(data.get('project_id')) is not int or data['project_id'] != project_id or type(data.get('organization_id')) is not int or data['organization_id'] != organization_id:
        raise ExceptionFeedError('Source project scope mismatch')
    if (data.get('read_only') is not True or data.get('complete_history') is not False
        or data.get('billing_certified') is not False or data.get('financials_authority_verified') is not False
        or data.get('external_inspection_verified') is not False or data.get('delivery_mode') != 'poll_snapshot'):
        raise ExceptionFeedError('Unsupported source authority')
    try:
        sampled = datetime.fromisoformat(data['as_of'].replace('Z', '+00:00'))
        if sampled.tzinfo is None: raise ValueError('Naive timestamp')
        age = ((now or datetime.now(timezone.utc)) - sampled).total_seconds()
        if age < -60 or age > max_age_seconds: raise ValueError('Stale timestamp')
        count = data['record_count']
        counts = data['exception_counts']
        records = data['exception_records']
        if type(count) is not int or not 0 <= count <= 500: raise ValueError('Count')
        if not isinstance(counts, dict) or not isinstance(records, list) or len(records) > count: raise ValueError('Counts')
        if any(not isinstance(k, str) or not k or type(v) is not int or v < 0 or v > count for k, v in counts.items()): raise ValueError('Count values')
        result_records = []
        for item in records:
            if not isinstance(item, dict) or set(item) != {'material_request_id','work_package_id','exception_codes','review_state'}: raise ValueError('Fields')
            if type(item['material_request_id']) is not int or item['material_request_id'] <= 0: raise ValueError('Request id')
            wp = item['work_package_id']
            if wp is not None and (type(wp) is not int or wp <= 0): raise ValueError('Work package')
            codes = item['exception_codes']
            if not isinstance(codes, list) or not codes or not all(isinstance(c, str) and c in counts for c in codes): raise ValueError('Exception codes')
            if not isinstance(item['review_state'], str): raise ValueError('Review state')
            result_records.append(item)
        if {k: sum(k in item['exception_codes'] for item in records) for k in counts} != counts: raise ValueError('Unmatched totals')
        return {'source': data['source'], 'organization_id': organization_id, 'project_id': project_id,
                'as_of': sampled.isoformat(), 'stale': False, 'record_count': count,
                'exception_counts': counts, 'exception_records': result_records,
                'coverage': str(data.get('coverage',''))[:300], 'complete_history': False,
                'external_inspection_verified': False, 'financials_authority_verified': False,
                'billing_certified': False}
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ExceptionFeedError('Invalid or stale source snapshot') from exc

def fetch_phase8_exceptions(*, base_url: str, service_key: str, organization_id: int,
                            project_id: int, viewer_authorized: bool,
                            opener: Callable[..., Any] | None = None,
                            allowed_origins: frozenset[str] | None = None) -> dict:
    if not viewer_authorized: raise ExceptionFeedError('Current project grant required')
    if not service_key or type(project_id) is not int or project_id <= 0 or type(organization_id) is not int or organization_id <= 0:
        raise ExceptionFeedError('Invalid feed configuration')
    safe_base_url = validate_source_url(base_url)
    if allowed_origins is not None and safe_base_url not in allowed_origins:
        raise ExceptionFeedError('Source origin not allowlisted')
    request = Request(safe_base_url + f'/api/projects/{project_id}/stores/internal-command-center/phase8-exception-snapshot?limit=200',
                      headers={'X-ZerroR-Service-Key': service_key, 'Accept':'application/json'}, method='GET')
    try:
        with (opener or _secure_open)(request, timeout=8) as response:
            # Bound memory usage even when the upstream omits Content-Length.
            raw = response.read(MAX_FEED_BYTES + 1)
            if len(raw) > MAX_FEED_BYTES:
                raise ValueError('Snapshot exceeded size limit')
            payload = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise ExceptionFeedError('Stores exception source unavailable') from exc
    return validate_exception_snapshot(payload, project_id=project_id, organization_id=organization_id)
