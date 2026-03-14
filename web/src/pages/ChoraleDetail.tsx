import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchChoraleDetail } from '@/lib/api';
import { PianoRoll } from '@/components/score/PianoRoll';
import { HarmonicOverlay } from '@/components/score/HarmonicOverlay';
import { PlaybackControls } from '@/components/score/PlaybackControls';
import { VoiceLeadingView } from '@/components/score/VoiceLeadingView';
import { useAudioPlayer } from '@/hooks/useAudioPlayer';
import { ExportButtons } from '@/components/shared/ExportButtons';
import type { AnalyticalClaim } from '@/types';

type ScoreView = 'piano-roll' | 'voice-leading';

const EVIDENCE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  SUPPORTED_FACT: { bg: 'bg-fact/10', text: 'text-fact', label: 'Clear' },
  INFERENCE: { bg: 'bg-inference/10', text: 'text-inference', label: 'Likely' },
  SPECULATION: { bg: 'bg-speculation/10', text: 'text-speculation', label: 'Tentative' },
  DISPUTED: { bg: 'bg-disputed/10', text: 'text-disputed', label: 'Disputed' },
};

const CLAIM_LABELS: Record<string, string> = {
  analysis_summary: 'Harmony note',
  voiceleading_summary: 'Voice-leading note',
};

