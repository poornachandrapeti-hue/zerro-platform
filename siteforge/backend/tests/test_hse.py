from datetime import date, datetime, timedelta, timezone

from .test_construction import _package
from .test_engineering import _user, sign_in
from .test_foundation import new_project


def _policy(reviewer_id, record_type):
    return {
        "record_type": record_type,
        "company_id": None,
        "discipline_id": None,
        "allow_self_approval": False,
        "stages": [
            {
                "name": "HSE review",
                "rule": "all",
                "quorum_count": 1,
                "reviewer_ids": [reviewer_id],
                "reviewers": [],
                "purpose": "Review the HSE record",
            }
        ],
    }


def _document(company_id, owner_id, number="HSE-01", revision="A"):
    return {
        "kind": "HSE Plan",
        "number": number,
        "title": "Project HSE plan",
        "revision_label": revision,
        "company_id": company_id,
        "owner_id": owner_id,
        "applicability": "Civil work packages",
        "engineering_reference": "Document control file HSE-PLAN",
    }


def _assessment(company_id, prepared_by, package_id, document_id, number="RA-01"):
    return {
        "number": number,
        "company_id": company_id,
        "package_id": package_id,
        "document_id": document_id,
        "task_description": "Pile cap concrete",
        "steps": "Place and vibrate",
        "hazards": "Fall of material",
        "exposed": "Crew and formwork",
        "existing_controls": "Exclusion zone",
        "initial_rating": "As written: High",
        "additional_controls": "Spotter",
        "residual_rating": "As written: Medium",
        "control_owners": "Supervisor",
        "required_permits": "Named in the site procedure",
        "required_competencies": "Named in the site procedure",
        "prepared_by": prepared_by,
    }


def test_hse_assessment_does_not_authorize_work(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="HSE-1",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(
        f"/api/projects/{pid}/areas",
        json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""},
    )
    assert area.status_code == 201, area.text
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
    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area.json()["id"], me["company_id"], civil, code="WP-H"),
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    assert package.json()["status"] == "Draft"
    outsider = _user(c, "hse-outsider@alpha.test", "HSE Outsider", me["company_id"])
    sign_in(c, "viewer@alpha.test")
    denied = c.post(f"/api/projects/{pid}/hse/documents", json=_document(me["company_id"], uid))
    assert denied.status_code == 403, denied.text
    sign_in(c)
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={
                "user_id": uid,
                "role_id": roles["HSE"],
                "company_id": me["company_id"],
                "scope": "ALL",
                "discipline_ids": [],
            },
        ).status_code
        == 201
    )
    stranger = c.post(f"/api/projects/{pid}/approval-policies", json=_policy(outsider, "hse.document"))
    assert stranger.status_code == 422, stranger.text
    sign_in(c, "viewer@alpha.test")
    draft = c.post(f"/api/projects/{pid}/hse/documents", json=_document(me["company_id"], uid))
    assert draft.status_code == 201, draft.text
    assert "does not authorize work" in draft.json()["statement"]
    missing = c.post(
        f"/api/projects/{pid}/hse/documents/{draft.json()['id']}/submit",
        json={"version": draft.json()["version"]},
    )
    assert missing.status_code == 422, missing.text
    assert "Mandatory reviewer configuration is missing" in missing.text
    sign_in(c)
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_policy(me["id"], "hse.document")).status_code == 201
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_policy(me["id"], "hse.assessment")).status_code == 201
    sign_in(c, "viewer@alpha.test")
    sent = c.post(
        f"/api/projects/{pid}/hse/documents/{draft.json()['id']}/submit",
        json={"version": draft.json()["version"]},
    )
    assert sent.status_code == 200, sent.text
    sign_in(c)
    approved = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert approved.status_code == 200, approved.text
    sign_in(c, "viewer@alpha.test")
    assessment = c.post(
        f"/api/projects/{pid}/hse/assessments",
        json=_assessment(me["company_id"], uid, package_id, draft.json()["id"]),
    )
    assert assessment.status_code == 201, assessment.text
    assert assessment.json()["initial_rating"] == "As written: High"
    assert assessment.json()["residual_rating"] == "As written: Medium"
    assert "does not authorize work" in assessment.json()["statement"]
    assert "does not apply a risk threshold" in assessment.json()["rating_note"]
    sent_assessment = c.post(
        f"/api/projects/{pid}/hse/assessments/{assessment.json()['id']}/submit",
        json={"version": assessment.json()["version"]},
    )
    assert sent_assessment.status_code == 200, sent_assessment.text
    own = c.post(
        f"/api/reviews/{sent_assessment.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent_assessment.json()["review"]["version"]},
    )
    assert own.status_code == 403, own.text
    sign_in(c)
    decided = c.post(
        f"/api/reviews/{sent_assessment.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent_assessment.json()["review"]["version"]},
    )
    assert decided.status_code == 200, decided.text
    board = c.get(f"/api/projects/{pid}/hse").json()
    saved = next(row for row in board["assessments"] if row["number"] == "RA-01")
    assert saved["status"] == "Approved"
    assert saved["package_status"] == "Draft"
    work = c.get(f"/api/projects/{pid}/hse/work", params={"package_id": package_id})
    assert work.status_code == 200, work.text
    assert work.json()["package_status"] == "Draft"
    assert "does not authorize work" in work.json()["note"]
    assert work.json()["assessments"][0]["number"] == "RA-01"
    sign_in(c, "viewer@alpha.test")
    follow = c.post(
        f"/api/projects/{pid}/hse/assessments/{saved['id']}/reassess",
        json={"number": "RA-02", "version": saved["version"]},
    )
    assert follow.status_code == 201, follow.text
    assert follow.json()["status"] == "Draft"
    assert follow.json()["supersedes_id"] == saved["id"]
    still = c.get(f"/api/projects/{pid}/hse").json()
    assert next(row for row in still["assessments"] if row["number"] == "RA-01")["status"] == "Approved"
    sent_follow = c.post(
        f"/api/projects/{pid}/hse/assessments/{follow.json()['id']}/submit",
        json={"version": follow.json()["version"]},
    )
    assert sent_follow.status_code == 200, sent_follow.text
    sign_in(c)
    closed = c.post(
        f"/api/reviews/{sent_follow.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent_follow.json()["review"]["version"]},
    )
    assert closed.status_code == 200, closed.text
    final = c.get(f"/api/projects/{pid}/hse").json()
    assert next(row for row in final["assessments"] if row["number"] == "RA-01")["status"] == "Superseded"
    assert next(row for row in final["assessments"] if row["number"] == "RA-02")["status"] == "Approved"
    assert next(row for row in final["assessments"] if row["number"] == "RA-02")["package_status"] == "Draft"
    links = c.get(f"/api/projects/{pid}/construction/connections")
    assert links.status_code == 200, links.text
    assert "does not authorize work" in links.json()["hse"]["assessment_note"]
    assert any(row["number"] == "RA-02" for row in links.json()["hse"]["assessments"])


def _window(hours_from_now):
    return (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).isoformat()


