"""Pure audit logic tests; do not require a database."""
import importlib.util
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[3] / 'tools/progress/p2c3_audit.py'
spec=importlib.util.spec_from_file_location('p2c3_audit', AUDIT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def row(**changes):
    d=dict(id=1,status='Approved',created_by=10,reviewed_by=11,accepted_quantity='3',version=2)
    d.update(changes)
    return d


def events(*actions):
    return [dict(link_id=1,action=a) for a in actions]


def test_valid_approval():
    assert mod.issues_from_rows([row()], events('Proposed','Approved')) == []


def test_self_review_denied():
    assert any('same proposer' in p for p in mod.issues_from_rows([row(reviewed_by=10)],events('Proposed','Approved')))


def test_missing_event():
    assert mod.issues_from_rows([row()], events('Proposed'))


def test_negative_quantity():
    assert mod.issues_from_rows([row(accepted_quantity='0')], events('Proposed','Approved'))


def test_version_mismatch():
    assert mod.issues_from_rows([row(version=3)], events('Proposed','Approved'))


def test_empty_link_set():
    assert mod.issues_from_rows([],[]) == []
