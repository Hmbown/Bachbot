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
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md text-xs font-medium bg-paper-light border border-secondary/55 text-ink hover:bg-secondary/8 hover:border-secondary transition-colors shadow-[0_8px_20px_rgba(43,43,43,0.04)]"
        >
          <DownloadIcon />
          {label}
        </button>
      ))}
    </div>
  );
}
