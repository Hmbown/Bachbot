import { useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchChoraleDetail } from '@/lib/api';
import { PianoRoll } from '@/components/score/PianoRoll';
import { HarmonicOverlay } from '@/components/score/HarmonicOverlay';
import { PlaybackControls } from '@/components/score/PlaybackControls';
import { ExportButtons } from '@/components/shared/ExportButtons';
import { useAudioPlayer } from '@/hooks/useAudioPlayer';
import type { CorpusDetailResponse, AnalysisReport } from '@/types';

function RadarChart({ labelsA, valuesA, valuesB, nameA, nameB }: {
  labelsA: string[];
  valuesA: number[];
  valuesB: number[];
  nameA: string;
  nameB: string;
}) {
  const labels = labelsA;
  const n = labels.length;
  const cx = 150, cy = 150, r = 110;
  const angleStep = (2 * Math.PI) / n;
  const maxVal = Math.max(...valuesA, ...valuesB, 1);

  function polarToCart(i: number, val: number) {
    const angle = angleStep * i - Math.PI / 2;
    const scaled = (val / maxVal) * r;
    return { x: cx + scaled * Math.cos(angle), y: cy + scaled * Math.sin(angle) };
  }

  const polyA = valuesA.map((v, i) => polarToCart(i, v)).map(p => `${p.x},${p.y}`).join(' ');
  const polyB = valuesB.map((v, i) => polarToCart(i, v)).map(p => `${p.x},${p.y}`).join(' ');

  return (
    <svg width={300} height={300} viewBox="0 0 300 300" className="mx-auto">
      {/* Grid rings */}
      {[0.25, 0.5, 0.75, 1].map(pct => (
        <polygon
          key={pct}
          points={Array.from({ length: n }, (_, i) => polarToCart(i, maxVal * pct))
            .map(p => `${p.x},${p.y}`).join(' ')}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={0.5}
        />
      ))}
      {/* Spokes + labels */}
      {labels.map((label, i) => {
        const tip = polarToCart(i, maxVal * 1.15);
        const spoke = polarToCart(i, maxVal);
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={spoke.x} y2={spoke.y} stroke="var(--color-border)" strokeWidth={0.5} />
            <text x={tip.x} y={tip.y} textAnchor="middle" dominantBaseline="middle" fontSize={8} fill="var(--color-ink-muted)">
              {label}
            </text>
          </g>
        );
      })}
      {/* Data polygons */}
      <polygon points={polyA} fill="var(--color-soprano)" fillOpacity={0.15} stroke="var(--color-soprano)" strokeWidth={1.5} />
      <polygon points={polyB} fill="var(--color-bass)" fillOpacity={0.15} stroke="var(--color-bass)" strokeWidth={1.5} />
      {/* Legend */}
      <rect x={10} y={275} width={8} height={8} fill="var(--color-soprano)" rx={1} />
      <text x={22} y={283} fontSize={9} fill="var(--color-ink-light)">{nameA}</text>
      <rect x={150} y={275} width={8} height={8} fill="var(--color-bass)" rx={1} />
      <text x={162} y={283} fontSize={9} fill="var(--color-ink-light)">{nameB}</text>
    </svg>
  );
}

function extractMetrics(report: AnalysisReport) {
  const counterpoint = (report.voice_leading as Record<string, Record<string, number>>)?.counterpoint || {};
  return {
    harmonyCount: report.harmony.length,
    cadenceCount: report.cadences.length,
    cadenceTypes: [...new Set(report.cadences.map(c => c.cadence_type))].length,
    keyRegions: ((report.modulation_graph as Record<string, unknown>)?.regions as unknown[] || []).length,
    parallel5ths: counterpoint.parallel_5ths || 0,
    parallel8ves: counterpoint.parallel_8ves || 0,
  };
}

