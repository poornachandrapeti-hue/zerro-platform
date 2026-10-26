from .test_engineering import _decide, _file, _ids, _member, _revision, _user, sign_in
from .test_phase2 import complete


def _board(c, pid, **params):
    response = c.get(f"/api/projects/{pid}/engineering-dashboard", params={"size": 100, **params})
    assert response.status_code == 200, response.text
    return response.json()


def _row(board, number):
    return next(row for row in board["register"]["items"] if row["number"] == number)


def _drawing(c, pid, number, discipline, company_id, owner, planned="2020-01-01"):
    response = c.post(
        f"/api/projects/{pid}/drawings",
        json={
            "number": number,
            "title": f"{number} layout",
            "drawing_type": "Layout",
            "discipline_id": discipline,
            "company_id": company_id,
            "responsible_user_id": owner,
            "planned_date": planned,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _through_internal(c, pid, drawing_id, code, body):
    sign_in(c, "engineer@alpha.test")
    revision = _revision(_file(c, pid, drawing_id, code, body), code)
    submitted = c.post(f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision['id']}/submit")
    assert submitted.status_code == 201, submitted.text
    sign_in(c, "head@alpha.test")
    assert _decide(c, _revision(submitted.json(), code)["review"], "approve").status_code == 200
    return revision


def _approve_and_release(c, pid, drawing_id, code, body):
    revision = _through_internal(c, pid, drawing_id, code, body)
    sign_in(c, "client@alpha.test")
    current = _revision(c.get(f"/api/projects/{pid}/drawings/{drawing_id}").json(), code)
    assert _decide(c, current["review"], "approve").status_code == 200
    sign_in(c, "head@alpha.test")
    current = _revision(c.get(f"/api/projects/{pid}/drawings/{drawing_id}").json(), code)
    released = c.post(
        f"/api/projects/{pid}/drawings/{drawing_id}/revisions/{revision['id']}/release",
        json={"version": current["version"]},
    )
    assert released.status_code == 200, released.text
    return revision


def test_import_accepts_excel_style_csv_and_reports_each_row(env):
    c, _maker = env
    sign_in(c)
    _roles, disciplines, _me = _ids(c)
    pid = complete(c, code="IMP-CSV", discipline_ids=[disciplines["Electrical"]])["id"]
    body = (
        "Drawing Number;Drawing Title;Drawing Type;Discipline;Planned Date;Priority\r\n"
        "E-101;Lighting layout;Layout;electrical;15/11/2026;high\r\n"
        "E-102;Earthing plan;Layout;Plumbing;;Normal\r\n"
        ";Missing number;Layout;Electrical;;\r\n"
    ).encode("cp1252")
    preview = c.post(
        f"/api/projects/{pid}/drawing-imports",
        files={"upload": ("Drawings.CSV", body, "text/csv")},
        data={"dry_run": "true"},
    )
    assert preview.status_code == 201, preview.text
    report = preview.json()
    assert report["created"] == ["E-101"]
    assert [row["outcome"] for row in report["rows"]] == ["created", "conflict", "conflict"]
    assert "Plumbing" in report["rows"][1]["reason"]
    assert c.get(f"/api/projects/{pid}/drawings").json()["items"] == []
    done = c.post(f"/api/projects/{pid}/drawing-imports", files={"upload": ("Drawings.CSV", body, "text/csv")})
    assert done.json()["created"] == ["E-101"]
    row = c.get(f"/api/projects/{pid}/drawings").json()["items"][0]
    assert row["planned_date"] == "2026-11-15" and row["priority"] == "High" and row["provenance"] == "import"
    wrong = c.post(
        f"/api/projects/{pid}/drawing-imports",
        files={"upload": ("x.csv", b"Code,Name\nA,B\n", "text/csv")},
    )
    assert wrong.status_code == 422 and "Missing column" in wrong.json()["detail"]


def test_dashboard_counts_unique_drawings_and_match_drill_downs(env, tmp_path):
    from app.config import settings

    settings.file_root = str(tmp_path)
    c, _maker = env
    sign_in(c)
    roles, disciplines, me = _ids(c)
    electrical, mechanical = disciplines["Electrical"], disciplines["Mechanical"]
    pid = complete(c, code="ENG-DASH", discipline_ids=[electrical, mechanical])["id"]
    company_id = me["company_id"]
    engineer = _user(c, "engineer@alpha.test", "Engineer", company_id)
    head = _user(c, "head@alpha.test", "Head", company_id)
    client = _user(c, "client@alpha.test", "Client", company_id)
    mech = _user(c, "mech@alpha.test", "Mechanic", company_id)
    _member(c, pid, engineer, roles["Engineering Engineer"], company_id, [electrical])
    _member(c, pid, head, roles["Discipline Head"], company_id, [electrical])
    _member(c, pid, client, roles["Client/PMC Reviewer"], company_id, [electrical])
    _member(c, pid, mech, roles["Engineering Engineer"], company_id, [mechanical])
    policy = c.post(
        f"/api/projects/{pid}/approval-policies",
        json={
            "record_type": "drawing.revision",
            "discipline_id": electrical,
            "allow_self_approval": False,
            "stages": [
                {"name": "Internal", "rule": "all", "purpose": "internal", "reviewer_ids": [head]},
                {"name": "Client", "rule": "all", "purpose": "client", "reviewer_ids": [client]},
            ],
        },
    )
    assert policy.status_code == 201, policy.text

    sign_in(c, "engineer@alpha.test")
    planned = _drawing(c, pid, "E-PLAN", electrical, company_id, engineer)
    client_pending = _drawing(c, pid, "E-CLIENT", electrical, company_id, engineer, None)
    newer = _drawing(c, pid, "E-REL", electrical, company_id, engineer, None)
    withdrawn = _drawing(c, pid, "E-WD", electrical, company_id, engineer, None)
    sign_in(c, "mech@alpha.test")
    _drawing(c, pid, "M-1", mechanical, company_id, mech, "2999-01-01")

    revision = _through_internal(c, pid, client_pending, "A", b"client-a")
    sign_in(c, "client@alpha.test")
    comment_ids = []
    for index, due in enumerate(["2020-01-01", None, None]):
        made = c.post(
            f"/api/projects/{pid}/drawings/{client_pending}/revisions/{revision['id']}/comments",
            json={"page_ref": str(index + 1), "body": f"Note {index}", "severity": "Minor", "owner_id": engineer, "due_date": due, "stage": "Client"},
        )
        assert made.status_code == 201, made.text
        comment_ids.append(made.json()["id"])

    _approve_and_release(c, pid, newer, "A", b"rel-a")
    sign_in(c, "engineer@alpha.test")
    revision_b = _revision(_file(c, pid, newer, "B", b"rel-b"), "B")
    assert c.post(f"/api/projects/{pid}/drawings/{newer}/revisions/{revision_b['id']}/submit").status_code == 201

    revision_wd = _approve_and_release(c, pid, withdrawn, "A", b"wd-a")
    current = _revision(c.get(f"/api/projects/{pid}/drawings/{withdrawn}").json(), "A")
    pulled = c.post(
        f"/api/projects/{pid}/drawings/{withdrawn}/revisions/{revision_wd['id']}/withdraw",
        json={"version": current["version"], "reason": "Clash found on site"},
    )
    assert pulled.status_code == 200, pulled.text

    sign_in(c)
    board = _board(c, pid)
    totals = board["totals"]
    assert totals["total"] == 5
    assert board["project"]["code"] == "ENG-DASH"

    row = _row(board, "E-PLAN")
    assert row["current_revision"] is None
    assert "to_prepare" in row["metrics"]
    assert row["pending_with"] == ["Engineer"]
    assert [item["action"] for item in row["overdue"]] == ["Preparation"]

    row = _row(board, "E-CLIENT")
    assert row["internal_status"] == "Accepted"
    assert row["client_status"] == "Pending Client Review"
    assert "client_review" in row["metrics"] and "approved" not in row["metrics"]
    assert row["open_comments"] == 3
    assert "Client" in row["pending_with"] and "Engineer (comment)" in row["pending_with"]
    assert any(item["action"].startswith("Comment response") for item in row["overdue"])
    assert totals["open_comments"] == 1
    assert totals["open_comment_items"] == 3

    row = _row(board, "E-REL")
    assert row["current_revision"] == "B" and row["released_revision"] == "A"
    assert row["release_status"] == "Released, newer revision in progress"
    assert {"internal_review", "released"} <= set(row["metrics"])
    assert row["pending_with"] == ["Head"]

    row = _row(board, "E-WD")
    assert row["release_status"] == "Withdrawn"
    assert row["released_revision"] is None
    assert "released" not in row["metrics"]
    assert totals["released"] == 1

    electrical_card = next(item for item in board["disciplines"] if item["id"] == electrical)
    assert electrical_card["total"] == 4
    assert sum(item["count"] for item in board["lifecycle"]) == totals["total"]
    for item in board["disciplines"]:
        for metric in ("total", "to_prepare", "preparing", "internal_review", "client_review", "open_comments", "approved", "released", "overdue"):
            drilled = _board(c, pid, metric=metric, drill_discipline=item["id"])
            assert drilled["register"]["total"] == item[metric], (item["name"], metric)
    for metric, count in totals.items():
        if metric != "open_comment_items":
            assert _board(c, pid, metric=metric)["register"]["total"] == count, metric
    assert _board(c, pid, overdue_only=True)["totals"]["total"] == totals["overdue"]
    assert _board(c, pid, q="e-rel")["totals"]["total"] == 1
    assert _board(c, pid, discipline_id=mechanical)["totals"]["total"] == 1
    paged = _board(c, pid, size=5, page=2, sort="number", direction="desc")
    assert paged["register"]["page"] == 1 and paged["register"]["pages"] == 1
    exported = c.get(f"/api/projects/{pid}/engineering-dashboard/export", params={"metric": "released"})
    assert exported.status_code == 200
    assert exported.text.count("\n") == 2 and "E-REL" in exported.text
    assert any(item["number"] == "E-PLAN" and "Preparation overdue" in item["issue"] for item in board["attention"])

    detail = c.get(f"/api/projects/{pid}/drawings/{newer}").json()
    assert detail["tracking"]["current_revision"] == "B"
    assert detail["tracking"]["released_revision"] == "A"
    assert detail["tracking"]["pending_with"] == ["Head"]
    route = detail["assignments"]["review_route"]
    assert [stage["reviewers"] for stage in route["stages"]] == [["Head"], ["Client"]]
    assert detail["assignments"]["responsible"]["name"] == "Engineer"
    assert "Head" in detail["assignments"]["release_authority"]
    sign_in(c, "mech@alpha.test")
    mech_id = _row(_board(c, pid), "M-1")["id"]
    missing = c.get(f"/api/projects/{pid}/drawings/{mech_id}").json()["assignments"]
    assert missing["review_route"] is None and "Mechanical" in missing["review_route_missing"]
    sign_in(c)
    rev_a = _revision(detail, "A")
    assert rev_a["created_by_name"] == "Engineer" and rev_a["released_by_name"] == "Head"
    assert any(event["kind"] == "released" and event["actor"] == "Head" for event in rev_a["events"])
    detail = c.get(f"/api/projects/{pid}/drawings/{client_pending}").json()
    assert [item["action"] for item in detail["tracking"]["overdue"]] == ["Comment response (1)"]

    sign_in(c, "engineer@alpha.test")
    late = comment_ids[0]
    assert c.post(f"/api/projects/{pid}/comments/{late}/respond", json={"response": "Done", "version": 1}).status_code == 200
    sign_in(c, "client@alpha.test")
    closed = c.post(f"/api/projects/{pid}/comments/{late}/close", json={"evidence": "Checked", "version": 2})
    assert closed.status_code == 200, closed.text
    sign_in(c)
    after = _board(c, pid)
    row = _row(after, "E-CLIENT")
    assert row["open_comments"] == 2
    assert row["overdue"] == []
    assert after["totals"]["overdue"] == totals["overdue"] - 1
    assert all(item["number"] != "E-CLIENT" for item in _board(c, pid, overdue_only=True)["register"]["items"])

    sign_in(c, "mech@alpha.test")
    scoped = _board(c, pid)
    assert [item["name"] for item in scoped["disciplines"]] == ["Mechanical"]
    assert [row["number"] for row in scoped["register"]["items"]] == ["M-1"]
    assert scoped["totals"]["total"] == 1
    assert scoped["attention"] == []
