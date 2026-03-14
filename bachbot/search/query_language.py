from __future__ import annotations


def parse_query(query: str) -> dict[str, list[str]]:
    tokens = [token.strip() for token in query.replace(",", " ").split() if token.strip()]
    return {"tokens": tokens}

