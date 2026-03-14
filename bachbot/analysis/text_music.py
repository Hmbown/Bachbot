"""Text-music relationship analysis for lyric-bearing chorales."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

from pydantic import Field

from bachbot.encodings.event_graph import EventGraph
from bachbot.models.base import BachbotModel, TypedNote
from bachbot.models.refs import PassageRef

UNSTRESSED_TOKENS = {
    "am",
    "an",
    "auf",
    "aus",
    "bei",
    "das",
    "dem",
    "den",
    "der",
    "des",
    "die",
    "du",
    "ein",
    "eine",
    "einer",
    "eines",
    "er",
    "es",
    "ich",
    "im",
    "in",
    "ist",
    "mit",
    "o",
    "sie",
    "und",
    "vom",
    "von",
    "wir",
    "zu",
    "zum",
    "zur",
}

RISING_STEMS = ("aufer", "empor", "ersteh", "himmel", "hoch", "steig", "stei")
FALLING_STEMS = ("fall", "herab", "hinab", "nieder", "sink", "tief")
CHROMATIC_STEMS = ("angst", "kreuz", "leid", "not", "schmerz", "sund", "sünd", "sterb", "tod", "weh")
SIGH_STEMS = ("ach", "o", "seuf", "warum", "weh")

LYRIC_NORMALIZER = re.compile(r"[^0-9A-Za-zÄÖÜäöüß]+")
MATCH_EPSILON = 0.125


class ProsodyEvent(BachbotModel):
    voice_id: str
    lyric: str
    normalized_lyric: str
    measure_number: int
    beat: float
    onset: float
    expected_stress: str
    metric_strength: str
    alignment: str


class ProsodySummary(BachbotModel):
    aligned: int = 0
    misaligned: int = 0
    neutral: int = 0
    alignment_ratio: float = 0.0
    lyric_events: list[ProsodyEvent] = Field(default_factory=list)


class WordPaintingMatch(BachbotModel):
    word: str
    voice_id: str
    figure: str
    passage_ref: PassageRef
    evidence: str
    confidence: float = 0.0


class RhetoricalFigureMatch(BachbotModel):
    figure: str
    voice_id: str
    passage_ref: PassageRef
    evidence: str
    confidence: float = 0.0
    lyrics: list[str] = Field(default_factory=list)


class TextMusicReport(BachbotModel):
    lyric_voices: list[str] = Field(default_factory=list)
    lyric_event_count: int = 0
    prosody: ProsodySummary = Field(default_factory=ProsodySummary)
    word_painting: list[WordPaintingMatch] = Field(default_factory=list)
    rhetorical_figures: list[RhetoricalFigureMatch] = Field(default_factory=list)


def analyze_text_music(graph: EventGraph) -> TextMusicReport:
    lyric_notes = [
        note
        for note in graph.sorted_events()
        if not note.is_rest and note.midi is not None and note.lyric and _normalize_lyric(note.lyric)
    ]
    lyric_voices = sorted({note.voice_id for note in lyric_notes})
    if not lyric_notes:
        return TextMusicReport()

    return TextMusicReport(
        lyric_voices=lyric_voices,
        lyric_event_count=len(lyric_notes),
        prosody=_analyze_prosody(graph),
        word_painting=_detect_word_painting(graph),
        rhetorical_figures=_detect_rhetorical_figures(graph),
    )


def _analyze_prosody(graph: EventGraph) -> ProsodySummary:
    events: list[ProsodyEvent] = []
    aligned = 0
    misaligned = 0
    neutral = 0
    for note in graph.sorted_events():
        if note.is_rest or note.midi is None or not note.lyric:
            continue
        normalized = _normalize_lyric(note.lyric)
        if not normalized:
            continue
        expected = "unstressed" if normalized in UNSTRESSED_TOKENS else "stressed"
        metric_strength = _metric_strength(note.beat, graph.meter)
        if expected == "stressed":
            alignment = "aligned" if metric_strength in {"strong", "secondary"} else "misaligned"
        elif expected == "unstressed":
            alignment = "aligned" if metric_strength == "weak" else "misaligned"
        else:
            alignment = "neutral"

        if alignment == "aligned":
            aligned += 1
        elif alignment == "misaligned":
            misaligned += 1
        else:
            neutral += 1

        events.append(
            ProsodyEvent(
                voice_id=note.voice_id,
                lyric=note.lyric,
                normalized_lyric=normalized,
                measure_number=note.measure_number,
                beat=round(note.beat, 3),
                onset=round(note.offset_quarters, 3),
                expected_stress=expected,
                metric_strength=metric_strength,
                alignment=alignment,
            )
        )

    observed = aligned + misaligned
    return ProsodySummary(
        aligned=aligned,
        misaligned=misaligned,
        neutral=neutral,
        alignment_ratio=round(aligned / observed, 3) if observed else 0.0,
        lyric_events=events,
    )


def _detect_word_painting(graph: EventGraph) -> list[WordPaintingMatch]:
    matches: list[WordPaintingMatch] = []
    for voice_id, notes in graph.notes_by_voice().items():
        pitched = [note for note in notes if not note.is_rest and note.midi is not None]
        for idx, note in enumerate(pitched):
            if not note.lyric:
                continue
            token = _normalize_lyric(note.lyric)
            if not token:
                continue
            forward_window = pitched[idx:min(len(pitched), idx + 4)]
            if _contains_stem(token, RISING_STEMS) and _is_ascending_window(forward_window):
                _append_unique(
                    matches,
                    WordPaintingMatch(
                        word=note.lyric,
                        voice_id=voice_id,
                        figure="anabasis",
                        passage_ref=_passage_ref(forward_window, voice_id),
                        evidence=f"Ascending melodic window over {len(forward_window)} note(s) for '{note.lyric}'.",
                        confidence=0.78,
                    ),
                )
            if _contains_stem(token, FALLING_STEMS) and _is_descending_window(forward_window):
                _append_unique(
                    matches,
                    WordPaintingMatch(
                        word=note.lyric,
                        voice_id=voice_id,
                        figure="catabasis",
                        passage_ref=_passage_ref(forward_window, voice_id),
                        evidence=f"Descending melodic window over {len(forward_window)} note(s) for '{note.lyric}'.",
                        confidence=0.78,
                    ),
                )
            if _contains_stem(token, CHROMATIC_STEMS):
                chromatic_window = _find_chromatic_window(pitched, idx)
                if chromatic_window:
                    _append_unique(
                        matches,
                        WordPaintingMatch(
                            word=note.lyric,
                            voice_id=voice_id,
                            figure="passus_duriusculus",
                            passage_ref=_passage_ref(chromatic_window, voice_id),
                            evidence=f"Chromatic semitone chain around '{note.lyric}'.",
                            confidence=0.82,
                        ),
                    )
            if _contains_stem(token, SIGH_STEMS) and _has_preceding_silence(notes, note):
                _append_unique(
                    matches,
                    WordPaintingMatch(
                        word=note.lyric,
                        voice_id=voice_id,
                        figure="suspiratio",
                        passage_ref=_passage_ref([note], voice_id),
                        evidence=f"Rest or silence precedes '{note.lyric}'.",
                        confidence=0.7,
                    ),
                )
    return matches


def _detect_rhetorical_figures(graph: EventGraph) -> list[RhetoricalFigureMatch]:
    matches: list[RhetoricalFigureMatch] = []
    for voice_id, notes in graph.notes_by_voice().items():
        pitched = [note for note in notes if not note.is_rest and note.midi is not None]
        for start in range(max(len(pitched) - 2, 0)):
            window = pitched[start:start + 4]
            if len(window) < 3:
                continue
            lyrics = [note.lyric for note in window if note.lyric]
            if _is_ascending_window(window):
                _append_unique(
                    matches,
                    RhetoricalFigureMatch(
                        figure="anabasis",
                        voice_id=voice_id,
                        passage_ref=_passage_ref(window, voice_id),
                        evidence=f"Ascending window from {window[0].pitch_name} to {window[-1].pitch_name}.",
                        confidence=0.74,
                        lyrics=lyrics,
                    ),
                )
            if _is_descending_window(window):
                _append_unique(
                    matches,
                    RhetoricalFigureMatch(
                        figure="catabasis",
                        voice_id=voice_id,
                        passage_ref=_passage_ref(window, voice_id),
                        evidence=f"Descending window from {window[0].pitch_name} to {window[-1].pitch_name}.",
                        confidence=0.74,
                        lyrics=lyrics,
                    ),
                )
            chromatic_window = _find_chromatic_window(pitched, start)
            if chromatic_window:
                _append_unique(
                    matches,
                    RhetoricalFigureMatch(
                        figure="passus_duriusculus",
                        voice_id=voice_id,
                        passage_ref=_passage_ref(chromatic_window, voice_id),
                        evidence="Three consecutive semitone motions in one direction.",
                        confidence=0.84,
                        lyrics=[note.lyric for note in chromatic_window if note.lyric],
                    ),
                )
        for note in pitched:
            if _has_preceding_silence(notes, note):
                _append_unique(
                    matches,
                    RhetoricalFigureMatch(
                        figure="suspiratio",
                        voice_id=voice_id,
                        passage_ref=_passage_ref([note], voice_id),
                        evidence=f"Rest or measurable silence before {note.pitch_name}.",
                        confidence=0.68,
                        lyrics=[note.lyric] if note.lyric else [],
                    ),
                )
    return matches


def _parse_meter(meter: str | None) -> tuple[int, int]:
    if not meter:
        return 4, 4
    numerator, _, denominator = meter.partition("/")
    try:
        num = int(numerator)
        denom = int(denominator)
    except ValueError:
        return 4, 4
    if num <= 0 or denom <= 0:
        return 4, 4
    return num, denom


def _metric_strength(beat: float, meter: str | None) -> str:
    num, denom = _parse_meter(meter)
    beats_per_measure = num * (4.0 / denom)
    if math.isclose(beat, 1.0, abs_tol=MATCH_EPSILON):
        return "strong"
    midpoint = 1.0 + (beats_per_measure / 2.0)
    if beats_per_measure >= 4.0 and math.isclose(beat, midpoint, abs_tol=MATCH_EPSILON):
        return "secondary"
    return "weak"


def _normalize_lyric(lyric: str) -> str:
    return LYRIC_NORMALIZER.sub("", lyric).casefold()


def _contains_stem(token: str, stems: Iterable[str]) -> bool:
    return any(stem in token for stem in stems)


def _intervals(notes: list[TypedNote]) -> list[int]:
    return [second.midi - first.midi for first, second in zip(notes, notes[1:]) if first.midi is not None and second.midi is not None]


def _is_ascending_window(notes: list[TypedNote]) -> bool:
    intervals = _intervals(notes)
    if len(intervals) < 2:
        return False
    return all(step > 0 for step in intervals) and sum(intervals) >= 3


def _is_descending_window(notes: list[TypedNote]) -> bool:
    intervals = _intervals(notes)
    if len(intervals) < 2:
        return False
    return all(step < 0 for step in intervals) and sum(intervals) <= -3


def _find_chromatic_window(notes: list[TypedNote], start: int) -> list[TypedNote]:
    window = notes[start:start + 4]
    intervals = _intervals(window)
    if len(intervals) < 3:
        return []
    if not all(abs(step) == 1 for step in intervals[:3]):
        return []
    if len({1 if step > 0 else -1 for step in intervals[:3]}) != 1:
        return []
    return window[:4]


def _has_preceding_silence(voice_notes: list[TypedNote], note: TypedNote) -> bool:
    try:
        index = voice_notes.index(note)
    except ValueError:
        return False
    if index == 0:
        return False
    previous = voice_notes[index - 1]
    previous_end = previous.offset_quarters + previous.duration_quarters
    return previous.is_rest or note.offset_quarters - previous_end > 0.24


def _passage_ref(notes: list[TypedNote], voice_id: str) -> PassageRef:
    return PassageRef(
        measure_start=min(note.measure_number for note in notes),
        measure_end=max(note.measure_number for note in notes),
        voice_ids=[voice_id],
    )


def _append_unique(
    target: list[WordPaintingMatch] | list[RhetoricalFigureMatch],
    candidate: WordPaintingMatch | RhetoricalFigureMatch,
) -> None:
    key = (
        candidate.figure,
        candidate.voice_id,
        candidate.passage_ref.measure_start,
        candidate.passage_ref.measure_end,
        tuple(candidate.passage_ref.voice_ids),
    )
    existing_keys = {
        (
            item.figure,
            item.voice_id,
            item.passage_ref.measure_start,
            item.passage_ref.measure_end,
            tuple(item.passage_ref.voice_ids),
        )
        for item in target
    }
    if key not in existing_keys:
        target.append(candidate)
