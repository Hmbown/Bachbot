from __future__ import annotations

from bachbot.composition.validators.hard_rules import validate_generated_chorale
from bachbot.encodings.event_graph import EventGraph


def score_generated_graph(graph: EventGraph) -> dict[str, object]:
    validation = validate_generated_chorale(graph)
    legality = 1.0 if validation["ok"] else 0.5
    return {"score": legality, "validation": validation}

