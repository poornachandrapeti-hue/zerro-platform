"""Fail-closed validation of cross-service SSO handoff payloads."""


def validate_handoff_claims(claims: object, expected_org: str) -> dict:
    if not isinstance(claims, dict):
        raise ValueError('Invalid claims payload')
    sub = claims.get('sub')
    org = claims.get('org')
    if not isinstance(sub, (str, int)) or isinstance(sub, bool) or not str(sub).strip():
        raise ValueError('Missing subject')
    if not isinstance(org, (str, int)) or str(org) != expected_org:
        raise ValueError('Organization mismatch')
    if claims.get('role') != 'VIEWER':
        raise ValueError('Invalid role')
    grants = claims.get('grants')
    if not isinstance(grants, list) or len(grants) > 1000:
        raise ValueError('Invalid grants')
    seen = set()
    for grant in grants:
        if not isinstance(grant, dict):
            raise ValueError('Invalid grant')
        code = grant.get('code')
        ids = grant.get('discipline_ids')
        names = grant.get('discipline_names')
        if not isinstance(code, str) or not code.strip() or code in seen:
            raise ValueError('Missing or duplicate project')
        seen.add(code)
        if not isinstance(ids, list) or len(ids) > 500 or any(not isinstance(v, int) or isinstance(v, bool) for v in ids):
            raise ValueError('Invalid discipline IDs')
        if not isinstance(names, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in names.items()):
            raise ValueError('Invalid discipline names')
        if grant.get('full_scope') not in (True, False):
            raise ValueError('Invalid scope')
        if grant.get('commercial') not in (True, False):
            raise ValueError('Invalid commercial permission')
        if len(set(ids)) != len(ids) or any(str(i) not in names for i in ids):
            raise ValueError('Incomplete discipline mapping')
    return {'sub': str(sub), 'org': str(org), 'role': 'VIEWER', 'grants': grants}
