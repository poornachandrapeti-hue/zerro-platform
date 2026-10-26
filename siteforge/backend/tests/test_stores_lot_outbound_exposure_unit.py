from app.domains.stores_inventory.lot_outbound_exposure import exposure_flags


def test_missing_qa_and_unallocated_issue_is_blocked():
    flags = exposure_flags(False, [], 2, 0, 0, 3)
    assert 'LOT_QA_ATTRIBUTION_MISSING' in flags
    assert 'UNATTRIBUTED_OUTBOUND_MOVEMENTS' in flags


def test_outdated_decision_is_reported():
    flags = exposure_flags(True, [1], 2, '4', '4', 0)
    assert 'LOT_QA_DECISION_STALE' in flags


def test_quantity_mismatch_is_reported():
    flags = exposure_flags(True, [2], 2, '3', '2', 0)
    assert 'QA_ACCEPTED_VS_RECEIPT_MAPPING_MISMATCH' in flags


def test_diagnostic_without_mismatch_has_no_flags():
    assert exposure_flags(True, [2], 2, '3', '3', 0) == []
