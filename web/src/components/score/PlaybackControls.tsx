import type { PlaybackState, VoiceVolumes } from '@/hooks/useAudioPlayer';
import { VOICE_COLORS, VOICE_NAMES } from '@/types';

interface PlaybackControlsProps {
  state: PlaybackState;
  currentBeat: number;
  duration: number;
  tempo: number;
  voiceVolumes: VoiceVolumes;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  onTempoChange: (bpm: number) => void;
  onVoiceVolumeChange: (voice: string, db: number) => void;
  compact?: boolean;
}

function PlayIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
      <path d="M4 2.5v11l9-5.5L4 2.5z" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
      <rect x="3" y="2" width="3.5" height="12" rx="0.5" />
      <rect x="9.5" y="2" width="3.5" height="12" rx="0.5" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
      <rect x="3" y="3" width="10" height="10" rx="1" />
    </svg>
  );
}

function formatBeat(beat: number): string {
  const measure = Math.floor(beat / 4) + 1;
  const b = (beat % 4) + 1;
  return `m${measure} b${b.toFixed(1)}`;
}

export function PlaybackControls({
  state,
  currentBeat,
  duration,
  tempo,
  voiceVolumes,
  onPlay,
  onPause,
  onStop,
  onTempoChange,
  onVoiceVolumeChange,
  compact = false,
}: PlaybackControlsProps) {
  const progress = duration > 0 ? (currentBeat / duration) * 100 : 0;

  return (
    <div className="flex flex-col gap-2">
      {/* Transport + progress */}
      <div className="flex items-center gap-3">
        {/* Play/Pause */}
        <button
          onClick={state === 'playing' ? onPause : onPlay}
          className="w-9 h-9 flex items-center justify-center rounded-lg bg-primary-dark text-white hover:bg-primary transition-colors"
          aria-label={state === 'playing' ? 'Pause' : 'Play'}
        >
          {state === 'playing' ? <PauseIcon /> : <PlayIcon />}
        </button>

        {/* Stop */}
        <button
          onClick={onStop}
          disabled={state === 'stopped'}
          className="w-9 h-9 flex items-center justify-center rounded-lg bg-surface border border-border text-ink-light hover:text-ink hover:border-primary/30 transition-colors disabled:opacity-30"
          aria-label="Stop"
        >
          <StopIcon />
        </button>

        {/* Progress bar */}
        <div className="flex-1 flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-paper-dark rounded-full overflow-hidden">
            <div
              className="h-full bg-primary-dark rounded-full transition-[width] duration-75"
              style={{ width: `${Math.min(100, progress)}%` }}
            />
          </div>
          <span className="text-xs font-mono text-ink-muted w-16 text-right">
            {formatBeat(currentBeat)}
          </span>
        </div>

        {/* Tempo */}
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-ink-muted" htmlFor="tempo-slider">BPM</label>
          <input
            id="tempo-slider"
            type="range"
            min={60}
            max={180}
            step={5}
            value={tempo}
            onChange={(e) => onTempoChange(Number(e.target.value))}
            className="w-16 h-1 accent-primary-dark"
          />
          <span className="text-xs font-mono text-ink-muted w-6">{tempo}</span>
        </div>
      </div>

      {/* Voice mixer (hide in compact mode) */}
      {!compact && (
        <div className="flex items-center gap-4">
          {(['S', 'A', 'T', 'B'] as const).map((voice) => (
            <div key={voice} className="flex items-center gap-1.5">
              <div
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: VOICE_COLORS[voice] }}
              />
              <span className="text-xs text-ink-muted w-6">{VOICE_NAMES[voice].slice(0, 3)}</span>
              <input
                type="range"
                min={-30}
                max={0}
                step={1}
                value={voiceVolumes[voice]}
                onChange={(e) => onVoiceVolumeChange(voice, Number(e.target.value))}
                className="w-12 h-1 accent-primary-dark"
                aria-label={`${VOICE_NAMES[voice]} volume`}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
