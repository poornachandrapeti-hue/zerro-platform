from types import SimpleNamespace
from app.domains.stores_inventory.phase8_contract_readiness import contract_reference_readiness, ContractObligationLinkIn
from pydantic import ValidationError


def request():
    return SimpleNamespace(id=9, requirement_line_id=21, requester_company_id=3,
        work_package_id=6, planning_wbs_id=2, item_id=5, base_unit='EA', status='Approved')


def test_explicit_reference_does_not_grant_free_issue_or_recovery():
    contract = SimpleNamespace(id=12, counterparty_company_id=3)
    link = SimpleNamespace(material_request_id=9, contract_id=12, obligation_id=45)
    obligation = SimpleNamespace(id=45, contract_id=12)
    result = contract_reference_readiness([request()], [], [contract], [link], [obligation])[0]
    assert result['explicit_contract_link_verified'] is True
    assert result['linked_obligation_id'] == 45
    assert result['free_issue_entitlement_verified'] is False
    assert result['finance_recovery_authorized'] is False
    assert result['readiness'] == 'Blocked'


def test_unrelated_obligation_cannot_be_presented_as_valid():
    contract = SimpleNamespace(id=12, counterparty_company_id=3)
    link = SimpleNamespace(material_request_id=9, contract_id=12, obligation_id=45)
    obligation = SimpleNamespace(id=45, contract_id=99)
    result = contract_reference_readiness([request()], [], [contract], [link], [obligation])[0]
    assert result['explicit_contract_link_verified'] is False
    assert result['linked_obligation_id'] is None


def test_evidence_required():
    try:
        ContractObligationLinkIn(contract_id=12, obligation_id=45, evidence='short')
        assert False
    except ValidationError:
        pass
