"""Read-only PostgreSQL readiness audit for gated Stores return postings.

Never enables feature flags, calls the posting endpoint or modifies business rows.
Run from siteforge/backend with:
  python -m app.domains.stores_inventory.return_db_readiness --project-id 1
Uses the existing backend DATABASE_URL/settings; output contains no credentials.
"""
import argparse
import json
from sqlalchemy import inspect, text
from app.db import engine

REQUIRED = {
    'stores_material_returns': {'id','organization_id','project_id','handover_id','status','received_quantity','stock_posting_id','version'},
    'stores_material_handovers': {'id','organization_id','project_id','stock_posting_line_id'},
    'stock_postings': {'id','organization_id','project_id','kind','status','number_key'},
    'stock_posting_lines': {'id','posting_id','source_line_id','quantity','item_id','unit'},
    'stock_balances': {'id','organization_id','project_id','on_hand','reserved'},
}

def classify_schema(dialect, present):
    """Pure, testable fail-closed prerequisite assessment."""
    problems = []
    if dialect != 'postgresql':
        problems.append('PostgreSQL is required for row-locking correctness')
    for table, required in REQUIRED.items():
        missing = required - set(present.get(table, ()))
        if missing:
            problems.append(f'{table} missing: {", ".join(sorted(missing))}')
    return problems

def audit(project_id):
    if not isinstance(project_id, int) or project_id < 1:
        raise ValueError('An explicit positive project ID is required')
    if engine.dialect.name != 'postgresql':
        return {'project_id': project_id, 'ready_for_live_posting': False,
                'issues': classify_schema(engine.dialect.name, {}), 'read_only': True}
    inspector = inspect(engine)
    present = {}
    for table in REQUIRED:
        present[table] = {c['name'] for c in inspector.get_columns(table)} if inspector.has_table(table) else set()
    problems = classify_schema(engine.dialect.name, present)
    result = {'project_id':project_id, 'read_only':True,
              'schema_ready':not problems, 'ready_for_live_posting':False,
              'issues':problems,
              'note':'Passing this report does not validate concurrent writes, rollback or authorize enabling return posting.'}
    if problems:
        return result
    # All reads are scoped to the selected project and performed inside a
    # read-only transaction; the final rollback leaves no application changes.
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            bad_balances = conn.execute(text('''
                SELECT count(*) FROM stock_balances
                WHERE project_id = :pid AND (on_hand < 0 OR reserved < 0 OR reserved > on_hand)
            '''), {'pid':project_id}).scalar_one()
            missing_postings = conn.execute(text('''
                SELECT count(*) FROM stores_material_returns r
                WHERE r.project_id = :pid AND r.stock_posting_id IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM stock_postings p WHERE p.id=r.stock_posting_id
                    AND p.project_id=r.project_id AND p.organization_id=r.organization_id
                    AND p.kind='Return' AND p.status='Posted')
            '''), {'pid':project_id}).scalar_one()
            posted_returns = conn.execute(text('''
                SELECT count(*) FROM stores_material_returns
                WHERE project_id=:pid AND stock_posting_id IS NOT NULL
            '''), {'pid':project_id}).scalar_one()
            result['observations'] = {'invalid_stock_balances':bad_balances,
                'return_references_without_valid_posting':missing_postings,
                'recorded_posted_returns':posted_returns}
            if bad_balances:
                result['issues'].append('Existing stock balances violate invariants')
            if missing_postings:
                result['issues'].append('Existing return references lack a valid posted ledger entry')
        finally:
            trans.rollback()
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description='Read-only Stores return PostgreSQL readiness audit')
    parser.add_argument('--project-id', type=int, required=True)
    args=parser.parse_args(argv)
    try:
        result=audit(args.project_id)
    except Exception as exc:
        result={'project_id':args.project_id, 'read_only':True, 'ready_for_live_posting':False,
                'issues':[f'Preflight could not complete: {type(exc).__name__}']}
    print(json.dumps(result, indent=2))
    return 0 if result.get('schema_ready') and not result.get('issues') else 1

if __name__ == '__main__':
    raise SystemExit(main())
