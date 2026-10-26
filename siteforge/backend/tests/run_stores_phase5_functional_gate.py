"""Offline, dependency-light Phase 5 functional contract inventory.

Checks actual route declarations and router mounting. These are structural checks,
not a substitute for database and E2E verification.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOM = ROOT / 'app' / 'domains' / 'stores_inventory'
MAIN = (ROOT / 'app' / 'main.py').read_text()
CHECKS = {
    'issue_handover': ('material_handovers.py', 'POST', '/material-handovers'),
    'contractor_ack': ('material_handovers.py', 'POST', '/material-handovers/{handover_id}/acknowledge'),
    'discrepancy_review': ('material_handovers.py', 'POST', '/material-handovers/{handover_id}/resolve'),
    'return_request': ('material_returns.py', 'POST', '/material-returns'),
    'return_receipt': ('material_returns.py', 'POST', '/material-returns/{return_id}/receive'),
    'return_qa': ('material_returns.py', 'POST', '/material-returns/{return_id}/qa-disposition'),
    'return_placement': ('material_returns.py', 'POST', '/material-returns/{return_id}/placement'),
    'return_posting_gated': ('material_returns.py', 'POST', '/material-returns/{return_id}/post-stock'),
    'return_exception': ('material_returns.py', 'GET', '/material-returns/exception-monitor'),
    'construction_usage': ('construction_material_usage.py', 'POST', '/phase5/material-usages'),
    'independent_qa_usage': ('construction_material_usage.py', 'POST', '/phase5/material-usages/{usage_id}/verify'),
    'qa_usage_queue': ('construction_material_usage.py', 'GET', '/phase5/material-usages/qa-queue'),
    'construction_manager_balance': ('phase5_material_balance.py', 'GET', '/phase5/construction-manager-material-balance'),
}
mounts = ['stores_material_handovers_router', 'stores_material_returns_router', 'stores_construction_material_usage_router', 'stores_phase5_material_balance_router']
results = {}
for name, (file, verb, url) in CHECKS.items():
    source = (DOM / file).read_text()
    pattern = rf'@router\.{verb.lower()}\([\'\"]{re.escape(url)}[\'\"]'
    results[name] = {'present': bool(re.search(pattern, source)), 'source': file, 'path': url}
for name in mounts:
    results['mounted_' + name] = {'present': f'app.include_router({name})' in MAIN}
source = (DOM / 'material_returns.py').read_text()
results['return_post_gate_remains'] = {'present': all(s in source for s in ['STORES_ATOMIC_LOT_RETURN_ENABLED','STORES_LOT_WRITER_CUTOVER'])}
summary = {'as_of_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'static source contracts only', 'checks': results, 'passed': sum(v['present'] for v in results.values()), 'total': len(results), 'live_db_validated': False, 'frontend_built': False, 'command_center_runtime_connected': False, 'release_ready': False}
if __name__ == '__main__':
    output = ROOT / 'stores_phase5_functional_gate.json'
    output.write_text(json.dumps(summary, indent=2) + '\n')
    print(f"Phase 5 static functional gate: {summary['passed']}/{summary['total']} checks")
    print('Production gate: BLOCKED (database / frontend / cross-module runtime checks deferred)')
    raise SystemExit(0 if summary['passed'] == summary['total'] else 1)
