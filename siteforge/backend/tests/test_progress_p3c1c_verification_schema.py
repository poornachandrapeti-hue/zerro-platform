"""P3C1C source contract tests (do not imply DB/live approval tests)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'app/domains/progress_monitoring/p3c1c_verification_models.py'
MIGRATION = ROOT / 'migrations/versions/progress_p3c1c_quantity_verifications.py'


def test_python_syntax():
    for file in (MODEL, MIGRATION):
        ast.parse(file.read_text(encoding='utf-8'))


def test_single_migration_parent():
    txt = MIGRATION.read_text(encoding='utf-8')
    assert "down_revision = 'progress_p2c2a_evidence_links'" in txt


def test_tables_named_consistently():
    for file in (MODEL, MIGRATION):
        txt = file.read_text(encoding='utf-8')
        assert 'progress_quantity_verifications' in txt
        assert 'progress_quantity_verification_events' in txt


def test_independent_reviewer_constraint():
    for file in (MODEL, MIGRATION):
        assert 'reviewer_user_id <> proposer_user_id' in file.read_text(encoding='utf-8')


def test_quantity_must_be_positive():
    for file in (MODEL, MIGRATION):
        assert 'verified_quantity > 0' in file.read_text(encoding='utf-8')


def test_status_domain():
    for file in (MODEL, MIGRATION):
        assert "('Proposed', 'Approved', 'Rejected', 'Revoked')" in file.read_text(encoding='utf-8')


def test_unique_revision_binding():
    for file in (MODEL, MIGRATION):
        assert 'uq_progress_qty_verification_revision' in file.read_text(encoding='utf-8')


def test_no_progress_or_billing_write():
    txt = MODEL.read_text(encoding='utf-8') + MIGRATION.read_text(encoding='utf-8')
    assert 'billing_ledger' not in txt
    assert 'progress_rollup' not in txt
