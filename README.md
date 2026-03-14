# BachBot

**Explore, analyze, and compose in the style of Johann Sebastian Bach.**

BachBot is a full-stack platform for studying Bach's 371 chorales. It performs symbolic music analysis — harmony, counterpoint, cadences, voice-leading — and uses those findings to generate new four-part chorales, figured bass realizations, melodies, and two-part inventions.

**Try it live:** [bachbot-production.up.railway.app](https://bachbot-production.up.railway.app)

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Tests](https://img.shields.io/badge/tests-688%20passing-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## What it does

- **Browse 361 analyzed chorales** — search by key, cadence type, or title. Every chorale has a full harmonic analysis, cadence map, voice-leading report, and evidence bundle.
- **Compose new music** — four-part chorale harmonization from a soprano melody, figured bass realization, melody generation from chord progressions, and two-part invention generation.
- **Counterpoint solver** — all 5 species of counterpoint with 12 built-in cantus firmi. Write your own and get instant rule-checking.
- **Research tools** — style fingerprinting (35 features), corpus-wide anomaly detection, harmonic pattern mining, embedding visualization, and harmonic rhythm analysis.
- **Blind A/B evaluation** — rate generated chorales against Bach originals on musicality, authenticity, and voice-leading. Computes Krippendorff's alpha for inter-rater reliability.
- **MIDI playback** — Tone.js plays any chorale or composition directly in the browser with per-voice controls.
- **Export** — MIDI, MusicXML, and LilyPond for everything.

## Quick start

```bash
# Install
python3 -m pip install -e ".[dev]"

# Run the test suite (688 tests)
pytest -q

# Start the web app locally
python3 -m bachbot serve
# Open http://localhost:8000
```

## CLI examples

```bash
# Analyze a chorale
python3 -m bachbot analyze chorale examples/chorales/simple_chorale.musicxml

# Compose a four-part harmonization from a soprano line
python3 -m bachbot compose chorale examples/chorales/simple_cantus.musicxml

# Validate voice-leading rules
python3 -m bachbot validate score examples/chorales/simple_chorale.musicxml

# Run the composition quality benchmark
python3 -m bachbot benchmark quality --sample 30

# Export an analysis report
python3 -m bachbot export report examples/chorales/simple_chorale.musicxml
```

## How it works

Bach's chorales follow strict rules: soprano-alto spacing under an octave, no parallel fifths, tendency tones resolve, cadences land in the right places. BachBot encodes these rules and uses them both for analysis (finding what Bach did) and composition (generating music that follows the same constraints).

The pipeline:

1. **Parse** — MusicXML, MEI, Humdrum, or DCML TSV files are normalized into an internal event graph with stable measure/voice addressing.
2. **Analyze** — Extract harmony (Roman numerals), cadences, voice-leading, counterpoint, nonharmonic tones, modulations, and form.
3. **Bundle** — Package analytical findings into structured evidence bundles that downstream tools can consume.
4. **Compose** — Generate new music using constraint-based search: 19 chord types, SATB spacing enforcement, cadence targeting, seventh chord upgrades, and exhaustive parallel voicing search.
5. **Validate** — Check generated output against Bach's rules. Report parallel fifths/octaves, range violations, and spacing errors.

## Architecture

```
bachbot/
  analysis/     Harmony, counterpoint, cadence, fugue, form, style
  composition/  Pattern-fill harmonizer, figured bass, melody, invention, counterpoint
  encodings/    MusicXML/MEI/Humdrum parsing, normalization, event graph
  claims/       Evidence bundles — the contract between analysis and everything else
  exports/      MIDI, MusicXML, LilyPond, features, embeddings
  api/          FastAPI backend (38 routes)
  benchmark/    Composition quality benchmarks
  evaluation/   Human A/B evaluation protocol
  connectors/   Bach Digital, RISM, DCML corpus connectors

web/            React + Vite + Tailwind frontend
```

## Requirements

- Python >= 3.11
- Node.js >= 18 (for the frontend)
- No GPU needed — all analysis and composition is symbolic

## License

MIT
