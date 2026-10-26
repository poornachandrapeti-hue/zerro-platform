"""Project-scoped import mapping and controlled revision import regression tests."""
import json
from .test_engineering import sign_in, _ids
from .test_phase2 import complete


def _request(c, pid, content, **kwargs):
    data = {"dry_run": "true", **kwargs}
    return c.post(f"/api/projects/{pid}/drawing-imports", data=data, files={"upload": ("drawings.csv", content.encode(), "text/csv")})


def test_unknown_location_can_be_revalidated_without_creating_area(env):
    c, _ = env
    sign_in(c)
    _, disciplines, _ = _ids(c)
    pid = complete(c, code="LOC-IMP", discipline_ids=[disciplines["Electrical"]])["id"]
    added = c.post(f"/api/projects/{pid}/areas", json={"code":"U-001","name":"Utilities","area_type":"Unit"})
    assert added.status_code == 201, added.text
    locations = c.get(f"/api/projects/{pid}/areas").json()
    assert locations
    target = next(a for a in locations if a["active"])
    csv = "number,title,discipline,location\nLOC-11,Test,Electrical,Legacy Unknown\n"
    preview = _request(c, pid, csv)
    assert preview.status_code == 201, preview.text
    assert preview.json()["invalid"] == 1
    assert "Map it" in preview.json()["conflicts"][0]["reason"]
    mapping = {"legacy unknown": target["id"]}
    revalidated = _request(c, pid, csv, location_mappings=json.dumps(mapping))
    assert revalidated.status_code == 201, revalidated.text
    assert revalidated.json()["valid"] == 1
    assert len(c.get(f"/api/projects/{pid}/areas").json()) == len(locations)
    saved = c.post(f"/api/projects/{pid}/drawing-imports", data={"location_mappings": json.dumps(mapping)}, files={"upload": ("drawings.csv", csv.encode(), "text/csv")})
    assert saved.status_code == 201, saved.text
    assert saved.json()["created"] == ["LOC-11"]
    drawings = c.get(f"/api/projects/{pid}/drawings").json()["items"]
    assert next(x for x in drawings if x["number"] == "LOC-11")["area_id"] == target["id"]
    bad = _request(c, pid, csv, location_mappings=json.dumps({"legacy unknown": 99999999}))
    assert bad.status_code == 422


def test_unsupported_workflow_fields_rejected_without_persisting(env):
    c, _ = env
    sign_in(c)
    _, disciplines, _ = _ids(c)
    pid = complete(c, code="REV-IMP", discipline_ids=[disciplines["Electrical"]])["id"]
    csv = "Drawing Number,Drawing Title,Discipline,Revision,Approval Status,Document Type,Description\nREV-1,Drawing,Electrical,A,Approved,Drawing,Important\n"
    response = _request(c, pid, csv)
    assert response.status_code == 201, response.text
    assert response.json()["invalid"] == 1
    assert "no approval" in response.json()["rows"][0]["reason"]
    assert not c.get(f"/api/projects/{pid}/drawings").json()["items"]


def test_duplicate_in_same_upload_and_malformed_file(env):
    c, _ = env
    sign_in(c)
    _, disciplines, _ = _ids(c)
    pid = complete(c, code="DUP-IMP", discipline_ids=[disciplines["Electrical"]])["id"]
    csv = "number,title,discipline\nD-11,Drawing,Electrical\nD-11,Drawing,Electrical\n"
    response = _request(c, pid, csv)
    assert response.status_code == 201
    assert response.json()["duplicates"] == 1
    malformed = c.post(f"/api/projects/{pid}/drawing-imports", files={"upload": ("bad.xlsx", b"garbage", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert malformed.status_code == 422


def test_template_contains_project_specific_locations(env):
    from io import BytesIO
    from openpyxl import load_workbook
    c, _ = env
    sign_in(c)
    _, disciplines, _ = _ids(c)
    pid = complete(c, code="TPL-IMP", discipline_ids=[disciplines["Electrical"]])["id"]
    added = c.post(f"/api/projects/{pid}/areas", json={"code":"T-001","name":"Tank Farm","area_type":"Unit"})
    assert added.status_code == 201, added.text
    response = c.get(f"/api/projects/{pid}/drawing-imports/template")
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content))
    locations = {str(a[0]) for a in list(book["Project Locations"].values)[1:]}
    assert locations == {a["code"] for a in c.get(f"/api/projects/{pid}/areas").json() if a["active"]}