def test_permit_activation_is_separate_and_blocks_affected_work(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="HSE-PTW",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    pid = created.json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""})
    assert area.status_code == 201, area.text
    area_id = area.json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    for user_id, role in ((uid, "Site Engineer"), (uid, "HSE"), (me["id"], "Project Manager")):
        assert (
            c.post(
                f"/api/projects/{pid}/memberships",
                json={"user_id": user_id, "role_id": roles[role], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
            ).status_code
            == 201
        )
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_policy(me["id"], "hse.permit")).status_code == 201
    hot = c.post(f"/api/projects/{pid}/hse/permit-types", json={"name": "Hot Work", "physical_required": False, "handover_required": True})
    assert hot.status_code == 201, hot.text
    paper = c.post(f"/api/projects/{pid}/hse/permit-types", json={"name": "Confined Space", "physical_required": True, "handover_required": False})
    assert paper.status_code == 201, paper.text
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area_id, me["company_id"], civil, code="WP-P"))
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    other = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area_id, me["company_id"], civil, code="WP-A"))
    assert other.status_code == 201, other.text
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": other.json()["id"],
            "code": "PILE",
            "name": "Piling",
            "quantity": "1",
            "unit": "ea",
            "company_id": me["company_id"],
            "measurement_method": "Item completion",
            "predecessor_ids": [],
        },
    )
    assert activity.status_code == 201, activity.text
    with maker() as db:
        from app.domains.construction.models import WorkHold, WorkPackage

        for row_id in (package_id, other.json()["id"]):
            row = db.get(WorkPackage, row_id)
            row.status = "Ready"
            row.release_state = "Released"
        db.add(WorkHold(project_id=pid, package_id=package_id, reason="Weather", status="Open", opened_by=me["id"]))
        held_package = db.get(WorkPackage, package_id)
        held_package.status = "On Hold"
        db.commit()
    sign_in(c, "viewer@alpha.test")
    body = {
        "type_id": hot.json()["id"],
        "number": "PTW-1",
        "company_id": me["company_id"],
        "area_id": area_id,
        "package_id": package_id,
        "task_description": "Weld the pipe support",
        "applicant_id": uid,
        "performing_authority_id": uid,
        "area_owner_id": me["id"],
        "issuer_id": me["id"],
        "conditions": "Fire watch stays until cool",
        "valid_from": _window(-1),
        "valid_until": _window(48),
        "checks": ["Gas test"],
    }
    draft = c.post(f"/api/projects/{pid}/hse/permits", json=body)
    assert draft.status_code == 201, draft.text
    original_until = draft.json()["valid_until"]
    assert "does not activate" in draft.json()["statement"]
    sent = c.post(f"/api/projects/{pid}/hse/permits/{draft.json()['id']}/submit", json={"version": draft.json()["version"]})
    assert sent.status_code == 200, sent.text
    sign_in(c)
    approved = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert approved.status_code == 200, approved.text
    board = c.get(f"/api/projects/{pid}/hse").json()
    permit = next(row for row in board["permits"] if row["number"] == "PTW-1")
    assert permit["status"] == "Authorized"
    assert permit["package_status"] == "On Hold"
    blocked = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert blocked.status_code == 409, blocked.text
    assert "not active" in blocked.text
    with maker() as db:
        from app.domains.construction.models import WorkHold

        holds = db.query(WorkHold).filter_by(package_id=package_id).one().id
    refused = c.post(f"/api/projects/{pid}/construction/holds/{holds}/resume", json={"version": 1})
    assert refused.status_code == 409, refused.text
    assert "not active" in refused.text
    sign_in(c, "viewer@alpha.test")
    outsider = c.post(f"/api/projects/{pid}/hse/permits/{permit['id']}/activate", json={"version": permit["version"]})
    assert outsider.status_code == 403, outsider.text
    sign_in(c)
    bare = c.post(f"/api/projects/{pid}/hse/permits/{permit['id']}/activate", json={"version": permit["version"]})
    assert bare.status_code == 409, bare.text
    assert "Gas test" in bare.text
    checked = c.post(
        f"/api/projects/{pid}/hse/permits/{permit['id']}/checks/{permit['checks'][0]['id']}/verify",
        json={"evidence": "Reading 0% LEL", "acknowledged": True},
    )
    assert checked.status_code == 200, checked.text
    active = c.post(f"/api/projects/{pid}/hse/permits/{permit['id']}/activate", json={"version": checked.json()["version"]})
    assert active.status_code == 200, active.text
    assert active.json()["status"] == "Active"
    assert active.json()["package_status"] == "On Hold"
    clear = c.get(f"/api/projects/{pid}/hse/work", params={"package_id": package_id})
    assert clear.json()["permit_block"] == ""
    with maker() as db:
        from app.domains.hse.models import HsePermit

        row = db.query(HsePermit).filter_by(project_id=pid, number="PTW-1").one()
        row.valid_until = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()
        expired_version = row.version
    expired = c.post(f"/api/projects/{pid}/construction/holds/{holds}/resume", json={"version": 1})
    assert expired.status_code == 409, expired.text
    assert "expired" in expired.text
    current = next(row for row in c.get(f"/api/projects/{pid}/hse").json()["permits"] if row["number"] == "PTW-1")
    extended = c.post(
        f"/api/projects/{pid}/hse/permits/{current['id']}/extend",
        json={"version": current["version"], "valid_until": _window(120), "reason": "Work continued the next shift"},
    )
    assert extended.status_code == 200, extended.text
    assert extended.json()["valid_until"] == current["valid_until"]
    assert extended.json()["status"] == "Authorized"
    assert any(row["kind"] == "Extension" for row in extended.json()["events"])
    assert expired_version
    still = c.post(f"/api/projects/{pid}/construction/holds/{holds}/resume", json={"version": 1})
    assert still.status_code == 409, still.text
    assert "not active" in still.text
    again = c.post(f"/api/projects/{pid}/hse/permits/{current['id']}/activate", json={"version": extended.json()["version"]})
    assert again.status_code == 200, again.text
    isolation = c.post(
        f"/api/projects/{pid}/hse/isolations",
        json={"kind": "Isolation Certificate", "number": "ISO-1", "authority_id": uid, "area_id": area_id, "evidence": "Locks applied"},
    )
    assert isolation.status_code == 201, isolation.text
    sign_in(c, "viewer@alpha.test")
    linked = c.post(f"/api/projects/{pid}/hse/permits/{current['id']}/isolations", json={"isolation_id": isolation.json()["id"]})
    assert linked.status_code == 200, linked.text
    second = c.post(
        f"/api/projects/{pid}/hse/permits",
        json={**body, "number": "PTW-2", "package_id": None, "checks": []},
    )
    assert second.status_code == 201, second.text
    c.post(f"/api/projects/{pid}/hse/permits/{second.json()['id']}/isolations", json={"isolation_id": isolation.json()["id"]})
    sign_in(c)
    forced = c.post(f"/api/projects/{pid}/hse/isolations/{isolation.json()['id']}/approve", json={"version": isolation.json()["version"]})
    assert forced.status_code == 200, forced.text
    assert forced.json()["status"] == "In Force"
    assert len(forced.json()["permit_ids"]) == 2
    sign_in(c, "viewer@alpha.test")
    kept = c.post(
        f"/api/projects/{pid}/hse/isolations/{isolation.json()['id']}/remove",
        json={"version": forced.json()["version"], "reason": "Work finished"},
    )
    assert kept.status_code == 409, kept.text
    assert "depends" in kept.text
    sign_in(c)
    same = c.post(
        f"/api/projects/{pid}/hse/isolations/{isolation.json()['id']}/remove",
        json={"version": forced.json()["version"], "reason": "Work finished"},
    )
    assert same.status_code == 403, same.text
    sign_in(c, "viewer@alpha.test")
    scoped = c.post(
        f"/api/projects/{pid}/hse/permits",
        json={**body, "number": "PTW-ACT", "package_id": other.json()["id"], "activity_id": activity.json()["id"], "area_id": None, "checks": []},
    )
    assert scoped.status_code == 201, scoped.text
    sent_scoped = c.post(f"/api/projects/{pid}/hse/permits/{scoped.json()['id']}/submit", json={"version": scoped.json()["version"]})
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{sent_scoped.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": sent_scoped.json()["review"]["version"]},
        ).status_code
        == 200
    )
    started = c.post(f"/api/projects/{pid}/construction/packages/{other.json()['id']}/start", json={"version": 1})
    assert started.status_code == 409, started.text
    assert "readiness" in started.text
    rule = c.post(
        f"/api/projects/{pid}/hse/conflict-rules",
        json={"type_a_id": hot.json()["id"], "type_b_id": hot.json()["id"], "same_area": True, "require_decision": True, "note": "Two hot-work permits in one area"},
    )
    assert rule.status_code == 201, rule.text
    sign_in(c, "viewer@alpha.test")
    overlap = c.post(f"/api/projects/{pid}/hse/permits", json={**body, "number": "PTW-HOT", "package_id": None, "checks": [], "valid_until": _window(20)})
    assert overlap.status_code == 201, overlap.text
    sent_hot = c.post(f"/api/projects/{pid}/hse/permits/{overlap.json()['id']}/submit", json={"version": overlap.json()["version"]})
    sign_in(c)
    assert (
        c.post(
            f"/api/reviews/{sent_hot.json()['review']['id']}/decisions",
            json={"action": "approve", "reason": "", "comment": "", "version": sent_hot.json()["review"]["version"]},
        ).status_code
        == 200
    )
    hot_row = next(row for row in c.get(f"/api/projects/{pid}/hse").json()["permits"] if row["number"] == "PTW-HOT")
    waiting = c.post(f"/api/projects/{pid}/hse/permits/{hot_row['id']}/activate", json={"version": hot_row["version"]})
    assert waiting.status_code == 409, waiting.text
    assert "coordination" in waiting.text
    sign_in(c, "viewer@alpha.test")
    decided = c.post(
        f"/api/projects/{pid}/hse/permits/{hot_row['id']}/coordination",
        json={"other_permit_id": current["id"], "decision": "Separate fire watches", "controls": "Two metre gap"},
    )
    assert decided.status_code == 200, decided.text
    sign_in(c)
    opened = c.post(f"/api/projects/{pid}/hse/permits/{hot_row['id']}/activate", json={"version": hot_row["version"]})
    assert opened.status_code == 200, opened.text
    assert "every hazard" in c.get(f"/api/projects/{pid}/hse").json()["simops_note"]
    assert original_until


