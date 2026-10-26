"""Execute Stores Phase 4 test gate. Never claim release readiness with skipped tests.

Usage: python tests/run_stores_phase4_release_gate.py
Requires a dedicated migrated PostgreSQL database via STORES_TEST_DATABASE_URL
for a potential PASS. This script never enables inventory feature flags.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

BACKEND = Path(__file__).resolve().parents[1]
REPORT = BACKEND / 'stores_phase4_release_report.json'
JUNIT = BACKEND / 'stores_phase4_release_junit.xml'

def main():
    env = os.environ.copy()
    # This test runner must not permit accidental use of enabled writer flags.
    prohibited = [k for k in ('STORES_LOT_WRITER_CUTOVER', 'STORES_ENABLE_ATOMIC_LOT_ISSUE',
              'STORES_ENABLE_ATOMIC_LOT_ACCEPTANCE', 'STORES_ENABLE_LOT_RESERVATIONS')
             if env.get(k, '').lower() in ('1','true','yes','on')]
    if prohibited:
        print('RELEASE GATE BLOCKED: enabled stock writer flags: ' + ', '.join(prohibited), file=sys.stderr)
        return 2
    env['STORES_LOT_WRITER_CUTOVER'] = 'false'
    started = time.time()
    args = [sys.executable, '-m', 'pytest', '-q', 'tests/test_stores_*',
            '--junitxml', str(JUNIT)]
    # pytest does not expand shell globs passed via subprocess, so discover files ourselves.
    args = args[:4] + [str(p.relative_to(BACKEND)) for p in sorted((BACKEND/'tests').glob('test_stores_*.py'))] + args[5:]
    process = subprocess.run(args, cwd=BACKEND, env=env, capture_output=True, text=True)
    print(process.stdout[-4000:]); print(process.stderr[-1500:], file=sys.stderr)
    totals = dict(tests=0, failures=0, errors=0, skipped=0)
    if JUNIT.exists():
        root = ET.parse(JUNIT).getroot()
        suites = [root] if root.tag == 'testsuite' else root.findall('.//testsuite')
        # Avoid double count when testsuites contains nested suites.
        suites = [s for s in suites if not s.findall('testsuite')]
        for suite in suites:
            for key in totals:
                totals[key] += int(suite.get(key, '0'))
    configured_pg = bool(env.get('STORES_TEST_DATABASE_URL'))
    result = {
        'gate': 'STORES_PHASE4', 'outcome': 'PASS' if process.returncode == 0 and totals['skipped'] == 0 and configured_pg else 'BLOCKED',
        'returncode': process.returncode, 'test_counts': totals,
        'postgres_test_url_configured': configured_pg,
        'runtime_seconds': round(time.time()-started, 2),
        'reason': ('No PostgreSQL test URL configured' if not configured_pg else
                   'Some tests skipped or failed' if totals['skipped'] or process.returncode else 'All suite checks passed'),
        'live_inventory_writer_cutover_enabled': False,
        'note': 'Passing this test suite alone does not certify live Docker, frontend or separate Command Center integration.'
    }
    REPORT.write_text(json.dumps(result, indent=2)+'\n')
    print('GATE: ' + result['outcome'] + '; ' + result['reason'])
    print('Report: ' + str(REPORT))
    return 0 if result['outcome']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
