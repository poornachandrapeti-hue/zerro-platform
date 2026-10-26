from app.domains.coordination.models import Notification
from app.domains.identity_projects.models import Membership, User

from .test_engineering import _ids, _member, _user, sign_in
from .test_foundation import new_project


def _person(company_id, designation, trade, code="W-001", **extra):
    return {
        "code": code,
        "full_name": "Arun Kumar",
        "company_id": company_id,
        "personnel_type": "Contract Worker",
        "designation_id": designation,
        "trade_id": trade,
        "start_date": "2026-10-01",
        **extra,
    }


def test_personnel_register_keeps_workers_apart_from_logins(env):
    c, maker = env
    sign_in(c)
    roles, disciplines, me = _ids(c)
    pid = new_project(c, code="HR-01", client_company_id=me["company_id"]).json()["id"]

    board = c.get(f"/api/projects/{pid}/hr")
    assert board.status_code == 200, board.text
    assert "not a login" in board.json()["note"]

    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Steel Fixer"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Steel Fixer"}).json()["id"]
    assert c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "steel fixer"}).status_code == 409
    assert c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Role", "name": "Admin"}).status_code == 422

    # Designation and trade are separate lists.
    wrong = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(me["company_id"], trade, trade))
    assert wrong.status_code == 422 and "designation" in wrong.text

    with maker() as db:
        users_before = db.query(User).count()
        members_before = db.query(Membership).count()
    created = c.post(
        f"/api/projects/{pid}/hr/personnel",
        json=_person(me["company_id"], designation, trade, contact_number="98450", emergency_contact="Spouse 98451"),
    )
    assert created.status_code == 201, created.text
    with maker() as db:
        assert db.query(User).count() == users_before
        assert db.query(Membership).count() == members_before

    duplicate = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(me["company_id"], designation, trade, code="w-001"))
    assert duplicate.status_code == 409 and "already used" in duplicate.text
    backwards = c.post(
        f"/api/projects/{pid}/hr/personnel",
        json=_person(me["company_id"], designation, trade, code="W-002", end_date="2026-09-01"),
    )
    assert backwards.status_code == 422
    separated = c.post(
        f"/api/projects/{pid}/hr/personnel",
        json=_person(me["company_id"], designation, trade, code="W-003", status="Separated"),
    )
    assert separated.status_code == 422 and "end date" in separated.text

    # A viewer with hr.view sees the worker but not contact details.
    viewer_id = _user(c, "hr-viewer@alpha.test", "Site Viewer", me["company_id"])
    _member(c, pid, viewer_id, roles["Supervisor"], me["company_id"], [])
    hr_id = _user(c, "hr-officer@alpha.test", "HR Officer", me["company_id"])
    _member(c, pid, hr_id, roles["HR"], me["company_id"], [])
    sign_in(c, "hr-viewer@alpha.test")
    seen = c.get(f"/api/projects/{pid}/hr").json()
    row = seen["personnel"][0]
    assert row["full_name"] == "Arun Kumar"
    assert row["contact_number"] is None and row["emergency_contact"] is None
    assert seen["restricted_visible"] is False
    assert c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Rigger"}).status_code == 403

    sign_in(c, "hr-officer@alpha.test")
    seen = c.get(f"/api/projects/{pid}/hr").json()
    row = seen["personnel"][0]
    assert row["contact_number"] == "98450"
    assert seen["counts"]["without_login"] == 1

    # Linking a login stores the reference only. Separating asks for an access review.
    payload = {
        **_person(me["company_id"], designation, trade),
        "user_id": viewer_id,
        "status": "Separated",
        "end_date": "2026-10-09",
        "contact_number": "98450",
        "emergency_contact": "Spouse 98451",
        "version": row["version"],
    }
    saved = c.put(f"/api/projects/{pid}/hr/personnel/{row['id']}", json=payload)
    assert saved.status_code == 200, saved.text
    stale = c.put(f"/api/projects/{pid}/hr/personnel/{row['id']}", json=payload)
    assert stale.status_code == 409
    after = c.get(f"/api/projects/{pid}/hr").json()
    assert after["personnel"][0]["access_review"] is True
    assert after["counts"]["access_reviews"] == 1
    with maker() as db:
        login = db.get(User, viewer_id)
        assert login.active is True
        admin_alerts = db.query(Notification).filter_by(user_id=me["id"], title="Login access review needed").all()
        assert len(admin_alerts) == 1
        assert "Arun" not in admin_alerts[0].body


