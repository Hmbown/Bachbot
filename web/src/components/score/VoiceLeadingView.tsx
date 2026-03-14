import { useMemo } from 'react';
import type { EventGraph } from '@/types';
import { normalizeVoiceId, VOICE_COLORS, VOICE_NAMES } from '@/types';

interface VoiceLeadingViewProps {
  graph: EventGraph;
  width?: number;
  height?: number;
}

const PADDING = { top: 40, right: 20, bottom: 30, left: 50 };

export function VoiceLeadingView({ graph, width = 1200, height = 350 }: VoiceLeadingViewProps) {
  const { voiceNotes, plotWidth, plotHeight, midiRange, totalDuration } = useMemo(() => {
    const pitched = graph.notes.filter((n) => !n.is_rest && n.midi > 0);
    if (pitched.length === 0) {
      return {
        voiceNotes: {} as Record<string, typeof pitched>,
        plotWidth: width - PADDING.left - PADDING.right,
        plotHeight: height - PADDING.top - PADDING.bottom,
        midiRange: [60, 72] as [number, number],
        totalDuration: 4,
      };
    }
    const midis = pitched.map((n) => n.midi);
    const minMidi = Math.min(...midis) - 2;
    const maxMidi = Math.max(...midis) + 2;
    const maxOnset = Math.max(...pitched.map((n) => n.offset_quarters + n.duration_quarters));

    const byVoice: Record<string, typeof pitched> = {};
    for (const n of pitched) {
      const v = normalizeVoiceId(n.voice_id);
      if (!byVoice[v]) byVoice[v] = [];
      byVoice[v].push(n);
    }
    for (const v of Object.keys(byVoice)) {
      byVoice[v].sort((a, b) => a.offset_quarters - b.offset_quarters);
    }

    return {
      voiceNotes: byVoice,
      plotWidth: width - PADDING.left - PADDING.right,
      plotHeight: height - PADDING.top - PADDING.bottom,
      midiRange: [minMidi, maxMidi] as [number, number],
      totalDuration: maxOnset,
    };
  }, [graph, width, height]);

  const xScale = (onset: number) => PADDING.left + (onset / totalDuration) * plotWidth;
  const yScale = (midi: number) => PADDING.top + plotHeight - ((midi - midiRange[0]) / (midiRange[1] - midiRange[0])) * plotHeight;

  // Detect parallel 5ths/8ves between outer voices (S and B)
  const parallels = useMemo(() => {
    const sNotes = voiceNotes['S'] || [];
    const bNotes = voiceNotes['B'] || [];
    const issues: { onset: number; type: string }[] = [];

    for (let i = 0; i < sNotes.length - 1; i++) {
      const s1 = sNotes[i], s2 = sNotes[i + 1];
      // Find bass notes at same onset
      const b1 = bNotes.find((n) => Math.abs(n.offset_quarters - s1.offset_quarters) < 0.01);
      const b2 = bNotes.find((n) => Math.abs(n.offset_quarters - s2.offset_quarters) < 0.01);
      if (!b1 || !b2) continue;

      const interval1 = Math.abs(s1.midi - b1.midi) % 12;
      const interval2 = Math.abs(s2.midi - b2.midi) % 12;
      if (interval1 === interval2 && (interval1 === 0 || interval1 === 7)) {
        if (s1.midi !== s2.midi || b1.midi !== b2.midi) {
          issues.push({ onset: s2.offset_quarters, type: interval1 === 0 ? 'P8' : 'P5' });
        }
      }
    }
    return issues;
  }, [voiceNotes]);

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="bg-surface rounded-lg border border-border">
      <text x={width / 2} y={20} textAnchor="middle" fontSize={13} fontWeight={600} fill="var(--color-ink)" style={{ fontFamily: 'var(--font-serif)' }}>
        Voice-Leading Connections
      </text>

      {/* Connection lines per voice */}
      {Object.entries(voiceNotes).map(([voice, notes]) => {
        const lines: React.ReactElement[] = [];
        for (let i = 0; i < notes.length - 1; i++) {
          const n1 = notes[i];
          const n2 = notes[i + 1];
          const x1 = xScale(n1.offset_quarters + n1.duration_quarters / 2);
          const x2 = xScale(n2.offset_quarters + n2.duration_quarters / 2);
          const y1 = yScale(n1.midi);
          const y2 = yScale(n2.midi);
          const interval = Math.abs(n2.midi - n1.midi);
          const isStep = interval <= 2;
          const isLeap = interval > 2;

          lines.push(
            <line
              key={`${voice}-${i}`}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={isLeap ? 'var(--color-suspension)' : 'var(--color-neighbor)'}
              strokeWidth={isStep ? 1 : 1.5}
              opacity={0.6}
            />
          );
        }
        return <g key={voice}>{lines}</g>;
      })}

      {/* Note dots */}
      {Object.entries(voiceNotes).map(([voice, notes]) => (
        <g key={`dots-${voice}`}>
          {notes.map((n, i) => (
            <circle
              key={i}
              cx={xScale(n.offset_quarters + n.duration_quarters / 2)}
              cy={yScale(n.midi)}
              r={3}
              fill={VOICE_COLORS[voice] || '#888'}
              opacity={0.9}
            >
              <title>{`${n.pitch} (${VOICE_NAMES[voice]})\nMeasure ${n.measure_number}`}</title>
            </circle>
          ))}
        </g>
      ))}

      {/* Parallel violation markers */}
      {parallels.map((p, i) => (
        <g key={`par-${i}`}>
          <line
            x1={xScale(p.onset)} y1={PADDING.top}
            x2={xScale(p.onset)} y2={height - PADDING.bottom}
            stroke="var(--color-structural)" strokeWidth={2} opacity={0.4} strokeDasharray="4,2"
          />
          <text
            x={xScale(p.onset)} y={PADDING.top - 5}
            textAnchor="middle" fontSize={9} fill="var(--color-structural)" fontWeight={600}
          >
            {p.type}
          </text>
        </g>
      ))}

      {/* Legend */}
      <g transform={`translate(${PADDING.left}, ${height - 12})`}>
        <rect width={8} height={3} fill="var(--color-neighbor)" rx={1} />
        <text x={12} y={4} fontSize={8} fill="var(--color-ink-muted)">Stepwise</text>
        <g transform="translate(70,0)">
          <rect width={8} height={3} fill="var(--color-suspension)" rx={1} />
          <text x={12} y={4} fontSize={8} fill="var(--color-ink-muted)">Leap</text>
        </g>
        <g transform="translate(120,0)">
          <rect width={8} height={3} fill="var(--color-structural)" rx={1} />
          <text x={12} y={4} fontSize={8} fill="var(--color-ink-muted)">Parallel 5th/8ve</text>
        </g>
        {(['S', 'A', 'T', 'B'] as const).map((v, i) => (
          <g key={v} transform={`translate(${250 + i * 55}, 0)`}>
            <circle cx={4} cy={1} r={3} fill={VOICE_COLORS[v]} />
            <text x={12} y={4} fontSize={8} fill="var(--color-ink-muted)">{VOICE_NAMES[v]}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
