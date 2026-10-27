from types import SimpleNamespace
import pytest
from app.domains.progress_monitoring.p3c2_integration_gate import gated_preview,ProgressAuthorityError
from app.domains.progress_monitoring.p3c3_scurve_preview import scurve_preview,discipline_preview
from app.domains.progress_monitoring.p4_publication_policy import decide,PublicationPolicyError

def row(i, reported=80, verified=70, accepted=60):
    return dict(server_authorized=True,source_revalidated=True,organization_id=1,project_id=2,activity_id=i,
      baseline_approved=True,construction_verified=True,qa_evidence_approved=True,attachment_authenticated=True,
      planned_quantity=100,reported_quantity=reported,verified_quantity=verified,accepted_quantity=accepted,
      unit='m3',verified_unit='m3',qa_unit='m3',construction_activity_id=100+i,
      verification_id=200+i,inspection_id=300+i,attachment_id=400+i)
def weights():return [SimpleNamespace(activity_id=1,weight_basis_points=6000),SimpleNamespace(activity_id=2,weight_basis_points=4000)]
def preview(**kwargs):
    args=dict(authority_rows=[row(1),row(2,60,50,40)],target_rows=weights(),organization_id=1,project_id=2,authorized=True,full_scope=True)
    args.update(kwargs);return gated_preview(**args)
def test_wbs_numbers_and_never_billable():
    v=preview();assert v['measures']=={'reported_percent':72.0,'verified_percent':62.0,'accepted_percent':52.0};assert not v['publication_eligible'];assert v['earned_percent'] is None
@pytest.mark.parametrize('changes', [
  {'source_revalidated':False},{'attachment_authenticated':False},{'project_id':9},
  {'qa_evidence_approved':False},{'verified_quantity':85},{'unit':'kg'},
  {'planned_quantity':0},{'accepted_quantity':90},{'verification_id':None}])
def test_bad_leaf(changes):
    data=[row(1,**{}) if False else row(1),row(2,60,50,40)];data[0].update(changes)
    with pytest.raises(ProgressAuthorityError):preview(authority_rows=data)
def test_filtered_scope_denied():
    with pytest.raises(ProgressAuthorityError):preview(full_scope=False)
def test_bad_weights_denied():
    with pytest.raises(ProgressAuthorityError):preview(target_rows=[SimpleNamespace(activity_id=1,weight_basis_points=10000)])
def test_scurve():
    period=lambda date,rows:dict(as_of=date,authority_rows=rows,target_rows=weights())
    result=scurve_preview(periods=[period('2026-10-01',[row(1,60,50,40),row(2,40,30,20)]),period('2026-10-15',[row(1),row(2,60,50,40)])],organization_id=1,project_id=2,authorized=True,full_scope=True)
    assert result['series'][1]['accepted_percent']==52.0 and not result['published']
def test_regression_rejected():
    period=lambda date,rows:dict(as_of=date,authority_rows=rows,target_rows=weights())
    with pytest.raises(ProgressAuthorityError):scurve_preview(periods=[period('2026-10-01',[row(1),row(2,60,50,40)]),period('2026-10-15',[row(1,60,50,40),row(2,40,30,20)])],organization_id=1,project_id=2,authorized=True,full_scope=True)
def test_discipline_no_project_total():
    result=discipline_preview(disciplines={'Civil':dict(authority_rows=[row(1),row(2,60,50,40)],target_rows=weights())},organization_id=1,project_id=2,authorized=True)
    assert result['project_total'] is None

def transition(**kw):
    args=dict(state='Pending',action='approve',version=3,expected_version=3,proposer_id='a',actor_id='b',permissions={'progress.approve'},source_integrity=True,wbs_complete=True,approvals_current=True,project_authorized=True)
    args.update(kw);return decide(**args)
def test_independent_review():
    assert transition().next_state=='Approved'
@pytest.mark.parametrize('change',[{'actor_id':'a'},{'expected_version':2},{'source_integrity':False},{'permissions':set()},{'project_authorized':False},{'state':'Published'}])
def test_denials(change):
    with pytest.raises(PublicationPolicyError):transition(**change)
def test_publish_policy_only():
    d=transition(state='Approved',action='publish',permissions={'progress.publish'})
    assert d.published and d.next_version==4
def test_supersede_reason():
    with pytest.raises(PublicationPolicyError):transition(state='Published',action='supersede',permissions={'progress.publish'})
