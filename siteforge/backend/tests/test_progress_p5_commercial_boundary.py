import copy
import pytest
from app.domains.progress_monitoring.p5_commercial_boundary import (
    CommercialBoundaryError, inspect_commercial_handoff, command_center_progress_view
)

PROGRESS = dict(organization_id=1, project_id=22, server_authorized=True,
    status='Published', published=True, publication_persisted=True,
    approval_audit_valid=True, source_integrity_valid=True, revoked=False,
    snapshot_id='ps-1', revision_id='rev-2', contract_id='ct-1',
    work_package_id='wp-1', unit='m3', qa_accepted_quantity='65',
    independently_verified_quantity='80')
CONTRACT = dict(organization_id=1, project_id=22, server_authorized=True,
    status='Active', billing_terms_approved=True, contract_id='ct-1',
    work_package_id='wp-1', unit='m3', approved_quantity='100',
    previously_certified_quantity='40')

def review(progress=None, contract=None, **kwargs):
    return inspect_commercial_handoff(progress=PROGRESS if progress is None else progress,
        contract=CONTRACT if contract is None else contract,
        organization_id=1, project_id=22, authorized=True,
        server_revalidated=True, **kwargs)

def rejected_progress(**changes):
    p=copy.deepcopy(PROGRESS);p.update(changes)
    with pytest.raises(CommercialBoundaryError): review(progress=p)

def test_review_candidate_never_posts():
    r=review()
    assert r['maximum_reviewable_quantity']=='25'
    assert not r['billing_certified'] and not r['finance_posted'] and not r['invoice_created']

def test_unpublished_preview_denied(): rejected_progress(status='UNPUBLISHED_PREVIEW', published=False)
def test_unpersisted_publication_denied(): rejected_progress(publication_persisted=False)
def test_missing_audit_denied(): rejected_progress(approval_audit_valid=False)
def test_revoked_denied(): rejected_progress(revoked=True)
def test_cross_project_denied(): rejected_progress(project_id=99)
def test_oververified_denied(): rejected_progress(qa_accepted_quantity='81')
def test_nan_denied(): rejected_progress(qa_accepted_quantity='NaN')
def test_missing_snapshot_id_denied(): rejected_progress(snapshot_id=None)
def test_missing_trust_denied(): rejected_progress(server_authorized=False)

def test_wrong_contract_denied():
    c=dict(CONTRACT,contract_id='different')
    with pytest.raises(CommercialBoundaryError):review(contract=c)

def test_double_certification_denied():
    c=dict(CONTRACT, previously_certified_quantity='75')
    with pytest.raises(CommercialBoundaryError):review(contract=c)

def test_dashboard_provisional_measures():
    x=command_center_progress_view(snapshot=dict(organization_id=1,project_id=22,
        server_authorized=True,status='Approved',measures=dict(reported_percent='80',
        verified_percent='65',accepted_percent='55')),
        organization_id=1,project_id=22,authorized=True,server_revalidated=True)
    assert x['is_published'] is False and x['earned_percent'] is None

def test_dashboard_rejects_wrong_order():
    with pytest.raises(CommercialBoundaryError):
        command_center_progress_view(snapshot=dict(organization_id=1,project_id=22,
            server_authorized=True,status='Draft',measures=dict(reported_percent=10,
            verified_percent=20,accepted_percent=1)), organization_id=1, project_id=22,
            authorized=True,server_revalidated=True)

def test_dashboard_cross_project_rejected():
    with pytest.raises(CommercialBoundaryError):
        command_center_progress_view(snapshot=dict(organization_id=1, project_id=10,
            server_authorized=True,status='Draft',measures=dict(reported_percent=10,
            verified_percent=5,accepted_percent=2)),organization_id=1,project_id=22,
            authorized=True,server_revalidated=True)
