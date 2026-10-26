"""Fail-closed closeout-source verification regression checks."""
from pathlib import Path
import ast

ROUTER = Path(__file__).resolve().parents[1] / 'app/domains/contracts/router.py'

def test_read_endpoint_present_and_project_scoped():
    tree = ast.parse(ROUTER.read_text())
    f = next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='closeout_source_verification')
    source = ast.get_source_segment(ROUTER.read_text(),f)
    assert 'get_contract(db,user,pid,cid)' in source
    assert "'policy':'fail_closed'" in source
    assert "'source_verified':verified" in source

def test_external_evidence_does_not_stamp_verified_at():
    source = ROUTER.read_text()
    assert "row.verified_by=None if body.check_type in CLOSEOUT_SOURCES else user.id" in source
    assert "row.verified_at=None if body.check_type in CLOSEOUT_SOURCES else datetime.now(timezone.utc)" in source
    assert "'Evidence Recorded' if body.check_type in CLOSEOUT_SOURCES" in source

def test_readiness_and_close_action_share_fail_closed_blockers():
    """Legacy Verified status alone cannot satisfy an external source check."""
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.domains.contracts.router import CLOSEOUT_TYPES, CLOSEOUT_SOURCES, closeout_blockers
    contract=SimpleNamespace(id=4,organization_id=2)
    db=Mock()
    db.query.return_value.filter_by.return_value.all.side_effect=[
        [SimpleNamespace(check_type=name,status='Verified') for name in CLOSEOUT_TYPES],
        [], []
    ]
    blockers=closeout_blockers(db,contract)
    assert set(blockers)=={'check:'+name for name in CLOSEOUT_SOURCES}
