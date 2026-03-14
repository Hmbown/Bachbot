"""BachBench: comprehensive composition evaluation benchmark suite."""

from bachbot.benchmark.protocol import BenchTask, SuiteResult, TaskInput, TaskOutput, TaskResult
from bachbot.benchmark.complexity import ComplexityCorpusStats, ComplexityProfile, compute_complexity
from bachbot.benchmark.quality import (
    QualityCorpusStats,
    QualityReport,
    evaluate_generation,
    load_or_compute_quality_corpus_stats,
)
from bachbot.benchmark.runner import run_suite
from bachbot.benchmark.split import compute_split
from bachbot.benchmark.tasks import TASK_REGISTRY

__all__ = [
    "BenchTask",
    "ComplexityCorpusStats",
    "ComplexityProfile",
    "QualityCorpusStats",
    "QualityReport",
    "SuiteResult",
    "TASK_REGISTRY",
    "compute_complexity",
    "evaluate_generation",
    "load_or_compute_quality_corpus_stats",
    "TaskInput",
    "TaskOutput",
    "TaskResult",
    "compute_split",
    "run_suite",
]
