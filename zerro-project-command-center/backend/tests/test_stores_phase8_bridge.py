"""Phase 8 Stores bridge: deny ambiguous mapping, reject stale/mis-scoped feed."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.routers.stores_exceptions import source_identity, validate_snapshot


def snapshot():
    return dict(source='zerrobuild.stores.phase8_cross_module_audit', schema_version=1,
                organization_id=7, project_id=48, read_only=True, complete_history=False,
                billing_certified=False, financials_authority_verified=False,
                external_inspection_verified=False, delivery_mode='poll_snapshot',
                as_of=datetime.now(timezone.utc).isoformat(), record_count=2,
                coverage='bounded audit', exception_counts={'missing_qa':1},
                exception_records=[{'material_request_id':3, 'work_package_id':2,
                                    'exception_codes':['missing_qa'],'review_state':'review'}])


def test_correct_snapshot_remains_unverified():
    r=validate_snapshot(snapshot(),7,48)
    assert r['financials_authority_verified'] is False
    assert r['record_count']==2

@pytest.mark.parametrize('change', [
    {'project_id':49}, {'organization_id':8}, {'billing_certified':True},
    {'financials_authority_verified':True}, {'external_inspection_verified':True},
    {'read_only':False}, {'exception_counts':{'missing_qa':2}},
    {'as_of':(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()},
])
def test_rejects_untrusted_snapshot(change):
    with pytest.raises(ValueError): validate_snapshot({**snapshot(),**change},7,48)


def test_source_mapping_uses_authoritative_id_not_cc_id():
    project=SimpleNamespace(code='CC-001')
    viewer=SimpleNamespace(project_code='CC-001',discipline_codes=frozenset(['CIVIL']))
    settings=SimpleNamespace(command_center_project_map='{"ZSP-001":"CC-001"}',command_center_expected_org='7')
    assert source_identity(project, viewer, settings, {'ZSP-001':{'id':48}})==(7,48)


def test_missing_or_ambiguous_source_mapping_denied():
    project=SimpleNamespace(code='CC-001')
    viewer=SimpleNamespace(project_code='CC-001',discipline_codes=frozenset(['CIVIL']))
    settings=SimpleNamespace(command_center_project_map='{}',command_center_expected_org='7')
    with pytest.raises(HTTPException):source_identity(project,viewer,settings,{'ZSP-001':{'id':48}})
    settings.command_center_project_map='{"ZSP-001":"CC-001","OTHER":"CC-001"}'
    with pytest.raises(HTTPException):source_identity(project,viewer,settings,{'ZSP-001':{'id':48}})
