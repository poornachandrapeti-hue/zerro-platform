"""HTTP regression: a terminal Stores QA revocation cannot be reauthorized by Quality handoff."""

from decimal import Decimal

from tests.conftest import sign_in
from tests.test_quality import _posted_receipt, new_project
from app.domains.stores_inventory.models import StoresInspectionCase
from app.domains.identity_projects.models import User


def test_revoked_stores_case_cannot_be_reconciled_again(env):
    client, maker = env
    sign_in(client)
    me = client.get("/api/auth/me").json()["user"]
    catalog = client.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    created = new_project(
        client,
        code="QA-REVOKE-1",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]

    with maker() as db:
        _receipt_id, line_id, _item_id = _posted_receipt(
            db, pid, me["id"], me["company_id"], civil, "GR-QA-REVOKE", "10"
        )
        org_id = db.get(User, me["id"]).organization_id
        case = StoresInspectionCase(
            organization_id=org_id,
            project_id=pid,
            goods_receipt_line_id=line_id,
            pending_qty=Decimal("0"),
            accepted_qty=Decimal("6"),
            rejected_qty=Decimal("3"),
            quarantined_qty=Decimal("1"),
            status="Quality Revoked",
            version=2,
            created_by=me["id"],
        )
        db.add(case)
        db.commit()
        case_id = case.id

    url = f"/api/projects/{pid}/stores/inspection-cases/from-quality/{line_id}/reconcile"
    response = client.post(url, params={"expected_version": 2})
    assert response.status_code == 409, response.text
    assert "Revoked QA case" in response.text

    with maker() as db:
        saved = db.get(StoresInspectionCase, case_id)
        assert saved.status == "Quality Revoked"
        assert saved.version == 2
        assert Decimal(saved.accepted_qty) == Decimal("6")
        assert Decimal(saved.rejected_qty) == Decimal("3")
        assert Decimal(saved.quarantined_qty) == Decimal("1")
