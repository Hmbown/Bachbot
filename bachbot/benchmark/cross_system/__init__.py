"""Cross-system composition benchmark: standardized test set, system adapters, and comparison evaluator."""

from bachbot.benchmark.cross_system.adapters import (
    BachbotAdapter,
    GroundTruthAdapter,
    MidiImportAdapter,
    Music21Adapter,
    SystemAdapter,
)
from bachbot.benchmark.cross_system.evaluator import (
    ComparisonReport,
    SystemScore,
    compare_systems,
    evaluate_harmonization,
    generate_comparison_table,
)
from bachbot.benchmark.cross_system.test_set import STANDARD_30_COUNT, BenchmarkMelody, build_standard_test_set

__all__ = [
    "BachbotAdapter",
    "ComparisonReport",
    "GroundTruthAdapter",
    "MidiImportAdapter",
    "Music21Adapter",
    "STANDARD_30_COUNT",
    "SystemAdapter",
    "SystemScore",
    "BenchmarkMelody",
    "build_standard_test_set",
    "compare_systems",
    "evaluate_harmonization",
    "generate_comparison_table",
]
