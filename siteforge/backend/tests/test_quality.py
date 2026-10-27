from app.domains.coordination.models import Notification

from .test_construction import _package, _progress_policy, _report
from .test_engineering import _user, sign_in
from .test_foundation import new_project


def _inspection_policy(discipline_id, reviewer_id):
    body = _progress_policy(discipline_id, reviewer_id)
    body["record_type"] = "quality.inspection"
    body["stages"][0]["name"] = "Inspection"
    body["stages"][0]["purpose"] = "Accept the verified quantity"
    return body


def _activity(c, pid, package_id, company_id, code, method, quantity):
    saved = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": package_id,
            "code": code,
            "name": code,
            "quantity": quantity,
            "unit": "m3",
            "company_id": company_id,
            "measurement_method": method,
            "predecessor_ids": [],
        },
    )
    assert saved.status_code == 201, saved.text
    return saved.json()


def test_inspection_accepts_verified_quantity_without_billing(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="QUAL-1",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area_id = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    ).json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    for user_id, role in ((uid, "Site Engineer"), (me["id"], "Project Manager")):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    outsider = _user(c, "outsider@alpha.test", "Outsider", me["company_id"])
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(civil, me["id"])).status_code == 201
    sign_in(c, "viewer@alpha.test")
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-Q"),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    pour = _activity(c, pid, package_id, me["company_id"], "POUR", "Quantity", "12")
    other = _activity(c, pid, package_id, me["company_id"], "OTHER", "Quantity", "5")
    marks = _activity(c, pid, package_id, me["company_id"], "MARKS", "Weighted milestones", "1")
    closed = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-EARLY", "package_id": package_id},
    )
    assert closed.status_code == 409, closed.text
    assert "released work package" in closed.text
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, package_id)
        row.status = "In Progress"
        row.release_state = "Released"
        db.commit()
    draft = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-1", "package_id": package_id},
    )
    assert draft.status_code == 201, draft.text
    assert "does not certify" in draft.json()["statement"]
    missing = c.post(
        f"/api/projects/{pid}/quality/offers/{draft.json()['id']}/submit",
        json={"version": draft.json()["version"]},
    )
    assert missing.status_code == 422, missing.text
    assert "Mandatory reviewer" in missing.text
    sign_in(c)
    stranger = c.post(
        f"/api/projects/{pid}/approval-policies",
        json=_inspection_policy(civil, outsider),
    )
    assert stranger.status_code == 422, stranger.text
    assert "not an active member" in stranger.text
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_inspection_policy(civil, uid)).status_code == 201
    sign_in(c, "viewer@alpha.test")
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, package_id)
        row.status = "On Hold"
        db.commit()
    paused = c.post(
        f"/api/projects/{pid}/quality/offers/{draft.json()['id']}/submit",
        json={"version": draft.json()["version"]},
    )
    assert paused.status_code == 422, paused.text
    assert "Resume the work package" in paused.text
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, package_id)
        row.status = "In Progress"
        db.commit()
    cancelled = c.post(
        f"/api/projects/{pid}/quality/offers/{draft.json()['id']}/cancel",
        json={"reason": "Replaced after the hold", "version": draft.json()["version"]},
    )
    assert cancelled.status_code == 200, cancelled.text
    saved_marks = c.put(
        f"/api/projects/{pid}/construction/activities/{marks['id']}/milestones",
        json={"milestones": [{"name": "Complete", "weight": "100"}]},
    )
    assert saved_marks.status_code == 200, saved_marks.text
    milestone_id = saved_marks.json()["milestones"][0]["id"]
    report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-Q"),
    )
    assert report.status_code == 201, report.text
    first = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines",
        json={"activity_id": pour["id"], "quantity": "10"},
    )
    assert first.status_code == 201, first.text
    second = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines",
        json={"activity_id": other["id"], "quantity": "5"},
    )
    assert second.status_code == 201, second.text
    third = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines",
        json={"activity_id": marks["id"], "milestone_id": milestone_id, "evidence": "Milestone is complete"},
    )
    assert third.status_code == 201, third.text
    submitted = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/submit",
        json={"version": third.json()["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{submitted.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": submitted.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    offer = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-A", "package_id": package_id, "activity_id": pour["id"]},
    )
    assert offer.status_code == 201, offer.text
    sent = c.post(
        f"/api/projects/{pid}/quality/offers/{offer.json()['id']}/submit",
        json={"version": offer.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["payload"]["activities"][0]["verified_quantity"] == "10.000"
    assert sent.json()["package_status"] == "In Progress"
    sign_in(c)
    blocked_admin = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert blocked_admin.status_code == 403, blocked_admin.text
    sign_in(c, "viewer@alpha.test")
    own = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    assert "cannot approve your own" in own.text
    rejected = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "reject", "reason": "Hold the pour", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert rejected.status_code == 200, rejected.text
    board = c.get(f"/api/projects/{pid}/quality").json()
    refused = next(row for row in board["offers"] if row["number"] == "INSP-A")
    assert refused["status"] == "Rejected"
    assert refused["package_status"] == "In Progress"
    assert all(line["accepted_quantity"] is None for line in refused["lines"])
    again = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-A2", "package_id": package_id, "activity_id": pour["id"]},
    )
    assert again.status_code == 201, again.text
    again_sent = c.post(
        f"/api/projects/{pid}/quality/offers/{again.json()['id']}/submit",
        json={"version": again.json()["version"]},
    )
    assert again_sent.status_code == 200, again_sent.text
    sign_in(c)
    assert (
        c.post(
            f"/api/projects/{pid}/approval-policies",
            json=_inspection_policy(civil, me["id"]),
        ).status_code
        == 201
    )
    assert (
        c.post(
            f"/api/reviews/{again_sent.json()['review']['id']}/decisions",
            json={
                "action": "reject",
                "reason": "Use the saved quality reviewer",
                "comment": "",
                "version": again_sent.json()["review"]["version"],
            },
        ).status_code
        == 403
    )
    sign_in(c, "viewer@alpha.test")
    assert (
        c.post(
            f"/api/reviews/{again_sent.json()['review']['id']}/decisions",
            json={
                "action": "reject",
                "reason": "Offer it again to the quality reviewer",
                "comment": "",
                "version": again_sent.json()["review"]["version"],
            },
        ).status_code
        == 200
    )
    fresh = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-OK", "package_id": package_id, "activity_id": pour["id"]},
    )
    assert fresh.status_code == 201, fresh.text
    fresh_sent = c.post(
        f"/api/projects/{pid}/quality/offers/{fresh.json()['id']}/submit",
        json={"version": fresh.json()["version"]},
    )
    assert fresh_sent.status_code == 200, fresh_sent.text
    overlap = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-ALL", "package_id": package_id},
    )
    assert overlap.status_code == 409, overlap.text
    assert "open inspection offer" in overlap.text
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{fresh_sent.json()['review']['id']}/decisions",
            json={
                "action": "approve",
                "reason": "",
                "comment": "",
                "version": fresh_sent.json()["review"]["version"],
            },
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    accepted = c.get(f"/api/projects/{pid}/quality").json()
    package_row = next(row for row in accepted["packages"] if row["id"] == package_id)
    assert package_row["status"] == "In Progress"
    pour_row = next(row for row in package_row["activities"] if row["code"] == "POUR")
    other_row = next(row for row in package_row["activities"] if row["code"] == "OTHER")
    assert pour_row["accepted_quantity"] == "10.000"
    assert "does not certify" in pour_row["accepted_note"]
    assert other_row["accepted_quantity"] is None
    assert "does not accept" in other_row["accepted_note"]
    same = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-SAME", "package_id": package_id, "activity_id": pour["id"]},
    )
    assert same.status_code == 201, same.text
    same_sent = c.post(
        f"/api/projects/{pid}/quality/offers/{same.json()['id']}/submit",
        json={"version": same.json()["version"]},
    )
    assert same_sent.status_code == 422, same_sent.text
    assert "already has this verified quantity" in same_sent.text
    cleared = c.post(
        f"/api/projects/{pid}/quality/offers/{same.json()['id']}/cancel",
        json={"reason": "Quantity has not increased", "version": same.json()["version"]},
    )
    assert cleared.status_code == 200, cleared.text
    measured = c.get(f"/api/projects/{pid}/construction/progress").json()["activities"]
    pour_measure = next(row for row in measured if row["activity_id"] == pour["id"])
    assert pour_measure["accepted_quantity"] == "10.000"
    assert pour_measure["certified_quantity"] is None
    marks_offer = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-MS", "package_id": package_id, "activity_id": marks["id"]},
    )
    assert marks_offer.status_code == 201, marks_offer.text
    marks_sent = c.post(
        f"/api/projects/{pid}/quality/offers/{marks_offer.json()['id']}/submit",
        json={"version": marks_offer.json()["version"]},
    )
    assert marks_sent.status_code == 200, marks_sent.text
    assert marks_sent.json()["payload"]["activities"][0]["verified_percent"] == "100.00"
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{marks_sent.json()['review']['id']}/decisions",
            json={
                "action": "approve",
                "reason": "",
                "comment": "",
                "version": marks_sent.json()["review"]["version"],
            },
        ).status_code
        == 200
    )
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        assert db.get(WorkPackage, package_id).status == "In Progress"
        note = db.query(Notification).filter_by(title="Quantity accepted", project_id=pid).first()
        assert note is not None
        assert "commissioning" in note.body
    sign_in(c, "viewer@alpha.test")
    grown = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, uid, number="DPR-Q2"),
    )
    grown_line = c.post(
        f"/api/projects/{pid}/construction/progress/{grown.json()['id']}/lines",
        json={"activity_id": pour["id"], "quantity": "2"},
    )
    assert grown_line.status_code == 201, grown_line.text
    grown_sent = c.post(
        f"/api/projects/{pid}/construction/progress/{grown.json()['id']}/submit",
        json={"version": grown_line.json()["version"]},
    )
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{grown_sent.json()['review']['id']}/decisions",
            json={
                "action": "approve",
                "reason": "",
                "comment": "",
                "version": grown_sent.json()["review"]["version"],
            },
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    raised = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-MORE", "package_id": package_id, "activity_id": pour["id"]},
    )
    assert raised.status_code == 201, raised.text
    raised_sent = c.post(
        f"/api/projects/{pid}/quality/offers/{raised.json()['id']}/submit",
        json={"version": raised.json()["version"]},
    )
    assert raised_sent.status_code == 200, raised_sent.text
    assert raised_sent.json()["payload"]["activities"][0]["verified_quantity"] == "12.000"
    sign_in(c)
    own_offer = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-SELF", "package_id": package_id, "activity_id": other["id"]},
    )
    assert own_offer.status_code == 201, own_offer.text
    own_sent = c.post(
        f"/api/projects/{pid}/quality/offers/{own_offer.json()['id']}/submit",
        json={"version": own_offer.json()["version"]},
    )
    assert own_sent.status_code == 200, own_sent.text
    self_approval = c.post(
        f"/api/reviews/{own_sent.json()['review']['id']}/decisions",
        json={
            "action": "approve",
            "reason": "",
            "comment": "",
            "version": own_sent.json()["review"]["version"],
        },
    )
    assert self_approval.status_code == 403, self_approval.text
    final = c.get(f"/api/projects/{pid}/quality").json()
    final_package = next(row for row in final["packages"] if row["id"] == package_id)
    assert final_package["status"] == "In Progress"
    marks_row = next(row for row in final_package["activities"] if row["code"] == "MARKS")
    assert marks_row["accepted_quantity"] is None
    assert "100.00%" in marks_row["accepted_note"]
    other_final = next(row for row in final_package["activities"] if row["code"] == "OTHER")
    assert other_final["accepted_quantity"] is None


