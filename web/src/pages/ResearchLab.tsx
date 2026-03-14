import { useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  fetchFingerprint,
  fetchCorpusBaseline,
  fetchAnomalies,
  fetchPatterns,
  searchPatterns,
  fetchEmbeddings,
  fetchHarmonicRhythm,
  searchCorpus,
} from '@/lib/api';

// ─── Types ──────────────────────────────────────────────────────────

type ResearchTool = 'fingerprint' | 'anomaly' | 'patterns' | 'embeddings' | 'rhythm' | 'editions';

interface ToolDef {
  title: string;
  icon: string;
  description: string;
}

interface AnomalyEntry {
  work_id: string;
  anomaly_score: number;
  outlier_features: { name: string; left_value: number; right_value: number; difference: number }[];
  nearest_neighbors: [string, number][];
}

interface PatternEntry {
  progression: string[];
  count: number;
}

interface PatternMatch {
  chorale_id: string;
  title: string;
  onset_index: number;
}

interface EmbeddingPoint {
  id: string;
  x: number;
  y: number;
  key?: string;
  title?: string;
}

interface HarmonicRhythmEvent {
  onset: number;
  duration: number;
  chord: string;
  measure: number;
  is_cadence?: boolean;
}

// ─── Tool Definitions ───────────────────────────────────────────────

const TOOLS: Record<ResearchTool, ToolDef> = {
  fingerprint: {
    title: 'Chorale Profile',
    icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2',
    description:
      'See what makes one chorale stand out against the rest of the collection: harmonic variety, cadence habits, spacing, and melodic shape.',
  },
  anomaly: {
    title: 'Outliers',
    icon: 'M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4.99c-.77-1.33-2.69-1.33-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z',
    description:
      'Find the pieces that sit furthest from the center of the corpus. Some are unusually adventurous; some simply favor uncommon habits.',
  },
  patterns: {
    title: 'Common Progressions',
    icon: 'M4 6h16M4 12h16M4 18h7',
    description:
      'Look for recurring chord successions across the chorales, from familiar cadential turns to rarer sequences.',
  },
  embeddings: {
    title: 'Chorale Map',
    icon: 'M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    description:
      'Plot the chorales as a map of stylistic likeness. Nearby pieces tend to share harmonic habits; distant ones feel less alike.',
  },
  rhythm: {
    title: 'Harmonic Rhythm',
    icon: 'M9 19V6l12-3v13',
    description:
      'Watch how often Bach changes harmony and where he lets a sonority breathe.',
  },
  editions: {
    title: 'Edition Comparison',
    icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
    description:
      'Paste two versions of a chorale and inspect pitch, rhythm, or accidental differences side by side.',
  },
};

// ─── Shared Components ──────────────────────────────────────────────

