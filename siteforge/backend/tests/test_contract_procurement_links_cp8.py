"""Checkpoint 8: governing contract links never mutate purchase orders."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from datetime import date
from app.db import Base
from app.domains.identity_projects.models import Organization, Company, User, Project
from app.domains.contracts.models import Contract, ContractVersion, ContractProcurementLink
from app.domains.contracts.router import ProcurementLinkIn, link_procurement_po
from app.domains.supply_chain.models import Vendor, PurchaseOrder


def test_procurement_link_requires_matching_vendor_and_preserves_po():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org=Organization(name='Cp8 Org'); db.add(org);db.flush()
        owner=Company(organization_id=org.id,name='Owner',name_key='owner')
        vendorco=Company(organization_id=org.id,name='Vendor',name_key='vendor')
        wrong=Company(organization_id=org.id,name='Wrong',name_key='wrong')
        db.add_all([owner,vendorco,wrong]);db.flush()
        admin=User(organization_id=org.id,email='cp8@test.invalid',name='Admin',password_hash='!',organization_admin=True)
        db.add(admin);db.flush()
        proj=Project(organization_id=org.id,code='CP8',code_key='cp8',name='CP8',created_by=admin.id)
        db.add(proj);db.flush()
        c=Contract(organization_id=org.id,project_id=proj.id,number='C-1',title='Vendor agreement',contract_type='Subcontract',contracting_company_id=owner.id,counterparty_company_id=vendorco.id,manager_user_id=admin.id,scope='Supplier scope',currency='INR',original_value=100,lifecycle='Executed',current_version=1,created_by=admin.id)
        db.add(c);db.flush()
        ver=ContractVersion(contract_id=c.id,version=1,snapshot={},reason='Initial execution',created_by=admin.id)
        db.add(ver);db.flush()
        v=Vendor(organization_id=org.id,code='WRONG',code_key='wrong',company_id=wrong.id,created_by=admin.id)
        db.add(v);db.flush()
        # These IDs must point at real references; use an issued PO with only required values.
        po=PurchaseOrder(organization_id=org.id,project_id=proj.id,rfq_id=1,vendor_id=v.id,number='PO1',number_key='po1',company_id=owner.id,discipline_id=1,currency='INR',terms='',delivery_location='',promised_date=date(2026,12,1),issue_date=date(2026,10,20),status='Issued',created_by=admin.id)
        db.add(po);db.flush()
        with pytest.raises(HTTPException) as exc:
            link_procurement_po(proj.id,c.id,ProcurementLinkIn(purchase_order_id=po.id),admin,db)
        assert exc.value.status_code==409
        v.company_id=vendorco.id;db.flush()
        first=link_procurement_po(proj.id,c.id,ProcurementLinkIn(purchase_order_id=po.id),admin,db)
        assert first['idempotent'] is False
        second=link_procurement_po(proj.id,c.id,ProcurementLinkIn(purchase_order_id=po.id),admin,db)
        assert second['idempotent'] is True
        assert db.query(ContractProcurementLink).count()==1
        assert po.status=='Issued'
