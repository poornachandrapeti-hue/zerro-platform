from datetime import date, timedelta

from app.domains.coordination.models import Notification
from app.domains.workforce.models import AttendanceRecord, AttendanceSheet, Credential, Deployment, Leave, WorkforceRequest

from .test_construction import _package
from .test_engineering import _ids, _member, _user, sign_in
from .test_foundation import new_project
from .test_workforce import _decide, _person, _route


def test_demand_is_the_shared_request_and_keeps_requested_approved_confirmed_apart(env):
    c, maker = env
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    pid = new_project(c, code="MP-01", client_company_id=company).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Fitter"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Pipe Fitter"}).json()["id"]
    grade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Skill grade", "name": "Grade A"}).json()["id"]
    person = c.post(
        f"/api/projects/{pid}/hr/personnel",
        json=_person(company, designation, trade, contact_number="98450", identity_reference="ID-7"),
    ).json()["id"]

    users = {}
    for key, role in (
        ("hr", "HR"),
        ("pm", "Project Manager"),
        ("se", "Site Engineer"),
        ("mc", "Manpower Coordinator"),
        ("plan", "Planning"),
        ("cm", "Commercial Manager"),
    ):
        users[key] = _user(c, f"{key}-mp@alpha.test", f"{key.upper()} Manpower", company)
        _member(c, pid, users[key], roles[role], company, [])
    _route(c, pid, "hr.deployment", users["pm"])
    _route(c, pid, "hr.request", users["pm"])

    # Commercial staff have no manpower view.
    sign_in(c, "cm-mp@alpha.test")
    assert c.get(f"/api/projects/{pid}/manpower").status_code == 403

    # HR mobilizes the person through its own deployment record.
    sign_in(c, "hr-mp@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": person, "planned_start": "2026-10-05", "checks": []}).status_code == 201
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm-mp@alpha.test")
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert _decide(c, deployment["review"]).status_code == 200

    # Site engineering raises the demand in Manpower.
    sign_in(c, "se-mp@alpha.test")
    body = {
        "number": "MD-1",
        "company_id": company,
        "trade_id": trade,
        "grade_id": grade,
        "headcount": 2,
        "required_hours": 320,
        "start_date": "2026-10-10",
        "end_date": "2026-11-30",
        "required_mobilization": "2026-10-08",
        "shift": "Day",
        "priority": "High",
        "justification": "Spool erection",
    }
    late = c.post(f"/api/projects/{pid}/manpower/demands", json={**body, "required_mobilization": "2026-10-12"})
    assert late.status_code == 422 and "mobilization" in late.text
    wrong_grade = c.post(f"/api/projects/{pid}/manpower/demands", json={**body, "grade_id": trade})
    assert wrong_grade.status_code == 422 and "skill grade" in wrong_grade.text
    made = c.post(f"/api/projects/{pid}/manpower/demands", json=body)
    assert made.status_code == 201, made.text

    board = c.get(f"/api/projects/{pid}/manpower").json()
    demand = board["demands"][0]
    assert demand["grade"] == "Grade A" and demand["required_hours"] == 320
    assert demand["required_mobilization"] == "2026-10-08"
    assert demand["tracking"] == {"requested": 2, "approved": 0, "proposed": 0, "confirmed": 0, "shortfall": None}
    reference = board["references"][0]
    assert reference["deployment_status"] == "Approved for Mobilization"
    assert "contact_number" not in reference and "identity_reference" not in reference
    assert board["can_demand"] is True and board["can_coordinate"] is False

    # The same record is visible in HR; there is no second intake.
    with maker() as db:
        assert db.query(WorkforceRequest).filter_by(project_id=pid).count() == 1
    assert c.post(f"/api/projects/{pid}/manpower/demands/{demand['id']}/submit", json={"version": demand["version"]}).status_code == 200
    sign_in(c, "pm-mp@alpha.test")
    demand = c.get(f"/api/projects/{pid}/manpower").json()["demands"][0]
    assert demand["review"]["actions"]
    assert _decide(c, demand["review"]).status_code == 200

    sign_in(c, "se-mp@alpha.test")
    demand = c.get(f"/api/projects/{pid}/manpower").json()["demands"][0]
    assert demand["status"] == "Open"
    assert demand["tracking"] == {"requested": 2, "approved": 2, "proposed": 0, "confirmed": 0, "shortfall": 2}
    # Proposing people is coordination, not engineering.
    assert c.post(f"/api/projects/{pid}/manpower/demands/{demand['id']}/lines", json={"personnel_id": person, "state": "Proposed", "version": demand["version"]}).status_code == 403

    sign_in(c, "mc-mp@alpha.test")
    assert c.post(f"/api/projects/{pid}/manpower/demands/{demand['id']}/lines", json={"personnel_id": person, "state": "Proposed", "version": demand["version"]}).status_code == 200
    demand = c.get(f"/api/projects/{pid}/manpower").json()["demands"][0]
    assert demand["tracking"]["proposed"] == 1 and demand["tracking"]["shortfall"] == 2
    unlinked = c.post(f"/api/projects/{pid}/manpower/demands/{demand['id']}/lines", json={"personnel_id": person, "state": "Allocated", "version": demand["version"]})
    assert unlinked.status_code == 422
    confirmed = c.post(
        f"/api/projects/{pid}/manpower/demands/{demand['id']}/lines",
        json={"personnel_id": person, "state": "Allocated", "deployment_id": deployment["id"], "version": demand["version"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    board = c.get(f"/api/projects/{pid}/manpower").json()
    demand = board["demands"][0]
    assert demand["status"] == "Partially Allocated"
    assert demand["tracking"] == {"requested": 2, "approved": 2, "proposed": 0, "confirmed": 1, "shortfall": 1}
    assert board["counts"]["shortfall"] == 1 and board["counts"]["confirmed"] == 1

    # A changed forecast reaches the requester and Planning, once.
    for _ in range(2):
        moved = c.post(f"/api/projects/{pid}/manpower/demands/{demand['id']}/forecast", json={"expected_mobilization": "2026-10-15", "version": demand["version"]})
        assert moved.status_code == 200, moved.text
        demand = c.get(f"/api/projects/{pid}/manpower").json()["demands"][0]
    with maker() as db:
        for key in ("se", "plan"):
            assert db.query(Notification).filter_by(user_id=users[key], title="Mobilization forecast changed").count() == 1
        assert db.query(Notification).filter_by(user_id=users["mc"], title="Mobilization forecast changed").count() == 0

    sign_in(c, "hr-mp@alpha.test")
    hr_view = c.get(f"/api/projects/{pid}/hr").json()["requests"][0]
    assert hr_view["number"] == "MD-1" and hr_view["counts"]["allocated"] == 1


def test_crews_move_to_manpower_and_availability_reads_hr(env):
    c, maker = env
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    today = date.today()
    day = lambda offset: (today + timedelta(days=offset)).isoformat()  # noqa: E731
    pid = new_project(c, code="MP-02", client_company_id=company).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Fitter"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Pipe Fitter"}).json()["id"]
    leave_type = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Leave type", "name": "Annual leave"}).json()["id"]
    first = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(company, designation, trade, start_date=day(-60))).json()["id"]
    second = c.post(
        f"/api/projects/{pid}/hr/personnel",
        json=_person(company, designation, trade, code="W-002", full_name="Bala Murugan", start_date=day(-60)),
    ).json()["id"]

    users = {}
    for key, role in (
        ("hr", "HR"),
        ("pm", "Project Manager"),
        ("se", "Site Engineer"),
        ("mc", "Manpower Coordinator"),
        ("sup", "Supervisor"),
    ):
        users[key] = _user(c, f"{key}-crew@alpha.test", f"{key.upper()} Crew", company)
        _member(c, pid, users[key], roles[role], company, [])
    outsider = _user(c, "out-crew@alpha.test", "Not On Project", company)
    _route(c, pid, "hr.deployment", users["pm"])
    _route(c, pid, "hr.request", users["pm"])

    sign_in(c, "hr-crew@alpha.test")
    for person in (first, second):
        assert c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": person, "planned_start": day(-5), "checks": []}).status_code == 201
    for row in c.get(f"/api/projects/{pid}/hr").json()["deployments"]:
        assert c.post(f"/api/projects/{pid}/hr/deployments/{row['id']}/submit", json={"version": row["version"]}).status_code == 200
    sign_in(c, "pm-crew@alpha.test")
    for row in c.get(f"/api/projects/{pid}/hr").json()["deployments"]:
        assert _decide(c, row["review"]).status_code == 200
    with maker() as db:
        mobilized = db.query(Deployment).filter_by(project_id=pid, personnel_id=first).one()
        mobilized.status, mobilized.actual_start = "Mobilized", today - timedelta(days=5)
        db.add(
            Leave(
                organization_id=mobilized.organization_id,
                project_id=pid,
                personnel_id=first,
                company_id=company,
                leave_type_id=leave_type,
                start_date=today + timedelta(days=2),
                end_date=today + timedelta(days=3),
                reason="Private family matter",
                requested_by=users["hr"],
                status="Approved",
                created_by=users["hr"],
            )
        )
        db.commit()

    # Engineering sees crews but does not build them.
    crew = {
        "code": "PF-01",
        "name": "Pipe crew",
        "company_id": company,
        "trade_id": trade,
        "supervisor_id": users["sup"],
        "lead_id": first,
        "effective_from": day(-5),
    }
    sign_in(c, "se-crew@alpha.test")
    assert c.post(f"/api/projects/{pid}/manpower/crews", json=crew).status_code == 403

    sign_in(c, "mc-crew@alpha.test")
    wrong_trade = c.post(f"/api/projects/{pid}/manpower/crews", json={**crew, "trade_id": designation})
    assert wrong_trade.status_code == 422 and "trade" in wrong_trade.text
    stranger = c.post(f"/api/projects/{pid}/manpower/crews", json={**crew, "supervisor_id": outsider})
    assert stranger.status_code == 422 and "supervisor" in stranger.text
    made = c.post(f"/api/projects/{pid}/manpower/crews", json=crew)
    assert made.status_code == 201, made.text
    other = c.post(f"/api/projects/{pid}/manpower/crews", json={**crew, "code": "PF-02", "name": "Second crew"}).json()
    joined = c.post(f"/api/projects/{pid}/manpower/crews/{made.json()['id']}/members", json={"personnel_id": first, "start_date": day(-5), "version": 1})
    assert joined.status_code == 201, joined.text
    twice = c.post(f"/api/projects/{pid}/manpower/crews/{other['id']}/members", json={"personnel_id": first, "start_date": day(0), "version": 1})
    assert twice.status_code == 409 and "PF-01" in twice.text

    board = c.get(f"/api/projects/{pid}/manpower").json()
    row = next(item for item in board["crews"] if item["code"] == "PF-01")
    assert row["name"] == "Pipe crew" and row["trade"] == "Pipe Fitter" and row["supervisor"] == "SUP Crew"
    assert row["members"][0]["today"] == "Available"
    assert row["strength"] == {"members": 1, "available": 1, "away": 0}
    assert board["counts"]["available_today"] == 1 and board["counts"]["active_crews"] == 2

    # HR attendance uses the same crew, and an older HR save keeps the Manpower fields.
    sign_in(c, "hr-crew@alpha.test")
    hr_crew = next(item for item in c.get(f"/api/projects/{pid}/hr").json()["crews"] if item["code"] == "PF-01")
    saved = c.put(
        f"/api/projects/{pid}/hr/crews/{hr_crew['id']}",
        json={"code": "PF-01", "company_id": company, "lead_id": first, "effective_from": day(-5), "active": True, "version": hr_crew["version"]},
    )
    assert saved.status_code == 200, saved.text
    hr_crew = next(item for item in c.get(f"/api/projects/{pid}/hr").json()["crews"] if item["code"] == "PF-01")
    assert hr_crew["name"] == "Pipe crew" and hr_crew["supervisor_id"] == users["sup"]

    # Engineering raises demand for three fitters; once approved it is compared with HR availability.
    sign_in(c, "se-crew@alpha.test")
    demand = {
        "number": "MD-9",
        "company_id": company,
        "trade_id": trade,
        "headcount": 3,
        "start_date": day(0),
        "end_date": day(10),
        "justification": "Hydrotest spools",
    }
    raised = c.post(f"/api/projects/{pid}/manpower/demands", json=demand)
    assert raised.status_code == 201, raised.text
    row = c.get(f"/api/projects/{pid}/manpower").json()["demands"][0]
    assert c.post(f"/api/projects/{pid}/manpower/demands/{row['id']}/submit", json={"version": row["version"]}).status_code == 200
    sign_in(c, "pm-crew@alpha.test")
    row = c.get(f"/api/projects/{pid}/manpower").json()["demands"][0]
    assert _decide(c, row["review"]).status_code == 200

    sign_in(c, "se-crew@alpha.test")
    assert c.get(f"/api/projects/{pid}/manpower/availability?days=40").status_code == 422
    found = c.get(f"/api/projects/{pid}/manpower/availability?start={day(0)}&days=7")
    assert found.status_code == 200, found.text
    assert "Private family matter" not in found.text
    data = found.json()
    assert len(data["dates"]) == 7 and data["dates"][0] == day(0)
    people = {item["id"]: item["days"] for item in data["people"]}
    assert people[first][0] == {"status": "Available", "crew": "PF-01"}
    assert people[first][2]["status"] == "On leave"
    assert people[second][0] == {"status": "Expected", "crew": ""}
    fitters = next(item for item in data["trades"] if item["trade_id"] == trade)["days"]
    assert fitters[0] == {"available": 1, "expected": 1, "away": 0, "needed": 3, "gap": 2}
    assert fitters[2] == {"available": 0, "expected": 1, "away": 1, "needed": 3, "gap": 3}


