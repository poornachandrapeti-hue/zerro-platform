import pytest
from app.project_identity import load_project_mapping, to_command_center_code, to_siteforge_code


def test_shared_code_without_mapping():
    assert to_command_center_code("STEEL-001", {}) == "STEEL-001"
    assert to_siteforge_code("STEEL-001", {}) == "STEEL-001"


def test_legacy_explicit_code_mapping():
    mapping = load_project_mapping('{"SF-001":"CC-001"}')
    assert to_command_center_code("SF-001", mapping) == "CC-001"
    assert to_siteforge_code("CC-001", mapping) == "SF-001"
    assert to_siteforge_code("NEW-001", mapping) == "NEW-001"

@pytest.mark.parametrize("raw", ['[]', '{"a":1}', '{"a":"b","c":"b"}', '{"":"foo"}', 'not-json'])
def test_reject_bad_or_ambiguous_mapping(raw):
    with pytest.raises(ValueError):
        load_project_mapping(raw)
