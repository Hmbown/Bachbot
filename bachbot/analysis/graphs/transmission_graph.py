from __future__ import annotations

from bachbot.models.source import Source
from bachbot.models.work import Work


def build_transmission_graph(work: Work, sources: list[Source]) -> dict[str, list[str]]:
    return {work.work_id: [source.source_id for source in sources]}

