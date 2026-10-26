import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'app/domains/progress_monitoring/p3_quantity_measurement.py'
spec = importlib.util.spec_from_file_location('p3_quantity_measurement', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
calculate = module.calculate_leaf_quantities

BASE = dict(planned_quantity='100', unit='m3', reported_quantity='85',
            verified_quantity='80', project_id=7, activity_id=11, construction_line_id=21)

def link(**changes):
    value = dict(link_id=1, qa_inspection_id=45, project_id=7, activity_id=11,
                 construction_line_id=21, state='Approved', accepted_quantity='65',
                 proposer_user_id=20, reviewer_user_id=21)
    value.update(changes)
    return value

def run(links=None, **changes):
    inputs = BASE.copy();inputs.update(changes)
    return calculate(**inputs, approved_evidence_links=[link()] if links is None else links)

def test_distinct_percentages():
    result=run()
    assert result['valid']
    assert result['measurement']=={'reported_percent':85.0,'verified_percent':80.0,'accepted_percent':65.0}
    assert result['earned_percent'] is None and result['billing_eligible_quantity'] is None

def test_no_qa_accepted_means_zero_not_verified():
    result=run(links=[])
    assert result['valid'] and result['measurement']['accepted_percent']==0

def test_missing_source_collection_fails_closed():
    args=BASE.copy();result=calculate(**args, approved_evidence_links=None)
    assert not result['valid'] and result['measurement']['accepted_percent'] is None

def test_reviewer_must_be_independent():
    assert not run(links=[link(reviewer_user_id=20)])['valid']

def test_proposed_not_accepted():
    assert not run(links=[link(state='Proposed')])['valid']

def test_mismatched_project_fails():
    assert not run(links=[link(project_id=8)])['valid']

def test_mismatched_line_fails():
    assert not run(links=[link(construction_line_id=99)])['valid']

def test_duplicate_inspection_fails():
    assert not run(links=[link(),link(link_id=2)])['valid']

def test_accepted_above_verified_fails():
    assert not run(links=[link(accepted_quantity=81)])['valid']

def test_verified_above_reported_fails():
    assert not run(verified_quantity=90)['valid']

def test_reported_above_plan_fails():
    assert not run(reported_quantity=105,verified_quantity=80)['valid']

def test_nan_and_boolean_quantities_rejected():
    assert not run(reported_quantity='NaN')['valid']
    assert not run(reported_quantity=True)['valid']

def test_zero_or_negative_plan_rejected():
    assert not run(planned_quantity=0)['valid']
    assert not run(planned_quantity=-1)['valid']

def test_missing_unit_rejected():
    assert not run(unit='')['valid']

def test_no_earning_without_approval_policy():
    assert run()['status']=='UNPUBLISHED_MEASUREMENT_PREVIEW'
