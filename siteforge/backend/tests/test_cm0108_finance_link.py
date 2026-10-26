from decimal import Decimal
from fastapi import HTTPException
import pytest
from app.domains.contracts.router import FinanceLinkIn,create_finance_link,read_finance_effective_value
from app.domains.commercial_financials.models import FinanceContract
from tests.test_contracts_integrated import state, contract


def make_finance(state, c, number=None):
    db,p,admin,peer,pa,pb,a,b,other=state
    f=FinanceContract(organization_id=c.organization_id,project_id=p.id,
        number=number or c.number,contract_type=c.contract_type,
        counterparty_company_id=c.counterparty_company_id,currency=c.currency,
        original_value=c.original_value,created_by=admin.id)
    db.add(f);db.commit()
    return f


def test_finance_link_idempotent_and_read_only(state):
    db,p,admin,*_=state
    c=contract(state);f=make_finance(state,c)
    response=create_finance_link(p.id,c.id,FinanceLinkIn(finance_contract_id=f.id),admin,db)
    assert response['idempotent'] is False
    again=create_finance_link(p.id,c.id,FinanceLinkIn(finance_contract_id=f.id),admin,db)
    assert again['idempotent'] is True
    result=read_finance_effective_value(p.id,c.id,admin,db)
    assert Decimal(result['approved_effective_value'])==Decimal('100000')
    assert result['billing_records_modified'] is False
    assert db.get(FinanceContract,f.id).original_value==Decimal('100000')


def test_finance_link_rejects_mismatched_identity(state):
    db,p,admin,*_=state
    c=contract(state);f=make_finance(state,c,number='DIFFERENT')
    with pytest.raises(HTTPException) as exc:
        create_finance_link(p.id,c.id,FinanceLinkIn(finance_contract_id=f.id),admin,db)
    assert exc.value.status_code==409
