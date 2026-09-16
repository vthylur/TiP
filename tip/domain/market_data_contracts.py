"""
TASK-004 — Core data contracts.

Domain facts about historical market data: field availability,
OHLC validation outcome, provenance, adjustment state, and
certification status. No persistence, ingestion, validation
mathematics, corporate-action methodology, or certification
workflow logic belongs here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


class PriceField(Enum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"


class FieldRequirement(Enum):
    FULL_OHLC = "full_ohlc"
    CLOSE_ONLY = "close_only"


class VolumeAvailability(Enum):
    REQUIRED = "required"
    NOT_APPLICABLE = "not_applicable"


_FULL_OHLC_FIELDS: FrozenSet[PriceField] = frozenset(
    {PriceField.OPEN, PriceField.HIGH, PriceField.LOW, PriceField.CLOSE}
)


@dataclass(frozen=True)
class FieldAvailability:
    requirement: FieldRequirement
    present_fields: FrozenSet[PriceField]
    volume_availability: VolumeAvailability

    def __post_init__(self) -> None:
        if PriceField.CLOSE not in self.present_fields:
            raise ValueError("CLOSE must always be present")
        if self.requirement is FieldRequirement.FULL_OHLC:
            missing = _FULL_OHLC_FIELDS - self.present_fields
            if missing:
                raise ValueError(
                    f"FULL_OHLC requires OPEN/HIGH/LOW/CLOSE; missing: "
                    f"{sorted(f.value for f in missing)}"
                )


class ValidationOutcome(Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class AdjustmentState(Enum):
    ADJUSTED = "adjusted"
    UNADJUSTED = "unadjusted"
    UNKNOWN = "unknown"


class CertificationStatus(Enum):
    CERTIFIED = "certified"
    NOT_CERTIFIED = "not_certified"
    PENDING = "pending"


@dataclass(frozen=True)
class Provenance:
    source: str
    source_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-blank string")
        if not isinstance(self.source_version, str) or not self.source_version.strip():
            raise ValueError("source_version must be a non-blank string")