def test_assignments_check_eligibility_booking_and_mobilization(env):
    c, maker = env
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    today = date.today()
    day = lambda offset: (today + timedelta(days=offset)).isoformat()  # noqa: E731
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    pid = new_project(
        c,
        code="MP-03",
        client_company_id=company,
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    ).json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""}).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Rigger"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Rigger"}).json()["id"]
    leave_type = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Leave type", "name": "Casual leave"}).json()["id"]
    first = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(company, designation, trade, start_date=day(-60))).json()["id"]
    second = c.post(
        f"/api/projects/{pid}/hr/personnel",
        json=_person(company, designation, trade, code="W-002", full_name="Bala Murugan", start_date=day(-60)),
    ).json()["id"]
    users = {}
    for key, role in (("hr", "HR"), ("pm", "Project Manager"), ("mc", "Manpower Coordinator"), ("sup", "Supervisor"), ("cm", "Commercial Manager")):
        users[key] = _user(c, f"{key}-alloc@alpha.test", f"{key.upper()} Alloc", company)
        _member(c, pid, users[key], roles[role], company, [])
    _route(c, pid, "hr.deployment", users["pm"])

    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area, company, civil, code="WP-A"))
    assert package.status_code == 201, package.text
    activities = {}
    for code in ("LIFT", "RIG"):
        made = c.post(
            f"/api/projects/{pid}/construction/activities",
            json={"package_id": package.json()["id"], "code": code, "name": code.title(), "quantity": "10", "unit": "nos", "company_id": company, "measurement_method": "Quantity", "predecessor_ids": []},
        )
        assert made.status_code == 201, made.text
        activities[code] = made.json()["id"]
    kind = c.post(f"/api/projects/{pid}/hr/credential-types", json={"name": "Working at height", "owner": "HSE", "requires_expiry": True}).json()["id"]
    assert c.post(f"/api/projects/{pid}/hr/credential-rules", json={"type_id": kind, "activity_id": activities["LIFT"]}).status_code == 201

    sign_in(c, "hr-alloc@alpha.test")
    shifts = {}
    for code, start, end in (("DAY", "08:00", "17:00"), ("LATE", "16:00", "01:00")):
        made = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": code, "name": code.title(), "start_time": start, "end_time": end, "break_minutes": 60, "effective_from": day(-30)})
        assert made.status_code == 201, made.text
        shifts[code] = made.json()["id"]
    for person in (first, second):
        assert c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": person, "planned_start": day(-5), "checks": []}).status_code == 201
    for row in c.get(f"/api/projects/{pid}/hr").json()["deployments"]:
        assert c.post(f"/api/projects/{pid}/hr/deployments/{row['id']}/submit", json={"version": row["version"]}).status_code == 200
    sign_in(c, "pm-alloc@alpha.test")
    for row in c.get(f"/api/projects/{pid}/hr").json()["deployments"]:
        assert _decide(c, row["review"]).status_code == 200
    sign_in(c)
    mobilize = next(row for row in c.get(f"/api/projects/{pid}/hr").json()["deployments"] if row["personnel_id"] == first)
    moved = c.post(f"/api/projects/{pid}/hr/deployments/{mobilize['id']}/move", json={"action": "mobilize", "on": day(-3), "version": mobilize["version"]})
    assert moved.status_code == 200, moved.text
    with maker() as db:
        org = db.get(Deployment, mobilize["id"]).organization_id
        expired = Credential(
            organization_id=org,
            personnel_id=first,
            type_id=kind,
            issue_date=today - timedelta(days=400),
            expiry_date=today - timedelta(days=1),
            status="Verified",
            created_by=users["hr"],
        )
        db.add(expired)
        db.commit()
        credential = expired.id

    url = f"/api/projects/{pid}/manpower/assignments"
    lift = {"activity_id": activities["LIFT"], "work_date": day(0), "shift_id": shifts["DAY"], "personnel_id": first, "planned_minutes": 240}

    # Commercial staff do not allocate; an expired qualification blocks the person without private detail.
    sign_in(c, "cm-alloc@alpha.test")
    assert c.post(url, json=lift).status_code == 403
    sign_in(c, "sup-alloc@alpha.test")
    blocked = c.post(url, json=lift)
    assert blocked.status_code == 422 and "Working at height expired" in blocked.text
    with maker() as db:
        db.get(Credential, credential).expiry_date = today + timedelta(days=100)
        db.commit()
    made = c.post(url, json=lift)
    assert made.status_code == 201, made.text
    first_lift = made.json()["created"][0]

    # No double booking: same activity, over the shift's scheduled hours, or an overlapping shift.
    twice = c.post(url, json=lift)
    assert twice.status_code == 422 and "already assigned to this activity" in twice.text
    rig = {**lift, "activity_id": activities["RIG"], "planned_minutes": 300}
    over = c.post(url, json=rig)
    assert over.status_code == 422 and "more than its 8:00 scheduled" in over.text
    assert c.post(url, json={**rig, "planned_minutes": 240}).status_code == 201
    late = c.post(url, json={**rig, "shift_id": shifts["LATE"], "planned_minutes": 120})
    assert late.status_code == 422 and "overlaps" in late.text

    # A crew assignment takes the members who can work and reports the rest.
    sign_in(c, "mc-alloc@alpha.test")
    crew = c.post(f"/api/projects/{pid}/manpower/crews", json={"code": "RG-1", "company_id": company, "effective_from": day(-5)}).json()["id"]
    for person in (first, second):
        joined = c.post(f"/api/projects/{pid}/manpower/crews/{crew}/members", json={"personnel_id": person, "start_date": day(-3), "version": 1 if person == first else 2})
        assert joined.status_code == 201, joined.text
    sign_in(c, "sup-alloc@alpha.test")
    by_crew = {"activity_id": activities["RIG"], "work_date": day(1), "shift_id": shifts["DAY"], "crew_id": crew, "planned_minutes": 480}
    taken = c.post(url, json=by_crew)
    assert taken.status_code == 201, taken.text
    assert len(taken.json()["created"]) == 2 and taken.json()["skipped"] == []
    second_rig = next(
        item for item in c.get(f"/api/projects/{pid}/manpower/allocations?start={day(1)}&days=1").json()["assignments"]
        if item["personnel_id"] == second
    )
    assert "approved for mobilization but not yet mobilized" in second_rig["problems"]
    unready = c.post(f"{url}/{second_rig['id']}/confirm", json={"version": second_rig["version"]})
    assert unready.status_code == 422 and "not yet mobilized" in unready.text
    assert c.post(f"{url}/{first_lift}/confirm", json={"version": 1}).status_code == 200
    assert c.post(f"{url}/{first_lift}/confirm", json={"version": 2}).status_code == 409

    # Approved leave blocks new work and flags confirmed work already planned.
    with maker() as db:
        db.add(
            Leave(
                organization_id=org,
                project_id=pid,
                personnel_id=first,
                company_id=company,
                leave_type_id=leave_type,
                start_date=today,
                end_date=today,
                requested_by=users["hr"],
                status="Approved",
                created_by=users["hr"],
            )
        )
        db.commit()
    board = c.get(f"/api/projects/{pid}/manpower/allocations?start={day(0)}&days=2").json()
    confirmed = next(item for item in board["assignments"] if item["id"] == first_lift)
    assert confirmed["state"] == "Confirmed" and "on approved leave" in confirmed["problems"]
    assert board["counts"]["confirmed"] == 1 and board["counts"]["proposed"] == 3 and board["counts"]["flagged"] >= 2

    assert c.post(f"{url}/{second_rig['id']}/release", json={"reason": "No", "version": second_rig["version"]}).status_code == 422
    released = c.post(f"{url}/{second_rig['id']}/release", json={"reason": "Not mobilized in time", "version": second_rig["version"]})
    assert released.status_code == 200 and released.json()["state"] == "Released"
    assert c.get(f"/api/projects/{pid}/manpower").json()["can_allocate"] is True


