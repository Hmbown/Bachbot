`bachbot.benchmark.quality.evaluate_generation(graph, corpus_stats)` scores a
generated chorale against corpus-wide Bach statistics and returns a
`QualityReport` with a composite `bach_fidelity_score`.

Run the dedicated quality benchmark:

```bash
python3 -m bachbot benchmark quality --sample 30 \
  --output data/derived/quality_benchmark.json
```

The CLI prints a per-chorale evidence-vs-baseline comparison table followed by
aggregate fidelity and divergence summaries. The JSON report stores the same
per-sample comparisons under `results` and aggregate rollups under `summary`.

The report includes these reproducible metric families:

- `chord_kl_divergence`: KL divergence between the generated chord distribution and the normalized Bach corpus chord distribution.
- `cadence_kl_divergence`: KL divergence between generated cadence-type frequencies and corpus cadence frequencies.
- `chord_variety_z`: z-score of unique chord vocabulary size against corpus mean/std.
- `harmonic_rhythm_mean_z`: z-score of mean chord changes per measure.
- `nonharmonic_tone_density_z`: z-score of tagged nonharmonic tones per harmonic event.
- `contrary_motion_ratio_z`: z-score of contrary-motion share across outer-voice motions.
- `parallel_violation_rate`: normalized parallel-fifths/octaves penalty from the hard-rule validator.
- `parallel_violation_rate_z`: z-score of that penalty relative to the corpus.
- Complexity z-scores:
  `harmonic_entropy_z`, `melodic_information_content_z`,
  `voice_leading_mutual_information_z`, `pitch_lz_complexity_z`,
  `rhythm_lz_complexity_z`, `average_tonal_tension_z`,
  `peak_tonal_tension_z`.
- Reference-only metrics used by the benchmark command:
  `harmonic_similarity_to_reference` and
  `complexity_divergence_to_reference`.

`bach_fidelity_score` is a 0-100 aggregate over those penalties and z-scores.
Lower divergences, lower rule violations, and corpus-like complexity profiles
raise the score.

Corpus-wide comparison stats are cached at
`data/derived/quality_corpus_stats.json` so repeated runs stay deterministic and
cheap.
