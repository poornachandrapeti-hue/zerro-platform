from app.domains.progress_monitoring.reports_router import permission_granted

def test_partner_never_allowed():
    assert not permission_granted(['planning.partner.view','planning.manage','progress.publish'],'progress.publish')

def test_view_cannot_publish():
    assert permission_granted(['progress.view'],'planning.view')
    assert not permission_granted(['progress.view'],'progress.publish')

def test_dedicated_review():
    assert permission_granted(['progress.review'],'progress.review')
    assert not permission_granted(['progress.review'],'progress.approve')

def test_legacy_planning_compatibility():
    assert permission_granted(['planning.manage'],'progress.policy.approve')
    assert not permission_granted(['planning.view'],'progress.review')
