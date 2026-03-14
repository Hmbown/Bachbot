import type {
  CorpusSearchResponse,
  CorpusDetailResponse,
  HealthResponse,
  AnalyzeResponse,
  ComposeResponse,
  EvaluateResponse,
  CorpusSummary,
} from '@/types';

const BASE = '/api';

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ─── Health ─────────────────────────────────────────────────────────

export function fetchHealth(): Promise<HealthResponse> {
  return fetchJSON('/health');
}

// ─── Corpus ─────────────────────────────────────────────────────────

export interface CorpusSearchParams {
  key?: string;
  cadence_type?: string;
  title_contains?: string;
  limit?: number;
}

export function searchCorpus(params: CorpusSearchParams = {}): Promise<CorpusSearchResponse> {
  const searchParams = new URLSearchParams();
  if (params.key) searchParams.set('key', params.key);
  if (params.cadence_type) searchParams.set('cadence_type', params.cadence_type);
  if (params.title_contains) searchParams.set('title_contains', params.title_contains);
  if (params.limit) searchParams.set('limit', String(params.limit));
  const qs = searchParams.toString();
  return fetchJSON(`/corpus/search${qs ? `?${qs}` : ''}`);
}

export function fetchCorpusList(): Promise<CorpusSearchResponse> {
  return searchCorpus({ limit: 500 });
}

export function fetchChoraleDetail(choraleId: string): Promise<CorpusDetailResponse> {
  return fetchJSON(`/corpus/${encodeURIComponent(choraleId)}`);
}

// ─── Analysis ───────────────────────────────────────────────────────

export function analyzeMusic(musicxml: string, workId?: string): Promise<AnalyzeResponse> {
  return fetchJSON('/analyze', {
    method: 'POST',
    body: JSON.stringify({ musicxml, work_id: workId }),
  });
}

// ─── Composition ────────────────────────────────────────────────────

export function composeChorale(
  musicxml: string,
  evidenceBundle?: Record<string, unknown>,
): Promise<ComposeResponse> {
  return fetchJSON('/compose', {
    method: 'POST',
    body: JSON.stringify({ musicxml, evidence_bundle: evidenceBundle }),
  });
}

// ─── Evaluation ─────────────────────────────────────────────────────

export function evaluateMusic(musicxml: string): Promise<EvaluateResponse> {
  return fetchJSON('/evaluate', {
    method: 'POST',
    body: JSON.stringify({ musicxml }),
  });
}

// ─── Composition modes ──────────────────────────────────────────────

export function composeFiguredBass(musicxml: string, figures?: string[]): Promise<ComposeResponse> {
  return fetchJSON('/compose/figured-bass', {
    method: 'POST',
    body: JSON.stringify({ musicxml, figures }),
  });
}

export function composeMelody(chords: string[], key: string = 'C major'): Promise<ComposeResponse> {
  return fetchJSON('/compose/melody', {
    method: 'POST',
    body: JSON.stringify({ chords, key }),
  });
}

export function composeInvention(musicxml: string): Promise<ComposeResponse> {
  return fetchJSON('/compose/invention', {
    method: 'POST',
    body: JSON.stringify({ musicxml }),
  });
}

// ─── Counterpoint ───────────────────────────────────────────────────

export interface CounterpointValidation {
  species: number;
  violations: { rule: string; measure: number; beat: number; message: string }[];
  is_valid: boolean;
  score: number;
}

export function validateCounterpoint(
  cantus_firmus: number[], counterpoint: number[], species: number, position: string = 'above',
): Promise<CounterpointValidation> {
  return fetchJSON('/counterpoint/validate', {
    method: 'POST',
    body: JSON.stringify({ cantus_firmus, counterpoint, species, position }),
  });
}

export function solveCounterpoint(
  cantus_firmus: number[], species: number, position: string = 'above',
): Promise<{ solution: number[]; steps: string[] }> {
  return fetchJSON('/counterpoint/solve', {
    method: 'POST',
    body: JSON.stringify({ cantus_firmus, species, position }),
  });
}

// ─── Research ───────────────────────────────────────────────────────

export interface StyleFingerprint {
  work_id: string;
  feature_count: number;
  features: Record<string, number>;
}

export function fetchFingerprint(choraleId: string): Promise<StyleFingerprint> {
  return fetchJSON(`/research/fingerprint/${encodeURIComponent(choraleId)}`);
}

