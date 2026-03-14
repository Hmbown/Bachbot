"""Unified fugue analysis pipeline.

Provides typed models for fugue structures (subject, answer, stretto,
episodes) and an ``analyze_fugue()`` entry point that orchestrates all
analysis stages.
"""

from __future__ import annotations

from pydantic import Field

from bachbot.encodings.event_graph import EventGraph
from bachbot.features.intervals import melodic_intervals
from bachbot.models.base import BachbotModel
from bachbot.models.refs import PassageRef


# ── Domain models ──


class FugueSubject(BachbotModel):
    """A detected subject statement in a fugal texture."""

    voice_id: str
    start_onset: float
    end_onset: float
    midi_sequence: list[int] = Field(default_factory=list)
    interval_sequence: list[int] = Field(default_factory=list)
    passage_ref: PassageRef


class FugueAnswer(BachbotModel):
    """A detected answer entry following the subject."""

    voice_id: str
    start_onset: float
    answer_type: str  # "real" or "tonal"
    transposition_interval: int  # semitones
    passage_ref: PassageRef


class StrettoEntry(BachbotModel):
    """A stretto occurrence where a new entry begins before the previous
    entry finishes."""

    voice_id: str
    start_onset: float
    overlap_beats: float
    distance_from_previous: float


class FugueEpisode(BachbotModel):
    """A passage between subject entries — typically sequential."""

    start_onset: float
    end_onset: float
    measure_start: int
    measure_end: int
    sequential: bool = False


class FugueAnalysisReport(BachbotModel):
    """Complete fugue analysis output."""

    work_id: str
    voice_count: int
    subject: FugueSubject | None = None
    answer: FugueAnswer | None = None
    subject_entries: list[FugueSubject] = Field(default_factory=list)
    stretto_entries: list[StrettoEntry] = Field(default_factory=list)
    episodes: list[FugueEpisode] = Field(default_factory=list)
    exposition_end_onset: float | None = None


# ── Analysis functions ──


def identify_subject(
    graph: EventGraph,
    *,
    voice_hint: str | None = None,
) -> FugueSubject | None:
    """Identify the fugue subject as the first melodic statement.

    The subject is the notes in the first voice to enter, from its first
    note until the second voice enters (or all its notes if only one
    voice is present).
    """
    voice_ids = graph.ordered_voice_ids()
    if not voice_ids:
        return None

    # Determine voice entry order by first-note onset.
    entry_onsets: list[tuple[float, str]] = []
    for vid in voice_ids:
        events = graph.voice_events(vid)
        if events:
            entry_onsets.append((events[0].offset_quarters, vid))
    entry_onsets.sort()

    if not entry_onsets:
        return None

    # Select the first voice, or use the hint.
    if voice_hint and any(vid == voice_hint for _, vid in entry_onsets):
        first_voice = voice_hint
    else:
        first_voice = entry_onsets[0][1]

    first_events = graph.voice_events(first_voice)
    if not first_events:
        return None

    # Subject extends until the next voice to enter after the chosen voice.
    first_voice_onset = first_events[0].offset_quarters
    later_entries = [
        onset for onset, vid in entry_onsets
        if vid != first_voice and onset > first_voice_onset
    ]
    if later_entries:
        cutoff = min(later_entries)
        subject_notes = [n for n in first_events if n.offset_quarters < cutoff]
    elif len(entry_onsets) >= 2:
        # Other voices entered earlier; use the next entry after ours.
        other_onsets = [onset for onset, vid in entry_onsets if vid != first_voice]
        if other_onsets:
            # All other voices entered before this one; subject is all notes
            # until the first event from any other voice that starts after
            # the chosen voice's first note, or all notes if none.
            subject_notes = first_events
        else:
            subject_notes = first_events
    else:
        subject_notes = first_events

    if not subject_notes:
        return None

    midi_seq = [n.midi for n in subject_notes if n.midi is not None]
    interval_seq = [b - a for a, b in zip(midi_seq, midi_seq[1:])]
    last = subject_notes[-1]
    end_onset = last.offset_quarters + last.duration_quarters

    return FugueSubject(
        voice_id=first_voice,
        start_onset=subject_notes[0].offset_quarters,
        end_onset=end_onset,
        midi_sequence=midi_seq,
        interval_sequence=interval_seq,
        passage_ref=PassageRef(
            measure_start=subject_notes[0].measure_number,
            measure_end=last.measure_number,
            voice_ids=[first_voice],
        ),
    )


