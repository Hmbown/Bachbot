# MVP Plan

## Goal

Ship a credible `v0.1` local-first research system, not a chat wrapper.

## Phase 0: Foundation

- Create the package and repository skeleton.
- Define typed schemas for works, sources, encodings, claims, provenance, and artifacts.
- Implement dataset manifests, checksum handling, storage policy, and license tracking.
- Document truth-labeling, provenance, and licensing policies.

## Phase 1: Chorale Corpus MVP

- Ingest authority metadata from Bach Digital and RISM.
- Register an open chorale seed corpus.
- Normalize seed encodings into event graphs and stable address maps.
- Implement SATB validation, harmonic-event candidates, and cadence detection.
- Export evidence bundles for scholar-mode reporting.

Success criterion:

- analyze a seed chorale set reproducibly with source metadata, passage references, cadence maps, and validator reports.

## Phase 2: Contrapuntal Small Forms

- Add inventions, sinfonias, and selected fugue expositions.
- Implement subject, answer, countersubject, and sequence detectors.
- Add motif search and similarity indexing.

## Phase 3: Composition MVP

- Implement chorale study generation with hard validators.
- Add two-voice invention studies and fugue exposition studies.
- Export labeled artifacts with validation traces.

## Phase 4: Constrained LLM Modes

- Scholar mode.
- Composer mode.
- Pedagogy mode.
- Detective mode.
- AI/ML hypothesis mode.

All five modes should consume the same evidence-bundle schema.

## Phase 5: Source Complexity

- variant comparison;
- edition/source differencing;
- doubtful/spurious support;
- fragment and continuation workflows;
- contextual archival enrichment.

## Deferred

- browser UI;
- autonomous agents;
- heavy ML training infrastructure;
- large-scale text and audio alignment;
- performance-oriented audio workflows.

The determinant of readiness is not how much text the system can generate. It is whether the symbolic, provenance, and validation layers are stable enough that generated text remains bounded by evidence.