def _route(c, pid, record_type, reviewer_id):
    response = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": record_type,
            "company_id": None,
            "discipline_id": None,
            "allow_self_approval": False,
            "stages": [
                {
                    "name": "HR review",
                    "rule": "all",
                    "quorum_count": 1,
                    "reviewer_ids": [reviewer_id],
                    "reviewers": [],
                    "purpose": "Review",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text


def _decide(c, review, action="approve", reason=""):
    return c.post(
        f"/api/reviews/{review['id']}/decisions",
        json={"action": action, "reason": reason, "comment": "", "version": review["version"]},
    )


def test_deployment_needs_checks_and_approval_and_requests_track_shortfall(env):
    c, maker = env
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    pid = new_project(c, code="HR-02", client_company_id=company).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Fixer"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Steel Fixer"}).json()["id"]
    person = c.post(f"/api/projects/{pid}/hr/personnel", json=_person(company, designation, trade)).json()["id"]

    hr_id = _user(c, "hr2@alpha.test", "HR Two", company)
    _member(c, pid, hr_id, roles["HR"], company, [])
    hse_id = _user(c, "hse2@alpha.test", "HSE Two", company)
    _member(c, pid, hse_id, roles["HSE"], company, [])
    pm_id = _user(c, "pm2@alpha.test", "PM Two", company)
    _member(c, pid, pm_id, roles["Project Manager"], company, [])
    se_id = _user(c, "se2@alpha.test", "SE Two", company)
    _member(c, pid, se_id, roles["Site Engineer"], company, [])

    sign_in(c, "hr2@alpha.test")
    with maker() as db:
        members_before = db.query(Membership).count()
    made = c.post(
        f"/api/projects/{pid}/hr/deployments",
        json={"personnel_id": person, "planned_start": "2026-10-05", "planned_end": "2026-12-31", "checks": ["Personnel documents", "Site induction"]},
    )
    assert made.status_code == 201, made.text
    with maker() as db:
        assert db.query(Membership).count() == members_before
    early = c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": person, "planned_start": "2026-09-01"})
    assert early.status_code == 422 and "employment start" in early.text
    overlap = c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": person, "planned_start": "2026-11-01"})
    assert overlap.status_code == 409

    board = c.get(f"/api/projects/{pid}/hr").json()
    deployment = board["deployments"][0]
    assert deployment["status"] == "Proposed"
    blocked = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]})
    assert blocked.status_code == 409 and "Site induction" in blocked.text

    checks = {row["check_type"]: row for row in deployment["checks"]}
    assert checks["Qualifications"]["status"] == "Not required"
    docs = checks["Personnel documents"]
    induction = checks["Site induction"]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/checks/{docs['id']}", json={"status": "Verified", "evidence": "", "version": docs["version"]}).status_code == 422
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/checks/{docs['id']}", json={"status": "Verified", "evidence": "ID and contract seen", "version": docs["version"]}).status_code == 200
    wrong_owner = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/checks/{induction['id']}", json={"status": "Verified", "evidence": "Induction card", "version": induction["version"]})
    assert wrong_owner.status_code == 403 and "HSE" in wrong_owner.text
    sign_in(c, "hse2@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/checks/{induction['id']}", json={"status": "Verified", "evidence": "Induction card 44", "version": induction["version"]}).status_code == 200

    sign_in(c, "hr2@alpha.test")
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    missing = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]})
    assert missing.status_code == 422 and "Mandatory reviewer" in missing.text
    sign_in(c)
    _route(c, pid, "hr.deployment", pm_id)
    _route(c, pid, "hr.request", pm_id)
    sign_in(c, "hr2@alpha.test")
    sent = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]})
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "Pending Approval"

    sign_in(c, "pm2@alpha.test")
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert _decide(c, deployment["review"]).status_code == 200
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert deployment["status"] == "Approved for Mobilization"

    # Workforce request from site engineering.
    sign_in(c, "se2@alpha.test")
    request = c.post(
        f"/api/projects/{pid}/hr/requests",
        json={"number": "WR-1", "company_id": company, "trade_id": trade, "headcount": 2, "start_date": "2026-10-10", "end_date": "2026-11-30", "justification": "Pile cap rebar"},
    )
    assert request.status_code == 201, request.text
    row = c.get(f"/api/projects/{pid}/hr").json()["requests"][0]
    assert c.post(f"/api/projects/{pid}/hr/requests/{row['id']}/submit", json={"version": row["version"]}).status_code == 200
    sign_in(c, "pm2@alpha.test")
    row = c.get(f"/api/projects/{pid}/hr").json()["requests"][0]
    assert _decide(c, row["review"]).status_code == 200

    sign_in(c, "hr2@alpha.test")
    row = c.get(f"/api/projects/{pid}/hr").json()["requests"][0]
    assert row["status"] == "Open"
    proposed = c.post(f"/api/projects/{pid}/hr/requests/{row['id']}/lines", json={"personnel_id": person, "state": "Proposed", "version": row["version"]})
    assert proposed.status_code == 200, proposed.text
    row = c.get(f"/api/projects/{pid}/hr").json()["requests"][0]
    assert row["counts"] == {"required": 2, "proposed": 1, "allocated": 0, "shortfall": 2}
    no_deployment = c.post(f"/api/projects/{pid}/hr/requests/{row['id']}/lines", json={"personnel_id": person, "state": "Allocated", "version": row["version"]})
    assert no_deployment.status_code == 422
    allocated = c.post(
        f"/api/projects/{pid}/hr/requests/{row['id']}/lines",
        json={"personnel_id": person, "state": "Allocated", "deployment_id": deployment["id"], "version": row["version"]},
    )
    assert allocated.status_code == 200, allocated.text
    board = c.get(f"/api/projects/{pid}/hr").json()
    row = board["requests"][0]
    assert row["status"] == "Partially Allocated"
    assert row["counts"] == {"required": 2, "proposed": 0, "allocated": 1, "shortfall": 1}
    assert board["counts"]["shortfall"] == 1
    assert board["counts"]["deployed"] == 0

    deployment = board["deployments"][0]
    mobilized = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": "2026-10-06", "version": deployment["version"]})
    assert mobilized.status_code == 200, mobilized.text
    board = c.get(f"/api/projects/{pid}/hr").json()
    assert board["counts"]["deployed"] == 1
    deployment = board["deployments"][0]
    out = c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "demobilize", "on": "2026-10-20", "version": deployment["version"]})
    assert out.status_code == 409 and "offboarding" in out.text
    with maker() as db:
        assert db.query(Membership).count() == members_before


