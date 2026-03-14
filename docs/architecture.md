# Architecture

## System View

BACHBOT is a layered research system:

1. Deterministic core.
2. Evidence bundle layer.
3. Constrained LLM interpretation layer.
4. Composition and hypothesis workflows.
5. Evaluation, export, and long-horizon platform surfaces.

The ordering matters. The system should be useful even if the LLM layer is disabled.

## Layer 1: Deterministic Core

The deterministic core owns:

- corpus registration and manifests;
- source, edition, and catalog metadata;
- file checksums and license tracking;
- parsing and normalization of symbolic encodings;
- stable measure, beat, staff, and voice addressing;
- feature extraction;
- rule-based detectors for voice-leading, harmony, cadence, motifs, fugue entries, and chorale-specific checks;
- search and retrieval indexes;
- validation and export.

The canonical internal target is an event graph plus address maps, not raw MusicXML.

## Layer 2: Evidence Bundles

The evidence bundle is the contract between symbolic computation and language generation.

Each bundle should include:

- work and section identifiers;
- catalog status and revision context;
- passage references with measure and voice ranges;
- deterministic findings and confidence values;
- competing interpretations where relevant;
- provenance and method records;
- uncertainty statements;
- citation-ready payloads for reporting.

Nothing should pass to the LLM without first being reduced to this structured form.

## Layer 3: Constrained LLM Layer

The LLM layer may:

- explain evidence;
- compare analytical lenses;
- summarize findings for different audiences;
- draft falsifiable research hypotheses;
- compare composition candidates and explain validator results.

The LLM layer may not:

- invent score events;
- invent provenance or source claims;
- collapse ambiguity that the deterministic layer preserved;
- treat its own prose as evidence.

## Layer 4: Composition and Research Workflows

Composition workflows are constraint-first and validator-heavy. Research workflows are scan-first and hypothesis-driven.

Composition modules should:

- define a style bucket and scope;
- extract relevant priors from corpus summaries;
- generate macro scaffolds before surface detail;
- pass outputs through hard validators and soft evaluators;
- label every artifact truthfully.

Research modules should:

- run corpus scans at scale;
- store claims and hypotheses as versioned records;
- preserve contested readings;
- keep explicit falsification plans for promoted hypotheses.

## Layer 5: Platform Surface

`v0.1` should prioritize local Python, CLI, and notebook use.

Later additions may include:

- browser UI;
- APIs;
- batch jobs;
- pedagogical frontends;
- symbolic-audio linkage.

These are downstream of the deterministic foundation, not prerequisites for it.

## Core Entity Graph

The repo should model the following first-class objects:

- `Work`
- `Source`
- `Edition`
- `Section`
- `Voice`
- `MeasureRangeRef`
- `Motif`
- `Cadence`
- `HarmonicEvent`
- `AnalyticalClaim`
- `CompositionArtifact`
- `Hypothesis`
- `EvaluationResult`
- `ProvenanceRecord`

The critical modeling rule is many-to-many provenance. A single work may map to many sources, editions, encodings, analyses, and derived artifacts.

## Corpus Layers

BACHBOT should treat the corpus as five coupled layers:

- Authority and provenance layer.
- Symbolic score layer.
- Annotation layer.
- Contextual layer.
- Derived research layer.

Keeping these layers separate avoids both licensing mistakes and analytical flattening.

## Canonical Internal Representation

Recommended split:

- Semantic computation layer: internal event graph with stable passage addressing.
- Archival notation layer: normalized MEI where possible.
- Interchange layer: MusicXML.
- Analytic audit layer: Humdrum `**kern`.
- Editable working layer: MuseScore plus optional `ms3` extraction outputs.

## CLI Orientation

The initial CLI should favor reproducible, file-oriented commands such as:

- dataset registration and sync;
- normalization to canonical artifacts;
- deterministic analysis by work or section;
- evidence-bundle export;
- labeled composition study generation;
- validation and report export.

Interactive conversation is downstream of reproducible commands, not a substitute for them.
