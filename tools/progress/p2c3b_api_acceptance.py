"""P2C3B authenticated integration acceptance against an isolated local API ONLY.

Requires a separately launched ZerroBuild backend connected to
siteforge_equipment_e10_test. Runs write operations against that isolated DB.
Set P2C3B_RUN_WRITES=I_UNDERSTAND_TEST_ONLY.
All credentials/fixture IDs must be supplied via environment variables; no secrets logged.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ValueError(f'Missing environment variable {name}')
    return value


def safe_base(value):
    p = urlsplit(value)
    if p.scheme != 'http' or p.hostname not in ('localhost', '127.0.0.1') or p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
        raise ValueError('P2C3B only permits http://localhost:<port> or http://127.0.0.1:<port>')
    if p.port is None or p.port in (80, 8080):
        raise ValueError('Use a dedicated isolated backend port, not the existing app port')
    return value.rstrip('/')


def request(base, token, method, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = Request(base + path, data=body, method=method, headers={
        'Authorization': f'Bearer {token}', 'Accept': 'application/json', 'Content-Type': 'application/json'
    })
    try:
        with urlopen(req, timeout=25) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = e.read()
        try: detail = json.loads(raw)
        except ValueError: detail = {'error': 'HTTP error'}
        return e.code, detail


def expect(status, permitted, label):
    if status not in permitted:
        raise AssertionError(f'{label}: unexpected HTTP {status}; expected {sorted(permitted)}')
    print(f'PASS {label}: HTTP {status}')


def run():
    if required('P2C3B_RUN_WRITES') != 'I_UNDERSTAND_TEST_ONLY':
        raise ValueError('Writes not authorized')
    if required('P2C3B_DATABASE_NAME') != 'siteforge_equipment_e10_test':
        raise ValueError('Only the isolated database is supported')
    base = safe_base(required('P2C3B_BASE_URL'))
    pid = int(required('P2C3B_PROJECT_ID'))
    other_pid = int(required('P2C3B_OTHER_PROJECT_ID'))
    if pid <= 0 or other_pid <= 0 or pid == other_pid:
        raise ValueError('Provide two different positive project IDs')
    proposer = required('P2C3B_PROPOSER_BEARER')
    reviewer = required('P2C3B_REVIEWER_BEARER')
    outsider = required('P2C3B_OUTSIDER_BEARER')
    if len({proposer, reviewer, outsider}) != 3:
        raise ValueError('Three distinct identities are required')
    report = int(required('P2C3B_REPORT_ID'))
    line = int(required('P2C3B_LINE_ID'))
    qa1 = int(required('P2C3B_QA1_ID'))
    qa2 = int(required('P2C3B_QA2_ID'))
    quantity = Decimal(required('P2C3B_QUANTITY'))
    if min(report, line, qa1, qa2) <= 0 or qa1 == qa2 or not quantity.is_finite() or quantity <= 0:
        raise ValueError('Invalid fixtures or quantity')
    prefix = f'/api/projects/{pid}/progress/evidence-links'
    # Operator verifies in advance: each QA accepted >= quantity, Construction line
    # quantity >= quantity but < 2*quantity, records all Approved and linkable.
    # Two distinct QA requests permit separate proposals with same construction line.
    made = []
    for idx, qa in enumerate((qa1, qa2), start=1):
        code, item = request(base, proposer, 'POST', prefix, {
            'report_id': report, 'progress_line_id': line, 'inspection_request_id': qa,
            'accepted_quantity': str(quantity), 'binding_evidence_ref': f'P2C3B_TEST_{idx}'
        })
        expect(code, {200, 201}, f'proposal {idx}')
        if not isinstance(item, dict) or item.get('status') != 'Proposed' or not item.get('id'):
            raise AssertionError('Proposal not persisted correctly')
        made.append(item)
    a = made[0]
    link_path = f'{prefix}/{a["id"]}'
    code, _ = request(base, proposer, 'POST', link_path + '/decisions/approve', {'version':a['version'], 'note':'Self approval must be denied'})
    expect(code, {403}, 'self approval denied')
    code, _ = request(base, outsider, 'GET', link_path)
    expect(code, {403, 404}, 'outsider cannot read project link')
    code, _ = request(base, reviewer, 'GET', f'/api/projects/{other_pid}/progress/evidence-links/{a["id"]}')
    expect(code, {403, 404}, 'cross-project link hidden')
    def approve(item):
        return request(base, reviewer, 'POST', f'{prefix}/{item["id"]}/decisions/approve', {
            'version': item['version'], 'note': 'P2C3B concurrent approval test'
        })
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(approve, item) for item in made]
        responses = [f.result() for f in futures]
    statuses = [code for code,_ in responses]
    # Exactly one may be approved; the other must fail via capacity conflict.
    if sorted(statuses) != [200, 409]:
        raise AssertionError(f'Concurrent capacity enforcement failed: HTTP statuses {statuses}')
    print('PASS parallel approvals: exactly one approved and one quantity conflict')
    approved_index = statuses.index(200)
    winner = made[approved_index]
    loser = made[1-approved_index]
    code, current = request(base, reviewer, 'GET', f'{prefix}/{winner["id"]}')
    expect(code, {200}, 'approved record readback')
    if current.get('status') != 'Approved':
        raise AssertionError('Successful approval not persisted')
    code, _ = approve(winner)
    expect(code, {409}, 'duplicate/old version approval blocked')
    code, _ = request(base, reviewer, 'POST', f'{prefix}/{loser["id"]}/decisions/reject', {
        'version': loser['version'], 'note':'P2C3B closing unsuccessful concurrency proposal'
    })
    expect(code, {200}, 'rejection persists')
    print('PASS P2C3B authenticated API cases. Run P2C3A DB audit to inspect events.')
    print('NOTE: Test records remain in isolated DB for audit; do not use production.')
    return 0

if __name__ == '__main__':
    try: sys.exit(run())
    except Exception as exc:
        print('FAIL:', str(exc), file=sys.stderr)
        sys.exit(1)
