import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { startEvaluation, submitRating, fetchEvalResults } from '@/lib/api';
import { useAudioPlayer } from '@/hooks/useAudioPlayer';
import { PlaybackControls } from '@/components/score/PlaybackControls';
import type { EventGraph } from '@/types';

function LikertScale({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="mb-3">
      <label className="block text-sm font-medium text-ink-light mb-1">{label}</label>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5, 6, 7].map((n) => (
          <button
            key={n}
            onClick={() => onChange(n)}
            className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${
              value === n ? 'bg-primary-dark text-white' : 'bg-surface border border-border text-ink-light hover:text-ink hover:border-primary/30'
            }`}
          >
            {n}
          </button>
        ))}
      </div>
      <div className="flex justify-between text-xs text-ink-muted mt-0.5">
        <span>Poor</span>
        <span>Excellent</span>
      </div>
    </div>
  );
}

function AudioPanel({ label, eventGraph }: { label: string; eventGraph?: EventGraph }) {
  const player = useAudioPlayer();

  if (!eventGraph) {
    return (
      <div className="p-6 rounded-xl border border-border bg-surface text-center text-ink-muted text-sm">
        Audio for {label} will be loaded from the evaluation pair
      </div>
    );
  }

  return (
    <div className="p-4 rounded-xl border border-border bg-surface">
      <h3 className="text-lg font-serif font-semibold mb-2">{label}</h3>
      <PlaybackControls
        state={player.state}
        currentBeat={player.currentBeat}
        duration={player.duration}
        tempo={player.tempo}
        voiceVolumes={player.voiceVolumes}
        onPlay={() => player.play(eventGraph)}
        onPause={player.pause}
        onStop={player.stop}
        onTempoChange={player.setTempo}
        onVoiceVolumeChange={player.setVoiceVolume}
        compact
      />
    </div>
  );
}

type EvalPhase = 'setup' | 'evaluating' | 'results';

export function HumanEvaluation() {
  const [phase, setPhase] = useState<EvalPhase>('setup');
  const [evaluatorId, setEvaluatorId] = useState('');
  const [sessionData, setSessionData] = useState<Record<string, unknown> | null>(null);
  const [currentPairIndex, setCurrentPairIndex] = useState(0);
  const [ratings, setRatings] = useState({
    musicality_a: 4, musicality_b: 4,
    authenticity_a: 4, authenticity_b: 4,
    voice_leading_a: 4, voice_leading_b: 4,
    identified_original: 'unsure' as string,
    notes: '',
  });

  const startMut = useMutation({
    mutationFn: (evalId: string) => startEvaluation(evalId),
    onSuccess: (data) => {
      setSessionData(data);
      setPhase('evaluating');
    },
  });

  const rateMut = useMutation({
    mutationFn: (rating: Record<string, unknown>) => submitRating(rating),
    onSuccess: () => {
      const pairs = (sessionData as Record<string, unknown[]>)?.pairs || [];
      if (currentPairIndex < pairs.length - 1) {
        setCurrentPairIndex((i) => i + 1);
        setRatings({
          musicality_a: 4, musicality_b: 4, authenticity_a: 4, authenticity_b: 4,
          voice_leading_a: 4, voice_leading_b: 4, identified_original: 'unsure', notes: '',
        });
      } else {
        setPhase('results');
      }
    },
  });

  const resultsQuery = useQuery({
    queryKey: ['evaluation-results'],
    queryFn: fetchEvalResults,
    enabled: phase === 'results',
  });

  if (phase === 'setup') {
    return (
      <div className="max-w-[800px] mx-auto px-6 py-12">
        <h1 className="text-3xl font-serif font-bold text-ink mb-4">Human Evaluation</h1>
        <p className="text-ink-light mb-6">
          Participate in a blind A/B listening test comparing generated chorales against Bach originals.
          Rate musicality, authenticity, and voice-leading quality on 7-point Likert scales.
        </p>
        <div className="p-6 rounded-xl border border-border bg-surface">
          <label className="block text-sm font-medium text-ink-light mb-2">Your Evaluator ID</label>
          <input
            type="text"
            value={evaluatorId}
            onChange={(e) => setEvaluatorId(e.target.value)}
            placeholder="Enter your name or ID..."
            className="w-full px-3 py-2 rounded-lg border border-border bg-paper text-sm text-ink placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 mb-4"
          />
          <button
            onClick={() => evaluatorId.trim() && startMut.mutate(evaluatorId.trim())}
            disabled={!evaluatorId.trim() || startMut.isPending}
            className="px-6 py-2.5 bg-primary-dark text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
          >
            {startMut.isPending ? 'Starting...' : 'Start Evaluation'}
          </button>
          {startMut.error && (
            <div className="mt-3 p-3 bg-structural/10 border border-structural/20 rounded-lg text-sm text-structural">
              {String(startMut.error)}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (phase === 'evaluating') {
    const pairs = (sessionData as Record<string, unknown[]>)?.pairs || [];
    const pair = pairs[currentPairIndex] as Record<string, string> | undefined;

    return (
      <div className="max-w-[1200px] mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-serif font-bold text-ink">
            Pair {currentPairIndex + 1} of {pairs.length}
          </h1>
          <div className="text-sm text-ink-muted">
            Evaluator: <span className="font-medium text-ink">{evaluatorId}</span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-2 bg-paper-dark rounded-full mb-8 overflow-hidden">
          <div className="h-full bg-primary-dark rounded-full transition-all" style={{ width: `${((currentPairIndex) / pairs.length) * 100}%` }} />
        </div>

        {/* Audio panels */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <AudioPanel label="Chorale A" eventGraph={(pair as Record<string, unknown>)?.event_graph_a as EventGraph | undefined} />
          <AudioPanel label="Chorale B" eventGraph={(pair as Record<string, unknown>)?.event_graph_b as EventGraph | undefined} />
        </div>

        {/* Rating form */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div className="p-4 rounded-xl border border-border bg-surface">
            <h3 className="font-serif font-semibold mb-3">Rate Chorale A</h3>
            <LikertScale label="Musicality" value={ratings.musicality_a} onChange={(v) => setRatings({ ...ratings, musicality_a: v })} />
            <LikertScale label="Authenticity (Bach-likeness)" value={ratings.authenticity_a} onChange={(v) => setRatings({ ...ratings, authenticity_a: v })} />
            <LikertScale label="Voice-Leading Quality" value={ratings.voice_leading_a} onChange={(v) => setRatings({ ...ratings, voice_leading_a: v })} />
          </div>
          <div className="p-4 rounded-xl border border-border bg-surface">
            <h3 className="font-serif font-semibold mb-3">Rate Chorale B</h3>
            <LikertScale label="Musicality" value={ratings.musicality_b} onChange={(v) => setRatings({ ...ratings, musicality_b: v })} />
            <LikertScale label="Authenticity (Bach-likeness)" value={ratings.authenticity_b} onChange={(v) => setRatings({ ...ratings, authenticity_b: v })} />
            <LikertScale label="Voice-Leading Quality" value={ratings.voice_leading_b} onChange={(v) => setRatings({ ...ratings, voice_leading_b: v })} />
          </div>
        </div>

        {/* Which is Bach? */}
        <div className="p-4 rounded-xl border border-border bg-surface mb-6">
          <label className="block text-sm font-medium text-ink-light mb-2">Which do you think is the Bach original?</label>
          <div className="flex gap-3">
            {[['a', 'Chorale A'], ['b', 'Chorale B'], ['unsure', 'Unsure']].map(([val, label]) => (
              <button
                key={val}
                onClick={() => setRatings({ ...ratings, identified_original: val })}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  ratings.identified_original === val ? 'bg-primary-dark text-white' : 'bg-surface border border-border text-ink-light hover:text-ink'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-ink-light mb-1">Notes (optional)</label>
          <textarea
            value={ratings.notes}
            onChange={(e) => setRatings({ ...ratings, notes: e.target.value })}
            placeholder="Any observations..."
            className="w-full h-20 px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 resize-y"
          />
        </div>

        <button
          onClick={() => rateMut.mutate({ pair_id: pair?.pair_id || '', evaluator_id: evaluatorId, ...ratings })}
          disabled={rateMut.isPending}
          className="px-8 py-3 bg-primary-dark text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
        >
          {rateMut.isPending ? 'Submitting...' : currentPairIndex < pairs.length - 1 ? 'Submit & Next' : 'Submit & View Results'}
        </button>
      </div>
    );
  }

  // Results phase
  const results = resultsQuery.data as Record<string, number> | undefined;

  return (
    <div className="max-w-[800px] mx-auto px-6 py-12">
      <h1 className="text-3xl font-serif font-bold text-ink mb-4">Evaluation Complete</h1>
      <p className="text-ink-light mb-6">Thank you for participating! Your ratings have been recorded.</p>

      {results && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="p-4 rounded-lg border border-border bg-surface">
            <div className="text-2xl font-serif font-bold text-primary-dark">{results.total_ratings || 0}</div>
            <div className="text-xs text-ink-muted">Total Ratings</div>
          </div>
          <div className="p-4 rounded-lg border border-border bg-surface">
            <div className="text-2xl font-serif font-bold text-primary-dark">{((results.identification_accuracy || 0) * 100).toFixed(0)}%</div>
            <div className="text-xs text-ink-muted">Identification Accuracy</div>
          </div>
        </div>
      )}
    </div>
  );
}
