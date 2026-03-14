import { useMemo } from 'react';
import type { EventGraph, TypedNote } from '@/types';
import { normalizeVoiceId, VOICE_COLORS, VOICE_NAMES } from '@/types';

interface PianoRollProps {
  graph: EventGraph;
  width?: number;
  height?: number;
  showLegend?: boolean;
  highlightMeasure?: number;
  onNoteClick?: (note: TypedNote) => void;
  playbackBeat?: number;
}

const PADDING = { top: 40, right: 20, bottom: 30, left: 50 };

function formatKeyEstimate(keyEstimate: unknown): string | null {
  if (!keyEstimate) return null;
  if (typeof keyEstimate === 'string') return keyEstimate;
  if (typeof keyEstimate === 'object') {
    const record = keyEstimate as { tonic?: unknown; mode?: unknown };
    if (typeof record.tonic === 'string' && typeof record.mode === 'string') {
      return `${record.tonic} ${record.mode}`;
    }
  }
  return null;
}

export function PianoRoll({
  graph,
  width = 800,
  height = 400,
  showLegend = true,
  highlightMeasure,
  onNoteClick,
  playbackBeat,
}: PianoRollProps) {
  const { notes, plotWidth, plotHeight, midiRange, totalDuration, measureLines } = useMemo(() => {
    const pitched = graph.notes.filter((n) => !n.is_rest && n.midi > 0);
    if (pitched.length === 0) {
      return {
        notes: [],
        plotWidth: width - PADDING.left - PADDING.right,
        plotHeight: height - PADDING.top - PADDING.bottom,
        midiRange: [60, 72] as [number, number],
        totalDuration: 4,
        measureLines: [] as number[],
      };
    }

    const midis = pitched.map((n) => n.midi);
    const minMidi = Math.min(...midis) - 2;
    const maxMidi = Math.max(...midis) + 2;
    const maxOnset = Math.max(...pitched.map((n) => n.offset_quarters + n.duration_quarters));

    const measures = [...new Set(pitched.map((n) => n.measure_number))].sort((a, b) => a - b);
    const mLines: number[] = [];
    for (const m of measures) {
      const notesInMeasure = pitched.filter((n) => n.measure_number === m);
      if (notesInMeasure.length > 0) {
        mLines.push(Math.min(...notesInMeasure.map((n) => n.offset_quarters)));
      }
    }

    return {
      notes: pitched,
      plotWidth: width - PADDING.left - PADDING.right,
      plotHeight: height - PADDING.top - PADDING.bottom,
      midiRange: [minMidi, maxMidi] as [number, number],
      totalDuration: maxOnset,
      measureLines: mLines,
    };
  }, [graph, width, height]);

  const xScale = (onset: number) => PADDING.left + (onset / totalDuration) * plotWidth;
  const yScale = (midi: number) =>
    PADDING.top + plotHeight - ((midi - midiRange[0]) / (midiRange[1] - midiRange[0])) * plotHeight;
  const noteHeight = Math.max(2, Math.min(8, plotHeight / (midiRange[1] - midiRange[0])));

  // Octave grid lines
  const octaveLines = useMemo(() => {
    const lines: { midi: number; label: string }[] = [];
    for (let m = Math.ceil(midiRange[0] / 12) * 12; m <= midiRange[1]; m += 12) {
      const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
      lines.push({ midi: m, label: `${noteNames[m % 12]}${Math.floor(m / 12) - 1}` });
    }
    return lines;
  }, [midiRange]);

  const keyLabel = formatKeyEstimate(graph.metadata.key_estimate as unknown);
  const title = keyLabel
    ? `${graph.metadata.work_id || graph.metadata.encoding_id} — ${keyLabel}`
    : graph.metadata.work_id || graph.metadata.encoding_id;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="bg-paper-light rounded-lg border border-border shadow-[inset_0_1px_0_rgba(255,255,255,0.4)]"
      style={{ fontFamily: 'var(--font-sans)' }}
    >
      <rect x="0" y="0" width={width} height={height} fill="var(--color-paper-light)" rx="8" />

      {/* Title */}
      <text
        x={width / 2}
        y={20}
        textAnchor="middle"
        fontSize={13}
        fontWeight={600}
        fill="var(--color-ink-light)"
        style={{ fontFamily: 'var(--font-serif)' }}
      >
        {title}
      </text>

      {/* Octave grid */}
      {octaveLines.map(({ midi, label }) => (
        <g key={`oct-${midi}`}>
          <line
            x1={PADDING.left}
            y1={yScale(midi)}
            x2={width - PADDING.right}
            y2={yScale(midi)}
            stroke="var(--color-border-light)"
            strokeWidth={0.5}
            opacity={0.9}
          />
          <text
            x={PADDING.left - 4}
            y={yScale(midi) + 3}
            textAnchor="end"
            fontSize={9}
            fill="var(--color-ink-muted)"
          >
            {label}
          </text>
        </g>
      ))}

      {/* Measure lines */}
      {measureLines.map((onset, i) => (
        <g key={`m-${i}`}>
          <line
            x1={xScale(onset)}
            y1={PADDING.top}
            x2={xScale(onset)}
            y2={height - PADDING.bottom}
            stroke="var(--color-border)"
            strokeWidth={0.5}
            strokeDasharray="2,2"
            opacity={0.8}
          />
          <text
            x={xScale(onset)}
            y={height - PADDING.bottom + 14}
            textAnchor="middle"
            fontSize={8}
            fill="var(--color-ink-muted)"
          >
            {i + 1}
          </text>
        </g>
      ))}

      {/* Highlight measure */}
      {highlightMeasure != null && (() => {
        const mNotes = notes.filter((n) => n.measure_number === highlightMeasure);
        if (mNotes.length === 0) return null;
        const x1 = xScale(Math.min(...mNotes.map((n) => n.offset_quarters)));
        const x2 = xScale(Math.max(...mNotes.map((n) => n.offset_quarters + n.duration_quarters)));
        return (
          <rect
            x={x1}
            y={PADDING.top}
            width={x2 - x1}
            height={plotHeight}
            fill="var(--color-primary)"
            opacity={0.06}
          />
        );
      })()}

      {/* Notes */}
      {notes.map((note, i) => {
        const voice = normalizeVoiceId(note.voice_id);
        const color = VOICE_COLORS[voice];
        const x = xScale(note.offset_quarters);
        const w = Math.max(2, (note.duration_quarters / totalDuration) * plotWidth - 1);
        const y = yScale(note.midi) - noteHeight / 2;

        return (
          <rect
            key={`${note.voice_id}-${note.offset_quarters}-${note.midi}-${i}`}
            x={x}
            y={y}
            width={w}
            height={noteHeight}
            fill={color}
            opacity={0.85}
            rx={1}
            className={onNoteClick ? 'cursor-pointer hover:opacity-100' : ''}
            onClick={() => onNoteClick?.(note)}
          >
            <title>
              {`${note.pitch} (MIDI ${note.midi})\n${VOICE_NAMES[voice]}\nMeasure ${note.measure_number}, Beat ${note.beat}\nDuration: ${note.duration_quarters}q`}
            </title>
          </rect>
        );
      })}

      {/* Playback cursor */}
      {playbackBeat != null && playbackBeat > 0 && totalDuration > 0 && (
        <line
          x1={xScale(playbackBeat)}
          y1={PADDING.top}
          x2={xScale(playbackBeat)}
          y2={height - PADDING.bottom}
          stroke="var(--color-structural)"
          strokeWidth={2}
          opacity={0.8}
        />
      )}

      {/* Legend */}
      {showLegend && (
        <g transform={`translate(${width - PADDING.right - 182}, ${PADDING.top - 8})`}>
          <rect x="-8" y="-10" width="184" height="20" rx="10" fill="rgba(255,253,247,0.85)" stroke="var(--color-border)" />
          {(['S', 'A', 'T', 'B'] as const).map((voice, i) => (
            <g key={voice} transform={`translate(${i * 45}, 0)`}>
              <rect width={10} height={10} fill={VOICE_COLORS[voice]} rx={1} opacity={0.85} />
              <text x={13} y={9} fontSize={9} fill="var(--color-ink-light)">
                {VOICE_NAMES[voice]}
              </text>
            </g>
          ))}
        </g>
      )}
    </svg>
  );
}
