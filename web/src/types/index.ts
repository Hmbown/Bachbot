// ─── Core Domain Types ───────────────────────────────────────────────

export interface TypedNote {
  pitch: string;
  midi: number;
  duration_quarters: number;
  offset_quarters: number;
  measure_number: number;
  beat: number;
  voice_id: string;
  is_rest: boolean;
  accidental?: string;
  octave?: number;
  step?: string;
  tied_to_next?: boolean;
  tied_from_prev?: boolean;
}

export interface Voice {
  voice_id: string;
  normalized_voice_name: string;
}

export interface EncodingMetadata {
  encoding_id: string;
  work_id: string;
  source_format: string;
  meter?: string;
  key_estimate?: string;
}

export interface Section {
  section_id: string;
  work_id: string;
  section_type?: string;
  measure_start?: number;
  measure_end?: number;
}

export interface EventGraph {
  metadata: EncodingMetadata;
  section: Section;
  voices: Voice[];
  notes: TypedNote[];
}

// ─── Analysis Types ─────────────────────────────────────────────────

export interface HarmonicEvent {
  ref_id: string;
  onset: number;
  duration: number;
  roman_numeral_candidate_set: string[];
  local_key?: string;
  nonharmonic_tone_tags?: string[];
}

export interface Cadence {
  ref_id: string;
  onset: number;
  cadence_type: string;
  strength: number;
}

export interface AnalyticalClaim {
  claim_id: string;
  claim_type: string;
  description: string;
  evidence_status: 'SUPPORTED_FACT' | 'INFERENCE' | 'SPECULATION' | 'DISPUTED';
  passage_ref?: Record<string, unknown>;
  supporting_data?: Record<string, unknown>;
}

export interface AnalysisReport {
  work_id?: string;
  encoding_id?: string;
  key?: string;
  harmony: HarmonicEvent[];
  cadences: Cadence[];
  voice_leading: Record<string, unknown>;
  phrase_endings: Record<string, unknown>[];
  fugue: Record<string, unknown>;
  distributions: Record<string, unknown>;
  anomalies: Record<string, unknown>;
  validation_report: Record<string, unknown>;
  modulation_graph: Record<string, unknown>;
  harmonic_rhythm: Record<string, unknown>;
  schenkerian: Record<string, unknown>;
  text_music: Record<string, unknown>;
  claims: AnalyticalClaim[];
}

export interface EvidenceBundle {
  bundle_id: string;
  work_id: string;
  section_id: string;
  passage_refs: Record<string, unknown>[];
  metadata: {
    genre: string;
    catalog_revision: string;
    key?: string;
    key_tonic?: string;
    key_mode?: string;
    encoding_id?: string;
  };
  deterministic_findings: {
    cadences: Cadence[];
    voice_leading: Record<string, unknown>;
    harmony: HarmonicEvent[];
    phrase_endings: Record<string, unknown>[];
    distributions: Record<string, unknown>;
    modulation_graph: Record<string, unknown>;
    harmonic_rhythm: Record<string, unknown>;
    schenkerian: Record<string, unknown>;
    text_music: Record<string, unknown>;
    claims: AnalyticalClaim[];
    [key: string]: unknown;
  };
  uncertainties: string[];
  provenance: Record<string, unknown>[];
}

// ─── API Response Types ─────────────────────────────────────────────

export interface CorpusSummary {
  chorale_id: string;
  title: string;
  encoding_id: string;
  work_id: string;
  key: string | null;
  cadence_count: number;
  cadence_types: string[];
  harmonic_event_count: number;
}

export interface CorpusSearchResponse {
  dataset_id: string;
  count: number;
  results: CorpusSummary[];
}

export interface CorpusDetailResponse {
  dataset_id: string;
  chorale_id: string;
  title: string;
  event_graph: EventGraph;
  analysis_report: AnalysisReport;
  evidence_bundle: EvidenceBundle;
}

export interface HealthResponse {
  status: string;
  version: string;
  workspace_root: string;
  dataset_id: string;
}

export interface AnalyzeResponse {
  event_graph: EventGraph;
  analysis_report: AnalysisReport;
  evidence_bundle: EvidenceBundle;
  elapsed_ms: number;
}

export interface ComposeResponse {
  event_graph: EventGraph;
  artifact: CompositionArtifact;
  report: {
    plan: { key: string; chord_labels: string[] };
    validation: Record<string, unknown>;
    trace: string[];
  };
  elapsed_ms: number;
}

export interface CompositionArtifact {
  artifact_id: string;
  artifact_class: string;
  generation_trace: Record<string, unknown>;
  validation_refs: Record<string, unknown>[];
  labels_for_display: string[];
}

export interface EvaluateResponse {
  analysis_report: AnalysisReport;
  validation_report: Record<string, unknown>;
  metrics: {
    harmonic_event_count: number;
    cadence_count: number;
    parallel_5ths: number;
    parallel_8ves: number;
    range_issue_count: number;
    spacing_issue_count: number;
    error_count: number;
    warning_count: number;
    passed_validation: boolean;
  };
  elapsed_ms: number;
}

// ─── Voice Helpers ──────────────────────────────────────────────────

export type VoiceRole = 'S' | 'A' | 'T' | 'B';

export const VOICE_COLORS: Record<string, string> = {
  S: '#4477AA',
  A: '#44AA77',
  T: '#DDAA33',
  B: '#CC4444',
};

export const VOICE_NAMES: Record<string, string> = {
  S: 'Soprano',
  A: 'Alto',
  T: 'Tenor',
  B: 'Bass',
};

export function normalizeVoiceId(voiceId: string): VoiceRole {
  const upper = voiceId.toUpperCase();
  if (upper.startsWith('S') || upper === 'SOPRANO') return 'S';
  if (upper.startsWith('A') || upper === 'ALTO') return 'A';
  if (upper.startsWith('T') || upper === 'TENOR') return 'T';
  if (upper.startsWith('B') || upper === 'BASS') return 'B';
  return 'S';
}
