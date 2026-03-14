"""Minimal FastAPI evaluation web interface for blind A/B comparison."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from bachbot.evaluation.models import EvaluationPair, EvaluationRating, EvaluationSession


# ---------------------------------------------------------------------------
# HTML templates (inline, no Jinja2 dependency)
# ---------------------------------------------------------------------------

_STYLE = """
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; }
  h1, h2 { color: #333; }
  .pair-box { border: 1px solid #ccc; border-radius: 8px; padding: 1.5em; margin: 1em 0; }
  .likert { display: flex; gap: 0.4em; align-items: center; margin: 0.4em 0; }
  .likert label { min-width: 3em; text-align: center; }
  table { border-collapse: collapse; width: 100%; }
  td, th { border: 1px solid #ddd; padding: 0.5em 1em; text-align: left; }
  .btn { background: #2563eb; color: white; border: none; padding: 0.7em 2em;
         border-radius: 6px; cursor: pointer; font-size: 1em; }
  .btn:hover { background: #1d4ed8; }
  input[type=text] { padding: 0.5em; width: 300px; }
  textarea { width: 100%; min-height: 80px; }
  .columns { display: flex; gap: 2em; }
  .columns > div { flex: 1; }
  .progress { background: #e5e7eb; border-radius: 4px; height: 24px; margin: 1em 0; }
  .progress-bar { background: #2563eb; border-radius: 4px; height: 100%;
                  display: flex; align-items: center; justify-content: center;
                  color: white; font-size: 0.85em; min-width: 2em; }
</style>
"""


def _landing_page(pair_count: int) -> str:
    return f"""<!DOCTYPE html><html><head><title>Bachbot Evaluation</title>{_STYLE}</head><body>
<h1>Bachbot Human Evaluation</h1>
<p>You will listen to {pair_count} pairs of chorales and rate each on three dimensions
(musicality, authenticity, voice-leading) using a 7-point scale. For each pair you will
also try to identify which chorale is the original Bach composition.</p>
<form method="get" action="/start">
  <label for="evaluator_id"><strong>Evaluator ID:</strong></label><br>
  <input type="text" id="evaluator_id" name="evaluator_id" required placeholder="e.g. your initials"><br><br>
  <button class="btn" type="submit">Start Evaluation</button>
</form>
</body></html>"""


def _likert_row(name: str, label: str) -> str:
    radios = "".join(
        f'<label><input type="radio" name="{name}" value="{i}" required> {i}</label>'
        for i in range(1, 8)
    )
    return f'<div class="likert"><strong>{label}:</strong> {radios}</div>'


def _evaluate_page(pair: EvaluationPair, evaluator_id: str, index: int, total: int) -> str:
    return f"""<!DOCTYPE html><html><head><title>Pair {index}/{total}</title>{_STYLE}</head><body>
<h1>Pair {index} of {total}</h1>
<p>Evaluator: <strong>{evaluator_id}</strong></p>
<form method="post" action="/evaluate/{pair.pair_id}">
<input type="hidden" name="evaluator_id" value="{evaluator_id}">
<div class="columns">
<div class="pair-box">
  <h2>Chorale A</h2>
  <audio controls><source src="/midi/{pair.pair_id}_a.mid" type="audio/midi"></audio>
  <p><a href="/midi/{pair.pair_id}_a.mid" download>Download MIDI A</a></p>
  {_likert_row("musicality_a", "Musicality (1=poor, 7=excellent)")}
  {_likert_row("authenticity_a", "Authenticity / Bach-likeness")}
  {_likert_row("voice_leading_a", "Voice-leading quality")}
</div>
<div class="pair-box">
  <h2>Chorale B</h2>
  <audio controls><source src="/midi/{pair.pair_id}_b.mid" type="audio/midi"></audio>
  <p><a href="/midi/{pair.pair_id}_b.mid" download>Download MIDI B</a></p>
  {_likert_row("musicality_b", "Musicality (1=poor, 7=excellent)")}
  {_likert_row("authenticity_b", "Authenticity / Bach-likeness")}
  {_likert_row("voice_leading_b", "Voice-leading quality")}
</div>
</div>
<h3>Which is the original Bach chorale?</h3>
<div class="likert">
  <label><input type="radio" name="identified_original" value="a" required> A</label>
  <label><input type="radio" name="identified_original" value="b"> B</label>
  <label><input type="radio" name="identified_original" value="unsure"> Unsure</label>
</div>
<h3>Notes (optional)</h3>
<textarea name="notes" placeholder="Any observations about these chorales..."></textarea><br><br>
<button class="btn" type="submit">Submit &amp; Next</button>
</form>
</body></html>"""


def _progress_page(rated: int, total: int, evaluator_id: str) -> str:
    pct = round(100 * rated / total) if total > 0 else 0
    status = "Complete!" if rated >= total else "In progress"
    return f"""<!DOCTYPE html><html><head><title>Progress</title>{_STYLE}</head><body>
<h1>Evaluation Progress</h1>
<p>Evaluator: <strong>{evaluator_id}</strong> | Status: {status}</p>
<div class="progress"><div class="progress-bar" style="width:{pct}%">{rated}/{total}</div></div>
<p>{rated} of {total} pairs rated ({pct}%).</p>
{"<p><strong>Thank you for completing the evaluation!</strong></p>" if rated >= total else
 f'<p><a href="/evaluate/next?evaluator_id={evaluator_id}">Continue evaluation</a></p>'}
<p><a href="/">Back to start</a></p>
</body></html>"""


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_evaluation_app(session_dir: Path) -> FastAPI:
    """Create the evaluation web app.

    The ``session_dir`` must contain a ``session.json`` file produced by
    ``bachbot evaluate setup``.
    """
    app = FastAPI(title="Bachbot Evaluation", docs_url=None, redoc_url=None)

    session_path = session_dir / "session.json"
    ratings_dir = session_dir / "ratings"
    ratings_dir.mkdir(parents=True, exist_ok=True)

    def _load_session() -> EvaluationSession:
        return EvaluationSession.model_validate_json(session_path.read_text(encoding="utf-8"))

    def _rated_pair_ids(evaluator_id: str) -> set[str]:
        ids: set[str] = set()
        for path in ratings_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("evaluator_id") == evaluator_id:
                    ids.add(data["pair_id"])
            except (json.JSONDecodeError, KeyError):
                continue
        return ids

    @app.get("/", response_class=HTMLResponse)
    def landing() -> str:
        session = _load_session()
        return _landing_page(len(session.pairs))

    @app.get("/start", response_class=HTMLResponse)
    def start(evaluator_id: str = "") -> HTMLResponse:
        if not evaluator_id.strip():
            return HTMLResponse(_landing_page(_load_session().pairs.__len__()), status_code=400)
        return HTMLResponse(
            status_code=303,
            headers={"Location": f"/evaluate/next?evaluator_id={evaluator_id.strip()}"},
        )

    @app.get("/evaluate/next")
    def next_pair(evaluator_id: str = "") -> RedirectResponse:
        session = _load_session()
        rated = _rated_pair_ids(evaluator_id)
        for i, pair in enumerate(session.pairs):
            if pair.pair_id not in rated:
                return RedirectResponse(
                    f"/evaluate/{pair.pair_id}?evaluator_id={evaluator_id}&index={i + 1}",
                    status_code=303,
                )
        return RedirectResponse(f"/progress?evaluator_id={evaluator_id}", status_code=303)

    @app.get("/evaluate/{pair_id}", response_class=HTMLResponse)
    def evaluate_pair(pair_id: str, evaluator_id: str = "", index: int = 1) -> str:
        session = _load_session()
        pair = next((p for p in session.pairs if p.pair_id == pair_id), None)
        if pair is None:
            raise HTTPException(status_code=404, detail=f"Unknown pair: {pair_id}")
        return _evaluate_page(pair, evaluator_id, index, len(session.pairs))

    @app.post("/evaluate/{pair_id}")
    def submit_rating(
        pair_id: str,
        evaluator_id: str = Form(...),
        musicality_a: int = Form(...),
        musicality_b: int = Form(...),
        authenticity_a: int = Form(...),
        authenticity_b: int = Form(...),
        voice_leading_a: int = Form(...),
        voice_leading_b: int = Form(...),
        identified_original: str = Form(...),
        notes: str = Form(""),
    ) -> RedirectResponse:
        rating = EvaluationRating(
            pair_id=pair_id,
            evaluator_id=evaluator_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            musicality_a=musicality_a,
            musicality_b=musicality_b,
            authenticity_a=authenticity_a,
            authenticity_b=authenticity_b,
            voice_leading_a=voice_leading_a,
            voice_leading_b=voice_leading_b,
            identified_original=identified_original,
            notes=notes,
        )
        rating_path = ratings_dir / f"{evaluator_id}_{pair_id}.json"
        rating_path.write_text(rating.model_dump_json(indent=2), encoding="utf-8")
        return RedirectResponse(f"/evaluate/next?evaluator_id={evaluator_id}", status_code=303)

    @app.get("/progress", response_class=HTMLResponse)
    def progress(evaluator_id: str = "") -> str:
        session = _load_session()
        rated = _rated_pair_ids(evaluator_id)
        return _progress_page(len(rated), len(session.pairs), evaluator_id)

    @app.get("/midi/{filename}")
    def serve_midi(filename: str) -> FileResponse:
        midi_path = session_dir / "midi" / filename
        if not midi_path.exists():
            raise HTTPException(status_code=404, detail=f"MIDI file not found: {filename}")
        return FileResponse(midi_path, media_type="audio/midi")

    return app
