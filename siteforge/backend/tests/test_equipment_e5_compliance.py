from datetime import date, timedelta
from types import SimpleNamespace as Obj
import pytest
from fastapi import HTTPException
from app.domains.planning_reporting.equipment_compliance_rules import ensure_compliant, review_allowed, release_allowed

TODAY=date(2026,10,26)

def asset(required=None):
    return Obj(operating_specs={'required_certificates': required or []})
def certificate(kind='Calibration',status='Verified',expires=None,required=True,created_by=11):
    return Obj(kind=kind,status=status,valid_through=expires or TODAY+timedelta(days=5),required=required,created_by=created_by)
def hold(status='Active',created_by=12):
    return Obj(status=status,created_by=created_by)
def blocked(fn,status):
    with pytest.raises(HTTPException) as e: fn()
    assert e.value.status_code == status

def test_empty_compliance_without_mandatory_categories():
    assert ensure_compliant(asset(),[],[],TODAY)
def test_active_hold_blocks_equipment():
    blocked(lambda:ensure_compliant(asset(),[],[hold()],TODAY),409)
def test_released_hold_not_block():
    assert ensure_compliant(asset(),[],[hold('Released')],TODAY)
def test_required_missing_blocks():
    blocked(lambda:ensure_compliant(asset(['Calibration']),[],[],TODAY),409)
def test_required_rejected_blocks():
    blocked(lambda:ensure_compliant(asset(['Calibration']),[certificate(status='Rejected')],[],TODAY),409)
def test_expiring_before_allocation_end_blocks():
    blocked(lambda:ensure_compliant(asset(['Calibration']),[certificate(expires=TODAY)],[],TODAY+timedelta(days=1)),409)
def test_verified_certificate_allows():
    assert ensure_compliant(asset(['Calibration']),[certificate()],[],TODAY)
def test_required_evidence_fail_closed_even_if_not_in_config():
    blocked(lambda:ensure_compliant(asset(),[certificate(status='Pending')],[],TODAY),409)
def test_optional_evidence_does_not_hold():
    assert ensure_compliant(asset(),[certificate(status='Rejected',required=False)],[],TODAY)
def test_invalid_required_kind_fails():
    blocked(lambda:ensure_compliant(asset(['Unknown']),[],[],TODAY),409)
def test_creator_cannot_approve_own_evidence():
    blocked(lambda:review_allowed(certificate(status='Pending'),11,'Verified'),403)
def test_independent_reviewer_can_verify():
    assert review_allowed(certificate(status='Pending'),17,'Verified')
def test_review_once_only():
    blocked(lambda:review_allowed(certificate(status='Verified'),17,'Rejected'),409)
def test_hold_creator_cannot_release():
    blocked(lambda:release_allowed(hold(),12,'RELEASE-EVIDENCE'),403)
def test_independent_hold_release():
    assert release_allowed(hold(),17,'RELEASE-EVIDENCE')
def test_duplicate_release_blocks():
    blocked(lambda:release_allowed(hold('Released'),17,'RELEASE-EVIDENCE'),409)
def test_empty_evidence_blocks_release():
    blocked(lambda:release_allowed(hold(),17,' '),422)
