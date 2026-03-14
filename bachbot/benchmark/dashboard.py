"""Persistence, dashboard rendering, and regression checks for benchmark runs."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HISTORY_DIR = Path("data/derived/benchmarks")
DEFAULT_DASHBOARD_PATH = DEFAULT_HISTORY_DIR / "index.html"
LATEST_SNAPSHOT = DEFAULT_HISTORY_DIR / "latest.json"

_CHART_SPECS = [
    {
        "id": "pass-rate",
        "title": "Validation Pass Rate",
        "metrics": [
            ("evidence_avg_pass_rate", "Evidence"),
            ("baseline_avg_pass_rate", "Baseline"),
        ],
    },
    {
        "id": "chord-variety",
        "title": "Average Chord Variety",
        "metrics": [
            ("evidence_avg_chord_variety", "Evidence"),
            ("baseline_avg_chord_variety", "Baseline"),
            ("original_avg_chord_variety", "Original"),
        ],
    },
    {
        "id": "parallel-violations",
        "title": "Average Parallel Violations",
        "metrics": [
            ("evidence_avg_parallel_violations", "Evidence"),
            ("baseline_avg_parallel_violations", "Baseline"),
        ],
    },
    {
        "id": "voice-leading",
        "title": "Average Voice-Leading Score",
        "metrics": [
            ("evidence_avg_voice_leading_score", "Evidence"),
            ("baseline_avg_voice_leading_score", "Baseline"),
        ],
    },
    {
        "id": "complexity",
        "title": "Pitch-Class Entropy",
        "metrics": [
            ("evidence_avg_pitch_class_entropy", "Evidence"),
            ("baseline_avg_pitch_class_entropy", "Baseline"),
            ("original_avg_pitch_class_entropy", "Original"),
        ],
    },
    {
        "id": "harmonic-similarity",
        "title": "Average Harmonic Similarity To Original",
        "metrics": [
            ("evidence_avg_harmonic_similarity", "Evidence"),
            ("baseline_avg_harmonic_similarity", "Baseline"),
        ],
    },
]

_REGRESSION_RULES = {
    "evidence_avg_pass_rate": {
        "label": "Evidence pass rate",
        "direction": "min",
        "threshold": 0.03,
    },
    "evidence_avg_chord_variety": {
        "label": "Evidence chord variety",
        "direction": "min",
        "threshold": 0.5,
    },
    "evidence_avg_parallel_violations": {
        "label": "Evidence parallel violations",
        "direction": "max",
        "threshold": 0.5,
    },
    "evidence_avg_voice_leading_score": {
        "label": "Evidence voice-leading score",
        "direction": "min",
        "threshold": 0.03,
    },
    "evidence_avg_harmonic_similarity": {
        "label": "Evidence harmonic similarity",
        "direction": "min",
        "threshold": 0.03,
    },
}


def build_report_metadata(*, sample_size: int, output: Path, split: str = "full") -> dict[str, Any]:
    """Return stable metadata that is written into benchmark reports."""

    generated_at = datetime.now(timezone.utc).isoformat()
    git_commit = _resolve_git_commit() or "unknown"
    return {
        "generated_at": generated_at,
        "git_commit": git_commit,
        "sample_size": sample_size,
        "split": split,
        "source_output": str(output),
    }


def persist_benchmark_history(
    report: dict[str, Any],
    *,
    history_dir: Path = DEFAULT_HISTORY_DIR,
) -> Path:
    """Persist a benchmark report as a timestamped history snapshot plus latest.json."""

    metadata = dict(report.get("metadata", {}))
    metadata.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    metadata["git_commit"] = metadata.get("git_commit") or _resolve_git_commit() or "unknown"
    metadata.setdefault("sample_size", report.get("summary", {}).get("sample_size", 0))
    snapshot = {
        "schema_version": "1.0.0",
        "metadata": metadata,
        "summary": dict(report.get("summary", {})),
    }

    history_dir.mkdir(parents=True, exist_ok=True)
    stamp = _slugify_timestamp(str(metadata["generated_at"]))
    commit = _slugify(str(metadata.get("git_commit") or "unknown"))[:12] or "unknown"
    snapshot_path = history_dir / f"benchmark-{stamp}-{commit}.json"
    payload = json.dumps(snapshot, indent=2, sort_keys=True)
    snapshot_path.write_text(payload, encoding="utf-8")
    (history_dir / LATEST_SNAPSHOT.name).write_text(payload, encoding="utf-8")
    return snapshot_path


def load_benchmark_history(history_dir: Path = DEFAULT_HISTORY_DIR) -> list[dict[str, Any]]:
    """Load sorted benchmark snapshots from disk."""

    history: list[dict[str, Any]] = []
    snapshot_paths = sorted(
        path for path in history_dir.glob("*.json")
        if path.name != LATEST_SNAPSHOT.name
    )
    if not snapshot_paths and (history_dir / LATEST_SNAPSHOT.name).exists():
        snapshot_paths = [history_dir / LATEST_SNAPSHOT.name]

    for path in snapshot_paths:
        try:
            history.append(_normalize_snapshot(json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, OSError, ValueError):
            continue
    history.sort(key=lambda item: str(item.get("metadata", {}).get("generated_at", "")))
    return history


def compare_benchmark_runs(
    current: dict[str, Any],
    baseline: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return regression alerts when current results are meaningfully worse than baseline."""

    current_summary = _normalize_snapshot(current).get("summary", {})
    baseline_summary = _normalize_snapshot(baseline).get("summary", {})
    alerts: list[dict[str, Any]] = []

    for metric, rule in _REGRESSION_RULES.items():
        current_value = current_summary.get(metric)
        baseline_value = baseline_summary.get(metric)
        if not isinstance(current_value, (int, float)) or not isinstance(baseline_value, (int, float)):
            continue

        threshold = float(rule["threshold"])
        is_regression = False
        if rule["direction"] == "min":
            is_regression = current_value < baseline_value - threshold
        else:
            is_regression = current_value > baseline_value + threshold

        if is_regression:
            alerts.append(
                {
                    "metric": metric,
                    "label": rule["label"],
                    "current": round(float(current_value), 4),
                    "baseline": round(float(baseline_value), 4),
                    "threshold": threshold,
                    "direction": rule["direction"],
                }
            )

    return alerts


