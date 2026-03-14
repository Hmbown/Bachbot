"""Humdrum support placeholders."""

from __future__ import annotations


class HumdrumParser:
    def parse(self, path: str, *_args, **_kwargs):
        raise NotImplementedError("Humdrum parsing is planned but not implemented in v0.1.")
