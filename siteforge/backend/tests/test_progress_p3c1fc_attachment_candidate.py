import hashlib
from types import SimpleNamespace
import pytest
from app.domains.progress_monitoring.p3c1fc_attachment_candidate import (
    EvidenceCandidateError, read_project_attachment_candidate,
)
from app.domains.engineering_documents.models import ProjectFile, StoredFile


class FakeDb:
    def __init__(self, link, file):
        self.link, self.file = link, file
    def get(self, cls, ident):
        if cls is ProjectFile:
            return self.link if self.link and ident == self.link.id else None
        if cls is StoredFile:
            return self.file if self.file and ident == self.file.id else None
        raise AssertionError(cls)


def fixture():
    payload = b'not proof of physical measurement'
    digest = hashlib.sha256(payload).hexdigest()
    link = SimpleNamespace(id=21, project_id=7, file_id=33, active=True)
    file = SimpleNamespace(id=33, organization_id=5, sha256=digest, size=len(payload), storage_name=digest, scan_status='available')
    return FakeDb(link,file),payload


def read(db, **opts):
    return read_project_attachment_candidate(db, organization_id=opts.get('organization_id',5),
         project_id=opts.get('project_id',7),project_file_id=opts.get('project_file_id',21),
         authorized=opts.get('authorized',True))


def test_valid_attachment_is_only_candidate(monkeypatch):
    db,payload=fixture()
    monkeypatch.setattr('app.domains.engineering_documents.files.read_file',lambda _:payload)
    result=read(db)
    assert result.attachment_integrity_verified
    assert not result.physical_measurement_authenticated
    assert not result.eligible_for_publication
    assert not result.eligible_for_billing

@pytest.mark.parametrize('override',[{'authorized':False},{'project_id':8},{'organization_id':6},{'project_file_id':22},{'project_id':0}])
def test_fail_closed_scopes(monkeypatch,override):
    db,payload=fixture()
    monkeypatch.setattr('app.domains.engineering_documents.files.read_file',lambda _:payload)
    with pytest.raises(EvidenceCandidateError):read(db,**override)

@pytest.mark.parametrize('change',[('active',False),('file_id',55)])
def test_invalid_project_links(monkeypatch,change):
    db,payload=fixture()
    setattr(db.link,*change)
    monkeypatch.setattr('app.domains.engineering_documents.files.read_file',lambda _:payload)
    with pytest.raises(EvidenceCandidateError):read(db)

@pytest.mark.parametrize('change',[('scan_status','pending'),('size',999),('storage_name','fake'),('sha256','bad')])
def test_invalid_metadata(monkeypatch,change):
    db,payload=fixture()
    setattr(db.file,*change)
    monkeypatch.setattr('app.domains.engineering_documents.files.read_file',lambda _:payload)
    with pytest.raises(EvidenceCandidateError):read(db)


def test_bytes_tampered(monkeypatch):
    db,_=fixture()
    monkeypatch.setattr('app.domains.engineering_documents.files.read_file',lambda _:b'changed bytes not real')
    with pytest.raises(EvidenceCandidateError):read(db)


def test_read_fails(monkeypatch):
    db,_=fixture()
    def bad(_):raise OSError('not found')
    monkeypatch.setattr('app.domains.engineering_documents.files.read_file',bad)
    with pytest.raises(EvidenceCandidateError):read(db)
