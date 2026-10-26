"""Unified project identity: same-code by default; optional explicit legacy mapping.

Identity resolution is deterministic and rejects ambiguous many-to-one mappings.
This module does not create projects or copy authoritative SiteForge records.
"""
import json


def load_project_mapping(raw: str) -> dict[str, str]:
    mapping = json.loads(raw)
    if not isinstance(mapping, dict) or not all(
        isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
        for k, v in mapping.items()
    ):
        raise ValueError("Project mapping must be a nonempty-string dictionary")
    if len(mapping.values()) != len(set(mapping.values())):
        raise ValueError("Ambiguous many-to-one project mapping")
    return mapping


def to_command_center_code(source_code: str, mapping: dict[str, str]) -> str:
    # An explicit mapping overrides the shared canonical code for legacy records.
    return mapping.get(source_code, source_code)


def to_siteforge_code(command_center_code: str, mapping: dict[str, str]) -> str:
    reverse = {value: key for key, value in mapping.items()}
    return reverse.get(command_center_code, command_center_code)
