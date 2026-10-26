from types import SimpleNamespace as Obj
from app.domains.progress_monitoring.source_evidence import engineering_evidence, procurement_evidence, scoped


def test_engineering_deduplicates_multiple_revisions():
    drawings = [Obj(id=1,number='D-01',company_id=2,discipline_id=3,record_status='Active',preparation='Completed')]
    revisions = [Obj(drawing_id=1,release_state='Released',released_at='2026-01-01'),
                 Obj(drawing_id=1,release_state='Released',released_at='2026-02-01')]
    result = engineering_evidence(drawings, revisions)
    assert result['released_drawings'] == 1
    assert result['earned_percent'] is None


def test_not_released_without_release_evidence():
    d = Obj(id=1,number='D-1',company_id=2,discipline_id=3,record_status='Active',preparation='Prepared')
    result = engineering_evidence([d], [Obj(drawing_id=1,release_state='Released',released_at=None)])
    assert result['released_drawings'] == 0


def test_receipt_counts_do_not_infer_acceptance_or_progress():
    orders = [Obj(id=1,number='PO1',status='Issued',company_id=1,discipline_id=3)]
    receipts = [Obj(purchase_order_id=1,status='Posted'),Obj(purchase_order_id=1,status='Cancelled')]
    result = procurement_evidence(orders,receipts)
    assert result['orders_with_posted_receipts'] == 1
    assert result['earned_percent'] is None


def test_scoped_company_and_discipline():
    scope = {'all':False,'pairs':[(5,{3})]}
    assert scoped(Obj(company_id=5,discipline_id=3),scope)
    assert not scoped(Obj(company_id=6,discipline_id=3),scope)
    assert not scoped(Obj(company_id=5,discipline_id=4),scope)
