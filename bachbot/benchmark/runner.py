"""BachBench runner — orchestrates tasks, computes summaries."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from bachbot.benchmark.protocol import SuiteResult, TaskResult
from bachbot.benchmark.split import compute_grouped_split, load_split_manifest, save_split_manifest
from bachbot.benchmark.tasks import TASK_REGISTRY
from bachbot.encodings.event_graph import EventGraph

_CORPUS_NORM = Path("data/normalized/dcml_bach_chorales")
_CORPUS_DERIVED = Path("data/derived/dcml_bach_chorales")
_SPLIT_PATH = Path("data/manifests/bachbench_split_v2.json")


def _load_corpus(limit: int | None = None) -> tuple[list[EventGraph], list[dict]]:
    """Load corpus event graphs + evidence bundles."""
    graphs: list[EventGraph] = []
    bundles: list[dict] = []

    graph_paths = sorted(_CORPUS_NORM.glob("*.event_graph.json"))
    if limit:
        graph_paths = graph_paths[:limit]

    for gp in graph_paths:
        stem = gp.name.replace(".event_graph.json", "")
        bp = _CORPUS_DERIVED / f"{stem}.evidence_bundle.json"
        if not bp.exists():
            continue
        try:
            g = EventGraph.model_validate(json.loads(gp.read_text(encoding="utf-8")))
            b = json.loads(bp.read_text(encoding="utf-8"))
            graphs.append(g)
            bundles.append(b)
        except Exception:
            continue

    return graphs, bundles


def _get_split(graphs: list[EventGraph], split_mode: str) -> set[str]:
    """Get the set of work IDs for the requested split."""
    if split_mode == "full":
        return {g.work_id for g in graphs}

    current_ids = {g.work_id for g in graphs}
    if _SPLIT_PATH.exists():
        split = load_split_manifest(_SPLIT_PATH)
        if current_ids > set(split):
            split = compute_grouped_split(graphs)
            save_split_manifest(split, _SPLIT_PATH)
    else:
        split = compute_grouped_split(graphs)
        save_split_manifest(split, _SPLIT_PATH)

    return {wid for wid, role in split.items() if role == split_mode}


def run_suite(
    tasks: list[str] | None = None,
    split: str = "test",
    sample: int | None = None,
    solver_name: str = "bachbot-evidence",
    output: Path | None = None,
) -> SuiteResult:
    """Run the BachBench benchmark suite.

    Parameters
    ----------
    tasks : list of task names, or None for all
    split : "test", "train", or "full"
    sample : limit corpus loading for quick dev runs
    solver_name : name for the results
    output : path to write JSON results
    """
    graphs, bundles = _load_corpus(limit=sample)
    if not graphs:
        return SuiteResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            solver_name=solver_name,
            split=split,
        )

    split_ids = _get_split(graphs, split)
    task_names = tasks or list(TASK_REGISTRY.keys())

    all_results: list[TaskResult] = []
    task_summaries: dict[str, dict[str, float]] = {}

    for tname in task_names:
        task = TASK_REGISTRY.get(tname)
        if task is None:
            continue

        instances = task.generate_instances(graphs, bundles, split_ids)
        task_results: list[TaskResult] = []

        for inp, gt_graph, bundle in instances:
            try:
                baseline_output = task.run_baseline(inp, bundle=bundle)
                result = task.evaluate(inp, baseline_output, gt_graph, bundle)
                task_results.append(result)
            except Exception:
                task_results.append(TaskResult(
                    task_id=inp.task_id,
                    task_type=tname,
                    chorale_id=inp.metadata.get("work_id", ""),
                    metrics={"composite": 0.0},
                    passed=False,
                ))

        # Compute summary for this task
        if task_results:
            metric_sums: dict[str, float] = defaultdict(float)
            for r in task_results:
                for k, v in r.metrics.items():
                    metric_sums[k] += v
            n = len(task_results)
            task_summaries[tname] = {k: round(v / n, 4) for k, v in metric_sums.items()}
            task_summaries[tname]["instance_count"] = float(n)
            task_summaries[tname]["pass_rate"] = round(
                sum(1 for r in task_results if r.passed) / n, 4
            )

        all_results.extend(task_results)

    suite = SuiteResult(
        suite_version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        solver_name=solver_name,
        split=split,
        task_summaries=task_summaries,
        per_instance=all_results,
        corpus_size=len(split_ids),
    )

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(suite.model_dump(), indent=2, default=str),
            encoding="utf-8",
        )

    return suite
