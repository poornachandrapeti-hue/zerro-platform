from app.domains.supply_chain.catalogue_import_validation import duplicate_codes, MAX_IMPORT_ROWS


def test_case_insensitive_duplicate_codes_flag_all_occurrences():
    duplicates = duplicate_codes(["code", "description"], [
        (" MEC-001 ", "Pump"), ("CIV-001", "Concrete"), ("mec-001", "Pump again")
    ])
    assert duplicates == {2: (2, 4), 4: (2, 4)}


def test_unique_codes_have_no_issues():
    assert duplicate_codes(["code"], [("MEC-001",), ("MEC-002",)]) == {}


def test_blank_rows_ignored():
    assert duplicate_codes(["code"], [(None,), (" X ",), ("",), ("x",)]) == {3: (3, 5), 5: (3, 5)}


def test_missing_code_header_safe():
    assert duplicate_codes(["name"], [("A",)]) == {}


def test_import_limit_positive_and_bounded():
    assert 0 < MAX_IMPORT_ROWS <= 10000