def identify_answer(
    graph: EventGraph,
    subject: FugueSubject,
) -> FugueAnswer | None:
    """Find the answer entry in the second voice after the subject.

    Compares the interval sequence to classify as *real* (exact
    transposition) or *tonal* (with degree mutations).
    """
    voice_ids = graph.ordered_voice_ids()
    entry_onsets: list[tuple[float, str]] = []
    for vid in voice_ids:
        events = graph.voice_events(vid)
        if events:
            entry_onsets.append((events[0].offset_quarters, vid))
    entry_onsets.sort()

    if len(entry_onsets) < 2:
        return None

    # The answer voice is the second to enter.
    answer_voice = entry_onsets[1][1]
    answer_events = graph.voice_events(answer_voice)
    if not answer_events:
        return None

    # Take as many notes as the subject has.
    n_subject = len(subject.midi_sequence)
    answer_notes = answer_events[:n_subject]
    answer_midi = [n.midi for n in answer_notes if n.midi is not None]

    if len(answer_midi) < 2 or len(subject.midi_sequence) < 2:
        return None

    answer_intervals = [b - a for a, b in zip(answer_midi, answer_midi[1:])]
    subj_intervals = subject.interval_sequence

    # Determine transposition.
    transposition = answer_midi[0] - subject.midi_sequence[0]

    # Classify: real if intervals match exactly, tonal otherwise.
    if answer_intervals == subj_intervals:
        answer_type = "real"
    else:
        answer_type = "tonal"

    last_note = answer_notes[-1]
    return FugueAnswer(
        voice_id=answer_voice,
        start_onset=answer_notes[0].offset_quarters,
        answer_type=answer_type,
        transposition_interval=transposition,
        passage_ref=PassageRef(
            measure_start=answer_notes[0].measure_number,
            measure_end=last_note.measure_number,
            voice_ids=[answer_voice],
        ),
    )


def find_subject_entries(
    graph: EventGraph,
    subject: FugueSubject,
    *,
    tolerance: int = 0,
) -> list[FugueSubject]:
    """Search all voices for occurrences of the subject's interval pattern.

    Allows transposition (same intervals at different pitch levels).
    *tolerance* allows fuzzy matching (max abs deviation per interval).
    """
    target = subject.interval_sequence
    if not target:
        return []

    entries: list[FugueSubject] = []
    for vid in graph.ordered_voice_ids():
        events = [n for n in graph.voice_events(vid) if n.midi is not None]
        if len(events) < len(target) + 1:
            continue
        intervals = melodic_intervals(graph, vid)
        # Sliding window search.
        for i in range(len(intervals) - len(target) + 1):
            window = intervals[i : i + len(target)]
            if tolerance == 0:
                match = window == target
            else:
                match = all(abs(w - t) <= tolerance for w, t in zip(window, target))
            if match:
                note_window = events[i : i + len(target) + 1]
                midi_seq = [n.midi for n in note_window if n.midi is not None]
                last = note_window[-1]
                entries.append(
                    FugueSubject(
                        voice_id=vid,
                        start_onset=note_window[0].offset_quarters,
                        end_onset=last.offset_quarters + last.duration_quarters,
                        midi_sequence=midi_seq,
                        interval_sequence=list(window),
                        passage_ref=PassageRef(
                            measure_start=note_window[0].measure_number,
                            measure_end=last.measure_number,
                            voice_ids=[vid],
                        ),
                    )
                )

    # Deduplicate overlapping entries in the same voice.
    entries.sort(key=lambda e: (e.voice_id, e.start_onset))
    deduped: list[FugueSubject] = []
    for entry in entries:
        if deduped and deduped[-1].voice_id == entry.voice_id and entry.start_onset < deduped[-1].end_onset:
            continue
        deduped.append(entry)

    return deduped


