from datetime import datetime,timezone
from fastapi import HTTPException
import pytest
from app.domains.contracts.router import CorrespondenceCreateIn, CorrespondenceIssueIn, CORRESPONDENCE_CATEGORIES, aware

def test_correspondence_categories_and_valid_draft():
    assert {'Notice','Letter','Instruction','Response'}.issubset(CORRESPONDENCE_CATEGORIES)
    draft=CorrespondenceCreateIn(number='N-001',category='Notice',subject='Delay notice',content='Notice regarding delay event.',sender_company_id=1,recipient_company_id=2)
    assert draft.linked_claim_id is None

def test_dispatch_evidence_is_mandatory():
    with pytest.raises(Exception):
        CorrespondenceIssueIn(delivery_method='Email',dispatch_reference='EMAIL-1',dispatch_evidence='',issued_at=datetime.now(timezone.utc))

def test_issue_timestamp_requires_timezone():
    with pytest.raises(HTTPException) as e:
        aware(datetime(2026,10,21))
    assert e.value.status_code==422