def test_crews_shifts_attendance_corrections_and_locks(env):
    from datetime import date, timedelta

    c, _maker = env
    day = date.today() - timedelta(days=1)
    iso = lambda d: d.isoformat()
    at = lambda d, hm: f"{d.isoformat()}T{hm}"
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    pid = new_project(c, code="HR-03", client_company_id=company).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Welder"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Welder"}).json()["id"]
    body = _person(company, designation, trade)
    body["start_date"] = iso(day - timedelta(days=60))
    person = c.post(f"/api/projects/{pid}/hr/personnel", json=body).json()["id"]

    hr_id = _user(c, "hr3@alpha.test", "HR Three", company)
    _member(c, pid, hr_id, roles["HR"], company, [])
    sup_id = _user(c, "sup3@alpha.test", "Sup Three", company)
    _member(c, pid, sup_id, roles["Supervisor"], company, [])
    pm_id = _user(c, "pm3@alpha.test", "PM Three", company)
    _member(c, pid, pm_id, roles["Project Manager"], company, [])
    for record_type in ("hr.deployment", "hr.attendance", "hr.correction"):
        _route(c, pid, record_type, pm_id)

    sign_in(c, "hr3@alpha.test")
    made = c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": person, "planned_start": iso(day - timedelta(days=10)), "checks": []})
    assert made.status_code == 201, made.text
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm3@alpha.test")
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/reviews/{deployment['review']['id']}/decisions", json={"action": "approve", "reason": "", "comment": "", "version": deployment["review"]["version"]}).status_code == 200
    sign_in(c, "hr3@alpha.test")
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": iso(day - timedelta(days=5)), "version": deployment["version"]}).status_code == 200

    # Shifts
    long_break = {"code": "BAD", "name": "Bad", "start_time": "08:00", "end_time": "09:00", "break_minutes": 90, "effective_from": iso(day - timedelta(days=30))}
    assert c.post(f"/api/projects/{pid}/hr/shifts", json=long_break).status_code == 422
    day_shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "break_minutes": 60, "effective_from": iso(day - timedelta(days=30))})
    assert day_shift.status_code == 201, day_shift.text
    night = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "NIGHT", "name": "Night", "start_time": "20:00", "end_time": "06:00", "break_minutes": 30, "attribution": "Start day", "effective_from": iso(day - timedelta(days=30))})
    assert night.status_code == 201
    day_id, night_id = day_shift.json()["id"], night.json()["id"]
    shifts = {row["code"]: row for row in c.get(f"/api/projects/{pid}/hr").json()["shifts"]}
    assert shifts["NIGHT"]["overnight"] is True and shifts["NIGHT"]["scheduled"] == "9:30"
    assert shifts["DAY"]["scheduled"] == "8:00"

    # Crews
    crew = c.post(f"/api/projects/{pid}/hr/crews", json={"code": "C1", "company_id": company, "shift_id": day_id, "effective_from": iso(day - timedelta(days=30))})
    assert crew.status_code == 201, crew.text
    crew_id = crew.json()["id"]
    other = c.post(f"/api/projects/{pid}/hr/crews", json={"code": "C2", "company_id": company, "effective_from": iso(day - timedelta(days=30))}).json()["id"]
    early = c.post(f"/api/projects/{pid}/hr/crews/{crew_id}/members", json={"personnel_id": person, "start_date": iso(day - timedelta(days=20)), "version": 1})
    assert early.status_code == 422 and "deployment" in early.text
    joined = c.post(f"/api/projects/{pid}/hr/crews/{crew_id}/members", json={"personnel_id": person, "start_date": iso(day - timedelta(days=5)), "version": 1})
    assert joined.status_code == 201, joined.text
    twice = c.post(f"/api/projects/{pid}/hr/crews/{other}/members", json={"personnel_id": person, "start_date": iso(day), "version": 1})
    assert twice.status_code == 409 and "C1" in twice.text

    # Attendance
    sign_in(c, "sup3@alpha.test")
    future = c.post(f"/api/projects/{pid}/hr/attendance", json={"shift_id": day_id, "crew_id": crew_id, "attendance_date": iso(date.today() + timedelta(days=1))})
    assert future.status_code == 422
    sheet = c.post(f"/api/projects/{pid}/hr/attendance", json={"shift_id": day_id, "crew_id": crew_id, "attendance_date": iso(day)})
    assert sheet.status_code == 201, sheet.text
    sheet_id, version = sheet.json()["id"], sheet.json()["version"]
    assert c.post(f"/api/projects/{pid}/hr/attendance", json={"shift_id": day_id, "crew_id": crew_id, "attendance_date": iso(day)}).status_code == 409
    record = lambda status, segs, v: {"personnel_id": person, "status": status, "segments": [{"check_in": a, "check_out": b} for a, b in segs], "version": v}
    assert c.post(f"/api/projects/{pid}/hr/attendance/{sheet_id}/records", json=record("Present", [], version)).status_code == 422
    assert c.post(f"/api/projects/{pid}/hr/attendance/{sheet_id}/records", json=record("Absent", [(at(day, "08:00"), at(day, "17:00"))], version)).status_code == 422
    put = c.post(f"/api/projects/{pid}/hr/attendance/{sheet_id}/records", json=record("Present", [(at(day, "07:00"), at(day, "12:00")), (at(day, "13:00"), at(day, "19:00"))], version))
    assert put.status_code == 200, put.text
    version = put.json()["sheet_version"]
    row = c.get(f"/api/projects/{pid}/hr").json()["sheets"][0]["records"][0]
    assert (row["worked"], row["regular"], row["overtime"]) == ("11:00", "8:00", "3:00")

    night_sheet = c.post(f"/api/projects/{pid}/hr/attendance", json={"shift_id": night_id, "attendance_date": iso(day)}).json()
    clash = c.post(f"/api/projects/{pid}/hr/attendance/{night_sheet['id']}/records", json=record("Present", [(at(day, "18:00"), at(day + timedelta(days=1), "04:00"))], night_sheet["version"]))
    assert clash.status_code == 409
    wrong_day = c.post(f"/api/projects/{pid}/hr/attendance/{night_sheet['id']}/records", json=record("Present", [(at(day - timedelta(days=1), "20:00"), at(day, "06:00"))], night_sheet["version"]))
    assert wrong_day.status_code == 422 and "check-in" in wrong_day.text
    overnight = c.post(f"/api/projects/{pid}/hr/attendance/{night_sheet['id']}/records", json=record("Present", [(at(day, "20:00"), at(day + timedelta(days=1), "06:00"))], night_sheet["version"]))
    assert overnight.status_code == 200, overnight.text
    night_row = next(s for s in c.get(f"/api/projects/{pid}/hr").json()["sheets"] if s["id"] == night_sheet["id"])["records"][0]
    assert (night_row["worked"], night_row["overtime"]) == ("9:30", "0:00")

    sent = c.post(f"/api/projects/{pid}/hr/attendance/{sheet_id}/submit", json={"version": version})
    assert sent.status_code == 200, sent.text
    assert c.post(f"/api/projects/{pid}/hr/attendance/{sheet_id}/records", json=record("Absent", [], version + 1)).status_code == 409
    sign_in(c, "pm3@alpha.test")
    sheet_row = next(s for s in c.get(f"/api/projects/{pid}/hr").json()["sheets"] if s["id"] == sheet_id)
    assert c.post(f"/api/reviews/{sheet_row['review']['id']}/decisions", json={"action": "approve", "reason": "", "comment": "", "version": sheet_row["review"]["version"]}).status_code == 200
    sheet_row = next(s for s in c.get(f"/api/projects/{pid}/hr").json()["sheets"] if s["id"] == sheet_id)
    assert sheet_row["status"] == "Approved"

    # Correction keeps the original
    sign_in(c, "sup3@alpha.test")
    record_id = sheet_row["records"][0]["id"]
    fix = {
        "kind": "Missing punch",
        "status": "Present",
        "segments": [{"check_in": at(day, "07:00"), "check_out": at(day, "12:00")}, {"check_in": at(day, "13:00"), "check_out": at(day, "17:00")}],
        "reason": "Left at 17:00, gate log",
        "evidence": "Gate log page 4",
    }
    asked = c.post(f"/api/projects/{pid}/hr/attendance/records/{record_id}/corrections", json=fix)
    assert asked.status_code == 201, asked.text
    assert c.post(f"/api/projects/{pid}/hr/attendance/records/{record_id}/corrections", json=fix).status_code == 409
    sign_in(c, "pm3@alpha.test")
    correction = c.get(f"/api/projects/{pid}/hr").json()["corrections"][0]
    assert c.post(f"/api/reviews/{correction['review']['id']}/decisions", json={"action": "approve", "reason": "", "comment": "", "version": correction["review"]["version"]}).status_code == 200
    board = c.get(f"/api/projects/{pid}/hr").json()
    correction = board["corrections"][0]
    assert correction["status"] == "Approved"
    assert correction["original"]["worked"] == "11:00" and correction["proposed"]["worked"] == "9:00"
    fixed = next(s for s in board["sheets"] if s["id"] == sheet_id)["records"][0]
    assert (fixed["worked"], fixed["overtime"]) == ("9:00", "1:00")

    # Period locks
    sign_in(c, "hr3@alpha.test")
    blocked = c.post(f"/api/projects/{pid}/hr/attendance-locks", json={"period_start": iso(day), "period_end": iso(day)})
    assert blocked.status_code == 409 and "not decided" in blocked.text
    lock = c.post(f"/api/projects/{pid}/hr/attendance-locks", json={"period_start": iso(day - timedelta(days=4)), "period_end": iso(day - timedelta(days=2)), "reason": "Week closed"})
    assert lock.status_code == 201, lock.text
    assert c.post(f"/api/projects/{pid}/hr/attendance-locks", json={"period_start": iso(day - timedelta(days=3)), "period_end": iso(day - timedelta(days=3))}).status_code == 409
    sign_in(c, "sup3@alpha.test")
    locked = c.post(f"/api/projects/{pid}/hr/attendance", json={"shift_id": day_id, "attendance_date": iso(day - timedelta(days=3))})
    assert locked.status_code == 409 and "locked" in locked.text
    sign_in(c, "hr3@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/attendance-locks/{lock.json()['id']}/reopen", json={"reason": "x"}).status_code == 422
    assert c.post(f"/api/projects/{pid}/hr/attendance-locks/{lock.json()['id']}/reopen", json={"reason": "Late gate log"}).status_code == 200
    sign_in(c, "sup3@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/attendance", json={"shift_id": day_id, "attendance_date": iso(day - timedelta(days=3))}).status_code == 201


