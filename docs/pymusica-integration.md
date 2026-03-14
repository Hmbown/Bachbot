# PyMusica Integration Strategy

`bachbot` and `PyMusica` should converge as a layered merge, not a flat repo collapse.

## Why the merge is logical

- `bachbot` is strongest at deterministic normalization, analysis, provenance, evidence bundles, and Bach-specific composition validation.
- `PyMusica` is strongest at general symbolic score IR, transformation utilities, and reusable exporter infrastructure.
- Both projects are built around symbolic-first music data rather than raw MIDI-first workflows.

That makes the projects complementary. The overlap is not the analysis core; it is the score/export substrate.

## Why a full collapse would be premature

- `bachbot`'s canonical analytical object is `EventGraph`, which carries stable measure and voice addressing needed by its analysis and provenance layers.
- `PyMusica`'s canonical object is `ScoreIR`, which is better suited to score construction, transformations, and projection into MIDI, MusicXML, and LilyPond.
- The repos currently declare different Python floors: `bachbot >=3.11`, `PyMusica >=3.12`.
- `bachbot`'s LilyPond export includes Bach-specific analysis markup that does not belong in a general-purpose symbolic toolkit.

## Integration boundary

Phase 1 uses `PyMusica` as an optional local backend for replaceable export surfaces.

- `EventGraph` remains the source of truth for analysis.
- `EventGraph -> ScoreIR` is handled by an adapter in `bachbot.integrations.pymusica`.
- `ScoreIR -> EventGraph` is now available for a selective, documented subset so PyMusica-authored material can re-enter bachbot analysis without going through lossy file exports.
- the adapter preserves stable score identity above the IR boundary through metadata such as measure references, voice labels, staff / part provenance, source refs, and defensible note-level markings
- the current adapter keeps one PyMusica `Part` per bachbot part label and one `VoiceTrack` per bachbot voice id, so part/voice addressing stays reconstructible without making `EventGraph` secondary
- preserved note metadata currently includes measure numbers, beat, source refs, part/staff provenance, articulations, lyrics, fermatas, ties, and exact offset/duration values where available
- `MusicXML` and `MIDI` can use `PyMusica` behind explicit backend selection.
- `LilyPond` stays native for now because `bachbot` adds Roman numerals, phrase breaths, and figured-bass overlays that are domain-specific.

## Reverse adapter subset

`score_ir_to_event_graph(...)` is intentionally narrow. It only accepts `ScoreIR` material that bachbot can analyze without inventing analytical structure.

- one non-overlapping monophonic event stream per `VoiceTrack`
- fixed global meter with no pickup measure
- no repeat / volta / rehearsal overlays
- no transposed voices
- no notation-only event overlays such as slurs, beams, or tuplets
- no score or event dynamics that would be silently discarded
- no events that cross a computed barline
- at most one initial key-signature change and one initial tempo change

The reverse adapter preserves bachbot identity metadata when present, including voice ids, section ids, measure numbering, source refs, and key-estimate metadata. When that metadata is absent, it emits deterministic defaults:

- `EncodingMetadata.source_format = "pymusica-scoreir"`
- provenance defaults to `["pymusica:scoreir"]`
- measure numbering starts at `1` unless bachbot section metadata says otherwise

Unsupported material fails loudly with `ScoreIRUnsupportedError` instead of being guessed into a misleading `EventGraph`.

## Bachbot-only fields

Some information should remain explicitly bachbot-only even when score identity is preserved through the adapter.

- `EventGraph` remains canonical for analytical addressing, evidence bundles, and deterministic validation.
- harmony-analysis products such as Roman numeral candidate sets, figured-bass summaries, cadence findings, phrase endings, and modulation graphs do not become PyMusica ontology.
- those fields should stay in bachbot reports / evidence payloads unless a future bridge needs a clearly scoped metadata mirror for a specific workflow.

## Local development setup

PyMusica-backed workflows are now treated as an explicit integration contract rather than a best-effort import side effect.

Discovery order is:

1. an installed `pymusica_lang` package already importable in the current interpreter
2. an explicit `BACHBOT_PYMUSICA_SRC=/path/to/PyMusica/src`
3. a documented sibling checkout layout such as `/Volumes/VIXinSSD/PyMusica/src`

If `BACHBOT_PYMUSICA_SRC` is set, it must point to a real `src/` directory containing `pymusica_lang`. `bachbot` no longer silently falls through to a sibling checkout when that override is wrong.

## Runtime contract

- `bachbot` core still declares `python >=3.11`
- `PyMusica` currently declares `python >=3.12`
- the supported interop contract for maintainers and CI is therefore a shared Python `3.12+` environment when PyMusica-backed workflows are required
- `bachbot` without PyMusica remains supported on `3.11+`
- sibling-source discovery exists as a local development bridge, but the reproducible contract is either:
  - install both repos into the same Python `3.12+` environment
  - or run `bachbot` with an explicit `BACHBOT_PYMUSICA_SRC`

Recommended local setup:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e "/path/to/PyMusica"
python -m pip install -e "/path/to/bachbot[dev]"
pytest tests/test_pymusica_integration.py tests/test_pymusica_runtime_contract.py -q
```

Supported local checkout bridge:

```bash
export BACHBOT_PYMUSICA_SRC=/path/to/PyMusica/src
python -m pip install -e "/path/to/bachbot[dev]"
pytest tests/test_pymusica_integration.py tests/test_pymusica_runtime_contract.py -q
```

CI guidance:

- use Python `3.12+` for jobs that exercise the PyMusica backend
- install `PyMusica` before `bachbot`, or set `BACHBOT_PYMUSICA_SRC` explicitly in the job environment
- run the integration suite, not just exporter smoke tests, so both discovery and `auto` fallback behavior stay pinned

If `pymusica_lang` is not installed into the current environment, `bachbot` can still find a sibling checkout by:

- `BACHBOT_PYMUSICA_SRC=/path/to/PyMusica/src`
- or the default sibling layout `/Volumes/VIXinSSD/PyMusica/src`

## Next phases

1. Expand the bridge to preserve more notation metadata where `EventGraph` has it.
2. Decide whether exporter code should eventually live entirely in `PyMusica` with `bachbot` retaining only Bach-specific annotation layers.
3. Revisit packaging once the shared boundary is stable enough to justify a real dependency instead of local checkout discovery.
