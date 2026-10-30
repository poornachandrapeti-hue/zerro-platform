from decimal import Decimal
from types import SimpleNamespace
from app.domains.engineering_documents import takeoff


class Line(SimpleNamespace):
    pass


def test_r0_r1_quantity_delta_for_matched_catalogue_items():
    # item_id omitted so the pure diff path does not require a DB session.
    r0 = [
        Line(item_id=None, description="Reinforcement Steel Fe500", quantity=Decimal("1000"), unit="kg", specification="Fe500"),
        Line(item_id=None, description="Ready Mix Concrete M30", quantity=Decimal("20"), unit="m3", specification="M30"),
    ]
    r1 = [
        Line(item_id=None, description="Reinforcement Steel Fe500", quantity=Decimal("1250"), unit="kg", specification="Fe500"),
        Line(item_id=None, description="Ready Mix Concrete M30", quantity=Decimal("24"), unit="m3", specification="M30"),
    ]
    old_row = SimpleNamespace()
    new_row = SimpleNamespace()

    def fake_active(_db, row):
        return r0 if row is old_row else r1

    original = takeoff._active_lines
    takeoff._active_lines = fake_active
    try:
        changes = takeoff.diff(None, old_row, new_row)
    finally:
        takeoff._active_lines = original

    assert len(changes["quantity_changed"]) == 2
    by_label = {row["label"]: row for row in changes["quantity_changed"]}
    assert by_label["Reinforcement Steel Fe500"]["old"].startswith("1000")
    assert by_label["Reinforcement Steel Fe500"]["new"].startswith("1250")
    assert by_label["Ready Mix Concrete M30"]["old"].startswith("20")
    assert by_label["Ready Mix Concrete M30"]["new"].startswith("24")
    assert changes["added"] == []
    assert changes["removed"] == []
