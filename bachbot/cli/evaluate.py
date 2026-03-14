"""CLI commands for the human evaluation protocol."""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(help="Human evaluation protocol: setup, serve, and analyze blind A/B sessions.")


@app.command("setup")
def setup(
    originals: Path = typer.Option(
        Path("data/derived/dcml_bach_chorales"),
        "--originals",
        help="Directory containing original evidence bundle JSON files.",
    ),
    generated: Path = typer.Option(
        Path("data/derived/compositions"),
        "--generated",
        help="Directory containing generated evidence bundle JSON files.",
    ),
    count: int = typer.Option(50, "--count", help="Number of A/B pairs to generate."),
    seed: int = typer.Option(42, "--seed", help="Random seed for deterministic pair assignment."),
    output: Path = typer.Option(
        Path("eval_session"),
        "--output",
        help="Output directory for the evaluation session.",
    ),
) -> None:
    """Generate randomized A/B evaluation pairs from original and generated chorales."""
    from bachbot.evaluation.models import EvaluationSession
    from bachbot.evaluation.protocol import generate_evaluation_pairs

    original_files = sorted(originals.glob("*.json"))
    generated_files = sorted(generated.glob("*.json"))

    if not original_files:
        typer.echo(f"No JSON files found in {originals}")
        raise typer.Exit(code=1)
    if not generated_files:
        typer.echo(f"No JSON files found in {generated}")
        raise typer.Exit(code=1)

    midi_dir = output / "midi"
    pairs = generate_evaluation_pairs(
        original_files,
        generated_files,
        count=count,
        seed=seed,
        output_dir=midi_dir,
    )

    session = EvaluationSession(
        session_id=f"eval-{seed}",
        evaluator_id="pending",
        pairs=pairs,
    )
    output.mkdir(parents=True, exist_ok=True)
    session_path = output / "session.json"
    session_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    typer.echo(f"Created {len(pairs)} evaluation pairs.")
    typer.echo(f"Session saved to: {session_path}")
    typer.echo(f"MIDI files in: {midi_dir}")


@app.command("serve")
def serve(
    session: Path = typer.Option(
        Path("eval_session"),
        "--session",
        help="Session directory from 'evaluate setup'.",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface."),
    port: int = typer.Option(8080, "--port", min=1, max=65535, help="Port."),
) -> None:
    """Start the evaluation web interface."""
    import uvicorn

    from bachbot.evaluation.server import create_evaluation_app

    session_path = session / "session.json"
    if not session_path.exists():
        typer.echo(f"Session file not found: {session_path}")
        typer.echo("Run 'bachbot evaluate setup' first.")
        raise typer.Exit(code=1)

    evaluation_app = create_evaluation_app(session)
    typer.echo(f"Serving evaluation UI at http://{host}:{port}")
    uvicorn.run(evaluation_app, host=host, port=port)


@app.command("analyze")
def analyze(
    session: Path = typer.Option(
        Path("eval_session"),
        "--session",
        help="Session directory containing session.json and ratings/.",
    ),
) -> None:
    """Analyze collected evaluation ratings and print summary statistics."""
    from bachbot.evaluation.models import EvaluationRating, EvaluationSession
    from bachbot.evaluation.protocol import analyze_evaluation

    session_path = session / "session.json"
    if not session_path.exists():
        typer.echo(f"Session file not found: {session_path}")
        raise typer.Exit(code=1)

    base_session = EvaluationSession.model_validate_json(
        session_path.read_text(encoding="utf-8")
    )

    ratings_dir = session / "ratings"
    ratings: list[EvaluationRating] = []
    if ratings_dir.exists():
        for rating_path in sorted(ratings_dir.glob("*.json")):
            try:
                ratings.append(
                    EvaluationRating.model_validate_json(rating_path.read_text(encoding="utf-8"))
                )
            except Exception as exc:
                typer.echo(f"Warning: skipping {rating_path.name}: {exc}")

    # Build per-evaluator sessions so analyze_evaluation can work
    evaluator_sessions: dict[str, EvaluationSession] = {}
    for r in ratings:
        if r.evaluator_id not in evaluator_sessions:
            evaluator_sessions[r.evaluator_id] = EvaluationSession(
                session_id=f"{base_session.session_id}-{r.evaluator_id}",
                evaluator_id=r.evaluator_id,
                pairs=base_session.pairs,
            )
        evaluator_sessions[r.evaluator_id].ratings.append(r)

    sessions = list(evaluator_sessions.values()) if evaluator_sessions else [base_session]
    summary = analyze_evaluation(sessions)

    typer.echo(f"\n{'='*50}")
    typer.echo("EVALUATION SUMMARY")
    typer.echo(f"{'='*50}")
    typer.echo(f"Total pairs:              {summary.total_pairs}")
    typer.echo(f"Total evaluators:         {summary.total_evaluators}")
    typer.echo(f"Total ratings:            {summary.total_ratings}")
    typer.echo(f"Avg musicality (orig):    {summary.avg_musicality_original:.3f}")
    typer.echo(f"Avg musicality (gen):     {summary.avg_musicality_generated:.3f}")
    typer.echo(f"Avg authenticity (orig):  {summary.avg_authenticity_original:.3f}")
    typer.echo(f"Avg authenticity (gen):   {summary.avg_authenticity_generated:.3f}")
    typer.echo(f"Avg voice-leading (orig): {summary.avg_voice_leading_original:.3f}")
    typer.echo(f"Avg voice-leading (gen):  {summary.avg_voice_leading_generated:.3f}")
    typer.echo(f"Identification accuracy:  {summary.identification_accuracy:.3f}")
    typer.echo(f"Krippendorff alpha:       {summary.krippendorff_alpha:.3f}")

    # Save summary
    summary_path = session / "summary.json"
    summary_path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    typer.echo(f"\nSummary saved to: {summary_path}")
