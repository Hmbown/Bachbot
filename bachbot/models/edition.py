from __future__ import annotations

from collections import Counter

from pydantic import Field

from bachbot.models.base import BachbotModel, StrEnum
from bachbot.models.refs import PassageRef


class Edition(BachbotModel):
    edition_id: str
    title: str
    editor: str | None = None
    publisher: str | None = None
    year: int | None = None
    edition_type: str | None = None
    source_basis: list[str] = Field(default_factory=list)
    critical_report_ref: str | None = None
    editorial_interventions: list[str] = Field(default_factory=list)
    license: str | None = None


class VariantType(StrEnum):
    PITCH = "pitch"
    RHYTHM = "rhythm"
    ACCIDENTAL = "accidental"
    TEXT = "text"
    TIE = "tie"
    ADDED_NOTE = "added_note"
    REMOVED_NOTE = "removed_note"


class EditionNoteAddress(BachbotModel):
    measure_number: int
    onset: float
    beat: float
    voice_id: str
    source_ref: str | None = None


class EditionNoteSnapshot(BachbotModel):
    address: EditionNoteAddress
    pitch: str | None = None
    midi: int | None = None
    duration_quarters: float
    accidental: str | None = None
    lyric: str | None = None
    tie_start: bool = False
    tie_stop: bool = False
    is_rest: bool = False


class EditionVariant(BachbotModel):
    variant_type: VariantType
    passage_ref: PassageRef
    address: EditionNoteAddress
    left_note: EditionNoteSnapshot | None = None
    right_note: EditionNoteSnapshot | None = None
    detail: str | None = None


class VariantSummary(BachbotModel):
    variant_count: int = 0
    unchanged_count: int = 0
    measure_count: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_voice: dict[str, int] = Field(default_factory=dict)
    by_measure: dict[int, int] = Field(default_factory=dict)

    @classmethod
    def from_variants(
        cls,
        variants: list[EditionVariant],
        *,
        unchanged_count: int,
        measure_count: int,
    ) -> "VariantSummary":
        counts = Counter(item.variant_type.value for item in variants)
        voice_counts = Counter(item.address.voice_id for item in variants)
        measure_counts = Counter(item.address.measure_number for item in variants)
        return cls(
            variant_count=len(variants),
            unchanged_count=unchanged_count,
            measure_count=measure_count,
            by_type={key: counts[key] for key in sorted(counts)},
            by_voice={key: voice_counts[key] for key in sorted(voice_counts)},
            by_measure={key: measure_counts[key] for key in sorted(measure_counts)},
        )


class VariantReport(BachbotModel):
    left_label: str
    right_label: str
    left_work_id: str
    right_work_id: str
    measure_span_comparison: dict[int, tuple[int, int]] = Field(default_factory=dict)
    voice_span_comparison: dict[str, tuple[int, int]] = Field(default_factory=dict)
    variants: list[EditionVariant] = Field(default_factory=list)
    summary: VariantSummary = Field(default_factory=VariantSummary)
