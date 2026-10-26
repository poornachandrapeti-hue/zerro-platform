"""Read-only P2C3 PostgreSQL evidence-link checks. Requires SQLAlchemy + psycopg.
Usage: DATABASE_URL=<test DB url> python tools/progress/p2c3_audit.py
Never supply a live DB URL; must be an explicitly named isolated database.
"""
import os
import sys
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

EXPECTED_DB = 'siteforge_equipment_e10_test'
REQUIRED = {'progress_evidence_links','progress_evidence_link_events'}
EXPECTED_CONSTRAINTS = {'uq_progress_evidence_pair','ck_progress_evidence_link_status','ck_progress_evidence_accepted_qty','ck_progress_evidence_link_action'}


def issues_from_rows(link_rows, event_rows):
    problems=[]
    event_map={}
    for e in event_rows:
        event_map.setdefault(e['link_id'], []).append(e['action'])
    for link in link_rows:
        actions=event_map.get(link['id'],[])
        if not actions or actions[0]!='Proposed':
            problems.append(f"link {link['id']}: missing initial Proposed audit event")
        if link['status'] in ('Approved','Rejected','Revoked') and link['status'] not in actions:
            problems.append(f"link {link['id']}: status missing matching audit event")
        if link['status']=='Approved' and link['created_by']==link['reviewed_by']:
            problems.append(f"link {link['id']}: same proposer and reviewer")
        if link['status']=='Approved' and Decimal(str(link['accepted_quantity']))<=0:
            problems.append(f"link {link['id']}: non-positive approved quantity")
        if link['status']=='Approved' and link['reviewed_by'] is None:
            problems.append(f"link {link['id']}: approved without reviewer")
        if link['version'] != len(actions):
            problems.append(f"link {link['id']}: version {link['version']} differs from {len(actions)} events")
    return problems


def run():
    raw=os.environ.get('DATABASE_URL','')
    if not raw:
        raise RuntimeError('DATABASE_URL required (test DB only)')
    url=make_url(raw)
    if url.database!=EXPECTED_DB:
        raise RuntimeError(f'Refusing database {url.database!r}; allowed: {EXPECTED_DB}')
    engine=create_engine(url, pool_pre_ping=True)
    problems=[]
    with engine.connect() as db:
        ident=db.execute(text('select current_database(), current_user')).one()
        if ident[0]!=EXPECTED_DB:
            raise RuntimeError('Actual connected database mismatch; abort')
        print(f'CONNECTED TO ISOLATED DATABASE: {ident[0]} as {ident[1]}')
        tables={r[0] for r in db.execute(text("select tablename from pg_tables where schemaname='public'"))}
        missing=REQUIRED-tables
        if missing:
            raise RuntimeError(f'P2C2A migration has not been applied to isolated DB: {sorted(missing)}')
        constraints={r[0] for r in db.execute(text("""select c.conname from pg_constraint c join pg_class t on t.oid=c.conrelid join pg_namespace n on n.oid=t.relnamespace where n.nspname='public' and t.relname in ('progress_evidence_links','progress_evidence_link_events')"""))}
        for name in sorted(EXPECTED_CONSTRAINTS-constraints):
            problems.append(f'Missing constraint: {name}')
        rows=db.execute(text('select id,organization_id,project_id,progress_line_id,inspection_request_id,accepted_quantity,status,created_by,reviewed_by,version from public.progress_evidence_links order by id')).mappings().all()
        events=db.execute(text('select link_id,action from public.progress_evidence_link_events order by link_id,id')).mappings().all()
        problems += issues_from_rows(rows,events)
        # DB referential integrity should protect these, but explicitly report for diagnosis.
        orphan=db.execute(text('select count(*) from public.progress_evidence_link_events e left join public.progress_evidence_links l on l.id=e.link_id where l.id is null')).scalar_one()
        if orphan: problems.append(f'{orphan} orphan audit events')
        # Check cumulative approved values against the authoritative source readbacks.
        exceeded=db.execute(text('''
        with totals as (
          select progress_line_id, sum(accepted_quantity) as qty from public.progress_evidence_links where status='Approved' group by progress_line_id
        ) select t.progress_line_id from totals t join public.progress_lines l on l.id=t.progress_line_id where t.qty>l.quantity
        ''' )).scalars().all()
        for k in exceeded: problems.append(f'approved quantity exceeds Construction line {k}')
        qa_exceeded=db.execute(text('''
        with totals as (
          select inspection_request_id, sum(accepted_quantity) as qty from public.progress_evidence_links where status='Approved' group by inspection_request_id
        ) select t.inspection_request_id from totals t join public.quality_construction_requests q on q.id=t.inspection_request_id where t.qty>q.accepted_quantity
        ''' )).scalars().all()
        for k in qa_exceeded: problems.append(f'approved quantity exceeds QA request {k}')
        print(f'EVIDENCE LINKS: {len(rows)}; AUDIT EVENTS: {len(events)}')
        if not rows: print('NOTICE: no real evidence links; transactional/API/concurrency behavior is NOT tested')
        print(f'CONSTRAINTS: {len(EXPECTED_CONSTRAINTS & constraints)}/{len(EXPECTED_CONSTRAINTS)} required')
    engine.dispose()
    if problems:
        for p in problems: print('FAIL:',p)
        return 1
    print('PASS: isolated DB structure and current records read-only audit')
    print('NOT COVERED: authenticated API transactions, concurrent approvals, source revocation, reviewer role grants')
    return 0

if __name__=='__main__':
    try: sys.exit(run())
    except Exception as e:
        print('ERROR:',e, file=sys.stderr)
        sys.exit(2)
