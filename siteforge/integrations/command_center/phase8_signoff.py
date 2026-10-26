"""Stores Phase 8 evidence-based sign-off gate. Never implies deployed readiness.

Operator-controlled evidence is explicit; no database writes or production network calls.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

REQUIRED_CHECKS = (
    'source_tests', 'frontend_build', 'postgres_migrations', 'docker_services',
    'feed_smoke', 'command_backend_route', 'viewer_rbac', 'tenant_isolation',
    'project_mapping', 'qa_authority', 'finance_authority', 'recovery_and_observability'
)


def assess(evidence: dict) -> dict:
    """Only exact boolean true constitutes passed evidence; unknown remains blocked."""
    if not isinstance(evidence, dict):
        raise ValueError('Evidence must be a JSON object')
    unexpected = set(evidence) - set(REQUIRED_CHECKS)
    if unexpected:
        raise ValueError('Unknown check names: ' + ', '.join(sorted(unexpected)))
    statuses = {name: ('passed' if evidence.get(name) is True else
                       'failed' if evidence.get(name) is False else 'unverified')
                for name in REQUIRED_CHECKS}
    pending = [name for name, status in statuses.items() if status != 'passed']
    return {'phase': 'Stores Phase 8', 'checkpoint': 12,
            'signoff': 'blocked' if pending else 'eligible_for_manual_review',
            'statuses': statuses, 'blocking_checks': pending,
            'note': 'Eligibility is not production approval; authorized owners must review evidence.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Evidence-only Stores Phase 8 sign-off gate')
    parser.add_argument('--evidence', type=Path, help='Local JSON map from check names to true/false/null')
    parser.add_argument('--output', type=Path, help='Optional output path for JSON report')
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence.read_text(encoding='utf-8')) if args.evidence else {}
        result = assess(evidence)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'Invalid evidence: {exc}\n')
    serialized = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(serialized + '\n', encoding='utf-8')
    print(serialized)
    return 0 if result['signoff'] == 'eligible_for_manual_review' else 1


if __name__ == '__main__':
    raise SystemExit(main())
