import { useState, useMemo, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { validateCounterpoint, solveCounterpoint } from '@/lib/api';
import type { CounterpointValidation } from '@/lib/api';

// ─── Species Metadata ───────────────────────────────────────────────

type Species = 1 | 2 | 3 | 4 | 5;

const SPECIES_INFO: Record<Species, { title: string; description: string; subdivisions: number; rules: string[] }> = {
  1: {
    title: 'First Species',
    description: 'Note against note. Each counterpoint note aligns with one cantus firmus note.',
    subdivisions: 1,
    rules: [
      'All intervals on downbeats must be consonant (unison, 3rd, 5th, 6th, octave)',
      'No parallel fifths or octaves between consecutive intervals',
      'Contrary motion preferred; avoid similar motion to perfect intervals',
      'Begin and end on perfect consonances',
    ],
  },
  2: {
    title: 'Second Species',
    description: 'Two notes against one. Introduces passing tones on weak beats.',
    subdivisions: 2,
    rules: [
      'Strong beats must be consonant',
      'Weak beats may be dissonant if approached and left by step (passing tone)',
      'No parallel fifths or octaves on consecutive strong beats',
      'Prefer stepwise motion; leaps should be balanced by contrary step motion',
    ],
  },
  3: {
    title: 'Third Species',
    description: 'Four notes against one. Greater melodic freedom with neighbor and passing tones.',
    subdivisions: 4,
    rules: [
      'First note of each measure must be consonant',
      'Dissonances on weak beats must be passing or neighbor tones',
      'Cambiata (nota cambiata) pattern permitted',
      'Avoid more than two consecutive leaps in the same direction',
    ],
  },
  4: {
    title: 'Fourth Species',
    description: 'Syncopation and suspensions. Tied notes create prepared dissonances.',
    subdivisions: 1,
    rules: [
      'Suspensions must be prepared (consonance), sustained (creating dissonance), and resolved (step down)',
      '7-6 and 4-3 suspensions above the bass; 2-3 below the bass',
      'If the tied note is consonant, it need not resolve by step',
      'Breaking species (reverting to first species) is permitted when suspensions are impossible',
    ],
  },
  5: {
    title: 'Fifth Species (Florid)',
    description: 'Free counterpoint combining all previous species. The most creative and challenging.',
    subdivisions: 4,
    rules: [
      'Freely combine elements of species 1-4',
      'Maintain rhythmic variety — avoid staying in one species too long',
      'All dissonance treatment rules from previous species apply',
      'The line should have a clear climax and overall melodic shape',
    ],
  },
};

// ─── Cantus Firmi ───────────────────────────────────────────────────

interface CantusFirmus {
  name: string;
  notes: number[];
}

const CANTUS_FIRMI: CantusFirmus[] = [
  { name: 'Fux #1',      notes: [60, 62, 65, 64, 65, 67, 69, 67, 64, 62, 60] },
  { name: 'Fux #2',      notes: [60, 64, 65, 67, 64, 69, 67, 64, 65, 64, 62, 60] },
  { name: 'Jeppesen #1', notes: [62, 65, 64, 62, 67, 65, 69, 67, 65, 64, 62] },
  { name: 'Schenker #1', notes: [60, 62, 64, 65, 64, 62, 64, 60, 59, 60] },
];

// ─── MIDI / Pitch Helpers ───────────────────────────────────────────

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

function midiToName(midi: number): string {
  return `${NOTE_NAMES[midi % 12]}${Math.floor(midi / 12) - 1}`;
}

function isWhiteKey(midi: number): boolean {
  const pc = midi % 12;
  return [0, 2, 4, 5, 7, 9, 11].includes(pc);
}

const MIDI_MIN = 48; // C3
const MIDI_MAX = 84; // C6
const ALL_MIDI: number[] = [];
for (let m = MIDI_MAX; m >= MIDI_MIN; m--) {
  ALL_MIDI.push(m); // top-to-bottom for SVG rendering
}

// ─── Validation Status for Notes ────────────────────────────────────

type NoteStatus = 'valid' | 'violation' | 'warning' | 'neutral';

function getNoteStatus(
  cfIndex: number,
  subIndex: number,
  validation: CounterpointValidation | null,
): NoteStatus {
  if (!validation) return 'neutral';
  if (validation.is_valid) return 'valid';
  // Map violations to cells
  for (const v of validation.violations) {
    if (v.measure === cfIndex + 1) {
      // Beat-based matching: beat 1 = sub 0, beat 1.5 = sub 1, etc.
      // Simplified: any violation in this measure applies to all notes in it
      if (v.beat <= 0 || Math.floor(v.beat) === subIndex + 1 || subIndex === 0) {
        if (v.rule.toLowerCase().includes('warning')) return 'warning';
        return 'violation';
      }
    }
  }
  return 'valid';
}

function getStatusColor(status: NoteStatus): string {
  switch (status) {
    case 'valid': return 'var(--color-fact)';         // green
    case 'violation': return 'var(--color-structural)'; // red
    case 'warning': return 'var(--color-suspension)';   // yellow
    case 'neutral': return 'var(--color-primary)';      // blue
  }
}

function getStatusBgColor(status: NoteStatus): string {
  switch (status) {
    case 'valid': return 'rgba(45, 125, 70, 0.85)';
    case 'violation': return 'rgba(204, 68, 68, 0.85)';
    case 'warning': return 'rgba(221, 170, 51, 0.85)';
    case 'neutral': return 'rgba(44, 82, 130, 0.75)';
  }
}

// ─── Component ──────────────────────────────────────────────────────

type Position = 'above' | 'below';

export function TheoryClassroom() {
  const [species, setSpecies] = useState<Species>(1);
  const [selectedCF, setSelectedCF] = useState(0);
  const [position, setPosition] = useState<Position>('above');
  // Counterpoint grid: cfIndex -> subIndex -> MIDI pitch (or 0 for empty)
  const [grid, setGrid] = useState<Map<string, number>>(new Map());
  const [validation, setValidation] = useState<CounterpointValidation | null>(null);
  const [solveSteps, setSolveSteps] = useState<string[]>([]);

  const cf = CANTUS_FIRMI[selectedCF];
  const info = SPECIES_INFO[species];
  const subdivisions = info.subdivisions;

  // Flatten grid to counterpoint array for API calls.
  // For species 1/4: one note per CF note. For 2: two notes. For 3/5: four notes.
  const flattenGrid = useCallback((): number[] => {
    const result: number[] = [];
    for (let c = 0; c < cf.notes.length; c++) {
      for (let s = 0; s < subdivisions; s++) {
        result.push(grid.get(`${c}-${s}`) ?? 0);
      }
    }
    return result;
  }, [grid, cf.notes.length, subdivisions]);

  // Reset grid when CF or species changes
  const resetGrid = useCallback(() => {
    setGrid(new Map());
    setValidation(null);
    setSolveSteps([]);
  }, []);

  // Toggle note in grid
  const toggleNote = useCallback((cfIndex: number, subIndex: number, midi: number) => {
    setGrid(prev => {
      const next = new Map(prev);
      const key = `${cfIndex}-${subIndex}`;
      if (next.get(key) === midi) {
        next.delete(key);
      } else {
        next.set(key, midi);
      }
      return next;
    });
    // Clear stale validation on any change
    setValidation(null);
  }, []);

  // Validation mutation
  const validateMutation = useMutation({
    mutationFn: () => {
      const cp = flattenGrid();
      return validateCounterpoint(cf.notes, cp, species, position);
    },
    onSuccess: (data) => setValidation(data),
  });

  // Solve mutation
  const solveMutation = useMutation({
    mutationFn: () => solveCounterpoint(cf.notes, species, position),
    onSuccess: (data) => {
      // Place solution into grid
      const next = new Map<string, number>();
      let idx = 0;
      for (let c = 0; c < cf.notes.length; c++) {
        for (let s = 0; s < subdivisions; s++) {
          if (idx < data.solution.length && data.solution[idx] > 0) {
            next.set(`${c}-${s}`, data.solution[idx]);
          }
          idx++;
        }
      }
      setGrid(next);
      setSolveSteps(data.steps || []);
      setValidation(null);
    },
  });

  const hasAnyNotes = grid.size > 0;

  // ─── SVG Grid Layout ──────────────────────────────────────────────

  const CELL_W = 40;
  const SUB_CELL_W = CELL_W / subdivisions;
  const CELL_H = 12;
  const LABEL_W = 48;
  const HEADER_H = 32;
  const CF_ROW_H = 28;
  const PADDING = 16;

  // Only show diatonic (white keys) by default for a cleaner grid.
  // Full chromatic range available but we filter to keep it manageable.
  const visibleMidi = useMemo(() => ALL_MIDI.filter(isWhiteKey), []);
  const gridWidth = cf.notes.length * CELL_W;
  const gridHeight = visibleMidi.length * CELL_H;
  const svgWidth = LABEL_W + gridWidth + PADDING;
  const svgHeight = HEADER_H + CF_ROW_H + gridHeight + PADDING + 4;

  // Find CF pitches in the visible range for highlighting
  const cfMidiSet = useMemo(() => new Set(cf.notes), [cf.notes]);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-3xl font-serif font-bold text-ink mb-2">Theory Classroom</h1>
        <p className="text-ink-light">
          Interactive species counterpoint exercises with real-time validation, built on
          BachBot's 12 built-in cantus firmi and 5-species validator.
        </p>
      </div>

      {/* Species selector */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {([1, 2, 3, 4, 5] as Species[]).map((s) => (
          <button
            key={s}
            onClick={() => { setSpecies(s); resetGrid(); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              species === s
                ? 'bg-primary-dark text-white'
                : 'bg-surface border border-border text-ink-light hover:text-ink hover:border-primary/30'
            }`}
          >
            Species {s}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">
        {/* ─── Main exercise area (3 cols) ──────────────────────────── */}
        <div className="xl:col-span-3">
          <h2 className="text-xl font-serif font-semibold mb-1">{info.title}</h2>
          <p className="text-sm text-ink-light mb-4">{info.description}</p>

          {/* Controls row */}
          <div className="flex flex-wrap items-end gap-4 mb-4">
            {/* CF selector */}
            <div>
              <label className="block text-xs font-medium text-ink-muted mb-1.5">Cantus Firmus</label>
              <div className="flex gap-1.5">
                {CANTUS_FIRMI.map((c, i) => (
                  <button
                    key={i}
                    onClick={() => { setSelectedCF(i); resetGrid(); }}
                    className={`px-3 py-1.5 rounded text-sm transition-colors ${
                      selectedCF === i
                        ? 'bg-primary/10 text-primary-dark border border-primary/30 font-medium'
                        : 'bg-surface border border-border text-ink-light hover:text-ink'
                    }`}
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Position toggle */}
            <div>
              <label className="block text-xs font-medium text-ink-muted mb-1.5">Position</label>
              <div className="flex">
                <button
                  onClick={() => { setPosition('above'); resetGrid(); }}
                  className={`px-3 py-1.5 rounded-l text-sm border transition-colors ${
                    position === 'above'
                      ? 'bg-primary/10 text-primary-dark border-primary/30 font-medium'
                      : 'bg-surface border-border text-ink-light hover:text-ink'
                  }`}
                >
                  Above
                </button>
                <button
                  onClick={() => { setPosition('below'); resetGrid(); }}
                  className={`px-3 py-1.5 rounded-r text-sm border border-l-0 transition-colors ${
                    position === 'below'
                      ? 'bg-primary/10 text-primary-dark border-primary/30 font-medium'
                      : 'bg-surface border-border text-ink-light hover:text-ink'
                  }`}
                >
                  Below
                </button>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-2 ml-auto">
              <button
                onClick={() => validateMutation.mutate()}
                disabled={!hasAnyNotes || validateMutation.isPending}
                className="px-4 py-2 bg-primary-dark text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {validateMutation.isPending ? 'Validating...' : 'Validate'}
              </button>
              <button
                onClick={() => solveMutation.mutate()}
                disabled={solveMutation.isPending}
                className="px-4 py-2 bg-surface border border-primary/30 text-primary-dark rounded-lg text-sm font-medium hover:bg-primary/5 transition-colors disabled:opacity-40"
              >
                {solveMutation.isPending ? 'Solving...' : 'Show Solution'}
              </button>
              <button
                onClick={resetGrid}
                className="px-4 py-2 bg-surface border border-border text-ink-light rounded-lg text-sm hover:text-ink transition-colors"
              >
                Clear
              </button>
            </div>
          </div>

          {/* Validation summary */}
          {validation && (
            <div className={`mb-4 p-3 rounded-lg border text-sm flex items-center gap-3 ${
              validation.is_valid
                ? 'bg-fact/5 border-fact/20 text-fact'
                : 'bg-structural/5 border-structural/20 text-structural'
            }`}>
              <span className="font-medium">
                {validation.is_valid ? 'Valid!' : `${validation.violations.length} violation${validation.violations.length !== 1 ? 's' : ''}`}
              </span>
              {validation.score > 0 && (
                <span className="text-xs opacity-70">Score: {validation.score.toFixed(1)}</span>
              )}
            </div>
          )}

          {validateMutation.error && (
            <div className="mb-4 p-3 bg-structural/10 border border-structural/20 rounded-lg text-sm text-structural">
              {String(validateMutation.error)}
            </div>
          )}
          {solveMutation.error && (
            <div className="mb-4 p-3 bg-structural/10 border border-structural/20 rounded-lg text-sm text-structural">
              {String(solveMutation.error)}
            </div>
          )}

          {/* ─── SVG Counterpoint Grid ──────────────────────────────── */}
          <div className="overflow-x-auto rounded-lg border border-border bg-surface">
            <svg
              width={svgWidth}
              height={svgHeight}
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              style={{ fontFamily: 'var(--font-sans)', minWidth: svgWidth }}
            >
              {/* ── Column headers: measure numbers ── */}
              {cf.notes.map((_, c) => (
                <text
                  key={`hdr-${c}`}
                  x={LABEL_W + c * CELL_W + CELL_W / 2}
                  y={18}
                  textAnchor="middle"
                  fontSize={10}
                  fontWeight={500}
                  fill="var(--color-ink-muted)"
                >
                  {c + 1}
                </text>
              ))}

              {/* ── Cantus firmus row ── */}
              <rect
                x={LABEL_W}
                y={HEADER_H}
                width={gridWidth}
                height={CF_ROW_H}
                fill="var(--color-paper-dark)"
              />
              <text
                x={LABEL_W - 6}
                y={HEADER_H + CF_ROW_H / 2 + 4}
                textAnchor="end"
                fontSize={9}
                fontWeight={600}
                fill="var(--color-ink-muted)"
              >
                C.F.
              </text>
              {cf.notes.map((midi, c) => (
                <g key={`cf-${c}`}>
                  {/* CF note cell */}
                  <rect
                    x={LABEL_W + c * CELL_W + 1}
                    y={HEADER_H + 2}
                    width={CELL_W - 2}
                    height={CF_ROW_H - 4}
                    rx={3}
                    fill="var(--color-sepia-dark)"
                    opacity={0.75}
                  />
                  <text
                    x={LABEL_W + c * CELL_W + CELL_W / 2}
                    y={HEADER_H + CF_ROW_H / 2 + 4}
                    textAnchor="middle"
                    fontSize={10}
                    fontWeight={600}
                    fill="white"
                    style={{ fontFamily: 'var(--font-serif)' }}
                  >
                    {midiToName(midi)}
                  </text>
                </g>
              ))}

              {/* ── Separator line ── */}
              <line
                x1={LABEL_W}
                y1={HEADER_H + CF_ROW_H}
                x2={LABEL_W + gridWidth}
                y2={HEADER_H + CF_ROW_H}
                stroke="var(--color-border)"
                strokeWidth={1.5}
              />

              {/* ── Pitch grid ── */}
              <g transform={`translate(0, ${HEADER_H + CF_ROW_H})`}>
                {/* Row backgrounds and labels */}
                {visibleMidi.map((midi, row) => {
                  const isCF = cfMidiSet.has(midi);
                  const isC = midi % 12 === 0;
                  return (
                    <g key={`row-${midi}`}>
                      {/* Row background */}
                      <rect
                        x={LABEL_W}
                        y={row * CELL_H}
                        width={gridWidth}
                        height={CELL_H}
                        fill={isCF
                          ? 'rgba(166, 146, 116, 0.08)'
                          : isC
                            ? 'rgba(44, 82, 130, 0.03)'
                            : row % 2 === 0
                              ? 'transparent'
                              : 'rgba(0,0,0,0.015)'
                        }
                      />
                      {/* Horizontal grid line */}
                      <line
                        x1={LABEL_W}
                        y1={row * CELL_H}
                        x2={LABEL_W + gridWidth}
                        y2={row * CELL_H}
                        stroke={isC ? 'var(--color-border)' : 'var(--color-border-light)'}
                        strokeWidth={isC ? 0.8 : 0.3}
                      />
                      {/* Y-axis pitch label */}
                      <text
                        x={LABEL_W - 4}
                        y={row * CELL_H + CELL_H / 2 + 3}
                        textAnchor="end"
                        fontSize={8}
                        fill={isCF ? 'var(--color-sepia-dark)' : isC ? 'var(--color-ink-light)' : 'var(--color-ink-muted)'}
                        fontWeight={isCF ? 600 : isC ? 500 : 400}
                      >
                        {midiToName(midi)}
                      </text>
                    </g>
                  );
                })}

                {/* Vertical column dividers */}
                {cf.notes.map((_, c) => (
                  <line
                    key={`vl-${c}`}
                    x1={LABEL_W + c * CELL_W}
                    y1={0}
                    x2={LABEL_W + c * CELL_W}
                    y2={gridHeight}
                    stroke="var(--color-border)"
                    strokeWidth={0.5}
                  />
                ))}
                {/* Right edge */}
                <line
                  x1={LABEL_W + gridWidth}
                  y1={0}
                  x2={LABEL_W + gridWidth}
                  y2={gridHeight}
                  stroke="var(--color-border)"
                  strokeWidth={0.5}
                />

                {/* Subdivision dividers for species 2/3/5 */}
                {subdivisions > 1 && cf.notes.map((_, c) => {
                  const subs: React.ReactElement[] = [];
                  for (let s = 1; s < subdivisions; s++) {
                    subs.push(
                      <line
                        key={`sub-${c}-${s}`}
                        x1={LABEL_W + c * CELL_W + s * SUB_CELL_W}
                        y1={0}
                        x2={LABEL_W + c * CELL_W + s * SUB_CELL_W}
                        y2={gridHeight}
                        stroke="var(--color-border-light)"
                        strokeWidth={0.3}
                        strokeDasharray="2,3"
                      />,
                    );
                  }
                  return subs;
                })}

                {/* Clickable cells */}
                {visibleMidi.map((midi, row) =>
                  cf.notes.map((_, c) => {
                    const cells: React.ReactElement[] = [];
                    for (let s = 0; s < subdivisions; s++) {
                      const key = `${c}-${s}`;
                      const isPlaced = grid.get(key) === midi;
                      const status = isPlaced ? getNoteStatus(c, s, validation) : 'neutral';
                      cells.push(
                        <rect
                          key={`cell-${c}-${s}-${midi}`}
                          x={LABEL_W + c * CELL_W + s * SUB_CELL_W + 0.5}
                          y={row * CELL_H + 0.5}
                          width={SUB_CELL_W - 1}
                          height={CELL_H - 1}
                          rx={isPlaced ? 2 : 0}
                          fill={isPlaced ? getStatusBgColor(status) : 'transparent'}
                          stroke={isPlaced ? getStatusColor(status) : 'transparent'}
                          strokeWidth={isPlaced ? 1 : 0}
                          opacity={isPlaced ? 1 : 0}
                          className="cursor-pointer"
                          style={{ transition: 'fill 0.15s, opacity 0.15s' }}
                          onClick={() => toggleNote(c, s, midi)}
                        >
                          <title>
                            {midiToName(midi)} {isPlaced ? '(click to remove)' : '(click to place)'}
                            {'\n'}Measure {c + 1}{subdivisions > 1 ? `, beat ${s + 1}/${subdivisions}` : ''}
                          </title>
                        </rect>,
                      );
                    }
                    return cells;
                  }),
                )}

                {/* Hover overlay: invisible rects for hover state */}
                {visibleMidi.map((midi, row) =>
                  cf.notes.map((_, c) => {
                    const hoverCells: React.ReactElement[] = [];
                    for (let s = 0; s < subdivisions; s++) {
                      const key = `${c}-${s}`;
                      const isPlaced = grid.get(key) === midi;
                      if (!isPlaced) {
                        hoverCells.push(
                          <rect
                            key={`hover-${c}-${s}-${midi}`}
                            x={LABEL_W + c * CELL_W + s * SUB_CELL_W + 0.5}
                            y={row * CELL_H + 0.5}
                            width={SUB_CELL_W - 1}
                            height={CELL_H - 1}
                            rx={1}
                            fill="var(--color-primary)"
                            opacity={0}
                            className="cursor-pointer hover:opacity-15"
                            style={{ transition: 'opacity 0.1s' }}
                            onClick={() => toggleNote(c, s, midi)}
                          >
                            <title>
                              {midiToName(midi)}{'\n'}Measure {c + 1}{subdivisions > 1 ? `, beat ${s + 1}/${subdivisions}` : ''}
                            </title>
                          </rect>,
                        );
                      }
                    }
                    return hoverCells;
                  }),
                )}

                {/* Placed note labels (pitch name inside filled cells) */}
                {Array.from(grid.entries()).map(([key, midi]) => {
                  const [cStr, sStr] = key.split('-');
                  const c = parseInt(cStr, 10);
                  const s = parseInt(sStr, 10);
                  const rowIdx = visibleMidi.indexOf(midi);
                  if (rowIdx < 0) return null; // off-grid (chromatic pitch)
                  void getNoteStatus(c, s, validation);
                  return (
                    <text
                      key={`lbl-${key}`}
                      x={LABEL_W + c * CELL_W + s * SUB_CELL_W + SUB_CELL_W / 2}
                      y={rowIdx * CELL_H + CELL_H / 2 + 3}
                      textAnchor="middle"
                      fontSize={7}
                      fontWeight={600}
                      fill="white"
                      className="pointer-events-none select-none"
                    >
                      {NOTE_NAMES[midi % 12]}
                    </text>
                  );
                })}
              </g>

              {/* Bottom border */}
              <line
                x1={LABEL_W}
                y1={HEADER_H + CF_ROW_H + gridHeight}
                x2={LABEL_W + gridWidth}
                y2={HEADER_H + CF_ROW_H + gridHeight}
                stroke="var(--color-border)"
                strokeWidth={0.5}
              />
            </svg>
          </div>

          {/* Inline violation messages per measure */}
          {validation && validation.violations.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {validation.violations.map((v, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 text-xs"
                >
                  <span className="w-5 h-5 rounded-full bg-structural/10 text-structural flex items-center justify-center flex-shrink-0 text-[10px] font-medium mt-0.5">
                    {v.measure}
                  </span>
                  <span className="text-ink-light">
                    <span className="font-medium text-structural">{v.rule}</span>
                    {' '}&mdash; {v.message}
                    {v.beat > 0 && <span className="text-ink-muted"> (beat {v.beat})</span>}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Solution steps */}
          {solveSteps.length > 0 && (
            <div className="mt-4 p-4 rounded-lg bg-paper-dark/30 border border-border">
              <h4 className="text-xs font-semibold text-ink-muted mb-2">Solution Trace</h4>
              <div className="space-y-0.5 max-h-36 overflow-y-auto">
                {solveSteps.map((step, i) => (
                  <div key={i} className="text-xs text-ink-muted flex items-start gap-2">
                    <span className="font-mono text-ink-muted/50 w-4 text-right flex-shrink-0">{i + 1}</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Legend */}
          <div className="mt-4 flex gap-4 text-xs text-ink-muted">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm" style={{ background: 'rgba(45, 125, 70, 0.85)' }} />
              Valid
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm" style={{ background: 'rgba(204, 68, 68, 0.85)' }} />
              Violation
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm" style={{ background: 'rgba(221, 170, 51, 0.85)' }} />
              Warning
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm" style={{ background: 'rgba(44, 82, 130, 0.75)' }} />
              Unvalidated
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm" style={{ background: 'var(--color-sepia-dark)', opacity: 0.75 }} />
              Cantus Firmus
            </span>
          </div>
        </div>

        {/* ─── Rules panel (1 col) ──────────────────────────────────── */}
        <div>
          <h3 className="text-lg font-serif font-semibold mb-3">Rules</h3>
          <div className="space-y-3">
            {info.rules.map((rule, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className="w-5 h-5 rounded-full bg-primary/10 text-primary-dark flex items-center justify-center flex-shrink-0 text-xs font-medium mt-0.5">
                  {i + 1}
                </span>
                <span className="text-ink-light leading-relaxed">{rule}</span>
              </div>
            ))}
          </div>

          {/* Species rhythm diagram */}
          <div className="mt-6 p-4 rounded-lg bg-paper-dark/30 border border-border">
            <h4 className="text-xs font-semibold text-ink-muted mb-2">Rhythmic Pattern</h4>
            <div className="flex gap-1 items-end">
              {Array.from({ length: 4 }).map((_, i) => {
                const active = i < subdivisions;
                return (
                  <div
                    key={i}
                    className={`rounded transition-all ${active ? 'bg-primary/30' : 'bg-border-light'}`}
                    style={{
                      width: `${100 / 4}%`,
                      height: active ? 24 : 8,
                    }}
                  />
                );
              })}
            </div>
            <p className="text-xs text-ink-muted mt-2">
              {subdivisions === 1 && 'One note per cantus firmus note (whole notes).'}
              {subdivisions === 2 && 'Two notes per cantus firmus note (half notes).'}
              {subdivisions === 4 && 'Four notes per cantus firmus note (quarter notes).'}
            </p>
          </div>

          {/* Position indicator */}
          <div className="mt-4 p-4 rounded-lg bg-surface-warm border border-border">
            <h4 className="text-xs font-semibold text-ink-muted mb-2">Current Setup</h4>
            <div className="space-y-1 text-xs text-ink-light">
              <div>
                <span className="text-ink-muted">CF:</span>{' '}
                <span className="font-medium">{cf.name}</span>{' '}
                <span className="text-ink-muted">({cf.notes.length} notes)</span>
              </div>
              <div>
                <span className="text-ink-muted">Position:</span>{' '}
                <span className="font-medium capitalize">{position}</span>
              </div>
              <div>
                <span className="text-ink-muted">Species:</span>{' '}
                <span className="font-medium">{species}</span>{' '}
                <span className="text-ink-muted">({subdivisions} note{subdivisions > 1 ? 's' : ''} per CF note)</span>
              </div>
              <div>
                <span className="text-ink-muted">Notes placed:</span>{' '}
                <span className="font-medium">{grid.size}</span>
                <span className="text-ink-muted"> / {cf.notes.length * subdivisions}</span>
              </div>
            </div>
          </div>

          {/* Corpus insight */}
          <div className="mt-4 p-4 rounded-lg bg-surface-warm border border-border">
            <h4 className="text-sm font-semibold text-ink-light mb-2">From the Corpus</h4>
            <p className="text-xs text-ink-muted leading-relaxed">
              Bach uses perfect authentic cadences to end 89% of chorale phrases.
              The average chorale modulates 3.6 times, with 75% of modulations using
              common-chord pivots. V/V appears in 73% of chorales.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
