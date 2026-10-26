"""Source contract regression guard for the QA revocation state machine.

Live PostgreSQL interleaving still requires a running test database.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory'


def test_revoked_case_cannot_be_reopened_by_ordinary_disposition():
    source = (ROOT / 'router.py').read_text()
    portion = source.split('def record_inspection_decision(', 1)[1].split('class InspectionRevocationIn', 1)[0]
    assert 'if case.status == "Quality Revoked":' in portion
    assert 'raise HTTPException(409, "Revoked QA case requires a separate reinspection and release")' in portion
    assert portion.index('if previous:') < portion.index('if case.status == "Quality Revoked":') < portion.index('case.status = "Pending Inspection"')


def test_all_physical_writers_require_explicit_qa_case_state():
    for name in ('atomic_lot_issue.py', 'atomic_lot_acceptance.py', 'lot_reservations.py'):
        source = (ROOT / name).read_text()
        assert 'case.status not in (' in source, name
        assert 'Pending Inspection' in source and 'Disposition Recorded' in source, name
        assert 'case_version_at_entry == case.version' in source, name


def test_revocation_bumps_case_version_and_marks_terminal_hold():
    source = (ROOT / 'router.py').read_text()
    revocation = source.split('def revoke_inspection_acceptance(', 1)[1].split('@router.get(', 1)[0]
    assert 'case.status = "Quality Revoked"' in revocation
    assert 'case.version += 1' in revocation
    assert 'with_for_update()' in revocation