def _document_policy(discipline_id, reviewer_id, record_type="quality.document"):
    body = _inspection_policy(discipline_id, reviewer_id)
    body["record_type"] = record_type
    body["stages"][0]["name"] = "Quality document"
    body["stages"][0]["purpose"] = "Approve the quality document for use"
    return body


def test_quality_plan_keeps_the_approved_revision(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="QUAL-PLAN",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    pid = created.json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    for user_id, role in ((uid, "Site Engineer"), (me["id"], "Project Manager")):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    outsider = _user(c, "plan-outsider@alpha.test", "Plan Outsider", me["company_id"])
    sign_in(c, "viewer@alpha.test")
    denied = c.post(
        f"/api/projects/{pid}/quality/documents",
        json={
            "kind": "ITP",
            "number": "ITP-CIV",
            "title": "Civil inspection plan",
            "revision_label": "A",
            "discipline_id": civil,
            "company_id": me["company_id"],
            "engineering_reference": "Spec C-01",
            "applicable_activities": "Piling",
            "template_ids": [],
        },
    )
    assert denied.status_code == 403, denied.text
    sign_in(c)
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": uid,
                "role_id": roles["QA/QC"],
                "company_id": me["company_id"],
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    stranger = c.post(f"/api/projects/{pid}/approval-policies", json=_document_policy(civil, outsider))
    assert stranger.status_code == 422, stranger.text
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_document_policy(civil, me["id"])).status_code == 201
    assert (
        c.post(
            f"/api/projects/{pid}/approval-policies",
            json=_document_policy(civil, me["id"], "quality.template"),
        ).status_code
        == 201
    )
    sign_in(c, "viewer@alpha.test")
    draft = c.post(
        f"/api/projects/{pid}/quality/documents",
        json={
            "kind": "ITP",
            "number": "ITP-CIV",
            "title": "Civil inspection plan",
            "revision_label": "A",
            "discipline_id": civil,
            "company_id": me["company_id"],
            "engineering_reference": "Spec C-01",
            "applicable_activities": "Piling",
            "template_ids": [],
        },
    )
    assert draft.status_code == 201, draft.text
    assert "Nonattendance is not acceptance" in draft.json()["witness_rule"]
    bare = c.post(
        f"/api/projects/{pid}/quality/documents/{draft.json()['id']}/submit",
        json={"version": draft.json()["version"]},
    )
    assert bare.status_code == 422, bare.text
    assert "checkpoints" in bare.text
    held = c.put(
        f"/api/projects/{pid}/quality/documents/{draft.json()['id']}/checkpoints",
        json={
            "version": draft.json()["version"],
            "checkpoints": [
                {
                    "sequence": 1,
                    "name": "Pre-pour",
                    "criteria_reference": "Spec C-01",
                    "responsible_parties": "QA/QC",
                    "point_type": "Hold",
                    "notice_hours": 24,
                    "required_evidence": "Photos",
                    "required_signatories": "",
                    "partial_allowed": False,
                    "next_release_conditions": "",
                }
            ],
        },
    )
    assert held.status_code == 422, held.text
    assert "authorized release" in held.text
    saved = c.put(
        f"/api/projects/{pid}/quality/documents/{draft.json()['id']}/checkpoints",
        json={
            "version": draft.json()["version"],
            "checkpoints": [
                {
                    "sequence": 1,
                    "name": "Pre-pour",
                    "criteria_reference": "Spec C-01",
                    "responsible_parties": "QA/QC and client",
                    "point_type": "Hold",
                    "notice_hours": 24,
                    "required_evidence": "Photos and slump sheet",
                    "required_signatories": "QA inspector",
                    "partial_allowed": False,
                    "next_release_conditions": "QA releases the hold in writing",
                },
                {
                    "sequence": 2,
                    "name": "Pour witness",
                    "criteria_reference": "Spec C-01",
                    "responsible_parties": "Client",
                    "point_type": "Witness",
                    "notice_hours": 24,
                    "required_evidence": "Attendance sheet",
                    "required_signatories": "Client reviewer",
                    "partial_allowed": False,
                    "next_release_conditions": "",
                },
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    early_form = c.post(
        f"/api/projects/{pid}/quality/forms",
        json={
            "discipline_id": civil,
            "code": "CIV-POUR",
            "title": "Pre-pour checklist",
            "revision_label": "A",
            "criteria_document_id": draft.json()["id"],
            "units": "mm",
            "prerequisites": "Drawing released",
            "required_attachments": "Photo",
            "items": ["Cover is measured", "Formwork is clean"],
        },
    )
    assert early_form.status_code == 201, early_form.text
    too_soon = c.post(
        f"/api/projects/{pid}/quality/forms/{early_form.json()['id']}/submit",
        json={"version": early_form.json()["version"]},
    )
    assert too_soon.status_code == 422, too_soon.text
    assert "approved quality document" in too_soon.text
    sent = c.post(
        f"/api/projects/{pid}/quality/documents/{draft.json()['id']}/submit",
        json={"version": saved.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    sign_in(c, "viewer@alpha.test")
    own = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    locked = c.put(
        f"/api/projects/{pid}/quality/documents/{draft.json()['id']}",
        json={
            "version": sent.json()["version"],
            "title": "Changed after approval",
            "discipline_id": civil,
            "company_id": me["company_id"],
            "engineering_reference": "Spec C-01",
            "applicable_activities": "Piling",
            "template_ids": [],
        },
    )
    assert locked.status_code == 409, locked.text
    form_sent = c.post(
        f"/api/projects/{pid}/quality/forms/{early_form.json()['id']}/submit",
        json={"version": early_form.json()["version"]},
    )
    assert form_sent.status_code == 200, form_sent.text
    assert form_sent.json()["payload"]["items"] == ["Cover is measured", "Formwork is clean"]
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{form_sent.json()['review']['id']}/decisions",
            json={
                "action": "approve",
                "reason": "",
                "comment": "",
                "version": form_sent.json()["review"]["version"],
            },
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    current = c.get(f"/api/projects/{pid}/quality/plans").json()
    approved = next(row for row in current["documents"] if row["number"] == "ITP-CIV" and row["status"] == "Approved")
    revised = c.post(
        f"/api/projects/{pid}/quality/documents/{approved['id']}/revise",
        json={"revision_label": "B", "version": approved["version"]},
    )
    assert revised.status_code == 201, revised.text
    revised_sent = c.post(
        f"/api/projects/{pid}/quality/documents/{revised.json()['id']}/submit",
        json={"version": revised.json()["version"]},
    )
    assert revised_sent.status_code == 200, revised_sent.text
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{revised_sent.json()['review']['id']}/decisions",
            json={
                "action": "approve",
                "reason": "",
                "comment": "",
                "version": revised_sent.json()["review"]["version"],
            },
        ).status_code
        == 200
    )
    with maker() as db:
        from app.domains.coordination.models import Notification
        from app.domains.quality.models import QualityDocument, QualityForm

        old = db.get(QualityDocument, draft.json()["id"])
        assert old.status == "Superseded"
        assert old.payload["revision_label"] == "A"
        frozen = db.get(QualityForm, early_form.json()["id"])
        assert frozen.payload["items"] == ["Cover is measured", "Formwork is clean"]
        assert frozen.payload["criteria_revision"] == "A"
        note = db.query(Notification).filter_by(title="Quality document approved", project_id=pid).first()
        assert note is not None
    sign_in(c, "viewer@alpha.test")
    stale = c.post(
        f"/api/projects/{pid}/quality/forms",
        json={
            "discipline_id": civil,
            "code": "CIV-OLD",
            "title": "Uses the old revision",
            "revision_label": "A",
            "criteria_document_id": draft.json()["id"],
            "units": "mm",
            "prerequisites": "",
            "required_attachments": "",
            "items": ["Old cover check"],
        },
    )
    assert stale.status_code == 201, stale.text
    stale_sent = c.post(
        f"/api/projects/{pid}/quality/forms/{stale.json()['id']}/submit",
        json={"version": stale.json()["version"]},
    )
    assert stale_sent.status_code == 422, stale_sent.text
    assert "approved quality document" in stale_sent.text


def _material_policy(discipline_id, reviewer_id):
    return {
        "record_type": "quality.material",
        "company_id": None,
        "discipline_id": discipline_id,
        "allow_self_approval": False,
        "stages": [
            {
                "name": "Inspection",
                "rule": "all",
                "quorum_count": 1,
                "reviewer_ids": [reviewer_id],
                "reviewers": [],
                "purpose": "Accept the received quantity",
            }
        ],
    }


def _posted_receipt(db, project_id, user_id, company_id, discipline_id, number, quantity, status="Posted"):
    from datetime import date
    from decimal import Decimal

    from app.domains.identity_projects.models import Project
    from app.domains.supply_chain.models import (
        GoodsReceipt,
        GoodsReceiptLine,
        MaterialRequirement,
        ProcurementItem,
        PurchaseOrder,
        PurchaseOrderLine,
        PurchaseRequisition,
        QuotationLine,
        RequestForQuotation,
        RequirementLine,
        RequisitionLine,
        RfqAward,
        RfqLine,
        Vendor,
        VendorQuotation,
    )

    project = db.get(Project, project_id)
    day = date(2026, 12, 2)
    amount = Decimal(quantity)
    item = ProcurementItem(
        organization_id=project.organization_id,
        code=number,
        code_key=number.casefold(),
        description="Cable",
        item_type="Material",
        category="Cable",
        discipline_ids=[discipline_id],
        base_unit="m",
        inspection_required=True,
        created_by=user_id,
    )
    db.add(item)
    db.flush()
    vendor = Vendor(
        organization_id=project.organization_id,
        code=f"V-{number}",
        code_key=f"v-{number}".casefold(),
        company_id=company_id,
        created_by=user_id,
    )
    db.add(vendor)
    db.flush()
    requirement = MaterialRequirement(
        organization_id=project.organization_id,
        project_id=project.id,
        number=f"MR-{number}",
        number_key=f"mr-{number}".casefold(),
        company_id=company_id,
        discipline_id=discipline_id,
        requested_by=user_id,
        required_date=day,
        purpose="Install",
        created_by=user_id,
    )
    db.add(requirement)
    db.flush()
    requirement_line = RequirementLine(
        requirement_id=requirement.id,
        position=1,
        item_id=item.id,
        quantity=amount,
        unit="m",
        required_date=day,
    )
    db.add(requirement_line)
    db.flush()
    requisition = PurchaseRequisition(
        organization_id=project.organization_id,
        project_id=project.id,
        number=f"PR-{number}",
        number_key=f"pr-{number}".casefold(),
        company_id=company_id,
        discipline_id=discipline_id,
        requested_by=user_id,
        request_date=day,
        required_delivery=day,
        justification="Need the cable",
        created_by=user_id,
    )
    db.add(requisition)
    db.flush()
    requisition_line = RequisitionLine(
        requisition_id=requisition.id,
        requirement_line_id=requirement_line.id,
        position=1,
        item_id=item.id,
        quantity=amount,
        unit="m",
    )
    db.add(requisition_line)
    db.flush()
    rfq = RequestForQuotation(
        organization_id=project.organization_id,
        project_id=project.id,
        requisition_id=requisition.id,
        number=f"RFQ-{number}",
        number_key=f"rfq-{number}".casefold(),
        company_id=company_id,
        discipline_id=discipline_id,
        due_date=day,
        created_by=user_id,
    )
    db.add(rfq)
    db.flush()
    rfq_line = RfqLine(rfq_id=rfq.id, requisition_line_id=requisition_line.id, position=1, quantity=amount)
    db.add(rfq_line)
    db.flush()
    quote = VendorQuotation(
        rfq_id=rfq.id,
        vendor_id=vendor.id,
        reference=number,
        quotation_date=day,
        validity_date=day,
        currency="INR",
        created_by=user_id,
    )
    db.add(quote)
    db.flush()
    quote_line = QuotationLine(
        quotation_id=quote.id,
        rfq_line_id=rfq_line.id,
        quantity=amount,
        unit_price=Decimal("10"),
    )
    db.add(quote_line)
    db.flush()
    award = RfqAward(rfq_id=rfq.id, quotation_line_id=quote_line.id, quantity=amount, awarded_by=user_id)
    db.add(award)
    db.flush()
    order = PurchaseOrder(
        organization_id=project.organization_id,
        project_id=project.id,
        rfq_id=rfq.id,
        vendor_id=vendor.id,
        number=f"PO-{number}",
        number_key=f"po-{number}".casefold(),
        company_id=company_id,
        discipline_id=discipline_id,
        promised_date=day,
        status="Issued",
        created_by=user_id,
    )
    db.add(order)
    db.flush()
    order_line = PurchaseOrderLine(
        purchase_order_id=order.id,
        award_id=award.id,
        position=1,
        quantity=amount,
        unit_price=Decimal("10"),
    )
    db.add(order_line)
    db.flush()
    receipt = GoodsReceipt(
        organization_id=project.organization_id,
        project_id=project.id,
        purchase_order_id=order.id,
        number=number,
        number_key=number.casefold(),
        receipt_date=day,
        status=status,
        created_by=user_id,
    )
    db.add(receipt)
    db.flush()
    receipt_line = GoodsReceiptLine(
        goods_receipt_id=receipt.id,
        purchase_order_line_id=order_line.id,
        quantity=amount,
    )
    db.add(receipt_line)
    db.commit()
    return receipt.id, receipt_line.id, item.id


def _move(line_id, origin, destination, quantity):
    return {
        "goods_receipt_line_id": line_id,
        "from_state": origin,
        "to_state": destination,
        "quantity": quantity,
        "batch_number": "B-1",
        "heat_number": "H-1",
        "serial_number": "",
    }


def test_material_inspection_splits_a_receipt_without_accepting_installation(env):
    from decimal import Decimal

    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="MAT-1",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    qa = _user(c, "qa.mat@alpha.test", "Qa Mat", me["company_id"])
    reviewer = _user(c, "rev.mat@alpha.test", "Rev Mat", me["company_id"])
    outsider = _user(c, "out.mat@alpha.test", "Out Mat", me["company_id"])
    with maker() as db:
        from app.domains.identity_projects.models import User

        viewer_id = db.query(User).filter_by(email="viewer@alpha.test").one().id
    for user_id, role in ((viewer_id, "Site Engineer"), (qa, "QA/QC"), (reviewer, "Discipline Head"), (me["id"], "Project Manager")):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    with maker() as db:
        receipt_id, line_id, item_id = _posted_receipt(db, pid, me["id"], me["company_id"], civil, "GR-MAT", "10")
        cancelled_id, cancelled_line, _item = _posted_receipt(
            db, pid, me["id"], me["company_id"], civil, "GR-CANCEL", "1", "Cancelled"
        )
    sign_in(c, "viewer@alpha.test")
    denied = c.post(
        f"/api/projects/{pid}/quality/materials",
        json={
            "number": "MI-NO",
            "goods_receipt_id": receipt_id,
            "inspector_id": qa,
            "requested_on": "2026-12-02",
            "lines": [_move(line_id, "Pending", "Accepted", "1")],
        },
    )
    assert denied.status_code == 403, denied.text
    sign_in(c)
    warehouse = c.post(
        f"/api/projects/{pid}/procurement/warehouses",
        json={"code": "WH-MAT", "name": "Site store", "officer_id": me["id"]},
    )
    assert warehouse.status_code == 201, warehouse.text
    early_stock = c.post(
        f"/api/projects/{pid}/procurement/stock/acceptances",
        json={
            "number": "ACC-EARLY",
            "warehouse_id": warehouse.json()["id"],
            "goods_receipt_id": receipt_id,
            "lines": [{"goods_receipt_line_id": line_id, "quantity": "1"}],
        },
    )
    assert early_stock.status_code == 422, early_stock.text
    assert "quality has accepted" in early_stock.text
    sign_in(c, "qa.mat@alpha.test")
    cancelled = c.post(
        f"/api/projects/{pid}/quality/materials",
        json={
            "number": "MI-CANCEL",
            "goods_receipt_id": cancelled_id,
            "inspector_id": qa,
            "requested_on": "2026-12-02",
            "lines": [_move(cancelled_line, "Pending", "Accepted", "1")],
        },
    )
    assert cancelled.status_code == 422, cancelled.text
    assert "posted goods receipt" in cancelled.text
    kept = c.post(
        f"/api/projects/{pid}/quality/materials",
        json={
            "number": "MI-KEEP",
            "goods_receipt_id": receipt_id,
            "inspector_id": qa,
            "requested_on": "2026-12-02",
            "lines": [_move(line_id, "Accepted", "Rejected", "1")],
        },
    )
    assert kept.status_code == 422, kept.text
    assert "stays on record" in kept.text
    over = c.post(
        f"/api/projects/{pid}/quality/materials",
        json={
            "number": "MI-OVER",
            "goods_receipt_id": receipt_id,
            "inspector_id": qa,
            "requested_on": "2026-12-02",
            "lines": [_move(line_id, "Pending", "Accepted", "11")],
        },
    )
    assert over.status_code == 422, over.text
    assert "still pending" in over.text
    draft = c.post(
        f"/api/projects/{pid}/quality/materials",
        json={
            "number": "MI-SELF",
            "goods_receipt_id": receipt_id,
            "inspector_id": qa,
            "requested_on": "2026-12-02",
            "certificate_reference": "MTC-1",
            "findings": "Heat number is on the certificate",
            "lines": [_move(line_id, "Pending", "Accepted", "1")],
        },
    )
    assert draft.status_code == 201, draft.text
    assert "does not accept the installation" in draft.json()["statement"]
    missing = c.post(
        f"/api/projects/{pid}/quality/materials/{draft.json()['id']}/submit",
        json={"version": draft.json()["version"]},
    )
    assert missing.status_code == 422, missing.text
    assert "Mandatory reviewer" in missing.text
    sign_in(c)
    stranger = c.post(f"/api/projects/{pid}/approval-policies", json=_material_policy(civil, outsider))
    assert stranger.status_code == 422, stranger.text
    assert "not an active member" in stranger.text
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_material_policy(civil, qa)).status_code == 201
    sign_in(c, "qa.mat@alpha.test")
    sent = c.post(
        f"/api/projects/{pid}/quality/materials/{draft.json()['id']}/submit",
        json={"version": draft.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    own = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    assert "cannot approve your own" in own.text
    rejected = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "reject", "reason": "Certificate is incomplete", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert rejected.status_code == 200, rejected.text
    sign_in(c)
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_material_policy(civil, reviewer)).status_code == 201
    sign_in(c, "qa.mat@alpha.test")
    opened = c.get(f"/api/projects/{pid}/quality/materials").json()
    balance = next(row for row in opened["receipts"] if row["id"] == receipt_id)["lines"][0]
    assert balance["pending"] == "10.000"
    assert balance["accepted"] == "0.000"
    partial = c.post(
        f"/api/projects/{pid}/quality/materials",
        json={
            "number": "MI-1",
            "goods_receipt_id": receipt_id,
            "inspector_id": reviewer,
            "requested_on": "2026-12-02",
            "certificate_reference": "MTC-2",
            "findings": "Partial inspection",
            "lines": [
                _move(line_id, "Pending", "Accepted", "6"),
                _move(line_id, "Pending", "Rejected", "2"),
                _move(line_id, "Pending", "Quarantined", "1"),
            ],
        },
    )
    assert partial.status_code == 201, partial.text
    blocked = c.post(
        f"/api/projects/{pid}/quality/materials",
        json={
            "number": "MI-2",
            "goods_receipt_id": receipt_id,
            "inspector_id": reviewer,
            "requested_on": "2026-12-03",
            "lines": [_move(line_id, "Pending", "Accepted", "1")],
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert "open material inspection" in blocked.text
    submitted = c.post(
        f"/api/projects/{pid}/quality/materials/{partial.json()['id']}/submit",
        json={"version": partial.json()["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    sign_in(c)
    admin_decide = c.post(
        f"/api/reviews/{submitted.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": submitted.json()["review"]["version"]},
    )
    assert admin_decide.status_code == 403, admin_decide.text
    sign_in(c, "rev.mat@alpha.test")
    approved = c.post(
        f"/api/reviews/{submitted.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": submitted.json()["review"]["version"]},
    )
    assert approved.status_code == 200, approved.text
    sign_in(c, "qa.mat@alpha.test")
    after = c.get(f"/api/projects/{pid}/quality/materials").json()
    first = next(row for row in after["receipts"] if row["id"] == receipt_id)["lines"][0]
    assert first["pending"] == "1.000"
    assert first["accepted"] == "6.000"
    assert first["rejected"] == "2.000"
    assert first["quarantined"] == "1.000"
    assert (
        Decimal(first["pending"])
        + Decimal(first["accepted"])
        + Decimal(first["rejected"])
        + Decimal(first["quarantined"])
        == Decimal(first["received"])
    )
    follow = c.post(
        f"/api/projects/{pid}/quality/materials",
        json={
            "number": "MI-3",
            "goods_receipt_id": receipt_id,
            "inspector_id": reviewer,
            "requested_on": "2026-12-04",
            "findings": "Quarantine released to rejection and the last metre accepted",
            "lines": [
                _move(line_id, "Pending", "Accepted", "1"),
                _move(line_id, "Quarantined", "Rejected", "1"),
            ],
        },
    )
    assert follow.status_code == 201, follow.text
    follow_sent = c.post(
        f"/api/projects/{pid}/quality/materials/{follow.json()['id']}/submit",
        json={"version": follow.json()["version"]},
    )
    assert follow_sent.status_code == 200, follow_sent.text
    sign_in(c, "rev.mat@alpha.test")
    follow_ok = c.post(
        f"/api/reviews/{follow_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": follow_sent.json()["review"]["version"]},
    )
    assert follow_ok.status_code == 200, follow_ok.text
    sign_in(c)
    final = c.get(f"/api/projects/{pid}/quality/materials").json()
    done = next(row for row in final["receipts"] if row["id"] == receipt_id)["lines"][0]
    assert done["pending"] == "0.000"
    assert done["accepted"] == "7.000"
    assert done["rejected"] == "3.000"
    assert done["quarantined"] == "0.000"
    too_much = c.post(
        f"/api/projects/{pid}/procurement/stock/acceptances",
        json={
            "number": "ACC-MAT",
            "warehouse_id": warehouse.json()["id"],
            "goods_receipt_id": receipt_id,
            "lines": [{"goods_receipt_line_id": line_id, "quantity": "8"}],
        },
    )
    assert too_much.status_code == 422, too_much.text
    assert "quality has accepted" in too_much.text
    # A Quality-module approval alone does not authorize the independent
    # Stores QA case. Fail closed rather than bypassing QA revocation controls.
    stocked = c.post(
        f"/api/projects/{pid}/procurement/stock/acceptances",
        json={
            "number": "ACC-MAT",
            "warehouse_id": warehouse.json()["id"],
            "goods_receipt_id": receipt_id,
            "lines": [{"goods_receipt_line_id": line_id, "quantity": "7"}],
        },
    )
    assert stocked.status_code == 422, stocked.text
    assert "quality has accepted" in stocked.text

    # With no QA-authorized stock posting, item-level issues must also fail.
    blocked_issue = c.post(
        f"/api/projects/{pid}/procurement/stock/issues",
        json={
            "number": "ISS-MAT",
            "warehouse_id": warehouse.json()["id"],
            "reason": "Site issue",
            "recipient": "Civil crew",
            "lines": [{"item_id": item_id, "quantity": "7"}],
        },
    )
    assert blocked_issue.status_code == 409, blocked_issue.text
    assert "QA-certified stock source is unavailable" in blocked_issue.text

    # Real API handoff: approved Quality dispositions authorize an untouched
    # Stores inspection case, but never post stock or release mixed lots.
    handoff_url = (
        f"/api/projects/{pid}/stores/inspection-cases/"
        f"from-quality/{line_id}/reconcile"
    )
    transferred = c.post(handoff_url, params={"expected_version": 1})
    assert transferred.status_code == 200, transferred.text
    snapshot = transferred.json()
    assert Decimal(snapshot["accepted_qty"]) == Decimal("7")
    assert Decimal(snapshot["rejected_qty"]) == Decimal("3")
    assert Decimal(snapshot["quarantined_qty"]) == Decimal("0")
    assert Decimal(snapshot["pending_qty"]) == Decimal("0")
    assert snapshot["stock_posted"] is False
    assert snapshot["lot_release_enabled"] is False

    # Repeating with a stale expected version must not double-authorize QA.
    replay = c.post(handoff_url, params={"expected_version": 1})
    assert replay.status_code == 409, replay.text

    # Exercise access control through real HTTP requests (not source-text checks).
    sign_in(c, "viewer@alpha.test")
    forbidden = c.post(handoff_url, params={"expected_version": 2})
    assert forbidden.status_code == 403, forbidden.text

    sign_in(c, "admin@beta.test")
    cross_tenant = c.post(handoff_url, params={"expected_version": 2})
    assert cross_tenant.status_code in (403, 404), cross_tenant.text

    sign_in(c)
    wrong_project = c.post(
        f"/api/projects/{pid + 100000}/stores/inspection-cases/"
        f"from-quality/{line_id}/reconcile",
        params={"expected_version": 2},
    )
    assert wrong_project.status_code in (403, 404), wrong_project.text

    # A current version must still reject handoff over recorded Stores decisions.
    decided = c.post(handoff_url, params={"expected_version": 2})
    assert decided.status_code == 409, decided.text
    assert "Existing Stores decisions" in decided.text

    from app.domains.stores_inventory.models import StoresInspectionCase, StoresInspectionDecision
    with maker() as db:
        case = db.query(StoresInspectionCase).filter_by(goods_receipt_line_id=line_id).one()
        decisions = db.query(StoresInspectionDecision).filter_by(case_id=case.id).all()
        assert len(decisions) == 2
        assert Decimal(case.accepted_qty) == Decimal("7")
        assert Decimal(case.rejected_qty) == Decimal("3")

    # Posting beyond Quality acceptance remains forbidden after the handoff.
    still_too_much = c.post(
        f"/api/projects/{pid}/procurement/stock/acceptances",
        json={
            "number": "ACC-MAT-OVER",
            "warehouse_id": warehouse.json()["id"],
            "goods_receipt_id": receipt_id,
            "lines": [{"goods_receipt_line_id": line_id, "quantity": "8"}],
        },
    )
    assert still_too_much.status_code == 422, still_too_much.text

    authorized_stock = c.post(
        f"/api/projects/{pid}/procurement/stock/acceptances",
        json={
            "number": "ACC-MAT",
            "warehouse_id": warehouse.json()["id"],
            "goods_receipt_id": receipt_id,
            "lines": [{"goods_receipt_line_id": line_id, "quantity": "7"}],
        },
    )
    assert authorized_stock.status_code == 201, authorized_stock.text

    # The coarse item ledger still contains a partly rejected GRN; issuing
    # from an unsegregated item balance must remain blocked.
    mixed_issue = c.post(
        f"/api/projects/{pid}/procurement/stock/issues",
        json={
            "number": "ISS-MAT",
            "warehouse_id": warehouse.json()["id"],
            "reason": "Site issue",
            "recipient": "Civil crew",
            "lines": [{"item_id": item_id, "quantity": "7"}],
        },
    )
    assert mixed_issue.status_code == 409, mixed_issue.text
    assert "partial inspection" in mixed_issue.text
    with maker() as db:
        from app.domains.quality.models import QualityOffer

        assert db.query(QualityOffer).filter_by(project_id=pid).count() == 0
        note = db.query(Notification).filter_by(title="Material quantity accepted", project_id=pid).first()
        assert note is not None
        assert "does not accept the installation" in note.body


def _construction_policy(discipline_id, reviewer_id):
    body = _inspection_policy(discipline_id, reviewer_id)
    body["record_type"] = "quality.construction"
    body["stages"][0]["name"] = "Inspection"
    body["stages"][0]["purpose"] = "Accept the discipline checklist"
    return body


def test_construction_request_uses_a_discipline_form_without_billing(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    electrical = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Electrical")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="QUAL-REQ",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area_id = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    ).json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        viewer_id = db.query(User).filter_by(email="viewer@alpha.test").one().id
    reviewer = _user(c, "rev.req@alpha.test", "Rev Req", me["company_id"])
    outsider = _user(c, "out.req@alpha.test", "Out Req", me["company_id"])
    stores = _user(c, "stores.req@alpha.test", "Stores Req", me["company_id"])
    for user_id, role in (
        (viewer_id, "Site Engineer"),
        (reviewer, "Discipline Head"),
        (me["id"], "Project Manager"),
        (stores, "Stores Officer"),
    ):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(civil, me["id"])).status_code == 201
    sign_in(c, "viewer@alpha.test")
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-REQ"),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    pour = _activity(c, pid, package_id, me["company_id"], "POUR", "Quantity", "12")
    waiting = _activity(c, pid, package_id, me["company_id"], "WAIT", "Quantity", "4")
    closed = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-EARLY"),
    )
    early = _activity(c, pid, closed.json()["id"], me["company_id"], "EARLY", "Quantity", "1")
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.identity_projects.models import Project
        from app.domains.quality.models import QualityCheckpoint, QualityDocument, QualityForm

        project = db.get(Project, pid)
        released = db.get(WorkPackage, package_id)
        released.status = "In Progress"
        released.release_state = "Released"
        document = QualityDocument(
            organization_id=project.organization_id,
            project_id=pid,
            kind="ITP",
            number="ITP-REQ",
            number_key="itp-req",
            title="Pour plan",
            revision_label="A",
            revision_key="a",
            discipline_id=civil,
            company_id=me["company_id"],
            status="Approved",
            template_ids=[],
            payload={"revision_label": "A"},
            created_by=me["id"],
        )
        db.add(document)
        db.flush()
        review_point = QualityCheckpoint(
            document_id=document.id, sequence=1, name="Cover check", point_type="Review", criteria_reference="Spec"
        )
        witness_point = QualityCheckpoint(
            document_id=document.id, sequence=2, name="Pour witness", point_type="Witness", required_signatories="Client"
        )
        hold_point = QualityCheckpoint(
            document_id=document.id,
            sequence=3,
            name="Hold pour",
            point_type="Hold",
            next_release_conditions="Written release",
        )
        db.add_all([review_point, witness_point, hold_point])
        form = QualityForm(
            organization_id=project.organization_id,
            project_id=pid,
            discipline_id=civil,
            code="CIV-POUR",
            code_key="civ-pour",
            title="Pre-pour checklist",
            revision_label="A",
            revision_key="a",
            criteria_document_id=document.id,
            units="mm",
            items=["Cover is measured", "Formwork is clean"],
            status="Approved",
            payload={"revision_label": "A", "criteria_revision": "A", "items": ["Cover is measured", "Formwork is clean"]},
            created_by=me["id"],
        )
        draft_form = QualityForm(
            organization_id=project.organization_id,
            project_id=pid,
            discipline_id=civil,
            code="CIV-DRAFT",
            code_key="civ-draft",
            title="Draft form",
            revision_label="A",
            revision_key="a",
            criteria_document_id=document.id,
            units="mm",
            items=["Draft item"],
            status="Draft",
            payload={},
            created_by=me["id"],
        )
        other_form = QualityForm(
            organization_id=project.organization_id,
            project_id=pid,
            discipline_id=electrical,
            code="ELE-FORM",
            code_key="ele-form",
            title="Electrical form",
            revision_label="A",
            revision_key="a",
            criteria_document_id=document.id,
            units="ohm",
            items=["Continuity"],
            status="Approved",
            payload={},
            created_by=me["id"],
        )
        db.add_all([form, draft_form, other_form])
        db.commit()
        form_id, draft_id, other_id = form.id, draft_form.id, other_form.id
        review_id, witness_id, hold_id = review_point.id, witness_point.id, hold_point.id
    sign_in(c, "stores.req@alpha.test")
    denied = c.post(
        f"/api/projects/{pid}/quality/requests",
        json={
            "number": "REQ-NO",
            "activity_id": pour["id"],
            "template_id": form_id,
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "requester_id": viewer_id,
            "inspector_id": viewer_id,
        },
    )
    assert denied.status_code == 403, denied.text
    sign_in(c, "viewer@alpha.test")
    unreleased = c.post(
        f"/api/projects/{pid}/quality/requests",
        json={
            "number": "REQ-EARLY",
            "activity_id": early["id"],
            "template_id": form_id,
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "requester_id": viewer_id,
            "inspector_id": viewer_id,
        },
    )
    assert unreleased.status_code == 409, unreleased.text
    assert "released work package" in unreleased.text
    report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, viewer_id, number="DPR-REQ"),
    )
    assert report.status_code == 201, report.text
    line = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines",
        json={"activity_id": pour["id"], "quantity": "10"},
    )
    assert line.status_code == 201, line.text
    sent_report = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/submit",
        json={"version": line.json()["version"]},
    )
    assert sent_report.status_code == 200, sent_report.text
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{sent_report.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": sent_report.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "viewer@alpha.test")
    no_quantity = c.post(
        f"/api/projects/{pid}/quality/requests",
        json={
            "number": "REQ-WAIT",
            "activity_id": waiting["id"],
            "template_id": form_id,
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "requester_id": viewer_id,
            "inspector_id": viewer_id,
        },
    )
    assert no_quantity.status_code == 422, no_quantity.text
    assert "no verified quantity" in no_quantity.text
    draft_template = c.post(
        f"/api/projects/{pid}/quality/requests",
        json={
            "number": "REQ-DRAFT",
            "activity_id": pour["id"],
            "template_id": draft_id,
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "requester_id": viewer_id,
            "inspector_id": viewer_id,
        },
    )
    assert draft_template.status_code == 422, draft_template.text
    assert "approved discipline form" in draft_template.text
    other = c.post(
        f"/api/projects/{pid}/quality/requests",
        json={
            "number": "REQ-ELE",
            "activity_id": pour["id"],
            "template_id": other_id,
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "requester_id": viewer_id,
            "inspector_id": viewer_id,
        },
    )
    assert other.status_code == 422, other.text
    assert "another discipline" in other.text
    held = c.post(
        f"/api/projects/{pid}/quality/requests",
        json={
            "number": "REQ-HOLD",
            "activity_id": pour["id"],
            "template_id": form_id,
            "checkpoint_id": hold_id,
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "requester_id": viewer_id,
            "inspector_id": viewer_id,
        },
    )
    assert held.status_code == 422, held.text
    assert "quality hold for this hold point" in held.text
    witnessed = c.post(
        f"/api/projects/{pid}/quality/requests",
        json={
            "number": "REQ-WIT",
            "activity_id": pour["id"],
            "template_id": form_id,
            "checkpoint_id": witness_id,
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "requester_id": viewer_id,
            "inspector_id": viewer_id,
        },
    )
    assert witnessed.status_code == 422, witnessed.text
    assert "Record who attended" in witnessed.text

    def body(number, **extra):
        payload = {
            "number": number,
            "activity_id": pour["id"],
            "template_id": form_id,
            "checkpoint_id": review_id,
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "requester_id": viewer_id,
            "inspector_id": reviewer,
            "findings": "Cover checked",
        }
        payload.update(extra)
        return payload

    draft = c.post(f"/api/projects/{pid}/quality/requests", json=body("REQ-1"))
    assert draft.status_code == 201, draft.text
    assert "does not certify billing" in draft.json()["statement"]
    assert [row["item"] for row in draft.json()["results"]] == ["Cover is measured", "Formwork is clean"]
    bare = c.post(
        f"/api/projects/{pid}/quality/requests/{draft.json()['id']}/submit",
        json={"version": draft.json()["version"]},
    )
    assert bare.status_code == 422, bare.text
    assert "checklist item" in bare.text
    failed = c.put(
        f"/api/projects/{pid}/quality/requests/{draft.json()['id']}",
        json={
            "version": draft.json()["version"],
            "outcome": "Accepted",
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "inspector_id": reviewer,
            "results": [
                {"item": "Cover is measured", "result": "Fail", "measurement": "15"},
                {"item": "Formwork is clean", "result": "Pass", "measurement": ""},
            ],
        },
    )
    assert failed.status_code == 422, failed.text
    assert "cannot be accepted" in failed.text
    recorded = c.put(
        f"/api/projects/{pid}/quality/requests/{draft.json()['id']}",
        json={
            "version": draft.json()["version"],
            "outcome": "Rejected",
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "inspector_id": reviewer,
            "findings": "Cover is short",
            "results": [
                {"item": "Cover is measured", "result": "Fail", "measurement": "15"},
                {"item": "Formwork is clean", "result": "Pass", "measurement": ""},
            ],
        },
    )
    assert recorded.status_code == 200, recorded.text
    missing = c.post(
        f"/api/projects/{pid}/quality/requests/{draft.json()['id']}/submit",
        json={"version": recorded.json()["version"]},
    )
    assert missing.status_code == 422, missing.text
    assert "Mandatory reviewer" in missing.text
    sign_in(c)
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_construction_policy(civil, outsider)).status_code == 422
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_construction_policy(civil, viewer_id)).status_code == 201
    sign_in(c, "viewer@alpha.test")
    sent = c.post(
        f"/api/projects/{pid}/quality/requests/{draft.json()['id']}/submit",
        json={"version": recorded.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["payload"]["items"][0]["result"] == "Fail"
    assert sent.json()["payload"]["template_revision"] == "A"
    own = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    assert "cannot approve your own" in own.text
    sign_in(c)
    admin_block = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert admin_block.status_code == 403, admin_block.text
    sign_in(c, "viewer@alpha.test")
    review_rejected = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "reject", "reason": "Use the saved reviewer", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert review_rejected.status_code == 200, review_rejected.text
    sign_in(c)
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_construction_policy(civil, reviewer)).status_code == 201
    sign_in(c, "viewer@alpha.test")
    rejected = c.post(f"/api/projects/{pid}/quality/requests", json=body("REQ-REJ"))
    assert rejected.status_code == 201, rejected.text
    rejected_saved = c.put(
        f"/api/projects/{pid}/quality/requests/{rejected.json()['id']}",
        json={
            "version": rejected.json()["version"],
            "outcome": "Rejected",
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "inspector_id": reviewer,
            "results": [
                {"item": "Cover is measured", "result": "Fail", "measurement": "15"},
                {"item": "Formwork is clean", "result": "Pass", "measurement": ""},
            ],
        },
    )
    assert rejected_saved.status_code == 200, rejected_saved.text
    rejected_sent = c.post(
        f"/api/projects/{pid}/quality/requests/{rejected.json()['id']}/submit",
        json={"version": rejected_saved.json()["version"]},
    )
    assert rejected_sent.status_code == 200, rejected_sent.text
    sign_in(c, "rev.req@alpha.test")
    rejected_ok = c.post(
        f"/api/reviews/{rejected_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": rejected_sent.json()["review"]["version"]},
    )
    assert rejected_ok.status_code == 200, rejected_ok.text
    sign_in(c, "viewer@alpha.test")
    board = c.get(f"/api/projects/{pid}/quality").json()
    measured = next(row for package_row in board["packages"] for row in package_row["activities"] if row["code"] == "POUR")
    assert measured["accepted_quantity"] is None
    assert "does not accept" in measured["accepted_note"]
    assert next(package_row["status"] for package_row in board["packages"] if package_row["code"] == "WP-REQ") == "In Progress"
    unlinked = c.post(f"/api/projects/{pid}/quality/requests", json=body("REQ-OPEN"))
    assert unlinked.status_code == 422, unlinked.text
    assert "link the rejected result" in unlinked.text
    partial = c.post(f"/api/projects/{pid}/quality/requests", json=body("REQ-PART", follows_id=rejected.json()["id"]))
    assert partial.status_code == 201, partial.text
    too_much = c.put(
        f"/api/projects/{pid}/quality/requests/{partial.json()['id']}",
        json={
            "version": partial.json()["version"],
            "outcome": "Partially Accepted",
            "accepted_quantity": "20",
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "inspector_id": reviewer,
            "results": [
                {"item": "Cover is measured", "result": "Pass", "measurement": "40"},
                {"item": "Formwork is clean", "result": "Pass", "measurement": ""},
            ],
        },
    )
    assert too_much.status_code == 200, too_much.text
    too_sent = c.post(
        f"/api/projects/{pid}/quality/requests/{partial.json()['id']}/submit",
        json={"version": too_much.json()["version"]},
    )
    assert too_sent.status_code == 422, too_sent.text
    assert "less than the quantity" in too_sent.text
    partial_saved = c.put(
        f"/api/projects/{pid}/quality/requests/{partial.json()['id']}",
        json={
            "version": too_much.json()["version"],
            "outcome": "Partially Accepted",
            "accepted_quantity": "4",
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "inspector_id": reviewer,
            "results": [
                {"item": "Cover is measured", "result": "Pass", "measurement": "40"},
                {"item": "Formwork is clean", "result": "Pass", "measurement": ""},
            ],
        },
    )
    assert partial_saved.status_code == 200, partial_saved.text
    partial_sent = c.post(
        f"/api/projects/{pid}/quality/requests/{partial.json()['id']}/submit",
        json={"version": partial_saved.json()["version"]},
    )
    assert partial_sent.status_code == 200, partial_sent.text
    with maker() as db:
        from app.domains.quality.models import QualityForm

        form_row = db.get(QualityForm, form_id)
        form_row.revision_label = "B"
        db.commit()
    sign_in(c, "rev.req@alpha.test")
    stale = c.post(
        f"/api/reviews/{partial_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": partial_sent.json()["review"]["version"]},
    )
    assert stale.status_code == 409, stale.text
    assert "discipline form revision" in stale.text
    with maker() as db:
        from app.domains.quality.models import QualityForm

        form_row = db.get(QualityForm, form_id)
        form_row.revision_label = "A"
        db.commit()
    approved = c.post(
        f"/api/reviews/{partial_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": partial_sent.json()["review"]["version"]},
    )
    assert approved.status_code == 200, approved.text
    sign_in(c, "viewer@alpha.test")
    accepted = c.get(f"/api/projects/{pid}/quality").json()
    pour_row = next(row for package_row in accepted["packages"] for row in package_row["activities"] if row["code"] == "POUR")
    assert pour_row["accepted_quantity"] == "4.000"
    assert "does not certify" in pour_row["accepted_note"]
    assert next(package_row["status"] for package_row in accepted["packages"] if package_row["code"] == "WP-REQ") == "In Progress"
    rest = c.post(
        f"/api/projects/{pid}/quality/requests",
        json=body("REQ-REST", follows_id=partial.json()["id"]),
    )
    assert rest.status_code == 201, rest.text
    rest_saved = c.put(
        f"/api/projects/{pid}/quality/requests/{rest.json()['id']}",
        json={
            "version": rest.json()["version"],
            "outcome": "Accepted",
            "location": "Bay 1",
            "requested_on": "2026-10-09",
            "inspector_id": reviewer,
            "results": [
                {"item": "Cover is measured", "result": "Pass", "measurement": "40"},
                {"item": "Formwork is clean", "result": "Pass", "measurement": ""},
            ],
        },
    )
    assert rest_saved.status_code == 200, rest_saved.text
    rest_sent = c.post(
        f"/api/projects/{pid}/quality/requests/{rest.json()['id']}/submit",
        json={"version": rest_saved.json()["version"]},
    )
    assert rest_sent.status_code == 200, rest_sent.text
    assert rest_sent.json()["offered_quantity"] == "6.000"
    sign_in(c, "rev.req@alpha.test")
    rest_ok = c.post(
        f"/api/reviews/{rest_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": rest_sent.json()["review"]["version"]},
    )
    assert rest_ok.status_code == 200, rest_ok.text
    sign_in(c, "viewer@alpha.test")
    final = c.get(f"/api/projects/{pid}/quality").json()
    done = next(row for package_row in final["packages"] for row in package_row["activities"] if row["code"] == "POUR")
    assert done["accepted_quantity"] == "10.000"
    blocked = c.post(f"/api/projects/{pid}/quality/requests", json=body("REQ-MORE"))
    assert blocked.status_code == 422, blocked.text
    assert "already has this verified quantity accepted" in blocked.text
    sign_in(c)
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_inspection_policy(civil, reviewer)).status_code == 201
    sign_in(c, "viewer@alpha.test")
    offer = c.post(
        f"/api/projects/{pid}/quality/offers",
        json={"number": "INSP-REQ", "package_id": package_id, "activity_id": pour["id"]},
    )
    assert offer.status_code == 201, offer.text
    offer_sent = c.post(
        f"/api/projects/{pid}/quality/offers/{offer.json()['id']}/submit",
        json={"version": offer.json()["version"]},
    )
    assert offer_sent.status_code == 422, offer_sent.text
    assert "already has this verified quantity accepted" in offer_sent.text
    with maker() as db:
        note = db.query(Notification).filter_by(title="Construction quantity accepted", project_id=pid).first()
        assert note is not None
        assert "does not certify" in note.body


