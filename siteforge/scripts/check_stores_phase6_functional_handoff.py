"""Reproducible source-level Phase 6 handoff audit (not a deployment test)."""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / 'backend/app/domains/stores_inventory'
MAIN = (ROOT/'backend/app/main.py').read_text()
CONTRACTS = {
    'transfer request and listing': ('transfers.py', ['@router.post(\'/material-transfers\'', '@router.get(\'/material-transfers\'']),
    'approval, dispatch and same-project receipt': ('transfers.py', ['/decision\'', '/dispatch\'', '/receive\'']),
    'destination-project inbox and acceptance': ('transfers.py', ['destination-inbox', 'destination/{transfer_id}/accept', 'destination/{transfer_id}/receive']),
    'independent discrepancy decision': ('transfers.py', ['resolve-discrepancy']),
    'custody confirmation': ('transfers.py', ['confirm-custody']),
    'vendor return and replacement': ('vendor_returns.py', ['/vendor-returns\'', '/decision\'', '/dispatch\'', '/vendor-acknowledgment\'', '/replacement\'']),
    'transfer monitoring': ('transfer_monitor.py', ['/material-transfers/monitor', '/internal-command-center/transfer-monitor']),
    'preflight and fail-closed posting': ('transfer_posting_readiness.py', ['posting-readiness', 'post-stock', '503']),
}
results = []
for label,(filename,needles) in CONTRACTS.items():
    path=DOMAIN/filename
    src=path.read_text() if path.exists() else ''
    missing=[needle for needle in needles if needle not in src]
    results.append({'contract':label,'status':'PASS' if not missing else 'FAIL','missing':missing})
for label,needle in [('transfer router mounted','stores_phase6_transfers_router'),('vendor return router mounted','stores_vendor_returns_router'),('preflight router mounted','stores_phase6_transfer_posting_readiness_router'),('monitor router mounted','stores_phase6_transfer_monitor_router')]:
    results.append({'contract':label,'status':'PASS' if f'app.include_router({needle})' in MAIN else 'FAIL','missing':[]})
# Prevent presenting custody-only transfers as physically ledger-posted.
src=(DOMAIN/'transfer_posting_readiness.py').read_text()
block = re.search(r'def disabled_transfer_posting\b[\s\S]{0,750}',src)
results.append({'contract':'physical transfer posting remains blocked','status':'PASS' if block and '503' in block.group() else 'FAIL','missing':[]})
report={'scope':'source contracts only: NOT live database, frontend build, or deployment','results':results,'passed':sum(x['status']=='PASS' for x in results),'failed':sum(x['status']=='FAIL' for x in results),'production_ready':False,'open_blockers':['Atomic dual-warehouse lot-provenance-safe posting not implemented','PostgreSQL concurrency and migration execution deferred','Vendor acknowledgment is evidence recorded by Procurement, not supplier-authenticated','Separate Command Center consumer backend not connected','Frontend TypeScript build and Docker E2E not executed']}
output=ROOT/'STORES_PHASE6_SOURCE_AUDIT.json'
output.write_text(json.dumps(report,indent=2)+'\n')
print(f"Phase 6 source audit: {report['passed']} PASS, {report['failed']} FAIL; output: {output}")
sys.exit(bool(report['failed']))