def test_leave_and_overtime_keep_requested_approved_attended_and_payable_apart(env):
    from datetime import date, timedelta

    c, _maker = env
    today = date.today()
    day = today - timedelta(days=1)
    iso = lambda d: d.isoformat()
    at = lambda d, hm: f"{d.isoformat()}T{hm}"
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    pid = new_project(c, code="HR-04", client_company_id=company).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Mason"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Mason"}).json()["id"]
    annual = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Leave type", "name": "Annual leave"})
    assert annual.status_code == 201, annual.text
    annual = annual.json()["id"]
    body = _person(company, designation, trade)
    body["start_date"] = iso(day - timedelta(days=60))
    person = c.post(f"/api/projects/{pid}/hr/personnel", json=body).json()["id"]

    hr_id = _user(c, "hr4@alpha.test", "HR Four", company)
    _member(c, pid, hr_id, roles["HR"], company, [])
    sup_id = _user(c, "sup4@alpha.test", "Sup Four", company)
    _member(c, pid, sup_id, roles["Supervisor"], company, [])
    pm_id = _user(c, "pm4@alpha.test", "PM Four", company)
    _member(c, pid, pm_id, roles["Project Manager"], company, [])
    se_id = _user(c, "se4@alpha.test", "SE Four", company)
    _member(c, pid, se_id, roles["Site Engineer"], company, [])
    for record_type in ("hr.deployment", "hr.attendance"):
        _route(c, pid, record_type, pm_id)

    sign_in(c, "hr4@alpha.test")
    c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": person, "planned_start": iso(day - timedelta(days=10)), "checks": []})
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm4@alpha.test")
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert _decide(c, deployment["review"]).status_code == 200
    sign_in(c, "hr4@alpha.test")
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": iso(day - timedelta(days=5)), "version": deployment["version"]}).status_code == 200
    shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "break_minutes": 60, "effective_from": iso(day - timedelta(days=30))}).json()["id"]
    crew = c.post(f"/api/projects/{pid}/hr/crews", json={"code": "M1", "company_id": company, "shift_id": shift, "effective_from": iso(day - timedelta(days=30))}).json()["id"]
    assert c.post(f"/api/projects/{pid}/hr/crews/{crew}/members", json={"personnel_id": person, "start_date": iso(day - timedelta(days=5)), "version": 1}).status_code == 201

    # Leave
    leave = {"personnel_id": person, "leave_type_id": trade, "start_date": iso(today), "end_date": iso(today + timedelta(days=2)), "reason": "Family wedding"}
    sign_in(c, "pm4@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/leave", json={**leave, "leave_type_id": annual}).status_code == 403
    sign_in(c, "sup4@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/leave", json=leave).status_code == 422
    leave["leave_type_id"] = annual
    backwards = {**leave, "end_date": iso(today - timedelta(days=1))}
    assert c.post(f"/api/projects/{pid}/hr/leave", json=backwards).status_code == 422
    made = c.post(f"/api/projects/{pid}/hr/leave", json=leave)
    assert made.status_code == 201, made.text
    assert c.post(f"/api/projects/{pid}/hr/leave", json={**leave, "start_date": iso(today + timedelta(days=1))}).status_code == 409
    row = c.get(f"/api/projects/{pid}/hr").json()["leaves"][0]
    missing = c.post(f"/api/projects/{pid}/hr/leave/{row['id']}/submit", json={"version": row["version"]})
    assert missing.status_code == 422 and "Mandatory reviewer" in missing.text
    sign_in(c)
    _route(c, pid, "hr.leave", pm_id)
    _route(c, pid, "hr.overtime", pm_id)
    sign_in(c, "sup4@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/leave/{row['id']}/submit", json={"version": row["version"]}).status_code == 200
    row = c.get(f"/api/projects/{pid}/hr").json()["leaves"][0]
    assert row["reason"] == "Family wedding"
    assert "Crew M1" in row["effects"]
    sign_in(c, "se4@alpha.test")
    hidden = c.get(f"/api/projects/{pid}/hr").json()["leaves"][0]
    assert hidden["reason"] is None and hidden["evidence"] is None
    sign_in(c, "pm4@alpha.test")
    board = c.get(f"/api/projects/{pid}/hr").json()
    assert board["counts"]["pending_leave"] == 1
    available = board["counts"]["available_today"]
    assert _decide(c, board["leaves"][0]["review"]).status_code == 200
    board = c.get(f"/api/projects/{pid}/hr").json()
    assert board["leaves"][0]["status"] == "Approved"
    assert board["counts"]["on_leave_today"] == 1
    assert board["counts"]["available_today"] == available - 1
    approved = board["leaves"][0]

    # Overtime
    sign_in(c, "se4@alpha.test")
    neither = c.post(f"/api/projects/{pid}/hr/overtime", json={"work_date": iso(day), "shift_id": shift, "requested_minutes": 180, "reason": "Slab pour"})
    assert neither.status_code == 422
    both = c.post(f"/api/projects/{pid}/hr/overtime", json={"personnel_id": person, "crew_id": crew, "work_date": iso(day), "shift_id": shift, "requested_minutes": 180, "reason": "Slab pour"})
    assert both.status_code == 422
    ask = c.post(f"/api/projects/{pid}/hr/overtime", json={"crew_id": crew, "work_date": iso(day), "shift_id": shift, "requested_minutes": 180, "reason": "Slab pour"})
    assert ask.status_code == 201, ask.text
    assert c.post(f"/api/projects/{pid}/hr/overtime", json={"crew_id": crew, "work_date": iso(day), "shift_id": shift, "requested_minutes": 60, "reason": "Again"}).status_code == 409
    ot = c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]
    assert ot["target"] == "Crew M1" and ot["requested"] == "3:00" and ot["approved"] is None
    assert c.post(f"/api/projects/{pid}/hr/overtime/{ot['id']}/submit", json={"version": ot["version"]}).status_code == 200
    ot = c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]
    assert ot["can_set_hours"] is False
    assert c.post(f"/api/projects/{pid}/hr/overtime/{ot['id']}/hours", json={"approved_minutes": 120, "version": ot["version"]}).status_code == 403

    sign_in(c, "pm4@alpha.test")
    ot = c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]
    assert ot["can_set_hours"] is True
    assert c.post(f"/api/projects/{pid}/hr/overtime/{ot['id']}/hours", json={"approved_minutes": 240, "version": ot["version"]}).status_code == 422
    assert c.post(f"/api/projects/{pid}/hr/overtime/{ot['id']}/hours", json={"approved_minutes": 120, "version": ot["version"]}).status_code == 200
    ot = c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]
    assert _decide(c, ot["review"]).status_code == 200
    ot = c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]
    assert (ot["status"], ot["requested"], ot["approved"]) == ("Approved", "3:00", "2:00")
    assert ot["lines"][0]["attended"] == "0:00" and ot["lines"][0]["payable"] == "0:00"

    # Attended comes only from approved attendance; payable is the smaller of approved and attended.
    sign_in(c, "sup4@alpha.test")
    sheet = c.post(f"/api/projects/{pid}/hr/attendance", json={"shift_id": shift, "crew_id": crew, "attendance_date": iso(day)}).json()
    put = c.post(
        f"/api/projects/{pid}/hr/attendance/{sheet['id']}/records",
        json={"personnel_id": person, "status": "Present", "segments": [{"check_in": at(day, "07:00"), "check_out": at(day, "12:00")}, {"check_in": at(day, "13:00"), "check_out": at(day, "19:00")}], "version": sheet["version"]},
    )
    assert put.status_code == 200, put.text
    ot = c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]
    assert ot["lines"][0]["attended"] == "0:00"
    assert c.post(f"/api/projects/{pid}/hr/attendance/{sheet['id']}/submit", json={"version": put.json()["sheet_version"]}).status_code == 200
    sign_in(c, "pm4@alpha.test")
    sheet_row = c.get(f"/api/projects/{pid}/hr").json()["sheets"][0]
    assert _decide(c, sheet_row["review"]).status_code == 200
    ot = c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]
    assert (ot["lines"][0]["attended"], ot["lines"][0]["payable"]) == ("3:00", "2:00")

    sign_in(c, "se4@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/leave/{approved['id']}/cancel", json={"reason": "Trip called off", "version": approved["version"]}).status_code == 403
    sign_in(c, "hr4@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/leave/{approved['id']}/cancel", json={"reason": "Trip called off", "version": approved["version"]}).status_code == 200
    board = c.get(f"/api/projects/{pid}/hr").json()
    assert board["leaves"][0]["status"] == "Cancelled" and board["counts"]["on_leave_today"] == 0


