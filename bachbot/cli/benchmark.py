"""Benchmark evaluation: compare evidence-driven vs baseline compositions."""

from __future__ import annotations

import glob
import json
import os
from collections import Counter
from pathlib import Path

import typer

from bachbot.analysis.chorale.satb import analyze_chorale_texture
from bachbot.benchmark.complexity import (
    DEFAULT_COMPLEXITY_STATS_PATH,
    compare_profile_to_corpus,
    complexity_divergence,
    compute_complexity,
    load_or_compute_corpus_stats,
)
from bachbot.benchmark.dashboard import (
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_HISTORY_DIR,
    build_report_metadata,
    compare_benchmark_runs,
    load_benchmark_history,
    load_snapshot,
    persist_benchmark_history,
    render_dashboard,
)
from bachbot.benchmark.metrics import harmonic_similarity, pitch_class_entropy, voice_leading_score
from bachbot.benchmark.next_chord_eval import PREDICTORS, run_next_chord_benchmark
from bachbot.benchmark.quality import (
    DEFAULT_QUALITY_STATS_PATH,
    evaluate_generation,
    load_or_compute_quality_corpus_stats,
)
from bachbot.benchmark.runner import _load_corpus
from bachbot.composition import compose_chorale_study
from bachbot.composition.validators.hard_rules import validate_graph
from bachbot.encodings import Normalizer

app = typer.Typer(help="Benchmark composition quality against original evidence.")


def _chord_distribution(trace: list[str]) -> Counter:
    return Counter(
        line.rsplit(": ", 1)[-1]
        for line in trace
        if line.startswith("m") and ": " in line
    )


def _count_issues(validation) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in validation.issues:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    return counts


def _normalize_task_name(name: str) -> str:
    return name.strip().replace("-", "_")


def _parallel_violations(texture: dict) -> int:
    counterpoint = texture.get("counterpoint", {})
    return int(counterpoint.get("parallel_5ths", 0)) + int(counterpoint.get("parallel_8ves", 0))


def _format_quality_table(results: list[dict]) -> list[str]:
    headers = (
        "Chorale",
        "Ev score",
        "Bl score",
        "Ev chord KL",
        "Bl chord KL",
        "Ev cadence KL",
        "Bl cadence KL",
        "Better",
    )
    rows = [headers]
    for result in results:
        evidence = result["evidence"]
        baseline = result["baseline"]
        evidence_metrics = evidence["metrics"]
        baseline_metrics = baseline["metrics"]
        better = "tie"
        if evidence["bach_fidelity_score"] > baseline["bach_fidelity_score"]:
            better = "evidence"
        elif evidence["bach_fidelity_score"] < baseline["bach_fidelity_score"]:
            better = "baseline"
        rows.append(
            (
                result["name"],
                f"{evidence['bach_fidelity_score']:.2f}",
                f"{baseline['bach_fidelity_score']:.2f}",
                f"{evidence_metrics['chord_kl_divergence']:.4f}",
                f"{baseline_metrics['chord_kl_divergence']:.4f}",
                f"{evidence_metrics['cadence_kl_divergence']:.4f}",
                f"{baseline_metrics['cadence_kl_divergence']:.4f}",
                better,
            )
        )

    widths = [max(len(row[idx]) for row in rows) for idx in range(len(headers))]

    def render(row: tuple[str, ...]) -> str:
        return "  ".join(value.ljust(width) for value, width in zip(row, widths, strict=False))

    separator = "  ".join("-" * width for width in widths)
    return [render(headers), separator, *(render(row) for row in rows[1:])]


