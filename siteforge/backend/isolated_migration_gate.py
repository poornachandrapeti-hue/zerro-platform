"""Opt-in Alembic verification exclusively for disposable local PostgreSQL copies.

Defaults to a non-mutating configuration check. Never uses the application DATABASE_URL.
"""
import argparse
import re
import os
import subprocess
import sys
from urllib.parse import urlsplit

ALLOWED_HOSTS = {'127.0.0.1', 'localhost', '::1'}
REQUIRED_FINANCE_TABLES = (
    'finance_inventory_costing_policies',
    'finance_landed_cost_batches',
    'finance_landed_cost_receipt_links',
    'finance_receipt_cost_allocations',
    'finance_movement_journal_proposals',
)


# Critical structural guarantees from Finance-owned Alembic migrations.
REQUIRED_FINANCE_COLUMNS = {
    'finance_inventory_costing_policies': {'id', 'organization_id', 'project_id', 'revision', 'costing_method', 'currency', 'status', 'approved_by'},
    'finance_landed_cost_batches': {'id', 'organization_id', 'project_id', 'document_ref', 'currency', 'amount', 'status', 'approved_by'},
    'finance_landed_cost_receipt_links': {'id', 'batch_id', 'goods_receipt_line_id'},
    'finance_receipt_cost_allocations': {'id', 'organization_id', 'project_id', 'goods_receipt_line_id', 'vendor_invoice_line_id', 'quantity', 'currency', 'unit_cost', 'status', 'approved_by'},
    'finance_movement_journal_proposals': {'id', 'organization_id', 'project_id', 'source_movement_line_id', 'lines', 'currency', 'status', 'approved_by'},
}
REQUIRED_FINANCE_FOREIGN_KEYS = {
    'finance_landed_cost_receipt_links': {('batch_id', 'finance_landed_cost_batches'), ('goods_receipt_line_id', 'goods_receipt_lines')},
    'finance_receipt_cost_allocations': {('goods_receipt_line_id', 'goods_receipt_lines'), ('vendor_invoice_line_id', 'vendor_invoice_lines')},
    'finance_movement_journal_proposals': {('source_movement_line_id', 'stock_posting_lines')},
}


def inspect_finance_structure(inspector) -> tuple[bool, str]:
    """Verify critical columns and FK references, not merely table presence."""
    existing = set(inspector.get_table_names(schema='public'))
    missing = sorted(set(REQUIRED_FINANCE_TABLES) - existing)
    if missing:
        return False, 'Missing Finance tables: ' + ', '.join(missing)
    for table, required_columns in REQUIRED_FINANCE_COLUMNS.items():
        actual_columns = {col['name'] for col in inspector.get_columns(table, schema='public')}
        missing_columns = sorted(required_columns - actual_columns)
        if missing_columns:
            return False, f'Missing Finance columns in {table}: ' + ', '.join(missing_columns)
    for table, required_keys in REQUIRED_FINANCE_FOREIGN_KEYS.items():
        actual_keys = set()
        for fk in inspector.get_foreign_keys(table, schema='public'):
            for column in fk.get('constrained_columns') or []:
                actual_keys.add((column, fk.get('referred_table')))
        missing_keys = sorted(required_keys - actual_keys)
        if missing_keys:
            return False, f'Missing Finance foreign keys in {table}: ' + ', '.join(f'{col}->{ref}' for col, ref in missing_keys)
    return True, 'Required Finance tables, critical columns and foreign keys exist in public schema'


def verify_finance_schema(url: str) -> tuple[bool, str]:
    """Read-only structural inspection on independently verified disposable DB."""
    from sqlalchemy import create_engine, inspect
    engine = create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 5})
    try:
        with engine.connect() as connection:
            return inspect_finance_structure(inspect(connection))
    except Exception as exc:
        return False, f'Finance schema inspection failed: {type(exc).__name__}'
    finally:
        engine.dispose()


def validate_target(url: str, *, confirmed: bool = False) -> str:
    if not url:
        raise ValueError('TEST_DATABASE_URL must be provided explicitly')
    parts = urlsplit(url)
    if not parts.scheme.startswith('postgresql') or parts.hostname not in ALLOWED_HOSTS:
        raise ValueError('Only explicit loopback PostgreSQL test targets are supported')
    name = (parts.path or '').lstrip('/')
    if not name.endswith('_uat') or name in {'siteforge', 'zerro_dashboard'}:
        raise ValueError('Disposable test database name must end in _uat')
    if not parts.port or parts.port == 5432:
        raise ValueError('Use an explicit non-default port for the isolated PostgreSQL instance')
    if not confirmed:
        raise ValueError('Explicit disposable database confirmation required')
    return f'{parts.hostname}:{parts.port}/{name}'


def _revision_ids(output: str) -> set[str]:
    """Extract Alembic revision identifiers from `heads`/`current` output."""
    return set(re.findall(r"(?m)^\s*([A-Za-z0-9_]{4,128})(?=\s*(?:\(|$))", output))


def verify_revision_alignment(heads_output: str, current_output: str) -> bool:
    """Require exactly one declared head and exactly that applied revision."""
    heads = _revision_ids(heads_output)
    current = _revision_ids(current_output)
    return len(heads) == 1 and current == heads


def check_migration_state(env) -> tuple[bool, str]:
    results = []
    for action in ('heads', 'current'):
        result = subprocess.run(
            [sys.executable, '-m', 'alembic', action], env=env,
            check=False, capture_output=True, text=True,
        )
        if result.returncode:
            return False, f'alembic {action} failed: {result.stderr.strip()[:500]}'
        results.append(result.stdout)
    return verify_revision_alignment(*results), 'head/current match' if verify_revision_alignment(*results) else 'database revision does not match single migration head'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-disposable', action='store_true')
    parser.add_argument('--upgrade', action='store_true', help='Apply migrations on confirmed isolated test copy')
    args = parser.parse_args(argv)
    url = os.environ.get('TEST_DATABASE_URL', '')
    try:
        target = validate_target(url, confirmed=args.confirm_disposable)
    except ValueError as exc:
        print(f'BLOCKED: {exc}', file=sys.stderr)
        return 2
    if os.environ.get('DATABASE_URL') == url:
        print('BLOCKED: test target must not equal application DATABASE_URL', file=sys.stderr)
        return 2
    env = os.environ.copy()
    env['DATABASE_URL'] = url
    print('Validated disposable target:', target, flush=True)
    for action in [('heads',), ('current',)]:
        result = subprocess.run([sys.executable, '-m', 'alembic', *action], env=env, check=False)
        if result.returncode:
            return result.returncode
    if not args.upgrade:
        print('READ ONLY: no migrations executed')
        return 0
    if os.environ.get('STORES_ENABLE_TEST_MIGRATIONS') != 'YES_ON_DISPOSABLE_COPY':
        print('BLOCKED: set STORES_ENABLE_TEST_MIGRATIONS for explicit opt-in', file=sys.stderr)
        return 2
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=env, check=False)
    if result.returncode:
        return result.returncode
    aligned, reason = check_migration_state(env)
    if not aligned:
        print(f'BLOCKED: post-upgrade verification failed: {reason}', file=sys.stderr)
        return 3
    schema_ok, schema_reason = verify_finance_schema(url)
    if not schema_ok:
        print(f'BLOCKED: post-upgrade schema verification failed: {schema_reason}', file=sys.stderr)
        return 4
    print('VERIFIED: Alembic head and required Finance schema match')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