def _finding_policy(record_type, discipline_id, reviewer_id, purpose):
    body = _progress_policy(discipline_id, reviewer_id)
    body["record_type"] = record_type
    body["stages"][0]["name"] = purpose
    body["stages"][0]["purpose"] = purpose
    return body


def test_ncr_concession_and_quality_hold_do_not_certify(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="QUAL-NCR",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area_id = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    ).json()["id"]
    qa = _user(c, "qa.ncr@alpha.test", "QA NCR", me["company_id"])
    engineer = _user(c, "eng.ncr@alpha.test", "Eng NCR", me["company_id"])
    reviewer = _user(c, "rev.ncr@alpha.test", "Rev NCR", me["company_id"])
    outsider = _user(c, "out.ncr@alpha.test", "Out NCR", me["company_id"])
    stores = _user(c, "stores.ncr@alpha.test", "Stores NCR", me["company_id"])
    for user_id, role in (
        (qa, "QA/QC"),
        (engineer, "Site Engineer"),
        (reviewer, "Discipline Head"),
        (stores, "Stores Officer"),
        (me["id"], "Project Manager"),
    ):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    assert (
        c.post(
            f"/api/projects/{pid}/approval-policies",
            json=_finding_policy("quality.ncr", civil, outsider, "NCR disposition"),
        ).status_code
        == 422
    )
    for record_type, purpose in (
        ("quality.ncr", "NCR disposition"),
        ("quality.ncr.close", "NCR closure"),
        ("quality.concession", "Concession"),
        ("quality.hold", "Hold release"),
        ("quality.construction", "Inspection"),
    ):
        assert (
            c.post(
                f"/api/projects/{pid}/approval-policies",
                json=_finding_policy(record_type, civil, reviewer, purpose),
            ).status_code
            == 201
        )
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(civil, me["id"])).status_code == 201
    sign_in(c, "eng.ncr@alpha.test")
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-NCR"),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    pour = _activity(c, pid, package_id, me["company_id"], "POUR", "Quantity", "12")
    other = _activity(c, pid, package_id, me["company_id"], "WAIT", "Quantity", "4")
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.identity_projects.models import Project
        from app.domains.quality.models import QualityCheckpoint, QualityDocument, QualityForm

        project = db.get(Project, pid)
        released = db.get(WorkPackage, package_id)
        released.status = "In Progress"
        released.release_state = "Released"
        document = QualityDocument(
            organization_id=project.organization_id,
            project_id=pid,
            kind="ITP",
            number="ITP-NCR",
            number_key="itp-ncr",
            title="Pour plan",
            revision_label="A",
            revision_key="a",
            discipline_id=civil,
            company_id=me["company_id"],
            status="Approved",
            template_ids=[],
            payload={"revision_label": "A"},
            created_by=me["id"],
        )
        db.add(document)
        db.flush()
        hold_point = QualityCheckpoint(
            document_id=document.id,
            sequence=1,
            name="Hold pour",
            point_type="Hold",
            next_release_conditions="Written release",
        )
        db.add(hold_point)
        form = QualityForm(
            organization_id=project.organization_id,
            project_id=pid,
            discipline_id=civil,
            code="CIV-NCR",
            code_key="civ-ncr",
            title="Pour checklist",
            revision_label="A",
            revision_key="a",
            criteria_document_id=document.id,
            units="mm",
            items=["Cover is measured"],
            status="Approved",
            payload={"revision_label": "A", "criteria_revision": "A", "items": ["Cover is measured"]},
            created_by=me["id"],
        )
        db.add(form)
        db.commit()
        hold_id, form_id = hold_point.id, form.id
        receipt_id, line_id, item_id = _posted_receipt(db, pid, me["id"], me["company_id"], civil, "GR-NCR", "5")
    report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, engineer, number="DPR-NCR"),
    )
    assert report.status_code == 201, report.text
    line = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/lines",
        json={"activity_id": pour["id"], "quantity": "10"},
    )
    assert line.status_code == 201, line.text
    sent_report = c.post(
        f"/api/projects/{pid}/construction/progress/{report.json()['id']}/submit",
        json={"version": line.json()["version"]},
    )
    assert sent_report.status_code == 200, sent_report.text
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{sent_report.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": sent_report.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "eng.ncr@alpha.test")
    denied = c.post(
        f"/api/projects/{pid}/quality/ncrs",
        json={
            "number": "NCR-1",
            "source_kind": "activity",
            "source_id": pour["id"],
            "discipline_id": civil,
            "company_id": me["company_id"],
            "location": "Bay 1",
            "description": "Cover is short",
            "requirement": "Cover specification",
            "severity": "Major",
            "affected_scope": "POUR",
            "containment": "Stop the next pour",
            "owner_id": engineer,
            "raised_on": "2026-10-08",
            "target_on": "2026-10-10",
            "root_cause": "Spacer missing",
            "corrective_action": "Add spacers and recheck",
            "disposition": "Use-As-Is",
        },
    )
    assert denied.status_code == 403, denied.text
    sign_in(c, "qa.ncr@alpha.test")
    draft = c.post(
        f"/api/projects/{pid}/quality/ncrs",
        json={
            "number": "NCR-1",
            "source_kind": "activity",
            "source_id": pour["id"],
            "discipline_id": civil,
            "company_id": me["company_id"],
            "location": "Bay 1",
            "description": "Cover is short",
            "requirement": "Cover specification",
            "severity": "Major",
            "affected_scope": "POUR",
            "containment": "Stop the next pour",
            "owner_id": engineer,
            "raised_on": "2026-10-08",
            "target_on": "2026-10-10",
            "root_cause": "Spacer missing",
            "corrective_action": "Add spacers and recheck",
            "disposition": "Use-As-Is",
        },
    )
    assert draft.status_code == 201, draft.text
    early = c.post(
        f"/api/projects/{pid}/quality/ncrs/{draft.json()['id']}/submit",
        json={"version": draft.json()["version"]},
    )
    assert early.status_code == 422, early.text
    assert "approved concession" in early.text
    sign_in(c, "eng.ncr@alpha.test")
    concession = c.post(
        f"/api/projects/{pid}/quality/concessions",
        json={
            "ncr_id": draft.json()["id"],
            "number": "CON-1",
            "proposal": "Accept the short cover for this bay only",
            "technical_note": "Engineering reviewed the deviation",
        },
    )
    assert concession.status_code == 201, concession.text
    concession_sent = c.post(
        f"/api/projects/{pid}/quality/concessions/{concession.json()['id']}/submit",
        json={"version": concession.json()["version"]},
    )
    assert concession_sent.status_code == 200, concession_sent.text
    own = c.post(
        f"/api/reviews/{concession_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": concession_sent.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    sign_in(c)
    admin_block = c.post(
        f"/api/reviews/{concession_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": concession_sent.json()["review"]["version"]},
    )
    assert admin_block.status_code == 403, admin_block.text
    sign_in(c, "rev.ncr@alpha.test")
    concession_ok = c.post(
        f"/api/reviews/{concession_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": concession_sent.json()["review"]["version"]},
    )
    assert concession_ok.status_code == 200, concession_ok.text
    sign_in(c, "qa.ncr@alpha.test")
    still = c.get(f"/api/projects/{pid}/quality/ncrs").json()["ncrs"][0]
    assert still["status"] == "Draft"
    sent = c.post(
        f"/api/projects/{pid}/quality/ncrs/{draft.json()['id']}/submit",
        json={"version": still["version"]},
    )
    assert sent.status_code == 200, sent.text
    sign_in(c, "rev.ncr@alpha.test")
    approved = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert approved.status_code == 200, approved.text
    sign_in(c)
    measured = c.get(f"/api/projects/{pid}/construction/progress").json()["activities"]
    pour_row = next(row for row in measured if row["activity_code"] == "POUR")
    assert pour_row["accepted_quantity"] is None
    assert pour_row["certified_quantity"] is None
    assert "does not accept" in pour_row["accepted_note"]
    sign_in(c, "qa.ncr@alpha.test")
    open_ncr = c.get(f"/api/projects/{pid}/quality/ncrs").json()["ncrs"][0]
    assert open_ncr["status"] == "Approved"
    assert open_ncr["status"] != "Closed"
    closed = c.post(
        f"/api/projects/{pid}/quality/ncrs/{draft.json()['id']}/close",
        json={"version": open_ncr["version"], "evidence": "Spacers added", "verification": "Cover rechecked and recorded"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "Pending Verification"
    sign_in(c, "rev.ncr@alpha.test")
    finished = c.post(
        f"/api/reviews/{closed.json()['closure_review']['id']}/decisions",
        json={
            "action": "approve",
            "reason": "",
            "comment": "",
            "version": closed.json()["closure_review"]["version"],
        },
    )
    assert finished.status_code == 200, finished.text
    sign_in(c, "qa.ncr@alpha.test")
    done = next(row for row in c.get(f"/api/projects/{pid}/quality/ncrs").json()["ncrs"] if row["number"] == "NCR-1")
    assert done["status"] == "Closed"
    rework = c.post(
        f"/api/projects/{pid}/quality/ncrs",
        json={
            "number": "NCR-2",
            "source_kind": "activity",
            "source_id": other["id"],
            "discipline_id": civil,
            "company_id": me["company_id"],
            "location": "Bay 2",
            "description": "Honeycomb",
            "requirement": "Sound concrete",
            "severity": "Minor",
            "affected_scope": "WAIT",
            "containment": "Mark the area",
            "owner_id": engineer,
            "raised_on": "2026-10-08",
            "target_on": "2026-10-12",
            "root_cause": "Vibration missed",
            "corrective_action": "Break out and repour",
            "disposition": "Rework",
        },
    )
    assert rework.status_code == 201, rework.text
    rework_sent = c.post(
        f"/api/projects/{pid}/quality/ncrs/{rework.json()['id']}/submit",
        json={"version": rework.json()["version"]},
    )
    assert rework_sent.status_code == 200, rework_sent.text
    sign_in(c, "stores.ncr@alpha.test")
    assert (
        c.post(
            f"/api/projects/{pid}/quality/holds",
            json={
                "number": "QH-NO",
                "scope_kind": "activity",
                "scope_id": pour["id"],
                "owner_id": engineer,
                "reason": "Hold the pour",
                "conditions": "Written release after the cover is accepted",
                "blocks_work": True,
            },
        ).status_code
        == 403
    )
    sign_in(c, "qa.ncr@alpha.test")
    held = c.post(
        f"/api/projects/{pid}/quality/holds",
        json={
            "number": "QH-1",
            "scope_kind": "activity",
            "scope_id": pour["id"],
            "checkpoint_id": hold_id,
            "owner_id": engineer,
            "reason": "Hold the pour",
            "conditions": "Written release after the cover is accepted",
            "blocks_work": True,
            "blocks_handover": True,
        },
    )
    assert held.status_code == 201, held.text
    assert held.json()["status"] == "Active"
    sign_in(c, "eng.ncr@alpha.test")
    blocked_line = c.post(
        f"/api/projects/{pid}/construction/progress",
        json=_report(area_id, me["company_id"], civil, engineer, number="DPR-HELD"),
    )
    assert blocked_line.status_code == 201, blocked_line.text
    refused = c.post(
        f"/api/projects/{pid}/construction/progress/{blocked_line.json()['id']}/lines",
        json={"activity_id": pour["id"], "quantity": "1"},
    )
    assert refused.status_code == 422, refused.text
    assert "quality hold blocks this work" in refused.text
    requested = c.post(
        f"/api/projects/{pid}/quality/requests",
        json={
            "number": "REQ-HOLD",
            "activity_id": pour["id"],
            "template_id": form_id,
            "checkpoint_id": hold_id,
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "requester_id": engineer,
            "inspector_id": engineer,
        },
    )
    assert requested.status_code == 201, requested.text
    saved = c.put(
        f"/api/projects/{pid}/quality/requests/{requested.json()['id']}",
        json={
            "version": requested.json()["version"],
            "outcome": "Accepted",
            "location": "Bay 1",
            "requested_on": "2026-10-08",
            "inspector_id": engineer,
            "results": [{"item": "Cover is measured", "result": "Pass", "measurement": "40"}],
        },
    )
    assert saved.status_code == 200, saved.text
    request_sent = c.post(
        f"/api/projects/{pid}/quality/requests/{requested.json()['id']}/submit",
        json={"version": saved.json()["version"]},
    )
    assert request_sent.status_code == 200, request_sent.text
    sign_in(c, "rev.ncr@alpha.test")
    too_soon = c.post(
        f"/api/reviews/{request_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": request_sent.json()["review"]["version"]},
    )
    assert too_soon.status_code == 409, too_soon.text
    assert "Release the quality hold" in too_soon.text
    sign_in(c, "qa.ncr@alpha.test")
    release = c.post(
        f"/api/projects/{pid}/quality/holds/{held.json()['id']}/release",
        json={"version": held.json()["version"], "evidence": "Cover was accepted in writing"},
    )
    assert release.status_code == 200, release.text
    sign_in(c, "rev.ncr@alpha.test")
    released = c.post(
        f"/api/reviews/{release.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": release.json()["review"]["version"]},
    )
    assert released.status_code == 200, released.text
    accepted = c.post(
        f"/api/reviews/{request_sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": request_sent.json()["review"]["version"]},
    )
    assert accepted.status_code == 200, accepted.text
    sign_in(c, "eng.ncr@alpha.test")
    after = c.get(f"/api/projects/{pid}/construction/progress").json()["activities"]
    pour_after = next(row for row in after if row["activity_code"] == "POUR")
    assert pour_after["accepted_quantity"] == "10.000"
    assert pour_after["certified_quantity"] is None
    assert pour_after["package_status"] == "In Progress"
    sign_in(c, "qa.ncr@alpha.test")
    package_hold = c.post(
        f"/api/projects/{pid}/quality/holds",
        json={
            "number": "QH-2",
            "scope_kind": "package",
            "scope_id": package_id,
            "owner_id": engineer,
            "reason": "Hold handover",
            "conditions": "Close the remaining quality records",
            "blocks_handover": True,
        },
    )
    assert package_hold.status_code == 201, package_hold.text
    sign_in(c, "eng.ncr@alpha.test")
    dossier = c.post(
        f"/api/projects/{pid}/construction/handover",
        json={"number": "HO-NCR", "package_id": package_id},
    )
    assert dossier.status_code == 201, dossier.text
    dossier_sent = c.post(
        f"/api/projects/{pid}/construction/handover/{dossier.json()['id']}/submit",
        json={"version": dossier.json()["version"]},
    )
    assert dossier_sent.status_code == 422, dossier_sent.text
    assert "quality hold blocks handover" in dossier_sent.text
    sign_in(c)
    warehouse = c.post(
        f"/api/projects/{pid}/procurement/warehouses",
        json={"code": "WH-NCR", "name": "Site store", "location": "Yard", "officer_id": me["id"]},
    )
    assert warehouse.status_code == 201, warehouse.text
    sign_in(c, "qa.ncr@alpha.test")
    material_hold = c.post(
        f"/api/projects/{pid}/quality/holds",
        json={
            "number": "QH-3",
            "scope_kind": "receipt",
            "scope_id": line_id,
            "owner_id": stores,
            "reason": "Hold the cable",
            "conditions": "Replace the damaged coil",
            "blocks_issue": True,
        },
    )
    assert material_hold.status_code == 201, material_hold.text
    sign_in(c)
    issued = c.post(
        f"/api/projects/{pid}/procurement/stock/issues",
        json={
            "number": "ISS-NCR",
            "warehouse_id": warehouse.json()["id"],
            "reason": "Install",
            "recipient": "Crew",
            "lines": [{"item_id": item_id, "quantity": "1"}],
        },
    )
    assert issued.status_code == 409, issued.text
    assert "quality hold blocks issue" in issued.text
    with maker() as db:
        closed_note = db.query(Notification).filter_by(title="NCR closed", project_id=pid).first()
        assert closed_note is not None
        assert "certify billing" in closed_note.body
    assert receipt_id


