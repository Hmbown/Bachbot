"""MIDI export for EventGraph — maps SATB voices to MIDI channels."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from bachbot.encodings.event_graph import EventGraph
from bachbot.integrations.pymusica import (
    PyMusicaUnavailableError,
    event_graph_to_midi_with_pymusica,
    write_midi_with_pymusica,
)

# Voice → MIDI channel mapping (0-indexed). Standard GM organ patch.
_VOICE_CHANNEL: dict[str, int] = {
    "Soprano:1": 0, "S": 0, "soprano": 0, "Soprano": 0,
    "Alto:1": 1, "A": 1, "alto": 1, "Alto": 1,
    "Tenor:1": 2, "T": 2, "tenor": 2, "Tenor": 2,
    "Bass:1": 3, "B": 3, "bass": 3, "Bass": 3,
}

# GM program numbers: 0=Acoustic Grand Piano, 19=Church Organ
_DEFAULT_PROGRAM = 19  # Church organ
_TICKS_PER_BEAT = 480
_DEFAULT_TEMPO = 500000  # 120 BPM in microseconds per beat


def event_graph_to_midi(
    graph: EventGraph,
    tempo_bpm: int = 100,
    program: int | None = None,
    *,
    backend: str = "native",
) -> bytes:
    """Convert an EventGraph to MIDI bytes.

    Parameters
    ----------
    graph : EventGraph
        Source graph with SATB notes.
    tempo_bpm : int
        Tempo in beats per minute.
    program : int, optional
        GM program number (0-127). Defaults to 19 (Church Organ).

    Returns
    -------
    bytes
        Complete MIDI file content.
    """
    backend_name = backend.lower()
    if backend_name not in {"native", "pymusica", "auto"}:
        raise ValueError(f"Unsupported MIDI backend: {backend}")
    if backend_name != "native":
        try:
            return event_graph_to_midi_with_pymusica(graph, tempo_bpm=tempo_bpm)
        except PyMusicaUnavailableError:
            if backend_name == "pymusica":
                raise

    import mido

    mid = mido.MidiFile(ticks_per_beat=_TICKS_PER_BEAT)
    tempo = mido.bpm2tempo(tempo_bpm)
    prog = program if program is not None else _DEFAULT_PROGRAM

    # Collect notes per channel
    channel_notes: dict[int, list[tuple[float, float, int]]] = {}
    for note in graph.notes:
        if note.midi is None or note.is_rest:
            continue
        ch = _VOICE_CHANNEL.get(note.voice_id, 0)
        channel_notes.setdefault(ch, []).append(
            (note.offset_quarters, note.duration_quarters, note.midi)
        )

    # Create one track per channel
    for ch in sorted(channel_notes):
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # Tempo on first track only
        if ch == min(channel_notes):
            track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

        # Program change
        track.append(mido.Message("program_change", channel=ch, program=prog, time=0))

        # Build sorted events: (tick, type, midi, velocity)
        events: list[tuple[int, str, int, int]] = []
        for onset, dur, midi in channel_notes[ch]:
            on_tick = int(round(onset * _TICKS_PER_BEAT))
            off_tick = int(round((onset + dur) * _TICKS_PER_BEAT))
            events.append((on_tick, "note_on", midi, 64))
            events.append((off_tick, "note_off", midi, 0))

        events.sort(key=lambda e: (e[0], 0 if e[1] == "note_off" else 1))

        # Convert to delta times
        prev_tick = 0
        for tick, msg_type, midi, vel in events:
            delta = tick - prev_tick
            track.append(mido.Message(msg_type, channel=ch, note=midi, velocity=vel, time=delta))
            prev_tick = tick

    # Serialize to bytes
    import io
    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


def write_midi(graph: EventGraph, output: Path, **kwargs) -> None:
    """Write an EventGraph as a MIDI file."""
    backend_name = str(kwargs.get("backend", "native")).lower()
    if backend_name != "native":
        try:
            write_midi_with_pymusica(
                graph,
                output,
                tempo_bpm=int(kwargs.get("tempo_bpm", 100)),
            )
            return
        except PyMusicaUnavailableError:
            if backend_name == "pymusica":
                raise
    data = event_graph_to_midi(graph, **kwargs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)


def midi_to_wav(midi_path: Path, wav_path: Path, soundfont: str | None = None) -> bool:
    """Render MIDI to WAV using FluidSynth CLI (if installed).

    Returns True on success, False if FluidSynth is not available.
    """
    sf = soundfont
    if not sf:
        # Common macOS/Linux soundfont locations
        candidates = [
            "/usr/share/sounds/sf2/FluidR3_GM.sf2",
            "/usr/share/soundfonts/FluidR3_GM.sf2",
            "/opt/homebrew/share/fluidsynth/default.sf2",
            "/usr/local/share/fluidsynth/default.sf2",
        ]
        for c in candidates:
            if Path(c).exists():
                sf = c
                break

    if not sf:
        return False

    try:
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["fluidsynth", "-ni", sf, str(midi_path), "-F", str(wav_path), "-r", "44100"],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def midi_to_event_graph(midi_path: Path, work_id: str = "MIDI-IMPORT") -> EventGraph:
    """Import a MIDI file back to an EventGraph (for round-trip testing)."""
    import mido

    from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
    from bachbot.encodings.musicxml_io import midi_to_note_name
    from bachbot.models.base import TypedNote
    from bachbot.models.section import Section
    from bachbot.models.voice import Voice

    mid = mido.MidiFile(str(midi_path))
    tpb = mid.ticks_per_beat

    # Reverse channel mapping
    channel_voice = {0: "Soprano:1", 1: "Alto:1", 2: "Tenor:1", 3: "Bass:1"}

    notes: list[TypedNote] = []
    for track in mid.tracks:
        abs_tick = 0
        active: dict[tuple[int, int], float] = {}  # (channel, midi) -> onset_quarters

        for msg in track:
            abs_tick += msg.time
            onset_q = abs_tick / tpb

            if msg.type == "note_on" and msg.velocity > 0:
                active[(msg.channel, msg.note)] = onset_q
            elif msg.type in ("note_off", "note_on") and (msg.type == "note_off" or msg.velocity == 0):
                key = (msg.channel, msg.note)
                if key in active:
                    start = active.pop(key)
                    dur = onset_q - start
                    if dur > 0:
                        voice_id = channel_voice.get(msg.channel, f"Voice:{msg.channel}")
                        measure = int(start // 4) + 1  # approximate
                        beat = (start % 4) + 1
                        notes.append(TypedNote(
                            pitch=midi_to_note_name(msg.note),
                            midi=msg.note,
                            duration_quarters=round(dur, 4),
                            offset_quarters=round(start, 4),
                            measure_number=measure,
                            beat=round(beat, 4),
                            voice_id=voice_id,
                            part_name=voice_id.split(":")[0] if ":" in voice_id else voice_id,
                        ))

    sid = f"{work_id}:section:1"
    m_end = max((n.measure_number for n in notes), default=1)

    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id=work_id,
            work_id=work_id,
            source_format="midi",
        ),
        section=Section(
            section_id=sid, work_id=work_id, label="MIDI import",
            section_type="import", measure_start=1, measure_end=m_end,
        ),
        voices=[
            Voice(voice_id=vid, section_id=sid, part_name=vid.split(":")[0], normalized_voice_name=vid.split(":")[0])
            for vid in sorted({n.voice_id for n in notes})
        ],
        notes=notes,
    )