def _evaluate_single(raw_path: str, bundle_path: str, corpus_stats=None) -> dict:
    """Evaluate a single chorale: evidence vs baseline composition."""
    normalizer = Normalizer()
    graph = normalizer.normalize(Path(raw_path))
    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))

    # Evidence-driven composition
    ev_graph, _, ev_report = compose_chorale_study(graph, bundle=bundle)
    ev_validation = validate_graph(ev_graph)
    ev_chords = _chord_distribution(ev_report["trace"])
    ev_texture = analyze_chorale_texture(ev_graph)

    # Baseline composition (no evidence)
    bl_graph, _, bl_report = compose_chorale_study(graph, bundle=None)
    bl_validation = validate_graph(bl_graph)
    bl_chords = _chord_distribution(bl_report["trace"])
    bl_texture = analyze_chorale_texture(bl_graph)

    # Extract original analysis chord distribution from bundle
    orig_chords: Counter = Counter()
    for h in bundle.get("deterministic_findings", {}).get("harmony", []):
        candidates = h.get("roman_numeral_candidate_set", [])
        if candidates:
            orig_chords[candidates[0]] += 1

    # Chord variety: number of distinct chords used
    ev_variety = len(ev_chords)
    bl_variety = len(bl_chords)
    orig_variety = len(orig_chords)

    # Cadence count from evidence trace
    ev_cadences = sum(1 for l in ev_report["trace"] if "cadence:" in l and "→" in l)
    bl_cadences = 0  # baseline has no cadence plan
    ev_voice_leading = voice_leading_score(ev_graph)
    bl_voice_leading = voice_leading_score(bl_graph)
    ev_harmonic_similarity = harmonic_similarity(ev_graph, graph)
    bl_harmonic_similarity = harmonic_similarity(bl_graph, graph)
    ev_entropy = pitch_class_entropy(ev_graph)
    bl_entropy = pitch_class_entropy(bl_graph)
    orig_entropy = pitch_class_entropy(graph)
    original_complexity = compute_complexity(graph)
    evidence_complexity = compute_complexity(ev_graph)
    baseline_complexity = compute_complexity(bl_graph)
    evidence_complexity_comparison = (
        compare_profile_to_corpus(evidence_complexity, corpus_stats).model_dump(mode="json")
        if corpus_stats is not None
        else {"z_scores": {}, "divergence": 0.0}
    )
    baseline_complexity_comparison = (
        compare_profile_to_corpus(baseline_complexity, corpus_stats).model_dump(mode="json")
        if corpus_stats is not None
        else {"z_scores": {}, "divergence": 0.0}
    )
    evidence_complexity_divergence = (
        complexity_divergence(evidence_complexity, original_complexity, corpus_stats=corpus_stats)
        if corpus_stats is not None
        else 0.0
    )
    baseline_complexity_divergence = (
        complexity_divergence(baseline_complexity, original_complexity, corpus_stats=corpus_stats)
        if corpus_stats is not None
        else 0.0
    )

    return {
        "name": os.path.basename(raw_path),
        "evidence": {
            "passed": ev_validation.passed,
            "issues": _count_issues(ev_validation),
            "chords": dict(ev_chords.most_common()),
            "variety": ev_variety,
            "cadences": ev_cadences,
            "parallel_violations": _parallel_violations(ev_texture),
            "voice_leading_score": round(ev_voice_leading, 4),
            "harmonic_similarity": round(ev_harmonic_similarity, 4),
            "pitch_class_entropy": round(ev_entropy, 4),
            "complexity_profile": evidence_complexity.model_dump(mode="json"),
            "complexity_comparison": evidence_complexity_comparison,
            "complexity_divergence": evidence_complexity_divergence,
            "total_notes": sum(ev_chords.values()),
        },
        "baseline": {
            "passed": bl_validation.passed,
            "issues": _count_issues(bl_validation),
            "chords": dict(bl_chords.most_common()),
            "variety": bl_variety,
            "parallel_violations": _parallel_violations(bl_texture),
            "voice_leading_score": round(bl_voice_leading, 4),
            "harmonic_similarity": round(bl_harmonic_similarity, 4),
            "pitch_class_entropy": round(bl_entropy, 4),
            "complexity_profile": baseline_complexity.model_dump(mode="json"),
            "complexity_comparison": baseline_complexity_comparison,
            "complexity_divergence": baseline_complexity_divergence,
            "total_notes": sum(bl_chords.values()),
        },
        "original": {
            "chords": dict(orig_chords.most_common(10)),
            "variety": orig_variety,
            "pitch_class_entropy": round(orig_entropy, 4),
            "complexity_profile": original_complexity.model_dump(mode="json"),
        },
    }


