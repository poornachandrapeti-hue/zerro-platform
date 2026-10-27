"""P3C1E read-only inspection of independently verified quantity records.

Usage: DATABASE_URL=... python tools/progress/p3c1e_verification_audit.py
Never updates or inserts into any database. Execute against an isolated DB copy.
"""
import os
import sys
from collections import Counter
from sqlalchemy import create_engine, text

EXPECTED = {'Proposed': ['Proposed'], 'Approved': ['Proposed', 'Approved'],
            'Rejected': ['Proposed', 'Rejected'], 'Revoked': ['Proposed', 'Approved', 'Revoked']}


def evaluate(rows, event_rows):
    """Pure invariant checks; rows/event_rows are mappings returned by SQLAlchemy."""
    errors=[]
    by_id={}
    for row in rows:
        r=dict(row)
        rid=r['id']; by_id[rid]=r
        if r['status'] not in EXPECTED:
            errors.append(f'{rid}: unknown status')
            continue
        if r['verified_quantity'] is None or r['verified_quantity'] <= 0:
            errors.append(f'{rid}: non-positive verified quantity')
        if r['version'] is None or r['version'] < 1:
            errors.append(f'{rid}: invalid version')
        if r['status'] != 'Proposed' and r['reviewer_user_id'] is None:
            errors.append(f'{rid}: decision without reviewer')
        if r['reviewer_user_id'] is not None and r['reviewer_user_id'] == r['proposer_user_id']:
            errors.append(f'{rid}: self review')
        if r['status'] == 'Approved' and r['verified_at'] is None:
            errors.append(f'{rid}: approval missing timestamp')
        if r['status'] == 'Proposed' and r['reviewer_user_id'] is not None:
            errors.append(f'{rid}: proposed record unexpectedly reviewed')
    events={}
    for ev in event_rows:
        e=dict(ev); events.setdefault(e['verification_id'],[]).append(e)
        r=by_id.get(e['verification_id'])
        if r is None:
            errors.append(f"event {e['id']}: orphan")
        elif (e['organization_id'],e['project_id']) != (r['organization_id'],r['project_id']):
            errors.append(f"event {e['id']}: organization/project mismatch")
    for rid,r in by_id.items():
        ordered=sorted(events.get(rid,[]), key=lambda e:(e['created_at'],e['id']))
        actions=[e['action'] for e in ordered]
        expected=EXPECTED.get(r['status'])
        if expected and actions != expected:
            errors.append(f'{rid}: event sequence {actions} does not match {expected}')
        if r['version'] != len(ordered):
            errors.append(f'{rid}: version/event count mismatch')
        if ordered and r['status'] != 'Proposed' and ordered[-1]['actor_user_id'] != r['reviewer_user_id']:
            errors.append(f'{rid}: last reviewer and audit actor mismatch')
    approved=Counter((r['organization_id'],r['project_id'],r['progress_line_id'])
                     for r in by_id.values() if r['status']=='Approved')
    for key,count in approved.items():
        if count > 1:
            errors.append(f'{key}: {count} simultaneously approved quantity verifications')
    return errors


def main():
    url=os.environ.get('DATABASE_URL','')
    if not url or '/siteforge_equipment_e10_test' not in url.split('?')[0]:
        print('FAIL: DATABASE_URL must target the isolated siteforge_equipment_e10_test database', file=sys.stderr)
        return 2
    engine=create_engine(url, connect_args={'options':'-c default_transaction_read_only=on'}, pool_pre_ping=True)
    with engine.connect() as conn:
        version=conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        if version != 'progress_p3c1c_qty_verify':
            print(f'FAIL: unexpected Alembic version {version}', file=sys.stderr)
            return 2
        rows=conn.execute(text('SELECT id, organization_id, project_id, progress_line_id, '
            'verified_quantity, status, version, proposer_user_id, reviewer_user_id, verified_at '
            'FROM progress_quantity_verifications')).mappings().all()
        events=conn.execute(text('SELECT id, verification_id, organization_id, project_id, '
            'action, actor_user_id, created_at FROM progress_quantity_verification_events')).mappings().all()
    errors=evaluate(rows,events)
    print(f'Progress verification audit: {len(rows)} records, {len(events)} events, {len(errors)} findings')
    for error in errors[:100]: print('FAIL:',error)
    if not rows:
        print('NOTICE: empty table; no transactional workflow coverage. Do not treat as approval acceptance.')
    print('NOTICE: This audit does not validate external/physical measurement evidence, API RBAC, concurrency, or billing.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
