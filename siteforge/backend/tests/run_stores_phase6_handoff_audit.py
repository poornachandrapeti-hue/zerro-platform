"""Offline Phase 6 source handoff audit; does not approve inventory activation."""
from pathlib import Path
import ast, json, re
ROOT = Path(__file__).resolve().parents[2]
DOM = ROOT / 'backend/app/domains/stores_inventory'
checks = {
 'transfer custody workflow': ['transfers.py'],
 'vendor return workflow': ['vendor_returns.py'],
 'transfer monitoring': ['transfer_monitor.py'],
 'paired posting and preflight': ['transfer_posting_readiness.py'],
 'destination QA reconciliation': ['transfer_qa_reconciliation.py'],
 'destination QA acceptance': ['transfer_lot_eligibility.py'],
 'transfer reservation activation': ['transfer_reservation_activation.py'],
 'transfer reservation release': ['transfer_reservation_release.py'],
 'transfer lot issue': ['transfer_lot_issue.py'],
 'transfer allocation preview': ['transfer_allocation_preview.py'],
 'material return integration': ['material_returns.py'],
}
results = []
for label, filenames in checks.items():
    paths=[DOM / n for n in filenames]
    success=all(p.exists() for p in paths)
    errors=[]
    for p in paths:
        if p.exists():
            try: ast.parse(p.read_text(encoding='utf-8'))
            except SyntaxError as e: success=False; errors.append(str(e))
    results.append({'check':label,'passed':success,'errors':errors})
flags=['STORES_TRANSFER_LOT_ISSUE_ENABLED','STORES_TRANSFER_RESERVATION_ACTIVATION_ENABLED','STORES_TRANSFER_RESERVATION_RELEASE_ENABLED','STORES_LOT_WRITER_CUTOVER']
source='\n'.join(p.read_text(encoding='utf-8') for p in DOM.glob('*.py'))
for flag in flags:
    results.append({'check':'feature gate '+flag,'passed':flag in source})
versions=ROOT/'backend/migrations/versions'
revisions={}; parents=[]
for p in versions.glob('*.py'):
    s=p.read_text(encoding='utf-8')
    rev=re.search(r'^revision\s*(?::\s*[^=]+)?=\s*[\'\"]([^\'\"]+)',s,re.M)
    down=re.search(r'^down_revision\s*(?::\s*[^=]+)?=\s*[\'\"]([^\'\"]+)',s,re.M)
    if rev:
        revisions[rev.group(1)]=p.name
        if down: parents.append(down.group(1))
heads=set(revisions)-set(parents)
results.append({'check':'single migration head','passed':len(heads)==1,'heads':sorted(heads)})
report={'scope':'Phase 6 source-level audit only','checks':results,'passed':sum(r['passed'] for r in results),'total':len(results),'release_ready':False,'stock_posting_enabled':False,'deferred':['PostgreSQL migration execution and concurrency tests','Docker and frontend build','inter-project atomic posting','transfer reversal handling','vendor replacement GRN','separate Command Center runtime connection']}
out=ROOT/'STORES_PHASE6_FINAL_SOURCE_AUDIT.json';out.write_text(json.dumps(report,indent=2))
print(json.dumps({'passed':report['passed'],'total':report['total'],'failed':[r['check'] for r in results if not r['passed']],'migration_heads':sorted(heads)},indent=2))
raise SystemExit(0 if report['passed']==report['total'] else 1)