function ChoraleSearchInput({
  value,
  onChange,
  onSelect,
  placeholder = 'Search chorales by title or BWV...',
}: {
  value: string;
  onChange: (v: string) => void;
  onSelect: (id: string) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);

  const { data: results } = useQuery({
    queryKey: ['corpus', 'search', value],
    queryFn: () => searchCorpus({ title_contains: value, limit: 12 }),
    enabled: value.length >= 1,
    staleTime: 30_000,
  });

  return (
    <div className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20"
      />
      {open && results && results.results.length > 0 && (
        <div className="absolute z-20 mt-1 w-full max-h-60 overflow-y-auto rounded-lg border border-border bg-surface shadow-lg">
          {results.results.map((r) => (
            <button
              key={r.chorale_id}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onSelect(r.chorale_id);
                onChange(r.title || r.chorale_id);
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-paper-dark/40 flex justify-between items-center transition-colors"
            >
              <span className="text-ink truncate">{r.title || r.chorale_id}</span>
              <span className="text-xs font-mono text-ink-muted ml-2 flex-shrink-0">{r.chorale_id}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function LoadingSpinner({ text = 'Loading...' }: { text?: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        <span className="text-sm text-ink-muted">{text}</span>
      </div>
    </div>
  );
}

function ErrorBanner({ error }: { error: unknown }) {
  return (
    <div className="p-4 bg-structural/10 border border-structural/20 rounded-lg text-sm text-structural">
      {error instanceof Error ? error.message : 'An error occurred. Is the API server running?'}
    </div>
  );
}

function zScoreColor(z: number): string {
  const abs = Math.abs(z);
  if (abs > 2) return 'text-structural';
  if (abs > 1) return 'text-suspension';
  return 'text-fact';
}

function zScoreBg(z: number): string {
  const abs = Math.abs(z);
  if (abs > 2) return 'bg-structural/10';
  if (abs > 1) return 'bg-suspension/10';
  return 'bg-fact/10';
}

function anomalyColor(score: number): string {
  if (score > 3) return 'text-structural';
  if (score > 2) return 'text-orange-600';
  if (score > 1) return 'text-suspension';
  return 'text-ink-light';
}

function anomalyBadgeBg(score: number): string {
  if (score > 3) return 'bg-structural/15 border-structural/30';
  if (score > 2) return 'bg-orange-100 border-orange-300';
  if (score > 1) return 'bg-suspension/15 border-suspension/30';
  return 'bg-paper-dark border-border';
}

// ─── 1. Style Fingerprinting ────────────────────────────────────────

function FingerprintTool() {
  const [searchText, setSearchText] = useState('');
  const [choraleId, setChoraleId] = useState('');

  const { data: fingerprint, isLoading: fpLoading, error: fpError } = useQuery({
    queryKey: ['fingerprint', choraleId],
    queryFn: () => fetchFingerprint(choraleId),
    enabled: !!choraleId,
    staleTime: 60_000,
  });

  const { data: baseline, isLoading: blLoading } = useQuery({
    queryKey: ['corpus-baseline'],
    queryFn: fetchCorpusBaseline,
    staleTime: 5 * 60_000,
  });

  const features = useMemo(() => {
    if (!fingerprint || !baseline) return [];
    return Object.entries(fingerprint.features).map(([name, value]) => {
      const mean = baseline.mean[name] ?? 0;
      const std = baseline.std[name] ?? 1;
      const zScore = std > 0 ? (value - mean) / std : 0;
      return { name, value, mean, std, zScore };
    }).sort((a, b) => Math.abs(b.zScore) - Math.abs(a.zScore));
  }, [fingerprint, baseline]);

  // Radar chart: top 12 features by |z-score| for readability
  const radarFeatures = useMemo(() => features.slice(0, 12), [features]);

  const radarSvg = useMemo(() => {
    if (radarFeatures.length === 0) return null;
    const cx = 200, cy = 200, maxR = 160;
    const n = radarFeatures.length;
    const angleStep = (2 * Math.PI) / n;

    // Max absolute z for scaling
    const maxZ = Math.max(3, ...radarFeatures.map((f) => Math.abs(f.zScore)));

    // Grid rings at 1, 2, 3 sigma
    const rings = [1, 2, 3].filter((r) => r <= maxZ);

    // Points for corpus mean (z=0) and chorale
    const meanPoints: string[] = [];
    const choralePoints: string[] = [];
    const labels: { x: number; y: number; name: string; anchor: string }[] = [];

    radarFeatures.forEach((f, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      const cosA = Math.cos(angle);
      const sinA = Math.sin(angle);

      // mean is at z=0, but we center the chart so z=0 is a ring at 0
      // Actually, show normalized z on the radar: map z -> radius
      // z=0 is center (no deviation), maxZ is the edge
      const normZ = Math.min(Math.abs(f.zScore), maxZ);
      const r = (normZ / maxZ) * maxR;

      choralePoints.push(`${cx + r * cosA},${cy + r * sinA}`);
      meanPoints.push(`${cx},${cy}`); // Mean is center (z=0)

      // Label position
      const lr = maxR + 24;
      const lx = cx + lr * cosA;
      const ly = cy + lr * sinA;
      const anchor = cosA < -0.1 ? 'end' : cosA > 0.1 ? 'start' : 'middle';
      labels.push({ x: lx, y: ly, name: f.name.replace(/_/g, ' '), anchor });
    });

    return (
      <svg viewBox="0 0 400 400" className="w-full max-w-md mx-auto">
        {/* Grid rings */}
        {rings.map((r) => {
          const radius = (r / maxZ) * maxR;
          return (
            <g key={r}>
              <circle
                cx={cx} cy={cy} r={radius}
                fill="none" stroke="currentColor" strokeWidth="0.5"
                className="text-border"
              />
              <text
                x={cx + 4} y={cy - radius + 4}
                className="text-ink-muted fill-current" fontSize="9" fontFamily="var(--font-mono)"
              >
                {r}s
              </text>
            </g>
          );
        })}

        {/* Spokes */}
        {radarFeatures.map((_, i) => {
          const angle = -Math.PI / 2 + i * angleStep;
          return (
            <line
              key={i}
              x1={cx} y1={cy}
              x2={cx + maxR * Math.cos(angle)} y2={cy + maxR * Math.sin(angle)}
              stroke="currentColor" strokeWidth="0.5" className="text-border"
            />
          );
        })}

        {/* Chorale polygon */}
        <polygon
          points={choralePoints.join(' ')}
          fill="rgba(44, 82, 130, 0.15)" stroke="#2c5282" strokeWidth="2"
        />

        {/* Chorale dots */}
        {radarFeatures.map((f, i) => {
          const angle = -Math.PI / 2 + i * angleStep;
          const normZ = Math.min(Math.abs(f.zScore), maxZ);
          const r = (normZ / maxZ) * maxR;
          const x = cx + r * Math.cos(angle);
          const y = cy + r * Math.sin(angle);
          const absZ = Math.abs(f.zScore);
          const dotColor = absZ > 2 ? '#CC4444' : absZ > 1 ? '#DDAA33' : '#2d7d46';
          return (
            <circle key={i} cx={x} cy={y} r="4" fill={dotColor} stroke="white" strokeWidth="1.5">
              <title>{`${f.name}: z=${f.zScore.toFixed(2)}`}</title>
            </circle>
          );
        })}

        {/* Labels */}
        {labels.map((l, i) => (
          <text
            key={i} x={l.x} y={l.y}
            textAnchor={l.anchor as 'start' | 'middle' | 'end'}
            dominantBaseline="middle"
            className="fill-ink-light" fontSize="9" fontFamily="var(--font-sans)"
          >
            {l.name.length > 18 ? l.name.slice(0, 16) + '...' : l.name}
          </text>
        ))}

        {/* Center dot (corpus mean) */}
        <circle cx={cx} cy={cy} r="3" fill="#8a8177" opacity="0.6" />
      </svg>
    );
  }, [radarFeatures]);

  return (
    <div>
      <div className="mb-6 max-w-md">
        <label className="block text-sm font-medium text-ink-light mb-2">Choose a chorale</label>
        <ChoraleSearchInput
          value={searchText}
          onChange={setSearchText}
          onSelect={setChoraleId}
        />
      </div>

      {fpLoading || blLoading ? (
        <LoadingSpinner text="Reading chorale profile..." />
      ) : fpError ? (
        <ErrorBanner error={fpError} />
      ) : choraleId && fingerprint && baseline ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          {/* Radar chart */}
          <div>
            <h3 className="text-sm font-semibold text-ink-light mb-3">
              What stands out most
            </h3>
            <div className="p-4 rounded-xl border border-border bg-surface">
              {radarSvg}
              <div className="flex justify-center gap-4 mt-3 text-xs text-ink-muted">
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-fact inline-block" /> close to average
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-suspension inline-block" /> noticeable
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-structural inline-block" /> far from average
                </span>
              </div>
            </div>
          </div>

          {/* Feature table */}
          <div>
            <h3 className="text-sm font-semibold text-ink-light mb-3">
              Full feature table ({features.length})
            </h3>
            <div className="overflow-y-auto max-h-[520px] rounded-xl border border-border bg-surface">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-paper-dark/80 backdrop-blur-sm">
                  <tr className="border-b border-border">
                    <th className="text-left px-3 py-2 font-semibold text-ink-light">Feature</th>
                    <th className="text-right px-3 py-2 font-semibold text-ink-light">This chorale</th>
                    <th className="text-right px-3 py-2 font-semibold text-ink-light">Corpus mean</th>
                    <th className="text-right px-3 py-2 font-semibold text-ink-light">z-score</th>
                  </tr>
                </thead>
                <tbody>
                  {features.map((f) => (
                    <tr key={f.name} className={`border-b border-border-light ${zScoreBg(f.zScore)}`}>
                      <td className="px-3 py-1.5 text-ink text-xs">{f.name.replace(/_/g, ' ')}</td>
                      <td className="px-3 py-1.5 text-right font-mono text-xs text-ink-light">
                        {f.value.toFixed(3)}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono text-xs text-ink-muted">
                        {f.mean.toFixed(3)}
                      </td>
                      <td className={`px-3 py-1.5 text-right font-mono text-xs font-semibold ${zScoreColor(f.zScore)}`}>
                        {f.zScore >= 0 ? '+' : ''}{f.zScore.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : !choraleId ? (
        <EmptyState text="Search for a chorale above to see its profile." />
      ) : null}
    </div>
  );
}

// ─── 2. Anomaly Detection ───────────────────────────────────────────

function AnomalyTool() {
  const [sortField, setSortField] = useState<'work_id' | 'anomaly_score'>('anomaly_score');
  const [sortAsc, setSortAsc] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['anomalies'],
    queryFn: fetchAnomalies,
    staleTime: 5 * 60_000,
  });

  const sorted = useMemo(() => {
    if (!data) return [];
    const list = [...data.anomalies];
    list.sort((a, b) => {
      const aVal = sortField === 'work_id' ? a.work_id : a.anomaly_score;
      const bVal = sortField === 'work_id' ? b.work_id : b.anomaly_score;
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortAsc ? aVal - bVal : bVal - aVal;
      }
      const cmp = String(aVal).localeCompare(String(bVal));
      return sortAsc ? cmp : -cmp;
    });
    return list;
  }, [data, sortField, sortAsc]);

  const handleSort = (field: 'work_id' | 'anomaly_score') => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === 'work_id');
    }
  };

  if (isLoading) return <LoadingSpinner text="Ranking outliers..." />;
  if (error) return <ErrorBanner error={error} />;
  if (!data) return null;

  return (
    <div>
      <div className="text-sm text-ink-muted mb-4">
        {data.anomalies.length} chorales sorted by outlier score. Higher numbers sit farther from the corpus average.
      </div>

      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-paper-dark/30">
              <th
                className="text-left px-4 py-3 font-semibold text-ink-light cursor-pointer hover:text-ink"
                onClick={() => handleSort('work_id')}
              >
                Chorale
                <SortArrow active={sortField === 'work_id'} asc={sortAsc} />
              </th>
              <th
                className="text-right px-4 py-3 font-semibold text-ink-light cursor-pointer hover:text-ink"
                onClick={() => handleSort('anomaly_score')}
              >
                Outlier Score
                <SortArrow active={sortField === 'anomaly_score'} asc={sortAsc} />
              </th>
              <th className="text-left px-4 py-3 font-semibold text-ink-light">What Stands Out</th>
              <th className="w-10 px-2 py-3" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((entry: AnomalyEntry) => {
              const expanded = expandedId === entry.work_id;
              return (
                <tbody key={entry.work_id}>
                  <tr
                    className={`border-b border-border-light cursor-pointer transition-colors ${
                      expanded ? 'bg-paper-dark/30' : 'hover:bg-paper-dark/20'
                    }`}
                    onClick={() => setExpandedId(expanded ? null : entry.work_id)}
                  >
                    <td className="px-4 py-3 font-mono text-primary font-medium">{entry.work_id}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold border ${anomalyBadgeBg(entry.anomaly_score)} ${anomalyColor(entry.anomaly_score)}`}>
                        {entry.anomaly_score.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1 flex-wrap">
                        {entry.outlier_features.slice(0, 3).map((f) => (
                          <span
                            key={f.name}
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-paper-dark text-ink-muted"
                          >
                            {f.name.replace(/_/g, ' ')}
                          </span>
                        ))}
                        {entry.outlier_features.length > 3 && (
                          <span className="text-xs text-ink-muted">+{entry.outlier_features.length - 3}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-3 text-ink-muted">
                      <svg
                        className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
                        viewBox="0 0 20 20" fill="currentColor"
                      >
                        <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                    </td>
                  </tr>
                  {expanded && (
                    <tr className="bg-paper-dark/15">
                      <td colSpan={4} className="px-4 py-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div>
                            <h4 className="text-xs font-semibold text-ink-light mb-2 uppercase tracking-wide">Full List</h4>
                            <div className="space-y-1">
                              {entry.outlier_features.map((f) => {
                                const diff = Math.abs(f.difference);
                                return (
                                  <div key={f.name} className="flex items-center justify-between text-xs">
                                    <span className="text-ink">{f.name.replace(/_/g, ' ')}</span>
                                    <div className="flex items-center gap-3">
                                      <span className="font-mono text-ink-muted">
                                        {f.left_value.toFixed(2)} vs {f.right_value.toFixed(2)}
                                      </span>
                                      <span className={`font-mono font-semibold ${diff > 3 ? 'text-structural' : diff > 2 ? 'text-orange-600' : 'text-suspension'}`}>
                                        {diff.toFixed(2)}s
                                      </span>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                          {entry.nearest_neighbors.length > 0 && (
                            <div>
                              <h4 className="text-xs font-semibold text-ink-light mb-2 uppercase tracking-wide">Closest Matches</h4>
                              <div className="space-y-1">
                                {entry.nearest_neighbors.map(([id, dist]) => (
                                  <div key={id} className="flex items-center justify-between text-xs">
                                    <span className="font-mono text-primary">{id}</span>
                                    <span className="font-mono text-ink-muted">distance {typeof dist === 'number' ? dist.toFixed(3) : dist}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SortArrow({ active, asc }: { active: boolean; asc: boolean }) {
  if (!active) return <span className="text-ink-muted/40 ml-1">&#8597;</span>;
  return <span className="text-primary ml-1">{asc ? '\u25B2' : '\u25BC'}</span>;
}

// ─── 3. Pattern Mining ──────────────────────────────────────────────

function PatternTool() {
  const navigate = useNavigate();
  const [length, setLength] = useState(3);
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: patterns, isLoading, error } = useQuery({
    queryKey: ['patterns', length],
    queryFn: () => fetchPatterns(length),
    staleTime: 5 * 60_000,
  });

  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['pattern-search', searchQuery],
    queryFn: () => searchPatterns(searchQuery),
    enabled: !!searchQuery,
    staleTime: 60_000,
  });

  const top20 = useMemo(() => {
    if (!patterns) return [];
    return patterns.patterns.slice(0, 20);
  }, [patterns]);

  const maxCount = useMemo(() => {
    return top20.length > 0 ? top20[0].count : 1;
  }, [top20]);

  const handleSearch = () => {
    if (searchInput.trim()) {
      setSearchQuery(searchInput.trim());
    }
  };

  return (
    <div>
      {/* Length selector */}
      <div className="flex items-center gap-4 mb-6">
        <label className="text-sm font-medium text-ink-light">Length of progression:</label>
        <div className="flex gap-1">
          {[2, 3, 4, 5, 6].map((n) => (
            <button
              key={n}
              onClick={() => setLength(n)}
              className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${
                length === n
                  ? 'bg-primary-dark text-white'
                  : 'bg-surface border border-border text-ink-light hover:text-ink'
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <LoadingSpinner text="Counting progressions..." />
      ) : error ? (
        <ErrorBanner error={error} />
      ) : (
        <>
          {/* Bar chart */}
          <div className="mb-8">
            <h3 className="text-sm font-semibold text-ink-light mb-3">Most Common Progressions (length {length})</h3>
            <div className="space-y-1.5">
              {top20.map((p: PatternEntry, i: number) => {
                const pct = (p.count / maxCount) * 100;
                return (
                  <div key={i} className="flex items-center gap-3 group">
                    <div className="w-40 flex-shrink-0 text-right">
                      <span className="text-xs font-mono text-ink-light group-hover:text-ink transition-colors">
                        {p.progression.join(' - ')}
                      </span>
                    </div>
                    <div className="flex-1 h-6 bg-paper-dark/40 rounded overflow-hidden">
                      <div
                        className="h-full bg-primary/70 rounded transition-all group-hover:bg-primary"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-12 text-right text-xs font-mono text-ink-muted">{p.count}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Progression search */}
          <div className="border-t border-border pt-6">
            <h3 className="text-sm font-semibold text-ink-light mb-3">Find a Progression in the Corpus</h3>
            <div className="flex gap-2 max-w-lg mb-4">
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="e.g. I,IV,V or V,vi,IV,I"
                className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink font-mono placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20"
              />
              <button
                onClick={handleSearch}
                disabled={!searchInput.trim()}
                className="px-4 py-2 bg-primary-dark text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Search
              </button>
            </div>

            {searchLoading && <LoadingSpinner text="Searching..." />}

            {searchResults && (
              <div>
                <div className="text-xs text-ink-muted mb-2">
                  {searchResults.matches.length} chorales contain{' '}
                  <span className="font-mono font-medium text-ink-light">
                    {searchResults.progression.join(' - ')}
                  </span>
                </div>
                {searchResults.matches.length > 0 && (
                  <div className="overflow-x-auto rounded-lg border border-border bg-surface">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border bg-paper-dark/30">
                          <th className="text-left px-4 py-2 font-semibold text-ink-light">Chorale</th>
                          <th className="text-left px-4 py-2 font-semibold text-ink-light">Title</th>
                          <th className="text-right px-4 py-2 font-semibold text-ink-light">Onset Index</th>
                        </tr>
                      </thead>
                      <tbody>
                        {searchResults.matches.map((m: PatternMatch, i: number) => (
                          <tr
                            key={`${m.chorale_id}-${i}`}
                            className="border-b border-border-light hover:bg-paper-dark/20 cursor-pointer transition-colors"
                            onClick={() => navigate(`/corpus/${m.chorale_id}`)}
                          >
                            <td className="px-4 py-2 font-mono text-primary font-medium">{m.chorale_id}</td>
                            <td className="px-4 py-2 text-ink">{m.title}</td>
                            <td className="px-4 py-2 text-right font-mono text-ink-muted">{m.onset_index}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ─── 4. Embedding Space ─────────────────────────────────────────────

function EmbeddingTool() {
  const navigate = useNavigate();
  const [hoveredPoint, setHoveredPoint] = useState<EmbeddingPoint | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const { data, isLoading, error } = useQuery({
    queryKey: ['embeddings'],
    queryFn: fetchEmbeddings,
    staleTime: 5 * 60_000,
  });

  const points: EmbeddingPoint[] = useMemo(() => {
    if (!data) return [];
    // Flexible: accept { coordinates: [...] } or { points: [...] } or array
    const raw = (data as Record<string, unknown>).coordinates
      ?? (data as Record<string, unknown>).points
      ?? (Array.isArray(data) ? data : []);
    return (raw as EmbeddingPoint[]).filter((p) => typeof p.x === 'number' && typeof p.y === 'number');
  }, [data]);

  const bounds = useMemo(() => {
    if (points.length === 0) return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    for (const p of points) {
      if (p.x < xMin) xMin = p.x;
      if (p.x > xMax) xMax = p.x;
      if (p.y < yMin) yMin = p.y;
      if (p.y > yMax) yMax = p.y;
    }
    const padX = (xMax - xMin) * 0.08 || 1;
    const padY = (yMax - yMin) * 0.08 || 1;
    return { xMin: xMin - padX, xMax: xMax + padX, yMin: yMin - padY, yMax: yMax + padY };
  }, [points]);

  const svgW = 700, svgH = 500, pad = 40;

  const mapX = useCallback((x: number) => {
    return pad + ((x - bounds.xMin) / (bounds.xMax - bounds.xMin)) * (svgW - 2 * pad);
  }, [bounds]);

  const mapY = useCallback((y: number) => {
    return pad + ((bounds.yMax - y) / (bounds.yMax - bounds.yMin)) * (svgH - 2 * pad);
  }, [bounds]);

  const isMajor = (key?: string): boolean => {
    if (!key) return true;
    return key.toLowerCase().includes('major') || (!key.toLowerCase().includes('minor') && key === key.replace(/\s.*/, ''));
  };

  if (isLoading) return <LoadingSpinner text="Loading chorale map..." />;
  if (error) return <ErrorBanner error={error} />;
  if (points.length === 0) {
    return <EmptyState text="No chorale map is available yet." />;
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-4">
        <span className="text-sm text-ink-muted">{points.length} chorales placed on a two-dimensional map</span>
        <div className="flex items-center gap-3 text-xs text-ink-muted">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-passing inline-block" /> Major
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-structural inline-block" /> Minor
          </span>
        </div>
      </div>

      <div className="relative rounded-xl border border-border bg-surface p-2 overflow-hidden">
        <svg
          viewBox={`0 0 ${svgW} ${svgH}`}
          className="w-full"
          style={{ maxHeight: '520px' }}
        >
          {/* Dots */}
          {points.map((p) => {
            const cx = mapX(p.x);
            const cy = mapY(p.y);
            const major = isMajor(p.key);
            return (
              <circle
                key={p.id}
                cx={cx}
                cy={cy}
                r={hoveredPoint?.id === p.id ? 6 : 3.5}
                fill={major ? '#4477AA' : '#CC4444'}
                opacity={hoveredPoint && hoveredPoint.id !== p.id ? 0.25 : 0.7}
                className="cursor-pointer transition-opacity"
                onMouseEnter={(e) => {
                  setHoveredPoint(p);
                  const svgEl = e.currentTarget.closest('svg');
                  if (svgEl) {
                    const rect = svgEl.getBoundingClientRect();
                    const scaleX = rect.width / svgW;
                    const scaleY = rect.height / svgH;
                    setTooltipPos({
                      x: cx * scaleX + rect.left - (svgEl.parentElement?.getBoundingClientRect().left ?? 0),
                      y: cy * scaleY,
                    });
                  }
                }}
                onMouseLeave={() => setHoveredPoint(null)}
                onClick={() => navigate(`/corpus/${p.id}`)}
              />
            );
          })}

          {/* Axis labels */}
          <text x={svgW / 2} y={svgH - 4} textAnchor="middle" className="fill-ink-muted" fontSize="10" fontFamily="var(--font-sans)">
            Axis 1
          </text>
          <text x={10} y={svgH / 2} textAnchor="middle" className="fill-ink-muted" fontSize="10" fontFamily="var(--font-sans)" transform={`rotate(-90, 10, ${svgH / 2})`}>
            Axis 2
          </text>
        </svg>

        {/* Tooltip */}
        {hoveredPoint && (
          <div
            className="absolute z-30 pointer-events-none px-3 py-2 rounded-lg bg-ink text-paper text-xs shadow-lg"
            style={{
              left: `${tooltipPos.x + 12}px`,
              top: `${tooltipPos.y - 8}px`,
              maxWidth: '240px',
            }}
          >
            <div className="font-semibold">{hoveredPoint.title || hoveredPoint.id}</div>
            <div className="text-paper/70 font-mono">{hoveredPoint.id}</div>
            {hoveredPoint.key && <div className="text-paper/70 mt-0.5">{hoveredPoint.key}</div>}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── 5. Harmonic Rhythm ─────────────────────────────────────────────

function RhythmTool() {
  const [searchText, setSearchText] = useState('');
  const [choraleId, setChoraleId] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['harmonic-rhythm', choraleId],
    queryFn: () => fetchHarmonicRhythm(choraleId),
    enabled: !!choraleId,
    staleTime: 60_000,
  });

  const events: HarmonicRhythmEvent[] = useMemo(() => {
    if (!data) return [];
    const raw = (data as Record<string, unknown>).events
      ?? (data as Record<string, unknown>).rhythm
      ?? (Array.isArray(data) ? data : []);
    return (raw as HarmonicRhythmEvent[]).filter(
      (e) => typeof e.onset === 'number' && typeof e.duration === 'number',
    );
  }, [data]);

  const measures = useMemo(() => {
    if (events.length === 0) return { min: 1, max: 4 };
    const ms = events.map((e) => e.measure).filter(Boolean);
    return { min: Math.min(...ms, 1), max: Math.max(...ms, 4) };
  }, [events]);

  const totalDuration = useMemo(() => {
    if (events.length === 0) return 16;
    return Math.max(...events.map((e) => e.onset + e.duration), 16);
  }, [events]);

  const svgW = 900;
  const barH = 28;
  const topPad = 30;
  const leftPad = 10;
  const rightPad = 20;
  const usableW = svgW - leftPad - rightPad;
  const svgH = topPad + barH + 40;

  // Color chords by hashing their label
  const chordColor = useCallback((chord: string): string => {
    const colors = [
      '#2c5282', '#2d7d46', '#DDAA33', '#CC4444', '#4477AA',
      '#44AA77', '#a69274', '#7b5ea7', '#c0392b', '#16a085',
    ];
    let hash = 0;
    for (let i = 0; i < chord.length; i++) {
      hash = ((hash << 5) - hash + chord.charCodeAt(i)) | 0;
    }
    return colors[Math.abs(hash) % colors.length];
  }, []);

  return (
    <div>
      <div className="mb-6 max-w-md">
        <label className="block text-sm font-medium text-ink-light mb-2">Choose a chorale</label>
        <ChoraleSearchInput
          value={searchText}
          onChange={setSearchText}
          onSelect={setChoraleId}
        />
      </div>

      {isLoading ? (
        <LoadingSpinner text="Reading harmonic rhythm..." />
      ) : error ? (
        <ErrorBanner error={error} />
      ) : choraleId && events.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold text-ink-light mb-3">
            Chord Timeline ({events.length} events, measures {measures.min}--{measures.max})
          </h3>

          <div className="overflow-x-auto rounded-xl border border-border bg-surface p-4">
            <svg viewBox={`0 0 ${svgW} ${svgH}`} className="w-full" style={{ minWidth: '600px' }}>
              {/* Measure grid lines */}
              {Array.from({ length: measures.max - measures.min + 2 }, (_, i) => {
                const m = measures.min + i;
                // Estimate onset for measure start (assuming 4/4, 4 quarters per measure)
                const onset = (m - measures.min) * 4;
                const x = leftPad + (onset / totalDuration) * usableW;
                if (x > svgW - rightPad) return null;
                return (
                  <g key={m}>
                    <line
                      x1={x} y1={topPad - 5} x2={x} y2={topPad + barH + 5}
                      stroke="currentColor" strokeWidth="0.5" className="text-border"
                      strokeDasharray="4,3"
                    />
                    <text
                      x={x} y={topPad - 10}
                      textAnchor="middle" className="fill-ink-muted" fontSize="9" fontFamily="var(--font-mono)"
                    >
                      m.{m}
                    </text>
                  </g>
                );
              })}

              {/* Chord bars */}
              {events.map((e, i) => {
                const x = leftPad + (e.onset / totalDuration) * usableW;
                const w = Math.max((e.duration / totalDuration) * usableW, 2);
                const color = chordColor(e.chord || 'I');
                return (
                  <g key={i}>
                    <rect
                      x={x} y={topPad} width={w} height={barH}
                      rx={3}
                      fill={color} opacity={0.75}
                    >
                      <title>{`${e.chord || '?'} (m.${e.measure}, onset=${e.onset.toFixed(1)}, dur=${e.duration.toFixed(1)})`}</title>
                    </rect>
                    {w > 24 && (
                      <text
                        x={x + w / 2} y={topPad + barH / 2 + 1}
                        textAnchor="middle" dominantBaseline="middle"
                        fill="white" fontSize="10" fontFamily="var(--font-mono)" fontWeight="600"
                      >
                        {e.chord || '?'}
                      </text>
                    )}

                    {/* Cadence marker */}
                    {e.is_cadence && (
                      <g>
                        <line
                          x1={x + w} y1={topPad + barH + 4} x2={x + w} y2={topPad + barH + 16}
                          stroke="#CC4444" strokeWidth="2"
                        />
                        <text
                          x={x + w} y={topPad + barH + 26}
                          textAnchor="middle" fill="#CC4444" fontSize="8" fontFamily="var(--font-mono)" fontWeight="600"
                        >
                          CAD
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-3 mt-3 text-xs text-ink-muted">
            <span>Longer bars mean longer-held chords.</span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-structural inline-block" />
              Cadence
            </span>
          </div>
        </div>
      ) : choraleId && events.length === 0 ? (
        <EmptyState text="No harmonic rhythm data available for this chorale." />
      ) : (
        <EmptyState text="Search for a chorale above to see how the harmony moves through the piece." />
      )}
    </div>
  );
}

// ─── 6. Edition Comparison ──────────────────────────────────────────

function EditionTool() {
  const [editionA, setEditionA] = useState('');
  const [editionB, setEditionB] = useState('');
  const [submitted, setSubmitted] = useState(false);

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-ink-light mb-2">Edition A (MusicXML)</label>
          <textarea
            value={editionA}
            onChange={(e) => { setEditionA(e.target.value); setSubmitted(false); }}
            rows={10}
            placeholder="Paste MusicXML content here..."
            className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink font-mono placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 resize-y"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-ink-light mb-2">Edition B (MusicXML)</label>
          <textarea
            value={editionB}
            onChange={(e) => { setEditionB(e.target.value); setSubmitted(false); }}
            rows={10}
            placeholder="Paste MusicXML content here..."
            className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink font-mono placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 resize-y"
          />
        </div>
      </div>

      <button
        onClick={() => setSubmitted(true)}
        disabled={!editionA.trim() || !editionB.trim()}
        className="px-6 py-2 bg-primary-dark text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Compare editions
      </button>

      {submitted && (
        <div className="mt-6 p-8 rounded-xl border-2 border-dashed border-border bg-paper-dark/20 text-center">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto mb-3 text-ink-muted/40">
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p className="text-sm text-ink-muted mb-2">Edition comparison is not wired up yet.</p>
          <p className="text-xs text-ink-muted/70">
            When this view is ready, it will line the two scores up note by note so you can spot pitch,
            rhythm, and accidental differences.
          </p>
        </div>
      )}
    </div>
  );
}

// ─── Empty state ────────────────────────────────────────────────────

function EmptyState({ text }: { text: string }) {
  return (
    <div className="p-12 rounded-xl border-2 border-dashed border-border bg-paper-dark/20 text-center">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mx-auto mb-3 text-ink-muted/30">
        <circle cx="11" cy="11" r="8" />
        <path d="M21 21l-4.35-4.35" />
      </svg>
      <p className="text-sm text-ink-muted">{text}</p>
    </div>
  );
}

// ─── Tool Router ────────────────────────────────────────────────────

function ToolWorkspace({ tool }: { tool: ResearchTool }) {
  switch (tool) {
    case 'fingerprint':
      return <FingerprintTool />;
    case 'anomaly':
      return <AnomalyTool />;
    case 'patterns':
      return <PatternTool />;
    case 'embeddings':
      return <EmbeddingTool />;
    case 'rhythm':
      return <RhythmTool />;
    case 'editions':
      return <EditionTool />;
  }
}

// ─── Main Page ──────────────────────────────────────────────────────

export function ResearchLab() {
  const [activeTool, setActiveTool] = useState<ResearchTool>('fingerprint');
  const tool = TOOLS[activeTool];

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-serif font-bold text-ink mb-2">Research Tools</h1>
        <p className="text-ink-light">
          Compare chorales, trace favorite progressions, and look for pieces that sit near one another
          or far apart. The language is statistical at times, but the questions are musical.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Tool selector sidebar */}
        <div className="lg:col-span-1">
          <div className="space-y-1">
            {(Object.keys(TOOLS) as ResearchTool[]).map((t) => (
              <button
                key={t}
                onClick={() => setActiveTool(t)}
                className={`w-full text-left px-4 py-3 rounded-lg text-sm transition-colors flex items-center gap-3 ${
                  activeTool === t
                    ? 'bg-primary/10 text-primary-dark font-medium border border-primary/20'
                    : 'text-ink-light hover:text-ink hover:bg-paper-dark/50'
                }`}
              >
                <svg
                  width="16" height="16" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  className="flex-shrink-0"
                >
                  <path d={TOOLS[t].icon} />
                </svg>
                {TOOLS[t].title}
              </button>
            ))}
          </div>

          {/* Color legend sidebar card */}
          <div className="mt-6 p-4 rounded-lg bg-surface-warm border border-border">
            <h4 className="text-xs font-semibold text-ink-light mb-2 uppercase tracking-wide">How Far from Average?</h4>
            <div className="space-y-1.5 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-fact/20 border border-fact/40 flex-shrink-0" />
                <span className="text-ink-muted">|z| &lt; 1: close to the corpus average</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-suspension/20 border border-suspension/40 flex-shrink-0" />
                <span className="text-ink-muted">1 &lt; |z| &lt; 2: noticeably different</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-structural/20 border border-structural/40 flex-shrink-0" />
                <span className="text-ink-muted">|z| &gt; 2: well outside the usual range</span>
              </div>
            </div>
          </div>
        </div>

        {/* Tool workspace */}
        <div className="lg:col-span-3">
          <h2 className="text-xl font-serif font-semibold mb-2">{tool.title}</h2>
          <p className="text-sm text-ink-light mb-6">{tool.description}</p>

          <ToolWorkspace tool={activeTool} />
        </div>
      </div>
    </div>
  );
}
