import json
import pytest
from integrations.command_center.phase8_signoff import REQUIRED_CHECKS, assess, main


def test_empty_evidence_is_blocked():
    result = assess({})
    assert result['signoff'] == 'blocked'
    assert len(result['blocking_checks']) == len(REQUIRED_CHECKS)


def test_false_and_nonboolean_do_not_pass():
    result = assess({'source_tests': False, 'frontend_build': 'true', 'feed_smoke': 1})
    assert result['statuses']['source_tests'] == 'failed'
    assert result['statuses']['frontend_build'] == 'unverified'
    assert result['statuses']['feed_smoke'] == 'unverified'


def test_all_explicit_checks_are_only_eligible_for_review():
    result = assess(dict.fromkeys(REQUIRED_CHECKS, True))
    assert result['signoff'] == 'eligible_for_manual_review'
    assert not result['blocking_checks']


def test_unknown_check_rejected():
    with pytest.raises(ValueError, match='Unknown check'):
        assess({'invented_check': True})


def test_cli_generates_blocking_report(tmp_path, capsys):
    out = tmp_path / 'signoff.json'
    assert main(['--output', str(out)]) == 1
    saved = json.loads(out.read_text())
    assert saved['signoff'] == 'blocked'
    assert 'command_backend_route' in saved['blocking_checks']
    assert 'blocked' in capsys.readouterr().out


def test_invalid_evidence_returns_error(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{invalid')
    with pytest.raises(SystemExit) as exc:
        main(['--evidence', str(path)])
    assert exc.value.code == 2
