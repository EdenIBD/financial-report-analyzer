import pytest

from src.ingestion.sections import (
    CANONICAL_SECTIONS,
    REQUIRED_CANONICAL_SECTIONS,
    FilingValidationError,
    validate_sections,
)


def test_canonical_sections_10k_and_10q_map_to_same_required_categories():
    assert set(CANONICAL_SECTIONS["10-K"].values()) == REQUIRED_CANONICAL_SECTIONS
    assert set(CANONICAL_SECTIONS["10-Q"].values()) == REQUIRED_CANONICAL_SECTIONS


def test_validate_sections_passes_when_all_required_present():
    sections = {name: "some text" for name in REQUIRED_CANONICAL_SECTIONS}
    validate_sections(sections)  # nu trebuie sa arunce


def test_validate_sections_raises_when_missing():
    sections = {"mdna": "text"}
    with pytest.raises(FilingValidationError):
        validate_sections(sections)
