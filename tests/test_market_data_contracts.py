"""
TASK-004 — Core data contracts.

Proves the domain contracts for quality (validation outcome), field
availability, provenance, and adjustment state behave per the locked
vocabulary: closed enums, no silent favorable defaults, and no value
substitution between fields.
"""

import pytest

from tip.domain.market_data_contracts import (
    AdjustmentState,
    CertificationStatus,
    FieldAvailability,
    FieldRequirement,
    PriceField,
    Provenance,
    ValidationOutcome,
    VolumeAvailability,
)


# ---------------------------------------------------------------------------
# Locked vocabulary — exact membership, no expansion
# ---------------------------------------------------------------------------


def test_validation_outcome_has_exactly_locked_members() -> None:
    assert {m.name for m in ValidationOutcome} == {"VALID", "INVALID", "UNKNOWN"}


def test_adjustment_state_has_exactly_locked_members() -> None:
    assert {m.name for m in AdjustmentState} == {"ADJUSTED", "UNADJUSTED", "UNKNOWN"}


def test_certification_status_has_exactly_locked_members() -> None:
    assert {m.name for m in CertificationStatus} == {
        "CERTIFIED",
        "NOT_CERTIFIED",
        "PENDING",
    }


def test_price_field_has_exactly_locked_members() -> None:
    assert {m.name for m in PriceField} == {"OPEN", "HIGH", "LOW", "CLOSE"}


def test_field_requirement_has_exactly_locked_members() -> None:
    assert {m.name for m in FieldRequirement} == {"FULL_OHLC", "CLOSE_ONLY"}


def test_volume_availability_has_exactly_locked_members() -> None:
    assert {m.name for m in VolumeAvailability} == {"REQUIRED", "NOT_APPLICABLE"}


@pytest.mark.parametrize(
    "enum_cls", [ValidationOutcome, AdjustmentState, CertificationStatus]
)
def test_locked_enums_reject_unrecognized_values(enum_cls) -> None:
    with pytest.raises(ValueError):
        enum_cls("not_a_real_state")


# ---------------------------------------------------------------------------
# Quality state is not a boolean and validation/adjustment/certification
# are distinct concepts, not interchangeable.
# ---------------------------------------------------------------------------


def test_validation_adjustment_certification_are_distinct_enum_types() -> None:
    assert ValidationOutcome is not AdjustmentState
    assert ValidationOutcome is not CertificationStatus
    assert AdjustmentState is not CertificationStatus
    assert ValidationOutcome.VALID != AdjustmentState.ADJUSTED
    assert ValidationOutcome.VALID != CertificationStatus.CERTIFIED
    assert AdjustmentState.ADJUSTED != CertificationStatus.CERTIFIED


# ---------------------------------------------------------------------------
# Fail-closed: UNKNOWN/PENDING must never equal a favorable state.
# ---------------------------------------------------------------------------


def test_unknown_validity_is_not_valid() -> None:
    assert ValidationOutcome.UNKNOWN != ValidationOutcome.VALID


def test_unknown_adjustment_is_not_adjusted() -> None:
    assert AdjustmentState.UNKNOWN != AdjustmentState.ADJUSTED


def test_pending_certification_is_not_certified() -> None:
    assert CertificationStatus.PENDING != CertificationStatus.CERTIFIED


def test_not_certified_is_not_certified() -> None:
    assert CertificationStatus.NOT_CERTIFIED != CertificationStatus.CERTIFIED


# ---------------------------------------------------------------------------
# Field availability: FULL_OHLC completeness, no silent CLOSE_ONLY downgrade,
# no substitution of CLOSE into missing O/H/L.
# ---------------------------------------------------------------------------


def test_full_ohlc_succeeds_when_all_four_fields_present() -> None:
    fa = FieldAvailability(
        requirement=FieldRequirement.FULL_OHLC,
        present_fields=frozenset(
            {PriceField.OPEN, PriceField.HIGH, PriceField.LOW, PriceField.CLOSE}
        ),
        volume_availability=VolumeAvailability.REQUIRED,
    )
    assert fa.requirement is FieldRequirement.FULL_OHLC


@pytest.mark.parametrize(
    "present_fields",
    [
        frozenset({PriceField.HIGH, PriceField.LOW, PriceField.CLOSE}),  # missing OPEN
        frozenset({PriceField.OPEN, PriceField.LOW, PriceField.CLOSE}),  # missing HIGH
        frozenset({PriceField.OPEN, PriceField.HIGH, PriceField.CLOSE}),  # missing LOW
        frozenset({PriceField.OPEN, PriceField.HIGH, PriceField.LOW}),  # missing CLOSE
        frozenset({PriceField.CLOSE}),  # only close present
        frozenset(),  # nothing present
    ],
)
def test_full_ohlc_rejects_incomplete_fields_instead_of_becoming_close_only(
    present_fields,
) -> None:
    with pytest.raises(ValueError):
        FieldAvailability(
            requirement=FieldRequirement.FULL_OHLC,
            present_fields=present_fields,
            volume_availability=VolumeAvailability.REQUIRED,
        )


def test_close_only_requires_close_present() -> None:
    with pytest.raises(ValueError):
        FieldAvailability(
            requirement=FieldRequirement.CLOSE_ONLY,
            present_fields=frozenset(),
            volume_availability=VolumeAvailability.NOT_APPLICABLE,
        )


def test_close_only_succeeds_with_only_close_present_and_does_not_fabricate_ohl() -> None:
    fa = FieldAvailability(
        requirement=FieldRequirement.CLOSE_ONLY,
        present_fields=frozenset({PriceField.CLOSE}),
        volume_availability=VolumeAvailability.NOT_APPLICABLE,
    )
    assert fa.present_fields == frozenset({PriceField.CLOSE})
    assert PriceField.OPEN not in fa.present_fields
    assert PriceField.HIGH not in fa.present_fields
    assert PriceField.LOW not in fa.present_fields


def test_volume_not_applicable_is_representable_without_fabricating_volume() -> None:
    fa = FieldAvailability(
        requirement=FieldRequirement.FULL_OHLC,
        present_fields=frozenset(
            {PriceField.OPEN, PriceField.HIGH, PriceField.LOW, PriceField.CLOSE}
        ),
        volume_availability=VolumeAvailability.NOT_APPLICABLE,
    )
    assert fa.volume_availability is VolumeAvailability.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Provenance: required, non-null, non-blank source and source_version.
# ---------------------------------------------------------------------------


def test_provenance_succeeds_with_valid_source_and_version() -> None:
    p = Provenance(source="vendor_x", source_version="2.3.1")
    assert p.source == "vendor_x"
    assert p.source_version == "2.3.1"


def test_provenance_rejects_blank_source() -> None:
    with pytest.raises(ValueError):
        Provenance(source="", source_version="1.0")


def test_provenance_rejects_whitespace_only_source() -> None:
    with pytest.raises(ValueError):
        Provenance(source="   ", source_version="1.0")


def test_provenance_rejects_none_source() -> None:
    with pytest.raises((ValueError, TypeError)):
        Provenance(source=None, source_version="1.0")


def test_provenance_rejects_blank_source_version() -> None:
    with pytest.raises(ValueError):
        Provenance(source="vendor_x", source_version="")


def test_provenance_rejects_whitespace_only_source_version() -> None:
    with pytest.raises(ValueError):
        Provenance(source="vendor_x", source_version="   ")


def test_provenance_rejects_none_source_version() -> None:
    with pytest.raises((ValueError, TypeError)):
        Provenance(source="vendor_x", source_version=None)
