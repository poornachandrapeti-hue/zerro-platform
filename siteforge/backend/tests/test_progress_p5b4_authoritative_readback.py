import pytest
from app.domains.progress_monitoring.p5b4_authoritative_readback import commercial_readback, safe_command_center_projection, AuthorityUnavailable

AUTH = dict(server_checked=True, commercial_view=True, dashboard_view=True, organization_id=1, project_id=2)
def snapshot(**kw):
    d = dict(organization_id=1, project_id=2, server_authorized=True, snapshot_id=3,
             status='Published', publication_persisted=True, requires_source_integrity_revalidation=False,
             qa_evidence_authenticated=True, qa_accepted_quantity_by_boq={'5':'60'}, unit_by_boq={'5':'m3'})
    d.update(kw);return d
def boq(**kw):
    d = dict(organization_id=1, project_id=2, server_authorized=True, contract_id=4,
             boq_line_id=5, billing_terms_approved=True, approved_quantity='100', unit='m3')
    d.update(kw);return d
def finance(**kw):
    d = dict(organization_id=1, project_id=2, contract_id=4, boq_line_id=5,
             source_authoritative=True, complete_history=True, reversals_reconciled=True,
             rows=[dict(server_authorized=True,organization_id=1,project_id=2,contract_id=4,
                        boq_line_id=5,certification_id='C-1',status='Posted',revoked=False,quantity='25',unit='m3')])
    d.update(kw);return d
def run(**overrides):
    params=dict(organization_id=1,project_id=2,snapshot_id=3,contract_id=4,boq_line_id=5,
       fetch_published_snapshot=lambda **_:snapshot(),fetch_contract_boq=lambda **_:boq(),
       fetch_finance_certifications=lambda **_:finance(),authorization=AUTH,evidence_current=True)
    params.update(overrides);return commercial_readback(**params)
def test_happy_readonly():
    r=run(); assert r['remaining_candidate_quantity']=='35';assert r['billing_certified'] is False
    assert r['requires_finance_owner_final_approval'] is True
def test_missing_finance():
    with pytest.raises(AuthorityUnavailable):run(fetch_finance_certifications=None)
def test_finance_empty_not_implicit():
    with pytest.raises(AuthorityUnavailable):run(fetch_finance_certifications=lambda **_:[])
def test_auth_required():
    with pytest.raises(AuthorityUnavailable):run(authorization={'server_checked':False})
def test_cross_project_auth():
    with pytest.raises(AuthorityUnavailable):run(authorization={**AUTH,'project_id':9})
def test_unpublished():
    with pytest.raises(AuthorityUnavailable):run(fetch_published_snapshot=lambda **_:snapshot(status='Draft'))
def test_unauthenticated_measurement():
    with pytest.raises(AuthorityUnavailable):run(fetch_published_snapshot=lambda **_:snapshot(qa_evidence_authenticated=False))
def test_stale_evidence():
    with pytest.raises(AuthorityUnavailable):run(fetch_published_snapshot=lambda **_:snapshot(requires_source_integrity_revalidation=True))
def test_no_terms():
    with pytest.raises(AuthorityUnavailable):run(fetch_contract_boq=lambda **_:boq(billing_terms_approved=False))
def test_incomplete_history():
    with pytest.raises(AuthorityUnavailable):run(fetch_finance_certifications=lambda **_:finance(complete_history=False))
def test_reversal_unreconciled():
    with pytest.raises(AuthorityUnavailable):run(fetch_finance_certifications=lambda **_:finance(reversals_reconciled=False))
def test_unit_mismatch():
    with pytest.raises(AuthorityUnavailable):run(fetch_contract_boq=lambda **_:boq(unit='kg'))
def test_cross_project_finance():
    with pytest.raises(AuthorityUnavailable):run(fetch_finance_certifications=lambda **_:finance(project_id=99))
def test_missing_boq_mapping():
    with pytest.raises(AuthorityUnavailable):run(fetch_published_snapshot=lambda **_:snapshot(qa_accepted_quantity_by_boq={}))
def test_negative_certification():
    with pytest.raises(ValueError):run(fetch_finance_certifications=lambda **_:finance(rows=[{**finance()['rows'][0],'quantity':'-1'}]))
def test_duplicate_certification():
    with pytest.raises(ValueError):run(fetch_finance_certifications=lambda **_:finance(rows=finance()['rows']*2))
def test_dashboard_auth():
    with pytest.raises(AuthorityUnavailable):safe_command_center_projection(organization_id=1,project_id=2,snapshot=snapshot(),reconciliation={'status':'READ_ONLY_RECONCILIATION'},authorization={},evidence_current=True)
def test_bad_snapshot_identity():
    with pytest.raises(AuthorityUnavailable):run(fetch_published_snapshot=lambda **_:snapshot(snapshot_id=999))
