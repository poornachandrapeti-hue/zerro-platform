"""Focused security tests for company/discipline-scoped internal reviewers."""
from types import SimpleNamespace
from app.domains.planning_reporting.partner_router import reviewer_can_access


def m(company, scope, disciplines):
    return SimpleNamespace(company_id=company, scope=scope, discipline_ids=disciplines)


def activity(company, discipline):
    return SimpleNamespace(company_id=company, discipline_id=discipline)


def test_matching_company_and_selected_discipline():
    assert reviewer_can_access(activity(10, 3), [m(10, 'SELECTED', [3])])


def test_rejects_wrong_company_even_when_discipline_matches():
    assert not reviewer_can_access(activity(11, 3), [m(10, 'ALL', [])])


def test_rejects_other_discipline():
    assert not reviewer_can_access(activity(10, 4), [m(10, 'SELECTED', [3])])


def test_selected_without_discipline_is_denied():
    assert not reviewer_can_access(activity(10, None), [m(10, 'SELECTED', [3])])


def test_multiple_memberships_union_only_their_scopes():
    grants = [m(10, 'SELECTED', [3]), m(11, 'SELECTED', [4])]
    assert reviewer_can_access(activity(11, 4), grants)
    assert not reviewer_can_access(activity(10, 4), grants)


def test_admin_and_empty_grants():
    assert reviewer_can_access(activity(17, 9), None)
    assert not reviewer_can_access(activity(17, 9), [])
