import copy
import pytest
from app.domains.progress_monitoring.p5b_authority_bridge import (
    commercial_review_from_sources, dashboard_from_source, CommercialBoundaryError,
)

PROGRESS = dict(organization_id=1, project_id=2, server_authorized=True, status='Published',
 published=True, publication_persisted=True, approval_audit_valid=True,
 source_integrity_valid=True, revoked=False, snapshot_id=5, revision_id=9,
 contract_id=6, work_package_id=7, unit='m3', qa_accepted_quantity='80',
 independently_verified_quantity='90', measures=dict(reported_percent=90,
 verified_percent=85, accepted_percent=80))
CONTRACT = dict(organization_id=1, project_id=2, server_authorized=True,
 status='Active', billing_terms_approved=True, contract_id=6,
 work_package_id=7, unit='m3', approved_quantity='100', previously_certified_quantity='20')

def args():
    return dict(organization_id=1, project_id=2, snapshot_id=5, contract_id=6,
                fetch_snapshot=lambda **_: copy.deepcopy(PROGRESS),
                fetch_contract=lambda **_: copy.deepcopy(CONTRACT),
                can_review=True, evidence_current=True, certification_current=True)

def test_review_candidate_not_certificate():
    r = commercial_review_from_sources(**args())
    assert r['maximum_reviewable_quantity']=='60'
    assert r['billing_certified'] is False and r['invoice_created'] is False
    assert r['persistent_certification_created'] is False

@pytest.mark.parametrize('field', ['can_review','evidence_current','certification_current'])
def test_authorization_gates(field):
    a=args();a[field]=False
    with pytest.raises(CommercialBoundaryError): commercial_review_from_sources(**a)

def test_missing_resolver():
    a=args();a['fetch_contract']=None
    with pytest.raises(CommercialBoundaryError): commercial_review_from_sources(**a)

def test_cross_project_snapshot():
    a=args();a['fetch_snapshot']=lambda **_:dict(PROGRESS, project_id=3)
    with pytest.raises(CommercialBoundaryError): commercial_review_from_sources(**a)

def test_cross_project_contract():
    a=args();a['fetch_contract']=lambda **_:dict(CONTRACT, project_id=3)
    with pytest.raises(CommercialBoundaryError): commercial_review_from_sources(**a)

def test_untrusted_source():
    a=args();a['fetch_snapshot']=lambda **_:dict(PROGRESS, server_authorized=False)
    with pytest.raises(CommercialBoundaryError): commercial_review_from_sources(**a)

def test_unpublished_source():
    a=args();a['fetch_snapshot']=lambda **_:dict(PROGRESS, status='Approved')
    with pytest.raises(CommercialBoundaryError): commercial_review_from_sources(**a)

def test_revoked_evidence():
    a=args();a['fetch_snapshot']=lambda **_:dict(PROGRESS, revoked=True)
    with pytest.raises(CommercialBoundaryError): commercial_review_from_sources(**a)

def test_identifier_mismatch():
    a=args();a['fetch_contract']=lambda **_:dict(CONTRACT, contract_id=100)
    with pytest.raises(CommercialBoundaryError): commercial_review_from_sources(**a)

def test_dashboard_candidate_is_never_billable():
    result=dashboard_from_source(organization_id=1,project_id=2,snapshot_id=5,
        fetch_snapshot=lambda **_:dict(PROGRESS), can_view=True,evidence_current=True)
    assert result['is_published'] is True and result['billing_certified'] is False
    assert result['earned_percent'] is None

def test_dashboard_scope_denied():
    with pytest.raises(CommercialBoundaryError):
        dashboard_from_source(organization_id=1,project_id=2,snapshot_id=5,
            fetch_snapshot=lambda **_:dict(PROGRESS, project_id=3),can_view=True,evidence_current=True)

def test_invalid_organization_denied():
    a=args();a['organization_id']=0
    with pytest.raises(CommercialBoundaryError): commercial_review_from_sources(**a)
