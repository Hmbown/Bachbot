import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { composeChorale, composeFiguredBass, composeMelody, composeInvention } from '@/lib/api';
import { PianoRoll } from '@/components/score/PianoRoll';
import { PlaybackControls } from '@/components/score/PlaybackControls';
import { ExportButtons } from '@/components/shared/ExportButtons';
import { useAudioPlayer } from '@/hooks/useAudioPlayer';
import type { ComposeResponse } from '@/types';

type CompositionMode = 'harmonize' | 'figured-bass' | 'melody' | 'invention';

const MODE_INFO: Record<CompositionMode, { title: string; description: string; inputLabel: string }> = {
  harmonize: {
    title: 'Chorale Harmonization',
    description:
      'Paste or step-enter a soprano melody. BachBot harmonizes it into four-part SATB with the two-phase Viterbi engine, secondary dominants, and nonharmonic tones.',
    inputLabel: 'Soprano MusicXML',
  },
  'figured-bass': {
    title: 'Figured Bass Realization',
    description:
      'Enter a bass line with figured bass symbols and generate upper voices using the Viterbi upper-voice search with figure parsing.',
    inputLabel: 'Bass Line MusicXML',
  },
  melody: {
    title: 'Melody Generation',
    description:
      'Select chords from the palette below to build a progression. BachBot generates a singable soprano melody.',
    inputLabel: 'Chord Progression',
  },
  invention: {
    title: 'Two-Part Invention',
    description:
      'Provide a monophonic subject and BachBot generates a complete exposition with tonal answer, invertible countersubject, and sequential episode.',
    inputLabel: 'Subject MusicXML',
  },
};

const EXAMPLE_MUSICXML = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Soprano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type><voice>1</voice></note>
      <note><pitch><step>B</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type><voice>1</voice></note>
      <note><pitch><step>A</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type><voice>1</voice></note>
      <note><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type><voice>1</voice></note>
    </measure>
    <measure number="2">
      <note><pitch><step>F</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type><voice>1</voice></note>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type><voice>1</voice></note>
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type><voice>1</voice></note>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration><type>half</type><voice>1</voice></note>
    </measure>
  </part>
