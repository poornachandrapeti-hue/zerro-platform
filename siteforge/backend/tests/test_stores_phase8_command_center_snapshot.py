from types import SimpleNamespace as R
from unittest.mock import Mock, patch
from fastapi import HTTPException
import pytest
from app.domains.stores_inventory import phase8_cross_module_audit as audit


def test_summary_excludes_unnecessary_handover_detail():
    example = {'records': [{'material_request_id': 3, 'work_package_id': 5, 'exceptions': ['NO_ISSUE_HANDOVER'], 'review_state': 'Requires Review', 'handovers': [{'secret': 'not-for-feed'}]}],
               'exception_counts': {'NO_ISSUE_HANDOVER': 1}, 'as_of': 'now', 'coverage': 'Limited'}
    with patch.object(audit, '_audit_window', return_value=example):
        result = audit.command_center_exception_snapshot(Mock(), 2, 7)
    assert result['project_id'] == 7
    assert result['exception_counts']['NO_ISSUE_HANDOVER'] == 1
    assert 'handovers' not in result['exception_records'][0]
    assert result['delivery_mode'] == 'poll_snapshot'
    assert not result['billing_certified']


def test_empty_snapshot():
    with patch.object(audit, '_audit_window', return_value={'records': [], 'exception_counts': {}, 'as_of': 'now', 'coverage': 'Limited'}):
        result = audit.command_center_exception_snapshot(Mock(), 2, 7)
    assert result['record_count'] == 0
    assert result['complete_history'] is False


def test_invalid_limit():
    with pytest.raises(HTTPException) as exc:
        audit.command_center_exception_snapshot(Mock(), 2, 7, limit=501)
    assert exc.value.status_code == 422


def test_internal_requires_service_key_even_if_project_exists():
    db = Mock()
    request = R(headers={})
    with patch.object(audit.settings, 'command_center_identity_service_key', 'private-key'):
        with pytest.raises(HTTPException) as exc:
            audit.command_center_phase8_exception_snapshot(7, request, db=db)
    assert exc.value.status_code == 403
    db.get.assert_not_called()


def test_valid_key_uses_project_organization():
    db = Mock()
    db.get.return_value = R(organization_id=20)
    request = R(headers={'X-ZerroR-Service-Key': 'private-key'})
    with patch.object(audit.settings, 'command_center_identity_service_key', 'private-key'):
        with patch.object(audit, 'command_center_exception_snapshot', return_value={'ok': True}) as snapshot:
            result = audit.command_center_phase8_exception_snapshot(9, request, db=db)
    assert result == {'ok': True}
    snapshot.assert_called_once_with(db, 20, 9, None, 200)
