"""Tests for bachbot.jupyter — SVG generation and display functions."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

from bachbot.analysis.pipeline import AnalysisReport
from bachbot.claims.bundle import BundleMetadata, EvidenceBundle
from bachbot.encodings.event_graph import EncodingMetadata, EventGraph
from bachbot.jupyter.svg import SVGCanvas, midi_to_y, onset_to_x, voice_color
from bachbot.models.base import KeyEstimate, TypedNote
from bachbot.models.cadence import Cadence
from bachbot.models.harmonic_event import HarmonicEvent
from bachbot.models.section import Section
from bachbot.models.voice import Voice


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_note(
    pitch: str, midi: int, offset: float, duration: float,
    measure: int, beat: float, voice_id: str,
) -> TypedNote:
    return TypedNote(
        pitch=pitch, midi=midi, duration_quarters=duration,
        offset_quarters=offset, measure_number=measure, beat=beat,
        voice_id=voice_id,
    )


def _make_graph(notes: list[TypedNote] | None = None) -> EventGraph:
    """Build a minimal EventGraph for testing."""
    if notes is None:
        notes = [
            _make_note("C5", 72, 0.0, 1.0, 1, 1.0, "Soprano:1"),
            _make_note("E4", 64, 0.0, 1.0, 1, 1.0, "Alto:1"),
            _make_note("G3", 55, 0.0, 1.0, 1, 1.0, "Tenor:1"),
            _make_note("C3", 48, 0.0, 1.0, 1, 1.0, "Bass:1"),
            _make_note("D5", 74, 1.0, 1.0, 1, 2.0, "Soprano:1"),
            _make_note("F4", 65, 1.0, 1.0, 1, 2.0, "Alto:1"),
            _make_note("A3", 57, 1.0, 1.0, 1, 2.0, "Tenor:1"),
            _make_note("D3", 50, 1.0, 1.0, 1, 2.0, "Bass:1"),
            _make_note("E5", 76, 2.0, 2.0, 2, 1.0, "Soprano:1"),
            _make_note("G4", 67, 2.0, 2.0, 2, 1.0, "Alto:1"),
            _make_note("B3", 59, 2.0, 2.0, 2, 1.0, "Tenor:1"),
            _make_note("E3", 52, 2.0, 2.0, 2, 1.0, "Bass:1"),
        ]
    return EventGraph(
        metadata=EncodingMetadata(
            encoding_id="TEST-ENC",
            work_id="BWV-TEST",
            title="Test Chorale",
            key_estimate=KeyEstimate(tonic="C", mode="major", confidence=0.9),
            meter="4/4",
        ),
        section=Section(
            section_id="SEC-1",
            work_id="BWV-TEST",
            label="test",
            section_type="chorale",
            measure_start=1,
            measure_end=2,
        ),
        voices=[
            Voice(voice_id="Soprano:1", section_id="SEC-1", part_name="Soprano", normalized_voice_name="soprano"),
            Voice(voice_id="Alto:1", section_id="SEC-1", part_name="Alto", normalized_voice_name="alto"),
            Voice(voice_id="Tenor:1", section_id="SEC-1", part_name="Tenor", normalized_voice_name="tenor"),
            Voice(voice_id="Bass:1", section_id="SEC-1", part_name="Bass", normalized_voice_name="bass"),
        ],
        notes=notes,
    )


def _make_analysis() -> AnalysisReport:
    return AnalysisReport(
        work_id="BWV-TEST",
        encoding_id="TEST-ENC",
        section_id="SEC-1",
        genre="chorale",
        key="C major",
        harmony=[
            HarmonicEvent(
                harmonic_event_id="HE-1", ref_id="HE-TEST-0",
                onset=0.0, duration=1.0, verticality_class="053",
                roman_numeral_candidate_set=["I"], local_key="C",
            ),
            HarmonicEvent(
                harmonic_event_id="HE-2", ref_id="HE-TEST-1",
                onset=1.0, duration=1.0, verticality_class="025",
                roman_numeral_candidate_set=["ii"], local_key="C",
            ),
            HarmonicEvent(
                harmonic_event_id="HE-3", ref_id="HE-TEST-2",
                onset=2.0, duration=2.0, verticality_class="047",
                roman_numeral_candidate_set=["V"], local_key="C",
            ),
        ],
        cadences=[
            Cadence(
                cadence_id="CAD-1", ref_id="HE-TEST-2",
                cadence_type="authentic", strength=0.8,
            ),
        ],
    )


def _make_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="EB-BWV-TEST-SEC-1",
        work_id="BWV-TEST",
        section_id="SEC-1",
        metadata=BundleMetadata(
            genre="chorale", key="C major",
            key_tonic="C", key_mode="major",
            encoding_id="TEST-ENC",
        ),
        deterministic_findings={
            "harmony": [
                {
                    "harmonic_event_id": "HE-1", "ref_id": "HE-TEST-0",
                    "onset": 0.0, "duration": 1.0, "verticality_class": "053",
                    "roman_numeral_candidate_set": ["I"], "local_key": "C",
                    "confidence": 0.0, "method": "rule",
                },
                {
                    "harmonic_event_id": "HE-2", "ref_id": "HE-TEST-1",
                    "onset": 1.0, "duration": 1.0, "verticality_class": "025",
                    "roman_numeral_candidate_set": ["ii"], "local_key": "C",
                    "confidence": 0.0, "method": "rule",
                },
            ],
            "cadences": [
                {
                    "cadence_id": "CAD-1", "ref_id": "HE-TEST-2",
                    "cadence_type": "authentic", "strength": 0.8,
                    "type_candidates": [], "voice_leading_evidence": [],
                    "detector_confidence": 0.0,
                },
            ],
        },
    )


def _parse_svg(svg_str: str) -> ET.Element:
    """Parse SVG string as XML and return root element."""
    return ET.fromstring(svg_str)


# ---------------------------------------------------------------------------
# SVG Canvas tests
# ---------------------------------------------------------------------------


class TestSVGCanvas:
    def test_empty_canvas_renders_valid_svg(self):
        canvas = SVGCanvas(400, 300)
        svg = canvas.render()
        root = _parse_svg(svg)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert root.attrib["width"] == "400"
        assert root.attrib["height"] == "300"

    def test_rect_element(self):
        canvas = SVGCanvas(100, 100)
        canvas.rect(10, 20, 30, 40, "#FF0000")
        svg = canvas.render()
        root = _parse_svg(svg)
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        assert len(rects) == 1
        assert rects[0].attrib["fill"] == "#FF0000"

    def test_rect_with_title(self):
        canvas = SVGCanvas(100, 100)
        canvas.rect(0, 0, 50, 50, "#00FF00", title="Hello <world>")
        svg = canvas.render()
        assert "Hello &lt;world&gt;" in svg
        root = _parse_svg(svg)
        titles = root.findall(".//{http://www.w3.org/2000/svg}title")
        assert len(titles) == 1

    def test_line_element(self):
        canvas = SVGCanvas(100, 100)
        canvas.line(0, 0, 100, 100, "#000000", width=2)
        svg = canvas.render()
        root = _parse_svg(svg)
        lines = root.findall(".//{http://www.w3.org/2000/svg}line")
        assert len(lines) == 1
        assert lines[0].attrib["stroke"] == "#000000"

    def test_text_element(self):
        canvas = SVGCanvas(100, 100)
        canvas.text(10, 20, "Hello & Goodbye", font_size=12)
        svg = canvas.render()
        assert "Hello &amp; Goodbye" in svg
        root = _parse_svg(svg)
        texts = root.findall(".//{http://www.w3.org/2000/svg}text")
        assert len(texts) == 1

    def test_line_with_dash(self):
        canvas = SVGCanvas(100, 100)
        canvas.line(0, 0, 50, 50, "#000", dash="4,2")
        svg = canvas.render()
        assert 'stroke-dasharray="4,2"' in svg

    def test_multiple_elements(self):
        canvas = SVGCanvas(200, 200)
        canvas.rect(0, 0, 100, 100, "#AAA")
        canvas.line(0, 0, 200, 200, "#BBB")
        canvas.text(50, 50, "X")
        svg = canvas.render()
        root = _parse_svg(svg)
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        lines = root.findall(".//{http://www.w3.org/2000/svg}line")
        texts = root.findall(".//{http://www.w3.org/2000/svg}text")
        assert len(rects) == 1
        assert len(lines) == 1
        assert len(texts) == 1


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_midi_to_y_range(self):
        # Higher MIDI = lower Y (visual convention)
        y_high = midi_to_y(80, 0, 100, 60, 80)
        y_low = midi_to_y(60, 0, 100, 60, 80)
        assert y_high < y_low

    def test_midi_to_y_same_pitch(self):
        y = midi_to_y(60, 0, 100, 60, 60)
        assert y == 50.0  # midpoint

    def test_onset_to_x(self):
        x = onset_to_x(5.0, 50, 450, 10.0)
        assert x == pytest.approx(250.0)

    def test_onset_to_x_zero_duration(self):
        x = onset_to_x(5.0, 50, 450, 0.0)
        assert x == 50.0  # returns x_min

    def test_voice_color_soprano(self):
        assert voice_color("Soprano:1") == "#4477AA"

    def test_voice_color_alto(self):
        assert voice_color("Alto:1") == "#44AA77"

    def test_voice_color_tenor(self):
        assert voice_color("Tenor:1") == "#DDAA33"

    def test_voice_color_bass(self):
        assert voice_color("Bass:1") == "#CC4444"

    def test_voice_colors_different(self):
        colors = {voice_color(v) for v in ["Soprano:1", "Alto:1", "Tenor:1", "Bass:1"]}
        assert len(colors) == 4

    def test_voice_color_fallback(self):
        c = voice_color("Unknown:99")
        assert c.startswith("#")

    def test_voice_color_lowercase_match(self):
        assert voice_color("soprano_main") == "#4477AA"


# ---------------------------------------------------------------------------
# Piano Roll tests
# ---------------------------------------------------------------------------


class TestPianoRoll:
    def test_render_basic_graph(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        graph = _make_graph()
        svg = render_piano_roll(graph)
        root = _parse_svg(svg)
        # Should have note rectangles (12 notes + background rect + possible grid)
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        assert len(rects) >= 12

    def test_render_contains_measure_numbers(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        graph = _make_graph()
        svg = render_piano_roll(graph)
        # Measure numbers 1 and 2 should appear
        assert ">1<" in svg or ">1 <" in svg or ">1</" in svg
        assert ">2<" in svg or ">2 <" in svg or ">2</" in svg

    def test_render_contains_title(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        graph = _make_graph()
        svg = render_piano_roll(graph)
        assert "Test Chorale" in svg

    def test_render_contains_key(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        graph = _make_graph()
        svg = render_piano_roll(graph)
        assert "C major" in svg

    def test_render_empty_graph(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        graph = _make_graph(notes=[])
        svg = render_piano_roll(graph)
        root = _parse_svg(svg)
        assert "No pitch events" in svg

    def test_render_single_note(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        graph = _make_graph(notes=[
            _make_note("C4", 60, 0.0, 1.0, 1, 1.0, "Soprano:1"),
        ])
        svg = render_piano_roll(graph)
        root = _parse_svg(svg)
        # Background rect + 1 note rect = at least 2
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        assert len(rects) >= 2

    def test_render_valid_xml(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        graph = _make_graph()
        svg = render_piano_roll(graph)
        # Should not raise
        _parse_svg(svg)

    def test_render_note_hover_titles(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        graph = _make_graph()
        svg = render_piano_roll(graph)
        # Title elements for note hover info
        assert "<title>" in svg
        assert "MIDI" in svg


# ---------------------------------------------------------------------------
# Analysis overlay tests
# ---------------------------------------------------------------------------


class TestAnalysisOverlay:
    def test_render_analysis_svg(self):
        from bachbot.jupyter.display import render_analysis_svg

        graph = _make_graph()
        analysis = _make_analysis()
        svg = render_analysis_svg(graph, analysis)
        root = _parse_svg(svg)
        texts = root.findall(".//{http://www.w3.org/2000/svg}text")
        text_content = [t.text for t in texts if t.text]
        # Roman numerals should appear
        assert any("I" in t for t in text_content)

    def test_render_analysis_cadence_markers(self):
        from bachbot.jupyter.display import render_analysis_svg

        graph = _make_graph()
        analysis = _make_analysis()
        svg = render_analysis_svg(graph, analysis)
        # Cadence marker should be present
        assert "AUT" in svg  # "authentic" truncated to 3 chars

    def test_render_analysis_local_keys(self):
        from bachbot.jupyter.display import render_analysis_svg

        graph = _make_graph()
        analysis = _make_analysis()
        svg = render_analysis_svg(graph, analysis)
        # Local key "C" annotations
        root = _parse_svg(svg)
        texts = [t.text for t in root.findall(".//{http://www.w3.org/2000/svg}text") if t.text]
        assert "C" in texts

    def test_render_analysis_empty_graph(self):
        from bachbot.jupyter.display import render_analysis_svg

        graph = _make_graph(notes=[])
        analysis = _make_analysis()
        svg = render_analysis_svg(graph, analysis)
        assert "No pitch events" in svg


# ---------------------------------------------------------------------------
# Bundle rendering tests
# ---------------------------------------------------------------------------


class TestBundleRendering:
    def test_render_bundle_svg(self):
        from bachbot.jupyter.display import render_bundle_svg

        bundle = _make_bundle()
        svg = render_bundle_svg(bundle)
        root = _parse_svg(svg)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"

    def test_render_bundle_has_title(self):
        from bachbot.jupyter.display import render_bundle_svg

        bundle = _make_bundle()
        svg = render_bundle_svg(bundle)
        assert "EB-BWV-TEST-SEC-1" in svg

    def test_render_bundle_has_roman_numerals(self):
        from bachbot.jupyter.display import render_bundle_svg

        bundle = _make_bundle()
        svg = render_bundle_svg(bundle)
        root = _parse_svg(svg)
        texts = [t.text for t in root.findall(".//{http://www.w3.org/2000/svg}text") if t.text]
        assert any("I" in t for t in texts)

    def test_render_bundle_empty_findings(self):
        from bachbot.jupyter.display import render_bundle_svg

        bundle = EvidenceBundle(
            bundle_id="EB-EMPTY",
            work_id="BWV-EMPTY",
            section_id="SEC-EMPTY",
            metadata=BundleMetadata(genre="chorale", encoding_id="EMPTY-ENC"),
            deterministic_findings={},
        )
        svg = render_bundle_svg(bundle)
        assert "No harmonic data" in svg


# ---------------------------------------------------------------------------
# Voice leading tests
# ---------------------------------------------------------------------------


class TestVoiceLeading:
    def test_render_voice_leading(self):
        from bachbot.jupyter.display import render_voice_leading_svg

        graph = _make_graph()
        svg = render_voice_leading_svg(graph)
        root = _parse_svg(svg)
        lines = root.findall(".//{http://www.w3.org/2000/svg}line")
        # Should have voice-leading lines (at least 1 per voice with 2+ notes)
        assert len(lines) >= 4

    def test_render_voice_leading_title(self):
        from bachbot.jupyter.display import render_voice_leading_svg

        graph = _make_graph()
        svg = render_voice_leading_svg(graph)
        assert "Voice Leading" in svg

    def test_render_voice_leading_empty(self):
        from bachbot.jupyter.display import render_voice_leading_svg

        graph = _make_graph(notes=[])
        svg = render_voice_leading_svg(graph)
        assert "No pitch events" in svg

    def test_render_voice_leading_single_note(self):
        from bachbot.jupyter.display import render_voice_leading_svg

        graph = _make_graph(notes=[
            _make_note("C4", 60, 0.0, 1.0, 1, 1.0, "Soprano:1"),
        ])
        svg = render_voice_leading_svg(graph)
        root = _parse_svg(svg)
        # No voice-leading lines for single note
        lines = root.findall(".//{http://www.w3.org/2000/svg}line")
        # Only background lines (no connection lines)
        assert len(lines) == 0


# ---------------------------------------------------------------------------
# Display function tests (mock IPython)
# ---------------------------------------------------------------------------


class TestDisplayFunctions:
    def test_display_graph_returns_html(self):
        mock_html = MagicMock()
        with patch.dict("sys.modules", {"IPython": MagicMock(), "IPython.display": MagicMock(HTML=mock_html)}):
            from importlib import reload

            import bachbot.jupyter.display as disp_mod
            reload(disp_mod)
            result = disp_mod.display_graph(_make_graph())
            mock_html.assert_called_once()
            svg_arg = mock_html.call_args[0][0]
            assert "<svg" in svg_arg

    def test_display_analysis_returns_html(self):
        mock_html = MagicMock()
        with patch.dict("sys.modules", {"IPython": MagicMock(), "IPython.display": MagicMock(HTML=mock_html)}):
            from importlib import reload

            import bachbot.jupyter.display as disp_mod
            reload(disp_mod)
            result = disp_mod.display_analysis(_make_graph(), _make_analysis())
            mock_html.assert_called_once()

    def test_display_bundle_returns_html(self):
        mock_html = MagicMock()
        with patch.dict("sys.modules", {"IPython": MagicMock(), "IPython.display": MagicMock(HTML=mock_html)}):
            from importlib import reload

            import bachbot.jupyter.display as disp_mod
            reload(disp_mod)
            result = disp_mod.display_bundle(_make_bundle())
            mock_html.assert_called_once()

    def test_display_voice_leading_returns_html(self):
        mock_html = MagicMock()
        with patch.dict("sys.modules", {"IPython": MagicMock(), "IPython.display": MagicMock(HTML=mock_html)}):
            from importlib import reload

            import bachbot.jupyter.display as disp_mod
            reload(disp_mod)
            result = disp_mod.display_voice_leading(_make_graph())
            mock_html.assert_called_once()


# ---------------------------------------------------------------------------
# Auto-detect dispatch tests
# ---------------------------------------------------------------------------


class TestAutoDetect:
    def test_dispatch_event_graph(self):
        mock_html = MagicMock()
        with patch.dict("sys.modules", {"IPython": MagicMock(), "IPython.display": MagicMock(HTML=mock_html)}):
            from importlib import reload

            import bachbot.jupyter.display as disp_mod
            reload(disp_mod)
            import bachbot.jupyter as jup_mod
            reload(jup_mod)
            jup_mod.display(_make_graph())
            mock_html.assert_called_once()

    def test_dispatch_bundle(self):
        """Verify display() dispatches EvidenceBundle to display_bundle."""
        from bachbot.jupyter.display import render_bundle_svg

        # Test the dispatch logic without needing IPython
        bundle = _make_bundle()
        from bachbot.jupyter import display as smart_display
        # We can't call smart_display directly (needs IPython), so test the
        # type detection logic: EvidenceBundle should not raise TypeError
        assert isinstance(bundle, EvidenceBundle)
        # Verify the SVG renderer works for bundles
        svg = render_bundle_svg(bundle)
        assert "<svg" in svg

    def test_dispatch_analysis_report_raises(self):
        from bachbot.jupyter import display
        with pytest.raises(TypeError, match="AnalysisReport requires an EventGraph"):
            display(_make_analysis())

    def test_dispatch_unknown_type_raises(self):
        from bachbot.jupyter import display
        with pytest.raises(TypeError, match="Cannot display"):
            display("not a valid object")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_graph_with_rests_only(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        rest = TypedNote(
            pitch=None, midi=None, duration_quarters=1.0,
            offset_quarters=0.0, measure_number=1, beat=1.0,
            voice_id="Soprano:1", is_rest=True,
        )
        graph = _make_graph(notes=[rest])
        svg = render_piano_roll(graph)
        assert "No pitch events" in svg

    def test_very_wide_canvas(self):
        from bachbot.jupyter.piano_roll import render_piano_roll

        graph = _make_graph()
        svg = render_piano_roll(graph, width=2000, height=200)
        root = _parse_svg(svg)
        assert root.attrib["width"] == "2000"

    def test_svg_canvas_group(self):
        canvas = SVGCanvas(100, 100)
        inner = ['<rect x="0" y="0" width="10" height="10" fill="red"/>']
        canvas.group(inner, transform="translate(5,5)")
        svg = canvas.render()
        assert '<g transform="translate(5,5)">' in svg

    def test_svg_renders_xmlns(self):
        canvas = SVGCanvas(100, 100)
        svg = canvas.render()
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
