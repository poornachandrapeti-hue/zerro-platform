from types import SimpleNamespace as Row
from app.domains.progress_monitoring.p3c1_baseline_authority import resolve_baseline_activity


def baseline(**changes):
    doc={'approval_status':'approved','approval_reference':'APR-1',
         'activities':[{'planning_activity_id':7,'construction_activity_id':14,
                        'approved_quantity':'100','unit':'m3'}]}
    fields=dict(id=9,organization_id=1,project_id=2,status='approved',
                approved_by=3,approved_at='2026-10-27',document=doc,revision='R1')
    fields.update(changes)
    return Row(**fields)


def check(rows,**kwargs):
    return resolve_baseline_activity(rows,organization_id=1,project_id=2,
        planning_activity_id=7,construction_activity_id=14,unit='m3',**kwargs)


def test_valid_baseline():
    r=check([baseline()]);assert r['status']=='APPROVED_QUANTITY_FOUND';assert r['approved_planning_quantity']=='100'

def test_no_baseline():
    assert check([])['approved_planning_quantity'] is None

def test_wrong_project():
    assert check([baseline(project_id=4)])['approved_planning_quantity'] is None

def test_unapproved():
    assert check([baseline(status='draft')])['approved_planning_quantity'] is None

def test_multiple_approved_revisions_fail_closed():
    assert check([baseline(),baseline(id=10,revision='R2')])['status']=='BASELINE_AMBIGUOUS'

def test_source_mapping_required():
    assert check([baseline(document={'approval_status':'approved','approval_reference':'a','activities':[{'planning_activity_id':7,'approved_quantity':100,'unit':'m3'}]})])['approved_planning_quantity'] is None

def test_unit_mismatch():
    b=baseline();b.document['activities'][0]['unit']='ton';assert check([b])['approved_planning_quantity'] is None

def test_no_inferred_quantity():
    b=baseline();b.document['activities'][0].pop('approved_quantity');assert check([b])['approved_planning_quantity'] is None

def test_negative_quantity():
    b=baseline();b.document['activities'][0]['approved_quantity']='-1';assert check([b])['approved_planning_quantity'] is None

def test_duplicate_mapping():
    b=baseline();b.document['activities'].append(dict(b.document['activities'][0]));assert check([b])['approved_planning_quantity'] is None

def test_missing_approval_reference():
    b=baseline();b.document.pop('approval_reference');assert check([b])['approved_planning_quantity'] is None

def test_non_finite_quantity():
    b=baseline();b.document['activities'][0]['approved_quantity']='NaN';assert check([b])['approved_planning_quantity'] is None