def test_daily_returns_reconcile_plan_attendance_and_block_self_accept(env):
    c, maker = env
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    today = date.today()
    day = lambda offset: (today + timedelta(days=offset)).isoformat()  # noqa: E731
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    pid = new_project(
        c,
        code="MP-04",
        client_company_id=company,
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    ).json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""}).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Rigger"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Rigger"}).json()["id"]
    first = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(company, designation, trade, start_date=day(-60))).json()["id"]
    users = {}
    for key, role in (("hr", "HR"), ("pm", "Project Manager"), ("mc", "Manpower Coordinator"), ("sup", "Supervisor"), ("cm", "Commercial Manager")):
        users[key] = _user(c, f"{key}-ret@alpha.test", f"{key.upper()} Ret", company)
        _member(c, pid, users[key], roles[role], company, [])
    _route(c, pid, "hr.deployment", users["pm"])
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area, company, civil, code="WP-R"))
    assert package.status_code == 201, package.text
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={"package_id": package.json()["id"], "code": "LIFT", "name": "Lift", "quantity": "10", "unit": "nos", "company_id": company, "measurement_method": "Quantity", "predecessor_ids": []},
    ).json()["id"]

    sign_in(c, "hr-ret@alpha.test")
    shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "break_minutes": 60, "effective_from": day(-30)}).json()["id"]
    assert c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": first, "planned_start": day(-5), "checks": []}).status_code == 201
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm-ret@alpha.test")
    assert _decide(c, c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]["review"]).status_code == 200
    sign_in(c)
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    moved = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": day(-3), "version": deployment["version"]})
    assert moved.status_code == 200, moved.text

    # Plan 4 hours and confirm it.
    sign_in(c, "sup-ret@alpha.test")
    made = c.post(f"/api/projects/{pid}/manpower/assignments", json={"activity_id": activity, "work_date": day(0), "shift_id": shift, "personnel_id": first, "planned_minutes": 240})
    assert made.status_code == 201, made.text
    assert c.post(f"/api/projects/{pid}/manpower/assignments/{made.json()['created'][0]}/confirm", json={"version": 1}).status_code == 200

    # HR attendance says 7 hours; the HR attendance flow has its own tests.
    with maker() as db:
        org = db.get(Deployment, deployment["id"]).organization_id
        sheet = AttendanceSheet(organization_id=org, project_id=pid, shift_id=shift, attendance_date=today, status="Approved", created_by=users["hr"])
        db.add(sheet)
        db.flush()
        record = AttendanceRecord(
            sheet_id=sheet.id, project_id=pid, personnel_id=first, deployment_id=deployment["id"], shift_id=shift,
            attendance_date=today, status="Present", worked_minutes=420, regular_minutes=420, created_by=users["hr"],
        )
        db.add(record)
        db.commit()
        record_id = record.id

    url = f"/api/projects/{pid}/manpower/returns"
    view = c.get(f"{url}?work_date={day(0)}&shift_id={shift}").json()
    assert len(view["lines"]) == 1 and "attended 7:00 against 4:00 planned" in view["lines"][0]["flags"]
    assert view["record"] is None and view["can_submit"] is True and view["can_accept"] is False

    body = {"work_date": day(0), "shift_id": shift, "reasons": []}
    sign_in(c, "cm-ret@alpha.test")
    assert c.post(url, json=body).status_code == 403
    sign_in(c, "sup-ret@alpha.test")
    missing = c.post(url, json=body)
    assert missing.status_code == 422 and "Give a reason" in missing.text
    assert c.post(url, json={**body, "work_date": day(1)}).status_code == 422
    body["reasons"] = [{"personnel_id": first, "reason": "Extra lifting after rain delay"}]
    sent = c.post(url, json=body)
    assert sent.status_code == 201, sent.text
    rid = sent.json()["id"]
    assert c.post(url, json=body).status_code == 409
    assert c.post(f"{url}/{rid}/accept", json={"version": 1}).status_code == 403

    # Sent back, resubmitted by the coordinator, who then cannot accept their own return.
    sign_in(c, "mc-ret@alpha.test")
    assert c.post(f"{url}/{rid}/return", json={"reason": "No", "version": 1}).status_code == 422
    back = c.post(f"{url}/{rid}/return", json={"reason": "Check the overtime", "version": 1})
    assert back.status_code == 200 and back.json()["state"] == "Returned"
    again = c.post(url, json={**body, "version": 2})
    assert again.status_code == 201, again.text
    assert c.post(f"{url}/{rid}/accept", json={"version": 3}).status_code == 403
    sign_in(c, "hr-ret@alpha.test")
    accepted = c.post(f"{url}/{rid}/accept", json={"version": 3})
    assert accepted.status_code == 200 and accepted.json()["state"] == "Accepted"
    assert c.post(f"{url}/{rid}/accept", json={"version": 4}).status_code == 409

    # A later attendance change is shown, not written into the accepted return.
    with maker() as db:
        db.get(AttendanceRecord, record_id).worked_minutes = 240
        db.commit()
    view = c.get(f"{url}?work_date={day(0)}&shift_id={shift}").json()
    assert view["record"]["state"] == "Accepted" and view["changed"] is True
    assert view["lines"][0]["attended_minutes"] == 420


