"""Contract checks: Stores issue requests reference existing approved demand."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / 'app/domains/stores_inventory/material_requests.py').read_text()
MODEL = (ROOT / 'app/domains/stores_inventory/models.py').read_text()
FRONT = (ROOT.parent / 'frontend/src/stores.tsx').read_text()
MIGRATION = (ROOT / 'migrations/versions/stores_phase4_shared_requirement_link.py').read_text()

def test_approved_requirement_is_mandatory():
    assert 'requirement_line_id: int = Field(gt=0)' in API
    assert "parent.status != 'Approved'" in API
    assert "parent.impact_state == 'Review required'" in API

def test_quantity_bound_to_single_requirement_line():
    assert 'with_for_update()' in API
    assert 'data.quantity > remaining' in API
    assert 'line.item_id != data.item_id' in API
    assert 'line.unit != chosen_item.base_unit' in API

def test_model_migration_and_ui_link():
    assert 'requirement_line_id: Mapped[int | None]' in MODEL
    assert 'down_revision = \'stores_phase4_material_requests\'' in MIGRATION
    assert 'requirement_line_id:Number(requestRequirementLine)' in FRONT
    assert 'Approved Procurement requirement line ID' in FRONT
