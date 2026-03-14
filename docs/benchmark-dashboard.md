# Benchmark Dashboard

`bachbot benchmark run` now persists a timestamped benchmark snapshot under
`data/derived/benchmarks/` and refreshes a static dashboard at
`data/derived/benchmarks/index.html`.

## Commands

Run the composition benchmark and persist history:

```bash
python3 -m bachbot benchmark run --sample 20
```

Render the dashboard from existing history:

```bash
python3 -m bachbot benchmark dashboard
```

Check a benchmark snapshot against a baseline and fail on regression:

```bash
python3 -m bachbot benchmark check-regressions \
  --current data/derived/benchmarks/latest.json \
  --baseline /tmp/main-latest.json
```

## Snapshot Schema

Each persisted snapshot is JSON with:

- `schema_version`
- `metadata.generated_at`
- `metadata.git_commit`
- `metadata.sample_size`
- `metadata.source_output`
- `summary.*` for tracked metrics

`latest.json` always mirrors the newest persisted snapshot so CI and local tools
have a stable comparison target.

## Tracked Metrics

The dashboard charts these benchmark summary metrics over time:

- `evidence_avg_pass_rate` and `baseline_avg_pass_rate`
- `evidence_avg_chord_variety`, `baseline_avg_chord_variety`,
  `original_avg_chord_variety`
- `evidence_avg_parallel_violations`, `baseline_avg_parallel_violations`
- `evidence_avg_voice_leading_score`, `baseline_avg_voice_leading_score`
- `evidence_avg_pitch_class_entropy`, `baseline_avg_pitch_class_entropy`,
  `original_avg_pitch_class_entropy`
- `evidence_avg_harmonic_similarity`, `baseline_avg_harmonic_similarity`

These are derived from the same composition benchmark run already used in the
repo, so the dashboard reflects existing workflow outputs instead of inventing a
second reporting path.

## Regression Thresholds

CI flags regressions when the current snapshot is worse than the baseline by at
least the configured threshold:

- Evidence pass rate drops by `0.03`
- Evidence chord variety drops by `0.5`
- Evidence parallel violations increase by `0.5`
- Evidence voice-leading score drops by `0.03`
- Evidence harmonic similarity drops by `0.03`

Those thresholds live in `bachbot/benchmark/dashboard.py` so the dashboard and
CI comparison use the same definitions.
