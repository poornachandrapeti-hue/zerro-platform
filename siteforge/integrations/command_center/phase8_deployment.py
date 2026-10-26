"""Phase 8 Command Center deployment validation (no credential output or mutations).

Usage: python -m integrations.command_center.phase8_deployment --preflight
       python -m integrations.command_center.phase8_deployment --smoke --organization-id 1 --project-id 2
Environment: ZERROBUILD_FEED_ORIGIN, ZERROBUILD_FEED_ALLOWED_ORIGINS,
             ZERROR_INTERNAL_SERVICE_KEY (or COMMAND_CENTER_IDENTITY_SERVICE_KEY).
Smoke testing is a trusted operator action; never expose this CLI to browser callers.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from urllib.parse import urlsplit

from .stores_phase8_exceptions import ExceptionFeedError, fetch_phase8_exceptions, validate_source_url


def get_deployment_config(env=None):
    """Fail closed on unset origin, explicit origin allowlist and secret; never return secrets in errors."""
    env = os.environ if env is None else env
    origin = validate_source_url(env.get('ZERROBUILD_FEED_ORIGIN', ''))
    entries = [x.strip() for x in env.get('ZERROBUILD_FEED_ALLOWED_ORIGINS', '').split(',') if x.strip()]
    if not entries or len(entries) != len(set(entries)):
        raise ExceptionFeedError('Explicit nonduplicate feed origin allowlist is required')
    allowed = frozenset(validate_source_url(x) for x in entries)
    if origin not in allowed:
        raise ExceptionFeedError('Configured feed origin is not allowlisted')
    key = env.get('ZERROR_INTERNAL_SERVICE_KEY', '') or env.get('COMMAND_CENTER_IDENTITY_SERVICE_KEY', '')
    if len(key.strip()) < 24:
        raise ExceptionFeedError('Server-side service credential is missing or too short')
    return {'origin': origin, 'allowed_origins': allowed, 'service_key': key}


def deployment_smoke(*, env=None, organization_id: int, project_id: int, opener=None):
    """Only proves server-to-server transport and snapshot validation, not viewer RBAC."""
    config = get_deployment_config(env)
    snapshot = fetch_phase8_exceptions(
        base_url=config['origin'], service_key=config['service_key'],
        organization_id=organization_id, project_id=project_id,
        viewer_authorized=True, allowed_origins=config['allowed_origins'], opener=opener)
    return {'result': 'passed', 'project_id': snapshot['project_id'],
            'organization_id': snapshot['organization_id'], 'source_as_of': snapshot['as_of'],
            'exception_record_count': snapshot['record_count'],
            'authority': 'read_only_unverified', 'viewer_rbac_tested': False}


def main(argv=None, env=None):
    parser = argparse.ArgumentParser(description='Phase 8 Command Center deployment preflight')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--preflight', action='store_true')
    group.add_argument('--smoke', action='store_true')
    parser.add_argument('--organization-id', type=int)
    parser.add_argument('--project-id', type=int)
    args = parser.parse_args(argv)
    try:
        config = get_deployment_config(env)
        if args.smoke:
            if not args.organization_id or args.organization_id < 1 or not args.project_id or args.project_id < 1:
                parser.error('Smoke mode requires positive organization and project IDs')
            result = deployment_smoke(env=env, organization_id=args.organization_id, project_id=args.project_id)
        else:
            result = {'result': 'passed', 'origin': config['origin'],
                      'allowlist_size': len(config['allowed_origins']), 'network_tested': False}
        print(json.dumps(result, sort_keys=True))
        return 0
    except ExceptionFeedError as exc:
        print(json.dumps({'result': 'failed', 'reason': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