def _evaluate_quality_single(raw_path: str, bundle_path: str, quality_stats) -> dict:
    """Evaluate one chorale with the quality-report API."""
    normalizer = Normalizer()
    graph = normalizer.normalize(Path(raw_path))
    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))

    evidence_graph, _, _ = compose_chorale_study(graph, bundle=bundle)
    baseline_graph, _, _ = compose_chorale_study(graph, bundle=None)

    evidence_report = evaluate_generation(
        evidence_graph,
        quality_stats,
        reference_graph=graph,
    )
    baseline_report = evaluate_generation(
        baseline_graph,
        quality_stats,
        reference_graph=graph,
    )

    return {
        "name": os.path.basename(raw_path),
        "evidence": evidence_report.model_dump(mode="json"),
        "baseline": baseline_report.model_dump(mode="json"),
    }


@app.command("run")
def run_benchmark(
    sample_size: int = typer.Option(20, "--sample", help="Number of chorales to evaluate."),
    output: Path = typer.Option(
        Path("data/derived/benchmark_results.json"),
        "--output",
        help="Path to write benchmark results JSON.",
    ),
    history_dir: Path = typer.Option(
        DEFAULT_HISTORY_DIR,
        "--history-dir",
        help="Directory to persist benchmark history snapshots.",
    ),
    dashboard_output: Path = typer.Option(
        DEFAULT_DASHBOARD_PATH,
        "--dashboard-output",
        help="Path to write the static benchmark dashboard.",
    ),
    suite: str = typer.Option("", "--suite", help="Run BachBench suite (e.g., 'bachbench')."),
    task: str = typer.Option("", "--task", help="Single BachBench task alias, e.g. next-chord."),
    tasks: str = typer.Option("", "--tasks", help="Comma-separated task names for --suite."),
    split: str = typer.Option("test", "--split", help="Split mode: test, val, train, or full."),
) -> None:
    """Run composition benchmark on a sample of chorales."""
    task_list = [_normalize_task_name(task)] if task.strip() else []
    task_list.extend(_normalize_task_name(t) for t in tasks.split(",") if t.strip())
    if suite == "bachbench" or task_list:
        from bachbot.benchmark.leaderboard import print_leaderboard
        from bachbot.benchmark.runner import run_suite

        result = run_suite(
            tasks=task_list or None,
            split=split,
            sample=sample_size if sample_size != 20 else None,
            output=output,
        )
        typer.echo(print_leaderboard(result))
        typer.echo(f"\nResults saved to: {output}")
        return

    bundles = sorted(glob.glob("data/derived/dcml_bach_chorales/*.evidence_bundle.json"))
    raw_notes = sorted(glob.glob("data/raw/dcml_bach_chorales/notes/*.notes.tsv"))

    def stem(p: str) -> str:
        base = os.path.basename(p)
        if base.startswith("notes__"):
            return base.replace("notes__", "").replace(".evidence_bundle.json", "")
        return base.replace(".notes.tsv", "")

    bundle_map = {stem(b): b for b in bundles}
    pairs = [(r, bundle_map[stem(r)]) for r in raw_notes if stem(r) in bundle_map]
    corpus_graphs, _ = _load_corpus()
    corpus_stats = load_or_compute_corpus_stats(
        corpus_graphs,
        output=DEFAULT_COMPLEXITY_STATS_PATH,
    )

    # Sample evenly across the corpus
    step = max(1, len(pairs) // sample_size)
    sample = pairs[::step][:sample_size]

    results = []
    ev_pass = bl_pass = 0
    ev_variety_sum = bl_variety_sum = orig_variety_sum = 0.0
    ev_cadence_sum = 0
    ev_parallel_sum = bl_parallel_sum = 0.0
    ev_voice_leading_sum = bl_voice_leading_sum = 0.0
    ev_harmonic_similarity_sum = bl_harmonic_similarity_sum = 0.0
    ev_entropy_sum = bl_entropy_sum = orig_entropy_sum = 0.0
    ev_complexity_divergence_sum = bl_complexity_divergence_sum = 0.0

    for i, (raw, bundle) in enumerate(sample):
        typer.echo(f"[{i + 1}/{len(sample)}] {os.path.basename(raw)}")
        try:
            result = _evaluate_single(raw, bundle, corpus_stats=corpus_stats)
            results.append(result)
            if result["evidence"]["passed"]:
                ev_pass += 1
            if result["baseline"]["passed"]:
                bl_pass += 1
            ev_variety_sum += result["evidence"]["variety"]
            bl_variety_sum += result["baseline"]["variety"]
            orig_variety_sum += result["original"]["variety"]
            ev_cadence_sum += result["evidence"]["cadences"]
            ev_parallel_sum += result["evidence"]["parallel_violations"]
            bl_parallel_sum += result["baseline"]["parallel_violations"]
            ev_voice_leading_sum += result["evidence"]["voice_leading_score"]
            bl_voice_leading_sum += result["baseline"]["voice_leading_score"]
            ev_harmonic_similarity_sum += result["evidence"]["harmonic_similarity"]
            bl_harmonic_similarity_sum += result["baseline"]["harmonic_similarity"]
            ev_entropy_sum += result["evidence"]["pitch_class_entropy"]
            bl_entropy_sum += result["baseline"]["pitch_class_entropy"]
            orig_entropy_sum += result["original"]["pitch_class_entropy"]
            ev_complexity_divergence_sum += result["evidence"]["complexity_divergence"]
            bl_complexity_divergence_sum += result["baseline"]["complexity_divergence"]
        except Exception as e:
            typer.echo(f"  ERROR: {e}")

    n = len(results)
    if n == 0:
        typer.echo("No results.")
        return

    summary = {
        "sample_size": n,
        "evidence_avg_pass_rate": round(ev_pass / n, 3),
        "baseline_avg_pass_rate": round(bl_pass / n, 3),
        "evidence_avg_chord_variety": round(ev_variety_sum / n, 1),
        "baseline_avg_chord_variety": round(bl_variety_sum / n, 1),
        "original_avg_chord_variety": round(orig_variety_sum / n, 1),
        "evidence_avg_cadences": round(ev_cadence_sum / n, 1),
        "evidence_avg_parallel_violations": round(ev_parallel_sum / n, 2),
        "baseline_avg_parallel_violations": round(bl_parallel_sum / n, 2),
        "evidence_avg_voice_leading_score": round(ev_voice_leading_sum / n, 4),
        "baseline_avg_voice_leading_score": round(bl_voice_leading_sum / n, 4),
        "evidence_avg_harmonic_similarity": round(ev_harmonic_similarity_sum / n, 4),
        "baseline_avg_harmonic_similarity": round(bl_harmonic_similarity_sum / n, 4),
        "evidence_avg_pitch_class_entropy": round(ev_entropy_sum / n, 4),
        "baseline_avg_pitch_class_entropy": round(bl_entropy_sum / n, 4),
        "original_avg_pitch_class_entropy": round(orig_entropy_sum / n, 4),
        "evidence_avg_complexity_divergence": round(ev_complexity_divergence_sum / n, 4),
        "baseline_avg_complexity_divergence": round(bl_complexity_divergence_sum / n, 4),
    }

    # Aggregate issue counts
    ev_issue_agg: Counter = Counter()
    bl_issue_agg: Counter = Counter()
    for r in results:
        for code, cnt in r["evidence"]["issues"].items():
            ev_issue_agg[code] += cnt
        for code, cnt in r["baseline"]["issues"].items():
            bl_issue_agg[code] += cnt

    summary["evidence_issues"] = dict(ev_issue_agg.most_common())
    summary["baseline_issues"] = dict(bl_issue_agg.most_common())

    report = {
        "metadata": build_report_metadata(sample_size=n, output=output),
        "summary": summary,
        "results": results,
        "complexity_corpus_stats": corpus_stats.model_dump(mode="json"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    snapshot_path = persist_benchmark_history(report, history_dir=history_dir)
    dashboard_path = render_dashboard(
        load_benchmark_history(history_dir),
        output=dashboard_output,
    )

    typer.echo(f"\n{'='*60}")
    typer.echo("BENCHMARK RESULTS")
    typer.echo(f"{'='*60}")
    typer.echo(f"Sample size:          {n}")
    typer.echo(f"Validation pass rate: evidence={summary['evidence_avg_pass_rate']:.0%}  baseline={summary['baseline_avg_pass_rate']:.0%}")
    typer.echo(f"Avg chord variety:    evidence={summary['evidence_avg_chord_variety']}  baseline={summary['baseline_avg_chord_variety']}  original={summary['original_avg_chord_variety']}")
    typer.echo(f"Avg parallel issues:  evidence={summary['evidence_avg_parallel_violations']}  baseline={summary['baseline_avg_parallel_violations']}")
    typer.echo(f"Avg voice-leading:    evidence={summary['evidence_avg_voice_leading_score']:.4f}  baseline={summary['baseline_avg_voice_leading_score']:.4f}")
    typer.echo(f"Avg harmonic sim:     evidence={summary['evidence_avg_harmonic_similarity']:.4f}  baseline={summary['baseline_avg_harmonic_similarity']:.4f}")
    typer.echo(f"Avg complexity div:   evidence={summary['evidence_avg_complexity_divergence']:.4f}  baseline={summary['baseline_avg_complexity_divergence']:.4f}")
    typer.echo(f"Avg cadences placed:  evidence={summary['evidence_avg_cadences']}")
    typer.echo(f"\nEvidence issues:  {dict(ev_issue_agg.most_common())}")
    typer.echo(f"Baseline issues:  {dict(bl_issue_agg.most_common())}")
    typer.echo(f"\nResults saved to: {output}")
    typer.echo(f"History snapshot:    {snapshot_path}")
    typer.echo(f"Dashboard saved to:  {dashboard_path}")


@app.command("quality")
def quality_benchmark(
    sample_size: int = typer.Option(30, "--sample", help="Number of chorales to evaluate."),
    output: Path = typer.Option(
        Path("data/derived/quality_benchmark.json"),
        "--output",
        help="Path to write quality benchmark results JSON.",
    ),
    corpus_stats_output: Path = typer.Option(
        DEFAULT_QUALITY_STATS_PATH,
        "--corpus-stats-output",
        help="Path to write or reuse corpus-wide quality statistics JSON.",
    ),
) -> None:
    """Benchmark Bach fidelity metrics for evidence-driven vs baseline composition."""

    bundles = sorted(glob.glob("data/derived/dcml_bach_chorales/*.evidence_bundle.json"))
    raw_notes = sorted(glob.glob("data/raw/dcml_bach_chorales/notes/*.notes.tsv"))

    def stem(path: str) -> str:
        base = os.path.basename(path)
        if base.startswith("notes__"):
            return base.replace("notes__", "").replace(".evidence_bundle.json", "")
        return base.replace(".notes.tsv", "")

    bundle_map = {stem(bundle): bundle for bundle in bundles}
    pairs = [(raw, bundle_map[stem(raw)]) for raw in raw_notes if stem(raw) in bundle_map]
    corpus_graphs, _ = _load_corpus()
    quality_stats = load_or_compute_quality_corpus_stats(
        corpus_graphs,
        output=corpus_stats_output,
    )

    step = max(1, len(pairs) // sample_size)
    sample = pairs[::step][:sample_size]

    results = []
    evidence_fidelity_sum = baseline_fidelity_sum = 0.0
    evidence_chord_kl_sum = baseline_chord_kl_sum = 0.0
    evidence_cadence_kl_sum = baseline_cadence_kl_sum = 0.0
    evidence_harmonic_similarity_sum = baseline_harmonic_similarity_sum = 0.0

    for i, (raw, bundle) in enumerate(sample):
        typer.echo(f"[{i + 1}/{len(sample)}] {os.path.basename(raw)}")
        try:
            result = _evaluate_quality_single(raw, bundle, quality_stats)
        except Exception as exc:
            typer.echo(f"  ERROR: {exc}")
            continue
        results.append(result)
        evidence = result["evidence"]
        baseline = result["baseline"]
        evidence_metrics = evidence["metrics"]
        baseline_metrics = baseline["metrics"]
        evidence_fidelity_sum += evidence["bach_fidelity_score"]
        baseline_fidelity_sum += baseline["bach_fidelity_score"]
        evidence_chord_kl_sum += evidence_metrics["chord_kl_divergence"]
        baseline_chord_kl_sum += baseline_metrics["chord_kl_divergence"]
        evidence_cadence_kl_sum += evidence_metrics["cadence_kl_divergence"]
        baseline_cadence_kl_sum += baseline_metrics["cadence_kl_divergence"]
        evidence_harmonic_similarity_sum += evidence_metrics.get("harmonic_similarity_to_reference", 0.0)
        baseline_harmonic_similarity_sum += baseline_metrics.get("harmonic_similarity_to_reference", 0.0)

    n = len(results)
    if n == 0:
        typer.echo("No results.")
        return

    summary = {
        "sample_size": n,
        "evidence_avg_bach_fidelity": round(evidence_fidelity_sum / n, 2),
        "baseline_avg_bach_fidelity": round(baseline_fidelity_sum / n, 2),
        "evidence_avg_chord_kl_divergence": round(evidence_chord_kl_sum / n, 4),
        "baseline_avg_chord_kl_divergence": round(baseline_chord_kl_sum / n, 4),
        "evidence_avg_cadence_kl_divergence": round(evidence_cadence_kl_sum / n, 4),
        "baseline_avg_cadence_kl_divergence": round(baseline_cadence_kl_sum / n, 4),
        "evidence_avg_harmonic_similarity": round(evidence_harmonic_similarity_sum / n, 4),
        "baseline_avg_harmonic_similarity": round(baseline_harmonic_similarity_sum / n, 4),
    }
    summary["evidence_beats_baseline_on_chord_kl"] = (
        summary["evidence_avg_chord_kl_divergence"] <= summary["baseline_avg_chord_kl_divergence"]
    )

    payload = {
        "summary": summary,
        "results": results,
        "corpus_stats": quality_stats.model_dump(mode="json"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    typer.echo("\nQUALITY BENCHMARK")
    typer.echo(f"Sample size:           {n}")
    typer.echo("QUALITY COMPARISON TABLE")
    for line in _format_quality_table(results):
        typer.echo(line)
    typer.echo(
        "Bach fidelity score:   "
        f"evidence={summary['evidence_avg_bach_fidelity']:.2f}  "
        f"baseline={summary['baseline_avg_bach_fidelity']:.2f}"
    )
    typer.echo(
        "Chord KL divergence:   "
        f"evidence={summary['evidence_avg_chord_kl_divergence']:.4f}  "
        f"baseline={summary['baseline_avg_chord_kl_divergence']:.4f}"
    )
    typer.echo(
        "Cadence KL divergence: "
        f"evidence={summary['evidence_avg_cadence_kl_divergence']:.4f}  "
        f"baseline={summary['baseline_avg_cadence_kl_divergence']:.4f}"
    )
    typer.echo(
        "Harmonic similarity:   "
        f"evidence={summary['evidence_avg_harmonic_similarity']:.4f}  "
        f"baseline={summary['baseline_avg_harmonic_similarity']:.4f}"
    )
    typer.echo(
        "Evidence beats baseline on chord KL: "
        f"{'yes' if summary['evidence_beats_baseline_on_chord_kl'] else 'no'}"
    )
    typer.echo(f"Results saved to:      {output}")
    typer.echo(f"Corpus stats saved to: {corpus_stats_output}")


@app.command("predict-next")
def predict_next(
    model: str = typer.Option("bigram", "--model", help="Model: unigram, bigram, or degree_chord_map."),
    split: str = typer.Option("test", "--split", help="Split mode: test, val, or train."),
    sample_size: int = typer.Option(0, "--sample", help="Optional evaluation sample size for faster runs."),
    output: Path = typer.Option(
        Path("data/derived/next_chord_benchmark.json"),
        "--output",
        help="Path to write next-chord benchmark results JSON.",
    ),
    all_models: bool = typer.Option(False, "--all-models", help="Evaluate all baseline models."),
) -> None:
    normalized = _normalize_task_name(model)
    if not all_models and normalized not in PREDICTORS:
        raise typer.BadParameter(f"--model must be one of: {', '.join(sorted(PREDICTORS))}")

    payload = run_next_chord_benchmark(
        model_names=None if all_models else [normalized],
        split=split,
        sample=sample_size or None,
        output=output,
    )
    typer.echo("NEXT-CHORD BENCHMARK")
    typer.echo(f"Split: {payload['split']}")
    typer.echo(f"Train instances: {payload['train_instance_count']}")
    typer.echo(f"Eval instances:  {payload['eval_instance_count']}")
    for model_name, metrics in payload["results"].items():
        typer.echo(
            f"{model_name}: top1={metrics['top1_accuracy']:.4f} "
            f"top3={metrics['top3_accuracy']:.4f} "
            f"func={metrics['functional_accuracy']:.4f} "
            f"ppl={metrics['perplexity']:.4f}"
        )
    typer.echo(f"Results saved to: {output}")


@app.command("dashboard")
def build_dashboard(
    history_dir: Path = typer.Option(
        DEFAULT_HISTORY_DIR,
        "--history-dir",
        help="Directory containing persisted benchmark snapshots.",
    ),
    output: Path = typer.Option(
        DEFAULT_DASHBOARD_PATH,
        "--output",
        help="Path to write the static HTML dashboard.",
    ),
) -> None:
    """Render a static benchmark dashboard from persisted history."""

    history = load_benchmark_history(history_dir)
    if not history:
        raise typer.BadParameter(f"No benchmark history found in {history_dir}")
    render_dashboard(history, output=output)
    typer.echo(f"Dashboard saved to: {output}")
    typer.echo(f"Snapshots loaded: {len(history)}")


@app.command("check-regressions")
def check_regressions(
    current: Path = typer.Option(..., "--current", help="Current benchmark snapshot JSON."),
    baseline: Path = typer.Option(..., "--baseline", help="Baseline benchmark snapshot JSON."),
) -> None:
    """Exit non-zero when tracked benchmark metrics regress beyond thresholds."""

    alerts = compare_benchmark_runs(load_snapshot(current), load_snapshot(baseline))
    if not alerts:
        typer.echo("No benchmark regressions detected.")
        return

    typer.echo("Benchmark regression alerts:")
    for alert in alerts:
        typer.echo(
            f"- {alert['label']}: current={alert['current']} baseline={alert['baseline']} "
            f"threshold={alert['threshold']}"
        )
    raise typer.Exit(code=1)


@app.command("complexity")
def complexity_report(
    output: Path = typer.Option(
        DEFAULT_COMPLEXITY_STATS_PATH,
        "--output",
        help="Path to write corpus-wide complexity statistics JSON.",
    ),
    sample_size: int = typer.Option(
        0,
        "--sample",
        help="Optional corpus-size limit for development checks.",
    ),
) -> None:
    """Compute corpus-wide complexity statistics for Bach chorales."""

    graphs, _ = _load_corpus(limit=sample_size or None)
    stats = load_or_compute_corpus_stats(graphs, output=output)
    typer.echo(f"Complexity corpus stats saved to: {output}")
    typer.echo(f"Graphs analyzed: {stats.graph_count}")
    for metric, summary in stats.metrics.items():
        typer.echo(f"{metric}: mean={summary.mean:.4f} std={summary.std:.4f}")


@app.command("leaderboard")
def show_leaderboard(
    results_path: Path = typer.Argument(..., help="Path to BachBench results JSON."),
) -> None:
    """Pretty-print BachBench results as a leaderboard."""
    from bachbot.benchmark.leaderboard import print_leaderboard
    from bachbot.benchmark.protocol import SuiteResult

    data = json.loads(results_path.read_text(encoding="utf-8"))
    suite = SuiteResult.model_validate(data)
    typer.echo(print_leaderboard(suite))


@app.command("compare")
def compare_systems_cmd(
    systems: str = typer.Option("bachbot,ground_truth", "--systems", help="Comma-separated adapter names."),
    test_set: str = typer.Option("standard-30", "--test-set", help="'standard-30' or path to JSON test set."),
    limit: int = typer.Option(0, "--limit", help="Max melodies to evaluate (0 = all)."),
    output: Path = typer.Option(
        Path("data/derived/cross_system_comparison.json"),
        "--output",
        help="Path to write comparison report JSON.",
    ),
) -> None:
    """Compare harmonization quality across systems on a standardized test set."""
    from bachbot.benchmark.cross_system.adapters import ADAPTER_REGISTRY, get_adapter
    from bachbot.benchmark.cross_system.evaluator import compare_systems, generate_comparison_table
    from bachbot.benchmark.cross_system.test_set import BenchmarkMelody, build_standard_test_set

    # Build or load test set.
    if test_set == "standard-30":
        melody_limit = limit if limit > 0 else 30
        melodies = build_standard_test_set(limit=melody_limit)
    else:
        # Load from JSON file.
        test_set_path = Path(test_set)
        if not test_set_path.exists():
            raise typer.BadParameter(f"Test set file not found: {test_set}")
        raw = json.loads(test_set_path.read_text(encoding="utf-8"))
        melodies = [BenchmarkMelody.model_validate(m) for m in raw]
        if limit > 0:
            melodies = melodies[:limit]

    if not melodies:
        typer.echo("No test melodies available.")
        return

    # Instantiate adapters.
    adapter_names = [s.strip() for s in systems.split(",") if s.strip()]
    adapters = []
    for name in adapter_names:
        try:
            adapter = get_adapter(name)
        except ValueError as exc:
            typer.echo(f"WARNING: {exc}")
            continue
        if not adapter.is_available():
            typer.echo(f"WARNING: adapter '{name}' is not available, skipping.")
            continue
        adapters.append(adapter)

    if not adapters:
        typer.echo("No available adapters. Nothing to compare.")
        return

    typer.echo(f"Test set: {len(melodies)} melodies")
    typer.echo(f"Systems: {', '.join(a.name for a in adapters)}")
    typer.echo("")

    report = compare_systems(melodies, adapters)

    # Save report.
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )

    # Print table.
    typer.echo("CROSS-SYSTEM COMPARISON")
    typer.echo("=" * 60)
    typer.echo(generate_comparison_table(report))
    typer.echo("")
    typer.echo(f"Results saved to: {output}")