def test_utilization_shortfalls_and_alerts_read_current_records(env):
    c, maker = env
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    today = date.today()
    day = lambda offset: (today + timedelta(days=offset)).isoformat()  # noqa: E731
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    pid = new_project(
        c,
        code="MP-05",
        client_company_id=company,
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    ).json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""}).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Rigger"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Rigger"}).json()["id"]
    leave_type = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Leave type", "name": "Casual leave"}).json()["id"]
    first = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(company, designation, trade, start_date=day(-60))).json()["id"]
    users = {}
    for key, role in (("hr", "HR"), ("pm", "Project Manager"), ("mc", "Manpower Coordinator"), ("sup", "Supervisor")):
        users[key] = _user(c, f"{key}-util@alpha.test", f"{key.upper()} Util", company)
        _member(c, pid, users[key], roles[role], company, [])
    _route(c, pid, "hr.deployment", users["pm"])
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area, company, civil, code="WP-U"))
    assert package.status_code == 201, package.text
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={"package_id": package.json()["id"], "code": "LIFT", "name": "Lift", "quantity": "10", "unit": "nos", "company_id": company, "measurement_method": "Quantity", "predecessor_ids": []},
    ).json()["id"]

    sign_in(c, "hr-util@alpha.test")
    shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "break_minutes": 60, "effective_from": day(-30)}).json()["id"]
    assert c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": first, "planned_start": day(-5), "checks": []}).status_code == 201
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm-util@alpha.test")
    assert _decide(c, c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]["review"]).status_code == 200
    sign_in(c)
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    moved = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": day(-3), "version": deployment["version"]})
    assert moved.status_code == 200, moved.text

    # An open demand for two riggers over three days, entered directly; the demand review has its own test.
    with maker() as db:
        org = db.get(Deployment, deployment["id"]).organization_id
        demand = WorkforceRequest(
            organization_id=org, project_id=pid, number="WR-U1", number_key="wr-u1", company_id=company, trade_id=trade,
            activity_id=activity, headcount=2, start_date=today, end_date=today + timedelta(days=2),
            requested_by=users["sup"], status="Open", created_by=users["sup"],
        )
        db.add(demand)
        db.commit()
        demand_id = demand.id

    sign_in(c, "sup-util@alpha.test")
    assign = f"/api/projects/{pid}/manpower/assignments"
    for offset, minutes, linked in ((-1, 480, None), (0, 240, demand_id)):
        made = c.post(assign, json={"activity_id": activity, "work_date": day(offset), "shift_id": shift, "personnel_id": first, "planned_minutes": minutes, "demand_id": linked})
        assert made.status_code == 201, made.text
        assert c.post(f"{assign}/{made.json()['created'][0]}/confirm", json={"version": 1}).status_code == 200
    with maker() as db:
        sheet = AttendanceSheet(organization_id=org, project_id=pid, shift_id=shift, attendance_date=today - timedelta(days=1), status="Approved", created_by=users["hr"])
        db.add(sheet)
        db.flush()
        db.add(
            AttendanceRecord(
                sheet_id=sheet.id, project_id=pid, personnel_id=first, deployment_id=deployment["id"], shift_id=shift,
                attendance_date=today - timedelta(days=1), status="Present", worked_minutes=240, regular_minutes=240, created_by=users["hr"],
            )
        )
        db.commit()

    # Seven available days at 8:00; 12:00 planned; 4:00 attended against the three days up to today.
    assert c.get(f"/api/projects/{pid}/manpower/utilization?start={day(-2)}&days=3").status_code == 422
    data = c.get(f"/api/projects/{pid}/manpower/utilization?start={day(-2)}&days=7").json()
    person = data["people"][0]
    assert person["available_days"] == 7 and person["available"] == "56:00" and person["planned"] == "12:00"
    assert person["allocation_pct"] == 21 and person["utilization_pct"] == 17
    assert data["trades"][0]["trade"] == "Rigger" and data["trades"][0]["people"] == 1
    short = data["shortfalls"][0]
    assert short["number"] == "WR-U1" and short["first_short"] == day(0) and short["worst_gap"] == 2 and short["short_days"] == 3
    assert [item["assigned"] for item in short["days"]] == [1, 0, 0]

    url = f"/api/projects/{pid}/manpower/alerts"
    kinds = {item["kind"]: item for item in c.get(url).json()["alerts"]}
    assert set(kinds) == {"Demand short", "Daily return missing", "Low utilization"}
    assert kinds["Demand short"]["severity"] == "High" and "short on 3 day(s)" in kinds["Demand short"]["detail"]
    assert day(-1) in kinds["Daily return missing"]["detail"]
    assert "17%" in kinds["Low utilization"]["detail"]

    # Leave flags today's confirmed work; a sent-back return replaces the missing-return alert.
    with maker() as db:
        db.add(
            Leave(
                organization_id=org, project_id=pid, personnel_id=first, company_id=company, leave_type_id=leave_type,
                start_date=today, end_date=today, requested_by=users["hr"], status="Approved", created_by=users["hr"],
            )
        )
        db.commit()
    returns = f"/api/projects/{pid}/manpower/returns"
    sent = c.post(returns, json={"work_date": day(-1), "shift_id": shift, "reasons": [{"personnel_id": first, "reason": "Rain stopped lifting"}]})
    assert sent.status_code == 201, sent.text
    sign_in(c, "mc-util@alpha.test")
    assert c.post(f"{returns}/{sent.json()['id']}/return", json={"reason": "Add the rain hours", "version": 1}).status_code == 200
    body = c.get(url).json()
    kinds = {item["kind"]: item for item in body["alerts"]}
    assert "Daily return missing" not in kinds
    assert kinds["Daily return sent back"]["owner"] == "SUP Util" and "Add the rain hours" in kinds["Daily return sent back"]["detail"]
    assert "on approved leave" in kinds["Assignment needs attention"]["detail"]
    assert body["alerts"][0]["severity"] == "High" and body["counts"]["Demand short"] == 1


