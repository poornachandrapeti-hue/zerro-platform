from types import SimpleNamespace
from app.domains.planning_reporting.partner_scope import visible_to_membership, partner_activity_projection
from app.domains.identity_projects.seed import default_permissions

def m(company, scope, disciplines):
    return SimpleNamespace(company_id=company, scope=scope, discipline_ids=disciplines)

def test_company_restriction():
    assert not visible_to_membership(20,1,m(10,'ALL',[]))
    assert visible_to_membership(10,1,m(10,'ALL',[]))

def test_discipline_restriction():
    assert visible_to_membership(10,2,m(10,'SELECTED',[2]))
    assert not visible_to_membership(10,3,m(10,'SELECTED',[2]))
    assert not visible_to_membership(10,None,m(10,'SELECTED',[2]))
    assert not visible_to_membership(10,2,m(10,'INVALID',[2]))

def test_partner_projection_is_allowlisted():
    a=SimpleNamespace(code='ST-01',name='Erection',activity_type='Task',planned_start=None,planned_finish=None,discipline_id=2,remarks='PRIVATE',source_id='SECRET',company_id=10)
    p=partner_activity_projection(a)
    assert p['activity_code']=='ST-01'
    assert 'remarks' not in p and 'source_id' not in p and 'company_id' not in p

def test_partner_permissions_do_not_grant_global_planning():
    p=default_permissions('Contractor Planner')
    assert 'planning.partner.view' in p
    assert 'planning.view' not in p and 'planning.manage' not in p