def find_stretto_entries(entries: list[FugueSubject]) -> list[StrettoEntry]:
    """Detect stretto: a new subject entry begins before the previous ends."""
    if len(entries) < 2:
        return []

    sorted_entries = sorted(entries, key=lambda e: e.start_onset)
    stretto: list[StrettoEntry] = []

    for prev, curr in zip(sorted_entries, sorted_entries[1:]):
        if curr.start_onset < prev.end_onset:
            overlap = min(prev.end_onset, curr.end_onset) - curr.start_onset
            stretto.append(
                StrettoEntry(
                    voice_id=curr.voice_id,
                    start_onset=curr.start_onset,
                    overlap_beats=round(overlap, 3),
                    distance_from_previous=round(curr.start_onset - prev.start_onset, 3),
                )
            )

    return stretto


def find_episodes(
    graph: EventGraph,
    entries: list[FugueSubject],
) -> list[FugueEpisode]:
    """Detect episodes: gaps between subject entries.

    Checks for sequential patterns (repeated interval motifs at
    different pitch levels within the gap).
    """
    if not entries:
        return []

    sorted_entries = sorted(entries, key=lambda e: e.start_onset)

    # Merge overlapping entries.
    merged: list[tuple[float, float]] = []
    for entry in sorted_entries:
        if merged and entry.start_onset <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], entry.end_onset))
        else:
            merged.append((entry.start_onset, entry.end_onset))

    episodes: list[FugueEpisode] = []
    for (_, end_prev), (start_next, _) in zip(merged, merged[1:]):
        if start_next <= end_prev:
            continue
        # Determine measures.
        m_start = _measure_at_offset(graph, end_prev) or 1
        m_end = _measure_at_offset(graph, start_next) or m_start

        # Check for sequential patterns within the gap.
        sequential = _detect_sequential(graph, end_prev, start_next)

        episodes.append(
            FugueEpisode(
                start_onset=end_prev,
                end_onset=start_next,
                measure_start=m_start,
                measure_end=m_end,
                sequential=sequential,
            )
        )

    return episodes


def _measure_at_offset(graph: EventGraph, offset: float) -> int | None:
    """Find the measure number at or just after *offset*."""
    candidates = [n.measure_number for n in graph.sorted_events() if n.offset_quarters >= offset]
    return candidates[0] if candidates else None


def _detect_sequential(graph: EventGraph, start: float, end: float) -> bool:
    """Check if the passage between *start* and *end* contains a
    sequential pattern (a motif repeated at a different pitch level)."""
    pitches: list[int] = []
    for note in graph.sorted_events():
        if note.offset_quarters >= start and note.offset_quarters < end and note.midi is not None and not note.is_rest:
            pitches.append(note.midi)

    if len(pitches) < 4:
        return False

    intervals = [b - a for a, b in zip(pitches, pitches[1:])]
    # Look for a repeated 2-or-3-interval motif at different transposition.
    for motif_len in (2, 3):
        if len(intervals) < motif_len * 2:
            continue
        for i in range(len(intervals) - motif_len * 2 + 1):
            first = intervals[i : i + motif_len]
            second = intervals[i + motif_len : i + motif_len * 2]
            if first == second:
                return True
    return False


def analyze_fugue(graph: EventGraph) -> FugueAnalysisReport:
    """Main fugue analysis pipeline.

    Identify subject -> find answer -> find all entries -> detect stretto
    -> detect episodes.
    """
    voice_ids = graph.ordered_voice_ids()
    voice_count = len(voice_ids)

    subject = identify_subject(graph)
    answer: FugueAnswer | None = None
    subject_entries: list[FugueSubject] = []
    stretto_entries: list[StrettoEntry] = []
    episodes: list[FugueEpisode] = []
    exposition_end: float | None = None

    if subject is not None:
        answer = identify_answer(graph, subject)
        subject_entries = find_subject_entries(graph, subject)
        stretto_entries = find_stretto_entries(subject_entries)
        episodes = find_episodes(graph, subject_entries)

        # Exposition ends after all voices have entered with the subject.
        voices_entered: set[str] = set()
        for entry in sorted(subject_entries, key=lambda e: e.start_onset):
            voices_entered.add(entry.voice_id)
            if len(voices_entered) >= voice_count:
                exposition_end = entry.end_onset
                break

    return FugueAnalysisReport(
        work_id=graph.work_id,
        voice_count=voice_count,
        subject=subject,
        answer=answer,
        subject_entries=subject_entries,
        stretto_entries=stretto_entries,
        episodes=episodes,
        exposition_end_onset=exposition_end,
    )