</score-partwise>`;

const CHORD_PALETTE = ['I', 'ii', 'iii', 'IV', 'V', 'vi', 'vii°', 'V/V', 'V/vi', 'IV6', 'V7', 'I6'];
const KEY_OPTIONS = ['C major', 'G major', 'D major', 'F major', 'A minor', 'E minor', 'D minor'];

function MelodyInput({ chords, setChords, selectedKey, setSelectedKey }: {
  chords: string[];
  setChords: (c: string[]) => void;
  selectedKey: string;
  setSelectedKey: (k: string) => void;
}) {
  return (
    <div>
      <div className="mb-3">
        <label className="block text-sm font-medium text-ink-light mb-1">Key</label>
        <select
          value={selectedKey}
          onChange={(e) => setSelectedKey(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink focus:outline-none focus:border-primary/50"
        >
          {KEY_OPTIONS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
      </div>
      <label className="block text-sm font-medium text-ink-light mb-2">Click chords to build progression</label>
      <div className="flex gap-1.5 flex-wrap mb-3">
        {CHORD_PALETTE.map((c) => (
          <button
            key={c}
            onClick={() => setChords([...chords, c])}
            className="px-3 py-1.5 rounded border border-border bg-surface text-sm font-serif text-ink hover:bg-paper-dark transition-colors"
          >
            {c}
          </button>
        ))}
      </div>
      {chords.length > 0 && (
        <div className="p-3 rounded-lg border border-border bg-surface-warm mb-3">
          <div className="flex gap-1 flex-wrap items-center">
            {chords.map((c, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-1 rounded bg-primary/10 text-primary-dark text-sm font-serif">
                {c}
                <button onClick={() => setChords(chords.filter((_, j) => j !== i))} className="text-ink-muted hover:text-structural text-xs ml-0.5">&times;</button>
              </span>
            ))}
            <button onClick={() => setChords([])} className="text-xs text-ink-muted hover:text-ink ml-2">Clear</button>
          </div>
        </div>
      )}
    </div>
  );
}

function FiguredBassInput({ musicxml, setMusicxml, figures, setFigures }: {
  musicxml: string;
  setMusicxml: (v: string) => void;
  figures: string;
  setFigures: (v: string) => void;
}) {
  return (
    <div>
      <div className="mb-4">
        <label className="block text-sm font-medium text-ink-light mb-1">Bass Line MusicXML</label>
        <textarea
          value={musicxml}
          onChange={(e) => setMusicxml(e.target.value)}
          placeholder="Paste bass line MusicXML..."
          className="w-full h-32 px-3 py-2 rounded-lg border border-border bg-surface font-mono text-xs text-ink placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 resize-y"
        />
      </div>
      <div className="mb-4">
        <label className="block text-sm font-medium text-ink-light mb-1">
          Figured Bass Symbols <span className="text-ink-muted font-normal">(comma-separated, e.g. "6,6/4,7,,6")</span>
        </label>
        <input
          type="text"
          value={figures}
          onChange={(e) => setFigures(e.target.value)}
          placeholder="6, 6/4, 7, , 6"
          className="w-full px-3 py-2 rounded-lg border border-border bg-surface font-mono text-sm text-ink placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20"
        />
      </div>
    </div>
  );
}

export function CompositionWorkshop() {
  const [mode, setMode] = useState<CompositionMode>('harmonize');
  const [musicxml, setMusicxml] = useState('');
  const [result, setResult] = useState<ComposeResponse | null>(null);
  const [melodyChords, setMelodyChords] = useState<string[]>([]);
  const [melodyKey, setMelodyKey] = useState('C major');
  const [figures, setFigures] = useState('');
  const player = useAudioPlayer();

  const harmonizeMut = useMutation({
    mutationFn: (xml: string) => composeChorale(xml),
    onSuccess: (data) => setResult(data),
  });

  const figuredBassMut = useMutation({
    mutationFn: ({ xml, figs }: { xml: string; figs?: string[] }) => composeFiguredBass(xml, figs),
    onSuccess: (data) => setResult(data),
  });

  const melodyMut = useMutation({
    mutationFn: ({ chords, key }: { chords: string[]; key: string }) => composeMelody(chords, key),
    onSuccess: (data) => setResult(data),
  });

  const inventionMut = useMutation({
    mutationFn: (xml: string) => composeInvention(xml),
    onSuccess: (data) => setResult(data),
  });

  const isPending = harmonizeMut.isPending || figuredBassMut.isPending || melodyMut.isPending || inventionMut.isPending;
  const mutError = harmonizeMut.error || figuredBassMut.error || melodyMut.error || inventionMut.error;

  const handleCompose = () => {
    setResult(null);
    player.stop();

    switch (mode) {
      case 'harmonize': {
        const xml = musicxml.trim() || EXAMPLE_MUSICXML;
        harmonizeMut.mutate(xml);
        break;
      }
      case 'figured-bass': {
        const xml = musicxml.trim() || EXAMPLE_MUSICXML;
        const figs = figures.trim() ? figures.split(',').map((f) => f.trim()) : undefined;
        figuredBassMut.mutate({ xml, figs });
        break;
      }
      case 'melody': {
        if (melodyChords.length === 0) return;
        melodyMut.mutate({ chords: melodyChords, key: melodyKey });
        break;
      }
      case 'invention': {
        const xml = musicxml.trim() || EXAMPLE_MUSICXML;
        inventionMut.mutate(xml);
        break;
      }
    }
  };

  const info = MODE_INFO[mode];

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-serif font-bold text-ink mb-2">Composition Workshop</h1>
        <p className="text-ink-light">
          Create music with BachBot's four composition engines. All outputs include full analytical reports.
        </p>
      </div>

      {/* Mode selector */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {(Object.keys(MODE_INFO) as CompositionMode[]).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); setResult(null); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === m
                ? 'bg-primary-dark text-white'
                : 'bg-surface border border-border text-ink-light hover:text-ink hover:border-primary/30'
            }`}
          >
            {MODE_INFO[m].title}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Input panel */}
        <div>
          <h2 className="text-xl font-serif font-semibold mb-2">{info.title}</h2>
          <p className="text-sm text-ink-light mb-4">{info.description}</p>

          {mode === 'melody' ? (
            <MelodyInput chords={melodyChords} setChords={setMelodyChords} selectedKey={melodyKey} setSelectedKey={setMelodyKey} />
          ) : mode === 'figured-bass' ? (
            <FiguredBassInput musicxml={musicxml} setMusicxml={setMusicxml} figures={figures} setFigures={setFigures} />
          ) : (
            <div className="mb-4">
              <label className="block text-sm font-medium text-ink-light mb-1">{info.inputLabel}</label>
              <textarea
                value={musicxml}
                onChange={(e) => setMusicxml(e.target.value)}
                placeholder="Paste MusicXML here, or leave empty to use the example melody..."
                className="w-full h-48 px-3 py-2 rounded-lg border border-border bg-surface font-mono text-xs text-ink placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 resize-y"
              />
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleCompose}
              disabled={isPending || (mode === 'melody' && melodyChords.length === 0)}
              className="px-6 py-2.5 bg-primary-dark text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
            >
              {isPending ? 'Composing...' : 'Compose'}
            </button>
            {mode !== 'melody' && (
              <button
                onClick={() => setMusicxml(EXAMPLE_MUSICXML)}
                className="px-4 py-2.5 bg-surface border border-border rounded-lg text-sm text-ink-light hover:text-ink transition-colors"
              >
                Load Example
              </button>
            )}
            {mode === 'melody' && melodyChords.length === 0 && (
              <button
                onClick={() => setMelodyChords(['I', 'IV', 'V', 'I', 'ii', 'V', 'I'])}
                className="px-4 py-2.5 bg-surface border border-border rounded-lg text-sm text-ink-light hover:text-ink transition-colors"
              >
                Load Example
              </button>
            )}
          </div>

          {mutError && (
            <div className="mt-4 p-3 bg-structural/10 border border-structural/20 rounded-lg text-sm text-structural">
              {String(mutError)}
            </div>
          )}
        </div>

        {/* Output panel */}
        <div>
          {result ? (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xl font-serif font-semibold">Result</h2>
                <span className="text-xs font-mono text-ink-muted">{result.elapsed_ms.toFixed(0)}ms</span>
              </div>

              {/* Labels */}
              <div className="flex gap-2 mb-4 flex-wrap">
                {result.artifact.labels_for_display.map((label, i) => (
                  <span key={i} className="px-2 py-0.5 rounded text-xs font-medium bg-suspension/10 text-suspension">{label}</span>
                ))}
              </div>

              {/* Score + playback */}
              <div className="overflow-x-auto mb-4">
                <PianoRoll graph={result.event_graph} width={600} height={300} playbackBeat={player.currentBeat} />
                <div className="mt-2">
                  <PlaybackControls
                    state={player.state}
                    currentBeat={player.currentBeat}
                    duration={player.duration}
                    tempo={player.tempo}
                    voiceVolumes={player.voiceVolumes}
                    onPlay={() => player.play(result.event_graph)}
                    onPause={player.pause}
                    onStop={player.stop}
                    onTempoChange={player.setTempo}
                    onVoiceVolumeChange={player.setVoiceVolume}
                    compact
                  />
                </div>
                {result.report.plan?.chord_labels && (
                  <div className="mt-2 p-3 rounded-lg bg-paper-dark/30 border border-border">
                    <span className="text-xs font-medium text-ink-muted block mb-1">Chord Plan</span>
                    <div className="flex gap-1 flex-wrap font-serif text-sm text-ink">
                      {result.report.plan.chord_labels.map((label, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-surface rounded">{label}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Export buttons */}
              <div className="mb-4">
                <ExportButtons eventGraph={result.event_graph} />
              </div>

              {/* Trace */}
              {result.report.trace && result.report.trace.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-ink-light mb-2">Generation Trace</h3>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {result.report.trace.map((step, i) => (
                      <div key={i} className="text-xs text-ink-muted flex items-start gap-2">
                        <span className="font-mono text-ink-muted/60 w-4 text-right flex-shrink-0">{i + 1}</span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-ink-muted text-sm py-16">
              <div className="text-center">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mx-auto mb-3 opacity-30">
                  <path d="M9 18V5l12-2v13" />
                  <circle cx="6" cy="18" r="3" />
                  <circle cx="18" cy="16" r="3" />
                </svg>
                <p>Compose something to see the result here</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
