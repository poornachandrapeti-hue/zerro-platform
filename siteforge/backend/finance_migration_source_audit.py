"""Offline, non-mutating contract audit for the four Finance migrations.

Checks that the structural database post-check agrees with actual migration DDL.
Does not connect to any database, apply migrations, or attest live readiness.
"""
from __future__ import annotations

import ast
from pathlib import Path

from isolated_migration_gate import (
    REQUIRED_FINANCE_TABLES, REQUIRED_FINANCE_COLUMNS, REQUIRED_FINANCE_FOREIGN_KEYS,
)

VERSIONS = Path(__file__).resolve().parent / 'migrations' / 'versions'
MIGRATIONS = (
    'finance_inventory_costing_policy.py',
    'finance_landed_cost_batches.py',
    'finance_receipt_cost_allocations.py',
    'finance_movement_journal_proposals.py',
)


def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def extract_contract(base: Path = VERSIONS):
    tables: dict[str, dict[str, set]] = {}
    revisions: dict[str, str | None] = {}
    for filename in MIGRATIONS:
        tree = ast.parse((base / filename).read_text(encoding='utf-8'), filename=filename)
        revision = parent = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'revision':
                        revision = literal(node.value)
                    if isinstance(target, ast.Name) and target.id == 'down_revision':
                        parent = literal(node.value)
        if not isinstance(revision, str):
            raise ValueError(f'{filename}: missing literal revision')
        if revision in revisions:
            raise ValueError(f'duplicate migration revision: {revision}')
        revisions[revision] = parent
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'create_table':
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != 'op' or not node.args:
                continue
            table = literal(node.args[0])
            if not isinstance(table, str):
                continue
            if table in tables:
                raise ValueError(f'duplicate table definition: {table}')
            columns, fks = set(), set()
            for arg in node.args[1:]:
                if not isinstance(arg, ast.Call) or not isinstance(arg.func, ast.Attribute) or arg.func.attr != 'Column':
                    continue
                name = literal(arg.args[0]) if arg.args else None
                if not isinstance(name, str):
                    continue
                columns.add(name)
                for child in arg.args[1:]:
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == 'ForeignKey' and child.args:
                        dest = literal(child.args[0])
                        if isinstance(dest, str):
                            fks.add((name, dest.split('.')[0]))
            tables[table] = {'columns': columns, 'foreign_keys': fks}
    return tables, revisions


def audit(base: Path = VERSIONS) -> list[str]:
    tables, revisions = extract_contract(base)
    errors = []
    for table in REQUIRED_FINANCE_TABLES:
        if table not in tables:
            errors.append(f'missing Finance table in migrations: {table}')
            continue
        for col in sorted(REQUIRED_FINANCE_COLUMNS.get(table, set()) - tables[table]['columns']):
            errors.append(f'missing {table}.{col} in migration DDL')
        for col, dest in sorted(REQUIRED_FINANCE_FOREIGN_KEYS.get(table, set()) - tables[table]['foreign_keys']):
            errors.append(f'missing FK {table}.{col} -> {dest} in migration DDL')
    for child in ('finance_landed_cost_batches', 'finance_receipt_cost_allocations', 'finance_movement_journal_proposals'):
        if child not in revisions:
            errors.append(f'missing revision: {child}')
    return errors


if __name__ == '__main__':
    failures = audit()
    if failures:
        print('BLOCKED: migration source contract differs from schema check')
        for failure in failures:
            print('-', failure)
        raise SystemExit(1)
    print('PASS: four Finance migrations match required table, column and FK contract (offline only)')
