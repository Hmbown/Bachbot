from __future__ import annotations

import json
import re
import tempfile
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from bachbot import __version__
from bachbot.analysis import analyze_graph
from bachbot.claims import build_evidence_bundle
from bachbot.composition import compose_chorale_study
from bachbot.composition.validators.hard_rules import validate_graph
from bachbot.config import get_settings
from bachbot.encodings import EventGraph, Normalizer
from bachbot.models.base import BachbotModel

_DATASET_ID = "dcml_bach_chorales"
_ALNUM_RE = re.compile(r"[^a-z0-9]+")


class MusicXMLRequest(BachbotModel):
    musicxml: str
    work_id: str | None = None
    encoding_id: str | None = None


class ComposeRequest(MusicXMLRequest):
    evidence_bundle: dict[str, Any] | None = None


class CorpusSummary(BachbotModel):
    chorale_id: str
    title: str
    encoding_id: str
    work_id: str
    key: str | None = None
    cadence_count: int = 0
    cadence_types: list[str] = []
    harmonic_event_count: int = 0


def _json_path(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_lookup(value: str) -> str:
    return _ALNUM_RE.sub("", value.lower())


def _chorale_number(entry: dict[str, Any]) -> int | None:
    title = str(entry.get("title", ""))
    match = re.match(r"(\d{1,3})\b", title)
    if match:
        return int(match.group(1))
    encoding_id = str(entry.get("encoding_id", ""))
    match = re.search(r"notes__(\d{3})", encoding_id)
    if match:
        return int(match.group(1))
    return None


def _chorale_id(entry: dict[str, Any]) -> str:
    number = _chorale_number(entry)
    if number is not None:
        return f"BWV{number:03d}"
    return str(entry["encoding_id"])


def _chorale_aliases(entry: dict[str, Any]) -> set[str]:
    aliases = {
        _normalize_lookup(str(entry["encoding_id"])),
        _normalize_lookup(str(entry["work_id"])),
        _normalize_lookup(str(entry.get("title", ""))),
        _normalize_lookup(_chorale_id(entry)),
    }
    number = _chorale_number(entry)
    if number is not None:
        aliases.update(
            {
                _normalize_lookup(str(number)),
                _normalize_lookup(f"{number:03d}"),
                _normalize_lookup(f"BWV{number}"),
                _normalize_lookup(f"BWV-{number}"),
                _normalize_lookup(f"BWV{number:03d}"),
                _normalize_lookup(f"BWV-{number:03d}"),
            }
        )
    return {alias for alias in aliases if alias}


@lru_cache(maxsize=1)
def _corpus_index() -> dict[str, Any]:
    settings = get_settings()
    normalized_path = settings.normalized_dir / _DATASET_ID / "normalization_index.json"
    analysis_path = settings.derived_dir / _DATASET_ID / "analysis_index.json"
    if not normalized_path.exists() or not analysis_path.exists():
        raise FileNotFoundError(f"Corpus indices not found for dataset {_DATASET_ID}")

    normalized_entries = _json_path(normalized_path)["normalized"]
    analysis_entries = {entry["encoding_id"]: entry for entry in _json_path(analysis_path)["analyses"]}
    by_alias: dict[str, dict[str, Any]] = {}
    combined_entries: list[dict[str, Any]] = []

    for normalized_entry in normalized_entries:
        record = {
            "normalized": normalized_entry,
            "analysis": analysis_entries.get(normalized_entry["encoding_id"]),
        }
        combined_entries.append(record)
        for alias in _chorale_aliases(normalized_entry):
            by_alias[alias] = record

    return {"entries": combined_entries, "by_alias": by_alias}


@lru_cache(maxsize=1)
def _corpus_summaries() -> list[CorpusSummary]:
    summaries: list[CorpusSummary] = []
    for record in _corpus_index()["entries"]:
        normalized_entry = record["normalized"]
        analysis_entry = record["analysis"]
        analysis_report = _json_path(Path(analysis_entry["analysis_path"])) if analysis_entry else {}
        cadence_types = sorted(
            {
                cadence.get("cadence_type", "")
                for cadence in analysis_report.get("cadences", [])
                if cadence.get("cadence_type")
            }
        )
        summaries.append(
            CorpusSummary(
                chorale_id=_chorale_id(normalized_entry),
                title=str(normalized_entry.get("title", normalized_entry["encoding_id"])),
                encoding_id=str(normalized_entry["encoding_id"]),
                work_id=str(normalized_entry["work_id"]),
                key=analysis_report.get("key"),
                cadence_count=len(analysis_report.get("cadences", [])),
                cadence_types=cadence_types,
                harmonic_event_count=len(analysis_report.get("harmony", [])),
            )
        )
    return summaries


def _resolve_corpus_record(chorale_id: str) -> dict[str, Any]:
    try:
        return _corpus_index()["by_alias"][_normalize_lookup(chorale_id)]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown chorale: {chorale_id}") from exc


def _normalize_request(payload: MusicXMLRequest) -> EventGraph:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".musicxml", encoding="utf-8", delete=False) as handle:
            handle.write(payload.musicxml)
            temp_path = Path(handle.name)
        return Normalizer().normalize(temp_path, work_id=payload.work_id, encoding_id=payload.encoding_id)
    except Exception as exc:  # pragma: no cover - FastAPI surface converts mixed parser errors
        raise HTTPException(status_code=400, detail=f"Could not normalize submitted MusicXML: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _analysis_payload(graph: EventGraph) -> tuple[dict[str, Any], dict[str, Any]]:
    report = analyze_graph(graph)
    bundle = build_evidence_bundle(graph, report)
    return report.model_dump(mode="json"), bundle.model_dump(mode="json")


def _evaluation_metrics(analysis_report: dict[str, Any], validation_report: dict[str, Any]) -> dict[str, Any]:
    counterpoint = analysis_report.get("voice_leading", {}).get("counterpoint", {})
    issues = validation_report.get("issues", [])
    return {
        "harmonic_event_count": len(analysis_report.get("harmony", [])),
        "cadence_count": len(analysis_report.get("cadences", [])),
        "parallel_5ths": counterpoint.get("parallel_5ths", 0),
        "parallel_8ves": counterpoint.get("parallel_8ves", 0),
        "range_issue_count": sum(1 for issue in issues if issue.get("code") == "range"),
        "spacing_issue_count": sum(1 for issue in issues if issue.get("code") == "spacing"),
        "error_count": sum(1 for issue in issues if issue.get("severity") == "error"),
        "warning_count": sum(1 for issue in issues if issue.get("severity") == "warning"),
        "passed_validation": validation_report.get("passed", False),
    }


def create_app() -> FastAPI:
    app = FastAPI(
        title="Bachbot API",
        version=__version__,
        description="Programmatic access to Bachbot analysis, composition, evaluation, and corpus data.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        settings = get_settings()
        return {
            "status": "ok",
            "version": __version__,
            "workspace_root": str(settings.workspace_root),
            "dataset_id": _DATASET_ID,
        }

    @app.get("/corpus/search")
    def corpus_search(
        key: str | None = Query(None, description="Exact key label, e.g. 'G major'."),
        cadence_type: str | None = Query(None, description="Cadence type filter, e.g. 'cadential'."),
        title_contains: str | None = Query(None, description="Case-insensitive title substring."),
        limit: int = Query(10, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            summaries = _corpus_summaries()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        results = summaries
        if key:
            key_lower = key.lower()
            results = [item for item in results if (item.key or "").lower() == key_lower]
        if cadence_type:
            cadence_lower = cadence_type.lower()
            results = [item for item in results if cadence_lower in {value.lower() for value in item.cadence_types}]
        if title_contains:
            title_lower = title_contains.lower()
            results = [item for item in results if title_lower in item.title.lower()]

        selected = results[:limit]
        return {
            "dataset_id": _DATASET_ID,
            "count": len(selected),
            "results": [item.model_dump(mode="json") for item in selected],
        }

    @app.get("/corpus/{chorale_id}")
    def corpus_detail(chorale_id: str) -> dict[str, Any]:
        record = _resolve_corpus_record(chorale_id)
        normalized_entry = record["normalized"]
        analysis_entry = record["analysis"]

        graph = EventGraph.model_validate(_json_path(Path(normalized_entry["event_graph_path"])))
        analysis_report: dict[str, Any]
        evidence_bundle: dict[str, Any]
        if analysis_entry is not None:
            analysis_report = _json_path(Path(analysis_entry["analysis_path"]))
            evidence_bundle = _json_path(Path(analysis_entry["bundle_path"]))
        else:
            analysis_report, evidence_bundle = _analysis_payload(graph)

        return {
            "dataset_id": _DATASET_ID,
            "chorale_id": _chorale_id(normalized_entry),
            "title": normalized_entry.get("title"),
            "event_graph": graph.model_dump(mode="json"),
            "analysis_report": analysis_report,
            "evidence_bundle": evidence_bundle,
        }

    @app.post("/analyze")
    def analyze_endpoint(payload: MusicXMLRequest) -> dict[str, Any]:
        started = perf_counter()
        graph = _normalize_request(payload)
        analysis_report, evidence_bundle = _analysis_payload(graph)
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return {
            "event_graph": graph.model_dump(mode="json"),
            "analysis_report": analysis_report,
            "evidence_bundle": evidence_bundle,
            "elapsed_ms": elapsed_ms,
        }

    @app.post("/compose")
    def compose_endpoint(payload: ComposeRequest) -> dict[str, Any]:
        started = perf_counter()
        graph = _normalize_request(payload)
        try:
            composed_graph, artifact, report = compose_chorale_study(graph, bundle=payload.evidence_bundle)
        except Exception as exc:  # pragma: no cover - generator raises mixed search errors
            raise HTTPException(status_code=400, detail=f"Could not compose chorale study: {exc}") from exc
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return {
            "event_graph": composed_graph.model_dump(mode="json"),
            "artifact": artifact.model_dump(mode="json"),
            "report": report,
            "elapsed_ms": elapsed_ms,
        }

    @app.post("/evaluate")
    def evaluate_endpoint(payload: MusicXMLRequest) -> dict[str, Any]:
        started = perf_counter()
        graph = _normalize_request(payload)
        analysis_report = analyze_graph(graph).model_dump(mode="json")
        validation_report = validate_graph(graph).model_dump(mode="json")
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return {
            "analysis_report": analysis_report,
            "validation_report": validation_report,
            "metrics": _evaluation_metrics(analysis_report, validation_report),
            "elapsed_ms": elapsed_ms,
        }

    # ─── Export endpoints ────────────────────────────────────────────

    def _load_corpus_graph(chorale_id: str) -> EventGraph:
        record = _resolve_corpus_record(chorale_id)
        return EventGraph.model_validate(_json_path(Path(record["normalized"]["event_graph_path"])))

    @app.get("/corpus/{chorale_id}/midi")
    def corpus_midi(chorale_id: str) -> Response:
        from bachbot.exports.midi_export import event_graph_to_midi

        graph = _load_corpus_graph(chorale_id)
        data = event_graph_to_midi(graph)
        return Response(content=data, media_type="audio/midi", headers={
            "Content-Disposition": f'attachment; filename="{chorale_id}.mid"',
        })

    @app.get("/corpus/{chorale_id}/musicxml")
    def corpus_musicxml(chorale_id: str) -> Response:
        from bachbot.exports.musicxml_export import write_musicxml

        graph = _load_corpus_graph(chorale_id)
        with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as f:
            tmp = Path(f.name)
        try:
            write_musicxml(graph, tmp)
            content = tmp.read_text(encoding="utf-8")
        finally:
            tmp.unlink(missing_ok=True)
        return Response(content=content, media_type="application/xml", headers={
            "Content-Disposition": f'attachment; filename="{chorale_id}.musicxml"',
        })

    @app.get("/corpus/{chorale_id}/lilypond")
    def corpus_lilypond(chorale_id: str) -> Response:
        from bachbot.exports.lilypond_export import event_graph_to_lilypond

        graph = _load_corpus_graph(chorale_id)
        content = event_graph_to_lilypond(graph)
        return Response(content=content, media_type="text/x-lilypond", headers={
            "Content-Disposition": f'attachment; filename="{chorale_id}.ly"',
        })

    class ExportRequest(BachbotModel):
        event_graph: dict[str, Any]

    @app.post("/export/midi")
    def export_midi(payload: ExportRequest) -> Response:
        from bachbot.exports.midi_export import event_graph_to_midi

        graph = EventGraph.model_validate(payload.event_graph)
        data = event_graph_to_midi(graph)
        return Response(content=data, media_type="audio/midi", headers={
            "Content-Disposition": 'attachment; filename="bachbot_export.mid"',
        })

    @app.post("/export/musicxml")
    def export_musicxml(payload: ExportRequest) -> Response:
        from bachbot.exports.musicxml_export import write_musicxml

        graph = EventGraph.model_validate(payload.event_graph)
        with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as f:
            tmp = Path(f.name)
        try:
            write_musicxml(graph, tmp)
            content = tmp.read_text(encoding="utf-8")
        finally:
            tmp.unlink(missing_ok=True)
        return Response(content=content, media_type="application/xml", headers={
            "Content-Disposition": 'attachment; filename="bachbot_export.musicxml"',
        })

    @app.post("/export/lilypond")
    def export_lilypond(payload: ExportRequest) -> Response:
        from bachbot.exports.lilypond_export import event_graph_to_lilypond

        graph = EventGraph.model_validate(payload.event_graph)
        content = event_graph_to_lilypond(graph)
        return Response(content=content, media_type="text/x-lilypond", headers={
            "Content-Disposition": 'attachment; filename="bachbot_export.ly"',
        })

    # ─── Composition mode endpoints ─────────────────────────────────

    class FiguredBassRequest(BachbotModel):
        musicxml: str
        figures: list[str] | None = None

    @app.post("/compose/figured-bass")
    def compose_figured_bass(payload: FiguredBassRequest) -> dict[str, Any]:
        from bachbot.composition.generators.figured_bass import realize_figured_bass

        started = perf_counter()
        graph = _normalize_request(MusicXMLRequest(musicxml=payload.musicxml))
        try:
            composed_graph, artifact, report = realize_figured_bass(graph, figures=payload.figures)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Figured bass realization failed: {exc}") from exc
        return {
            "event_graph": composed_graph.model_dump(mode="json"),
            "artifact": artifact.model_dump(mode="json"),
            "report": report,
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
        }

    class MelodyRequest(BachbotModel):
        chords: list[str]
        key: str = "C major"

    @app.post("/compose/melody")
    def compose_melody(payload: MelodyRequest) -> dict[str, Any]:
        from bachbot.composition.generators.melody import generate_melody_from_chords

        started = perf_counter()
        try:
            graph, artifact, report = generate_melody_from_chords(payload.chords, key=payload.key)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Melody generation failed: {exc}") from exc
        return {
            "event_graph": graph.model_dump(mode="json"),
            "artifact": artifact.model_dump(mode="json"),
            "report": report,
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
        }

    @app.post("/compose/invention")
    def compose_invention(payload: MusicXMLRequest) -> dict[str, Any]:
        from bachbot.composition.generators.invention import generate_invention

        started = perf_counter()
        graph = _normalize_request(payload)
        try:
            composed_graph, artifact, report = generate_invention(graph)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invention generation failed: {exc}") from exc
        return {
            "event_graph": composed_graph.model_dump(mode="json"),
            "artifact": artifact.model_dump(mode="json"),
            "report": report,
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
        }

    # ─── Counterpoint endpoints ──────────────────────────────────────

    class CounterpointValidateRequest(BachbotModel):
        cantus_firmus: list[int]
        counterpoint: list[int]
        species: int
        position: str = "above"

    class CounterpointSolveRequest(BachbotModel):
        cantus_firmus: list[int]
        species: int
        position: str = "above"

    @app.post("/counterpoint/validate")
    def counterpoint_validate(payload: CounterpointValidateRequest) -> dict[str, Any]:
        from bachbot.composition.counterpoint import validate_counterpoint

        report = validate_counterpoint(
            payload.cantus_firmus, payload.counterpoint,
            payload.species, position=payload.position,
        )
        return report.model_dump(mode="json")

    @app.post("/counterpoint/solve")
    def counterpoint_solve(payload: CounterpointSolveRequest) -> dict[str, Any]:
        from bachbot.composition.counterpoint import generate_counterpoint

        notes = generate_counterpoint(
            payload.cantus_firmus, payload.species,
            position=payload.position,
        )
        midi_notes = [n.midi for n in notes if not n.is_rest and n.midi > 0]
        return {"solution": midi_notes, "steps": [f"Generated {len(midi_notes)} notes for species {payload.species}"]}

    # ─── Research endpoints ──────────────────────────────────────────

    @app.get("/research/fingerprint/{chorale_id}")
    def research_fingerprint(chorale_id: str) -> dict[str, Any]:
        from bachbot.analysis.style import compute_style_fingerprint

        record = _resolve_corpus_record(chorale_id)
        analysis_entry = record["analysis"]
        if analysis_entry is None:
            raise HTTPException(status_code=404, detail="No analysis available")
        bundle = _json_path(Path(analysis_entry["bundle_path"]))
        fp = compute_style_fingerprint(bundle)
        return fp.model_dump(mode="json")

    @app.get("/research/fingerprint/compare")
    def research_fingerprint_compare(ids: str = Query(..., description="Comma-separated chorale IDs")) -> dict[str, Any]:
        from bachbot.analysis.style import compute_style_fingerprint

        result = {}
        for cid in ids.split(","):
            cid = cid.strip()
            if not cid:
                continue
            record = _resolve_corpus_record(cid)
            analysis_entry = record["analysis"]
            if analysis_entry:
                bundle = _json_path(Path(analysis_entry["bundle_path"]))
                fp = compute_style_fingerprint(bundle)
                result[cid] = fp.model_dump(mode="json")
        return result

    @app.get("/research/corpus-baseline")
    def research_corpus_baseline() -> dict[str, Any]:
        from bachbot.analysis.style import load_corpus_fingerprints
        import numpy as np

        fps = load_corpus_fingerprints(limit=361)
        if not fps:
            return {"mean": {}, "std": {}, "count": 0}
        all_features = list(fps[0].features.keys())
        matrix = [[fp.features.get(k, 0.0) for k in all_features] for fp in fps]
        arr = np.array(matrix, dtype=float) if matrix else np.zeros((0, len(all_features)))
        mean = dict(zip(all_features, arr.mean(axis=0).tolist())) if len(arr) > 0 else {}
        std = dict(zip(all_features, arr.std(axis=0).tolist())) if len(arr) > 0 else {}
        return {"mean": mean, "std": std, "count": len(fps)}

    @app.get("/research/anomalies")
    def research_anomalies() -> dict[str, Any]:
        from bachbot.analysis.style import load_corpus_fingerprints, compute_anomaly

        fps = load_corpus_fingerprints(limit=361)
        if not fps:
            return {"anomalies": []}
        results = []
        for fp in fps:
            others = [f for f in fps if f.work_id != fp.work_id]
            report = compute_anomaly(fp, others)
            results.append(report.model_dump(mode="json"))
        results.sort(key=lambda r: r["anomaly_score"], reverse=True)
        return {"anomalies": results[:50]}

    @app.get("/research/patterns")
    def research_patterns(length: int = Query(3, ge=2, le=6)) -> dict[str, Any]:
        from collections import Counter

        ngrams: Counter[tuple[str, ...]] = Counter()
        for record in _corpus_index()["entries"]:
            analysis_entry = record["analysis"]
            if not analysis_entry:
                continue
            report = _json_path(Path(analysis_entry["analysis_path"]))
            harmony = report.get("harmony", [])
            labels = [h["roman_numeral_candidate_set"][0] for h in harmony if h.get("roman_numeral_candidate_set")]
            for i in range(len(labels) - length + 1):
                ngrams[tuple(labels[i:i + length])] += 1

        top = ngrams.most_common(30)
        return {"length": length, "patterns": [{"progression": list(p), "count": c} for p, c in top]}

    @app.get("/research/patterns/search")
    def research_patterns_search(progression: str = Query(..., description="Comma-separated, e.g. I,IV,V")) -> dict[str, Any]:
        target = [c.strip() for c in progression.split(",") if c.strip()]
        if not target:
            return {"matches": []}

        matches = []
        for record in _corpus_index()["entries"]:
            analysis_entry = record["analysis"]
            if not analysis_entry:
                continue
            normalized_entry = record["normalized"]
            report = _json_path(Path(analysis_entry["analysis_path"]))
            harmony = report.get("harmony", [])
            labels = [h["roman_numeral_candidate_set"][0] for h in harmony if h.get("roman_numeral_candidate_set")]
            for i in range(len(labels) - len(target) + 1):
                if labels[i:i + len(target)] == target:
                    matches.append({
                        "chorale_id": _chorale_id(normalized_entry),
                        "title": normalized_entry.get("title", ""),
                        "onset_index": i,
                    })
                    break
        return {"progression": target, "matches": matches}

    @app.get("/research/embeddings")
    def research_embeddings() -> dict[str, Any]:
        from bachbot.exports.embeddings import compute_corpus_embeddings

        result = compute_corpus_embeddings(limit=361)
        return result

    @app.get("/research/harmonic-rhythm/{chorale_id}")
    def research_harmonic_rhythm(chorale_id: str) -> dict[str, Any]:
        record = _resolve_corpus_record(chorale_id)
        analysis_entry = record["analysis"]
        if not analysis_entry:
            raise HTTPException(status_code=404, detail="No analysis available")
        report = _json_path(Path(analysis_entry["analysis_path"]))
        return {
            "chorale_id": _chorale_id(record["normalized"]),
            "harmonic_rhythm": report.get("harmonic_rhythm", {}),
            "harmony": report.get("harmony", []),
            "cadences": report.get("cadences", []),
        }

    # ─── Benchmark endpoints ─────────────────────────────────────────

    @app.get("/benchmark/history")
    def benchmark_history() -> dict[str, Any]:
        from bachbot.benchmark.dashboard import load_benchmark_history

        history = load_benchmark_history()
        return {"snapshots": history}

    @app.get("/benchmark/latest")
    def benchmark_latest() -> dict[str, Any]:
        from bachbot.benchmark.dashboard import load_benchmark_history

        history = load_benchmark_history()
        if not history:
            return {"snapshot": None}
        return {"snapshot": history[-1]}

    @app.post("/benchmark/run")
    def benchmark_run(sample_size: int = Query(10, ge=1, le=50)) -> dict[str, Any]:
        from bachbot.benchmark.dashboard import load_benchmark_history, compare_benchmark_runs

        started = perf_counter()
        # Import and run benchmark
        from bachbot.benchmark import run_benchmark

        report = run_benchmark(sample_size=sample_size)
        history = load_benchmark_history()
        alerts: list[dict[str, Any]] = []
        if len(history) >= 2:
            alerts = compare_benchmark_runs(history[-1], history[-2])
        return {
            "report": report,
            "alerts": alerts,
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
        }

    # ─── Evaluation endpoints ────────────────────────────────────────

    class EvalStartRequest(BachbotModel):
        evaluator_id: str
        pair_count: int = 10

    class EvalRateRequest(BachbotModel):
        pair_id: str
        evaluator_id: str
        musicality_a: int
        musicality_b: int
        authenticity_a: int
        authenticity_b: int
        voice_leading_a: int
        voice_leading_b: int
        identified_original: str = "unsure"
        notes: str = ""

    def _eval_dir() -> Path:
        return get_settings().derived_dir / "evaluations"

    def _load_or_create_campaign(pair_count: int) -> dict[str, Any]:
        """Load cached campaign or generate one deterministically."""
        import random as _rng_mod
        import uuid

        eval_dir = _eval_dir()
        campaign_path = eval_dir / "campaign.json"

        if campaign_path.exists():
            campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
            if len(campaign["pairs"]) >= pair_count:
                return campaign

        eval_dir.mkdir(parents=True, exist_ok=True)
        summaries = _corpus_summaries()
        rng = _rng_mod.Random(42)
        count = min(pair_count, len(summaries))
        selected = rng.sample(summaries, count)

        pairs: list[dict[str, Any]] = []
        ground_truth: dict[str, bool] = {}

        for summary in selected:
            try:
                record = _resolve_corpus_record(summary.chorale_id)
            except HTTPException:
                continue
            original_graph = EventGraph.model_validate(
                _json_path(Path(record["normalized"]["event_graph_path"]))
            )
            try:
                composed_graph, _artifact, _report = compose_chorale_study(original_graph)
            except Exception:
                continue

            pair_id = uuid.UUID(int=rng.getrandbits(128), version=4).hex[:12]
            a_is_original = rng.choice([True, False])
            graph_a = original_graph if a_is_original else composed_graph
            graph_b = composed_graph if a_is_original else original_graph

            ground_truth[pair_id] = a_is_original
            pairs.append({
                "pair_id": pair_id,
                "chorale_id": summary.chorale_id,
                "event_graph_a": graph_a.model_dump(mode="json"),
                "event_graph_b": graph_b.model_dump(mode="json"),
            })

        campaign = {"pairs": pairs, "ground_truth": ground_truth}
        campaign_path.write_text(json.dumps(campaign), encoding="utf-8")
        return campaign

    @app.post("/evaluation/start")
    def evaluation_start(payload: EvalStartRequest) -> dict[str, Any]:
        campaign = _load_or_create_campaign(payload.pair_count)
        session_id = f"session-{payload.evaluator_id}-{int(perf_counter() * 1000)}"

        # Return pairs without ground truth (blind test)
        blind_pairs = [
            {"pair_id": p["pair_id"], "event_graph_a": p["event_graph_a"], "event_graph_b": p["event_graph_b"]}
            for p in campaign["pairs"][:payload.pair_count]
        ]
        return {
            "session_id": session_id,
            "evaluator_id": payload.evaluator_id,
            "pairs": blind_pairs,
        }

    @app.post("/evaluation/rate")
    def evaluation_rate(payload: EvalRateRequest) -> dict[str, Any]:
        from datetime import datetime, timezone

        ratings_dir = _eval_dir() / "ratings"
        ratings_dir.mkdir(parents=True, exist_ok=True)

        rating_data = {
            "pair_id": payload.pair_id,
            "evaluator_id": payload.evaluator_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "musicality_a": payload.musicality_a,
            "musicality_b": payload.musicality_b,
            "authenticity_a": payload.authenticity_a,
            "authenticity_b": payload.authenticity_b,
            "voice_leading_a": payload.voice_leading_a,
            "voice_leading_b": payload.voice_leading_b,
            "identified_original": payload.identified_original,
            "notes": payload.notes,
        }
        rating_path = ratings_dir / f"{payload.evaluator_id}_{payload.pair_id}.json"
        rating_path.write_text(json.dumps(rating_data, indent=2), encoding="utf-8")
        return {"status": "recorded", "pair_id": payload.pair_id}

    @app.get("/evaluation/results")
    def evaluation_results() -> dict[str, Any]:
        from bachbot.evaluation.models import EvaluationPair, EvaluationRating, EvaluationSession
        from bachbot.evaluation.protocol import analyze_evaluation

        eval_dir = _eval_dir()
        ratings_dir = eval_dir / "ratings"
        campaign_path = eval_dir / "campaign.json"

        if not ratings_dir.exists() or not campaign_path.exists():
            return {"total_pairs": 0, "total_evaluators": 0, "total_ratings": 0,
                    "avg_musicality_original": 0.0, "avg_musicality_generated": 0.0,
                    "avg_authenticity_original": 0.0, "avg_authenticity_generated": 0.0,
                    "avg_voice_leading_original": 0.0, "avg_voice_leading_generated": 0.0,
                    "identification_accuracy": 0.0, "krippendorff_alpha": 0.0}

        campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
        ground_truth: dict[str, bool] = campaign.get("ground_truth", {})

        pairs = [
            EvaluationPair(
                pair_id=pid,
                chorale_a_id=pid,
                chorale_b_id=pid,
                chorale_a_is_original=a_is_orig,
                chorale_a_midi_path="",
                chorale_b_midi_path="",
            )
            for pid, a_is_orig in ground_truth.items()
        ]

        # Group ratings by evaluator
        evaluator_ratings: dict[str, list[EvaluationRating]] = {}
        for rating_path in ratings_dir.glob("*.json"):
            try:
                rd = json.loads(rating_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                continue
            eid = rd["evaluator_id"]
            evaluator_ratings.setdefault(eid, []).append(
                EvaluationRating(
                    pair_id=rd["pair_id"],
                    evaluator_id=eid,
                    timestamp=rd["timestamp"],
                    musicality_a=rd["musicality_a"],
                    musicality_b=rd["musicality_b"],
                    authenticity_a=rd["authenticity_a"],
                    authenticity_b=rd["authenticity_b"],
                    voice_leading_a=rd["voice_leading_a"],
                    voice_leading_b=rd["voice_leading_b"],
                    identified_original=rd["identified_original"],
                    notes=rd.get("notes", ""),
                )
            )

        sessions = [
            EvaluationSession(
                session_id=f"session-{eid}",
                evaluator_id=eid,
                pairs=pairs,
                ratings=ratings,
            )
            for eid, ratings in evaluator_ratings.items()
        ]

        summary = analyze_evaluation(sessions)
        return summary.model_dump(mode="json")

    # ─── Encyclopedia stats endpoint ─────────────────────────────────

    @app.get("/encyclopedia/stats")
    def encyclopedia_stats() -> dict[str, Any]:
        summaries = _corpus_summaries()
        total = len(summaries)
        if total == 0:
            return {}

        total_cadences = sum(s.cadence_count for s in summaries)
        total_harmony = sum(s.harmonic_event_count for s in summaries)
        cadence_type_counts: dict[str, int] = {}
        key_counts: dict[str, int] = {}
        for s in summaries:
            for ct in s.cadence_types:
                cadence_type_counts[ct] = cadence_type_counts.get(ct, 0) + 1
            if s.key:
                mode = "major" if "major" in s.key.lower() else "minor"
                key_counts[mode] = key_counts.get(mode, 0) + 1

        return {
            "total_chorales": total,
            "avg_cadences": round(total_cadences / total, 1),
            "avg_harmonic_events": round(total_harmony / total, 1),
            "cadence_type_distribution": dict(sorted(cadence_type_counts.items(), key=lambda x: -x[1])),
            "key_mode_distribution": key_counts,
            "avg_unique_chords": round(sum(s.harmonic_event_count for s in summaries) / total, 1),
            "total_keys": len({s.key for s in summaries if s.key}),
        }

    return app


def create_production_app() -> FastAPI:
    """Wrap the API app with SPA serving when web/dist is available."""
    api = create_app()
    # Check multiple candidate paths for web/dist (handles both editable and
    # installed-package layouts)
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "web" / "dist",
        get_settings().workspace_root / "web" / "dist",
    ]
    _web_dist = next((p for p in candidates if p.is_dir()), None)
    if _web_dist is None:
        return api

    root = FastAPI(title="Bachbot")
    root.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    root.mount("/api", api)
    root.mount("/assets", StaticFiles(directory=str(_web_dist / "assets")), name="static")

    @root.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        file_path = _web_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_web_dist / "index.html"))

    return root


# `api_app` is the raw API (for tests); `app` is the production app (API + SPA)
api_app = create_app()
app = create_production_app()

__all__ = ["api_app", "app", "create_app", "create_production_app"]
