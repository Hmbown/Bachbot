# Quickstart

This walkthrough assumes you are running from a local checkout of the repository root.

## Install

```bash
python3 -m pip install -e ".[dev]"
python3 -m bachbot --version
```

## Verify the baseline

```bash
pytest -q
```

## Analyze a shipped example chorale

```bash
python3 -m bachbot analyze chorale examples/chorales/simple_chorale.musicxml
```

This prints a deterministic evidence-oriented JSON payload for the example score.

To write the analysis bundle to disk instead:

```bash
python3 -m bachbot analyze chorale \
  examples/chorales/simple_chorale.musicxml \
  --output data/derived/example-analysis.json
```

## Export a report

```bash
python3 -m bachbot export report \
  examples/chorales/simple_chorale.musicxml \
  --output data/derived/example-report.md
```

## Validate a score

```bash
python3 -m bachbot validate score examples/chorales/simple_chorale.musicxml
```

For a detective-oriented summary:

```bash
python3 -m bachbot detective scan \
  examples/chorales/simple_chorale.musicxml \
  --output data/derived/example-detective.json
```

## Prepare an evidence-bounded LLM request

Dry-run is the default, so this prints the exact request payload without making a network call:

```bash
python3 -m bachbot llm run scholar \
  examples/chorales/simple_chorale.musicxml \
  --question "What does the cadence pattern suggest?"
```

To execute against an OpenAI-compatible provider, set credentials and opt in explicitly:

```bash
export BACHBOT_LLM_API_KEY=...
export BACHBOT_LLM_MODEL=gpt-4.1-mini
python3 -m bachbot llm run scholar \
  examples/chorales/simple_chorale.musicxml \
  --question "Summarize only what the bundle strongly supports." \
  --execute \
  --output data/derived/example-llm.json
```

## Generate a labeled chorale study

```bash
python3 -m bachbot compose chorale \
  examples/chorales/simple_cantus.musicxml \
  --output-prefix data/derived/example-chorale
```

This writes:

- `data/derived/example-chorale.musicxml`
- `data/derived/example-chorale.artifact.json`
- `data/derived/example-chorale.report.json`

## Register and process a local corpus

```bash
python3 -m bachbot corpus register data/manifests/dcml_bach_chorales.yaml
python3 -m bachbot corpus sync dcml_bach_chorales --source-root examples/chorales
python3 -m bachbot corpus normalize dcml_bach_chorales
python3 -m bachbot corpus analyze dcml_bach_chorales
```

## Register and process authority datasets

```bash
python3 -m bachbot corpus register data/manifests/bach_digital.yaml
python3 -m bachbot corpus register data/manifests/rism.yaml
python3 -m bachbot corpus sync bach_digital --kind work --record-id 00001262 --include-linked
python3 -m bachbot corpus sync rism --mode sources --record-id 1001145660
python3 -m bachbot corpus normalize bach_digital
python3 -m bachbot corpus analyze bach_digital
```

Notes:

- Bach Digital and RISM sync commands use live network access.
- The test suite uses offline fixtures, but real CLI sync uses the remote endpoints.
- Authority data is intentionally kept separate from `dcml_bach_chorales` normalized and derived score-analysis outputs in the current milestone.
