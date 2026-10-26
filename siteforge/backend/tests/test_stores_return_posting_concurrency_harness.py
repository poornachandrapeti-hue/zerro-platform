import pytest
from app.domains.stores_inventory.return_posting_concurrency_harness import validate_target, classify


def test_reject_remote(monkeypatch):
    monkeypatch.setenv('STORES_RETURN_TEST_DATABASE_ISOLATED', 'yes')
    with pytest.raises(ValueError):
        validate_target('https://zerroqa.flagestrator.com', 'I_UNDERSTAND_THIS_POSTS_TO_DISPOSABLE_STOCK', 1, 2, 3)


def test_reject_no_isolation(monkeypatch):
    monkeypatch.delenv('STORES_RETURN_TEST_DATABASE_ISOLATED', raising=False)
    with pytest.raises(ValueError):
        validate_target('http://localhost:8180', 'I_UNDERSTAND_THIS_POSTS_TO_DISPOSABLE_STOCK', 1, 2, 3)


def test_allow_isolated(monkeypatch):
    monkeypatch.setenv('STORES_RETURN_TEST_DATABASE_ISOLATED', 'yes')
    validate_target('http://127.0.0.1:8180', 'I_UNDERSTAND_THIS_POSTS_TO_DISPOSABLE_STOCK', 1, 2, 3)


@pytest.mark.parametrize('values,result', [([200,409],'RACE_GATE_PASS_API_ONLY'),([200,200],'FAIL_MULTIPLE_SUCCESSES'),([503,503],'INCONCLUSIVE'),([401,401],'INCONCLUSIVE')])
def test_classify(values, result):
    assert classify(values) == result
