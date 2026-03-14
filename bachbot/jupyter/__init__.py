"""Jupyter integration for interactive Bachbot analysis visualization.

Public API
----------
>>> from bachbot.jupyter import display
>>> display(event_graph)         # auto-detects type
>>> display(analysis_report)
>>> display(evidence_bundle)

Or use specific renderers:
>>> from bachbot.jupyter.display import display_graph, display_analysis, display_bundle
"""

from __future__ import annotations

from typing import Any

from bachbot.analysis.pipeline import AnalysisReport
from bachbot.claims.bundle import EvidenceBundle
from bachbot.encodings.event_graph import EventGraph


def display(obj: Any, **kwargs: Any) -> Any:
    """Smart display: auto-detect EventGraph, AnalysisReport, or EvidenceBundle.

    Parameters
    ----------
    obj : EventGraph | AnalysisReport | EvidenceBundle
        The object to visualize.
    **kwargs
        Passed through to the appropriate display function (width, height, etc.).

    Returns
    -------
    IPython.display.HTML
        Inline SVG visualization suitable for Jupyter notebooks.
    """
    from bachbot.jupyter.display import display_analysis, display_bundle, display_graph

    if isinstance(obj, EventGraph):
        return display_graph(obj, **kwargs)
    if isinstance(obj, AnalysisReport):
        raise TypeError(
            "AnalysisReport requires an EventGraph for visualization. "
            "Use display_analysis(graph, analysis) instead."
        )
    if isinstance(obj, EvidenceBundle):
        return display_bundle(obj, **kwargs)
    raise TypeError(
        f"Cannot display object of type {type(obj).__name__}. "
        f"Expected EventGraph, AnalysisReport, or EvidenceBundle."
    )