def render_dashboard(
    history: list[dict[str, Any]],
    *,
    output: Path = DEFAULT_DASHBOARD_PATH,
) -> Path:
    """Write a static HTML dashboard for the benchmark history."""

    output.parent.mkdir(parents=True, exist_ok=True)
    html = build_dashboard_html(history)
    output.write_text(html, encoding="utf-8")
    return output


def build_dashboard_html(history: list[dict[str, Any]]) -> str:
    """Build the HTML document for the benchmark dashboard."""

    normalized = [_normalize_snapshot(item) for item in history]
    latest = normalized[-1] if normalized else {"metadata": {}, "summary": {}}
    previous = normalized[-2] if len(normalized) > 1 else None
    alerts = compare_benchmark_runs(latest, previous) if previous else []
    payload = _build_chart_payload(normalized)

    latest_summary_rows = "\n".join(
        f"<tr><th>{_humanize(metric)}</th><td>{value}</td></tr>"
        for metric, value in sorted(latest.get("summary", {}).items())
        if isinstance(value, (int, float))
    ) or "<tr><td colspan='2'>No benchmark history yet.</td></tr>"

    alert_markup = "".join(
        "<li>"
        f"{alert['label']}: current {alert['current']} vs baseline {alert['baseline']} "
        f"(threshold {alert['threshold']})"
        "</li>"
        for alert in alerts
    ) or "<li>No regressions detected against the previous snapshot.</li>"

    chart_markup = "\n".join(
        f"""
        <section class="chart-card">
          <h2>{spec['title']}</h2>
          <canvas id="chart-{spec['id']}" height="160"></canvas>
        </section>
        """
        for spec in _CHART_SPECS
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bachbot Benchmark Dashboard</title>
  <style>
    :root {{
      --bg: #f6f2e8;
      --card: #fffdf8;
      --ink: #1f1b17;
      --muted: #6a6057;
      --accent: #8b3a2a;
      --accent-soft: #d8b7a4;
      --border: #d8cfc3;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top right, rgba(139, 58, 42, 0.12), transparent 32%),
        linear-gradient(180deg, #faf5eb 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    .hero {{
      display: grid;
      gap: 18px;
      margin-bottom: 28px;
    }}
    .hero h1 {{
      margin: 0;
      font-size: clamp(2rem, 4vw, 3rem);
      line-height: 1.05;
    }}
    .hero p {{
      margin: 0;
      max-width: 60rem;
      color: var(--muted);
      font-size: 1.05rem;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .pill {{
      border: 1px solid var(--border);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.72);
      padding: 7px 12px;
      font-size: 0.95rem;
    }}
    .grid {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
      margin-bottom: 24px;
    }}
    .card, .chart-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: 0 14px 30px rgba(53, 35, 20, 0.08);
      padding: 18px 18px 14px;
    }}
    .card h2, .chart-card h2 {{
      margin: 0 0 12px;
      font-size: 1.1rem;
    }}
    .summary-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}
    .summary-table th,
    .summary-table td {{
      padding: 7px 0;
      border-bottom: 1px solid rgba(216, 207, 195, 0.65);
      text-align: left;
      vertical-align: top;
    }}
    .summary-table th {{
      color: var(--muted);
      font-weight: 600;
      padding-right: 16px;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    li {{
      margin-bottom: 8px;
    }}
    .charts {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    }}
    footer {{
      margin-top: 26px;
      color: var(--muted);
      font-size: 0.9rem;
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div>
        <h1>Bachbot Benchmark Dashboard</h1>
        <p>Static trend view over persisted benchmark snapshots. The dashboard is generated from `data/derived/benchmarks/*.json` and highlights regressions against the previous snapshot.</p>
      </div>
      <div class="meta">
        <span class="pill">Snapshots: {len(normalized)}</span>
        <span class="pill">Latest commit: {latest.get("metadata", {}).get("git_commit") or "unknown"}</span>
        <span class="pill">Latest sample: {latest.get("metadata", {}).get("sample_size") or 0}</span>
        <span class="pill">Latest timestamp: {latest.get("metadata", {}).get("generated_at") or "n/a"}</span>
      </div>
    </section>

    <section class="grid">
      <article class="card">
        <h2>Latest Summary</h2>
        <table class="summary-table">
          {latest_summary_rows}
        </table>
      </article>
      <article class="card">
        <h2>Regression Alerts</h2>
        <ul>{alert_markup}</ul>
      </article>
    </section>

    <section class="charts">
      {chart_markup}
    </section>

    <footer>
      Dashboard generated from persisted benchmark snapshots. Thresholds are defined in `bachbot/benchmark/dashboard.py`.
    </footer>
  </main>

  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    const payload = {json.dumps(payload)};
    const colors = [
      "#8b3a2a",
      "#316879",
      "#8a6f2d",
      "#5a4f7a",
      "#3d6a45",
      "#b45f06"
    ];

    function dataset(metric, label, index) {{
      return {{
        label,
        data: payload.series[metric] || [],
        borderColor: colors[index % colors.length],
        backgroundColor: colors[index % colors.length],
        borderWidth: 2,
        tension: 0.3
      }};
    }}

    for (const chart of payload.charts) {{
      const datasets = chart.metrics.map((item, index) => dataset(item.metric, item.label, index));
      new Chart(document.getElementById(`chart-${{chart.id}}`), {{
        type: "line",
        data: {{
          labels: payload.labels,
          datasets
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          scales: {{
            y: {{
              beginAtZero: true
            }}
          }},
          plugins: {{
            legend: {{
              position: "bottom"
            }}
          }}
        }}
      }});
    }}
  </script>
</body>
</html>
"""


def load_snapshot(path: Path) -> dict[str, Any]:
    """Load a benchmark snapshot or report from disk."""

    return _normalize_snapshot(json.loads(path.read_text(encoding="utf-8")))


def _normalize_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    if "metadata" in payload and "summary" in payload:
        return payload
    raise ValueError("Expected benchmark payload with metadata and summary")


def _build_chart_payload(history: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [
        _short_label(item.get("metadata", {}).get("generated_at"), item.get("metadata", {}).get("git_commit"))
        for item in history
    ]
    series: dict[str, list[float | None]] = {}
    for spec in _CHART_SPECS:
        for metric, _ in spec["metrics"]:
            series[metric] = [
                _coerce_number(item.get("summary", {}).get(metric))
                for item in history
            ]
    charts = [
        {
            "id": spec["id"],
            "title": spec["title"],
            "metrics": [{"metric": metric, "label": label} for metric, label in spec["metrics"]],
        }
        for spec in _CHART_SPECS
    ]
    return {"labels": labels, "series": series, "charts": charts}


def _resolve_git_commit() -> str | None:
    env_commit = os.getenv("GITHUB_SHA")
    if env_commit:
        return env_commit[:12]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def _slugify_timestamp(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "", value) or "unknown"


def _slugify(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "-", value)


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value), 4)
    return None


def _short_label(timestamp: Any, commit: Any) -> str:
    if isinstance(timestamp, str) and "T" in timestamp:
        stamp = timestamp.replace("T", " ")[:16]
    else:
        stamp = str(timestamp or "n/a")
    suffix = str(commit or "unknown")[:7]
    return f"{stamp} {suffix}".strip()


def _humanize(metric: str) -> str:
    return metric.replace("_", " ").capitalize()
