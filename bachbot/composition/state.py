"""Unified composition state with active-note semantics.

Provides the same ``onset <= offset < onset + duration`` predicate as
``EventGraph.active_notes_at()``, ensuring composer and validator always
agree on which notes are sounding at any given offset.
"""

from __future__ import annotations

from bachbot.models.base import TypedNote


class CompositionState:
    """Mutable note container for in-progress composition.

    The parallel checker and nonharmonic-tone inserters query this object
    instead of building ad-hoc offset dicts, so held notes (suspensions,
    ties) are always visible — exactly matching the validator's view.
    """

    __slots__ = ("_notes",)

    def __init__(self, notes: list[TypedNote] | None = None) -> None:
        self._notes: list[TypedNote] = list(notes) if notes else []

    # ── mutators ──────────────────────────────────────────────────────

    def add_note(self, note: TypedNote) -> None:
        self._notes.append(note)

    def remove_note(self, note: TypedNote) -> None:
        self._notes.remove(note)

    def replace_note(self, old: TypedNote, new_notes: list[TypedNote]) -> None:
        """Remove *old* and insert *new_notes* in its place."""
        self._notes.remove(old)
        self._notes.extend(new_notes)

    # ── queries ───────────────────────────────────────────────────────

    @property
    def notes(self) -> list[TypedNote]:
        return list(self._notes)

    def active_notes_at(self, offset: float) -> list[TypedNote]:
        """All notes sounding at *offset*.

        Uses the identical predicate as ``EventGraph.active_notes_at``:
        ``note.offset_quarters <= offset < note.offset_quarters + note.duration_quarters``
        """
        return [
            n for n in self._notes
            if n.offset_quarters <= offset < n.offset_quarters + n.duration_quarters
        ]

    def active_midi_at(self, offset: float) -> dict[str, int]:
        """Return ``{voice_id: midi}`` for every pitched note sounding at *offset*.

        This is the drop-in replacement for the old ``previous_mapping`` dict
        used by ``_has_forbidden_parallel()``.
        """
        result: dict[str, int] = {}
        for n in self._notes:
            if (
                n.midi is not None
                and n.offset_quarters <= offset < n.offset_quarters + n.duration_quarters
            ):
                result[n.voice_id] = n.midi
        return result
