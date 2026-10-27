from types import SimpleNamespace
import pytest
from app.domains.progress_monitoring.p3c1fe_association_service import check_source,AssociationViolation
from app.domains.progress_monitoring.p3c2_wbs_preview import preview_wbs,ProgressPreviewError

DIGEST='a'*64

def source(**changes):
    d=dict(server_verified=True,organization_id=1,project_id=2,activity_id=3,inspection_id=4,
           progress_line_id=5,project_file_id=6,stored_file_id=7,digest=DIGEST,
           qa_status='Approved',qa_outcome='Accepted',attachment_integrity_verified=True)
    d.update(changes);return d

def validate(s):
    check_source(s,organization_id=1,project_id=2,activity_id=3,inspection_id=4,
                 line_id=5,file_id=6,stored_file_id=7,digest=DIGEST)

def test_good_source():validate(source())
@pytest.mark.parametrize('change',[
    {'server_verified':False},{'organization_id':10},{'project_id':10},
    {'activity_id':10},{'inspection_id':10},{'progress_line_id':10},
    {'project_file_id':10},{'stored_file_id':10},{'qa_status':'Pending'},
    {'qa_outcome':'Rejected'},{'attachment_integrity_verified':False},{'digest':'b'*64}])
def test_fail_closed_source(change):
    with pytest.raises(AssociationViolation):validate(source(**change))

def targets():return [SimpleNamespace(activity_id=1,weight_basis_points=6000),SimpleNamespace(activity_id=2,weight_basis_points=4000)]
def leaves():return [dict(activity_id=i,approved_baseline=True,measurement_valid=True,link_status='linked',
 source={'construction_activity_id':i+100},measurement={'reported_percent':x,'verified_percent':x-10,'accepted_percent':x-20})
 for i,x in [(1,80),(2,60)]]
def view(**changes):
    inputs=dict(leaves=leaves(),approved_targets=targets(),full_scope=True,
                authorized=True,association_evidence_complete=True)
    inputs.update(changes);return preview_wbs(**inputs)

def test_weighted_preview():
    result=view()
    assert result['measures']=={'reported_percent':72.0,'verified_percent':62.0,'accepted_percent':52.0}
    assert result['earned_percent'] is None and result['billable_quantity'] is None
    assert result['published'] is False
@pytest.mark.parametrize('missing', ['authorized','full_scope','association_evidence_complete'])
def test_scope_fail_closed(missing):
    with pytest.raises(ProgressPreviewError):view(**{missing:False})
def test_missing_baseline():
    data=leaves();data[0]['approved_baseline']=False
    with pytest.raises(ProgressPreviewError):view(leaves=data)
def test_invalid_measurement():
    data=leaves();data[0]['measurement_valid']=False
    with pytest.raises(ProgressPreviewError):view(leaves=data)
def test_bad_weights():
    t=targets();t[0].weight_basis_points=5000
    with pytest.raises(ProgressPreviewError):view(approved_targets=t)
def test_missing_leaf():
    with pytest.raises(ProgressPreviewError):view(leaves=leaves()[:1])
