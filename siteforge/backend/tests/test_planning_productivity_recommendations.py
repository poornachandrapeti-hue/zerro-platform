from app.domains.planning_reporting.productivity_recommendations import estimate_remaining


def source(scope=100, verified=60, unit='MT'):
    return {'link_status':'linked','measurement':{'scope_quantity':scope,'verified_quantity':verified,'unit':unit}}


def test_verified_quantity_rate():
    r=estimate_remaining(source(), 5, 'MT')
    assert r['recommended_remaining_hours']==8
    assert r['remaining_quantity']==40
    assert r['source_as_of_forecast_data_date'] is False


def test_completed():
    r=estimate_remaining(source(100,100), 5, 'MT')
    assert r['recommended_remaining_hours']==0
    assert r['completed_from_current_measurement'] is True


def test_bad_units_or_unknown_source_are_not_estimated():
    assert estimate_remaining(source(), 5, 'm3')['status']=='unavailable'
    assert estimate_remaining({'link_status':'unmapped'}, 5, 'MT')['status']=='unavailable'


def test_invalid_measurements_and_rate_are_rejected():
    assert estimate_remaining(source(100,120),5,'MT')['status']=='unavailable'
    assert estimate_remaining(source(),0,'MT')['status']=='unavailable'
    assert estimate_remaining(source(0,0),5,'MT')['status']=='unavailable'
