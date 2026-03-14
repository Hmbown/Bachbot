import { useRef, useState, useCallback, useEffect } from 'react';
import * as Tone from 'tone';
import type { EventGraph, TypedNote } from '@/types';
import { normalizeVoiceId } from '@/types';

export type PlaybackState = 'stopped' | 'playing' | 'paused';

export interface VoiceVolumes {
  S: number;
  A: number;
  T: number;
  B: number;
}

interface PlayerState {
  state: PlaybackState;
  currentBeat: number;
  tempo: number;
  voiceVolumes: VoiceVolumes;
  duration: number;
}

// Voice-specific timbre settings (passed as RecursivePartial)
const VOICE_TIMBRES = {
  S: { oscillator: { type: 'triangle' }, envelope: { attack: 0.02, decay: 0.3, sustain: 0.6, release: 0.4 } },
  A: { oscillator: { type: 'sine' }, envelope: { attack: 0.03, decay: 0.3, sustain: 0.5, release: 0.4 } },
  T: { oscillator: { type: 'fatsawtooth', count: 2, spread: 10 }, envelope: { attack: 0.04, decay: 0.3, sustain: 0.4, release: 0.5 } },
  B: { oscillator: { type: 'sawtooth' }, envelope: { attack: 0.05, decay: 0.4, sustain: 0.5, release: 0.6 } },
} as const;

