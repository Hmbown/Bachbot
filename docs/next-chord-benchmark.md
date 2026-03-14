# Next-Chord Benchmark

`bachbot benchmark predict-next` evaluates harmonic continuation baselines on the
361-chorale corpus.

## Split

The benchmark uses a deterministic melody-grouped split saved to
`data/manifests/bachbench_split_v2.json`.

- Train: 253 chorales
- Val: 55 chorales
- Test: 53 chorales

Duplicate soprano tunes are grouped by melodic signature before partitioning, so
reused chorale melodies never leak across `train`, `val`, and `test`.

## Commands

Run the dedicated next-chord benchmark:

```bash
python3 -m bachbot benchmark predict-next --all-models \
  --output data/derived/next_chord_benchmark.json
```

Run the BachBench suite on just this task:

```bash
python3 -m bachbot benchmark run --task next-chord \
  --output data/derived/next_chord_suite.json
```

## Baselines

The current baseline set is:

- `unigram`: global next-chord frequency baseline.
- `bigram`: first-order Markov model over Roman-numeral transitions.
- `degree_chord_map`: Bachbot-style melody-conditioned degree-to-chord prior.

`predict-next` reports `top1_accuracy`, `top3_accuracy`, `functional_accuracy`,
and `perplexity`.

## Current Results

Measured on the full `test` split on March 9, 2026:

| Model | Top-1 | Top-3 | Functional | Perplexity |
| --- | ---: | ---: | ---: | ---: |
| `unigram` | 0.1195 | 0.3270 | 0.3648 | 43.7413 |
| `bigram` | 0.2327 | 0.4403 | 0.4025 | 31.2637 |
| `degree_chord_map` | 0.2075 | 0.3333 | 0.3962 | 36.0560 |

The BachBench task runner currently evaluates Bachbot's built-in next-chord
baseline at:

- `top1_accuracy`: `0.4151`
- `top3_accuracy`: `0.7987`
- `functional_accuracy`: `0.5346`
- `composite`: `0.5409`

Those task-level numbers are reproducible from:

```bash
python3 -m bachbot benchmark run --task next-chord
```
