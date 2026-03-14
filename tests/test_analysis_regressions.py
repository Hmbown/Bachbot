from __future__ import annotations

from pathlib import Path

from bachbot.analysis import analyze_graph
from bachbot.analysis.chorale.satb import validate_spacing
from bachbot.analysis.counterpoint.dissonance import detect_suspensions
from bachbot.analysis.counterpoint.voiceleading import detect_parallels
from bachbot.analysis.form.phrase import infer_phrase_endings
from bachbot.analysis.fugue.answer import detect_real_or_tonal_answers
from bachbot.analysis.fugue.countersubject import detect_countersubjects
from bachbot.analysis.fugue.episodes import segment_episodes
from bachbot.analysis.fugue.stretto import scan_stretto_windows
from bachbot.analysis.fugue.subject import detect_subject_candidates
from bachbot.analysis.harmony.cadence import detect_cadences
from bachbot.analysis.harmony.verticalities import build_verticalities
from bachbot.claims.bundle import build_evidence_bundle
from bachbot.encodings.dcml_tsv_io import parse_dcml_tsv
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.encodings.musicxml_io import parse_musicxml
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.section import Section
from bachbot.models.voice import Voice


def _voice(voice_id: str) -> Voice:
    return Voice(
        voice_id=voice_id,
        section_id="section_1",
        part_name=voice_id,
        normalized_voice_name=voice_id,
        instrument_or_role=voice_id,
    )


def _note(
    voice_id: str,
    midi: int | None,
    onset: float,
    duration: float,
    *,
    measure: int | None = None,
    beat: float | None = None,
    tie_start: bool = False,
    tie_stop: bool = False,
    fermata: bool = False,
    is_rest: bool = False,
) -> TypedNote:
    inferred_measure = measure if measure is not None else int(onset // 4) + 1
    inferred_beat = beat if beat is not None else (onset % 4) + 1
    return TypedNote(
        pitch=None if midi is None else f"midi-{midi}",
        midi=midi,
        duration_quarters=duration,
        offset_quarters=onset,
        measure_number=inferred_measure,
        beat=inferred_beat,
        voice_id=voice_id,
        part_name=voice_id,
        tie_start=tie_start,
        tie_stop=tie_stop,
        fermata=fermata,
        is_rest=is_rest,
        source_ref=f"section_1:m{inferred_measure}",
    )


def _graph(
    notes: list[TypedNote],
    *,
    voice_ids: list[str],
    title: str = "Synthetic Piece",
    section_type: str = "movement",
    key_tonic: str = "C",
    key_mode: str = "major",
) -> EventGraph:
    measure_end = max(note.measure_number for note in notes) if notes else 1
    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id="synthetic",
            work_id="SYNTH",
            title=title,
            source_format="test",
            key_estimate=KeyEstimate(tonic=key_tonic, mode=key_mode, confidence=0.99),
        ),
        section=Section(
            section_id="section_1",
            work_id="SYNTH",
            label=title,
            section_type=section_type,
            measure_start=1,
            measure_end=measure_end,
        ),
        voices=[_voice(voice_id) for voice_id in voice_ids],
        notes=notes,
    )


def _fugue_graph() -> EventGraph:
    subject = [60, 62, 63, 62, 64]
    answer = [67, 69, 70, 69, 71]
    later_entry = [65, 67, 68, 67, 69]
    countersubject_b = [55, 56, 57, 58, 59]
    countersubject_c = [62, 63, 64, 65, 66]
    notes: list[TypedNote] = []
    for index, midi in enumerate(subject):
        notes.append(_note("S", midi, float(index), 1.0))
    for index, midi in enumerate(answer, start=2):
        notes.append(_note("A", midi, float(index), 1.0))
    for index, midi in enumerate(later_entry, start=9):
        notes.append(_note("T", midi, float(index), 1.0))
    for index, midi in enumerate(countersubject_b, start=12):
        notes.append(_note("B", midi, float(index), 1.0))
    for index, midi in enumerate(countersubject_c, start=16):
        notes.append(_note("C", midi, float(index), 1.0))
    return _graph(notes, voice_ids=["S", "A", "T", "B", "C"], title="Synthetic Fugue", section_type="fugue")


