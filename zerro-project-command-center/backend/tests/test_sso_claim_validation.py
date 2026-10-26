from copy import deepcopy
import pytest
from app.sso_claims import validate_handoff_claims
from app.vision_ticket import issue_ticket, verify_ticket

VALID = {'sub': '42', 'org': '7', 'role': 'VIEWER', 'grants': [
    {'code': 'PROJECT-A', 'discipline_ids': [1], 'discipline_names': {'1':'Civil'}, 'full_scope':False, 'commercial':False}
]}

def test_valid_claims():
    assert validate_handoff_claims(VALID, '7')['sub'] == '42'

@pytest.mark.parametrize('mutation', [
    {'sub': None}, {'sub': ''}, {'sub': True}, {'org':'8'}, {'role':'ADMIN'},
    {'grants': 'all'}, {'grants': [None]}, {'grants': [{'code':'A'}]},
])
def test_reject_bad_claims(mutation):
    claims = deepcopy(VALID)
    claims.update(mutation)
    with pytest.raises(ValueError): validate_handoff_claims(claims, '7')

def test_reject_duplicate_grant():
    claims = deepcopy(VALID)
    claims['grants'].append(deepcopy(claims['grants'][0]))
    with pytest.raises(ValueError): validate_handoff_claims(claims, '7')

def test_tampered_ticket_rejected():
    token = issue_ticket('x'*40, VALID)
    body, sig = token.split('.')
    bad = body + '.' + ('A' if sig[0]!='A' else 'B') + sig[1:]
    with pytest.raises(ValueError): verify_ticket('x'*40, bad)