def test_eligibility_toolbox_and_findings_follow_saved_rules(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="HSE-FLD",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U2", "name": "Unit 2", "area_type": "Unit", "description": ""})
    assert area.status_code == 201, area.text
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    assert (
        c.post(
            f"/api/projects/{pid}/memberships",
            json={"user_id": uid, "role_id": roles["HSE"], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
        ).status_code
        == 201
    )
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area.json()["id"], me["company_id"], civil, code="WP-F"))
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": package_id,
            "code": "DECK",
            "name": "Deck",
            "quantity": "1",
            "unit": "ea",
            "company_id": me["company_id"],
            "measurement_method": "Item completion",
            "predecessor_ids": [],
        },
    )
    assert activity.status_code == 201, activity.text
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, package_id)
        row.status = "Ready"
        row.release_state = "Released"
        db.commit()
    open_start = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert open_start.status_code == 409, open_start.text
    assert "readiness" in open_start.text
    today = datetime.now(timezone.utc).date().isoformat()
    activity_rule = c.post(
        f"/api/projects/{pid}/hse/toolbox-rules",
        json={"package_id": package_id, "activity_id": activity.json()["id"]},
    )
    assert activity_rule.status_code == 201, activity_rule.text
    still_open = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert still_open.status_code == 409 and "readiness" in still_open.text
    package_rule = c.post(f"/api/projects/{pid}/hse/toolbox-rules", json={"package_id": package_id})
    assert package_rule.status_code == 201, package_rule.text
    needs_talk = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert needs_talk.status_code == 409 and "Toolbox" in needs_talk.text
    sign_in(c, "viewer@alpha.test")
    talk = c.post(
        f"/api/projects/{pid}/hse/toolbox",
        json={
            "number": "TBT-1",
            "talk_on": today,
            "shift": "Day",
            "company_id": me["company_id"],
            "package_id": package_id,
            "topic": "Deck edge",
            "presenter_id": uid,
            "issues": "Loose boards",
            "follow_up": "Refix before the next shift",
        },
    )
    assert talk.status_code == 201, talk.text
    assert "crew assignment" in talk.json()["statement"]
    assert "not an action" in talk.json()["follow_up_note"]
    held = c.post(f"/api/projects/{pid}/hse/toolbox/{talk.json()['id']}/hold", json={"version": talk.json()["version"]})
    assert held.status_code == 200, held.text
    sign_in(c)
    still_needs = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert "Toolbox" in still_needs.text
    sign_in(c, "viewer@alpha.test")
    acked = c.post(
        f"/api/projects/{pid}/hse/toolbox/{talk.json()['id']}/acknowledgments",
        json={"member_id": uid, "evidence": "Signed the sheet"},
    )
    assert acked.status_code == 201, acked.text
    assert acked.json()["acknowledgments"][0]["member_name"]
    sign_in(c)
    covered = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert covered.status_code == 409 and "readiness" in covered.text
    rule = c.post(f"/api/projects/{pid}/hse/eligibility-rules", json={"category": "Site Induction", "package_id": package_id})
    assert rule.status_code == 201, rule.text
    kind = c.post(f"/api/projects/{pid}/hse/permit-types", json={"name": "Hot Work"})
    assert kind.status_code == 201, kind.text
    sign_in(c, "viewer@alpha.test")
    blocked_assignment = c.post(
        f"/api/projects/{pid}/hse/permits",
        json={
            "type_id": kind.json()["id"],
            "number": "PTW-E",
            "company_id": me["company_id"],
            "package_id": package_id,
            "task_description": "Weld the deck edge",
            "applicant_id": uid,
            "performing_authority_id": uid,
            "area_owner_id": uid,
            "issuer_id": uid,
            "valid_from": _window(-1),
            "valid_until": _window(24),
            "checks": [],
        },
    )
    assert blocked_assignment.status_code == 409, blocked_assignment.text
    assert "Site Induction" in blocked_assignment.text
    recorded = c.post(
        f"/api/projects/{pid}/hse/eligibility",
        json={"member_id": uid, "category": "Site Induction", "evidence": "Card checked at the gate", "expires_on": (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()},
    )
    assert recorded.status_code == 201, recorded.text
    assert "Medical detail is not stored" in recorded.json()["statement"]
    own = c.post(f"/api/projects/{pid}/hse/eligibility/{recorded.json()['id']}/verify", json={"version": recorded.json()["version"]})
    assert own.status_code == 403 and "own eligibility" in own.text
    sign_in(c)
    verified = c.post(f"/api/projects/{pid}/hse/eligibility/{recorded.json()['id']}/verify", json={"version": recorded.json()["version"]})
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "Verified"
    sign_in(c, "viewer@alpha.test")
    allowed = c.post(
        f"/api/projects/{pid}/hse/permits",
        json={
            "type_id": kind.json()["id"],
            "number": "PTW-E",
            "company_id": me["company_id"],
            "package_id": package_id,
            "task_description": "Weld the deck edge",
            "applicant_id": uid,
            "performing_authority_id": uid,
            "area_owner_id": uid,
            "issuer_id": uid,
            "valid_from": _window(-1),
            "valid_until": _window(24),
            "checks": [],
        },
    )
    assert allowed.status_code == 201, allowed.text
    with maker() as db:
        from app.domains.hse.models import HseEligibility

        evidence = db.query(HseEligibility).filter_by(project_id=pid, member_id=uid).one()
        evidence.expires_on = datetime.now(timezone.utc).date() - timedelta(days=1)
        kept = evidence.evidence
        db.commit()
    sign_in(c)
    board = c.get(f"/api/projects/{pid}/hse").json()
    expired = next(row for row in board["eligibility"] if row["id"] == recorded.json()["id"])
    assert expired["status"] == "Expired"
    assert expired["evidence"] == kept
    sign_in(c, "viewer@alpha.test")
    again = c.post(
        f"/api/projects/{pid}/hse/permits",
        json={
            "type_id": kind.json()["id"],
            "number": "PTW-E2",
            "company_id": me["company_id"],
            "package_id": package_id,
            "task_description": "Weld the next bay",
            "applicant_id": uid,
            "performing_authority_id": uid,
            "area_owner_id": uid,
            "issuer_id": uid,
            "valid_from": _window(-1),
            "valid_until": _window(24),
            "checks": [],
        },
    )
    assert again.status_code == 409 and "Site Induction" in again.text
    noted = c.post(
        f"/api/projects/{pid}/hse/inspections",
        json={
            "number": "SI-1",
            "inspection_type": "Workfront",
            "company_id": me["company_id"],
            "package_id": package_id,
            "inspector_id": uid,
            "inspected_on": today,
            "findings": [{"description": "Open edge", "severity": "Stop", "owner_id": uid, "action": "Barricade", "photo_reference": "Photo SI-1"}],
        },
    )
    assert noted.status_code == 201, noted.text
    sign_in(c)
    quiet = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert quiet.status_code == 409 and "readiness" in quiet.text
    severity = c.post(f"/api/projects/{pid}/hse/finding-rules", json={"severity": "Stop", "blocks_work": True})
    assert severity.status_code == 201, severity.text
    held_work = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert held_work.status_code == 409 and "not a safety-hold" in held_work.text
    sign_in(c, "viewer@alpha.test")
    refused = c.post(
        f"/api/projects/{pid}/hse/findings/{noted.json()['findings'][0]['id']}/close",
        json={"version": noted.json()["findings"][0]["version"], "evidence": "Barricade in place"},
    )
    assert refused.status_code == 403 and "separate" in refused.text
    sign_in(c)
    closed = c.post(
        f"/api/projects/{pid}/hse/findings/{noted.json()['findings'][0]['id']}/close",
        json={"version": noted.json()["findings"][0]["version"], "evidence": "Barricade in place"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "Closed"
    released = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert released.status_code == 409 and "readiness" in released.text
    sign_in(c, "viewer@alpha.test")
    extra = c.post(
        f"/api/projects/{pid}/hse/observations",
        json={"number": "OB-1", "observation_type": "Unsafe Condition", "description": "Missing toe board", "diagnosis": "sprained ankle"},
    )
    assert extra.status_code == 422, extra.text
    observation = c.post(
        f"/api/projects/{pid}/hse/observations",
        json={"number": "OB-1", "observation_type": "Unsafe Condition", "description": "Missing toe board"},
    )
    assert observation.status_code == 201, observation.text
    assert observation.json()["status"] == "Reported"
    assert "does not start an investigation" in observation.json()["statement"]
    sign_in(c)
    links = c.get(f"/api/projects/{pid}/construction/connections")
    assert links.status_code == 200, links.text
    assert "not a safety-hold release" in links.json()["hse"]["field_note"]


def test_incident_report_and_action_closure_are_separate(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="HSE-INC",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""})
    assert area.status_code == 201, area.text
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area.json()["id"], me["company_id"], civil, code="WP-I"))
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.identity_projects.models import User

        row = db.get(WorkPackage, package_id)
        row.status = "Ready"
        row.release_state = "Released"
        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
        db.commit()
    client = _user(c, "client-hse@alpha.test", "Client Reviewer", me["company_id"])
    assert c.post(
        f"/api/projects/{pid}/memberships",
        json={"user_id": uid, "role_id": roles["HSE"], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
    ).status_code == 201
    assert c.post(
        f"/api/projects/{pid}/memberships",
        json={"user_id": client, "role_id": roles["Client/PMC Reviewer"], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
    ).status_code == 201
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_policy(uid, "hse.incident")).status_code == 201
    category = c.post(f"/api/projects/{pid}/hse/incident-categories", json={"name": "Near Miss"})
    assert category.status_code == 201, category.text
    rule = c.post(f"/api/projects/{pid}/hse/incident-rules", json={"severity": "Serious", "requires_investigation": True})
    assert rule.status_code == 201, rule.text
    open_start = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert open_start.status_code == 409 and "readiness" in open_start.text
    sign_in(c, "client-hse@alpha.test")
    medical = c.post(
        f"/api/projects/{pid}/hse/incidents",
        json={
            "category_id": category.json()["id"],
            "number": "INC-1",
            "event_at": _window(-2),
            "timezone_name": "IST",
            "company_id": me["company_id"],
            "package_id": package_id,
            "description": "A load swung past the exclusion zone",
            "initial_severity": "Serious",
            "diagnosis": "bruised shoulder",
        },
    )
    assert medical.status_code == 422, medical.text
    report = c.post(
        f"/api/projects/{pid}/hse/incidents",
        json={
            "category_id": category.json()["id"],
            "number": "INC-1",
            "event_at": _window(-2),
            "timezone_name": "IST",
            "company_id": me["company_id"],
            "package_id": package_id,
            "description": "A load swung past the exclusion zone",
            "initial_severity": "Serious",
            "immediate_actions": "Stopped the lift",
        },
    )
    assert report.status_code == 201, report.text
    assert report.json()["status"] == "Reported"
    assert "emergency" in report.json()["statement"] and "Medical" in report.json()["statement"]
    blocked = c.post(
        f"/api/projects/{pid}/hse/incidents/{report.json()['id']}/investigate",
        json={"version": report.json()["version"], "verified_classification": "Near Miss", "team_ids": [uid]},
    )
    assert blocked.status_code == 403, blocked.text
    sign_in(c, "viewer@alpha.test")
    early = c.post(f"/api/projects/{pid}/hse/incidents/{report.json()['id']}/submit", json={"version": report.json()["version"]})
    assert early.status_code == 409 and "investigation" in early.text
    looked = c.post(
        f"/api/projects/{pid}/hse/incidents/{report.json()['id']}/investigate",
        json={
            "version": report.json()["version"],
            "verified_classification": "Near Miss",
            "contributing_factors": "The zone was not marked",
            "root_causes": "The lift plan was not at the workfront",
            "lessons": "Keep the lift plan with the crew",
            "team_ids": [uid],
        },
    )
    assert looked.status_code == 200, looked.text
    assert looked.json()["description"] == "A load swung past the exclusion zone"
    assert looked.json()["status"] == "Under Investigation"
    sent = c.post(f"/api/projects/{pid}/hse/incidents/{report.json()['id']}/submit", json={"version": looked.json()["version"]})
    assert sent.status_code == 200, sent.text
    own = c.post(
        f"/api/reviews/{sent.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": sent.json()["review"]["version"]},
    )
    assert own.status_code == 403 and "own" in own.text
    sign_in(c)
    still = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert still.status_code == 409 and "readiness" in still.text
    board = c.get(f"/api/projects/{pid}/hse").json()
    incident = next(row for row in board["incidents"] if row["number"] == "INC-1")
    assert incident["status"] == "Pending Closure"
    assert incident["package_status"] != "On Hold"
    assert board["counts"]["incidents"] >= 1
    assert "exposure hours" in board["incident_note"]
    action = c.post(
        f"/api/projects/{pid}/hse/actions",
        json={
            "number": "CA-1",
            "description": "Mark the exclusion zone before the next lift",
            "severity": "Serious",
            "company_id": me["company_id"],
            "owner_id": client,
            "verifier_id": uid,
            "source_type": "hse.incident",
            "source_id": report.json()["id"],
            "interim_controls": "Lift stays stopped",
        },
    )
    assert action.status_code == 201, action.text
    assert action.json()["status"] == "Open"
    assert action.json()["task_id"]
    sign_in(c, "client-hse@alpha.test")
    finished = c.post(
        f"/api/tasks/{action.json()['task_id']}",
        json={"status": "Completed", "evidence": "Marked on the generic task", "version": 1},
    )
    assert finished.status_code == 200, finished.text
    sign_in(c)
    unchanged = next(row for row in c.get(f"/api/projects/{pid}/hse").json()["actions"] if row["number"] == "CA-1")
    assert unchanged["status"] == "Open"
    assert unchanged["task_status"] == "Completed"
    sign_in(c, "client-hse@alpha.test")
    evidenced = c.post(
        f"/api/projects/{pid}/hse/actions/{action.json()['id']}/evidence",
        json={"version": unchanged["version"], "evidence": "Zone painted and photographed"},
    )
    assert evidenced.status_code == 200, evidenced.text
    assert evidenced.json()["status"] == "Pending Verification"
    owner_close = c.post(
        f"/api/projects/{pid}/hse/actions/{action.json()['id']}/close",
        json={"version": evidenced.json()["version"], "effectiveness": ""},
    )
    assert owner_close.status_code == 403, owner_close.text
    sign_in(c)
    admin_close = c.post(
        f"/api/projects/{pid}/hse/actions/{action.json()['id']}/close",
        json={"version": evidenced.json()["version"], "effectiveness": ""},
    )
    assert admin_close.status_code == 403, admin_close.text
    sign_in(c, "viewer@alpha.test")
    closed = c.post(
        f"/api/projects/{pid}/hse/actions/{action.json()['id']}/close",
        json={"version": evidenced.json()["version"], "effectiveness": ""},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "Closed"
    sign_in(c)
    saved = c.post(f"/api/projects/{pid}/hse/action-rules", json={"effectiveness_required": True})
    assert saved.status_code == 201, saved.text
    second = c.post(
        f"/api/projects/{pid}/hse/actions",
        json={
            "number": "CA-2",
            "description": "File the lift plan at the workfront",
            "severity": "Serious",
            "company_id": me["company_id"],
            "owner_id": client,
            "verifier_id": uid,
        },
    )
    assert second.status_code == 201, second.text
    sign_in(c, "client-hse@alpha.test")
    second_evidence = c.post(
        f"/api/projects/{pid}/hse/actions/{second.json()['id']}/evidence",
        json={"version": second.json()["version"], "evidence": "Plan is in the box"},
    )
    assert second_evidence.status_code == 200, second_evidence.text
    sign_in(c, "viewer@alpha.test")
    missing = c.post(
        f"/api/projects/{pid}/hse/actions/{second.json()['id']}/close",
        json={"version": second_evidence.json()["version"], "effectiveness": ""},
    )
    assert missing.status_code == 422, missing.text
    verified = c.post(
        f"/api/projects/{pid}/hse/actions/{second.json()['id']}/close",
        json={"version": second_evidence.json()["version"], "effectiveness": "The plan was still in the box the next shift"},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "Closed"
    sign_in(c)
    links = c.get(f"/api/projects/{pid}/construction/connections")
    assert links.status_code == 200, links.text
    assert "does not hold" in links.json()["hse"]["incident_note"]


def _hold(company_id, owner_id, package_id, number, **extra):
    body = {
        "number": number,
        "company_id": company_id,
        "owner_id": owner_id,
        "reason": "Open edge on the deck",
        "source": "Field",
        "severity": "Stop",
        "scope_kind": "package",
        "package_id": package_id,
        "restricted_actions": "Start and resume",
        "release_conditions": "Edge protected and checked",
    }
    body.update(extra)
    return body


def test_safety_hold_blocks_until_a_saved_authority_releases_it(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="HSE-HOLD",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""})
    assert area.status_code == 201, area.text
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area.json()["id"], me["company_id"], civil, code="WP-H"))
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={
            "package_id": package_id,
            "code": "EDGE",
            "name": "Edge protection",
            "quantity": "1",
            "unit": "ea",
            "company_id": me["company_id"],
            "measurement_method": "Item completion",
            "predecessor_ids": [],
        },
    )
    assert activity.status_code == 201, activity.text
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.identity_projects.models import User

        row = db.get(WorkPackage, package_id)
        row.status = "Ready"
        row.release_state = "Released"
        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
        db.commit()
    client = _user(c, "client-hold@alpha.test", "Hold Owner", me["company_id"])
    site = _user(c, "site-hold@alpha.test", "Site Authority", me["company_id"])
    for user_id, role in ((uid, "HSE"), (client, "Client/PMC Reviewer"), (site, "Site Engineer")):
        assert c.post(
            f"/api/projects/{pid}/memberships",
            json={"user_id": user_id, "role_id": roles[role], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
        ).status_code == 201
    refused = c.post(f"/api/projects/{pid}/hse/holds", json=_hold(me["company_id"], client, package_id, "SH-P"))
    assert refused.status_code == 409 and "formal hold" in refused.text
    assert c.post(f"/api/projects/{pid}/hse/hold-issuers", json={"user_id": uid}).status_code == 201
    sign_in(c, "viewer@alpha.test")
    self_hold = c.post(
        f"/api/projects/{pid}/hse/holds",
        json=_hold(me["company_id"], uid, None, "SH-SELF", scope_kind="equipment", equipment_note="Crane CR-1"),
    )
    assert self_hold.status_code == 201, self_hold.text
    sign_in(c)
    assert c.post(f"/api/projects/{pid}/hse/hold-rules", json={"separate_release": True}).status_code == 201
    sign_in(c, "viewer@alpha.test")
    issuer_release = c.post(
        f"/api/projects/{pid}/hse/holds/{self_hold.json()['id']}/release",
        json={"version": self_hold.json()["version"], "evidence": "Crane inspected"},
    )
    assert issuer_release.status_code == 422 and "issuer" in issuer_release.text
    same_owner = c.post(
        f"/api/projects/{pid}/hse/holds",
        json=_hold(me["company_id"], uid, None, "SH-SAME", scope_kind="equipment", equipment_note="Crane CR-2"),
    )
    assert same_owner.status_code == 422 and "owner" in same_owner.text
    sign_in(c)
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_policy(site, "hse.hold")).status_code == 201
    sign_in(c, "client-hold@alpha.test")
    concern = c.post(
        f"/api/projects/{pid}/hse/concerns",
        json={"number": "SH-C", "company_id": me["company_id"], "reason": "Loose board seen at the edge", "package_id": package_id},
    )
    assert concern.status_code == 201, concern.text
    assert concern.json()["status"] == "Reported"
    assert "does not issue a formal hold" in concern.json()["statement"]
    outsider = c.post(f"/api/projects/{pid}/hse/holds", json=_hold(me["company_id"], client, package_id, "SH-P"))
    assert outsider.status_code == 403, outsider.text
    sign_in(c)
    admin_hold = c.post(f"/api/projects/{pid}/hse/holds", json=_hold(me["company_id"], client, package_id, "SH-P"))
    assert admin_hold.status_code == 403, admin_hold.text
    open_start = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert open_start.status_code == 409 and "readiness" in open_start.text
    sign_in(c, "viewer@alpha.test")
    equipment = c.post(
        f"/api/projects/{pid}/hse/holds",
        json=_hold(me["company_id"], client, None, "SH-E", scope_kind="equipment", equipment_note="Crane CR-1"),
    )
    assert equipment.status_code == 201, equipment.text
    assert "equipment register is not open" in equipment.json()["statement"]
    sign_in(c)
    still_open = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert still_open.status_code == 409 and "readiness" in still_open.text
    sign_in(c, "viewer@alpha.test")
    activity_hold = c.post(
        f"/api/projects/{pid}/hse/holds",
        json=_hold(me["company_id"], client, package_id, "SH-ACT", scope_kind="activity", activity_id=activity.json()["id"]),
    )
    assert activity_hold.status_code == 201, activity_hold.text
    sign_in(c)
    activity_start = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert activity_start.status_code == 409 and "readiness" in activity_start.text
    sign_in(c, "viewer@alpha.test")
    placed = c.post(f"/api/projects/{pid}/hse/holds", json=_hold(me["company_id"], client, package_id, "SH-P"))
    assert placed.status_code == 201, placed.text
    assert placed.json()["status"] == "Active"
    assert placed.json()["package_status"] == "Ready"
    assert "does not start the work" in placed.json()["statement"]
    own_release = c.post(
        f"/api/projects/{pid}/hse/holds/{placed.json()['id']}/release",
        json={"version": placed.json()["version"], "evidence": "Edge is barricaded"},
    )
    assert own_release.status_code == 403 and "owner" in own_release.text
    sign_in(c)
    blocked = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert blocked.status_code == 409 and "SH-P" in blocked.text and "does not clear" in blocked.text
    with maker() as db:
        from app.domains.coordination.models import Notification

        assert db.query(Notification).filter_by(user_id=uid, title="A safety hold is active").count() >= 1
    sign_in(c, "client-hold@alpha.test")
    asked = c.post(
        f"/api/projects/{pid}/hse/holds/{placed.json()['id']}/release",
        json={"version": placed.json()["version"], "evidence": "Edge is barricaded"},
    )
    assert asked.status_code == 200, asked.text
    assert asked.json()["status"] == "Release Requested"
    sign_in(c)
    still_blocked = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert still_blocked.status_code == 409 and "SH-P" in still_blocked.text
    sign_in(c, "viewer@alpha.test")
    issuer_decision = c.post(
        f"/api/reviews/{asked.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": asked.json()["review"]["version"]},
    )
    assert issuer_decision.status_code == 403, issuer_decision.text
    sign_in(c)
    admin_decision = c.post(
        f"/api/reviews/{asked.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": asked.json()["review"]["version"]},
    )
    assert admin_decision.status_code == 403, admin_decision.text
    sign_in(c, "site-hold@alpha.test")
    released = c.post(
        f"/api/reviews/{asked.json()['review']['id']}/decisions",
        json={"action": "approve", "reason": "", "comment": "", "version": asked.json()["review"]["version"]},
    )
    assert released.status_code == 200, released.text
    sign_in(c)
    board = c.get(f"/api/projects/{pid}/hse").json()
    hold = next(row for row in board["holds"] if row["number"] == "SH-P")
    assert hold["status"] == "Released"
    assert hold["package_status"] == "Ready"
    assert any(item["kind"] == "Released" for item in hold["events"])
    assert any(item["kind"] == "Issued" for item in hold["events"])
    restarted = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert restarted.status_code == 409 and "readiness" in restarted.text
    sign_in(c, "viewer@alpha.test")
    area_hold = c.post(
        f"/api/projects/{pid}/hse/holds",
        json=_hold(me["company_id"], client, None, "SH-A", scope_kind="area", area_id=area.json()["id"]),
    )
    assert area_hold.status_code == 201, area_hold.text
    sign_in(c)
    area_block = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert area_block.status_code == 409 and "SH-A" in area_block.text
    links = c.get(f"/api/projects/{pid}/construction/connections")
    assert "does not start the work" in links.json()["hse"]["hold_note"]
    assert board["counts"]["active_holds"] >= 1


