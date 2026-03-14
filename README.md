# BachBot

**Browse, hear, and study Johann Sebastian Bach's chorales in a digital manuscript.**

BachBot is a full-stack Bach chorale study app built with FastAPI and React. It serves the DCML chorale corpus through a manuscript-style web interface with score views, cadence tables, playback, comparison tools, research panels, encyclopedia essays, and live API docs. The backend also exposes analysis and composition endpoints for symbolic music workflows.

**Try it live:** [bachbot-production.up.railway.app](https://bachbot-production.up.railway.app)

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Tests](https://img.shields.io/badge/tests-pytest-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## What the app includes

- **Home page** — a manuscript-style landing page that points directly to the corpus, research tools, encyclopedia, and API reference.
- **Corpus browser** — browse 361 chorales, search by title or BWV, filter by key, and compare two selections side by side.
- **Chorale detail** — piano-roll and voice-leading views, harmonic overlays, cadence tables, part-writing checks, playback controls, and download buttons.
- **Comparison view** — compare two chorales across score views, cadence layouts, vocabulary overlap, and summary metrics.
- **Research page** — chorale profiles, anomaly ranking, progression mining, embeddings, harmonic rhythm, and edition comparison.
- **Encyclopedia** — short essays and corpus-driven stats about chorales, harmony, voice-leading, fugue craft, and text setting.
- **API docs** — live request/response playground for the FastAPI backend.
- **Backend composition and analysis endpoints** — SATB harmonization, figured bass realization, melody generation, invention generation, counterpoint validation, and score analysis remain available through the API and CLI.

## Quick start

```bash
# Install Python dependencies
python3 -m pip install -e ".[dev]"

# Install frontend dependencies
cd web && npm install && cd ..

# Build the frontend
cd web && npm run build && cd ..

# Run the backend + built frontend together
python3 -m uvicorn bachbot.api.app:app --host 127.0.0.1 --port 8000

# Open http://127.0.0.1:8000
```

## Development checks

```bash
# Frontend build
cd web && npm run build

# Backend tests
python3 -m pytest tests/ -q
```

## Deployment

```bash
# Deploy the current repo to Railway
railway up --detach
```

## CLI examples

```bash
# Analyze a score
python3 -m bachbot analyze chorale examples/chorales/simple_chorale.musicxml

# Harmonize a soprano line
python3 -m bachbot compose chorale examples/chorales/simple_cantus.musicxml

# Validate voice-leading
python3 -m bachbot validate score examples/chorales/simple_chorale.musicxml

# Export a report
python3 -m bachbot export report examples/chorales/simple_chorale.musicxml
```

## How it works

Bach's chorales follow strict constraints: tight upper-voice spacing, careful treatment of parallels, tendency-tone resolution, and cadence control. BachBot models those constraints in analysis pipelines and uses the same symbolic representations for exports and generative endpoints.

The pipeline:

1. **Parse** — MusicXML, MEI, Humdrum, or DCML TSV inputs are normalized into an internal event graph with stable measure and voice references.
2. **Analyze** — Harmony, cadence, voice-leading, modulation, rhythm, and validation layers are computed from the symbolic score.
3. **Bundle** — Findings are exposed through structured API responses and evidence bundles.
4. **Render** — The React frontend turns those results into score views, overlays, tables, comparison panels, and research visualizations.
5. **Export / Compose** — The same graph model also supports exports and composition endpoints.

## Architecture

```
bachbot/
  analysis/     Harmony, counterpoint, cadence, fugue, form, style
  composition/  Pattern-fill harmonizer, figured bass, melody, invention, counterpoint
  encodings/    MusicXML/MEI/Humdrum parsing, normalization, event graph
  claims/       Evidence bundles — the contract between analysis and everything else
  exports/      MIDI, MusicXML, LilyPond, features, embeddings
  api/          FastAPI backend
  benchmark/    Composition quality benchmarks
  connectors/   Bach Digital, RISM, DCML corpus connectors

web/            React + Vite + Tailwind frontend
```

## Requirements

- Python >= 3.11
- Node.js >= 18 (for the frontend)
- No GPU needed — all analysis and composition is symbolic

## License

MIT
