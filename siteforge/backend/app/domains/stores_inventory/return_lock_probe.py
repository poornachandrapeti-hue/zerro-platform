"""Opt-in, non-writing PostgreSQL transaction-lock probe.

Checks lock exclusion and rollback release on two connections. This does NOT
exercise Stores return posting or prove stock ledger concurrency correctness.
Never enable posting flags or modify inventory while running this probe.

Run: python -m app.domains.stores_inventory.return_lock_probe --project-id 1
"""
import argparse
import json
from sqlalchemy import text
from app.db import engine

# A separate lock namespace reserved for diagnostic probes. It cannot collide
# with application advisory keys because probe uses two-key PG lock signatures.
_PROBE_NAMESPACE = 73740712


def classify_observations(first_acquired, second_blocked, acquired_after_rollback):
    return bool(first_acquired and second_blocked and acquired_after_rollback)


def probe(project_id, *, db_engine=None):
    if not isinstance(project_id, int) or project_id < 1:
        raise ValueError('Explicit positive project ID required')
    db_engine = db_engine or engine
    result = {'project_id': project_id, 'read_only': True,
              'return_posting_validated': False, 'posting_feature_enabled': False,
              'lock_probe_passed': False,
              'note': 'Diagnostic advisory lock only. Does not test business row locks, posting concurrency or stock rollback.'}
    if db_engine.dialect.name != 'postgresql':
        result['issues'] = ['PostgreSQL required']
        return result
    # Two independent transactions; rollback must release the first lock.
    with db_engine.connect() as first, db_engine.connect() as second:
        tx1 = first.begin()
        tx2 = second.begin()
        try:
            first.execute(text('SET TRANSACTION READ ONLY'))
            second.execute(text('SET TRANSACTION READ ONLY'))
            got1 = first.execute(text('SELECT pg_try_advisory_xact_lock(:ns, :pid)'),
                                 {'ns': _PROBE_NAMESPACE, 'pid': project_id}).scalar_one()
            got2 = second.execute(text('SELECT pg_try_advisory_xact_lock(:ns, :pid)'),
                                  {'ns': _PROBE_NAMESPACE, 'pid': project_id}).scalar_one()
            tx1.rollback()
            got3 = second.execute(text('SELECT pg_try_advisory_xact_lock(:ns, :pid)'),
                                  {'ns': _PROBE_NAMESPACE, 'pid': project_id}).scalar_one()
            result['lock_probe_passed'] = classify_observations(got1, not got2, got3)
            if not result['lock_probe_passed']:
                result['issues'] = ['Unexpected advisory lock exclusivity or release behavior']
        finally:
            if tx1.is_active:
                tx1.rollback()
            if tx2.is_active:
                tx2.rollback()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Non-writing PostgreSQL transaction lock probe')
    parser.add_argument('--project-id', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        result = probe(args.project_id)
    except Exception as exc:
        result = {'project_id': args.project_id, 'read_only': True,
                  'lock_probe_passed': False, 'return_posting_validated': False,
                  'issues': [f'Probe could not complete: {type(exc).__name__}']}
    print(json.dumps(result, indent=2))
    return 0 if result.get('lock_probe_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
