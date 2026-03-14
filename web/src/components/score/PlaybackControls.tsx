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
    <div className={`flex flex-col gap-3 rounded-b-xl border border-[#3a3530] bg-charcoal px-4 py-3 shadow-[0_14px_30px_rgba(26,21,18,0.18)] ${compact ? 'rounded-xl' : ''}`}>
      {/* Transport + progress */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Play/Pause */}
        <button
          onClick={state === 'playing' ? onPause : onPlay}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-secondary text-charcoal hover:bg-secondary-light transition-colors shadow-[0_8px_20px_rgba(201,168,76,0.22)]"
          aria-label={state === 'playing' ? 'Pause' : 'Play'}
        >
          {state === 'playing' ? <PauseIcon /> : <PlayIcon />}
        </button>

        {/* Stop */}
        <button
          onClick={onStop}
          disabled={state === 'stopped'}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-white/4 border border-white/10 text-secondary hover:text-secondary-light hover:border-secondary/30 transition-colors disabled:opacity-30"
          aria-label="Stop"
        >
          <StopIcon />
        </button>

        {/* Progress bar */}
        <div className="flex-1 flex items-center gap-2 min-w-[180px]">
          <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-secondary rounded-full transition-[width] duration-75"
              style={{ width: `${Math.min(100, progress)}%` }}
            />
          </div>
          <span className="text-xs font-mono text-[#b9b1a8] w-16 text-right">
            {formatBeat(currentBeat)}
          </span>
        </div>

        {/* Tempo */}
        <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/4 px-3 py-1.5">
          <label className="text-[11px] uppercase tracking-[0.18em] text-[#9E9891]" htmlFor="tempo-slider">BPM</label>
          <input
            id="tempo-slider"
            type="range"
            min={60}
            max={180}
            step={5}
            value={tempo}
            onChange={(e) => onTempoChange(Number(e.target.value))}
            className="w-16 h-1 accent-secondary"
          />
          <span className="text-xs font-mono text-secondary w-6">{tempo}</span>
        </div>
      </div>

      {/* Voice mixer (hide in compact mode) */}
      {!compact && (
        <div className="flex flex-wrap items-center gap-3">
          {(['S', 'A', 'T', 'B'] as const).map((voice) => (
            <div key={voice} className="flex items-center gap-2 rounded-full border border-white/10 bg-white/4 px-3 py-1.5">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: VOICE_COLORS[voice] }}
              />
              <span className="text-[11px] uppercase tracking-[0.18em] text-[#b9b1a8] w-7">{VOICE_NAMES[voice].slice(0, 3)}</span>
              <input
                type="range"
                min={-30}
                max={0}
                step={1}
                value={voiceVolumes[voice]}
                onChange={(e) => onVoiceVolumeChange(voice, Number(e.target.value))}
                className="w-14 h-1 accent-secondary"
                aria-label={`${VOICE_NAMES[voice]} volume`}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