function midiToFreq(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

export function useAudioPlayer() {
  const [playerState, setPlayerState] = useState<PlayerState>({
    state: 'stopped',
    currentBeat: 0,
    tempo: 100,
    voiceVolumes: { S: 0, A: 0, T: 0, B: 0 },
    duration: 0,
  });

  const synthsRef = useRef<Record<string, Tone.PolySynth> | null>(null);
  const gainsRef = useRef<Record<string, Tone.Gain> | null>(null);
  const partsRef = useRef<Tone.Part[]>([]);
  const beatIntervalRef = useRef<number | null>(null);
  const graphRef = useRef<EventGraph | null>(null);
  const startTimeRef = useRef<number>(0);

  const initAudio = useCallback(async () => {
    if (Tone.getContext().state !== 'running') {
      await Tone.start();
    }

    if (!synthsRef.current) {
      const gains: Record<string, Tone.Gain> = {};
      const synths: Record<string, Tone.PolySynth> = {};

      for (const voice of ['S', 'A', 'T', 'B'] as const) {
        const gain = new Tone.Gain(0.3).toDestination();
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const synth = new Tone.PolySynth(Tone.Synth, VOICE_TIMBRES[voice] as any).connect(gain);
        gains[voice] = gain;
        synths[voice] = synth;
      }

      gainsRef.current = gains;
      synthsRef.current = synths;
    }
  }, []);

  const scheduleNotes = useCallback((graph: EventGraph, tempo: number) => {
    // Clear existing parts
    for (const part of partsRef.current) {
      part.dispose();
    }
    partsRef.current = [];

    Tone.getTransport().bpm.value = tempo;

    const byVoice: Record<string, { time: number; midi: number; dur: number }[]> = {
      S: [], A: [], T: [], B: [],
    };

    const pitched = graph.notes.filter((n: TypedNote) => !n.is_rest && n.midi > 0);
    let maxTime = 0;

    for (const note of pitched) {
      const voice = normalizeVoiceId(note.voice_id);
      const timeInBeats = note.offset_quarters;
      const durInBeats = note.duration_quarters;
      byVoice[voice].push({ time: timeInBeats, midi: note.midi, dur: durInBeats });
      maxTime = Math.max(maxTime, timeInBeats + durInBeats);
    }

    setPlayerState((s) => ({ ...s, duration: maxTime }));

    for (const voice of ['S', 'A', 'T', 'B'] as const) {
      const synth = synthsRef.current?.[voice];
      if (!synth || byVoice[voice].length === 0) continue;

      const events = byVoice[voice].map((e) => ({
        time: `0:${e.time}:0`,
        freq: midiToFreq(e.midi),
        dur: `0:${e.dur}:0`,
      }));

      const part = new Tone.Part((time, event) => {
        synth.triggerAttackRelease(event.freq, event.dur, time, 0.7);
      }, events);

      part.start(0);
      partsRef.current.push(part);
    }

    // Schedule stop at end
    Tone.getTransport().scheduleOnce(() => {
      stop();
    }, `0:${maxTime + 0.5}:0`);
  }, []);

  const play = useCallback(async (graph: EventGraph) => {
    await initAudio();
    graphRef.current = graph;

    const transport = Tone.getTransport();

    if (playerState.state === 'paused') {
      transport.start();
      startBeatTracker();
      setPlayerState((s) => ({ ...s, state: 'playing' }));
      return;
    }

    transport.stop();
    transport.cancel();
    transport.position = 0;

    scheduleNotes(graph, playerState.tempo);
    startTimeRef.current = Date.now();
    transport.start();
    startBeatTracker();
    setPlayerState((s) => ({ ...s, state: 'playing', currentBeat: 0 }));
  }, [initAudio, scheduleNotes, playerState.state, playerState.tempo]);

  const pause = useCallback(() => {
    Tone.getTransport().pause();
    stopBeatTracker();
    setPlayerState((s) => ({ ...s, state: 'paused' }));
  }, []);

  const stop = useCallback(() => {
    const transport = Tone.getTransport();
    transport.stop();
    transport.cancel();
    transport.position = 0;
    stopBeatTracker();

    // Release all notes
    if (synthsRef.current) {
      for (const synth of Object.values(synthsRef.current)) {
        synth.releaseAll();
      }
    }

    setPlayerState((s) => ({ ...s, state: 'stopped', currentBeat: 0 }));
  }, []);

  const setTempo = useCallback((bpm: number) => {
    Tone.getTransport().bpm.value = bpm;
    setPlayerState((s) => ({ ...s, tempo: bpm }));
  }, []);

  const setVoiceVolume = useCallback((voice: string, db: number) => {
    if (gainsRef.current?.[voice]) {
      gainsRef.current[voice].gain.value = db <= -30 ? 0 : Math.pow(10, db / 20) * 0.3;
    }
    setPlayerState((s) => ({
      ...s,
      voiceVolumes: { ...s.voiceVolumes, [voice]: db },
    }));
  }, []);

  const startBeatTracker = useCallback(() => {
    stopBeatTracker();
    beatIntervalRef.current = window.setInterval(() => {
      const transport = Tone.getTransport();
      const parts = String(transport.position).split(':');
      const bars = parseFloat(parts[0] || '0');
      const beats = parseFloat(parts[1] || '0');
      const sixteenths = parseFloat(parts[2] || '0');
      const currentBeat = bars * 4 + beats + sixteenths / 4;
      setPlayerState((s) => ({ ...s, currentBeat }));
    }, 50);
  }, []);

  const stopBeatTracker = useCallback(() => {
    if (beatIntervalRef.current !== null) {
      clearInterval(beatIntervalRef.current);
      beatIntervalRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopBeatTracker();
      const transport = Tone.getTransport();
      transport.stop();
      transport.cancel();
      for (const part of partsRef.current) {
        part.dispose();
      }
      if (synthsRef.current) {
        for (const synth of Object.values(synthsRef.current)) {
          synth.releaseAll();
          synth.dispose();
        }
        synthsRef.current = null;
      }
      if (gainsRef.current) {
        for (const gain of Object.values(gainsRef.current)) {
          gain.dispose();
        }
        gainsRef.current = null;
      }
    };
  }, [stopBeatTracker]);

  return {
    ...playerState,
    play,
    pause,
    stop,
    setTempo,
    setVoiceVolume,
  };
}
