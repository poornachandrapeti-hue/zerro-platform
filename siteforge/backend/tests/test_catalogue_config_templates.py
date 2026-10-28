import pytest
from fastapi import HTTPException
from app.domains.supply_chain.specification_templates import validate_template_fields, validate_configured_attributes


def test_valid_configuration():
    result = validate_template_fields([
        {"key": "rating_kw", "label": "Power", "type": "number", "required": True},
        {"key": "grade", "label": "Grade", "type": "select", "options": ["A", "B"]},
    ])
    assert result[0]["required"] is True
    assert result[1]["options"] == ["A", "B"]

@pytest.mark.parametrize("fields", [[], [{"key": "Bad Key", "label": "Bad"}],
    [{"key": "a", "label": "A"}, {"key": "a", "label": "Again"}],
    [{"key": "x", "label": "X", "type": "select"}],
    [{"key": "x", "label": "X", "type": "number", "options": ["1"]}],
    [{"key": "x", "label": "X", "required": "yes"}]])
def test_invalid_template(fields):
    with pytest.raises(HTTPException) as exc:
        validate_template_fields(fields)
    assert exc.value.status_code == 422

class FakeQuery:
    def __init__(self, row): self.row = row
    def filter_by(self, **kwargs): return self
    def first(self): return self.row

class FakeDB:
    def __init__(self, row): self.row = row
    def query(self, model): return FakeQuery(self.row)

class FakeRow:
    fields = [{"key": "power", "label": "Power", "type": "number", "required": True},
              {"key": "kind", "label": "Kind", "type": "select", "required": False, "options": ["A", "B"]}]


def test_configured_values():
    assert validate_configured_attributes(FakeDB(FakeRow()), 1, "Mechanical", "Pumps",
        {"power": 15, "kind": "A"}) == {"power": 15, "kind": "A"}

@pytest.mark.parametrize("value", [{}, {"power": "15"}, {"power": True},
                                   {"power": 15, "kind": "C"}, {"power": 15, "unknown": "x"}])
def test_configured_rejects_invalid(value):
    with pytest.raises(HTTPException) as exc:
        validate_configured_attributes(FakeDB(FakeRow()), 1, "Mechanical", "Pumps", value)
    assert exc.value.status_code == 422
