# Provenance Policy

## Principle

In BACHBOT, provenance is part of the musical object. A score artifact is never just “the piece.” It exists in relation to sources, copies, editions, encodings, parser pipelines, human corrections, and analytic derivations.

## Provenance Requirements

Each imported or derived asset should record:

- dataset or source identifier;
- retrieval timestamp;
- upstream URL or persistent identifier;
- file checksum;
- declared license;
- source type such as autograph, copy, printed edition, modern encoding, or machine conversion;
- parser or converter used;
- normalization steps applied;
- human corrections applied;
- confidence or trust notes.

## Provenance Subjects

The provenance layer should be attachable to:

- works;
- sources;
- editions;
- encodings;
- normalized event graphs;
- derived features;
- analytical claims;
- generated artifacts;
- evaluation runs.

## Transformation Lineage

Every transformation should produce a provenance record with:

- subject type and subject id;
- action name;
- tool name and version;
- operator or workflow id;
- input checksums;
- output checksums;
- effective license snapshot;
- notes on assumptions or repairs.

This keeps both deterministic and human-in-the-loop interventions auditable.

## Catalog Revision Discipline

Catalog data is not frozen. Work and status records should preserve:

- catalog scheme;
- catalog value;
- catalog revision;
- date of understanding or retrieval;
- authority source.

This matters because authenticity and work identity may shift across later scholarship or addenda.

## Addressability Rule

Every analytical claim should resolve back to:

- work id;
- section id where relevant;
- measure range;
- voice or staff scope where available;
- method identifier;
- source or encoding context if the claim is edition-sensitive.

If a claim cannot be addressed to a passage and method, it should not be stored as a strong analytical result.

## Human Corrections

Human fixes are expected, especially for converted symbolic files. Corrections should never silently overwrite uncertainty. Each fix should preserve:

- the original asset reference;
- the corrected derivative reference;
- a reason;
- who applied the change;
- when it was applied.

## Output Discipline

Reports, exported evidence bundles, and generated artifacts should surface enough provenance for later audit without forcing users to inspect internal storage manually.
