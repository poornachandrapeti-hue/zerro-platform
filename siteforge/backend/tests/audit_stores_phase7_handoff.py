"""Repeatable offline Phase 7 source coverage audit; does not certify production readiness."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
MAIN = (BACKEND / 'app/main.py').read_text()
ROUTES = BACKEND / 'app/domains/stores_inventory'
CHECKS = {
    'preservation routes mounted': 'stores_phase7_preservation_router' in MAIN and (ROUTES/'preservation.py').exists(),
    'cycle count routes mounted': 'stores_phase7_cycle_counts_router' in MAIN and (ROUTES/'cycle_counts.py').exists(),
    'adjustment review routes mounted': 'stores_phase7_adjustment_router' in MAIN and (ROUTES/'stock_adjustments.py').exists(),
    'scrap routes mounted': 'stores_phase7_scrap_router' in MAIN and (ROUTES/'scrap_disposal.py').exists(),
    'monitor feed routes mounted': 'stores_phase7_monitor_router' in MAIN and (ROUTES/'phase7_monitor.py').exists(),
    'preservation holds in receipt-lot reservation': 'preservation' in (ROUTES/'lot_reservations.py').read_text(),
    'preservation holds in receipt-lot issue': 'preservation' in (ROUTES/'atomic_lot_issue.py').read_text(),
    'phase 7 focused regression tests': len(list((BACKEND/'tests').glob('test_stores_phase7_*.py'))) >= 7,
}
versions = list((BACKEND/'migrations/versions').glob('*.py'))
rev = {}; parents=set()
for file in versions:
    s=file.read_text()
    m=re.search(r'^revision\s*(?::\s*str)?\s*=\s*[\'\"]([^\'\"]+)',s,re.M)
    p=re.search(r'^down_revision\s*(?::\s*[^=\n]+)?\s*=\s*(.+)$',s,re.M)
    if m:
        rev[m.group(1)]=file.name
        if p:
            parents.update(re.findall(r'[\'\"]([^\'\"]+)[\'\"]',p.group(1)))
heads=sorted(set(rev)-parents)
CHECKS['one migration head'] = len(heads)==1
out={'phase':'Phase 7','kind':'offline_source_contract_audit','checks':CHECKS,'passed':sum(CHECKS.values()),'total':len(CHECKS),'migration_heads':heads,'production_ready':False,'limitations':['PostgreSQL transaction/concurrency tests deferred','Frontend build and Docker end-to-end unverified','No authoritative lot-level point-in-time book count','No stock adjustment or scrap write-off posting','Preservation holds not complete for transfer lots/legacy writers','Separate Command Center backend not connected']}
path=ROOT/'STORES_PHASE7_FINAL_SOURCE_AUDIT.json'
path.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'passed':out['passed'],'total':out['total'],'heads':heads},indent=2))
raise SystemExit(0 if all(CHECKS.values()) else 1)
