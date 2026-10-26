"""Read-only evidence snapshots for isolated Stores return-posting race tests.

Run from backend with --project-id and --return-id, storing before/after JSON
outside the repository. This does not enable posting or prove crash rollback.
"""
import argparse
import json
from decimal import Decimal, InvalidOperation
from sqlalchemy import text
from app.db import engine


def as_decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Missing or invalid quantity evidence')
    if not result.is_finite():
        raise ValueError('Nonfinite quantity evidence')
    return result


def assess(before, after, expected_quantity):
    """Compare immutable snapshots; refuse to pass on missing/ambiguous evidence."""
    issues = []
    try:
        q = as_decimal(expected_quantity)
        if q <= 0:
            raise ValueError('Expected quantity must be positive')
        for name, sample in [('before', before), ('after', after)]:
            if not sample.get('read_only') or sample.get('scope') != after.get('scope') or not sample.get('scope'):
                issues.append(f'{name} missing read-only scope evidence')
        if as_decimal(after.get('return_requested_quantity')) < q:
            issues.append('Posting quantity exceeds original return request')
        if as_decimal(after.get('return_received_quantity')) != q:
            issues.append('Posting quantity differs from physically received quantity')
        if before.get('return_requested_quantity') != after.get('return_requested_quantity'):
            issues.append('Requested quantity changed across posting')
        if before.get('return_received_quantity') != after.get('return_received_quantity'):
            issues.append('Received quantity changed across posting')
        if not after.get('source_posting_id') or before.get('source_posting_id') != after.get('source_posting_id'):
            issues.append('Original issue reference missing or changed')
        if after.get('posting_source_id') != after.get('source_posting_id'):
            issues.append('Return posting is not linked to original issue')
        if after.get('posting_warehouse_id') != after.get('balance_key', [None])[0]:
            issues.append('Return posting warehouse differs from stock balance')
        if before.get('return_posting_id') is not None:
            issues.append('Return was posted before the race')
        posting_id = after.get('return_posting_id')
        if not isinstance(posting_id, int) or posting_id < 1:
            issues.append('Return lacks a new posting reference')
        if after.get('return_status') != 'Stock Posted':
            issues.append('Return is not Stock Posted')
        if after.get('posting_status') != 'Posted' or after.get('posting_kind') != 'Return':
            issues.append('Posting is not a posted Return')
        if after.get('posting_line_count') != 1:
            issues.append('Expected exactly one posting line')
        if as_decimal(after.get('posting_line_quantity')) != q:
            issues.append('Posting-line quantity differs from expected return')
        if before.get('balance_key') != after.get('balance_key') or not after.get('balance_key'):
            issues.append('Stock balance identity changed')
        if as_decimal(after.get('on_hand')) - as_decimal(before.get('on_hand')) != q:
            issues.append('Stock on-hand delta is not exactly one return quantity')
        if as_decimal(after.get('reserved')) != as_decimal(before.get('reserved')):
            issues.append('Unexpected reserved-stock movement')
        if after.get('matching_posting_count') != 1:
            issues.append('Expected exactly one matching return posting')
    except (ValueError, TypeError) as err:
        issues.append(str(err))
    return {'result': 'LEDGER_DELTA_PASS' if not issues else 'FAIL_OR_INCONCLUSIVE',
            'issues': issues, 'does_not_prove_crash_rollback': True}


