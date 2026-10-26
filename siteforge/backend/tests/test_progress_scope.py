"""Unit checks for Progress visible-record company/discipline intersections."""
from app.domains.progress_monitoring.router import permitted_activity


def test_all_permission():
    assert permitted_activity({'company_id': None, 'discipline_id': None}, {'all': True})


def test_selected_company_discipline():
    scope = {'all': False, 'pairs': [(2, {7}), (3, {8})]}
    assert permitted_activity({'company_id': 2, 'discipline_id': 7}, scope)
    assert permitted_activity({'company_id': 3, 'discipline_id': 8}, scope)
    assert not permitted_activity({'company_id': 2, 'discipline_id': 8}, scope)
    assert not permitted_activity({'company_id': 3, 'discipline_id': 7}, scope)
    assert not permitted_activity({'company_id': None, 'discipline_id': 7}, scope)


def test_selected_company_all_disciplines():
    scope = {'all': False, 'pairs': [(2, set())]}
    assert permitted_activity({'company_id': 2, 'discipline_id': None}, scope)
    assert not permitted_activity({'company_id': 4, 'discipline_id': None}, scope)