export function fetchFingerprintCompare(ids: string[]): Promise<Record<string, StyleFingerprint>> {
  return fetchJSON(`/research/fingerprint/compare?ids=${ids.join(',')}`);
}

export function fetchCorpusBaseline(): Promise<{ mean: Record<string, number>; std: Record<string, number>; count: number }> {
  return fetchJSON('/research/corpus-baseline');
}

export function fetchAnomalies(): Promise<{ anomalies: { work_id: string; anomaly_score: number; outlier_features: { name: string; left_value: number; right_value: number; difference: number }[]; nearest_neighbors: [string, number][] }[] }> {
  return fetchJSON('/research/anomalies');
}

export function fetchPatterns(length: number = 3): Promise<{ length: number; patterns: { progression: string[]; count: number }[] }> {
  return fetchJSON(`/research/patterns?length=${length}`);
}

export function searchPatterns(progression: string): Promise<{ progression: string[]; matches: { chorale_id: string; title: string; onset_index: number }[] }> {
  return fetchJSON(`/research/patterns/search?progression=${encodeURIComponent(progression)}`);
}

export function fetchEmbeddings(): Promise<Record<string, unknown>> {
  return fetchJSON('/research/embeddings');
}

export function fetchHarmonicRhythm(choraleId: string): Promise<Record<string, unknown>> {
  return fetchJSON(`/research/harmonic-rhythm/${encodeURIComponent(choraleId)}`);
}

// ─── Benchmark ──────────────────────────────────────────────────────

export function fetchBenchmarkHistory(): Promise<{ snapshots: Record<string, unknown>[] }> {
  return fetchJSON('/benchmark/history');
}

export function fetchBenchmarkLatest(): Promise<{ snapshot: Record<string, unknown> | null }> {
  return fetchJSON('/benchmark/latest');
}

export function runBenchmark(sampleSize: number = 10): Promise<Record<string, unknown>> {
  return fetchJSON(`/benchmark/run?sample_size=${sampleSize}`, { method: 'POST' });
}

// ─── Evaluation ─────────────────────────────────────────────────────

export function startEvaluation(evaluatorId: string, pairCount: number = 10): Promise<Record<string, unknown>> {
  return fetchJSON('/evaluation/start', {
    method: 'POST',
    body: JSON.stringify({ evaluator_id: evaluatorId, pair_count: pairCount }),
  });
}

export function submitRating(rating: Record<string, unknown>): Promise<Record<string, unknown>> {
  return fetchJSON('/evaluation/rate', { method: 'POST', body: JSON.stringify(rating) });
}

export function fetchEvalResults(): Promise<Record<string, unknown>> {
  return fetchJSON('/evaluation/results');
}

// ─── Encyclopedia ───────────────────────────────────────────────────

export function fetchEncyclopediaStats(): Promise<Record<string, unknown>> {
  return fetchJSON('/encyclopedia/stats');
}

// ─── Corpus Stats (computed client-side from search results) ────────

export interface CorpusStats {
  totalChorales: number;
  keys: { key: string; count: number }[];
  cadenceTypes: { type: string; count: number }[];
  avgHarmonicEvents: number;
  avgCadences: number;
}

export function computeCorpusStats(summaries: CorpusSummary[]): CorpusStats {
  const keyMap = new Map<string, number>();
  const cadenceMap = new Map<string, number>();
  let totalHarmonic = 0;
  let totalCadences = 0;

  for (const s of summaries) {
    if (s.key) keyMap.set(s.key, (keyMap.get(s.key) || 0) + 1);
    for (const ct of s.cadence_types) {
      cadenceMap.set(ct, (cadenceMap.get(ct) || 0) + 1);
    }
    totalHarmonic += s.harmonic_event_count;
    totalCadences += s.cadence_count;
  }

  return {
    totalChorales: summaries.length,
    keys: [...keyMap.entries()]
      .map(([key, count]) => ({ key, count }))
      .sort((a, b) => b.count - a.count),
    cadenceTypes: [...cadenceMap.entries()]
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count),
    avgHarmonicEvents: summaries.length ? Math.round(totalHarmonic / summaries.length) : 0,
    avgCadences: summaries.length ? +(totalCadences / summaries.length).toFixed(1) : 0,
  };
}
