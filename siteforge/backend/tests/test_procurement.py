from io import BytesIO

from openpyxl import Workbook

from .test_engineering import _file, _ids, _member, _user, sign_in
from .test_phase2 import complete


def _book(rows):
    book = Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _decide(c, review, action, reason=""):
    response = c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": action, "reason": reason, "version": review["version"]},
    )
    return response


def test_requirements_follow_approval_and_keep_commercial_data_private(env, tmp_path):
    from app.config import settings

    settings.file_root = str(tmp_path)
    c, _maker = env
    sign_in(c)
    roles, disciplines, me = _ids(c)
    electrical = disciplines["Electrical"]
    project = complete(c, code="BUY-1", discipline_ids=[electrical])
    pid = project["id"]
    company_id = me["company_id"]
    site = _user(c, "site.buy@alpha.test", "Site Buy", company_id)
    head = _user(c, "head.buy@alpha.test", "Head Buy", company_id)
    buyer = _user(c, "buyer.buy@alpha.test", "Buyer", company_id)
    manager = _user(c, "manager.buy@alpha.test", "Buyer Manager", company_id)
    commercial = _user(c, "commercial.buy@alpha.test", "Commercial", company_id)
    outsider = _user(c, "outsider.buy@alpha.test", "Outsider", company_id)
    _member(c, pid, site, roles["Site Engineer"], company_id, [electrical])
    _member(c, pid, head, roles["Discipline Head"], company_id, [electrical])
    _member(c, pid, buyer, roles["Procurement Officer"], company_id, [])
    _member(c, pid, manager, roles["Procurement Manager"], company_id, [])
    _member(c, pid, commercial, roles["Commercial Manager"], company_id, [])
    sign_in(c, "viewer@alpha.test")
    assert c.get(f"/api/projects/{pid}/procurement/dashboard").status_code == 403
    sign_in(c)
    denied_policy = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "procurement.requirement",
            "discipline_id": electrical,
            "stages": [{"name": "Discipline", "rule": "all", "reviewer_ids": [outsider]}],
        },
    )
    assert denied_policy.status_code == 422
    policy = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "procurement.requirement",
            "discipline_id": electrical,
            "stages": [{"name": "Discipline", "rule": "all", "reviewer_ids": [head]}],
        },
    )
    assert policy.status_code == 201, policy.text
    purchase_policy = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "procurement.requisition",
            "discipline_id": electrical,
            "stages": [
                {
                    "name": "Procurement",
                    "rule": "all",
                    "reviewers": [{"user_id": manager, "approval_limit": 100}],
                }
            ],
        },
    )
    assert purchase_policy.status_code == 201, purchase_policy.text
    item = c.post(
        "/api/procurement/items",
        json={
            "code": "CABLE-1",
            "description": "Power cable",
            "item_type": "Material",
            "category": "Cable",
            "discipline_ids": [electrical],
            "base_unit": "m",
            "inspection_required": True,
        },
    )
    assert item.status_code == 201, item.text
    item_id = item.json()["id"]
    drawing = c.post(
        f"/api/projects/{pid}/drawings",
        json={
            "number": "E-BUY",
            "title": "Cable route",
            "discipline_id": electrical,
            "company_id": company_id,
            "responsible_user_id": head,
        },
    )
    assert drawing.status_code == 201, drawing.text
    filed = _file(c, pid, drawing.json()["id"], "A")
    revision_id = next(row["id"] for row in filed["revisions"] if row["code"] == "A")
    sign_in(c, "site.buy@alpha.test")
    missing = c.post(
        f"/api/projects/{pid}/procurement/requirements",
        json={
            "number": "MR-1",
            "company_id": company_id,
            "discipline_id": electrical,
            "requested_by": site,
            "required_date": "2026-12-01",
            "priority": "High",
            "purpose": "Cable pull",
            "drawing_id": drawing.json()["id"],
            "drawing_revision_id": revision_id,
            "lines": [
                {
                    "item_id": item_id,
                    "quantity": "10",
                    "unit": "m",
                    "required_date": "2026-12-01",
                    "tag": "CB-1",
                }
            ],
        },
    )
    assert missing.status_code == 201, missing.text
    requirement = missing.json()
    assert requirement["fulfillment"] == "Not allocated"
    blocked = c.post(
        f"/api/projects/{pid}/procurement/requirements/{requirement['id']}/submit",
        json={"version": requirement["version"]},
    )
    assert blocked.status_code == 201, blocked.text
    review = blocked.json()["review"]
    assert review["subject"] == "Review requirement MR-1"
    own = _decide(c, review, "approve")
    assert own.status_code == 403
    sign_in(c, "head.buy@alpha.test")
    returned = _decide(c, review, "return", "Confirm the route")
    assert returned.status_code == 200, returned.text
    sign_in(c, "site.buy@alpha.test")
    current = c.get(f"/api/projects/{pid}/procurement/requirements/{requirement['id']}").json()
    assert current["status"] == "Returned for Correction"
    edited = c.put(
        f"/api/projects/{pid}/procurement/requirements/{requirement['id']}",
        json={
            "number": "MR-1",
            "company_id": company_id,
            "discipline_id": electrical,
            "requested_by": site,
            "required_date": "2026-12-01",
            "priority": "High",
            "purpose": "Cable pull",
            "drawing_id": drawing.json()["id"],
            "drawing_revision_id": revision_id,
            "version": current["version"],
            "lines": [
                {
                    "id": current["lines"][0]["id"],
                    "item_id": item_id,
                    "quantity": "10",
                    "unit": "m",
                    "required_date": "2026-12-01",
                    "tag": "CB-1",
                }
            ],
        },
    )
    assert edited.status_code == 200, edited.text
    again = c.post(
        f"/api/projects/{pid}/procurement/requirements/{requirement['id']}/resubmit",
        json={"version": edited.json()["version"], "review_version": edited.json()["review"]["version"]},
    )
    assert again.status_code == 200, again.text
    sign_in(c, "head.buy@alpha.test")
    approved = _decide(c, again.json()["review"], "approve")
    assert approved.status_code == 200, approved.text
    stored = c.get(f"/api/projects/{pid}/procurement/requirements/{requirement['id']}").json()
    assert stored["status"] == "Approved"
    assert stored["lines"][0]["quantity"] == "10.000"
    revision = next(row for row in c.get(f"/api/projects/{pid}/drawings/{drawing.json()['id']}").json()["revisions"] if row["code"] == "A")
    withdrawn = c.post(
        f"/api/projects/{pid}/drawings/{drawing.json()['id']}/revisions/{revision_id}/withdraw",
        json={"version": revision["version"], "reason": "Route changed"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    impacted = c.get(f"/api/projects/{pid}/procurement/requirements/{requirement['id']}").json()
    assert impacted["impact_state"] == "Review required"
    assert impacted["lines"][0]["quantity"] == "10.000"
    assert impacted["status"] == "Approved"
    sign_in(c, "buyer.buy@alpha.test")
    early = c.post(
        f"/api/projects/{pid}/procurement/requisitions",
        json={
            "number": "PR-1",
            "request_date": "2026-10-07",
            "required_delivery": "2026-12-01",
            "justification": "Buy the cable",
            "lines": [{"requirement_line_id": impacted["lines"][0]["id"], "quantity": "4"}],
        },
    )
    assert early.status_code == 422
    sign_in(c, "head.buy@alpha.test")
    cleared = c.post(
        f"/api/projects/{pid}/procurement/requirements/{requirement['id']}/impact",
        json={"decision": "Specification unchanged", "affected_quantity": "10", "version": impacted["version"]},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["impact_state"] == "Reviewed"
    sign_in(c, "buyer.buy@alpha.test")
    too_much = c.post(
        f"/api/projects/{pid}/procurement/requisitions",
        json={
            "number": "PR-1",
            "request_date": "2026-10-07",
            "required_delivery": "2026-12-01",
            "justification": "Buy the cable",
            "lines": [{"requirement_line_id": impacted["lines"][0]["id"], "quantity": "11"}],
        },
    )
    assert too_much.status_code == 422
    priced = c.post(
        f"/api/projects/{pid}/procurement/requisitions",
        json={
            "number": "PR-1",
            "request_date": "2026-10-07",
            "required_delivery": "2026-12-01",
            "justification": "Buy the cable",
            "currency": "INR",
            "lines": [
                {
                    "requirement_line_id": impacted["lines"][0]["id"],
                    "quantity": "4",
                    "estimated_price": "50",
                }
            ],
        },
    )
    assert priced.status_code == 403
    created = c.post(
        f"/api/projects/{pid}/procurement/requisitions",
        json={
            "number": "PR-1",
            "request_date": "2026-10-07",
            "required_delivery": "2026-12-01",
            "justification": "Buy the cable",
            "lines": [{"requirement_line_id": impacted["lines"][0]["id"], "quantity": "4"}],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["ordering"] == "Not Ordered"
    assert created.json()["lines"][0]["estimated_price"] is None
    overlap = c.post(
        f"/api/projects/{pid}/procurement/requisitions",
        json={
            "number": "PR-2",
            "request_date": "2026-10-07",
            "required_delivery": "2026-12-01",
            "justification": "Buy the rest",
            "lines": [{"requirement_line_id": impacted["lines"][0]["id"], "quantity": "7"}],
        },
    )
    assert overlap.status_code == 422
    sign_in(c, "manager.buy@alpha.test")
    commercial_pr = c.post(
        f"/api/projects/{pid}/procurement/requisitions",
        json={
            "number": "PR-2",
            "request_date": "2026-10-07",
            "required_delivery": "2026-12-01",
            "justification": "Priced balance",
            "currency": "INR",
            "lines": [
                {
                    "requirement_line_id": impacted["lines"][0]["id"],
                    "quantity": "6",
                    "estimated_price": "80",
                }
            ],
        },
    )
    assert commercial_pr.status_code == 201, commercial_pr.text
    assert commercial_pr.json()["lines"][0]["estimated_price"] == "80.00"
    submitted = c.post(
        f"/api/projects/{pid}/procurement/requisitions/{commercial_pr.json()['id']}/submit",
        json={"version": commercial_pr.json()["version"]},
    )
    assert submitted.status_code == 201, submitted.text
    over_limit = _decide(c, submitted.json()["review"], "approve")
    assert over_limit.status_code == 403
    sign_in(c, "site.buy@alpha.test")
    hidden = c.get(
        f"/api/projects/{pid}/procurement/requisitions/{commercial_pr.json()['id']}"
    ).json()
    assert hidden["lines"][0]["estimated_price"] is None
    assert hidden["currency"] == ""
    sign_in(c, "commercial.buy@alpha.test")
    visible = c.get(
        f"/api/projects/{pid}/procurement/requisitions/{commercial_pr.json()['id']}"
    ).json()
    assert visible["lines"][0]["estimated_price"] == "80.00"
    stock = c.post(f"/api/projects/{pid}/procurement/requirements/{requirement['id']}/stock")
    assert stock.status_code == 403
    sign_in(c, "site.buy@alpha.test")
    stock = c.post(f"/api/projects/{pid}/procurement/requirements/{requirement['id']}/stock")
    assert stock.status_code == 409
    assert "purchase requisition" in stock.json()["detail"]
    board = c.get(f"/api/projects/{pid}/procurement/dashboard").json()
    assert board["open_requirements"] == 0
    assert board["requisitions_pending"] == 1
    assert any(row["name"] == "Invoice matching and payment" for row in board["unavailable"])
    assert all(row["name"] != "Vendor invoices" for row in board["unavailable"])
    assert all(row["name"] != "Stock, issues, and returns" for row in board["unavailable"])
    assert all(row["name"] != "Delivery and goods receipt" for row in board["unavailable"])
    assert all(row["name"] != "Purchase orders" for row in board["unavailable"])
    workbook = _book(
        [
            ["code", "description", "type", "category", "disciplines", "unit"],
            ["CABLE-1", "Duplicate", "Material", "Cable", "Electrical", "m"],
        ]
    )
    sign_in(c)
    preview = c.post(
        "/api/procurement/items/import?mode=preview",
        files={"upload": ("items.xlsx", workbook, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["errors"]
    assert preview.json()["saved"] == 0
    assert c.get("/api/procurement/items").json()[0]["description"] == "Power cable"


def test_saved_reviewer_opens_procurement_without_the_role(env):
    c, _maker = env
    sign_in(c)
    roles, disciplines, me = _ids(c)
    electrical = disciplines["Electrical"]
    project = complete(c, code="BUY-2", discipline_ids=[electrical])
    pid = project["id"]
    company_id = me["company_id"]
    engineer = _user(c, "eng.buy@alpha.test", "Eng Buy", company_id)
    _member(c, pid, engineer, roles["Engineering Engineer"], company_id, [electrical])
    sign_in(c, "eng.buy@alpha.test")
    assert c.get(f"/api/projects/{pid}/procurement/dashboard").status_code == 403
    sign_in(c)
    item = c.post(
        "/api/procurement/items",
        json={
            "code": "VALVE-2",
            "description": "Gate valve",
            "item_type": "Material",
            "category": "Valve",
            "discipline_ids": [electrical],
            "base_unit": "nos",
            "inspection_required": False,
        },
    )
    assert item.status_code == 201, item.text
    for record_type in ("procurement.requirement", "procurement.requisition"):
        saved = c.post(
            f"/api/projects/{pid}/approval-policies",
            json={
                "record_type": record_type,
                "discipline_id": electrical,
                "stages": [{"name": "Review", "rule": "all", "reviewer_ids": [engineer]}],
            },
        )
        assert saved.status_code == 201, saved.text
    requirement = c.post(
        f"/api/projects/{pid}/procurement/requirements",
        json={
            "number": "MR-ENG",
            "company_id": company_id,
            "discipline_id": electrical,
            "requested_by": me["id"],
            "required_date": "2026-12-01",
            "priority": "Normal",
            "purpose": "Valve",
            "lines": [
                {
                    "item_id": item.json()["id"],
                    "quantity": "2",
                    "unit": "nos",
                    "required_date": "2026-12-01",
                    "tag": "V-1",
                }
            ],
        },
    )
    assert requirement.status_code == 201, requirement.text
    submitted = c.post(
        f"/api/projects/{pid}/procurement/requirements/{requirement.json()['id']}/submit",
        json={"version": requirement.json()["version"]},
    )
    assert submitted.status_code == 201, submitted.text
    sign_in(c, "eng.buy@alpha.test")
    decided = _decide(c, submitted.json()["review"], "approve")
    assert decided.status_code == 200, decided.text
    sign_in(c)
    created = c.post(
        f"/api/projects/{pid}/procurement/requisitions",
        json={
            "number": "PR-ENG",
            "request_date": "2026-10-07",
            "required_delivery": "2026-12-01",
            "justification": "Need the valve",
            "lines": [{"requirement_line_id": requirement.json()["lines"][0]["id"], "quantity": "1"}],
        },
    )
    assert created.status_code == 201, created.text
    waiting = c.post(
        f"/api/projects/{pid}/procurement/requisitions/{created.json()['id']}/submit",
        json={"version": created.json()["version"]},
    )
    assert waiting.status_code == 201, waiting.text
    sign_in(c, "eng.buy@alpha.test")
    session = c.get("/api/auth/me")
    assert session.status_code == 200, session.text
    membership = next(row for row in session.json()["memberships"] if row["project_id"] == pid)
    assert "procurement.view" in membership["permissions"]
    assert c.get(f"/api/projects/{pid}/procurement/dashboard").status_code == 200
    opened = c.get(f"/api/projects/{pid}/procurement/requisitions/{created.json()['id']}")
    assert opened.status_code == 200, opened.text
    assert set(opened.json()["review"]["actions"]) >= {"approve", "reject", "return"}
    blocked = c.post(
        "/api/procurement/items",
        json={
            "code": "NOPE",
            "description": "No",
            "item_type": "Material",
            "category": "Valve",
            "discipline_ids": [electrical],
            "base_unit": "nos",
            "inspection_required": False,
        },
    )
    assert blocked.status_code == 403


def test_rfq_keeps_technical_and_commercial_decisions_separate(env):
    c, _maker = env
    sign_in(c)
    roles, disciplines, me = _ids(c)
    electrical = disciplines["Electrical"]
    project = complete(c, code="RFQ-1", discipline_ids=[electrical])
    pid = project["id"]
    company_id = me["company_id"]
    head = _user(c, "head.rfq@alpha.test", "Head Rfq", company_id)
    commercial = _user(c, "commercial.rfq@alpha.test", "Commercial Rfq", company_id)
    _member(c, pid, head, roles["Discipline Head"], company_id, [electrical])
    _member(c, pid, commercial, roles["Commercial Manager"], company_id, [])
    for record_type, reviewer in (
        ("procurement.requirement", head),
        ("procurement.requisition", commercial),
    ):
        saved = c.post(
            f"/api/projects/{pid}/approval-policies",
            json={
                "record_type": record_type,
                "discipline_id": electrical,
                "stages": [{"name": "Review", "rule": "all", "reviewer_ids": [reviewer]}],
            },
        )
        assert saved.status_code == 201, saved.text
    item = c.post(
        "/api/procurement/items",
        json={
            "code": "CABLE-RFQ",
            "description": "Quote cable",
            "item_type": "Material",
            "category": "Cable",
            "discipline_ids": [electrical],
            "base_unit": "m",
            "inspection_required": False,
        },
    )
    assert item.status_code == 201, item.text
    requirement = c.post(
        f"/api/projects/{pid}/procurement/requirements",
        json={
            "number": "MR-RFQ",
            "company_id": company_id,
            "discipline_id": electrical,
            "requested_by": me["id"],
            "required_date": "2026-12-01",
            "priority": "Normal",
            "purpose": "Quote",
            "lines": [
                {
                    "item_id": item.json()["id"],
                    "quantity": "4",
                    "unit": "m",
                    "required_date": "2026-12-01",
                    "tag": "C-1",
                }
            ],
        },
    )
    assert requirement.status_code == 201, requirement.text
    submitted = c.post(
        f"/api/projects/{pid}/procurement/requirements/{requirement.json()['id']}/submit",
        json={"version": requirement.json()["version"]},
    )
    assert submitted.status_code == 201, submitted.text
    sign_in(c, "head.rfq@alpha.test")
    assert _decide(c, submitted.json()["review"], "approve").status_code == 200
    sign_in(c)
    created = c.post(
        f"/api/projects/{pid}/procurement/requisitions",
        json={
            "number": "PR-RFQ",
            "request_date": "2026-10-07",
            "required_delivery": "2026-12-01",
            "justification": "Need quotes",
            "lines": [{"requirement_line_id": requirement.json()["lines"][0]["id"], "quantity": "4"}],
        },
    )
    assert created.status_code == 201, created.text
    waiting = c.post(
        f"/api/projects/{pid}/procurement/requisitions/{created.json()['id']}/submit",
        json={"version": created.json()["version"]},
    )
    assert waiting.status_code == 201, waiting.text
    sign_in(c, "commercial.rfq@alpha.test")
    assert _decide(c, waiting.json()["review"], "approve").status_code == 200
    sign_in(c)
    vendors = []
    for code in ("LOW", "HIGH"):
        vendor = c.post(
            "/api/procurement/vendors",
            json={"code": code, "company_id": company_id, "approval_status": "Approved"},
        )
        assert vendor.status_code == 201, vendor.text
        vendors.append(vendor.json()["id"])
    line_id = created.json()["lines"][0]["id"]
    draft = c.post(
        f"/api/projects/{pid}/procurement/rfqs",
        json={
            "number": "RFQ-1",
            "requisition_id": created.json()["id"],
            "due_date": "2026-11-01",
            "delivery_location": "Site store",
            "technical_requirements": "Copper conductor",
            "commercial_requirements": "30 day terms",
            "vendor_ids": vendors,
            "lines": [{"requisition_line_id": line_id, "quantity": "4"}],
        },
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["status"] == "Draft"
    assert draft.json()["technical_reviewers"][0]["name"] == "Head Rfq"
    issued = c.post(
        f"/api/projects/{pid}/procurement/rfqs/{draft.json()['id']}/issue",
        json={"version": draft.json()["version"]},
    )
    assert issued.status_code == 200, issued.text
    assert c.get(f"/api/projects/{pid}/procurement/dashboard").json()["rfqs_awaiting"] == 1
    sign_in(c, "head.rfq@alpha.test")
    hidden = c.post(
        f"/api/projects/{pid}/procurement/rfqs/{draft.json()['id']}/quotations",
        json={
            "vendor_id": vendors[0],
            "reference": "Q-LOW",
            "quotation_date": "2026-10-08",
            "validity_date": "2026-11-08",
            "currency": "INR",
            "lines": [{"rfq_line_id": issued.json()["lines"][0]["id"], "quantity": "4", "unit_price": "10"}],
            "version": issued.json()["version"],
        },
    )
    assert hidden.status_code == 403
    sign_in(c)
    current = issued.json()
    for vendor_id, reference, amount in ((vendors[0], "Q-LOW", "10"), (vendors[1], "Q-HIGH", "25")):
        quoted = c.post(
            f"/api/projects/{pid}/procurement/rfqs/{draft.json()['id']}/quotations",
            json={
                "vendor_id": vendor_id,
                "reference": reference,
                "quotation_date": "2026-10-08",
                "validity_date": "2026-11-08",
                "currency": "INR",
                "lines": [{"rfq_line_id": current["lines"][0]["id"], "quantity": "4", "unit_price": amount}],
                "version": current["version"],
            },
        )
        assert quoted.status_code == 201, quoted.text
        current = quoted.json()
    started = c.post(
        f"/api/projects/{pid}/procurement/rfqs/{draft.json()['id']}/technical-review",
        json={"version": current["version"]},
    )
    assert started.status_code == 200, started.text
    sign_in(c, "head.rfq@alpha.test")
    notes = c.get("/api/notifications")
    assert notes.status_code == 200, notes.text
    assert any(
        note["title"] == "Your technical review is required" and "RFQ-1" in note["body"]
        for note in notes.json()
    )
    opened = c.get(f"/api/projects/{pid}/procurement/rfqs/{draft.json()['id']}")
    assert opened.json()["prices_visible"] is False
    assert opened.json()["quotations"][0]["lines"][0]["unit_price"] is None
    technical = opened.json()
    low, high = technical["quotations"]
    rejected = c.post(
        f"/api/projects/{pid}/procurement/rfqs/{draft.json()['id']}/technical",
        json={"quotation_id": low["id"], "decision": "Not compliant", "reason": "Wrong conductor", "version": technical["version"]},
    )
    assert rejected.status_code == 200, rejected.text
    accepted = c.post(
        f"/api/projects/{pid}/procurement/rfqs/{draft.json()['id']}/technical",
        json={"quotation_id": high["id"], "decision": "Compliant", "reason": "", "version": rejected.json()["version"]},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "Commercial comparison"
    sign_in(c)
    compared = c.post(
        f"/api/projects/{pid}/procurement/rfqs/{draft.json()['id']}/commercial",
        json={
            "comparison_currency": "INR",
            "rate_date": "2026-10-09",
            "notes": [{"quotation_id": high["id"], "commercial_note": "Higher price, compliant", "conversion_rate": "1"}],
            "version": accepted.json()["version"],
        },
    )
    assert compared.status_code == 200, compared.text
    high_line = next(row for row in compared.json()["quotations"] if row["id"] == high["id"])["lines"][0]["id"]
    awarded = c.post(
        f"/api/projects/{pid}/procurement/rfqs/{draft.json()['id']}/award",
        json={
            "reason": "Compliant offer, not the lowest price",
            "lines": [{"quotation_line_id": high_line, "quantity": "4"}],
            "version": compared.json()["version"],
        },
    )
    assert awarded.status_code == 200, awarded.text
    assert awarded.json()["status"] == "Awarded"
    assert [step["status"] for step in awarded.json()["steps"]] == ["done", "done", "done", "done", "done"]
    assert awarded.json()["awards"][0]["vendor"] == "HIGH"
    stored = c.get(f"/api/projects/{pid}/procurement/requisitions/{created.json()['id']}").json()
    assert stored["ordering"] == "Not Ordered"
    route = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "procurement.purchase_order",
            "discipline_id": electrical,
            "allow_self_approval": False,
            "stages": [{"name": "Order approval", "rule": "all", "reviewer_ids": [commercial]}],
        },
    )
    assert route.status_code == 201, route.text
    offers = c.get(f"/api/projects/{pid}/procurement/order-sources")
    assert offers.status_code == 200, offers.text
    award_line = offers.json()[0]["lines"][0]
    too_much = c.post(
        f"/api/projects/{pid}/procurement/orders",
        json={
            "number": "PO-RFQ",
            "promised_date": "2026-12-01",
            "delivery_location": "Site store",
            "terms": "30 days",
            "lines": [{"award_id": award_line["award_id"], "quantity": "5"}],
        },
    )
    assert too_much.status_code == 422, too_much.text
    draft_order = c.post(
        f"/api/projects/{pid}/procurement/orders",
        json={
            "number": "PO-RFQ",
            "promised_date": "2026-12-01",
            "delivery_location": "Site store",
            "terms": "30 days",
            "lines": [{"award_id": award_line["award_id"], "quantity": "4"}],
        },
    )
    assert draft_order.status_code == 201, draft_order.text
    assert draft_order.json()["status"] == "Draft"
    sign_in(c, "head.rfq@alpha.test")
    hidden_order = c.get(f"/api/projects/{pid}/procurement/orders/{draft_order.json()['id']}")
    assert hidden_order.json()["lines"][0]["unit_price"] is None
    sign_in(c)
    early = c.post(
        f"/api/projects/{pid}/procurement/orders/{draft_order.json()['id']}/issue",
        json={"version": draft_order.json()["version"]},
    )
    assert early.status_code == 409
    submitted_order = c.post(
        f"/api/projects/{pid}/procurement/orders/{draft_order.json()['id']}/submit",
        json={"version": draft_order.json()["version"]},
    )
    assert submitted_order.status_code == 201, submitted_order.text
    own = _decide(c, submitted_order.json()["review"], "approve")
    assert own.status_code == 403
    sign_in(c, "commercial.rfq@alpha.test")
    notes = c.get("/api/notifications")
    assert any("PO-RFQ" in note["body"] or "PO-RFQ" in note["title"] for note in notes.json())
    approved_order = _decide(c, submitted_order.json()["review"], "approve")
    assert approved_order.status_code == 200, approved_order.text
    sign_in(c)
    ready = c.get(f"/api/projects/{pid}/procurement/orders/{draft_order.json()['id']}").json()
    assert ready["status"] == "Approved"
    issued = c.post(
        f"/api/projects/{pid}/procurement/orders/{draft_order.json()['id']}/issue",
        json={"version": ready["version"]},
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == "Issued"
    ordered = c.get(f"/api/projects/{pid}/procurement/requisitions/{created.json()['id']}").json()
    assert ordered["ordering"] == "Fully Ordered"
    locked = c.put(
        f"/api/projects/{pid}/procurement/orders/{draft_order.json()['id']}",
        json={
            "number": "PO-RFQ",
            "promised_date": "2026-12-01",
            "lines": [{"award_id": award_line["award_id"], "quantity": "4"}],
            "version": issued.json()["version"],
        },
    )
    assert locked.status_code == 409
    acknowledged = c.post(
        f"/api/projects/{pid}/procurement/orders/{draft_order.json()['id']}/acknowledge",
        json={"note": "Vendor accepted", "version": issued.json()["version"]},
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["status"] == "Acknowledged"
    assert [step["status"] for step in acknowledged.json()["steps"]] == ["done", "done", "done", "done", "done", "waiting", "waiting", "waiting"]
    amendment = c.post(
        f"/api/projects/{pid}/procurement/orders/{draft_order.json()['id']}/amendments",
        json={
            "number": "PO-RFQ-A1",
            "promised_date": "2026-12-15",
            "terms": "30 days",
            "reason": "Buy less",
            "lines": [{"award_id": award_line["award_id"], "quantity": "2"}],
        },
    )
    assert amendment.status_code == 201, amendment.text
    amendment_submit = c.post(
        f"/api/projects/{pid}/procurement/orders/{amendment.json()['id']}/submit",
        json={"version": amendment.json()["version"]},
    )
    assert amendment_submit.status_code == 201, amendment_submit.text
    sign_in(c, "commercial.rfq@alpha.test")
    amendment_ok = _decide(c, amendment_submit.json()["review"], "approve")
    assert amendment_ok.status_code == 200, amendment_ok.text
    sign_in(c)
    amendment_ready = c.get(f"/api/projects/{pid}/procurement/orders/{amendment.json()['id']}").json()
    amendment_issue = c.post(
        f"/api/projects/{pid}/procurement/orders/{amendment.json()['id']}/issue",
        json={"version": amendment_ready["version"]},
    )
    assert amendment_issue.status_code == 200, amendment_issue.text
    assert amendment_issue.json()["status"] == "Issued"
    original = c.get(f"/api/projects/{pid}/procurement/orders/{draft_order.json()['id']}").json()
    assert original["status"] == "Superseded"
    revised = c.get(f"/api/projects/{pid}/procurement/requisitions/{created.json()['id']}").json()
    assert revised["ordering"] == "Partially Ordered"
    line_id = amendment_issue.json()["lines"][0]["id"]
    sign_in(c, "commercial.rfq@alpha.test")
    denied = c.post(
        f"/api/projects/{pid}/procurement/receipts",
        json={
            "number": "GR-RFQ",
            "purchase_order_id": amendment.json()["id"],
            "receipt_date": "2026-12-02",
            "delivery_note": "DN-1",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "1"}],
        },
    )
    assert denied.status_code == 403, denied.text
    sign_in(c)
    against_old = c.post(
        f"/api/projects/{pid}/procurement/receipts",
        json={
            "number": "GR-OLD",
            "purchase_order_id": draft_order.json()["id"],
            "receipt_date": "2026-12-02",
            "lines": [{"purchase_order_line_id": issued.json()["lines"][0]["id"], "quantity": "1"}],
        },
    )
    assert against_old.status_code == 409, against_old.text
    too_much = c.post(
        f"/api/projects/{pid}/procurement/receipts",
        json={
            "number": "GR-RFQ",
            "purchase_order_id": amendment.json()["id"],
            "receipt_date": "2026-12-02",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "3"}],
        },
    )
    assert too_much.status_code == 422, too_much.text
    partial = c.post(
        f"/api/projects/{pid}/procurement/receipts",
        json={
            "number": "GR-RFQ",
            "purchase_order_id": amendment.json()["id"],
            "receipt_date": "2026-12-02",
            "delivery_note": "DN-1",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "1"}],
        },
    )
    assert partial.status_code == 201, partial.text
    assert partial.json()["status"] == "Posted"
    partial_order = c.get(f"/api/projects/{pid}/procurement/orders/{amendment.json()['id']}").json()
    assert partial_order["status"] == "Partially Received"
    assert partial_order["lines"][0]["received"] == "1.000"
    assert partial_order["lines"][0]["remaining"] == "1.000"
    assert next(step["status"] for step in partial_order["steps"] if step["name"] == "Partially Received") == "current"
    cancelled = c.post(
        f"/api/projects/{pid}/procurement/receipts/{partial.json()['id']}/cancel",
        json={"reason": "Counted twice", "version": partial.json()["version"]},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "Cancelled"
    restored = c.get(f"/api/projects/{pid}/procurement/orders/{amendment.json()['id']}").json()
    assert restored["status"] == "Issued"
    second = c.post(
        f"/api/projects/{pid}/procurement/receipts",
        json={
            "number": "GR-RFQ-2",
            "purchase_order_id": amendment.json()["id"],
            "receipt_date": "2026-12-03",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "1"}],
        },
    )
    assert second.status_code == 201, second.text
    finished = c.post(
        f"/api/projects/{pid}/procurement/receipts",
        json={
            "number": "GR-RFQ-3",
            "purchase_order_id": amendment.json()["id"],
            "receipt_date": "2026-12-04",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "1"}],
        },
    )
    assert finished.status_code == 201, finished.text
    received = c.get(f"/api/projects/{pid}/procurement/orders/{amendment.json()['id']}").json()
    assert received["status"] == "Received"
    assert next(step["status"] for step in received["steps"] if step["name"] == "Received") == "done"
    assert next(step["status"] for step in received["steps"] if step["name"] == "Closed") == "waiting"
    extra = c.post(
        f"/api/projects/{pid}/procurement/receipts",
        json={
            "number": "GR-RFQ-4",
            "purchase_order_id": amendment.json()["id"],
            "receipt_date": "2026-12-05",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "1"}],
        },
    )
    assert extra.status_code == 409, extra.text
    blocked = c.post(
        f"/api/projects/{pid}/procurement/orders/{amendment.json()['id']}/amendments",
        json={
            "number": "PO-RFQ-A2",
            "promised_date": "2026-12-20",
            "reason": "Too late",
            "lines": [{"award_id": award_line["award_id"], "quantity": "1"}],
        },
    )
    assert blocked.status_code == 409, blocked.text
    closed = c.post(
        f"/api/projects/{pid}/procurement/orders/{amendment.json()['id']}/close",
        json={"reason": "Delivery complete", "version": received["version"]},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "Closed"
    assert [step["status"] for step in closed.json()["steps"]] == ["done"] * 8
    still_ordered = c.get(f"/api/projects/{pid}/procurement/requisitions/{created.json()['id']}").json()
    assert still_ordered["ordering"] == "Partially Ordered"
    board = c.get(f"/api/projects/{pid}/procurement/dashboard").json()
    assert all(row["name"] != "Delivery and goods receipt" for row in board["unavailable"])
    assert all(row["name"] != "Stock, issues, and returns" for row in board["unavailable"])
    assert any(row["name"] == "Invoice matching and payment" for row in board["unavailable"])
    assert all(row["name"] != "Vendor invoices" for row in board["unavailable"])
    warehouse = c.post(
        f"/api/projects/{pid}/procurement/warehouses",
        json={"code": "WH-RFQ", "name": "Site store", "officer_id": me["id"]},
    )
    assert warehouse.status_code == 201, warehouse.text
    receipt_line = second.json()["lines"][0]["id"]
    sign_in(c, "commercial.rfq@alpha.test")
    denied_stock = c.post(
        f"/api/projects/{pid}/procurement/stock/acceptances",
        json={
            "number": "ACC-RFQ",
            "warehouse_id": warehouse.json()["id"],
            "goods_receipt_id": second.json()["id"],
            "lines": [{"goods_receipt_line_id": receipt_line, "quantity": "1"}],
        },
    )
    assert denied_stock.status_code == 403, denied_stock.text
    sign_in(c)
    too_accepted = c.post(
        f"/api/projects/{pid}/procurement/stock/acceptances",
        json={
            "number": "ACC-RFQ",
            "warehouse_id": warehouse.json()["id"],
            "goods_receipt_id": second.json()["id"],
            "lines": [{"goods_receipt_line_id": receipt_line, "quantity": "2"}],
        },
    )
    assert too_accepted.status_code == 422, too_accepted.text
    qa = _user(c, "qa.rfq@alpha.test", "Qa Rfq", company_id)
    _member(c, pid, qa, roles["QA/QC"], company_id, [electrical])
    material_policy = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "quality.material",
            "company_id": None,
            "discipline_id": electrical,
            "allow_self_approval": False,
            "stages": [
                {
                    "name": "Inspection",
                    "rule": "all",
                    "quorum_count": 1,
                    "reviewer_ids": [commercial],
                    "reviewers": [],
                    "purpose": "Accept the received quantity",
                }
            ],
        },
    )
    assert material_policy.status_code == 201, material_policy.text
    sign_in(c, "qa.rfq@alpha.test")
    inspection = c.post(
        f"/api/projects/{pid}/quality/materials",
        json={
            "number": "MI-RFQ",
            "goods_receipt_id": second.json()["id"],
            "inspector_id": qa,
            "requested_on": "2026-12-02",
            "certificate_reference": "MTC-1",
            "findings": "Quantity matches the delivery note",
            "lines": [
                {
                    "goods_receipt_line_id": receipt_line,
                    "from_state": "Pending",
                    "to_state": "Accepted",
                    "quantity": "1",
                }
            ],
        },
    )
    assert inspection.status_code == 201, inspection.text
    sent_material = c.post(
        f"/api/projects/{pid}/quality/materials/{inspection.json()['id']}/submit",
        json={"version": inspection.json()["version"]},
    )
    assert sent_material.status_code == 200, sent_material.text
    sign_in(c, "commercial.rfq@alpha.test")
    decided_material = _decide(c, sent_material.json()["review"], "approve")
    assert decided_material.status_code == 200, decided_material.text
    sign_in(c)
    accepted = c.post(
        f"/api/projects/{pid}/procurement/stock/acceptances",
        json={
            "number": "ACC-RFQ",
            "warehouse_id": warehouse.json()["id"],
            "goods_receipt_id": second.json()["id"],
            "lines": [{"goods_receipt_line_id": receipt_line, "quantity": "1"}],
        },
    )
    assert accepted.status_code == 201, accepted.text
    held = c.get(f"/api/projects/{pid}/procurement/stock").json()
    assert held[0]["on_hand"] == "1.000"
    assert held[0]["available"] == "1.000"
    reserved = c.post(
        f"/api/projects/{pid}/procurement/stock/reservations",
        json={
            "number": "RSV-RFQ",
            "warehouse_id": warehouse.json()["id"],
            "reason": "Hold for install",
            "lines": [{"item_id": held[0]["item_id"], "quantity": "1"}],
        },
    )
    assert reserved.status_code == 201, reserved.text
    blocked_issue = c.post(
        f"/api/projects/{pid}/procurement/stock/issues",
        json={
            "number": "ISS-RFQ",
            "warehouse_id": warehouse.json()["id"],
            "recipient": "Site crew",
            "reason": "Install",
            "lines": [{"item_id": held[0]["item_id"], "quantity": "1"}],
        },
    )
    assert blocked_issue.status_code == 422, blocked_issue.text
    released = c.post(
        f"/api/projects/{pid}/procurement/stock/postings/{reserved.json()['id']}/cancel",
        json={"reason": "Install now", "version": reserved.json()["version"]},
    )
    assert released.status_code == 200, released.text
    issued_stock = c.post(
        f"/api/projects/{pid}/procurement/stock/issues",
        json={
            "number": "ISS-RFQ",
            "warehouse_id": warehouse.json()["id"],
            "recipient": "Site crew",
            "reason": "Install",
            "lines": [{"item_id": held[0]["item_id"], "quantity": "1"}],
        },
    )
    assert issued_stock.status_code == 201, issued_stock.text
    empty = c.get(f"/api/projects/{pid}/procurement/stock").json()
    assert empty[0]["on_hand"] == "0.000"
    assert empty[0]["issued"] == "1.000"
    returned = c.post(
        f"/api/projects/{pid}/procurement/stock/returns",
        json={
            "number": "RET-RFQ",
            "issue_id": issued_stock.json()["id"],
            "reason": "Not used",
            "lines": [{"source_line_id": issued_stock.json()["lines"][0]["id"], "quantity": "1"}],
        },
    )
    assert returned.status_code == 201, returned.text
    back = c.get(f"/api/projects/{pid}/procurement/stock").json()
    assert back[0]["on_hand"] == "1.000"
    assert back[0]["returned"] == "1.000"
    assert c.get(f"/api/projects/{pid}/procurement/dashboard").json()["stock_on_hand"] == 1
    sign_in(c, "commercial.rfq@alpha.test")
    denied_invoice = c.post(
        f"/api/projects/{pid}/procurement/invoices",
        json={
            "number": "INV-RFQ",
            "purchase_order_id": amendment.json()["id"],
            "vendor_reference": "SUP-1",
            "invoice_date": "2026-12-06",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "2", "billed_unit_price": "9.50"}],
        },
    )
    assert denied_invoice.status_code == 403, denied_invoice.text
    sign_in(c)
    over_billed = c.post(
        f"/api/projects/{pid}/procurement/invoices",
        json={
            "number": "INV-RFQ",
            "purchase_order_id": amendment.json()["id"],
            "vendor_reference": "SUP-1",
            "invoice_date": "2026-12-06",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "3", "billed_unit_price": "9.50"}],
        },
    )
    assert over_billed.status_code == 422, over_billed.text
    draft_bill = c.post(
        f"/api/projects/{pid}/procurement/invoices",
        json={
            "number": "INV-RFQ",
            "purchase_order_id": amendment.json()["id"],
            "vendor_reference": "SUP-1",
            "invoice_date": "2026-12-06",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "2", "billed_unit_price": "9.50"}],
        },
    )
    assert draft_bill.status_code == 201, draft_bill.text
    assert draft_bill.json()["status"] == "Draft"
    assert draft_bill.json()["lines"][0]["billed_unit_price"] == "9.50"
    assert draft_bill.json()["lines"][0]["received"] == "2.000"
    assert draft_bill.json()["lines"][0]["order_unit_price"] != "9.50"
    assert "matched" not in draft_bill.json()
    second_bill = c.post(
        f"/api/projects/{pid}/procurement/invoices",
        json={
            "number": "INV-RFQ-2",
            "purchase_order_id": amendment.json()["id"],
            "vendor_reference": "SUP-2",
            "invoice_date": "2026-12-07",
            "lines": [{"purchase_order_line_id": line_id, "quantity": "2", "billed_unit_price": "9.50"}],
        },
    )
    assert second_bill.status_code == 201, second_bill.text
    revised = c.put(
        f"/api/projects/{pid}/procurement/invoices/{draft_bill.json()['id']}",
        json={
            "number": "INV-RFQ",
            "purchase_order_id": amendment.json()["id"],
            "vendor_reference": "SUP-1A",
            "invoice_date": "2026-12-06",
            "version": draft_bill.json()["version"],
            "lines": [{"purchase_order_line_id": line_id, "quantity": "2", "billed_unit_price": "9.50"}],
        },
    )
    assert revised.status_code == 200, revised.text
    recorded_bill = c.post(
        f"/api/projects/{pid}/procurement/invoices/{draft_bill.json()['id']}/record",
        json={"version": revised.json()["version"]},
    )
    assert recorded_bill.status_code == 200, recorded_bill.text
    assert recorded_bill.json()["status"] == "Recorded"
    assert recorded_bill.json()["vendor_reference"] == "SUP-1A"
    assert [step["status"] for step in recorded_bill.json()["steps"]] == ["done", "done"]
    blocked_bill = c.post(
        f"/api/projects/{pid}/procurement/invoices/{second_bill.json()['id']}/record",
        json={"version": second_bill.json()["version"]},
    )
    assert blocked_bill.status_code == 422, blocked_bill.text
    sign_in(c, "head.rfq@alpha.test")
    hidden_bill = c.get(f"/api/projects/{pid}/procurement/invoices/{draft_bill.json()['id']}").json()
    assert hidden_bill["lines"][0]["billed_unit_price"] is None
    assert hidden_bill["lines"][0]["order_unit_price"] is None
    assert hidden_bill["lines"][0]["received"] == "2.000"
    sign_in(c)
    billed_order = c.get(f"/api/projects/{pid}/procurement/orders/{amendment.json()['id']}").json()
    assert billed_order["status"] == "Closed"
    assert billed_order["invoices"][0]["number"] == "INV-RFQ"
    assert c.get(f"/api/projects/{pid}/procurement/dashboard").json()["stock_on_hand"] == 1
    cancelled_bill = c.post(
        f"/api/projects/{pid}/procurement/invoices/{draft_bill.json()['id']}/cancel",
        json={"reason": "Supplier reissued the bill", "version": recorded_bill.json()["version"]},
    )
    assert cancelled_bill.status_code == 200, cancelled_bill.text
    assert cancelled_bill.json()["status"] == "Cancelled"
    recorded_again = c.post(
        f"/api/projects/{pid}/procurement/invoices/{second_bill.json()['id']}/record",
        json={"version": second_bill.json()["version"]},
    )
    assert recorded_again.status_code == 200, recorded_again.text
    board = c.get(f"/api/projects/{pid}/procurement/dashboard").json()
    assert board["invoices_recorded"] == 1
    assert board["stock_on_hand"] == 1
    assert any(row["name"] == "Invoice matching and payment" for row in board["unavailable"])
    assert all(row["name"] != "Vendor invoices" for row in board["unavailable"])
