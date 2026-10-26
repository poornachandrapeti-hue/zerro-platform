from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from app.domains.contracts.models import ContractCloseoutCheck, ContractWarranty, ContractObligation, ContractSecurityInstrument
from app.domains.contracts.router import CLOSEOUT_TYPES, closeout_blockers, WarrantyIn, CloseoutCheckIn


def test_required_checklist_and_model_tables():
    assert len(CLOSEOUT_TYPES)==9
    assert {'finance_settlement','qa_acceptance','commissioning_handover','warranty_assignment'} <= CLOSEOUT_TYPES
    assert ContractCloseoutCheck.__tablename__=='contract_closeout_checks'
    assert ContractWarranty.__tablename__=='contract_warranties'


def test_closeout_blocks_unverified_checks_and_live_obligations_and_security():
    contract=SimpleNamespace(id=4,organization_id=2)
    db=Mock()
    db.query.return_value.filter_by.return_value.all.side_effect=[
        [SimpleNamespace(check_type='scope_completion',status='Verified')],
        [SimpleNamespace(id=5,status='In Progress')],
        [SimpleNamespace(id=9,status='Active')]
    ]
    blockers=closeout_blockers(db,contract)
    assert 'check:finance_settlement' in blockers
    assert 'obligation:5' in blockers
    assert 'security:9' in blockers


def test_warranty_and_closeout_evidence_required():
    with pytest.raises(Exception):WarrantyIn(description='x',owner_id=1)
    with pytest.raises(Exception):CloseoutCheckIn(check_type='finance_settlement',source_record_ref='',evidence_ref='a')
