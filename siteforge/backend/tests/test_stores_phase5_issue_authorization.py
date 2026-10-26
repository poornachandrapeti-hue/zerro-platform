"""Phase 5 demand-chain issue authorization; no database required."""
from decimal import Decimal
from types import SimpleNamespace as Obj
import pytest
from fastapi import HTTPException
from app.domains.stores_inventory.issue_authorization import require_issue_authorization
from app.domains.stores_inventory.router import AtomicLotIssueIn


class FakeResult:
    def __init__(self, row): self.row = row
    def scalar_one_or_none(self): return self.row


class FakeDB:
    def __init__(self, request, line, parent):
        self.results = iter([request, line])
        self.parent = parent
    def execute(self, query): return FakeResult(next(self.results))
    def get(self, model, identifier): return self.parent


def setup():
    project = Obj(id=10)
    request = Obj(id=21, project_id=10, organization_id=1, status='Approved',
                  requirement_line_id=31, item_id=42, base_unit='EA',
                  work_package_id=None, planning_wbs_id=51, requester_company_id=None)
    reservation = Obj(material_request_id=21, requirement_line_id=31,
                      work_package_id=None, planning_wbs_id=51, remaining_quantity=Decimal('4'))
    line = Obj(requirement_id=40, item_id=42, unit='EA', planning_wbs_id=51)
    parent = Obj(project_id=10, organization_id=1, status='Approved', impact_state='Clear')
    return project, request, reservation, line, parent


def authorize(project, request, reservation, line, parent, **overrides):
    return require_issue_authorization(FakeDB(request, line, parent),
        project=project, organization_id=1, reservation=reservation,
        item_id=overrides.get('item_id', 42), unit='EA', amount=overrides.get('amount', Decimal('2')))


def test_valid_approved_request_and_allocation():
    args = setup()
    assert authorize(*args).id == 21


@pytest.mark.parametrize('change', [
    lambda x: setattr(x[1], 'status', 'Rejected'),
    lambda x: setattr(x[1], 'requirement_line_id', None),
    lambda x: setattr(x[2], 'material_request_id', None),
    lambda x: setattr(x[2], 'planning_wbs_id', 999),
    lambda x: setattr(x[2], 'requirement_line_id', 999),
    lambda x: setattr(x[3], 'item_id', 99),
    lambda x: setattr(x[4], 'status', 'Withdrawn'),
    lambda x: setattr(x[4], 'impact_state', 'Review required'),
    lambda x: setattr(x[4], 'project_id', 100),
])
def test_invalid_authorization_fails_closed(change):
    args = setup(); change(args)
    with pytest.raises(HTTPException) as e: authorize(*args)
    assert e.value.status_code == 409


def test_over_issue_fails_closed():
    args = setup()
    with pytest.raises(HTTPException) as e: authorize(*args, amount=Decimal('5'))
    assert e.value.status_code == 409


def test_issue_api_requires_reservation_id():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AtomicLotIssueIn(lot_id=3, quantity='1', posting_number='MI-1', recipient='Crew', reason='Install')


@pytest.mark.parametrize('bad_qty', [Decimal('0'), Decimal('-1'), Decimal('NaN'), Decimal('Infinity')])
def test_nonpositive_or_nonfinite_issue_rejected(bad_qty):
    with pytest.raises(HTTPException) as e: authorize(*setup(), amount=bad_qty)
    assert e.value.status_code == 409


def test_changed_source_wbs_rejected_at_issue():
    args = setup()
    args[3].planning_wbs_id = 999
    with pytest.raises(HTTPException) as e: authorize(*args)
    assert e.value.status_code == 409
