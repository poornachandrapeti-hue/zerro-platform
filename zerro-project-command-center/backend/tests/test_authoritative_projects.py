from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from app.authoritative_projects import fetch_project_master
from app.routers.projects import create_project, delete_project


def settings():
    return SimpleNamespace(command_center_identity_url='http://siteforge:8000', command_center_identity_service_key='unit-test-secret')


def test_master_filters_invalid_org():
    with pytest.raises(HTTPException) as ex:
        fetch_project_master('wrong', settings())
    assert ex.value.status_code == 403


def test_master_rejects_missing_service_configuration():
    with pytest.raises(HTTPException) as ex:
        fetch_project_master('1', SimpleNamespace(command_center_identity_url='', command_center_identity_service_key=''))
    assert ex.value.status_code == 503


def test_master_fails_closed_on_duplicate_code(monkeypatch):
    response = Mock()
    response.json.return_value = [{'code':'PRJ-1','name':'A'},{'code':'prj-1','name':'B'}]
    response.raise_for_status.return_value = None
    monkeypatch.setattr('app.authoritative_projects.httpx.get', lambda *a, **kw: response)
    with pytest.raises(HTTPException) as ex:
        fetch_project_master('1', settings())
    assert ex.value.status_code == 503


def test_master_returns_authoritative_codes(monkeypatch):
    response = Mock()
    response.json.return_value = [{'code':'prj-1','name':'Steel Plant','status':'Active'}]
    response.raise_for_status.return_value = None
    monkeypatch.setattr('app.authoritative_projects.httpx.get', lambda *a, **kw: response)
    assert fetch_project_master('1', settings())['PRJ-1']['name'] == 'Steel Plant'


def test_command_center_project_create_blocked_in_unified_mode(monkeypatch):
    monkeypatch.setattr('app.routers.projects.get_settings', lambda: SimpleNamespace(command_center_authoritative_projects=True))
    with pytest.raises(HTTPException) as ex:
        create_project(None, None, None)
    assert ex.value.status_code == 409


def test_command_center_project_delete_blocked_in_unified_mode(monkeypatch):
    monkeypatch.setattr('app.routers.projects.get_settings', lambda: SimpleNamespace(command_center_authoritative_projects=True))
    with pytest.raises(HTTPException) as ex:
        delete_project(1, None, None)
    assert ex.value.status_code == 409
