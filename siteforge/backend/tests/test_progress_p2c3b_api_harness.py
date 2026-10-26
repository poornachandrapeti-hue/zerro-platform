import importlib.util
from pathlib import Path
import pytest

SRC = Path(__file__).resolve().parents[3] / 'tools/progress/p2c3b_api_acceptance.py'
spec = importlib.util.spec_from_file_location('p2c3b_api_acceptance', SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

@pytest.mark.parametrize('url',[
    'https://localhost:9999', 'http://evil.com:9999',
    'http://127.0.0.1:8080', 'http://localhost:80',
    'http://user:pass@localhost:9999', 'http://localhost:9999/some-path',
    'http://localhost:9999?token=secret'
])
def test_reject_unsafe_base_url(url):
    with pytest.raises(ValueError): m.safe_base(url)

def test_accept_dedicated_loopback():
    assert m.safe_base('http://127.0.0.1:8189/') == 'http://127.0.0.1:8189'

@pytest.mark.parametrize('missing',['P2C3B_RUN_WRITES','P2C3B_DATABASE_NAME','P2C3B_BASE_URL'])
def test_missing_required_setting_fails(monkeypatch,missing):
    monkeypatch.delenv(missing, raising=False)
    with pytest.raises(ValueError): m.required(missing)

def test_scope_rejects_production_name(monkeypatch):
    monkeypatch.setenv('P2C3B_RUN_WRITES','I_UNDERSTAND_TEST_ONLY')
    monkeypatch.setenv('P2C3B_DATABASE_NAME','siteforge')
    with pytest.raises(ValueError,match='isolated database'): m.run()
