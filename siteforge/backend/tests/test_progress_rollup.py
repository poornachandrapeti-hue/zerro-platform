from types import SimpleNamespace
from app.domains.progress_monitoring.rollup import calculate_construction_rollups

def record(id, source=None, **metrics):
    return dict(activity_id=id,link_status='linked', source={'construction_activity_id':source or id},
                measurement={'reported_percent':40,'verified_percent':30,'accepted_percent':20,**metrics})
def weights(*items):
    return [SimpleNamespace(activity_id=i,weight_basis_points=w) for i,w in items]

def test_separate_measures_and_repeated_period_weights():
    result=calculate_construction_rollups([record(1),record(2,reported_percent=80,verified_percent=60,accepted_percent=50)], weights((1,6000),(2,4000),(1,6000),(2,4000)),True)
    assert result['valid_scheme']
    assert result['measures']=={'reported_percent':56.0,'verified_percent':42.0,'accepted_percent':32.0}

def test_scoped_never_leaks_aggregate():
    assert calculate_construction_rollups([record(1)],weights((1,10000)),False)['measures']['verified_percent'] is None

def test_inconsistent_period_weights_block_every_measure():
    result=calculate_construction_rollups([record(1)],weights((1,10000),(1,5000)),True)
    assert not result['valid_scheme']
    assert all(value is None for value in result['measures'].values())

def test_duplicate_source_blocks_rollup():
    result=calculate_construction_rollups([record(1,9),record(2,9)],weights((1,5000),(2,5000)),True)
    assert not result['valid_scheme']

def test_missing_acceptance_does_not_invalidate_verified():
    result=calculate_construction_rollups([record(1,accepted_percent=None)],weights((1,10000)),True)
    assert result['measures']['verified_percent']==30
    assert result['measures']['accepted_percent'] is None

def test_scope_and_out_of_range_are_not_silently_capped():
    result=calculate_construction_rollups([record(1,verified_percent=101)],weights((1,10000)),True)
    assert result['measures']['verified_percent'] is None
    assert result['measures']['reported_percent']==40

def test_weights_must_total_full_scheme():
    result=calculate_construction_rollups([record(1)],weights((1,8000)),True)
    assert not result['valid_scheme']
