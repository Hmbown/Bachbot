# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test

```bash
python3 -m pip install -e ".[dev]"   # Install (editable + dev deps)
python3 -m bachbot --version         # Verify CLI
pytest -q                            # Run all tests (51 tests, must stay green)
pytest tests/test_analysis.py::test_name -v   # Single test
python3 -m bachbot benchmark run --sample 10  # Composition quality benchmark
```

Python >=3.11 required. Dependencies: httpx, pydantic, pyyaml, typer. No linter configured.

## CLI Entry Point

`python3 -m bachbot [COMMAND]` — Typer app at `bachbot/cli/main.py`.

Subcommands: `corpus`, `analyze`, `compose`, `validate`, `detective`, `export`, `llm`, `benchmark`.

## Architecture

Five-layer system where each layer builds on the one below. The system is useful even with the LLM layer disabled.

```
Layer 1: Deterministic Core (encodings, analysis, registry, connectors)
Layer 2: Evidence Bundles (claims/bundle.py — contract between symbolic computation and LLM)
Layer 3: Constrained LLM (llm/ — interprets evidence, never invents facts)
Layer 4: Composition (composition/ — constraint-first, validator-heavy)
Layer 5: Platform Surface (cli/, exports/)
```

### Data Flow

Corpus files → `Normalizer` → **EventGraph** → `analyze_chorale()` → **AnalysisReport** → `build_evidence_bundle()` → **EvidenceBundle** → composition or LLM interpretation.

### Key Types

- **EventGraph** (`encodings/event_graph.py`): Core representation. Voices, TypedNotes with stable measure/voice addressing.
- **EvidenceBundle** (`claims/bundle.py`): Structured analytical findings (cadences, harmony, voice-leading, distributions). Contract for all downstream consumers.
- **AnalysisReport** (`analysis/pipeline.py`): Output of `analyze_chorale()`. Harmony, cadences, voice-leading, validation.
- **CompositionArtifact** (`models/`): Labeled generated output with trace and validation report.
- **BachbotModel** (`models/base.py`): Pydantic BaseModel with `extra="forbid"`, `validate_assignment=True`. All domain classes inherit from this.

### Composition Engine

`composition/generators/pattern_fill.py` — Main harmonizer. 43 chord types (diatonic triads/sevenths, secondary dominants, Neapolitan, augmented sixths, modal mixture), SATB spacing enforcement (S-A ≤12, A-T ≤12, T-B ≤12, T-B ≤19 semitones), cadence targeting, local key modulation, seventh chord upgrades. Uses exhaustive parallel search for voicings. SATB ranges follow Aldwell & Schachter: S(C4-G5), A(F3-C5), T(C3-G4), B(E2-C4).

`composition/service.py` — Orchestrates: `plan_chorale()` → `compose_chorale_study()` → returns (EventGraph, CompositionArtifact, report).

`composition/validators/hard_rules.py` — Checks parallel 5ths/8ves, range violations, voice crossing.

### LLM Layer

- `llm/wrappers.py`: `prepare_mode_response()` (dry-run) and `execute_mode_response()` (live httpx POST to OpenAI-compatible `/chat/completions`).
- `llm/adapters.py`: `build_request()` for 5 modes: scholar, detective, pedagogy, composer, aiml.
- Env vars: `BACHBOT_LLM_API_KEY`, `BACHBOT_LLM_MODEL`, `BACHBOT_LLM_PROVIDER`.

### Connectors

`connectors/bach_digital.py` — Solr API. `connectors/rism.py` — RISM Online API. `connectors/dcml.py` — Local TSV. `connectors/local_files.py` — MusicXML/MEI/Humdrum from disk.

## Data Layout

```
data/raw/<dataset>/         — Downloaded/imported corpus material
data/normalized/<dataset>/  — Canonicalized event graphs + address maps
data/derived/<dataset>/     — Features, reports, similarity tables, benchmarks
data/manifests/             — Dataset metadata, checksums, license records
```

## Design Principles

- Deterministic before generative — symbolic analysis is the source of truth, LLM is commentary.
- Every analytical claim must carry an `EvidenceStatus`: `SUPPORTED_FACT`, `INFERENCE`, `SPECULATION`, `DISPUTED`.
- Generated artifacts must be truthfully labeled (e.g., `bachbot-study`, never "authentic Bach").
- Provenance tracking at every layer. Many-to-many: work → sources → editions → encodings → analyses.
- Stable addressing: notes by `(measure_number, offset_quarters, voice_id)`, passages by `PassageRef`.

### Harmonic Analysis

`analysis/harmony/roman_candidates.py` — Recognizes diatonic triads, seventh chords, secondary dominants, Neapolitan (N6), augmented sixths (It+6, Fr+6, Ger+6), and modal mixture (bVI, bVII, bIII, borrowed iv). Diatonic readings are preferred over chromatic via scoring penalty.

`analysis/harmony/cadence.py` — Detects PAC, IAC, HC, PHC (Phrygian half cadence), DC, and PC (plagal cadence). Phrygian half cadence is identified by bass formula 6-5 (b6→5 descent).

### Schenkerian Analysis

`analysis/schenker/reduction.py` — Three-layer reduction (foreground/middleground/background) with Urlinie and Bassbrechung detection. **Caveat:** This is a computational heuristic, not a musicological analysis. Schenkerian reduction is an interpretive practice; the output should be treated as one plausible reading, not a definitive analysis.

### Species Counterpoint

`composition/counterpoint.py` — Pedagogical framework (Fux 1725 / Jeppesen 1939), NOT a model of Bach's actual contrapuntal practice. Bach writes free counterpoint that routinely exceeds species constraints. The primary cantus firmus (Fux-1) is the verified D-Dorian CF from Gradus ad Parnassum.

## Current Quality Gaps

- Chord variety: Analysis now recognizes chromatic chords (N6, augmented sixths, modal mixture), but composition still produces ~4.3 unique chords per chorale vs ~14.7 in originals — the harmonizer needs to proactively select chromatic chords, not just voice them when a bundle specifies them.
- Parallel octaves: ~21/30 chorales still have them — needs contrary motion, tendency tone constraints.
- Nonharmonic tones: bundles have SUS/PT/NT/NCT data but the composer ignores them.
- Inversions: chords are labeled by root position quality only; functional inversion (6, 6/4) is not distinguished in the harmonic plan.
- LLM: dry-run only (no live API calls yet) — `execute_mode_response()` in wrappers.py is ready but needs API key.
