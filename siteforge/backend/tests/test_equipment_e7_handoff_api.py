from types import SimpleNamespace as NS
from datetime import date
import pytest
from fastapi import HTTPException
from app.domains.planning_reporting import equipment_e7_handoff_api as api


def body(kind='HireContract', key='request-key-123', aid=15, evidence='signed-off'):
    return api.HandoffInput(authority_kind=kind, authority_id=aid, request_key=key, evidence_ref=evidence)


class Query:
    def __init__(self, db):
        self.db = db
        self.kwargs = {}
    def filter_by(self, **kwargs):
        self.kwargs = kwargs
        return self
    def one_or_none(self):
        for record in self.db.records:
            if all(getattr(record, k, None) == v for k,v in self.kwargs.items()):
                return record
        return None


class DB:
    def __init__(self):
        self.records = []
        self.staged = None
        self.commits = 0
    def query(self, cls):
        assert cls is api.EquipmentAuthorityHandoff
        return Query(self)
    def add(self, record):
        self.staged = record
    def commit(self):
        self.commits += 1
        self.staged.id = self.commits
        self.records.append(self.staged)
        self.staged = None
    def refresh(self, record):
        pass


@pytest.fixture(autouse=True)
def authorized(monkeypatch):
    monkeypatch.setattr(api, '_authorized_asset',
                        lambda db,user,pid,asset_id: NS(id=asset_id,ownership_type='Hired',hire_contract_ref='H-18'))
    monkeypatch.setattr(api, 'read_hire_contract_authority',
                        lambda *args, **kw: {'reference':'H-18','contract_id':15,'expires_at':date(2028,1,1),'hire_rate_verified':False})
    monkeypatch.setattr(api, 'read_spares_request_authority',
                        lambda *args, **kw: {'stores_request_id':21, 'stock_posted':False})


def user():return NS(id=4, organization_id=2)


def test_hire_handoff_readback_snapshot_is_unposted():
    db = DB()
    result = api.record_authority_handoff(3, 8, body(), user(), db)
    assert result['handoff_recorded'] and result['finance_posted'] is False
    assert result['stock_posted'] is False and result['hire_billed'] is False
    assert result['authority_snapshot']['expires_at'] == '2028-01-01'
    assert db.commits == 1
    same = api.record_authority_handoff(3, 8, body(), user(), db)
    assert same['handoff_id'] == result['handoff_id'] and db.commits == 1
    assert api.get_authority_handoff(3,8,1,user(),db)['authority_kind']=='HireContract'


def test_spares_reference_does_not_post_stock():
    db=DB()
    result=api.record_authority_handoff(3,8,body('StoresSpareRequest', aid=21),user(),db)
    assert result['stock_posted'] is False and result['authority_snapshot']['stores_request_id']==21


@pytest.mark.parametrize('changed', [body(aid=16),body(evidence='different'),body(kind='StoresSpareRequest',aid=21)])
def test_idempotency_key_conflict(changed):
    db=DB()
    api.record_authority_handoff(3,8,body(),user(),db)
    with pytest.raises(HTTPException) as exc:
        api.record_authority_handoff(3,8,changed,user(),db)
    assert exc.value.status_code == 409


def test_other_project_cannot_get_record():
    db=DB()
    api.record_authority_handoff(3,8,body(),user(),db)
    with pytest.raises(HTTPException) as exc:
        api.get_authority_handoff(5,8,1,user(),db)
    assert exc.value.status_code==404


def test_ref_mismatch_denied(monkeypatch):
    monkeypatch.setattr(api, 'read_hire_contract_authority',lambda *args,**kwargs:{'reference':'OTHER'})
    with pytest.raises(HTTPException) as exc:
        api.record_authority_handoff(3,8,body(),user(),DB())
    assert exc.value.status_code==409


def test_unapproved_authority_denied(monkeypatch):
    def deny(*args,**kw): raise HTTPException(409,'unapproved')
    monkeypatch.setattr(api,'read_spares_request_authority',deny)
    with pytest.raises(HTTPException) as exc:
        api.record_authority_handoff(3,8,body('StoresSpareRequest',aid=21),user(),DB())
    assert exc.value.status_code==409


def test_invalid_idempotency_or_evidence_rejected():
    for attr, value in [('request_key',' bad-key '),('evidence_ref',' signed ')]:
        p=body().model_copy(update={attr:value})
        with pytest.raises(HTTPException) as exc:
            api.record_authority_handoff(3,8,p,user(),DB())
        assert exc.value.status_code==422


def test_disallow_non_hired_contract(monkeypatch):
    monkeypatch.setattr(api,'_authorized_asset',lambda *a: NS(ownership_type='Owned',hire_contract_ref=None))
    with pytest.raises(HTTPException) as exc:
        api.record_authority_handoff(3,8,body(),user(),DB())
    assert exc.value.status_code==409
