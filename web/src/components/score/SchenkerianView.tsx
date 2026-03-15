import { useState, useMemo } from 'react';
import type { EventGraph, AnalysisReport } from '@/types';
import { normalizeVoiceId, VOICE_COLORS } from '@/types';

type ReductionLayer = 'background' | 'middleground' | 'foreground';

interface SchenkerianViewProps {
  graph: EventGraph;
  report: AnalysisReport;
  width?: number;
  height?: number;
}

const PADDING = { top: 40, right: 20, bottom: 30, left: 50 };

const LAYER_COLORS: Record<ReductionLayer, { fill: string; opacity: number; label: string }> = {
  background: { fill: 'var(--color-structural)', opacity: 0.9, label: 'Structural tones (Urlinie + Bassbrechung)' },
  middleground: { fill: 'var(--color-passing)', opacity: 0.7, label: 'Prolongational arpeggiation + linear progressions' },
  foreground: { fill: 'var(--color-ink-light)', opacity: 0.5, label: 'Full diminution layer' },
};

export function SchenkerianView({ graph, report, width = 1200, height = 350 }: SchenkerianViewProps) {
  const [activeLayer, setActiveLayer] = useState<ReductionLayer>('foreground');

  const schenkerian = report.schenkerian as Record<string, unknown> || {};
  const layers: Record<ReductionLayer, number[]> = {
    background: (schenkerian.background as number[]) || [],
    middleground: (schenkerian.middleground as number[]) || [],
    foreground: (schenkerian.foreground as number[]) || [],
  };

  const { notes, plotWidth, plotHeight, midiRange, totalDuration } = useMemo(() => {
    const pitched = graph.notes.filter((n) => !n.is_rest && n.midi > 0);
    if (pitched.length === 0) {
      return { notes: [], plotWidth: width - PADDING.left - PADDING.right, plotHeight: height - PADDING.top - PADDING.bottom, midiRange: [60, 72] as [number, number], totalDuration: 4 };
    }
    const midis = pitched.map((n) => n.midi);
    const minMidi = Math.min(...midis) - 2;
    const maxMidi = Math.max(...midis) + 2;
    const maxOnset = Math.max(...pitched.map((n) => n.offset_quarters + n.duration_quarters));
    return { notes: pitched, plotWidth: width - PADDING.left - PADDING.right, plotHeight: height - PADDING.top - PADDING.bottom, midiRange: [minMidi, maxMidi] as [number, number], totalDuration: maxOnset };
  }, [graph, width, height]);

  const xScale = (onset: number) => PADDING.left + (onset / totalDuration) * plotWidth;
  const yScale = (midi: number) => PADDING.top + plotHeight - ((midi - midiRange[0]) / (midiRange[1] - midiRange[0])) * plotHeight;
  const noteHeight = Math.max(2, Math.min(8, plotHeight / (midiRange[1] - midiRange[0])));

  // Determine which note indices are structural
  const structuralIndices = new Set(layers.background);
  const prolongIndices = new Set(layers.middleground);

  const getNoteStyle = (idx: number) => {
    if (activeLayer === 'background') {
      if (structuralIndices.has(idx)) return { fill: LAYER_COLORS.background.fill, opacity: 0.9, size: 1.5 };
      return { fill: 'var(--color-border)', opacity: 0.15, size: 0.8 };
    }
    if (activeLayer === 'middleground') {
      if (structuralIndices.has(idx)) return { fill: LAYER_COLORS.background.fill, opacity: 0.9, size: 1.5 };
      if (prolongIndices.has(idx)) return { fill: LAYER_COLORS.middleground.fill, opacity: 0.7, size: 1.2 };
      return { fill: 'var(--color-border)', opacity: 0.15, size: 0.8 };
    }
    // Foreground: show all with voice colors
    const voice = normalizeVoiceId(notes[idx]?.voice_id || 'S');
    if (structuralIndices.has(idx)) return { fill: LAYER_COLORS.background.fill, opacity: 0.9, size: 1.5 };
    if (prolongIndices.has(idx)) return { fill: LAYER_COLORS.middleground.fill, opacity: 0.7, size: 1.2 };
    return { fill: VOICE_COLORS[voice], opacity: 0.5, size: 1.0 };
  };

  // Draw arcs between consecutive structural tones
  const drawArcs = (indices: number[], color: string) => {
    const arcs: React.ReactElement[] = [];
    const sorted = [...indices].sort((a, b) => (notes[a]?.offset_quarters || 0) - (notes[b]?.offset_quarters || 0));
    for (let i = 0; i < sorted.length - 1; i++) {
      const n1 = notes[sorted[i]];
      const n2 = notes[sorted[i + 1]];
      if (!n1 || !n2) continue;
      const x1 = xScale(n1.offset_quarters + n1.duration_quarters / 2);
      const x2 = xScale(n2.offset_quarters + n2.duration_quarters / 2);
      const y1 = yScale(n1.midi);
      const y2 = yScale(n2.midi);
      const mx = (x1 + x2) / 2;
      const my = Math.min(y1, y2) - 15;
      arcs.push(
        <path
          key={`arc-${sorted[i]}-${sorted[i + 1]}`}
          d={`M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          opacity={0.6}
        />
      );
    }
    return arcs;
  };

  const hasData = layers.background.length > 0 || layers.middleground.length > 0;

  return (
    <div>
      {/* Layer toggle */}
      <div className="flex gap-2 mb-3">
        {(['background', 'middleground', 'foreground'] as ReductionLayer[]).map((layer) => (
          <button
            key={layer}
            onClick={() => setActiveLayer(layer)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeLayer === layer
                ? 'bg-primary-dark text-white'
                : 'bg-surface border border-border text-ink-light hover:text-ink'
            }`}
          >
            {layer.charAt(0).toUpperCase() + layer.slice(1)}
          </button>
        ))}
        <span className="text-xs text-ink-muted self-center ml-2">
          {LAYER_COLORS[activeLayer].label}
        </span>
      </div>

      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="bg-surface rounded-lg border border-border">
        <text x={width / 2} y={20} textAnchor="middle" fontSize={13} fontWeight={600} fill="var(--color-ink)" style={{ fontFamily: 'var(--font-serif)' }}>
          Schenkerian Reduction — {activeLayer}
        </text>

        {/* Notes */}
        {notes.map((note, i) => {
          const style = getNoteStyle(i);
          const x = xScale(note.offset_quarters);
          const w = Math.max(2, (note.duration_quarters / totalDuration) * plotWidth - 1);
          const y = yScale(note.midi) - (noteHeight * style.size) / 2;
          return (
            <rect key={i} x={x} y={y} width={w * style.size} height={noteHeight * style.size} fill={style.fill} opacity={style.opacity} rx={1} />
          );
        })}

        {/* Arcs for structural connections */}
        {hasData && (activeLayer === 'background' || activeLayer === 'middleground') && drawArcs([...structuralIndices], LAYER_COLORS.background.fill)}
        {hasData && activeLayer === 'middleground' && drawArcs([...prolongIndices], LAYER_COLORS.middleground.fill)}

        {/* Legend */}
        <g transform={`translate(${PADDING.left}, ${height - 15})`}>
          {Object.entries(LAYER_COLORS).map(([key, val], i) => (
            <g key={key} transform={`translate(${i * 130}, 0)`}>
              <rect width={8} height={8} fill={val.fill} opacity={val.opacity} rx={1} />
              <text x={12} y={7} fontSize={8} fill="var(--color-ink-muted)">{key}</text>
            </g>
          ))}
        </g>
      </svg>

      {!hasData && (
        <p className="text-xs text-ink-muted mt-2">No Schenkerian reduction data available for this chorale.</p>
      )}
      <p className="text-xs text-ink-muted mt-2 italic">
        Computational heuristic, not a definitive analysis. Schenkerian reduction is interpretive — qualified analysts can disagree about the structural levels of the same piece.
      </p>
    </div>
  );
}