def test_overtime_approver_cannot_approve_their_own(env):
    from datetime import date, timedelta

    c, _maker = env
    day = date.today() - timedelta(days=1)
    iso = lambda d: d.isoformat()
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    pid = new_project(c, code="HR-05", client_company_id=company).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Rigger"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Rigger"}).json()["id"]
    body = _person(company, designation, trade, code="W-050")
    body["start_date"] = iso(day - timedelta(days=60))
    person = c.post(f"/api/projects/{pid}/hr/personnel", json=body).json()["id"]
    cm_id = _user(c, "cm5@alpha.test", "CM Five", company)
    _member(c, pid, cm_id, roles["Construction Manager"], company, [])
    for record_type in ("hr.deployment", "hr.overtime"):
        _route(c, pid, record_type, cm_id)
    c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": person, "planned_start": iso(day - timedelta(days=10)), "checks": []})
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "cm5@alpha.test")
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert _decide(c, deployment["review"]).status_code == 200
    shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "effective_from": iso(day - timedelta(days=30))})
    assert shift.status_code == 403
    sign_in(c)
    shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "effective_from": iso(day - timedelta(days=30))}).json()["id"]

    sign_in(c, "cm5@alpha.test")
    ask = c.post(f"/api/projects/{pid}/hr/overtime", json={"personnel_id": person, "work_date": iso(day), "shift_id": shift, "requested_minutes": 120, "reason": "Crane lift"})
    assert ask.status_code == 201, ask.text
    ot = c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]
    assert c.post(f"/api/projects/{pid}/hr/overtime/{ot['id']}/submit", json={"version": ot["version"]}).status_code == 200
    ot = c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]
    own = _decide(c, ot["review"])
    assert own.status_code in (403, 422), own.text
    assert c.get(f"/api/projects/{pid}/hr").json()["overtime"][0]["status"] == "Pending Approval"


def test_construction_labour_hours_reconcile_to_approved_attendance(env):
    from datetime import date, timedelta

    from .test_construction import _package, _progress_policy

    c, maker = env
    day = date.today() - timedelta(days=1)
    iso = lambda d: d.isoformat()
    at = lambda d, hm: f"{d.isoformat()}T{hm}"
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    pid = new_project(
        c,
        code="HR-06",
        client_company_id=company,
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    ).json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""}).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Carpenter"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Carpenter"}).json()["id"]
    body = _person(company, designation, trade, code="W-060")
    body["start_date"] = iso(day - timedelta(days=60))
    person = c.post(f"/api/projects/{pid}/hr/personnel", json=body).json()["id"]
    idle_body = _person(company, designation, trade, code="W-061")
    idle_body["start_date"] = iso(day - timedelta(days=60))
    benched = c.post(f"/api/projects/{pid}/hr/personnel", json=idle_body).json()["id"]

    pm_id = _user(c, "pm6@alpha.test", "PM Six", company)
    _member(c, pid, pm_id, roles["Project Manager"], company, [])
    se_id = _user(c, "se6@alpha.test", "SE Six", company)
    _member(c, pid, se_id, roles["Site Engineer"], company, [])
    _member(c, pid, me["id"], roles["Discipline Head"], company, [])
    for record_type in ("hr.deployment", "hr.attendance"):
        _route(c, pid, record_type, pm_id)
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(civil, me["id"])).status_code == 201

    c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": person, "planned_start": iso(day - timedelta(days=10)), "checks": []})
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm6@alpha.test")
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert _decide(c, deployment["review"]).status_code == 200
    sign_in(c)
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": iso(day - timedelta(days=5)), "version": deployment["version"]}).status_code == 200
    shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "break_minutes": 60, "effective_from": iso(day - timedelta(days=30))}).json()["id"]
    sheet = c.post(f"/api/projects/{pid}/hr/attendance", json={"shift_id": shift, "attendance_date": iso(day)}).json()
    put = c.post(
        f"/api/projects/{pid}/hr/attendance/{sheet['id']}/records",
        json={"personnel_id": person, "status": "Present", "segments": [{"check_in": at(day, "07:00"), "check_out": at(day, "12:00")}, {"check_in": at(day, "13:00"), "check_out": at(day, "19:00")}], "version": sheet["version"]},
    )
    assert put.status_code == 200, put.text
    assert c.post(f"/api/projects/{pid}/hr/attendance/{sheet['id']}/submit", json={"version": put.json()["sheet_version"]}).status_code == 200
    sign_in(c, "pm6@alpha.test")
    assert _decide(c, c.get(f"/api/projects/{pid}/hr").json()["sheets"][0]["review"]).status_code == 200

    # Construction daily report with per-person labour
    sign_in(c, "se6@alpha.test")
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area, company, civil, code="WP-LAB")).json()
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={"package_id": package["id"], "code": "FORM", "name": "Formwork", "quantity": "100", "unit": "m2", "company_id": company, "measurement_method": "Quantity", "predecessor_ids": []},
    ).json()
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, package["id"])
        row.status = "In Progress"
        row.release_state = "Released"
        db.commit()
    report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json={"number": "DPR-L1", "report_date": iso(day), "shift": "Day", "discipline_id": civil, "area_id": area, "company_id": company, "site_engineer_id": se_id, "weather": "", "remarks": ""},
    ).json()
    view = c.post(f"/api/projects/{pid}/construction/progress/{report['id']}/lines", json={"activity_id": activity["id"], "quantity": "20"}).json()
    line = view["lines"][0]["id"]
    labour = f"/api/projects/{pid}/construction/progress/{report['id']}/lines/{line}/labour"
    board = c.get(f"/api/projects/{pid}/construction/progress").json()
    assert [row["id"] for row in board["labour_people"]] == [person]
    assert "not attendance" in board["labour_note"]
    assert c.post(labour, json={"personnel_id": benched, "productive_minutes": 60}).status_code == 422
    assert c.post(labour, json={"personnel_id": person}).status_code == 422
    no_reason = c.post(labour, json={"personnel_id": person, "productive_minutes": 480, "idle_minutes": 60})
    assert no_reason.status_code == 422 and "idle" in no_reason.text
    added = c.post(labour, json={"personnel_id": person, "productive_minutes": 480, "idle_minutes": 60, "idle_reason": "Waiting for crane"})
    assert added.status_code == 201, added.text
    entry = added.json()["lines"][0]["labour"][0]
    assert (entry["productive"], entry["idle"], entry["idle_reason"]) == ("8:00", "1:00", "Waiting for crane")
    assert c.post(labour, json={"personnel_id": person, "productive_minutes": 30}).status_code == 409
    second = c.post(f"/api/projects/{pid}/construction/progress/{report['id']}/lines", json={"activity_id": activity["id"], "quantity": "5"}).json()
    over = c.post(f"/api/projects/{pid}/construction/progress/{report['id']}/lines/{second['lines'][1]['id']}/labour", json={"personnel_id": person, "productive_minutes": 1000})
    assert over.status_code == 409 and "24 hours" in over.text

    # Pending reports are not reconciled.
    sign_in(c)
    recon = c.get(f"/api/projects/{pid}/hr").json()["reconciliation"]
    assert len(recon) == 1
    row = recon[0]
    assert (row["attendance"], row["activity"], row["idle"], row["unallocated"]) == ("11:00", "0:00", "0:00", "11:00")
    assert row["exceptions"] == ["Overtime worked beyond approval by 3:00"]

    sign_in(c, "se6@alpha.test")
    current = next(r for r in c.get(f"/api/projects/{pid}/construction/progress").json()["reports"] if r["id"] == report["id"])
    assert c.post(f"/api/projects/{pid}/construction/progress/{report['id']}/submit", json={"version": current["version"]}).status_code == 200
    assert c.post(labour, json={"personnel_id": person, "productive_minutes": 30}).status_code == 409
    sign_in(c)
    current = next(r for r in c.get(f"/api/projects/{pid}/construction/progress").json()["reports"] if r["id"] == report["id"])
    assert _decide(c, current["review"]).status_code == 200
    board = c.get(f"/api/projects/{pid}/hr").json()
    row = board["reconciliation"][0]
    assert (row["attendance"], row["activity"], row["idle"], row["unallocated"]) == ("11:00", "8:00", "1:00", "2:00")
    assert board["counts"]["recon_exceptions"] == 1
    assert "not attendance" in board["reconciliation_note"]


