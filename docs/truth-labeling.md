# Truth Labeling

## Purpose

BACHBOT distinguishes between what is directly supported by sources or deterministic extraction and what is interpretive. That distinction is not cosmetic. It is necessary for scholarly honesty, reproducibility, and safe LLM use.

## Required Labels

Every nontrivial statement should be tagged as one of:

- `supported_fact`
- `inference`
- `speculation`
- `disputed` when preserved as a conflicting claim state

## Definitions

### `supported_fact`

A claim is a `supported_fact` when it is directly grounded in:

- source metadata from an authority dataset;
- stable catalog data with revision context;
- deterministic symbolic extraction;
- explicit validator or detector output tied to a method and passage.

Examples:

- A work page is linked to a specific Bach Digital persistent identifier.
- A passage contains no detected parallel fifths under the current rule set.
- A cadence candidate at measures 11 to 12 has a score of `0.74` under the cadence detector.

### `inference`

A claim is an `inference` when it interprets supported evidence without claiming final truth.

Examples:

- A cadence is plausibly best heard as `PAC` rather than `IAC`.
- A subject answer is more likely tonal than real.
- A passage seems designed to intensify phrase closure by registral compression.

Inferences must cite the evidence that motivated them and preserve uncertainty when alternatives remain viable.

### `speculation`

A claim is `speculation` when it proposes a hypothesis, research lead, or compositional rationale that is not yet established.

Examples:

- A source variant may reflect a later pedagogical adaptation.
- A recurring bass schema may be a productive feature for a new symbolic-learning baseline.
- A fragment continuation branch may align better with one stylistic bucket than another.

Speculation is allowed, but it must be labeled and never promoted to supported fact by prose alone.

### `disputed`

`disputed` is useful when the system stores materially incompatible interpretations side by side.

Examples:

- two Roman-numeral readings with different local-key assumptions;
- conflicting authenticity assignments across catalog revisions;
- competing phrase-boundary analyses.

## LLM Guardrail Rules

The language model must:

- use only supplied evidence bundles;
- preserve truth labels through summaries and explanations;
- explicitly mark unresolved ambiguity;
- avoid inventing dates, sources, editorial claims, or score events;
- end reports with what is certain, what is interpretive, and what further checks matter.

## Report Structure

Analytical reports should conclude with:

1. What the evidence strongly supports.
2. What remains interpretive.
3. What further source or score checks would sharpen the claim.

This is the simplest discipline that prevents analytical overclaiming and “music-theory fanfic.”