def snapshot(project_id, return_id):
    if min(project_id, return_id) < 1:
        raise ValueError('Positive project and return IDs required')
    if engine.dialect.name != 'postgresql':
        raise ValueError('PostgreSQL required')
    # Transaction-level READ ONLY guarantees this diagnostic cannot mutate stock.
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            record = conn.execute(text('''
              SELECT r.organization_id, r.project_id, r.status, r.stock_posting_id,
                     r.requested_quantity, r.received_quantity,
                     p.source_posting_id AS posting_source_id,
                     p.warehouse_id AS posting_warehouse_id,
                     issue.id AS source_posting_id,
                     p.status AS posting_status, p.kind AS posting_kind,
                     h.stock_posting_line_id AS source_line_id,
                     issue.warehouse_id, il.item_id, il.unit
              FROM stores_material_returns r
              JOIN stores_material_handovers h ON h.id=r.handover_id AND h.project_id=r.project_id AND h.organization_id=r.organization_id
              JOIN stock_posting_lines il ON il.id=h.stock_posting_line_id
              JOIN stock_postings issue ON issue.id=il.posting_id AND issue.project_id=r.project_id AND issue.organization_id=r.organization_id
              LEFT JOIN stock_postings p ON p.id=r.stock_posting_id AND p.project_id=r.project_id AND p.organization_id=r.organization_id
              WHERE r.project_id=:project AND r.id=:return_id
            '''), {'project':project_id,'return_id':return_id}).mappings().one_or_none()
            if record is None:
                raise ValueError('Return or source ledger not found in selected project')
            record = dict(record)
            posted = record['stock_posting_id']
            lines = conn.execute(text('''
              SELECT COUNT(*) AS n, COALESCE(SUM(l.quantity),0) AS qty
              FROM stock_posting_lines l WHERE l.posting_id=:posting AND l.source_line_id=:source
            '''), {'posting':posted or -1,'source':record['source_line_id']}).mappings().one()
            matching = conn.execute(text('''
              SELECT COUNT(DISTINCT p.id) FROM stock_postings p
              JOIN stock_posting_lines l ON l.posting_id=p.id
              WHERE p.organization_id=:org AND p.project_id=:project AND p.kind='Return'
                AND p.status='Posted' AND l.source_line_id=:source
            '''), {'org':record['organization_id'], 'project':project_id,'source':record['source_line_id']}).scalar_one()
            balance = conn.execute(text('''
              SELECT on_hand,reserved FROM stock_balances
              WHERE organization_id=:org AND project_id=:project
                AND warehouse_id=:warehouse AND item_id=:item AND unit=:unit
            '''), {'org':record['organization_id'],'project':project_id,'warehouse':record['warehouse_id'],
                   'item':record['item_id'],'unit':record['unit']}).mappings().one_or_none()
            if balance is None:
                raise ValueError('Authoritative warehouse balance not found')
            return {'read_only':True, 'scope':[record['organization_id'],project_id,return_id],
                    'return_status': record['status'], 'return_posting_id':posted,
                    'return_requested_quantity':str(record['requested_quantity']),
                    'return_received_quantity':str(record['received_quantity']) if record['received_quantity'] is not None else None,
                    'source_posting_id':record['source_posting_id'],
                    'posting_source_id':record['posting_source_id'],
                    'posting_warehouse_id':record['posting_warehouse_id'],
                    'posting_status':record['posting_status'],'posting_kind':record['posting_kind'],
                    'posting_line_count':lines['n'], 'posting_line_quantity':str(lines['qty']),
                    'matching_posting_count':matching,
                    'balance_key':[record['warehouse_id'],record['item_id'],record['unit']],
                    'on_hand':str(balance['on_hand']),'reserved':str(balance['reserved'])}
        finally:
            transaction.rollback()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-id', required=True, type=int)
    parser.add_argument('--return-id', required=True, type=int)
    parser.add_argument('--compare-before', help='Path to saved pre-race JSON snapshot')
    parser.add_argument('--expected-quantity', help='Required with --compare-before')
    args = parser.parse_args()
    current = snapshot(args.project_id, args.return_id)
    if args.compare_before:
        if args.expected_quantity is None:
            parser.error('--expected-quantity required when comparing')
        with open(args.compare_before, encoding='utf-8') as fp:
            previous = json.load(fp)
        report = assess(previous, current, args.expected_quantity)
        print(json.dumps({'snapshot': current, 'assessment':report}, indent=2))
        return 0 if report['result']=='LEDGER_DELTA_PASS' else 1
    print(json.dumps(current, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
