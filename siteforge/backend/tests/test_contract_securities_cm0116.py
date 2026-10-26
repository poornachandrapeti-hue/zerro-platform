from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.domains.contracts.router import SecurityCreateIn, SecurityRenewIn, SecurityReleaseIn, SECURITY_TYPES, aware
from app.domains.contracts.models import ContractSecurityInstrument, ContractSecurityEvent

def test_instrument_payload_and_type_catalogue():
    now=datetime.now(timezone.utc)
    item=SecurityCreateIn(instrument_type='Bank Guarantee',issuer='Approved Bank',reference_number='BG-100',amount=Decimal('1000.00'),currency='INR',issue_at=now,expires_at=now+timedelta(days=180),renewal_owner_id=1,release_conditions='Authorized project closeout',evidence_ref='private://evidence/bg100')
    assert item.currency=='INR' and item.instrument_type in SECURITY_TYPES
    assert ContractSecurityInstrument.__tablename__=='contract_security_instruments'
    assert ContractSecurityEvent.__tablename__=='contract_security_events'

def test_evidence_and_currency_are_required():
    now=datetime.now(timezone.utc)
    data=dict(instrument_type='Insurance',issuer='Insurer',reference_number='INS-01',amount='500',currency='INR',issue_at=now,expires_at=now+timedelta(days=30),renewal_owner_id=1,release_conditions='Upon closeout',evidence_ref='ref')
    with pytest.raises(Exception):SecurityCreateIn(**{**data,'currency':'RUPEES'})
    with pytest.raises(Exception):SecurityCreateIn(**{**data,'evidence_ref':''})
    with pytest.raises(Exception):SecurityRenewIn(expires_at=now,evidence_ref='')
    with pytest.raises(Exception):SecurityReleaseIn(evidence_ref='')

def test_dates_must_include_timezone():
    with pytest.raises(HTTPException) as ex:aware(datetime(2026,10,21))
    assert ex.value.status_code==422
