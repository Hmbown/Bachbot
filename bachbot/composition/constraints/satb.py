from __future__ import annotations

from bachbot.analysis.chorale.satb import analyze_chorale_texture
from bachbot.encodings.event_graph import EventGraph


def validate_satb_constraints(graph: EventGraph) -> dict[str, object]:
    analysis = analyze_chorale_texture(graph)
    return {"ok": analysis["ranges_ok"] and analysis["spacing_ok"] and analysis["counterpoint"]["parallel_5ths"] == 0 and analysis["counterpoint"]["parallel_8ves"] == 0, "details": analysis}

