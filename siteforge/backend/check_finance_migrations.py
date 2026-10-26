"""Read-only static Alembic revision graph preflight; requires only Python stdlib."""
from __future__ import annotations
import ast
import json
from pathlib import Path
import sys


def audit(folder: Path) -> dict:
    revisions = {}
    errors = []
    for file in sorted(folder.glob('*.py')):
        try:
            tree = ast.parse(file.read_text(encoding='utf-8'), filename=str(file))
            info = {}
            for statement in tree.body:
                if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    assignments = ((t, statement.value) for t in statement.targets) if isinstance(statement, ast.Assign) else ((statement.target, statement.value),)
                    for target, value in assignments:
                        if isinstance(target, ast.Name) and target.id in ('revision', 'down_revision'):
                            info[target.id] = ast.literal_eval(value)
            revision = info.get('revision')
            if not isinstance(revision, str) or not revision:
                errors.append(f'{file.name}: missing or invalid revision')
            elif revision in revisions:
                errors.append(f'{file.name}: duplicate revision {revision}')
            else:
                revisions[revision] = (info.get('down_revision'), file.name)
        except (SyntaxError, ValueError, TypeError) as e:
            errors.append(f'{file.name}: {e}')
    parents = set()
    for rev, (parent, name) in revisions.items():
        links = parent if isinstance(parent, (list, tuple)) else (parent,)
        for node in links:
            if node is not None:
                parents.add(node)
                if node not in revisions:
                    errors.append(f'{name}: missing parent revision {node}')
    heads = sorted(set(revisions) - parents)
    if len(heads) != 1:
        errors.append(f'Expected exactly one migration head; found {len(heads)}: {heads}')
    for revision in ('finance_inventory_costing_policy', 'finance_landed_cost_batches', 'finance_receipt_cost_allocations'):
        if revision not in revisions:
            errors.append(f'Missing Finance revision: {revision}')
    # Traverse parents and fail closed on loops; other disconnected components would have extra heads.
    for rev in revisions:
        seen = set()
        stack = [rev]
        while stack:
            node = stack.pop()
            if node in seen:
                errors.append(f'Cycle or shared-parent traversal detected from {rev}: {node}')
                break
            seen.add(node)
            parent = revisions[node][0]
            if isinstance(parent, (tuple, list)):
                stack.extend(x for x in parent if x in revisions)
            elif parent in revisions:
                stack.append(parent)
    return {'ok': not errors, 'revision_count': len(revisions), 'heads': heads, 'errors': sorted(set(errors))}

if __name__ == '__main__':
    result = audit(Path(__file__).resolve().parent / 'migrations' / 'versions')
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['ok'] else 1)