def test_verticalities_use_notes_starting_at_boundary_for_measure_numbers() -> None:
    graph = _graph(
        [
            _note("S", 67, 3.0, 2.0, measure=1, beat=4.0),
            _note("A", 64, 4.0, 1.0, measure=2, beat=1.0),
        ],
        voice_ids=["S", "A"],
    )
    slices = build_verticalities(graph)
    assert [slice_.measure_number for slice_ in slices] == [1, 2]


def test_cadence_detection_uses_boundary_transition_and_requires_bass_support_for_pac() -> None:
    pac_graph = _graph(
        [
            _note("B", 55, 3.0, 1.0),
            _note("T", 59, 3.0, 1.0),
            _note("A", 62, 3.0, 1.0),
            _note("S", 71, 3.0, 1.0),
            _note("B", 48, 4.0, 2.0),
            _note("T", 67, 4.0, 2.0),
            _note("A", 64, 4.0, 2.0),
            _note("S", 72, 4.0, 2.0),
            _note("B", 55, 6.0, 1.0),
            _note("T", 59, 6.0, 1.0),
            _note("A", 62, 6.0, 1.0),
            _note("S", 71, 6.0, 1.0),
        ],
        voice_ids=["S", "A", "T", "B"],
    )
    pac = detect_cadences(pac_graph)[0]
    assert pac.ref_id.endswith("m2")
    assert pac.cadence_type == "PAC"
    assert pac.bass_formula == "5-1"
    assert pac.soprano_formula == "7-1"

    iac_graph = _graph(
        [
            _note("B", 55, 3.0, 1.0),
            _note("T", 59, 3.0, 1.0),
            _note("A", 62, 3.0, 1.0),
            _note("S", 71, 3.0, 1.0),
            _note("B", 52, 4.0, 1.0),
            _note("T", 60, 4.0, 1.0),
            _note("A", 67, 4.0, 1.0),
            _note("S", 72, 4.0, 1.0),
        ],
        voice_ids=["S", "A", "T", "B"],
    )
    iac = detect_cadences(iac_graph)[0]
    assert iac.cadence_type == "IAC"


def test_cadence_detection_supports_deceptive_resolution() -> None:
    graph = _graph(
        [
            _note("B", 55, 3.0, 1.0),
            _note("T", 59, 3.0, 1.0),
            _note("A", 62, 3.0, 1.0),
            _note("S", 71, 3.0, 1.0),
            _note("B", 57, 4.0, 1.0),
            _note("T", 60, 4.0, 1.0),
            _note("A", 64, 4.0, 1.0),
            _note("S", 72, 4.0, 1.0),
        ],
        voice_ids=["S", "A", "T", "B"],
    )
    cadence = detect_cadences(graph)[0]
    assert cadence.cadence_type == "DC"
    assert cadence.bass_formula == "5-6"


def test_parallel_detector_distinguishes_direct_perfect_intervals() -> None:
    graph = _graph(
        [
            _note("A", 60, 0.0, 1.0),
            _note("S", 67, 0.0, 1.0),
            _note("A", 62, 1.0, 1.0),
            _note("S", 74, 1.0, 1.0),
        ],
        voice_ids=["S", "A"],
    )
    findings = detect_parallels(graph)
    assert all(item["type"] not in {"parallel_5ths", "parallel_8ves"} for item in findings)
    assert any(item["type"] == "direct_perfect" for item in findings)


def test_spacing_validation_checks_each_verticality() -> None:
    graph = _graph(
        [
            _note("B", 48, 0.0, 1.0),
            _note("T", 55, 0.0, 1.0),
            _note("A", 60, 0.0, 1.0),
            _note("S", 84, 0.0, 1.0),
            _note("B", 48, 1.0, 1.0),
            _note("T", 55, 1.0, 1.0),
            _note("A", 64, 1.0, 1.0),
            _note("S", 72, 1.0, 1.0),
        ],
        voice_ids=["S", "A", "T", "B"],
    )
    issues = validate_spacing(graph)
    assert len(issues) == 1
    assert issues[0]["onset"] == 0.0


