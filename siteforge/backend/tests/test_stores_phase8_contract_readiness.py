from types import SimpleNamespace as R
from app.domains.stores_inventory.phase8_contract_readiness import contract_reference_readiness


def request(**overrides):
    data = dict(id=1, requirement_line_id=13, requester_company_id=8,
                work_package_id=9, planning_wbs_id=10, item_id=11,
                base_unit='EA', status='Approved')
    data.update(overrides)
    return R(**data)


def test_company_match_never_claims_free_issue_approval():
    row = contract_reference_readiness([request()], [R(id=21, material_request_id=1)],
                                       [R(id=5, counterparty_company_id=8)])[0]
    assert row['contract_candidate_ids'] == [5]
    assert row['handover_ids'] == [21]
    assert row['readiness'] == 'Blocked'
    assert not row['explicit_contract_link_verified']
    assert not row['finance_recovery_authorized']


def test_missing_requirement_and_company_flagged():
    row = contract_reference_readiness([request(requirement_line_id=None, requester_company_id=None)], [], [])[0]
    assert any('Procurement' in b for b in row['blockers'])
    assert any('Requester company' in b for b in row['blockers'])


def test_ambiguous_contracts_never_auto_selected():
    row = contract_reference_readiness([request()], [],
        [R(id=10, counterparty_company_id=8), R(id=9, counterparty_company_id=8)])[0]
    assert row['contract_candidate_ids'] == [9, 10]
    assert any('ambiguous' in b for b in row['blockers'])