def test_qualifications_are_verified_by_their_owner_and_gate_labour_hse_and_quality(env):
    from datetime import date, timedelta
    from types import SimpleNamespace

    from app.domains.coordination.models import Job
    from app.domains.identity_projects.models import Project

    from .test_construction import _package, _progress_policy

    c, maker = env
    today = date.today()
    day = today - timedelta(days=1)
    iso = lambda d: d.isoformat()
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    catalog = c.get("/api/catalog").json()
    civil = next(row["id"] for row in catalog["disciplines"] if row["name"] == "Civil")
    pid = new_project(
        c,
        code="HR-07",
        client_company_id=company,
        discipline_ids=[civil],
        disciplines=[{"discipline_id": civil, "scope_description": "Civil", "active": True}],
    ).json()["id"]
    area = c.post(f"/api/projects/{pid}/areas", json={"code": "U1", "name": "Unit 1", "area_type": "Unit", "description": ""}).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Rigger"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Rigger"}).json()["id"]
    people = {}
    for login, title, role in (
        ("hr7@alpha.test", "HR Seven", "HR"),
        ("hse7@alpha.test", "HSE Seven", "HSE"),
        ("qa7@alpha.test", "QA Seven", "QA/QC"),
        ("qb7@alpha.test", "QA Eight", "QA/QC"),
        ("pm7@alpha.test", "PM Seven", "Project Manager"),
        ("se7@alpha.test", "SE Seven", "Site Engineer"),
    ):
        people[login] = _user(c, login, title, company)
        _member(c, pid, people[login], roles[role], company, [])
    _member(c, pid, me["id"], roles["Discipline Head"], company, [])
    start = iso(today - timedelta(days=200))
    worker = c.post(f"/api/projects/{pid}/hr/personnel", json={**_person(company, designation, trade, code="W-070"), "start_date": start}).json()["id"]
    inspector = c.post(
        f"/api/projects/{pid}/hr/personnel",
        json={**_person(company, designation, trade, code="W-071"), "start_date": start, "user_id": people["qa7@alpha.test"]},
    ).json()["id"]

    # Types are an HR list; each names the owner that verifies it.
    sign_in(c, "hse7@alpha.test")
    assert c.post(f"/api/projects/{pid}/hr/credential-types", json={"name": "Working at height", "owner": "HSE"}).status_code == 403
    sign_in(c, "hr7@alpha.test")
    types = {}
    for name, owner, expiry in (("Working at height", "HSE", True), ("Weld inspector", "QA/QC", True), ("Rigger card", "HR", False)):
        made = c.post(f"/api/projects/{pid}/hr/credential-types", json={"name": name, "owner": owner, "requires_expiry": expiry})
        assert made.status_code == 201, made.text
        types[name] = made.json()["id"]
    assert c.post(f"/api/projects/{pid}/hr/credential-types", json={"name": "working AT height", "owner": "HR"}).status_code == 409

    url = f"/api/projects/{pid}/hr/credentials"
    wah = {"personnel_id": worker, "type_id": types["Working at height"], "certificate_number": "WAH-1", "issuer": "NSC", "issue_date": iso(today - timedelta(days=100)), "evidence": "Card sighted"}
    assert c.post(url, json=wah).status_code == 422
    assert c.post(url, json={**wah, "issue_date": iso(today + timedelta(days=1)), "expiry_date": iso(today + timedelta(days=20))}).status_code == 422
    wah["expiry_date"] = iso(today + timedelta(days=20))
    made = c.post(url, json=wah)
    assert made.status_code == 201, made.text
    assert c.post(url, json=wah).status_code == 409
    clash = c.post(url, json={**wah, "personnel_id": inspector})
    assert clash.status_code == 409 and "another person" in clash.text

    record = next(row for row in c.get(f"/api/projects/{pid}/hr").json()["credentials"] if row["id"] == made.json()["id"])
    assert record["status"] == "Pending Verification" and record["owner"] == "HSE" and record["can_decide"] is False
    decide = f"{url}/{record['id']}/decide"
    assert c.post(decide, json={"action": "verify", "version": record["version"]}).status_code == 403
    sign_in(c, "hse7@alpha.test")
    assert c.post(decide, json={"action": "reject", "reason": "", "version": record["version"]}).status_code == 422
    verified = c.post(decide, json={"action": "verify", "reason": "Checked with NSC", "version": record["version"]})
    assert verified.status_code == 200 and verified.json()["status"] == "Verified"
    with maker() as db:
        keys = {row.dedupe_key for row in db.query(Job).filter_by(kind="hr.credential.alert")}
        assert keys == {f"hr:credential:{record['id']}:expiring:{wah['expiry_date']}", f"hr:credential:{record['id']}:expired:{wah['expiry_date']}"}

    # Whoever enters a record cannot verify it, and nobody verifies their own.
    sign_in(c)
    rigger = c.post(url, json={"personnel_id": worker, "type_id": types["Rigger card"], "issue_date": iso(today - timedelta(days=90)), "evidence": "Card sighted"}).json()
    rigger_row = next(row for row in c.get(f"/api/projects/{pid}/hr").json()["credentials"] if row["id"] == rigger["id"])
    assert rigger_row["can_decide"] is False and "entered" in rigger_row["decide_block"]
    assert c.post(f"{url}/{rigger['id']}/decide", json={"action": "verify", "version": rigger["version"]}).status_code == 403

    sign_in(c, "qa7@alpha.test")
    weld = c.post(url, json={"personnel_id": inspector, "type_id": types["Weld inspector"], "certificate_number": "CSWIP-9", "issuer": "TWI", "issue_date": iso(today - timedelta(days=30)), "expiry_date": iso(today + timedelta(days=700)), "evidence": "Certificate copy"})
    assert weld.status_code == 201, weld.text
    assert c.post(url, json={**wah, "personnel_id": worker, "certificate_number": "X"}).status_code == 403
    sign_in(c, "hr7@alpha.test")
    hse_card = c.post(url, json={"personnel_id": inspector, "type_id": types["Working at height"], "certificate_number": "WAH-2", "issuer": "NSC", "issue_date": iso(today - timedelta(days=10)), "expiry_date": iso(today + timedelta(days=300)), "evidence": "Card sighted"}).json()
    sign_in(c, "qb7@alpha.test")
    assert c.post(f"{url}/{weld.json()['id']}/decide", json={"action": "verify", "version": weld.json()["version"]}).status_code == 200
    sign_in(c, "hse7@alpha.test")
    assert c.post(f"{url}/{hse_card['id']}/decide", json={"action": "verify", "version": hse_card["version"]}).status_code == 200

    # HSE eligibility and Quality inspector coverage count the verified HR records of a linked login.
    with maker() as db:
        from app.domains.hse.field import eligible
        from app.domains.quality.competence import coverage_note, covers

        project = db.get(Project, pid)
        assert eligible(db, project, people["qa7@alpha.test"], "working at height", today) is True
        assert eligible(db, project, people["qa7@alpha.test"], "confined space", today) is False
        assert covers(db, project, people["qa7@alpha.test"], today) is True
        assert covers(db, project, people["qb7@alpha.test"], today) is False
        assert coverage_note(db, project, people["qa7@alpha.test"], today) == "A qualification was valid on the inspection date."
        assert "Quality or in HR" in coverage_note(db, project, people["qb7@alpha.test"], today)

    # Mobilize the worker and put a daily line in place.
    sign_in(c)
    _route(c, pid, "hr.deployment", people["pm7@alpha.test"])
    assert c.post(f"/api/projects/{pid}/approval-policies", json=_progress_policy(civil, me["id"])).status_code == 201
    c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": worker, "planned_start": iso(day - timedelta(days=10)), "checks": []})
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm7@alpha.test")
    assert _decide(c, c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]["review"]).status_code == 200
    sign_in(c)
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": iso(day - timedelta(days=5)), "version": deployment["version"]}).status_code == 200
    sign_in(c, "se7@alpha.test")
    package = c.post(f"/api/projects/{pid}/construction/packages", json=_package(area, company, civil, code="WP-Q")).json()
    activity = c.post(
        f"/api/projects/{pid}/construction/activities",
        json={"package_id": package["id"], "code": "LIFT", "name": "Lifting", "quantity": "10", "unit": "nos", "company_id": company, "measurement_method": "Quantity", "predecessor_ids": []},
    ).json()
    with maker() as db:
        from app.domains.construction.models import WorkPackage

        row = db.get(WorkPackage, package["id"])
        row.status = "In Progress"
        row.release_state = "Released"
        db.commit()

    # Requirements: the HR owner sets a project-wide one, HSE one for the package.
    rules = f"/api/projects/{pid}/hr/credential-rules"
    sign_in(c, "hse7@alpha.test")
    assert c.post(rules, json={"type_id": types["Rigger card"]}).status_code == 403
    assert c.post(rules, json={"type_id": types["Working at height"], "package_id": package["id"]}).status_code == 201
    assert c.post(rules, json={"type_id": types["Working at height"], "package_id": package["id"]}).status_code == 409
    sign_in(c, "hr7@alpha.test")
    assert c.post(rules, json={"type_id": types["Rigger card"]}).status_code == 201
    board = c.get(f"/api/projects/{pid}/hr").json()
    row = next(r for r in board["eligibility"] if r["personnel_id"] == worker)
    assert row["status"] == "Pending Verification"
    assert {(item["type"], item["status"]) for item in row["scoped"]} == {("Working at height", "Eligible")}
    assert board["counts"]["credentials_pending"] == 1 and board["counts"]["credentials_expiring"] == 1
    assert board["counts"]["not_eligible"] == 1

    sign_in(c, "se7@alpha.test")
    report = c.post(
        f"/api/projects/{pid}/construction/progress",
        json={"number": "DPR-Q1", "report_date": iso(day), "shift": "Day", "discipline_id": civil, "area_id": area, "company_id": company, "site_engineer_id": people["se7@alpha.test"], "weather": "", "remarks": ""},
    ).json()
    line = c.post(f"/api/projects/{pid}/construction/progress/{report['id']}/lines", json={"activity_id": activity["id"], "quantity": "2"}).json()["lines"][0]["id"]
    labour = f"/api/projects/{pid}/construction/progress/{report['id']}/lines/{line}/labour"
    blocked = c.post(labour, json={"personnel_id": worker, "productive_minutes": 240})
    assert blocked.status_code == 409 and "Rigger card (pending verification)" in blocked.text

    sign_in(c, "hr7@alpha.test")
    assert c.post(f"{url}/{rigger['id']}/decide", json={"action": "verify", "version": rigger["version"]}).status_code == 200
    sign_in(c, "se7@alpha.test")
    assert c.post(labour, json={"personnel_id": worker, "productive_minutes": 240}).status_code == 201

    # Withdrawing a required record blocks the submit as well.
    sign_in(c, "hr7@alpha.test")
    rigger_row = next(r for r in c.get(f"/api/projects/{pid}/hr").json()["credentials"] if r["id"] == rigger["id"])
    assert c.post(f"{url}/{rigger['id']}/withdraw", json={"reason": "Card revoked", "version": rigger_row["version"]}).status_code == 200
    sign_in(c, "se7@alpha.test")
    current = next(r for r in c.get(f"/api/projects/{pid}/construction/progress").json()["reports"] if r["id"] == report["id"])
    submit = c.post(f"/api/projects/{pid}/construction/progress/{report['id']}/submit", json={"version": current["version"]})
    assert submit.status_code == 422 and "not eligible" in submit.text

    # The expiry alert reaches the person's login and the verifier, without the full name.
    with maker() as db:
        from app.domains.workforce.credentials import alert

        job = SimpleNamespace(payload={"credential_id": hse_card["id"], "stage": "expired", "expiry": iso(today + timedelta(days=300))})
        alert(db, job)
        stale = SimpleNamespace(payload={"credential_id": hse_card["id"], "stage": "expired", "expiry": iso(today)})
        alert(db, stale)
        db.commit()
        sent = db.query(Notification).filter(Notification.title == "Qualification expired").all()
        assert {row.user_id for row in sent} == {people["qa7@alpha.test"], people["hse7@alpha.test"]}
        assert all("Arun" not in row.body and "W-071" in row.body for row in sent)


