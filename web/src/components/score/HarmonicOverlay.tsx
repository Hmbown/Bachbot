import { useMemo } from 'react';
import type { EventGraph, HarmonicEvent, Cadence } from '@/types';

interface HarmonicOverlayProps {
  graph: EventGraph;
  harmony: HarmonicEvent[];
  cadences: Cadence[];
  width?: number;
  height?: number;
}

const PADDING = { left: 50, right: 20 };
const OVERLAY_HEIGHT = 60;

export function HarmonicOverlay({
  graph,
  harmony,
  cadences,
  width = 800,
  height = OVERLAY_HEIGHT,
}: HarmonicOverlayProps) {
  const { totalDuration, plotWidth } = useMemo(() => {
    const pitched = graph.notes.filter((n) => !n.is_rest && n.midi > 0);
    const maxOnset = pitched.length > 0
      ? Math.max(...pitched.map((n) => n.offset_quarters + n.duration_quarters))
      : 4;
    return {
      totalDuration: maxOnset,
      plotWidth: width - PADDING.left - PADDING.right,
    };
  }, [graph, width]);

  const xScale = (onset: number) => PADDING.left + (onset / totalDuration) * plotWidth;

  // Group harmony events by local key for background regions
  const keyRegions = useMemo(() => {
    const regions: { key: string; startX: number; endX: number }[] = [];
    let currentKey = '';
    let startX = 0;

    for (const h of harmony) {
      const key = h.local_key || '';
      const x = xScale(h.onset);
      if (key !== currentKey) {
        if (currentKey) {
          regions.push({ key: currentKey, startX, endX: x });
        }
        currentKey = key;
        startX = x;
      }
    }
    if (currentKey && harmony.length > 0) {
      const last = harmony[harmony.length - 1];
      regions.push({ key: currentKey, startX, endX: xScale(last.onset + last.duration) });
    }
    return regions;
  }, [harmony, xScale]);

  const KEY_COLORS = [
    'rgba(68,119,170,0.08)',
    'rgba(68,170,119,0.08)',
    'rgba(221,170,51,0.08)',
    'rgba(204,68,68,0.08)',
  ];

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="bg-surface border-x border-b border-border rounded-b-lg"
      style={{ fontFamily: 'var(--font-sans)', marginTop: -1 }}
    >
      {/* Key region backgrounds */}
      {keyRegions.map((region, i) => (
        <g key={`region-${i}`}>
          <rect
            x={region.startX}
            y={0}
            width={region.endX - region.startX}
            height={height}
            fill={KEY_COLORS[i % KEY_COLORS.length]}
          />
          <text
            x={region.startX + 4}
            y={12}
            fontSize={8}
            fill="var(--color-ink-muted)"
            fontWeight={500}
          >
            {region.key}
          </text>
        </g>
      ))}

      {/* Roman numerals */}
      {harmony.map((h, i) => {
        const x = xScale(h.onset);
        const label = h.roman_numeral_candidate_set[0] || '?';
        return (
          <text
            key={`rn-${i}`}
            x={x}
            y={32}
            fontSize={10}
            fill="var(--color-ink-light)"
            fontWeight={500}
            style={{ fontFamily: 'var(--font-serif)' }}
          >
            {label}
          </text>
        );
      })}

      {/* Cadence markers */}
      {cadences.map((c, i) => {
        const x = xScale(c.onset);
        return (
          <g key={`cad-${i}`}>
            <line
              x1={x}
              y1={0}
              x2={x}
              y2={height}
              stroke="var(--color-structural)"
              strokeWidth={1.5}
              strokeDasharray="4,3"
              opacity={0.7}
            />
            <text
              x={x + 3}
              y={height - 6}
              fontSize={8}
              fill="var(--color-structural)"
              fontWeight={600}
            >
              {c.cadence_type}
            </text>
          </g>
        );
      })}

      {/* Left label */}
      <text
        x={4}
        y={32}
        fontSize={9}
        fill="var(--color-ink-muted)"
        fontWeight={600}
        style={{ fontFamily: 'var(--font-sans)' }}
      >
        Harmony
      </text>
    </svg>
  );
}
