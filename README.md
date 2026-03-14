# BACHBOT

BACHBOT is a deterministic, provenance-aware Bach research and composition system.

Version `0.1` is designed as a local-first Python package, CLI, and notebook environment for scholars, theorists, composers, teachers, and ML researchers who need inspectable symbolic workflows rather than an opaque chatbot. The core rule is simple: deterministic evidence comes first, and language-model output is commentary over that evidence, never a substitute for it.

## Thesis

BACHBOT binds together:

- authority metadata from Bach Digital, RISM, and related catalogs;
- machine-readable symbolic encodings such as MEI, MusicXML, Humdrum, and MuseScore-derived material;
- deterministic normalization into measure- and voice-addressable internal structures;
- rule-based analysis for harmony, counterpoint, cadence, motivic behavior, and form;
- a constrained LLM layer that may interpret, compare, explain, and hypothesize only from structured evidence bundles;
- a labeled composition engine for studies, continuations, and reconstruction hypotheses that never masquerade as authentic Bach.

The result is not “an AI that talks about Bach.” It is a reproducible research instrument for Bach scholarship and computational experimentation.

## Install and Quickstart

From a repo checkout:

```bash
python3 -m pip install -e ".[dev]"
python3 -m bachbot --version
pytest -q
```

Quickstart example commands:

```bash
python3 -m bachbot analyze chorale examples/chorales/simple_chorale.musicxml
python3 -m bachbot export report examples/chorales/simple_chorale.musicxml --output data/derived/example-report.md
python3 -m bachbot validate score examples/chorales/simple_chorale.musicxml
python3 -m bachbot detective scan examples/chorales/simple_chorale.musicxml --output data/derived/example-detective.json
python3 -m bachbot llm run scholar examples/chorales/simple_chorale.musicxml --question "What does the cadence pattern suggest?"
python3 -m bachbot compose chorale examples/chorales/simple_cantus.musicxml --output-prefix data/derived/example-chorale
python3 -m bachbot benchmark predict-next --all-models --output data/derived/next_chord_benchmark.json
python3 -m bachbot benchmark quality --sample 30 --output data/derived/quality_benchmark.json
```

The quality benchmark prints a per-chorale evidence-vs-baseline comparison
table and writes the same structured results to JSON for reproducible follow-up
analysis.

See [Quickstart](docs/quickstart.md) for a fuller walkthrough, including corpus registration and sync commands.

Optional PyMusica-backed workflows now use an explicit runtime contract:

- `bachbot` core remains `python >=3.11`
- `music21` interop is available via the optional extra: `python -m pip install -e ".[music21]"`
- `PyMusica` currently declares `python >=3.12`
- if you need the PyMusica MusicXML/MIDI backend or the `ScoreIR <-> EventGraph` bridge, use a shared Python `3.12+` environment and either:
  - `python -m pip install -e "/path/to/PyMusica"` before installing `bachbot`
  - or set `BACHBOT_PYMUSICA_SRC=/path/to/PyMusica/src`
- if `BACHBOT_PYMUSICA_SRC` is set, it must point to a real `src/` directory containing `pymusica_lang`

The focused integration validation command is:

```bash
pytest tests/test_pymusica_integration.py tests/test_pymusica_runtime_contract.py -q
```

For live evidence-bounded LLM execution, keep dry-run as the default and opt in explicitly:

```bash
export BACHBOT_LLM_API_KEY=...
export BACHBOT_LLM_MODEL=gpt-4.1-mini
python3 -m bachbot llm run scholar \
  examples/chorales/simple_chorale.musicxml \
  --question "Summarize what the bundle strongly supports." \
  --execute \
  --output data/derived/example-llm.json
```

## Core Principles

- Deterministic before generative.
- Source-first, not edition-blind.
- Every analytical claim must be addressable to passages, sources, and methods.
- Evidence typing is mandatory: `supported_fact`, `inference`, `speculation`.
- Multiple analytical lenses may coexist without forcing a single ground truth.
- Licensing and provenance are part of the architecture.
- Generated artifacts must be truthfully labeled.
- Local-first storage and human-correctable pipelines take priority over convenience.

## v0.1 Scope

The credible `v0.1` target is:

- corpus registration with manifests, checksums, license tracking, and catalog revision support;
- Bach Digital and RISM authority ingestion;
- normalization of seed symbolic corpora into an internal event graph with stable measure and voice references;
- deterministic chorale-oriented analysis including SATB legality checks, verticality summaries, harmonic-event candidates, and cadence detection;
- evidence-bundle export for scholar, pedagogy, detective, composer, and AI/ML modes;
- explicitly labeled composition studies with validation reports;
- local benchmarks for corpus integrity, analysis quality, provenance correctness, and generation honesty.

## Planned Repository Shape

The repo is organized around a deterministic scholarly core:

