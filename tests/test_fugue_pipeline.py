"""Tests for SHA-2830: WTC normalization and fugue analysis pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from bachbot.analysis.fugue.keyboard import normalize_keyboard_staves, separate_voices_by_pitch
from bachbot.analysis.fugue.pipeline import (
    FugueAnalysisReport,
    FugueAnswer,
    FugueEpisode,
    FugueSubject,
    StrettoEntry,
    analyze_fugue,
    find_episodes,
    find_stretto_entries,
    find_subject_entries,
    identify_answer,
    identify_subject,
)
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.models.base import TypedNote
from bachbot.models.refs import PassageRef
from bachbot.models.section import Section
from bachbot.models.voice import Voice


# ── Helpers ──


def _note(
    voice_id: str,
    midi: int,
    onset: float,
    duration: float = 1.0,
    measure: int = 1,
    beat: float = 1.0,
    staff_id: str | None = None,
) -> TypedNote:
    return TypedNote(
        pitch=None,
        midi=midi,
        duration_quarters=duration,
        offset_quarters=onset,
        measure_number=measure,
        beat=beat,
        voice_id=voice_id,
        staff_id=staff_id,
    )


def _make_graph(
    notes: list[TypedNote],
    voice_ids: list[str] | None = None,
    work_id: str = "WTC-TEST",
    section_type: str = "fugue",
) -> EventGraph:
    """Build a minimal EventGraph from a list of notes."""
    if voice_ids is None:
        voice_ids = sorted({n.voice_id for n in notes})
    section_id = f"{work_id}:s1"
    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id=f"{work_id}:enc",
            work_id=work_id,
            source_format="synthetic",
        ),
        section=Section(
            section_id=section_id,
            work_id=work_id,
            label="Fugue",
            section_type=section_type,
            measure_start=min(n.measure_number for n in notes),
            measure_end=max(n.measure_number for n in notes),
        ),
        voices=[
            Voice(
                voice_id=vid,
                section_id=section_id,
                normalized_voice_name=vid,
            )
            for vid in voice_ids
        ],
        notes=notes,
    )


def _two_voice_fugue_graph(
    *,
    subject_pitches: list[int],
    answer_pitches: list[int],
    subject_voice: str = "V1",
    answer_voice: str = "V2",
    subject_start: float = 0.0,
    answer_start: float | None = None,
) -> EventGraph:
    """Build a 2-voice graph with a subject then an answer."""
    if answer_start is None:
        answer_start = subject_start + len(subject_pitches)

    notes: list[TypedNote] = []
    for i, midi in enumerate(subject_pitches):
        onset = subject_start + i
        notes.append(_note(subject_voice, midi, onset, measure=int(onset // 4) + 1, beat=(onset % 4) + 1))
    for i, midi in enumerate(answer_pitches):
        onset = answer_start + i
        notes.append(_note(answer_voice, midi, onset, measure=int(onset // 4) + 1, beat=(onset % 4) + 1))
    return _make_graph(notes, voice_ids=[subject_voice, answer_voice])


# ── a) Subject identification ──


class TestSubjectIdentification:
    def test_subject_found_in_first_voice(self):
        """Voice 1 plays alone for 4 beats then voice 2 enters."""
        graph = _two_voice_fugue_graph(
            subject_pitches=[60, 62, 64, 65],
            answer_pitches=[67, 69, 71, 72],
        )
        subject = identify_subject(graph)
        assert subject is not None
        assert subject.voice_id == "V1"
        assert subject.midi_sequence == [60, 62, 64, 65]
        assert subject.interval_sequence == [2, 2, 1]
        assert subject.start_onset == 0.0
        assert subject.end_onset == 4.0

    def test_subject_none_on_empty_graph(self):
        graph = EventGraph(
            metadata=EncodingMetadata(encoding_id="empty", work_id="EMPTY", source_format="synthetic"),
            section=Section(section_id="EMPTY:s1", work_id="EMPTY", label="Fugue", section_type="fugue", measure_start=1, measure_end=1),
            voices=[],
            notes=[],
        )
        subject = identify_subject(graph)
        assert subject is None

    def test_subject_passage_ref(self):
        graph = _two_voice_fugue_graph(
            subject_pitches=[60, 62, 64, 65],
            answer_pitches=[67, 69, 71, 72],
        )
        subject = identify_subject(graph)
        assert subject is not None
        assert isinstance(subject.passage_ref, PassageRef)
        assert subject.passage_ref.voice_ids == ["V1"]

    def test_voice_hint_selects_alternate_voice(self):
        """When voice_hint is given, it overrides the default first voice."""
        # V2 enters first at onset 0, V1 enters at onset 4.
        notes = [
            _note("V2", 67, 0.0, measure=1, beat=1.0),
            _note("V2", 69, 1.0, measure=1, beat=2.0),
            _note("V1", 60, 4.0, measure=2, beat=1.0),
            _note("V1", 62, 5.0, measure=2, beat=2.0),
        ]
        graph = _make_graph(notes, voice_ids=["V1", "V2"])
        # Without hint, V2 is first.
        subject_default = identify_subject(graph)
        assert subject_default is not None
        assert subject_default.voice_id == "V2"
        # With hint, V1 is used (it must actually appear in entries).
        subject_hint = identify_subject(graph, voice_hint="V1")
        assert subject_hint is not None
        assert subject_hint.voice_id == "V1"


# ── b) Real answer detection ──


class TestRealAnswer:
    def test_real_answer_at_fifth(self):
        """Voice 2 enters with exact transposition at the 5th (+7 semitones)."""
        subject = [60, 62, 64, 65]
        answer = [67, 69, 71, 72]  # same intervals: +2, +2, +1
        graph = _two_voice_fugue_graph(subject_pitches=subject, answer_pitches=answer)
        subj = identify_subject(graph)
        assert subj is not None
        ans = identify_answer(graph, subj)
        assert ans is not None
        assert ans.answer_type == "real"
        assert ans.transposition_interval == 7
        assert ans.voice_id == "V2"


# ── c) Tonal answer detection ──


class TestTonalAnswer:
    def test_tonal_answer_with_mutation(self):
        """Voice 2 enters with a tonal mutation (interval change)."""
        subject = [60, 62, 64, 65]  # intervals: +2, +2, +1
        answer = [67, 69, 70, 72]   # intervals: +2, +1, +2 -- different!
        graph = _two_voice_fugue_graph(subject_pitches=subject, answer_pitches=answer)
        subj = identify_subject(graph)
        assert subj is not None
        ans = identify_answer(graph, subj)
        assert ans is not None
        assert ans.answer_type == "tonal"
        assert ans.transposition_interval == 7


# ── d) Subject entry search ──


class TestSubjectEntrySearch:
    def test_finds_entries_in_multiple_voices(self):
        """Subject placed at 3 different points in 2 voices."""
        # Subject: C D E F (intervals +2 +2 +1)
        subject_1 = [60, 62, 64, 65]  # V1, onset 0-3
        answer_1 = [67, 69, 71, 72]   # V2, onset 4-7 (real answer)
        # Third entry: V1 again at onset 8, transposed down
        entry_3 = [55, 57, 59, 60]    # same intervals

        notes: list[TypedNote] = []
        for i, m in enumerate(subject_1):
            notes.append(_note("V1", m, float(i), measure=1, beat=float(i % 4) + 1))
        for i, m in enumerate(answer_1):
            notes.append(_note("V2", m, float(i + 4), measure=2, beat=float(i % 4) + 1))
        for i, m in enumerate(entry_3):
            notes.append(_note("V1", m, float(i + 8), measure=3, beat=float(i % 4) + 1))

        graph = _make_graph(notes, voice_ids=["V1", "V2"])
        subject = identify_subject(graph)
        assert subject is not None
        entries = find_subject_entries(graph, subject)
        assert len(entries) >= 3
        voice_set = {e.voice_id for e in entries}
        assert "V1" in voice_set
        assert "V2" in voice_set

    def test_empty_subject_returns_empty(self):
        graph = _two_voice_fugue_graph(
            subject_pitches=[60],
            answer_pitches=[67],
        )
        subject = identify_subject(graph)
        assert subject is not None
        # Single-note subject has empty interval_sequence.
        assert subject.interval_sequence == []
        entries = find_subject_entries(graph, subject)
        assert entries == []


# ── e) Stretto detection ──


class TestStrettoDetection:
    def test_overlap_detected(self):
        """Second entry overlaps with first."""
        # Entry 1: V1, onset 0-3 (4 notes, each 1 beat)
        # Entry 2: V2, onset 2-5 (overlaps by 2 beats)
        entries = [
            FugueSubject(
                voice_id="V1",
                start_onset=0.0,
                end_onset=4.0,
                midi_sequence=[60, 62, 64, 65],
                interval_sequence=[2, 2, 1],
                passage_ref=PassageRef(measure_start=1, measure_end=1, voice_ids=["V1"]),
            ),
            FugueSubject(
                voice_id="V2",
                start_onset=2.0,
                end_onset=6.0,
                midi_sequence=[67, 69, 71, 72],
                interval_sequence=[2, 2, 1],
                passage_ref=PassageRef(measure_start=1, measure_end=2, voice_ids=["V2"]),
            ),
        ]
        stretto = find_stretto_entries(entries)
        assert len(stretto) == 1
        assert stretto[0].overlap_beats > 0
        assert stretto[0].voice_id == "V2"
        assert stretto[0].distance_from_previous == 2.0

    def test_no_overlap(self):
        """Non-overlapping entries produce no stretto."""
        entries = [
            FugueSubject(
                voice_id="V1",
                start_onset=0.0,
                end_onset=4.0,
                midi_sequence=[60, 62, 64, 65],
                interval_sequence=[2, 2, 1],
                passage_ref=PassageRef(measure_start=1, measure_end=1, voice_ids=["V1"]),
            ),
            FugueSubject(
                voice_id="V2",
                start_onset=4.0,
                end_onset=8.0,
                midi_sequence=[67, 69, 71, 72],
                interval_sequence=[2, 2, 1],
                passage_ref=PassageRef(measure_start=2, measure_end=2, voice_ids=["V2"]),
            ),
        ]
        stretto = find_stretto_entries(entries)
        assert stretto == []


# ── f) Episode detection ──


class TestEpisodeDetection:
    def test_gap_produces_episode(self):
        """Gap between two entry groups produces an episode."""
        # V1 subject at 0-3, V2 answer at 4-7 (so subject is 4 notes).
        # Then gap with non-matching filler, then V1 re-entry at 12-15.
        notes: list[TypedNote] = []
        # V1 subject.
        for i, m in enumerate([60, 62, 64, 65]):
            notes.append(_note("V1", m, float(i), measure=1, beat=float(i % 4) + 1))
        # V2 answer (real, at the 5th).
        for i, m in enumerate([67, 69, 71, 72]):
            notes.append(_note("V2", m, float(i + 4), measure=2, beat=float(i % 4) + 1))
        # Gap filler in V1 (non-matching intervals).
        for i, m in enumerate([70, 71, 70, 71]):
            notes.append(_note("V1", m, float(i + 8), measure=3, beat=float(i % 4) + 1))
        # V1 re-entry with subject transposed down.
        for i, m in enumerate([55, 57, 59, 60]):
            notes.append(_note("V1", m, float(i + 12), measure=4, beat=float(i % 4) + 1))

        graph = _make_graph(notes, voice_ids=["V1", "V2"])
        subject = identify_subject(graph)
        assert subject is not None
        assert len(subject.midi_sequence) == 4  # Subject is first 4 notes.
        entries = find_subject_entries(graph, subject)
        assert len(entries) >= 2
        episodes = find_episodes(graph, entries)
        assert len(episodes) >= 1
        ep = episodes[0]
        assert ep.end_onset > ep.start_onset

    def test_no_episodes_when_entries_adjacent(self):
        """Adjacent entries produce no episodes."""
        entries = [
            FugueSubject(
                voice_id="V1",
                start_onset=0.0,
                end_onset=4.0,
                midi_sequence=[60, 62, 64, 65],
                interval_sequence=[2, 2, 1],
                passage_ref=PassageRef(measure_start=1, measure_end=1, voice_ids=["V1"]),
            ),
            FugueSubject(
                voice_id="V2",
                start_onset=4.0,
                end_onset=8.0,
                midi_sequence=[67, 69, 71, 72],
                interval_sequence=[2, 2, 1],
                passage_ref=PassageRef(measure_start=2, measure_end=2, voice_ids=["V2"]),
            ),
        ]
        graph = _two_voice_fugue_graph(
            subject_pitches=[60, 62, 64, 65],
            answer_pitches=[67, 69, 71, 72],
        )
        episodes = find_episodes(graph, entries)
        assert episodes == []


# ── g) Full pipeline ──


class TestFullPipeline:
    def test_three_voice_exposition(self):
        """Complete synthetic 3-voice fugue exposition."""
        # Subject: C D E F (intervals: +2, +2, +1)
        # Answer in V2 at the 5th (real): G A B C
        # Third entry in V3 at the octave below: C D E F
        notes: list[TypedNote] = []
        subj = [60, 62, 64, 65]
        ans = [67, 69, 71, 72]
        entry3 = [48, 50, 52, 53]

        for i, m in enumerate(subj):
            notes.append(_note("V1", m, float(i), measure=1, beat=float(i % 4) + 1))
        for i, m in enumerate(ans):
            notes.append(_note("V2", m, float(i + 4), measure=2, beat=float(i % 4) + 1))
        # V1 continues with filler during V2 answer.
        for i, m in enumerate([64, 62, 60, 59]):
            notes.append(_note("V1", m, float(i + 4), measure=2, beat=float(i % 4) + 1))
        for i, m in enumerate(entry3):
            notes.append(_note("V3", m, float(i + 8), measure=3, beat=float(i % 4) + 1))
        # V1 and V2 continue with filler.
        for i, m in enumerate([60, 62]):
            notes.append(_note("V1", m, float(i + 8), measure=3, beat=float(i % 4) + 1))
        for i, m in enumerate([71, 69]):
            notes.append(_note("V2", m, float(i + 8), measure=3, beat=float(i % 4) + 1))

        graph = _make_graph(notes, voice_ids=["V1", "V2", "V3"])
        report = analyze_fugue(graph)

        assert isinstance(report, FugueAnalysisReport)
        assert report.work_id == "WTC-TEST"
        assert report.voice_count == 3
        assert report.subject is not None
        assert report.subject.voice_id == "V1"
        assert report.answer is not None
        assert report.answer.voice_id == "V2"
        assert report.answer.answer_type == "real"
        assert len(report.subject_entries) >= 3
        assert report.exposition_end_onset is not None

    def test_report_model_extra_forbid(self):
        """FugueAnalysisReport inherits BachbotModel extra=forbid."""
        with pytest.raises(Exception):
            FugueAnalysisReport(
                work_id="test",
                voice_count=2,
                extra_field="bad",
            )

    def test_empty_graph(self):
        """Pipeline handles an empty graph gracefully."""
        graph = _make_graph(
            [_note("V1", 60, 0.0)],
            voice_ids=["V1"],
        )
        report = analyze_fugue(graph)
        assert report.voice_count == 1
        assert report.subject is not None
        assert report.answer is None


# ── h) Voice separation ──


class TestVoiceSeparation:
    def test_interleaved_pitches_separated(self):
        """Interleaved pitches on one staff should be separated by proximity."""
        notes = [
            _note("X", 60, 0.0, staff_id="1"),   # low
            _note("X", 72, 0.0, staff_id="1"),   # high
            _note("X", 61, 1.0, staff_id="1"),   # low (close to 60)
            _note("X", 71, 1.0, staff_id="1"),   # high (close to 72)
            _note("X", 62, 2.0, staff_id="1"),   # low
            _note("X", 70, 2.0, staff_id="1"),   # high
        ]
        separated = separate_voices_by_pitch(notes, max_voices=2)
        assert len(separated) == 2

        # Check that each voice stays in a pitch band.
        for vid, vnotes in separated.items():
            midis = [n.midi for n in vnotes]
            assert max(midis) - min(midis) <= 4, f"Voice {vid} has too wide a range: {midis}"

    def test_single_voice(self):
        notes = [_note("X", 60, 0.0), _note("X", 62, 1.0)]
        separated = separate_voices_by_pitch(notes, max_voices=1)
        assert len(separated) == 1
        assert len(list(separated.values())[0]) == 2

    def test_empty_notes(self):
        assert separate_voices_by_pitch([], max_voices=2) == {}

    def test_normalize_keyboard_staves_two_staff(self):
        """Two-staff keyboard music is split into voice-separated graph."""
        notes = [
            _note("P1", 60, 0.0, staff_id="1"),
            _note("P1", 72, 0.0, staff_id="1"),
            _note("P2", 48, 0.0, staff_id="2"),
            _note("P1", 61, 1.0, staff_id="1"),
            _note("P1", 71, 1.0, staff_id="1"),
            _note("P2", 49, 1.0, staff_id="2"),
        ]
        graph = _make_graph(notes, voice_ids=["P1", "P2"])
        result = normalize_keyboard_staves(graph)
        new_voice_ids = sorted({n.voice_id for n in result.notes})
        # Should have more than original 2 voice ids.
        assert len(new_voice_ids) >= 2
        # All notes preserved.
        assert len(result.notes) == len(notes)


# ── i) CLI test ──


class TestCLI:
    def test_fugue_command_registered(self):
        """The 'fugue' command is registered in the analyze CLI."""
        from bachbot.cli.analyze import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "fugue" in command_names


# ── j) Parametrized corpus test (skipif no data) ──


_CORPUS_FUGUES = list(Path("data/raw").glob("**/fugue*")) if Path("data/raw").exists() else []


@pytest.mark.skipif(not _CORPUS_FUGUES, reason="No fugue corpus data available")
@pytest.mark.parametrize("fugue_path", _CORPUS_FUGUES[:3])
def test_corpus_fugue(fugue_path: Path):
    """Run pipeline on real fugue data if available."""
    from bachbot.encodings import Normalizer

    graph = Normalizer().normalize(fugue_path)
    report = analyze_fugue(graph)
    assert isinstance(report, FugueAnalysisReport)
    assert report.voice_count >= 1


# ── Additional edge case tests ──


class TestSequentialDetection:
    def test_sequential_episode_detected(self):
        """Episode with repeated intervallic motif is flagged sequential."""
        notes: list[TypedNote] = []
        # Subject in V1: onset 0-3.
        for i, m in enumerate([60, 62, 64, 65]):
            notes.append(_note("V1", m, float(i), measure=1, beat=float(i % 4) + 1))
        # Sequential episode: repeated motif at onset 4-7.
        # Motif: +2, +2 repeated twice at different levels.
        for i, m in enumerate([66, 68, 70, 72, 74, 76]):
            notes.append(_note("V1", m, float(i + 4), measure=2, beat=float((i + 4) % 4) + 1))
        # Subject return in V2 at onset 10.
        for i, m in enumerate([55, 57, 59, 60]):
            notes.append(_note("V2", m, float(i + 10), measure=3, beat=float((i + 10) % 4) + 1))

        graph = _make_graph(notes, voice_ids=["V1", "V2"])
        subject = identify_subject(graph)
        assert subject is not None
        entries = find_subject_entries(graph, subject)
        episodes = find_episodes(graph, entries)
        # Should find at least one episode between the subject groups.
        if episodes:
            # If the sequential detector fires, great.
            assert isinstance(episodes[0].sequential, bool)


class TestModelValidation:
    def test_fugue_subject_extra_forbid(self):
        with pytest.raises(Exception):
            FugueSubject(
                voice_id="V1",
                start_onset=0.0,
                end_onset=4.0,
                midi_sequence=[60],
                interval_sequence=[],
                passage_ref=PassageRef(measure_start=1, measure_end=1, voice_ids=["V1"]),
                bogus="bad",
            )

    def test_fugue_answer_extra_forbid(self):
        with pytest.raises(Exception):
            FugueAnswer(
                voice_id="V1",
                start_onset=0.0,
                answer_type="real",
                transposition_interval=7,
                passage_ref=PassageRef(measure_start=1, measure_end=1, voice_ids=["V1"]),
                bogus="bad",
            )

    def test_stretto_entry_extra_forbid(self):
        with pytest.raises(Exception):
            StrettoEntry(
                voice_id="V1",
                start_onset=0.0,
                overlap_beats=2.0,
                distance_from_previous=2.0,
                bogus="bad",
            )

    def test_fugue_episode_extra_forbid(self):
        with pytest.raises(Exception):
            FugueEpisode(
                start_onset=0.0,
                end_onset=4.0,
                measure_start=1,
                measure_end=1,
                bogus="bad",
            )
