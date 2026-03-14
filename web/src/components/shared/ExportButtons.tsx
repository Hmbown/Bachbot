import type { EventGraph } from '@/types';

interface ExportButtonsProps {
  choraleId?: string;
  eventGraph?: EventGraph;
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12h10" />
    </svg>
  );
}

async function downloadBlob(url: string, filename: string, init?: RequestInit) {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

function downloadCorpus(choraleId: string, format: string) {
  const ext = format === 'musicxml' ? 'musicxml' : format === 'lilypond' ? 'ly' : 'mid';
  downloadBlob(`/api/corpus/${encodeURIComponent(choraleId)}/${format}`, `${choraleId}.${ext}`);
}

function downloadExport(eventGraph: EventGraph, format: string) {
  const ext = format === 'musicxml' ? 'musicxml' : format === 'lilypond' ? 'ly' : 'mid';
  downloadBlob(`/api/export/${format}`, `bachbot_export.${ext}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_graph: eventGraph }),
  });
}

const FORMATS = [
  { key: 'midi', label: 'MIDI' },
  { key: 'musicxml', label: 'MusicXML' },
  { key: 'lilypond', label: 'LilyPond' },
];

export function ExportButtons({ choraleId, eventGraph }: ExportButtonsProps) {
  const handleDownload = (format: string) => {
    if (choraleId) {
      downloadCorpus(choraleId, format);
    } else if (eventGraph) {
      downloadExport(eventGraph, format);
    }
  };

  return (
    <div className="flex gap-2 flex-wrap">
      {FORMATS.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => handleDownload(key)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface border border-border text-ink-light hover:text-ink hover:border-primary/30 transition-colors"
        >
          <DownloadIcon />
          {label}
        </button>
      ))}
    </div>
  );
}
