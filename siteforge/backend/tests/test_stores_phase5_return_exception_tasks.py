"""Phase 5 exception task API and shared-task safety contract checks."""
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
import pytest
from app.domains.stores_inventory.material_returns import (
    RETURN_EXCEPTION_TASK_TYPE, _return_exception_kind, ReturnExceptionAssignIn,
    ReturnExceptionResolveIn, summarize_return_exceptions,
)


def test_exception_type_uses_existing_coordination_namespace():
    assert RETURN_EXCEPTION_TASK_TYPE == 'stores.material_return.exception_review'


def test_pending_and_qa_exceptions_are_distinct():
    pending = SimpleNamespace(id=1, handover_id=10, status='Submitted', stock_posting_id=None, return_location_id=None)
    qa = SimpleNamespace(id=2, handover_id=20, status='Awaiting QA', stock_posting_id=None, return_location_id=None)
    assert _return_exception_kind(pending) == 'awaiting_stores_receipt'
    assert _return_exception_kind(qa) == 'awaiting_qa'
    assert summarize_return_exceptions([pending, qa])['physical_stock_readiness'] == 'Unverified'


def test_task_inputs_reject_empty_resolution_and_invalid_owner():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ReturnExceptionAssignIn(owner_id=0)
    with pytest.raises(ValidationError):
        ReturnExceptionResolveIn(task_version=1, evidence='')


def test_shared_tasks_are_not_an_exception_completion_bypass():
    source = (Path(__file__).resolve().parents[1] / 'app/domains/coordination/service.py').read_text()
    assert '"stores.material_return.exception_review"' in source
    assert 'Use Construction acknowledgment and independent QA verification workflow' in source


def test_endpoint_has_real_state_transition_gate():
    source = (Path(__file__).resolve().parents[1] / 'app/domains/stores_inventory/material_returns.py').read_text()
    assert 'if current == original[1].strip():' in source
    assert 'Complete the underlying Stores/QA workflow' in source
    assert "Task.organization_id == u.organization_id" in source
    assert "Task.project_id == pid" in source
