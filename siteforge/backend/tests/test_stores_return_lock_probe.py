import pytest
from app.domains.stores_inventory.return_lock_probe import classify_observations, probe, _PROBE_NAMESPACE


def test_probe_truth_table():
    assert classify_observations(True, True, True)
    for args in [(False, True, True), (True, False, True), (True, True, False)]:
        assert not classify_observations(*args)


def test_requires_positive_project():
    for value in (0, -1, None, '1'):
        with pytest.raises(ValueError):
            probe(value)


def test_probe_namespace_not_zero():
    assert 0 < _PROBE_NAMESPACE < 2**31


def test_probe_does_not_claim_business_posting(monkeypatch):
    class FakeEngine:
        dialect = type('D', (), {'name': 'sqlite'})()
    result = probe(1, db_engine=FakeEngine())
    assert not result['lock_probe_passed']
    assert not result['return_posting_validated']
    assert not result['posting_feature_enabled']
    assert result['read_only']