def test_productivity_reads_approved_reports_and_summary_rolls_up(env):
    from decimal import Decimal

    from app.domains.construction.models import ProgressLabour, ProgressLine, ProgressReport

    c, maker = env
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    today = date.today()
    day = lambda offset: (today + timedelta(days=offset)).isoformat()  # noqa: E731
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    pid = new_project(
        c,
        code="MP-06",
        client_company_id=company,
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    ).json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""}).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Rigger"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Rigger"}).json()["id"]
    person = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(company, designation, trade, start_date=day(-60))).json()["id"]
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area, company, civil, code="WP-P"))
    assert package.status_code == 201, package.text
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={"package_id": package.json()["id"], "code": "LIFT", "name": "Lift", "quantity": "10", "unit": "nos", "company_id": company, "measurement_method": "Quantity", "predecessor_ids": []},
    ).json()["id"]

    # Approved reports count; reversals deduct; rework adds hours, not quantity; drafts are ignored.
    from app.domains.identity_projects.models import Project

    with maker() as db:
        org = db.get(Project, pid).organization_id
        engineer = me["id"]

        def report(number, offset, status):
            row = ProgressReport(
                organization_id=org, project_id=pid, number=number, number_key=number.lower(), report_date=today + timedelta(days=offset),
                shift="Day", discipline_id=civil, area_id=area, company_id=company, site_engineer_id=engineer, status=status, created_by=engineer,
            )
            db.add(row)
            db.flush()
            return row

        def line(row, quantity, **extra):
            item = ProgressLine(report_id=row.id, activity_id=activity, quantity=Decimal(quantity), unit="nos", created_by=engineer, **extra)
            db.add(item)
            db.flush()
            return item

        def labour(row, item, productive, idle=0, reason=""):
            db.add(ProgressLabour(report_id=row.id, line_id=item.id, personnel_id=person, productive_minutes=productive, idle_minutes=idle, idle_reason=reason, created_by=engineer))

        first = report("DPR-1", -1, "Approved")
        done = line(first, "10")
        labour(first, done, 300, 60, "Crane breakdown")
        labour(first, line(first, "2", rework=True), 60)
        second = report("DPR-2", 0, "Approved")
        line(second, "4", reverses_line_id=done.id)
        draft = report("DPR-3", 0, "Draft")
        labour(draft, line(draft, "100"), 600)
        db.commit()

    url = f"/api/projects/{pid}/manpower/productivity"
    assert c.get(f"{url}?start={day(0)}&end={day(-1)}").status_code == 422
    assert c.get(f"{url}?start={day(-100)}&end={day(0)}").status_code == 422
    data = c.get(f"{url}?start={day(-6)}&end={day(0)}").json()
    row = data["activities"][0]
    assert row["code"] == "LIFT" and row["unit"] == "nos" and row["quantity"] == "6"
    assert row["productive_hours"] == 6.0 and row["rework_hours"] == 1.0 and row["idle_hours"] == 1.0
    assert row["idle_pct"] == 14 and row["rate"] == "1.00" and row["people"] == 1 and row["reports"] == 2
    assert row["idle_reasons"] == [{"reason": "Crane breakdown", "hours": 1.0}]
    assert data["totals"]["productive_hours"] == 6.0 and data["totals"]["people"] == 1
    assert c.get(f"{url}?start={day(0)}&end={day(0)}").json()["activities"][0]["quantity"] == "-4"

    summary = c.get(f"/api/projects/{pid}/manpower/summary").json()
    assert summary["top_idle"][0]["code"] == "LIFT" and summary["idle_hours"] == 1.0
    assert summary["returns_pending"] == 0 and summary["short_today"] == 0
    assert summary["utilization_pct"] is None and set(summary["alerts"]) == {"High", "Medium", "Low"}