function EvidenceBadge({ status }: { status: string }) {
  const style = EVIDENCE_COLORS[status] || EVIDENCE_COLORS.INFERENCE;
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

function ClaimCard({ claim }: { claim: AnalyticalClaim }) {
  const claimLabel = CLAIM_LABELS[claim.claim_type] || claim.claim_type.replace(/_/g, ' ');

  return (
    <div className="p-3 rounded-lg border border-border bg-surface-warm">
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-xs font-medium text-ink-muted capitalize">{claimLabel}</span>
        <EvidenceBadge status={claim.evidence_status} />
      </div>
      <p className="text-sm text-ink leading-relaxed">{claim.description}</p>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="p-4 rounded-lg border border-border bg-surface">
      <div className="text-2xl font-serif font-bold text-primary-dark">{value}</div>
      <div className="text-xs text-ink-muted mt-1">{label}</div>
      {sub && <div className="text-xs text-ink-muted mt-0.5">{sub}</div>}
    </div>
  );
}

export function ChoraleDetail() {
  const { choraleId } = useParams<{ choraleId: string }>();
  const player = useAudioPlayer();
  const [scoreView, setScoreView] = useState<ScoreView>('piano-roll');

  const { data, isLoading, error } = useQuery({
    queryKey: ['chorale', choraleId],
    queryFn: () => fetchChoraleDetail(choraleId!),
    enabled: !!choraleId,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 py-12 text-center text-ink-muted">
        Loading score and analysis for {choraleId}...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 py-12">
        <div className="p-4 bg-structural/10 border border-structural/20 rounded-lg text-sm text-structural">
          Couldn&apos;t load chorale {choraleId}. {String(error || 'No data')}
        </div>
        <Link to="/corpus" className="text-primary text-sm mt-4 inline-block">
          Back to Chorales
        </Link>
      </div>
    );
  }

  const { event_graph, analysis_report, evidence_bundle } = data;
  const report = analysis_report;
  const validation = report.validation_report || {};
  const counterpoint = (report.voice_leading as Record<string, Record<string, number>>)?.counterpoint || {};
  const modGraph = report.modulation_graph as Record<string, unknown> || {};
  const regions = (modGraph.regions || []) as { key: string }[];
  const claims = report.claims || [];

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-ink-muted mb-6">
        <Link to="/corpus" className="hover:text-ink no-underline">Corpus</Link>
        <span>/</span>
        <span className="text-ink font-medium">{data.chorale_id}</span>
      </div>

      {/* Title */}
      <div className="mb-8">
        <h1 className="text-3xl font-serif font-bold text-ink mb-2">
          {data.title || data.chorale_id}
        </h1>
        <div className="flex items-center gap-3 text-sm text-ink-light">
          {report.key && (
            <span className="inline-flex items-center px-2 py-0.5 rounded bg-primary/10 text-primary-dark font-medium">
              {report.key}
            </span>
          )}
          <span className="font-mono text-ink-muted">{data.chorale_id}</span>
          <span className="text-ink-muted">|</span>
          <span>{event_graph.notes.length} notes</span>
          <span className="text-ink-muted">|</span>
          <span>{event_graph.voices.length} voices</span>
        </div>
      </div>

      {/* Score Visualization */}
      <section className="mb-8">
        <div className="flex items-center gap-4 mb-3">
          <h2 className="text-xl font-serif font-semibold">Score</h2>
          <div className="flex gap-1">
            {([['piano-roll', 'Piano Roll'], ['voice-leading', 'Voice Leading']] as [ScoreView, string][]).map(([view, label]) => (
              <button
                key={view}
                onClick={() => setScoreView(view)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  scoreView === view ? 'bg-primary-dark text-white' : 'bg-surface border border-border text-ink-light hover:text-ink'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          {scoreView === 'piano-roll' && (
            <>
              <PianoRoll graph={event_graph} width={1200} height={350} playbackBeat={player.currentBeat} />
              {report.harmony.length > 0 && (
                <HarmonicOverlay graph={event_graph} harmony={report.harmony} cadences={report.cadences} width={1200} />
              )}
            </>
          )}
          {scoreView === 'voice-leading' && (
            <VoiceLeadingView graph={event_graph} width={1200} height={350} />
          )}
        </div>
        <div className="mt-3">
          <PlaybackControls
            state={player.state}
            currentBeat={player.currentBeat}
            duration={player.duration}
            tempo={player.tempo}
            voiceVolumes={player.voiceVolumes}
            onPlay={() => player.play(event_graph)}
            onPause={player.pause}
            onStop={player.stop}
            onTempoChange={player.setTempo}
            onVoiceVolumeChange={player.setVoiceVolume}
          />
        </div>
      </section>

      {/* Stats Grid */}
      <section className="mb-8">
        <h2 className="text-xl font-serif font-semibold mb-3">At a Glance</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <StatCard label="Harmonic Changes" value={report.harmony.length} />
          <StatCard label="Cadences" value={report.cadences.length} />
          <StatCard
            label="Cadence Kinds"
            value={[...new Set(report.cadences.map((c) => c.cadence_type))].length}
            sub={[...new Set(report.cadences.map((c) => c.cadence_type))].join(', ')}
          />
          <StatCard label="Tonal Regions" value={regions.length} />
          <StatCard
            label="Parallel Fifths"
            value={counterpoint.parallel_5ths || 0}
          />
          <StatCard
            label="Parallel Octaves"
            value={counterpoint.parallel_8ves || 0}
          />
        </div>
      </section>

      {/* Modulation Graph */}
      {regions.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xl font-serif font-semibold mb-3">Tonal Regions</h2>
          <div className="flex gap-2 flex-wrap">
            {regions.map((region, i) => (
              <div
                key={i}
                className="px-3 py-2 rounded-lg border border-border bg-surface text-sm"
              >
                <span className="font-serif font-semibold text-primary-dark">{region.key}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Cadences */}
      {report.cadences.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xl font-serif font-semibold mb-3">Cadences</h2>
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-paper-dark/30">
                  <th className="text-left px-4 py-2 font-semibold text-ink-light">Type</th>
                  <th className="text-right px-4 py-2 font-semibold text-ink-light">Onset</th>
                  <th className="text-right px-4 py-2 font-semibold text-ink-light">Strength</th>
                </tr>
              </thead>
              <tbody>
                {report.cadences.map((c, i) => (
                  <tr key={i} className="border-b border-border-light">
                    <td className="px-4 py-2 font-medium text-ink">{c.cadence_type}</td>
                    <td className="px-4 py-2 text-right font-mono text-ink-light">{c.onset}</td>
                    <td className="px-4 py-2 text-right font-mono text-ink-light">
                      {c.strength.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Analytical Claims */}
      {claims.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xl font-serif font-semibold mb-3">
            Reading Notes
            <span className="text-sm font-sans font-normal text-ink-muted ml-2">
              ({claims.length})
            </span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {claims.map((claim, i) => (
              <ClaimCard key={i} claim={claim} />
            ))}
          </div>
        </section>
      )}

      {/* Validation */}
      <section className="mb-8">
        <h2 className="text-xl font-serif font-semibold mb-3">Part-Writing Checks</h2>
        <div className="p-4 rounded-lg border border-border bg-surface">
          <div className="flex items-center gap-2 mb-2">
            <span
              className={`w-3 h-3 rounded-full ${
                (validation as Record<string, boolean>).passed ? 'bg-fact' : 'bg-structural'
              }`}
            />
            <span className="font-semibold text-sm">
              {(validation as Record<string, boolean>).passed ? 'Looks clean' : 'Things to inspect'}
            </span>
          </div>
          {((validation as Record<string, unknown[]>).issues || []).length > 0 && (
            <div className="mt-2 space-y-1">
              {((validation as Record<string, Record<string, string>[]>).issues || []).map((issue, i) => (
                <div key={i} className="text-sm text-ink-light flex items-start gap-2">
                  <span
                    className={`mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                      issue.severity === 'error' ? 'bg-structural' : 'bg-suspension'
                    }`}
                  />
                  <span>{issue.message || JSON.stringify(issue)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Downloads */}
      <section className="mb-8">
        <h2 className="text-xl font-serif font-semibold mb-3">Downloads</h2>
        <div className="flex flex-col gap-3">
          <div>
            <span className="text-sm text-ink-light block mb-2">Export score</span>
            <ExportButtons choraleId={data.chorale_id} />
          </div>
          <div>
            <span className="text-sm text-ink-light block mb-2">Analysis data</span>
            <button
              onClick={() => {
                const blob = new Blob([JSON.stringify(evidence_bundle, null, 2)], {
                  type: 'application/json',
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${data.chorale_id}_evidence_bundle.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface border border-border text-ink-light hover:text-ink hover:border-primary/30 transition-colors"
            >
              Analysis Data (JSON)
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
