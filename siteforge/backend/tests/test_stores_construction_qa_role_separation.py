"""Prevent cross-discipline permission regressions in revocation impact workflow."""
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "app/domains/stores_inventory/qa_issued_impact.py").read_text()

def _body(name):
    return SRC.split(f"def {name}(", 1)[1].split("\n@router.", 1)[0]

def test_construction_ack_uses_project_and_construction_permissions_only():
    body = _body("acknowledge_construction_impact")
    assert "supply_service._project(db, u, pid, action=None)" in body
    assert "permitted(db, u, project, 'construction.view')" in body
    assert "qa_access(db, u, pid" not in body
    assert "if task.owner_id != u.id:" in body
    assert ".with_for_update().first()" in body

def test_qa_verification_requires_quality_edit_not_construction_role():
    body = _body("verify_construction_impact")
    assert "qa_access(db, u, pid, edit=True)" in body
    assert "permitted(db, u, project, 'construction.view')" not in body
    assert "if task.owner_id == u.id:" in body
    assert "task.version != data.task_version" in body
