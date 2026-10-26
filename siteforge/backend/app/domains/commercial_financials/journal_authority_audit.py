"""Read-only source capability audit for Finance journal integration.

This is a release preflight, not evidence that any deployed database matches source.
Supplier invoice verification is deliberately NOT accepted as a GL journal.
"""
import ast
import json
from pathlib import Path

REQUIRED_POSTING_FIELDS = frozenset({
    'organization_id', 'project_id', 'stock_movement_id', 'currency',
    'total_debit', 'total_credit', 'status', 'posted_at', 'posted_by',
})


def inspect_finance_models(source: str) -> dict:
    tree = ast.parse(source)
    classes = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        table = None
        fields = set()
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__tablename__' for t in stmt.targets):
                if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                    table = stmt.value.value
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                target = stmt.target if isinstance(stmt, ast.AnnAssign) else (stmt.targets[0] if len(stmt.targets) == 1 else None)
                if isinstance(target, ast.Name):
                    fields.add(target.id)
        if table:
            classes[table] = sorted(fields)
    eligible = {table: fields for table, fields in classes.items()
                if REQUIRED_POSTING_FIELDS.issubset(fields)}
    return {
        'status': 'SOURCE_CONTRACT_PRESENT_DB_UNVERIFIED' if eligible else 'BLOCKED',
        'general_ledger_posting_candidates': eligible,
        'journal_posting_authority_verified': False,
        'stock_movement_valuation_verified': False,
        'reason': 'Requires deployed Finance ledger read-back, posted movement cost and independent reconciliation'
                  if eligible else 'No Finance model exposes required movement-linked GL posting evidence',
        'finance_supplier_invoice_posting_is_not_general_ledger': True,
        'model_tables_checked': len(classes),
    }


def main():
    models_path = Path(__file__).with_name('models.py')
    print(json.dumps(inspect_finance_models(models_path.read_text(encoding='utf-8')), indent=2))
    return 2  # Block deployment on source-only evidence regardless of candidate discovery.


if __name__ == '__main__':
    raise SystemExit(main())
