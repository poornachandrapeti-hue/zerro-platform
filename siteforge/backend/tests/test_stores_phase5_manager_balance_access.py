"""Source-path regression for separate requester and Construction manager balance views."""
from types import SimpleNamespace
from unittest.mock import patch
from app.domains.stores_inventory import phase5_material_balance as mod


class FakeDb:
    def __init__(self, requests):
        self.requests = requests
        self.calls = 0
    def execute(self, statement):
        self.calls += 1
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self.requests if self.calls == 1 else []))


def test_requester_does_not_see_other_users_requests():
    user = SimpleNamespace(id=7, organization_id=1, organization_admin=False)
    db = FakeDb([SimpleNamespace(id=5, created_by=9)])
    with patch.object(mod, '_scope') as check:
        result = mod.work_package_material_balance(100, None, user, db)
    check.assert_called_once_with(db, user, 100, 'stores.requests.view')
    assert result['records'] == []
    assert db.calls == 1


def test_manager_uses_independent_construction_permission_and_cross_request_scope():
    user = SimpleNamespace(id=7, organization_id=1, organization_admin=False)
    db = FakeDb([SimpleNamespace(id=5, created_by=9)])
    with patch.object(mod, '_scope') as check:
        result = mod.construction_manager_material_balance(100, None, user, db)
    check.assert_called_once_with(db, user, 100, 'construction.view')
    assert result['records'] == []
    assert db.calls == 2  # manager may query handovers for another requester's record


def test_manager_rejects_invalid_work_package_id():
    from fastapi import HTTPException
    user = SimpleNamespace(id=7, organization_id=1, organization_admin=False)
    db = FakeDb([])
    with patch.object(mod, '_scope'):
        try:
            mod.construction_manager_material_balance(100, -1, user, db)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError('negative work package accepted')
