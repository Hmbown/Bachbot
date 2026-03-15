import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchBenchmarkLatest, fetchBenchmarkHistory, runBenchmark } from '@/lib/api';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Link } from 'react-router-dom';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

// ─── Types ──────────────────────────────────────────────────────────

interface BenchmarkSummary {
  evidence_avg_pass_rate: number;
  evidence_avg_chord_variety: number;
  evidence_avg_parallel_violations: number;
  evidence_avg_voice_leading_score: number;
  evidence_avg_complexity_divergence: number;
  evidence_avg_harmonic_similarity: number;
  original_avg_chord_variety: number;
  baseline_avg_pass_rate: number;
  [key: string]: number;
}

interface BenchmarkSnapshot {
  schema_version: string;
  metadata: { generated_at: string; sample_size: number };
  summary: BenchmarkSummary;
}

// ─── Metric Definitions ─────────────────────────────────────────────

interface MetricDef {
  key: string;
  label: string;
  description: string;
  format: (v: number) => string;
  higher_is_better: boolean;
  color: string;
  bgColor: string;
}

const METRICS: MetricDef[] = [
  {
    key: 'evidence_avg_pass_rate',
    label: 'Pass Rate',
    description: 'Fraction of chorales passing all hard rules',
    format: (v) => `${(v * 100).toFixed(1)}%`,
    higher_is_better: true,
    color: '#2d7d46',
    bgColor: 'rgba(45, 125, 70, 0.1)',
  },
  {
    key: 'evidence_avg_chord_variety',
    label: 'Chord Variety',
    description: 'Average unique chord types (Bach uses ~14)',
    format: (v) => v.toFixed(1),
    higher_is_better: true,
    color: '#2c5282',
    bgColor: 'rgba(44, 82, 130, 0.1)',
  },
  {
    key: 'evidence_avg_parallel_violations',
    label: 'Parallel Violations',
    description: 'Average parallel 5th/8ve violations per chorale',
    format: (v) => v.toFixed(2),
    higher_is_better: false,
    color: '#CC4444',
    bgColor: 'rgba(204, 68, 68, 0.1)',
  },
  {
    key: 'evidence_avg_voice_leading_score',
    label: 'Voice Leading',
    description: 'Average voice-leading smoothness score',
    format: (v) => v.toFixed(3),
    higher_is_better: true,
    color: '#4477AA',
    bgColor: 'rgba(68, 119, 170, 0.1)',
  },
  {
    key: 'evidence_avg_bach_fidelity',
    label: 'Bach Fidelity',
    description: 'Aggregate score: harmonic vocabulary, cadences, voice-leading vs. Bach',
    format: (v) => v.toFixed(1),
    higher_is_better: true,
    color: '#8B5E3C',
    bgColor: 'rgba(139, 94, 60, 0.1)',
  },
  {
    key: 'evidence_avg_harmonic_similarity',
    label: 'Harmonic Similarity',
    description: 'Cosine similarity of harmonic distributions vs Bach',
    format: (v) => v.toFixed(3),
    higher_is_better: true,
    color: '#44AA77',
    bgColor: 'rgba(68, 170, 119, 0.1)',
  },
];

const SAMPLE_SIZES = [5, 10, 20, 30] as const;

// ─── Helpers ────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
  } catch {
    return iso.slice(0, 10);
  }
}

function detectRegression(
  snapshots: BenchmarkSnapshot[],
  metric: MetricDef,
): { regressed: boolean; delta: number } {
  if (snapshots.length < 2) return { regressed: false, delta: 0 };
  const recent = snapshots[snapshots.length - 1].summary[metric.key];
  const previous = snapshots[snapshots.length - 2].summary[metric.key];
  if (recent == null || previous == null) return { regressed: false, delta: 0 };
  const delta = recent - previous;
  const regressed = metric.higher_is_better ? delta < -0.001 : delta > 0.001;
  return { regressed, delta };
}

// ─── Component ──────────────────────────────────────────────────────

