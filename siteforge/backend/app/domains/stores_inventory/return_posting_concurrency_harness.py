"""Opt-in API-level return-posting race harness for a disposable LOCAL test database.

Never run against an existing project or a shared database. Both requests mutate stock
if the return-posting feature has been enabled in that test deployment.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def validate_target(base_url, confirmation, project_id, return_id, version):
    parsed = urlsplit(base_url)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1') or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('Only plain HTTP localhost URLs without path or credentials are supported')
    if confirmation != 'I_UNDERSTAND_THIS_POSTS_TO_DISPOSABLE_STOCK':
        raise ValueError('Explicit disposable database confirmation required')
    if not all(isinstance(i, int) and i > 0 for i in (project_id, return_id, version)):
        raise ValueError('Positive project, return and version identifiers required')
    if os.getenv('STORES_RETURN_TEST_DATABASE_ISOLATED') != 'yes':
        raise ValueError('Set STORES_RETURN_TEST_DATABASE_ISOLATED=yes for an isolated database only')


def post_once(url, token, version, posting_number):
    body = json.dumps({'version': version, 'posting_number': posting_number,
                       'evidence': 'Disposable UAT simultaneous return-posting race'}).encode()
    request = Request(url, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with urlopen(request, timeout=15) as response:
            return response.status
    except HTTPError as error:
        return error.code
    except URLError as error:
        raise RuntimeError('Test endpoint unreachable') from error


def classify(results):
    if len(results) != 2:
        return 'INCONCLUSIVE'
    if sorted(results) == [200, 409]:
        return 'RACE_GATE_PASS_API_ONLY'
    if results.count(200) > 1:
        return 'FAIL_MULTIPLE_SUCCESSES'
    return 'INCONCLUSIVE'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--return-id', type=int, required=True)
    parser.add_argument('--version', type=int, required=True)
    parser.add_argument('--confirm', required=True)
    arguments = parser.parse_args(argv)
    validate_target(arguments.base_url, arguments.confirm, arguments.project_id,
                    arguments.return_id, arguments.version)
    token = os.getenv('STORES_RETURN_TEST_AUTH_TOKEN', '')
    if not token:
        parser.error('STORES_RETURN_TEST_AUTH_TOKEN is required and must be from an authorized test user')
    url = f"{arguments.base_url.rstrip('/')}/api/projects/{arguments.project_id}/stores/material-returns/{arguments.return_id}/post-stock"
    # Same posting number and record version deliberately contend for a single return.
    number = f'UAT-RACE-{arguments.project_id}-{arguments.return_id}'
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(post_once, url, token, arguments.version, number) for _ in range(2)]
        statuses = [f.result() for f in futures]
    conclusion = classify(statuses)
    print(json.dumps({'http_statuses': statuses, 'result': conclusion,
                      'stock_ledger_and_rollback_verified': False,
                      'next_action': 'Check one posted Return and one stock balance delta in database; test rollback separately'}))
    return 0 if conclusion == 'RACE_GATE_PASS_API_ONLY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