function ComparisonTable({ a, b, nameA, nameB }: { a: ReturnType<typeof extractMetrics>; b: ReturnType<typeof extractMetrics>; nameA: string; nameB: string }) {
  const rows = [
    { label: 'Harmonic Changes', va: a.harmonyCount, vb: b.harmonyCount },
    { label: 'Cadences', va: a.cadenceCount, vb: b.cadenceCount },
    { label: 'Cadence Kinds', va: a.cadenceTypes, vb: b.cadenceTypes },
    { label: 'Tonal Regions', va: a.keyRegions, vb: b.keyRegions },
    { label: 'Parallel Fifths', va: a.parallel5ths, vb: b.parallel5ths },
    { label: 'Parallel Octaves', va: a.parallel8ves, vb: b.parallel8ves },
  ];

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-paper-dark/30">
            <th className="text-left px-4 py-2 font-semibold text-ink-light">Metric</th>
            <th className="text-right px-4 py-2 font-semibold text-soprano">{nameA}</th>
            <th className="text-right px-4 py-2 font-semibold text-bass">{nameB}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ label, va, vb }) => (
            <tr key={label} className="border-b border-border-light">
              <td className="px-4 py-2 text-ink">{label}</td>
              <td className="px-4 py-2 text-right font-mono text-ink-light">{va}</td>
              <td className="px-4 py-2 text-right font-mono text-ink-light">{vb}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChoralePanel({ data, label, color }: { data: CorpusDetailResponse; label: string; color: string }) {
  const player = useAudioPlayer();
  return (
    <div>
      <h3 className="text-lg font-serif font-semibold mb-2" style={{ color }}>{label}: {data.title || data.chorale_id}</h3>
      <div className="text-xs text-ink-muted mb-2 flex gap-2">
        {data.analysis_report.key && <span className="px-2 py-0.5 bg-primary/10 text-primary-dark rounded">{data.analysis_report.key}</span>}
        <span>{data.event_graph.notes.length} notes</span>
      </div>
      <div className="overflow-x-auto">
        <PianoRoll graph={data.event_graph} width={580} height={280} playbackBeat={player.currentBeat} />
        {data.analysis_report.harmony.length > 0 && (
          <HarmonicOverlay graph={data.event_graph} harmony={data.analysis_report.harmony} cadences={data.analysis_report.cadences} width={580} />
        )}
      </div>
      <div className="mt-2">
        <PlaybackControls
          state={player.state}
          currentBeat={player.currentBeat}
          duration={player.duration}
          tempo={player.tempo}
          voiceVolumes={player.voiceVolumes}
          onPlay={() => player.play(data.event_graph)}
          onPause={player.pause}
          onStop={player.stop}
          onTempoChange={player.setTempo}
          onVoiceVolumeChange={player.setVoiceVolume}
          compact
        />
      </div>
      <div className="mt-2">
        <ExportButtons choraleId={data.chorale_id} />
      </div>
    </div>
  );
}

export function ChoraleComparison() {
  const [params] = useSearchParams();
  const idA = params.get('a') || '';
  const idB = params.get('b') || '';

  const queryA = useQuery({
    queryKey: ['chorale', idA],
    queryFn: () => fetchChoraleDetail(idA),
    enabled: !!idA,
    staleTime: 5 * 60 * 1000,
  });
  const queryB = useQuery({
    queryKey: ['chorale', idB],
    queryFn: () => fetchChoraleDetail(idB),
    enabled: !!idB,
    staleTime: 5 * 60 * 1000,
  });

  if (!idA || !idB) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 py-12 text-center text-ink-muted">
        Choose two chorales in the <Link to="/corpus" className="text-primary">Chorale browser</Link> to compare them side by side.
      </div>
    );
  }

  if (queryA.isLoading || queryB.isLoading) {
    return <div className="max-w-[1400px] mx-auto px-6 py-12 text-center text-ink-muted">Loading both chorales...</div>;
  }

  if (queryA.error || queryB.error || !queryA.data || !queryB.data) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 py-12">
        <div className="p-4 bg-structural/10 border border-structural/20 rounded-lg text-sm text-structural">
          Couldn&apos;t load one or both chorales.
        </div>
        <Link to="/corpus" className="text-primary text-sm mt-4 inline-block">Back to Corpus</Link>
      </div>
    );
  }

  const dataA = queryA.data;
  const dataB = queryB.data;
  const metricsA = extractMetrics(dataA.analysis_report);
  const metricsB = extractMetrics(dataB.analysis_report);

  const radarLabels = ['Chords', 'Cadences', 'Kinds', 'Keys', '5ths', '8ves'];
  const radarA = [metricsA.harmonyCount, metricsA.cadenceCount, metricsA.cadenceTypes, metricsA.keyRegions, metricsA.parallel5ths, metricsA.parallel8ves];
  const radarB = [metricsB.harmonyCount, metricsB.cadenceCount, metricsB.cadenceTypes, metricsB.keyRegions, metricsB.parallel5ths, metricsB.parallel8ves];

  // Harmonic vocabulary overlap
  const chordsA = new Set(dataA.analysis_report.harmony.flatMap(h => h.roman_numeral_candidate_set));
  const chordsB = new Set(dataB.analysis_report.harmony.flatMap(h => h.roman_numeral_candidate_set));
  const shared = [...chordsA].filter(c => chordsB.has(c));
  const onlyA = [...chordsA].filter(c => !chordsB.has(c));
  const onlyB = [...chordsB].filter(c => !chordsA.has(c));

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-ink-muted mb-6">
        <Link to="/corpus" className="hover:text-ink no-underline">Corpus</Link>
        <span>/</span>
        <span className="text-ink font-medium">Compare {idA} vs {idB}</span>
      </div>

      <h1 className="text-3xl font-serif font-bold text-ink mb-6">Compare Two Chorales</h1>

      {/* Side-by-side piano rolls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <ChoralePanel data={dataA} label={idA} color="var(--color-soprano)" />
        <ChoralePanel data={dataB} label={idB} color="var(--color-bass)" />
      </div>

      {/* Comparison table + radar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div>
          <h2 className="text-xl font-serif font-semibold mb-3">At a Glance</h2>
          <ComparisonTable a={metricsA} b={metricsB} nameA={idA} nameB={idB} />
        </div>
        <div>
          <h2 className="text-xl font-serif font-semibold mb-3">Profile at a Glance</h2>
          <div className="p-4 rounded-lg border border-border bg-surface">
            <RadarChart labelsA={radarLabels} valuesA={radarA} valuesB={radarB} nameA={idA} nameB={idB} />
          </div>
        </div>
      </div>

      {/* Harmonic vocabulary overlap */}
      <section className="mb-8">
        <h2 className="text-xl font-serif font-semibold mb-3">Chord Vocabulary</h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 rounded-lg border border-border bg-surface">
            <h3 className="text-sm font-semibold text-soprano mb-2">Only in {idA} ({onlyA.length})</h3>
            <div className="flex gap-1 flex-wrap text-xs font-serif">
              {onlyA.map(c => <span key={c} className="px-1.5 py-0.5 bg-soprano/10 text-soprano rounded">{c}</span>)}
            </div>
          </div>
          <div className="p-4 rounded-lg border border-border bg-surface">
            <h3 className="text-sm font-semibold text-ink mb-2">Shared ({shared.length})</h3>
            <div className="flex gap-1 flex-wrap text-xs font-serif">
              {shared.map(c => <span key={c} className="px-1.5 py-0.5 bg-fact/10 text-fact rounded">{c}</span>)}
            </div>
          </div>
          <div className="p-4 rounded-lg border border-border bg-surface">
            <h3 className="text-sm font-semibold text-bass mb-2">Only in {idB} ({onlyB.length})</h3>
            <div className="flex gap-1 flex-wrap text-xs font-serif">
              {onlyB.map(c => <span key={c} className="px-1.5 py-0.5 bg-bass/10 text-bass rounded">{c}</span>)}
            </div>
          </div>
        </div>
      </section>

      {/* Cadence pattern comparison */}
      <section className="mb-8">
        <h2 className="text-xl font-serif font-semibold mb-3">Cadence Layout</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[{ data: dataA, id: idA, color: 'soprano' }, { data: dataB, id: idB, color: 'bass' }].map(({ data: d, id, color }) => (
            <div key={id} className="p-4 rounded-lg border border-border bg-surface">
              <h3 className={`text-sm font-semibold text-${color} mb-2`}>{id}</h3>
              <div className="flex gap-2 flex-wrap">
                {d.analysis_report.cadences.map((c, i) => (
                  <span key={i} className="text-xs px-2 py-1 rounded border border-border font-serif">
                    {c.cadence_type} <span className="text-ink-muted font-mono">@{c.onset.toFixed(1)}</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
