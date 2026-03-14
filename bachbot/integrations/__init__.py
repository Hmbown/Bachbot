"""Integration helpers for optional external toolkits."""

from bachbot.integrations.music21 import (
    Music21UnavailableError,
    event_graph_to_music21,
    key_pitch_class,
    music21_available,
    music21_to_event_graph,
)
from bachbot.integrations.pymusica import (
    PyMusicaBackendStatus,
    PyMusicaUnavailableError,
    ScoreIRUnsupportedError,
    configured_pymusica_src,
    event_graph_to_score_ir,
    pymusica_available,
    pymusica_backend_status,
    resolved_pymusica_src,
    score_ir_to_event_graph,
)

__all__ = [
    "Music21UnavailableError",
    "PyMusicaBackendStatus",
    "PyMusicaUnavailableError",
    "ScoreIRUnsupportedError",
    "configured_pymusica_src",
    "event_graph_to_music21",
    "event_graph_to_score_ir",
    "key_pitch_class",
    "music21_available",
    "music21_to_event_graph",
    "pymusica_available",
    "pymusica_backend_status",
    "resolved_pymusica_src",
    "score_ir_to_event_graph",
]
