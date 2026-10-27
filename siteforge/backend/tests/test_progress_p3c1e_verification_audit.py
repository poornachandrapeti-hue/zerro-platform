"""P3C1E pure verification-audit invariant tests."""
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

MODULE = Path(__file__).resolve().parents[3] / 'tools/progress/p3c1e_verification_audit.py'
spec = importlib.util.spec_from_file_location('progress_p3c1e_audit', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
NOW = datetime.now(timezone.utc)


def record(**changes):
    r=dict(id=1, organization_id=1, project_id=8, progress_line_id=44,
           verified_quantity=Decimal('4'), status='Approved', version=2,
           proposer_user_id=10, reviewer_user_id=20, verified_at=NOW)
    r.update(changes)
    return r


def events():
    return [dict(id=1,verification_id=1,organization_id=1,project_id=8,
                 action='Proposed',actor_user_id=10,created_at=NOW),
            dict(id=2,verification_id=1,organization_id=1,project_id=8,
                 action='Approved',actor_user_id=20,created_at=NOW)]


def test_valid_approval(): assert audit.evaluate([record()],events()) == []
def test_self_review(): assert 'self review' in str(audit.evaluate([record(reviewer_user_id=10)],events()))
def test_missing_approval_timestamp(): assert 'timestamp' in str(audit.evaluate([record(verified_at=None)],events()))
def test_bad_event_sequence(): assert 'sequence' in str(audit.evaluate([record()],events()[:1]))
def test_stale_version(): assert 'version/event count' in str(audit.evaluate([record(version=3)],events()))
def test_wrong_event_project():
    e=events(); e[1]['project_id']=9
    assert 'mismatch' in str(audit.evaluate([record()],e))
def test_duplicate_approved_line():
    rows=[record(),record(id=2,version=2)]
    e=events()+[{**item,'id':item['id']+2,'verification_id':2} for item in events()]
    assert 'simultaneously approved' in str(audit.evaluate(rows,e))
def test_rejected_path():
    row=record(status='Rejected', verified_at=None)
    e=events();e[1]['action']='Rejected'
    assert audit.evaluate([row],e) == []
def test_revoked_path():
    row=record(status='Revoked',version=3)
    e=events()+[dict(id=3,verification_id=1,organization_id=1,project_id=8,
                     action='Revoked',actor_user_id=20,created_at=NOW)]
    assert audit.evaluate([row],e) == []
def test_proposed_path():
    row=record(status='Proposed',version=1,reviewer_user_id=None,verified_at=None)
    assert audit.evaluate([row],events()[:1]) == []
def test_orphan_event(): assert 'orphan' in str(audit.evaluate([],[events()[0]]))
def test_zero_quantity(): assert 'non-positive' in str(audit.evaluate([record(verified_quantity=0)],events()))