def test_construction_crew_check_reads_confirmed_manpower_assignments(env):
    c, maker = env
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    today = date.today()
    day = lambda offset: (today + timedelta(days=offset)).isoformat()  # noqa: E731
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    pid = new_project(
        c,
        code="MP-07",
        client_company_id=company,
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    ).json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""}).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Rigger"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Rigger"}).json()["id"]
    worker = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(company, designation, trade, start_date=day(-60))).json()["id"]
    users = {}
    for key, role in (("hr", "HR"), ("pm", "Project Manager"), ("sup", "Supervisor"), ("se", "Site Engineer")):
        users[key] = _user(c, f"{key}-crew@alpha.test", f"{key.upper()} Crew", company)
        _member(c, pid, users[key], roles[role], company, [])
    _route(c, pid, "hr.deployment", users["pm"])

    package = c.post(
        f"/api/projects/{pid}/construction/packages",
        json=_package(area, company, civil, code="WP-CREW", responsible_user_id=users["se"], planned_start=day(0), planned_finish=day(10)),
    ).json()
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={"package_id": package["id"], "code": "LIFT", "name": "Lift", "quantity": "10", "unit": "nos", "company_id": company, "measurement_method": "Quantity", "predecessor_ids": []},
    ).json()["id"]
    added = c.post(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks",
        json={"check_type": "Manpower", "classification": "Mandatory"},
    )
    assert added.status_code == 201, added.text

    def crew_check():
        card = next(row for row in c.get(f"/api/projects/{pid}/construction/readiness").json() if row["package"]["id"] == package["id"])
        return next(row for row in card["checks"] if row["check_type"] == "Manpower")

    # No confirmed people: Blocked, and a typed note cannot satisfy it.
    check = crew_check()
    assert check["manual"] is False and check["live_state"] == "Blocked" and check["live_owner"] == "Manpower"
    assert "has no confirmed, eligible people" in check["live_reason"]
    typed = c.put(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks/{check['id']}",
        json={"status": "Satisfied", "evidence": "Crew is named", "version": check["version"]},
    )
    assert typed.status_code == 422, typed.text
    not_applicable = c.put(
        f"/api/projects/{pid}/construction/packages/{package['id']}/checks/{check['id']}",
        json={"status": "Not Applicable", "evidence": "No crew needed for this package", "version": check["version"]},
    )
    assert not_applicable.status_code == 422, not_applicable.text

    sign_in(c, "hr-crew@alpha.test")
    shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "break_minutes": 60, "effective_from": day(-30)}).json()["id"]
    assert c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": worker, "planned_start": day(-5), "checks": []}).status_code == 201
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm-crew@alpha.test")
    assert _decide(c, c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]["review"]).status_code == 200
    sign_in(c)
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    moved = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": day(-3), "version": deployment["version"]})
    assert moved.status_code == 200, moved.text

    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, package["id"])
        row.status = "Ready"
        row.release_state = "Released"
        db.commit()
        version = row.version
    refused = c.post(f"/api/projects/{pid}/construction/packages/{package['id']}/start", json={"version": version})
    assert refused.status_code == 409 and "Manpower:" in refused.text, refused.text

    # A confirmed, eligible assignment for today satisfies the check and work can start.
    sign_in(c, "sup-crew@alpha.test")
    url = f"/api/projects/{pid}/manpower/assignments"
    made = c.post(url, json={"activity_id": activity, "work_date": day(0), "shift_id": shift, "personnel_id": worker, "planned_minutes": 240})
    assert made.status_code == 201, made.text
    assignment = made.json()["created"][0]
    sign_in(c)
    assert crew_check()["live_state"] == "Blocked"
    sign_in(c, "sup-crew@alpha.test")
    assert c.post(f"{url}/{assignment}/confirm", json={"version": 1}).status_code == 200
    sign_in(c)
    assert crew_check()["live_state"] == "Ready"
    started = c.post(f"/api/projects/{pid}/construction/packages/{package['id']}/start", json={"version": version})
    assert started.status_code == 200, started.text

    # Labour on a daily line needs a confirmed assignment for that person, activity, and date.
    sign_in(c, "se-crew@alpha.test")

    def labour_on(number, offset):
        report = c.post(
            f"/api/projects/{pid}/construction/progress",
            json={"number": number, "report_date": day(offset), "shift": "Day", "discipline_id": civil, "area_id": area, "company_id": company, "site_engineer_id": users["se"], "weather": "", "remarks": ""},
        )
        assert report.status_code == 201, report.text
        report = report.json()
        line = c.post(f"/api/projects/{pid}/construction/progress/{report['id']}/lines", json={"activity_id": activity, "quantity": "1"})
        assert line.status_code in (200, 201), line.text
        line_id = line.json()["lines"][0]["id"]
        return c.post(
            f"/api/projects/{pid}/construction/progress/{report['id']}/lines/{line_id}/labour",
            json={"personnel_id": worker, "productive_minutes": 120},
        )

    yesterday = labour_on("DPR-C1", -1)
    assert yesterday.status_code == 409 and "no confirmed Manpower assignment" in yesterday.text
    assert labour_on("DPR-C2", 0).status_code in (200, 201)
