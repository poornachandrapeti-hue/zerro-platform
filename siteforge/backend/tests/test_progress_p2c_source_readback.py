from types import SimpleNamespace as Obj
from fastapi import HTTPException
import pytest
from app.domains.progress_monitoring.p2c_source_readback import allowed, candidate_status, construction_candidate, qa_candidate

class Query:
    def __init__(self, data): self.data=data
    def filter_by(self, **kwargs):
        self.data=[x for x in self.data if all(getattr(x,k,None)==v for k,v in kwargs.items())]; return self
    def first(self): return self.data[0] if self.data else None

class DB:
    def __init__(self, line=None, report=None, activity=None, qa=None):
        self.line=line;self.report=report;self.activity=activity;self.qa=qa
    def get(self, cls, key): return self.line if self.line and self.line.id==key else None
    def query(self,cls):
        name=cls.__name__
        return Query([r for r in [self.report if name=='ProgressReport' else self.activity if name=='ConstructionActivity' else self.qa if name=='ConstructionRequest' else None] if r])

USER=Obj(organization_id=2)
SCOPE={'all':False,'pairs':[(10,{4})]}

def setup(monkeypatch):
    import app.domains.progress_monitoring.p2c_source_readback as m
    monkeypatch.setattr(m,'progress_scope',lambda db,user,pid:SCOPE)
    return DB(line=Obj(id=11,report_id=12,activity_id=13,quantity=5),
        report=Obj(id=12,organization_id=2,project_id=3,company_id=10,discipline_id=4,status='Approved'),
        activity=Obj(id=13,organization_id=2,project_id=3,company_id=10,discipline_id=4,package_id=17),
        qa=Obj(id=18,organization_id=2,project_id=3,company_id=10,activity_id=13,package_id=17,status='Approved',outcome='Accepted',accepted_quantity=4))

def test_scope():
    assert allowed(10,4,SCOPE)
    assert not allowed(11,4,SCOPE)
    assert not allowed(None,4,SCOPE)
    assert not allowed(10,None,SCOPE)
    assert allowed(None,None,{'all':True})

def test_never_earns_from_matching_activity():
    x=candidate_status(Obj(status='Approved'),Obj(activity_id=13),Obj(status='Approved',outcome='Accepted',activity_id=13))
    assert x['same_activity'] and not x['link_verified'] and not x['eligible_for_earned_progress']

def test_source_candidates(monkeypatch):
    db=setup(monkeypatch)
    c=construction_candidate(3,11,USER,db)
    q=qa_candidate(3,18,USER,db)
    assert c['reported_quantity']=='5' and q['accepted_quantity']=='4'
    assert not c['eligible_for_earned_progress'] and not q['eligible_for_earned_progress']

@pytest.mark.parametrize('bad', ['report_scope','activity_scope','company_scope','qa_package'])
def test_reject_bad_sources(monkeypatch,bad):
    db=setup(monkeypatch)
    if bad=='report_scope': db.report.project_id=99
    if bad=='activity_scope': db.activity.organization_id=99
    if bad=='company_scope': db.report.company_id=11
    if bad=='qa_package': db.qa.package_id=19
    with pytest.raises(HTTPException):
        (qa_candidate if bad=='qa_package' else construction_candidate)(3,18 if bad=='qa_package' else 11,USER,db)

def test_missing_and_cross_tenant_qa(monkeypatch):
    db=setup(monkeypatch)
    db.qa.organization_id=99
    with pytest.raises(HTTPException) as err: qa_candidate(3,18,USER,db)
    assert err.value.status_code==404