- `bachbot/models/`: typed schema entities for works, sources, sections, motifs, claims, provenance, and composition artifacts.
- `bachbot/registry/`: manifests, checksums, license handling, storage, and dataset registration.
- `bachbot/connectors/`: Bach Digital, RISM, DCML-like corpora, and local file connectors.
- `bachbot/encodings/`: parsing, normalization, address maps, and event-graph construction.
- `bachbot/analysis/`: counterpoint, harmony, cadence, fugue, chorale, form, graphs, and statistics.
- `bachbot/search/`: passage indexing and retrieval.
- `bachbot/composition/`: constraint solvers, scaffolds, validators, and artifact builders.
- `bachbot/claims/`: evidence bundles, uncertainty handling, and reporting.
- `bachbot/llm/`: prompts, wrappers, and guardrails.
- `bachbot/evals/`: benchmarks and rubrics.
- `bachbot/exports/`: JSON, MEI, MusicXML, report, and media exports.
- `bachbot/cli/`: user-facing commands for corpus management, analysis, search, composition, validation, and export.

## Data Layout

- `data/raw/`: downloaded or imported corpus material.
- `data/normalized/`: canonicalized event-graph and address-map outputs.
- `data/derived/`: features, indexes, reports, and similarity tables.
- `data/private/`: non-redistributable or rights-sensitive local assets.
- `data/manifests/`: dataset and benchmark metadata, provenance seeds, checksum policy, and license records.

Authority datasets follow the same three-stage lifecycle as local corpora:

- `corpus sync` stores raw search payloads and per-record authority exports under `data/raw/<dataset>/`.
- `corpus normalize` writes compact canonical authority summaries under `data/normalized/<dataset>/`.
- `corpus analyze` writes inspectable relationship and external-reference indexes under `data/derived/<dataset>/`.

## Corpus CLI Examples

Register manifests:

```bash
bachbot corpus register data/manifests/bach_digital.yaml
bachbot corpus register data/manifests/rism.yaml
bachbot corpus register data/manifests/dcml_bach_chorales.yaml
```

Sync an open local corpus:

```bash
bachbot corpus sync dcml_bach_chorales --source-root ./seed_corpus
```

Sync Bach Digital authority records by explicit identifier or URL:

```bash
bachbot corpus sync bach_digital --kind work --record-id 00001262 --include-linked
bachbot corpus sync bach_digital --kind source --record-url https://www.bach-digital.de/receive/BachDigitalSource_source_00000863?lang=en
```

Sync Bach Digital by deterministic first-page search:

```bash
bachbot corpus sync bach_digital --kind work --query "BWV 1076" --query-field musicrepo_work01 --limit 1
```

Sync RISM source authority records by explicit identifier or deterministic first-page search:

```bash
bachbot corpus sync rism --mode sources --record-id 1001145660
bachbot corpus sync rism --mode sources --query bach --rows 20 --limit 1
```

Normalize and analyze any registered dataset:

```bash
bachbot corpus normalize bach_digital
bachbot corpus analyze bach_digital
bachbot corpus normalize rism
bachbot corpus analyze rism
```

## Truth Labels

Every nontrivial claim in BACHBOT should be typed:

- `supported_fact`: directly grounded in source metadata or deterministic extraction.
- `inference`: a plausible interpretation drawn from evidence.
- `speculation`: a hypothesis or conjecture not yet established.

LLM output must preserve those distinctions. It may not invent score facts, source relationships, dates, or provenance.

## Generated Artifact Labels

Generated output is never “a lost Bach.” Artifacts must carry explicit classes such as:

- `bachbot-study`
- `bachbot-continuation`
- `bachbot-reconstruction-hypothesis`
- `bachbot-what-if`
- `bachbot-bach-inspired`

## Documentation

- [Quickstart](docs/quickstart.md)
- [Architecture](docs/architecture.md)
- [Next-Chord Benchmark](docs/next-chord-benchmark.md)
- [Quality Evaluation](docs/quality-evaluation.md)
- [Benchmark Dashboard](docs/benchmark-dashboard.md)
- [Complexity Metrics](docs/complexity-metrics.md)
- [Truth Labeling](docs/truth-labeling.md)
- [Provenance Policy](docs/provenance-policy.md)
- [Licensing Policy](docs/licensing.md)
- [PyMusica Integration Strategy](docs/pymusica-integration.md)
- [MVP Plan](docs/mvp-plan.md)

## Seed Manifests

Initial dataset and benchmark metadata live under `data/manifests/`:

- `bach_digital.yaml`
- `rism.yaml`
- `dcml_bach_chorales.yaml`
- `benchmark_core_v0_1.yaml`
- `benchmark_core_v0_1.json`

## Development Status

This repository is being built around a thesis-driven `v0.1` core. The emphasis is on reproducible symbolic infrastructure first, then constrained GPT-assisted interpretation and composition workflows on top of inspectable evidence bundles. The current milestone supports real Bach Digital and RISM authority ingestion with dataset-aware sync, normalize, and analyze stages, while keeping authority outputs separate from `dcml_bach_chorales` normalization and score-analysis artifacts.