def test_offboarding_needs_checklist_and_approval_and_alerts_escalate_only_when_configured(env):
    from datetime import date, timedelta

    from app.domains.coordination.models import Task
    from app.domains.workforce.models import CrewMember
    from app.domains.workforce.monitor import scan

    c, maker = env
    today = date.today()
    iso = lambda d: d.isoformat()
    sign_in(c)
    roles, _disciplines, me = _ids(c)
    company = me["company_id"]
    pid = new_project(c, code="HR-08", client_company_id=company).json()["id"]
    other_pid = new_project(c, code="HR-08B", client_company_id=company).json()["id"]
    designation = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Designation", "name": "Scaffolder"}).json()["id"]
    trade = c.post(f"/api/projects/{pid}/hr/masters", json={"kind": "Trade", "name": "Scaffolder"}).json()["id"]
    hr_id = _user(c, "hr8@alpha.test", "HR Eight", company)
    _member(c, pid, hr_id, roles["HR"], company, [])
    pm_id = _user(c, "pm8@alpha.test", "PM Eight", company)
    _member(c, pid, pm_id, roles["Project Manager"], company, [])
    worker_login = _user(c, "w8@alpha.test", "Worker Eight", company)
    _member(c, pid, worker_login, roles["Supervisor"], company, [])
    _member(c, other_pid, worker_login, roles["Supervisor"], company, [])
    boss_login = _user(c, "sup8@alpha.test", "Boss Eight", company)
    _member(c, pid, boss_login, roles["Supervisor"], company, [])
    start = iso(today - timedelta(days=200))
    boss = c.post(f"/api/projects/{pid}/hr/personnel", json={**_person(company, designation, trade, code="W-081"), "start_date": start, "user_id": boss_login}).json()["id"]
    worker = c.post(f"/api/projects/{pid}/hr/personnel", json={**_person(company, designation, trade, code="W-080"), "start_date": start, "user_id": worker_login}).json()["id"]
    _route(c, pid, "hr.deployment", pm_id)
    c.post(f"/api/projects/{pid}/hr/deployments", json={"personnel_id": worker, "supervisor_id": boss, "planned_start": iso(today - timedelta(days=20)), "checks": []})
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/submit", json={"version": deployment["version"]}).status_code == 200
    sign_in(c, "pm8@alpha.test")
    assert _decide(c, c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]["review"]).status_code == 200
    sign_in(c)
    deployment = c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]
    assert c.post(f"/api/projects/{pid}/hr/deployments/{deployment['id']}/move", json={"action": "mobilize", "on": iso(today - timedelta(days=10)), "version": deployment["version"]}).status_code == 200
    shift = c.post(f"/api/projects/{pid}/hr/shifts", json={"code": "DAY", "name": "Day", "start_time": "08:00", "end_time": "17:00", "break_minutes": 60, "effective_from": iso(today - timedelta(days=30))}).json()["id"]
    crew = c.post(f"/api/projects/{pid}/hr/crews", json={"code": "S1", "company_id": company, "shift_id": shift, "effective_from": iso(today - timedelta(days=30))}).json()["id"]
    assert c.post(f"/api/projects/{pid}/hr/crews/{crew}/members", json={"personnel_id": worker, "start_date": iso(today - timedelta(days=10)), "version": 1}).status_code == 201
    with maker() as db:
        task = Task(organization_id=db.get(User, me["id"]).organization_id, project_id=pid, source_type="manual", source_id=0, title="Inspect scaffold tags", owner_id=worker_login, creator_id=me["id"])
        db.add(task)
        db.commit()
        task_id = task.id

    # Alerts are listed live, but nothing is sent before settings are saved.
    board = c.get(f"/api/projects/{pid}/hr").json()
    assert board["monitor_settings"]["saved"] is False
    missing = next(a for a in board["alerts"] if a["kind"] == "Attendance missing")
    assert missing["subject"] == "W-080" and missing["escalated"] is True and "Boss Eight" in missing["recipients"]
    with maker() as db:
        scan(db)
        db.commit()
        assert db.query(Notification).filter(Notification.title.like("%Attendance missing%")).count() == 0

    sign_in(c, "pm8@alpha.test")
    assert c.put(f"/api/projects/{pid}/hr/monitor", json={"escalation_user_ids": [pm_id]}).status_code == 403
    sign_in(c, "hr8@alpha.test")
    assert c.put(f"/api/projects/{pid}/hr/monitor", json={"escalation_user_ids": [999999]}).status_code == 422
    saved = c.put(f"/api/projects/{pid}/hr/monitor", json={"enabled": True, "escalate_after_days": 3, "escalation_user_ids": [pm_id]})
    assert saved.status_code == 200, saved.text
    assert c.put(f"/api/projects/{pid}/hr/monitor", json={"escalation_user_ids": [pm_id]}).status_code == 409
    with maker() as db:
        scan(db)
        scan(db)
        db.commit()
        first = db.query(Notification).filter_by(title="Attendance missing").all()
        assert [row.user_id for row in first] == [boss_login]
        escalated = db.query(Notification).filter_by(title="Escalated: Attendance missing").all()
        assert [row.user_id for row in escalated] == [pm_id]
        assert all("W-080" in row.body and "Arun" not in row.body for row in first + escalated)

    # Offboarding: checklist, open tasks, then approval.
    url = f"/api/projects/{pid}/hr/offboardings"
    assert c.post(url, json={"deployment_id": deployment["id"], "last_working_date": iso(today - timedelta(days=30))}).status_code == 422
    made = c.post(url, json={"deployment_id": deployment["id"], "last_working_date": iso(today - timedelta(days=1)), "reason": "Scope complete"})
    assert made.status_code == 201, made.text
    assert c.post(url, json={"deployment_id": deployment["id"], "last_working_date": iso(today)}).status_code == 409
    with maker() as db:
        told = {row.user_id for row in db.query(Notification).filter_by(title="Demobilization has open tasks")}
        assert told == {worker_login, boss_login}
    row = c.get(f"/api/projects/{pid}/hr").json()["offboardings"][0]
    assert row["findings"]["open_tasks"][0]["title"] == "Inspect scaffold tags"
    assert row["findings"]["crew_memberships"] == 1 and row["findings"]["other_project_memberships"] == 1
    items = {item["item"]: item for item in row["items"]}
    task_item = items["Open task reassignment"]
    base = f"{url}/{row['id']}/items"
    blocked = c.post(f"{base}/{task_item['id']}", json={"status": "Done", "note": "Handed over", "version": task_item["version"]})
    assert blocked.status_code == 409 and "open task" in blocked.text
    assert c.post(f"{base}/{task_item['id']}", json={"status": "Done", "note": "", "version": task_item["version"]}).status_code == 422
    early = c.post(f"{url}/{row['id']}/submit", json={"version": row["version"]})
    assert early.status_code == 409 and "checklist" in early.text
    for name, item in items.items():
        assert c.post(f"{base}/{item['id']}", json={"status": "Not applicable", "note": "Not used on this project", "version": item["version"]}).status_code == 200
    tasks_left = c.post(f"{url}/{row['id']}/submit", json={"version": row["version"]})
    assert tasks_left.status_code == 409 and "open tasks" in tasks_left.text
    with maker() as db:
        db.get(Task, task_id).status = "Completed"
        db.commit()
    no_route = c.post(f"{url}/{row['id']}/submit", json={"version": row["version"]})
    assert no_route.status_code == 422 and "Mandatory reviewer" in no_route.text
    sign_in(c)
    _route(c, pid, "hr.offboarding", pm_id)
    sign_in(c, "hr8@alpha.test")
    with maker() as db:
        members_before = db.query(Membership).filter_by(user_id=worker_login, active=True).count()
    sent = c.post(f"{url}/{row['id']}/submit", json={"version": row["version"]})
    assert sent.status_code == 200, sent.text
    assert c.get(f"/api/projects/{pid}/hr").json()["deployments"][0]["status"] == "Mobilized"

    sign_in(c, "pm8@alpha.test")
    assert _decide(c, c.get(f"/api/projects/{pid}/hr").json()["offboardings"][0]["review"]).status_code == 200
    board = c.get(f"/api/projects/{pid}/hr").json()
    assert board["offboardings"][0]["status"] == "Approved"
    out = board["deployments"][0]
    assert out["status"] == "Demobilized" and out["actual_end"] == iso(today - timedelta(days=1))
    with maker() as db:
        member = db.query(CrewMember).filter_by(personnel_id=worker).one()
        assert member.end_date == today - timedelta(days=1)
        assert db.query(Membership).filter_by(user_id=worker_login, active=True).count() == members_before
        review = db.query(Notification).filter_by(title="Project access review needed", user_id=me["id"]).all()
        assert len(review) == 1 and "W-080" in review[0].body and "Arun" not in review[0].body