def test_qualification_and_calibration_do_not_certify(env):
    from datetime import date, timedelta

    from fastapi import HTTPException

    from app.domains.identity_projects.models import Project
    from app.domains.quality.competence import assert_inspector
    from app.domains.quality.models import Qualification

    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="QUAL-COMP",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    qa = _user(c, "qa.comp@alpha.test", "QA Comp", me["company_id"])
    engineer = _user(c, "eng.comp@alpha.test", "Eng Comp", me["company_id"])
    reviewer = _user(c, "rev.comp@alpha.test", "Rev Comp", me["company_id"])
    outsider = _user(c, "out.comp@alpha.test", "Out Comp", me["company_id"])
    stores = _user(c, "stores.comp@alpha.test", "Stores Comp", me["company_id"])
    for user_id, role in (
        (qa, "QA/QC"),
        (engineer, "Site Engineer"),
        (reviewer, "Discipline Head"),
        (stores, "Stores Officer"),
        (me["id"], "Project Manager"),
    ):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    blocked = _finding_policy("quality.qualification", civil, outsider, "Qualification")
    blocked["discipline_id"] = None
    assert c.post(f"/api/projects/{pid}/approval-policies", json=blocked).status_code == 422
    today = date.today()
    for record_type in ("quality.qualification", "quality.calibration"):
        policy = _finding_policy(record_type, civil, reviewer, record_type)
        policy["discipline_id"] = None
        policy["stages"][0]["rule"] = "quorum"
        policy["stages"][0]["reviewer_ids"] = [qa, reviewer]
        assert c.post(f"/api/projects/{pid}/approval-policies", json=policy).status_code == 201
    qualification = {
        "number": "Q-1",
        "person_id": engineer,
        "qualification_type": "Concrete inspection",
        "applicable_activities": "Civil pours",
        "issuer": "Your Company",
        "certificate_number": "CERT-1",
        "valid_from": (today - timedelta(days=10)).isoformat(),
        "valid_to": (today + timedelta(days=40)).isoformat(),
        "evidence": "Certificate scanned",
    }
    calibration = {
        "number": "CAL-1",
        "equipment_code": "GAUGE-1",
        "description": "Pressure gauge",
        "serial_number": "SN-1",
        "certificate_reference": "CAL-CERT-1",
        "calibrated_on": (today - timedelta(days=5)).isoformat(),
        "due_on": (today + timedelta(days=10)).isoformat(),
        "use_range": "0 to 10 bar",
        "evidence": "Certificate scanned",
    }
    sign_in(c, "stores.comp@alpha.test")
    assert c.post(f"/api/projects/{pid}/quality/qualifications", json=qualification).status_code == 403
    sign_in(c, "eng.comp@alpha.test")
    assert c.post(f"/api/projects/{pid}/quality/qualifications", json=qualification).status_code == 403
    sign_in(c, "qa.comp@alpha.test")
    backwards = dict(qualification, valid_to=(today - timedelta(days=20)).isoformat())
    assert c.post(f"/api/projects/{pid}/quality/qualifications", json=backwards).status_code == 422
    saved = c.post(f"/api/projects/{pid}/quality/qualifications", json=qualification)
    assert saved.status_code == 201, saved.text
    assert "HR is not the source" in saved.json()["statement"]
    assert "certify billing" in saved.json()["statement"]
    assert c.post(f"/api/projects/{pid}/quality/qualifications", json=qualification).status_code == 409
    sent = c.post(
        f"/api/projects/{pid}/quality/qualifications/{saved.json()['id']}/submit",
        json={"version": saved.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    gauge = c.post(f"/api/projects/{pid}/quality/calibrations", json=calibration)
    assert gauge.status_code == 201, gauge.text
    assert "Equipment management is not the source" in gauge.json()["statement"]
    gauge_sent = c.post(
        f"/api/projects/{pid}/quality/calibrations/{gauge.json()['id']}/submit",
        json={"version": gauge.json()["version"]},
    )
    assert gauge_sent.status_code == 200, gauge_sent.text
    own = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
        ).status_code
        == 403
    )
    sign_in(c, "rev.comp@alpha.test")
    assert (
        c.post(
            f"/api/reviews/{sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
        ).status_code
        == 200
    )
    assert (
        c.post(
            f"/api/reviews/{gauge_sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": gauge_sent.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "qa.comp@alpha.test")
    board = c.get(f"/api/projects/{pid}/quality/dashboard")
    assert board.status_code == 200, board.text
    body = board.json()
    assert body["open_ncrs"] == 0
    assert body["overdue_ncrs"] == 0
    assert body["active_holds"] == 0
    assert body["pending_material_lines"] == 0
    assert body["first_pass"] == {"accepted": 0, "partial": 0, "rejected": 0, "originals": 0, "reinspections": 0}
    assert body["expiring"] == [
        {"kind": "Calibration", "number": "CAL-1", "label": "GAUGE-1", "due": calibration["due_on"], "state": "Expiring"}
    ]
    assert "certify billing" in body["note"]
    again = c.get(f"/api/projects/{pid}/quality/dashboard")
    assert again.status_code == 200, again.text
    with maker() as db:
        notes = db.query(Notification).filter_by(user_id=qa, title="Calibration expiring", project_id=pid).all()
        assert len(notes) == 1
        assert "certify billing" in notes[0].body
        row = db.query(Qualification).filter_by(project_id=pid, number="Q-1").one()
        row.valid_to = today - timedelta(days=1)
        db.commit()
        project = db.get(Project, pid)
        assert_inspector(db, project, me["id"], today)
        try:
            assert_inspector(db, project, engineer, today)
        except HTTPException as exc:
            assert exc.status_code == 422
            assert "qualification valid" in exc.detail
        else:
            raise AssertionError("an expired qualification should block the inspection date")
    expired = c.get(f"/api/projects/{pid}/quality/dashboard")
    assert expired.status_code == 200, expired.text
    assert any(row["state"] == "Expired" and row["number"] == "Q-1" for row in expired.json()["expiring"])
    listed = c.get(f"/api/projects/{pid}/quality/qualifications")
    withdrawn = c.post(
        f"/api/projects/{pid}/quality/qualifications/{listed.json()['qualifications'][0]['id']}/withdraw",
        json={"version": listed.json()["qualifications"][0]["version"], "reason": "Certificate was revoked"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "Withdrawn"
    assert withdrawn.json()["affected"] == []
    gauges = c.get(f"/api/projects/{pid}/quality/calibrations")
    closed = c.post(
        f"/api/projects/{pid}/quality/calibrations/{gauges.json()['calibrations'][0]['id']}/withdraw",
        json={"version": gauges.json()["calibrations"][0]["version"], "reason": "Instrument replaced"},
    )
    assert closed.status_code == 200, closed.text
    assert "Equipment management is not open" in closed.json()["affected_note"]
    final = c.get(f"/api/projects/{pid}/quality/dashboard")
    assert final.status_code == 200, final.text
    assert final.json()["expiring"] == []
    assert final.json()["impacts"][0]["inspections"] == []
    with maker() as db:
        expired_notes = db.query(Notification).filter_by(user_id=qa, title="Qualification expired", project_id=pid).all()
        assert len(expired_notes) == 1


def test_quality_dossier_does_not_authorize_handover_or_billing(env):
    from datetime import date, timedelta

    from app.domains.construction.models import WorkPackage
    from app.domains.quality.models import QualityDocument

    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="QUAL-DOS",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area_id = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    ).json()["id"]
    qa = _user(c, "qa.dos@alpha.test", "QA Dos", me["company_id"])
    engineer = _user(c, "eng.dos@alpha.test", "Eng Dos", me["company_id"])
    reviewer = _user(c, "rev.dos@alpha.test", "Rev Dos", me["company_id"])
    outsider = _user(c, "out.dos@alpha.test", "Out Dos", me["company_id"])
    stores = _user(c, "stores.dos@alpha.test", "Stores Dos", me["company_id"])
    for user_id, role in (
        (qa, "QA/QC"),
        (engineer, "Site Engineer"),
        (reviewer, "Discipline Head"),
        (stores, "Stores Officer"),
        (me["id"], "Project Manager"),
    ):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={
                    "user_id": user_id,
                    "role_id": roles[role],
                    "company_id": me["company_id"],
                    "scope": "ALL",
                    "discipline_ids": [],
                },
            ).status_code
            == 201
        )
    blocked = _finding_policy("quality.dossier", civil, outsider, "Quality dossier")
    blocked["discipline_id"] = None
    assert c.post(f"/api/projects/{pid}/approval-policies", json=blocked).status_code == 422
    for record_type in ("quality.dossier", "quality.punch.close"):
        policy = _finding_policy(record_type, civil, reviewer, record_type)
        policy["discipline_id"] = None
        policy["stages"][0]["rule"] = "quorum"
        policy["stages"][0]["reviewer_ids"] = [qa, reviewer]
        assert c.post(f"/api/projects/{pid}/approval-policies", json=policy).status_code == 201
    sign_in(c, "eng.dos@alpha.test")
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area_id, me["company_id"], civil, code="WP-DOS"),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    kept_status = package.json()["status"]
    with maker() as db:
        from app.domains.identity_projects.models import Project

        project = db.get(Project, pid)
        db.add(
            QualityDocument(
                organization_id=project.organization_id,
                project_id=pid,
                kind="ITP",
                number="ITP-DOS",
                number_key="itp-dos",
                title="Civil inspection",
                revision_label="A",
                revision_key="a",
                discipline_id=civil,
                company_id=me["company_id"],
                status="Approved",
                template_ids=[],
                payload={"revision_label": "A"},
                created_by=me["id"],
            )
        )
        db.commit()
    punch = {
        "number": "P-1",
        "package_id": package_id,
        "issue_type": "Punch",
        "description": "Cover is short",
        "company_id": me["company_id"],
        "owner_id": engineer,
        "severity": "Major",
        "blocking": True,
        "due_on": (date.today() + timedelta(days=3)).isoformat(),
    }
    sign_in(c, "stores.dos@alpha.test")
    assert c.post(f"/api/projects/{pid}/quality/punches", json=punch).status_code == 403
    sign_in(c, "eng.dos@alpha.test")
    assert c.post(f"/api/projects/{pid}/quality/dossiers", json={"number": "QD-1", "package_id": package_id}).status_code == 403
    saved_punch = c.post(f"/api/projects/{pid}/quality/punches", json=punch)
    assert saved_punch.status_code == 201, saved_punch.text
    assert "certify billing" in saved_punch.json()["statement"]
    sign_in(c, "qa.dos@alpha.test")
    saved = c.post(f"/api/projects/{pid}/quality/dossiers", json={"number": "QD-1", "package_id": package_id})
    assert saved.status_code == 201, saved.text
    sent = c.post(
        f"/api/projects/{pid}/quality/dossiers/{saved.json()['id']}/submit",
        json={"version": saved.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    index = sent.json()["payload"]["index"]
    assert any(row["number"] == "ITP-DOS" and row["revision"] == "A" for row in index["procedures"])
    assert any(row["number"] == "P-1" and row["blocking"] for row in index["punches"])
    assert "A blocking punch is still open" in index["gaps"]
    assert "authorize handover" in sent.json()["statement"]
    assert "certify billing" in sent.json()["statement"]
    with maker() as db:
        document = db.query(QualityDocument).filter_by(project_id=pid, number="ITP-DOS").one()
        document.version = 4
        db.commit()
    sign_in(c, "rev.dos@alpha.test")
    changed = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert changed.status_code == 409, changed.text
    assert "quality index changed" in changed.text
    with maker() as db:
        document = db.query(QualityDocument).filter_by(project_id=pid, number="ITP-DOS").one()
        document.version = 1
        db.commit()
    assert (
        c.post(
            f"/api/reviews/{sent.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "qa.dos@alpha.test")
    board = c.get(f"/api/projects/{pid}/quality/dossiers")
    approved = board.json()["dossiers"][0]
    assert approved["status"] == "Approved"
    assert approved["package_status"] == kept_status
    assert any(row["number"] == "P-1" for row in approved["payload"]["index"]["punches"])
    eligible = c.get(f"/api/projects/{pid}/quality/eligibility", params={"package_id": package_id})
    assert eligible.status_code == 200, eligible.text
    assert eligible.json()["package_status"] == kept_status
    assert eligible.json()["approved_dossier"]["number"] == "QD-1"
    assert eligible.json()["blocking_punches"]
    assert "Commissioning is not open" in eligible.json()["handover_note"]
    assert "does not certify billing" in eligible.json()["billing_note"]
    assert eligible.json()["activities"] == []
    closed = c.post(
        f"/api/projects/{pid}/quality/punches/{saved_punch.json()['id']}/close",
        json={"version": saved_punch.json()["version"], "evidence": "Cover restored", "verification": "Measured on site"},
    )
    assert closed.status_code == 200, closed.text
    sign_in(c, "rev.dos@alpha.test")
    assert (
        c.post(
            f"/api/reviews/{closed.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": closed.json()["review"]["version"]},
        ).status_code
        == 200
    )
    sign_in(c, "qa.dos@alpha.test")
    after = c.get(f"/api/projects/{pid}/quality/dossiers").json()["dossiers"][0]
    assert any(row["number"] == "P-1" for row in after["payload"]["index"]["punches"])
    live = c.get(f"/api/projects/{pid}/quality/eligibility", params={"package_id": package_id}).json()
    assert live["blocking_punches"] == []
    with maker() as db:
        package_row = db.get(WorkPackage, package_id)
        assert package_row.status == kept_status