def test_dcml_and_musicxml_ties_produce_importer_agnostic_suspensions(tmp_path: Path) -> None:
    notes_path = tmp_path / "suspension.notes.tsv"
    notes_path.write_text(
        "\n".join(
            [
                "mn\tquarterbeats\tduration_qb\tstaff\tvoice\tmidi\tname\toctave\tmn_onset\ttied",
                "1\t4\t1\t1\t1\t67\tG\t4\t1\t1",
                "2\t5\t1\t1\t1\t67\tG\t4\t1\t-1",
                "2\t6\t1\t1\t1\t65\tF\t4\t2\t",
            ]
        ),
        encoding="utf-8",
    )
    dcml_graph = parse_dcml_tsv(notes_path)
    dcml_notes = dcml_graph.notes_by_voice()["S"]
    assert dcml_notes[0].tie_start is True
    assert dcml_notes[1].tie_stop is True
    assert len(detect_suspensions(dcml_graph)) == 1

    musicxml_path = tmp_path / "suspension.musicxml"
    musicxml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Soprano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <tie type="start"/>
        <notations><tied type="start"/></notations>
      </note>
      <forward><duration>3</duration></forward>
    </measure>
    <measure number="2">
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <tie type="stop"/>
        <notations><tied type="stop"/></notations>
      </note>
      <note>
        <pitch><step>F</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
      </note>
    </measure>
  </part>
</score-partwise>
""",
        encoding="utf-8",
    )
    musicxml_graph = parse_musicxml(musicxml_path)
    musicxml_notes = musicxml_graph.notes_by_voice()["S"]
    assert musicxml_notes[0].tie_start is True
    assert musicxml_notes[1].tie_stop is True
    assert len(detect_suspensions(musicxml_graph)) == 1


def test_phrase_endings_are_not_just_cadence_projection(simple_chorale_graph) -> None:
    cadences = detect_cadences(simple_chorale_graph)
    phrase_endings = infer_phrase_endings(simple_chorale_graph)
    assert cadences
    assert phrase_endings == []


def test_bundle_serializes_full_key_context_and_computed_findings(simple_chorale_graph) -> None:
    report = analyze_graph(simple_chorale_graph)
    bundle = build_evidence_bundle(simple_chorale_graph, report)
    assert bundle.metadata.key == "C major"
    assert bundle.metadata.key_tonic == "C"
    assert bundle.metadata.key_mode == "major"
    assert "distributions" in bundle.deterministic_findings
    assert "anomalies" in bundle.deterministic_findings
    assert "validation_report" in bundle.deterministic_findings
    assert bundle.deterministic_findings["claims"]


def test_fugue_detectors_use_positional_occurrences_and_export_voice_leading() -> None:
    graph = _fugue_graph()
    subjects = detect_subject_candidates(graph)
    primary = max(subjects, key=lambda item: len(item["occurrences"]))
    assert [occurrence["voice_id"] for occurrence in primary["occurrences"]] == ["S", "A", "T"]
    assert [occurrence["entry_order"] for occurrence in primary["occurrences"]] == [1, 2, 3]
    assert primary["occurrences"][1]["start_onset"] == 2.0

    answers = detect_real_or_tonal_answers(graph)
    assert any(item["subject_voice"] == "S" and item["answer_voice"] == "A" and item["answer_type"] == "real_answer" for item in answers)

    stretto = scan_stretto_windows(graph)
    assert stretto
    assert stretto[0]["overlap_duration"] > 0

    episodes = segment_episodes(graph)
    assert episodes
    assert episodes[0]["start_onset"] == 7.0
    assert episodes[0]["end_onset"] == 9.0

    countersubjects = detect_countersubjects(graph)
    assert any(len(item["voices"]) >= 2 for item in countersubjects)

    report = analyze_graph(graph)
    assert report.voice_leading["counterpoint"]["issues"] is not None
    assert report.fugue["answers"]