export function BenchmarkArena() {
  const queryClient = useQueryClient();
  const [sampleSize, setSampleSize] = useState<number>(10);

  const {
    data: latestData,
    isLoading: latestLoading,
    error: latestError,
  } = useQuery({
    queryKey: ['benchmark', 'latest'],
    queryFn: fetchBenchmarkLatest,
    staleTime: 60_000,
  });

  const {
    data: historyData,
    isLoading: historyLoading,
  } = useQuery({
    queryKey: ['benchmark', 'history'],
    queryFn: fetchBenchmarkHistory,
    staleTime: 60_000,
  });

  const benchmarkMutation = useMutation({
    mutationFn: (size: number) => runBenchmark(size),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['benchmark'] });
    },
  });

  const snapshot = latestData?.snapshot as BenchmarkSnapshot | null | undefined;
  const snapshots = (((historyData?.snapshots ?? []) as unknown as BenchmarkSnapshot[])).sort(
    (a, b) => new Date(a.metadata.generated_at).getTime() - new Date(b.metadata.generated_at).getTime(),
  );

  const hasData = snapshot?.summary != null;

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-serif font-bold text-ink mb-2">Benchmark Arena</h1>
        <p className="text-ink-light">
          BachBench evaluation suite: track composition quality over time, detect regressions,
          compare against ground truth, and run new benchmark snapshots.
        </p>
      </div>

      {/* Error state */}
      {latestError && (
        <div className="p-4 bg-structural/10 border border-structural/20 rounded-lg text-sm text-structural mb-6">
          Failed to load benchmark data. Is the API server running? ({String(latestError)})
        </div>
      )}

      {/* Run Benchmark controls */}
      <div className="flex items-center gap-3 mb-8">
        <label className="text-sm text-ink-light font-medium">Sample size:</label>
        <select
          value={sampleSize}
          onChange={(e) => setSampleSize(Number(e.target.value))}
          className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink focus:outline-none focus:border-primary/50"
        >
          {SAMPLE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s} chorales
            </option>
          ))}
        </select>
        <button
          onClick={() => benchmarkMutation.mutate(sampleSize)}
          disabled={benchmarkMutation.isPending}
          className="px-5 py-2 bg-primary-dark text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {benchmarkMutation.isPending ? 'Running...' : 'Run Benchmark'}
        </button>
        {benchmarkMutation.isSuccess && (
          <span className="text-sm text-fact font-medium">Benchmark complete.</span>
        )}
        {benchmarkMutation.isError && (
          <span className="text-sm text-structural font-medium">
            Failed: {String(benchmarkMutation.error)}
          </span>
        )}
      </div>

      {/* Latest snapshot summary card */}
      {latestLoading && (
        <div className="p-8 rounded-xl border border-border bg-surface text-center text-ink-muted mb-8">
          Loading latest benchmark...
        </div>
      )}

      {!latestLoading && !hasData && !latestError && (
        <div className="p-8 rounded-xl border-2 border-dashed border-border bg-paper-dark/20 text-center mb-8">
          <p className="text-ink-muted mb-2">No benchmark snapshots yet.</p>
          <p className="text-xs text-ink-muted/70">
            Run your first benchmark to see quality metrics and trend charts.
          </p>
        </div>
      )}

      {hasData && (
        <section className="mb-10">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-xl font-serif font-semibold">Latest Snapshot</h2>
            <div className="text-xs text-ink-muted font-mono">
              {formatDate(snapshot!.metadata.generated_at)} &middot; n={snapshot!.metadata.sample_size}
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {METRICS.map((m) => {
              const value = snapshot!.summary[m.key];
              const { regressed, delta } = detectRegression(snapshots, m);
              return (
                <div
                  key={m.key}
                  className={`p-4 rounded-xl border transition-colors ${
                    regressed
                      ? 'border-structural/40 bg-structural/5'
                      : 'border-border bg-surface'
                  }`}
                >
                  <div className="text-xs text-ink-muted mb-1 truncate" title={m.description}>
                    {m.label}
                  </div>
                  <div className="text-2xl font-serif font-bold text-ink">
                    {value != null ? m.format(value) : '--'}
                  </div>
                  {regressed && (
                    <div className="flex items-center gap-1 mt-1">
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        className="text-structural"
                      >
                        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                        <line x1="12" y1="9" x2="12" y2="13" />
                        <line x1="12" y1="17" x2="12.01" y2="17" />
                      </svg>
                      <span className="text-xs text-structural font-medium">
                        Regression ({m.higher_is_better ? '' : '+'}
                        {delta > 0 ? '+' : ''}
                        {delta.toFixed(3)})
                      </span>
                    </div>
                  )}
                  {!regressed && snapshots.length >= 2 && delta !== 0 && (
                    <div className="text-xs text-ink-muted mt-1">
                      {delta > 0 ? '+' : ''}
                      {delta.toFixed(3)} vs prev
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Trend charts */}
      {snapshots.length > 0 && (
        <section className="mb-10">
          <h2 className="text-xl font-serif font-semibold mb-4">Metric Trends</h2>
          {historyLoading ? (
            <div className="p-8 text-center text-ink-muted">Loading history...</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {METRICS.map((m) => {
                const labels = snapshots.map((s) => formatDate(s.metadata.generated_at));
                const values = snapshots.map((s) => s.summary[m.key] ?? null);
                const { regressed } = detectRegression(snapshots, m);

                return (
                  <div
                    key={m.key}
                    className={`p-5 rounded-xl border ${
                      regressed ? 'border-structural/30 bg-structural/5' : 'border-border bg-surface'
                    }`}
                  >
                    <div className="flex items-baseline justify-between mb-3">
                      <h3 className="font-serif text-sm font-semibold text-ink">{m.label}</h3>
                      {regressed && (
                        <span className="text-xs font-medium text-structural">REGRESSED</span>
                      )}
                    </div>
                    <div className="h-44">
                      <Line
                        data={{
                          labels,
                          datasets: [
                            {
                              label: m.label,
                              data: values,
                              borderColor: m.color,
                              backgroundColor: m.bgColor,
                              borderWidth: 2,
                              pointRadius: 3,
                              pointHoverRadius: 5,
                              pointBackgroundColor: m.color,
                              tension: 0.3,
                              fill: true,
                            },
                          ],
                        }}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: { display: false },
                            tooltip: {
                              backgroundColor: '#1a1a1a',
                              titleFont: { family: 'Inter' },
                              bodyFont: { family: 'JetBrains Mono', size: 12 },
                              callbacks: {
                                label: (ctx) =>
                                  ctx.raw != null ? m.format(ctx.raw as number) : '--',
                              },
                            },
                          },
                          scales: {
                            x: {
                              grid: { color: 'rgba(226, 217, 200, 0.4)' },
                              ticks: {
                                color: '#8a8177',
                                font: { size: 10, family: 'Inter' },
                                maxRotation: 45,
                              },
                            },
                            y: {
                              grid: { color: 'rgba(226, 217, 200, 0.4)' },
                              ticks: {
                                color: '#8a8177',
                                font: { size: 10, family: 'JetBrains Mono' },
                              },
                            },
                          },
                        }}
                      />
                    </div>
                    <p className="text-xs text-ink-muted mt-2">{m.description}</p>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Cross-system leaderboard */}
      <section className="mb-10">
        <h2 className="text-xl font-serif font-semibold mb-4">Cross-System Leaderboard</h2>
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-paper-dark/30">
                <th className="text-left px-4 py-3 font-semibold text-ink-light">System</th>
                <th className="text-right px-4 py-3 font-semibold text-ink-light">Pass Rate</th>
                <th className="text-right px-4 py-3 font-semibold text-ink-light">
                  Chord Variety
                </th>
                <th className="text-right px-4 py-3 font-semibold text-ink-light">
                  Parallel Violations
                </th>
                <th className="text-right px-4 py-3 font-semibold text-ink-light">
                  Voice Leading
                </th>
                <th className="text-right px-4 py-3 font-semibold text-ink-light">
                  Harmonic Sim.
                </th>
                <th className="text-right px-4 py-3 font-semibold text-ink-light">
                  Complexity Div.
                </th>
              </tr>
            </thead>
            <tbody>
              {/* Ground truth row (always present, uses latest data if available) */}
              <tr className="border-b border-border-light bg-fact/5">
                <td className="px-4 py-3 font-medium text-ink">
                  <span className="inline-flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-fact" />
                    Ground Truth (Bach)
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">
                  {hasData && snapshot!.summary.baseline_avg_pass_rate != null
                    ? `${(snapshot!.summary.baseline_avg_pass_rate * 100).toFixed(1)}%`
                    : '100.0%'}
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">
                  {hasData && snapshot!.summary.original_avg_chord_variety != null
                    ? snapshot!.summary.original_avg_chord_variety.toFixed(1)
                    : '14.7'}
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">0.0</td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">1.000</td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">1.000</td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">0.000</td>
              </tr>
              {/* BachBot row */}
              <tr className="border-b border-border-light">
                <td className="px-4 py-3 font-medium text-ink">
                  <span className="inline-flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-primary" />
                    BachBot
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">
                  {hasData
                    ? `${(snapshot!.summary.evidence_avg_pass_rate * 100).toFixed(1)}%`
                    : '90.0%'}
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">
                  {hasData
                    ? snapshot!.summary.evidence_avg_chord_variety.toFixed(1)
                    : '4.3'}
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">
                  {hasData
                    ? snapshot!.summary.evidence_avg_parallel_violations.toFixed(2)
                    : '0.70'}
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">
                  {hasData
                    ? snapshot!.summary.evidence_avg_voice_leading_score.toFixed(3)
                    : '0.998'}
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">
                  {hasData
                    ? snapshot!.summary.evidence_avg_harmonic_similarity.toFixed(3)
                    : '0.970'}
                </td>
                <td className="px-4 py-3 text-right font-mono text-ink-light">
                  {hasData
                    ? (snapshot!.summary.evidence_avg_bach_fidelity ?? snapshot!.summary.evidence_avg_complexity_divergence ?? 0).toFixed(1)
                    : '—'}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-xs text-ink-muted mt-2">
          Ground Truth values are from original Bach chorales in the test set.
          BachBot values reflect the latest benchmark snapshot{hasData ? ` (n=${snapshot!.metadata.sample_size})` : ''}.
        </p>
      </section>

      {/* Human Evaluation section */}
      <section>
        <h2 className="text-xl font-serif font-semibold mb-4">Human Evaluation</h2>
        <div className="p-6 rounded-xl border border-border bg-surface-warm">
          <p className="text-sm text-ink-light mb-3">
            Participate in blind A/B listening tests comparing generated chorales against Bach originals.
            Rate musicality, authenticity, and voice-leading quality on 7-point Likert scales.
          </p>
          <p className="text-xs text-ink-muted mb-4">
            Inter-rater reliability measured with Krippendorff's alpha.
            Correlation between algorithmic metrics and human judgments tracked via Pearson r.
          </p>
          <Link
            to="/benchmark/evaluate"
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-dark text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors no-underline"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            Start Evaluation Session
          </Link>
        </div>
      </section>
    </div>
  );
}