def test_emergency_records_do_not_start_the_response_or_hold_work(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="HSE-EMERG",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""})
    assert area.status_code == 201, area.text
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area.json()["id"], me["company_id"], civil, code="WP-E"))
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.identity_projects.models import User

        row = db.get(WorkPackage, package_id)
        row.status = "Ready"
        row.release_state = "Released"
        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
        db.commit()
    client = _user(c, "client-emerg@alpha.test", "Emergency Reader", me["company_id"])
    for user_id, role in ((uid, "HSE"), (client, "Client/PMC Reviewer")):
        assert c.post(
            f"/api/projects/{pid}/memberships",
            json={"user_id": user_id, "role_id": roles[role], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
        ).status_code == 201
    warden = c.post(
        f"/api/projects/{pid}/contacts",
        json={"name": "Gate Warden", "function": "Safety", "user_id": uid, "phone": "9000000001", "email": "warden@alpha.test"},
    )
    assert warden.status_code == 201, warden.text
    nurse = c.post(
        f"/api/projects/{pid}/contacts",
        json={"name": "Plant Nurse", "function": "Safety", "phone": "9000000002", "email": "nurse@alpha.test"},
    )
    assert nurse.status_code == 201, nurse.text
    sign_in(c, "client-emerg@alpha.test")
    refused = c.post(f"/api/projects/{pid}/hse/emergency-rules", json={"procedure": "Radio channel 1", "review_days": 30})
    assert refused.status_code == 403, refused.text
    sign_in(c, "viewer@alpha.test")
    saved = c.post(f"/api/projects/{pid}/hse/emergency-rules", json={"procedure": "Radio channel 1, then the site siren", "review_days": 30})
    assert saved.status_code == 201, saved.text
    copied = c.post(
        f"/api/projects/{pid}/hse/emergency-contacts",
        json={"contact_id": warden.json()["id"], "response_role": "Muster warden", "phone": "9000000001"},
    )
    assert copied.status_code == 422, copied.text
    own = c.post(
        f"/api/projects/{pid}/hse/emergency-contacts",
        json={"contact_id": warden.json()["id"], "response_role": "Muster warden"},
    )
    assert own.status_code == 201, own.text
    assert own.json()["phone"] is None
    assert "does not copy" in own.json()["statement"]
    linked = c.post(
        f"/api/projects/{pid}/hse/emergency-contacts",
        json={"contact_id": nurse.json()["id"], "response_role": "First aid"},
    )
    assert linked.status_code == 201, linked.text
    self_check = c.post(f"/api/projects/{pid}/hse/emergency-contacts/{own.json()['id']}/verify", json={"version": own.json()["version"]})
    assert self_check.status_code == 403 and "own" in self_check.text
    sign_in(c)
    verified = c.post(
        f"/api/projects/{pid}/hse/emergency-contacts/{linked.json()['id']}/verify",
        json={"version": linked.json()["version"]},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "Verified"
    assert verified.json()["phone"] == "9000000002"
    assert verified.json()["version"] == 2
    with maker() as db:
        from app.domains.hse.models import HseEmergencyContact

        row = db.get(HseEmergencyContact, linked.json()["id"])
        row.review_due_on = date.today() - timedelta(days=1)
        db.commit()
    board = c.get(f"/api/projects/{pid}/hse")
    assert board.status_code == 200, board.text
    body = board.json()
    due = next(row for row in body["emergency_contacts"] if row["name"] == "Plant Nurse")
    assert due["status"] == "Review due"
    assert due["stored_status"] == "Verified"
    assert due["version"] == 2
    assert body["counts"]["emergency_reviews_due"] >= 1
    assert "does not place the emergency call" in body["emergency_note"]
    again = c.get(f"/api/projects/{pid}/hse")
    assert again.status_code == 200
    with maker() as db:
        from app.domains.coordination.models import Notification
        from app.domains.hse.models import HseAction

        notices = db.query(Notification).filter_by(user_id=uid, title="Emergency contact review is due").count()
        assert notices == 1
        assert db.query(HseAction).filter_by(project_id=pid).count() == 0
    sign_in(c, "viewer@alpha.test")
    hidden = c.get(f"/api/projects/{pid}/hse").json()
    shown = next(row for row in hidden["emergency_contacts"] if row["name"] == "Plant Nurse")
    assert shown["phone"] is None
    muster = c.post(f"/api/projects/{pid}/hse/muster-points", json={"name": "North gate", "note": "Outside the fence"})
    assert muster.status_code == 201, muster.text
    gear = c.post(f"/api/projects/{pid}/hse/emergency-gear", json={"name": "Stretcher", "location": "Control room cupboard"})
    assert gear.status_code == 201, gear.text
    assert "equipment register is not the source" in gear.json()["statement"]
    plan = c.post(
        f"/api/projects/{pid}/hse/emergency-plans",
        json={"number": "EP-01", "title": "Site emergency plan", "engineering_reference": "Document control file EP-01"},
    )
    assert plan.status_code == 201, plan.text
    drill = c.post(
        f"/api/projects/{pid}/hse/drills",
        json={"number": "DR-01", "title": "Fire drill", "planned_on": date.today().isoformat(), "findings": "Hydrant was blocked"},
    )
    assert drill.status_code == 201, drill.text
    assert "not an action" in drill.json()["finding_note"]
    early = c.post(
        f"/api/projects/{pid}/hse/drills/{drill.json()['id']}/acknowledgments",
        json={"member_id": client, "evidence": "Present at the gate"},
    )
    assert early.status_code == 409 and "held" in early.text
    held = c.post(f"/api/projects/{pid}/hse/drills/{drill.json()['id']}/hold", json={"version": drill.json()["version"]})
    assert held.status_code == 200, held.text
    assert held.json()["findings"] == "Hydrant was blocked"
    sign_in(c, "client-emerg@alpha.test")
    acked = c.post(
        f"/api/projects/{pid}/hse/drills/{drill.json()['id']}/acknowledgments",
        json={"member_id": client, "evidence": "Present at the gate"},
    )
    assert acked.status_code == 201, acked.text
    assert acked.json()["acknowledgments"]
    sign_in(c)
    started = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert started.status_code == 409 and "readiness" in started.text
    work = c.get(f"/api/projects/{pid}/hse/work", params={"package_id": package_id})
    assert work.status_code == 200, work.text
    assert "do not hold work" in work.json()["emergency_note"]
    links = c.get(f"/api/projects/{pid}/construction/connections")
    assert "does not hold work" in links.json()["hse"]["emergency_note"]
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.hse.models import HseAction

        assert db.get(WorkPackage, package_id).status == "Ready"
        assert db.query(HseAction).filter_by(project_id=pid).count() == 0


def test_environmental_records_follow_saved_criteria_and_do_not_hold_work(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="HSE-ENV",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""})
    assert area.status_code == 201, area.text
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area.json()["id"], me["company_id"], civil, code="WP-N"))
    assert package.status_code == 201, package.text
    package_id = package.json()["id"]
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.identity_projects.models import User

        row = db.get(WorkPackage, package_id)
        row.status = "Ready"
        row.release_state = "Released"
        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
        db.commit()
    client = _user(c, "client-env@alpha.test", "Environment Reader", me["company_id"])
    for user_id, role in ((uid, "HSE"), (client, "Client/PMC Reviewer")):
        assert c.post(
            f"/api/projects/{pid}/memberships",
            json={"user_id": user_id, "role_id": roles[role], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
        ).status_code == 201
    sign_in(c, "client-env@alpha.test")
    refused = c.post(
        f"/api/projects/{pid}/hse/environment-criteria",
        json={"name": "Dust limit", "kind": "Dust/noise", "threshold": "Visible dust beyond the site boundary"},
    )
    assert refused.status_code == 403, refused.text
    spill = c.post(
        f"/api/projects/{pid}/hse/environment-records",
        json={
            "number": "EN-1",
            "kind": "Spill",
            "description": "Oil on the pad",
            "recorded_on": date.today().isoformat(),
            "package_id": package_id,
            "result": "Not assessed",
        },
    )
    assert spill.status_code == 201, spill.text
    assert spill.json()["package_status"] == "Ready"
    assert "does not file" in spill.json()["statement"]
    assert "does not open a new one" in spill.json()["action_note"]
    outside = c.post(
        f"/api/projects/{pid}/hse/environment-records",
        json={
            "number": "EN-2",
            "kind": "Dust/noise",
            "description": "Dust past the fence",
            "recorded_on": date.today().isoformat(),
            "result": "Outside criteria",
            "reading": "Visible plume",
            "report_filed": True,
        },
    )
    assert outside.status_code == 422, outside.text
    sign_in(c, "viewer@alpha.test")
    criterion = c.post(
        f"/api/projects/{pid}/hse/environment-criteria",
        json={"name": "Dust limit", "kind": "Dust/noise", "threshold": "Visible dust beyond the site boundary"},
    )
    assert criterion.status_code == 201, criterion.text
    mismatched = c.post(
        f"/api/projects/{pid}/hse/environment-records",
        json={
            "number": "EN-2",
            "kind": "Spill",
            "description": "Oil on the pad again",
            "recorded_on": date.today().isoformat(),
            "criterion_id": criterion.json()["id"],
            "reading": "Small stain",
            "result": "Within criteria",
        },
    )
    assert mismatched.status_code == 422 and "different record" in mismatched.text
    recorded = c.post(
        f"/api/projects/{pid}/hse/environment-records",
        json={
            "number": "EN-2",
            "kind": "Dust/noise",
            "description": "Dust past the fence",
            "recorded_on": date.today().isoformat(),
            "package_id": package_id,
            "criterion_id": criterion.json()["id"],
            "reading": "Visible plume",
            "result": "Outside criteria",
        },
    )
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["package_status"] == "Ready"
    assert recorded.json()["action_number"] == ""
    invented = c.post(
        f"/api/projects/{pid}/hse/actions",
        json={
            "number": "EA-1",
            "description": "Wash the pad",
            "company_id": me["company_id"],
            "owner_id": client,
            "verifier_id": uid,
            "source_type": "hse.environment",
        },
    )
    assert invented.status_code == 422, invented.text
    action = c.post(
        f"/api/projects/{pid}/hse/actions",
        json={
            "number": "EA-1",
            "description": "Wash the pad",
            "company_id": me["company_id"],
            "owner_id": client,
            "verifier_id": uid,
        },
    )
    assert action.status_code == 201, action.text
    broad = c.post(
        f"/api/projects/{pid}/hse/environment-criteria",
        json={"name": "Site check", "threshold": "As written in the site environmental plan"},
    )
    assert broad.status_code == 201, broad.text
    linked = c.post(
        f"/api/projects/{pid}/hse/environment-records",
        json={
            "number": "EN-3",
            "kind": "Monitoring evidence",
            "description": "Weekly dust check",
            "recorded_on": date.today().isoformat(),
            "criterion_id": broad.json()["id"],
            "reading": "No plume",
            "result": "Within criteria",
            "evidence": "Checked at the north fence",
            "action_id": action.json()["id"],
        },
    )
    assert linked.status_code == 201, linked.text
    assert linked.json()["action_number"] == "EA-1"
    assert linked.json()["action_status"] == "Open"
    sign_in(c)
    started = c.post(f"/api/projects/{pid}/construction/packages/{package_id}/start", json={"version": 1})
    assert started.status_code == 409 and "readiness" in started.text
    work = c.get(f"/api/projects/{pid}/hse/work", params={"package_id": package_id})
    assert "does not file" in work.json()["environment_note"]
    links = c.get(f"/api/projects/{pid}/construction/connections")
    assert "does not file" in links.json()["hse"]["environment_note"]
    board = c.get(f"/api/projects/{pid}/hse").json()
    assert board["counts"]["environment_outside"] >= 1
    with maker() as db:
        from app.domains.construction.models import WorkPackage
        from app.domains.coordination.models import Notification
        from app.domains.hse.models import HseAction

        assert db.get(WorkPackage, package_id).status == "Ready"
        assert db.query(HseAction).filter_by(project_id=pid).count() == 1
        assert db.query(HseAction).filter_by(project_id=pid, source_type="hse.environment").count() == 0
        assert db.query(Notification).filter_by(user_id=uid, title="An environmental reading is outside the saved criterion").count() == 1


def test_safety_dashboard_filters_stored_records_and_keeps_the_rate_blank(env):
    c, maker = env
    sign_in(c)
    me = c.get("/api/auth/me").json()["user"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    roles = {row["name"]: row["id"] for row in catalog["roles"]}
    created = new_project(
        c,
        code="HSE-DASH",
        client_company_id=me["company_id"],
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""})
    assert area.status_code == 201, area.text
    first = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area.json()["id"], me["company_id"], civil, code="WP-A"))
    second = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area.json()["id"], me["company_id"], civil, code="WP-B"))
    assert first.status_code == 201 and second.status_code == 201
    package_id = first.json()["id"]
    with maker() as db:
        from app.domains.identity_projects.models import User

        uid = db.query(User).filter_by(email="viewer@alpha.test").one().id
    client = _user(c, "client-dash@alpha.test", "Dashboard Reader", me["company_id"])
    for user_id, role in ((uid, "HSE"), (client, "Client/PMC Reviewer")):
        assert c.post(
            f"/api/projects/{pid}/memberships",
            json={"user_id": user_id, "role_id": roles[role], "company_id": me["company_id"], "scope": "ALL", "discipline_ids": []},
        ).status_code == 201
    near = c.post(f"/api/projects/{pid}/hse/incident-categories", json={"name": "Near Miss"})
    fire = c.post(f"/api/projects/{pid}/hse/incident-categories", json={"name": "Fire"})
    assert near.status_code == 201 and fire.status_code == 201
    assert c.post(f"/api/projects/{pid}/hse/hold-issuers", json={"user_id": uid}).status_code == 201
    when = datetime.now(timezone.utc).isoformat()
    sign_in(c, "client-dash@alpha.test")
    on_package = c.post(
        f"/api/projects/{pid}/hse/incidents",
        json={
            "category_id": near.json()["id"],
            "number": "INC-A",
            "event_at": when,
            "timezone_name": "IST",
            "company_id": me["company_id"],
            "package_id": package_id,
            "description": "A load swung past the exclusion zone",
            "initial_severity": "Major",
        },
    )
    assert on_package.status_code == 201, on_package.text
    loose = c.post(
        f"/api/projects/{pid}/hse/incidents",
        json={
            "category_id": fire.json()["id"],
            "number": "INC-B",
            "event_at": when,
            "timezone_name": "IST",
            "company_id": me["company_id"],
            "description": "Smoke at the laydown",
        },
    )
    assert loose.status_code == 201, loose.text
    unsafe = c.post(
        f"/api/projects/{pid}/hse/observations",
        json={"number": "OB-1", "observation_type": "Unsafe Condition", "description": "Open edge", "package_id": package_id},
    )
    positive = c.post(
        f"/api/projects/{pid}/hse/observations",
        json={"number": "OB-2", "observation_type": "Positive Observation", "description": "Barricade was in place"},
    )
    assert unsafe.status_code == 201 and positive.status_code == 201
    sign_in(c, "viewer@alpha.test")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    late = c.post(
        f"/api/projects/{pid}/hse/actions",
        json={
            "number": "DA-1",
            "description": "Close the edge",
            "severity": "Major",
            "company_id": me["company_id"],
            "owner_id": client,
            "verifier_id": uid,
            "due_on": yesterday,
        },
    )
    soon = c.post(
        f"/api/projects/{pid}/hse/actions",
        json={
            "number": "DA-2",
            "description": "Repaint the sign",
            "severity": "Minor",
            "company_id": me["company_id"],
            "owner_id": client,
            "verifier_id": uid,
            "due_on": tomorrow,
        },
    )
    assert late.status_code == 201 and soon.status_code == 201, late.text + soon.text
    ahead = c.post(
        f"/api/projects/{pid}/hse/drills",
        json={"number": "DR-A", "title": "Muster drill", "planned_on": tomorrow},
    )
    behind = c.post(
        f"/api/projects/{pid}/hse/drills",
        json={"number": "DR-B", "title": "Old drill", "planned_on": yesterday},
    )
    assert ahead.status_code == 201 and behind.status_code == 201
    criterion = c.post(
        f"/api/projects/{pid}/hse/environment-criteria",
        json={"name": "Dust limit", "kind": "Dust/noise", "threshold": "Visible dust beyond the site boundary"},
    )
    assert criterion.status_code == 201, criterion.text
    outside = c.post(
        f"/api/projects/{pid}/hse/environment-records",
        json={
            "number": "EN-1",
            "kind": "Dust/noise",
            "description": "Dust past the fence",
            "recorded_on": date.today().isoformat(),
            "package_id": package_id,
            "criterion_id": criterion.json()["id"],
            "reading": "Visible plume",
            "result": "Outside criteria",
        },
    )
    assert outside.status_code == 201, outside.text
    placed = c.post(
        f"/api/projects/{pid}/hse/holds",
        json=_hold(me["company_id"], client, package_id, "SH-D"),
    )
    assert placed.status_code == 201, placed.text
    sign_in(c)
    missing = c.get(f"/api/projects/{pid}/hse/dashboard", params={"date_from": yesterday})
    assert missing.status_code == 422 and "which date" in missing.text
    board = c.get(f"/api/projects/{pid}/hse/dashboard")
    assert board.status_code == 200, board.text
    body = board.json()
    assert body["rate"] == "N/A"
    assert "exposure hours" in body["rate_note"]
    names = {row["name"]: row["count"] for row in body["incidents_by_category"]}
    assert names["Near Miss"] == 1 and names["Fire"] == 1
    assert body["open_critical_observations"] == 1
    assert body["open_actions"] == 2 and body["overdue_actions"] == 1
    assert any(row["code"] == "WP-A" for row in body["blocked_work"])
    assert all(row["code"] != "WP-B" for row in body["blocked_work"])
    assert [row["number"] for row in body["upcoming_drills"]] == ["DR-A"]
    assert any(row["number"] == "EN-1" for row in body["environmental_issues"])
    narrowed = c.get(f"/api/projects/{pid}/hse/dashboard", params={"package_id": package_id})
    assert narrowed.status_code == 200, narrowed.text
    narrowed_names = {row["name"]: row["count"] for row in narrowed.json()["incidents_by_category"]}
    assert narrowed_names == {"Near Miss": 1}
    severe = c.get(f"/api/projects/{pid}/hse/dashboard", params={"severity": "major", "date_kind": "due", "date_to": yesterday})
    assert severe.status_code == 200, severe.text
    assert severe.json()["open_actions"] == 1 and severe.json()["overdue_actions"] == 1
    assert severe.json()["incidents_by_category"] == []
    by_discipline = c.get(f"/api/projects/{pid}/hse/dashboard", params={"discipline_id": civil})
    assert by_discipline.json()["incidents_by_category"] == []
    assert any(row["code"] == "WP-A" for row in by_discipline.json()["blocked_work"])
    assert by_discipline.json()["rate"] == "N/A"
