# Complexity Metrics

`bachbot.benchmark.complexity.compute_complexity(graph)` computes a
`ComplexityProfile` with information-theoretic and tonal metrics for a chorale.

## Scalar Metrics

- `harmonic_entropy`: Shannon entropy of the graph's harmonic-event labels
- `melodic_information_content`: average smoothed bigram surprisal of the
  soprano (or fallback melodic) pitch-class sequence
- `voice_leading_mutual_information`: mean pairwise mutual information across
  adjacent SATB voice pairs at shared onsets
- `pitch_lz_complexity`: Lempel-Ziv phrase ratio over the pitch-class sequence
- `rhythm_lz_complexity`: Lempel-Ziv phrase ratio over note durations
- `average_tonal_tension`: average circle-of-fifths distance from the tonic
- `peak_tonal_tension`: maximum value on the tonal-tension curve

## Time Series

`tonal_tension_curve` is exported as a list of `{onset, measure_number, tension}`
points so it can be visualized directly.

## Corpus Statistics

Compute corpus-wide mean/std summaries for the normalized chorale corpus:

```bash
python3 -m bachbot benchmark complexity --output data/derived/complexity_corpus_stats.json
```

The composition benchmark consumes the same corpus statistics and records
`complexity_divergence` between generated and original chorales in
`data/derived/benchmark_results.json`.
