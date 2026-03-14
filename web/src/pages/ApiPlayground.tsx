import { useState, useCallback } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { fetchHealth } from '@/lib/api';
import { BaroqueFlourish, StaffDivider } from '@/components/shared/Decorative';

interface Param {
  name: string;
  type: string;
  description: string;
  required?: boolean;
  default?: string;
}

interface Endpoint {
  method: 'GET' | 'POST';
  path: string;
  description: string;
  params?: Param[];
  body?: string;
  category: string;
}

const ENDPOINTS: Endpoint[] = [
  { method: 'GET', path: '/health', description: 'API status, version, workspace root, and dataset ID.', category: 'System' },
  { method: 'GET', path: '/corpus/search', description: 'Search the corpus by key, cadence type, or title.', category: 'Corpus', params: [
    { name: 'key', type: 'string', description: 'Exact key label, e.g. "G major"' },
    { name: 'cadence_type', type: 'string', description: 'Cadence type filter' },
    { name: 'title_contains', type: 'string', description: 'Title substring' },
    { name: 'limit', type: 'integer', description: 'Results limit (1-500)', default: '10' },
  ]},
  { method: 'GET', path: '/corpus/{chorale_id}', description: 'Full chorale detail: score events, analysis report, and analysis data.', category: 'Corpus', params: [
    { name: 'chorale_id', type: 'string', description: 'BWV number or encoding ID', required: true },
  ]},
  { method: 'GET', path: '/corpus/{chorale_id}/midi', description: 'Download MIDI file for a corpus chorale.', category: 'Export', params: [
    { name: 'chorale_id', type: 'string', description: 'BWV number', required: true },
  ]},
  { method: 'GET', path: '/corpus/{chorale_id}/musicxml', description: 'Download MusicXML for a corpus chorale.', category: 'Export', params: [
    { name: 'chorale_id', type: 'string', description: 'BWV number', required: true },
  ]},
  { method: 'GET', path: '/corpus/{chorale_id}/lilypond', description: 'Download LilyPond source for a corpus chorale.', category: 'Export', params: [
    { name: 'chorale_id', type: 'string', description: 'BWV number', required: true },
  ]},
  { method: 'POST', path: '/analyze', description: 'Submit MusicXML for a full reading of the score.', category: 'Analysis', body: '{\n  "musicxml": "<score-partwise>...</score-partwise>"\n}' },
  { method: 'POST', path: '/compose', description: 'Harmonize a soprano melody into SATB.', category: 'Composition', body: '{\n  "musicxml": "<soprano MusicXML>"\n}' },
  { method: 'POST', path: '/compose/figured-bass', description: 'Realize figured bass into SATB.', category: 'Composition', body: '{\n  "musicxml": "<bass MusicXML>",\n  "figures": ["6", "6/4", "7"]\n}' },
  { method: 'POST', path: '/compose/melody', description: 'Generate soprano from chord progression.', category: 'Composition', body: '{\n  "chords": ["I", "IV", "V", "I"],\n  "key": "C major"\n}' },
  { method: 'POST', path: '/compose/invention', description: 'Generate two-part invention from subject.', category: 'Composition', body: '{\n  "musicxml": "<subject MusicXML>"\n}' },
  { method: 'POST', path: '/evaluate', description: 'Check a submitted score for rule issues and summary counts.', category: 'Analysis', body: '{\n  "musicxml": "<score-partwise>...</score-partwise>"\n}' },
  { method: 'POST', path: '/counterpoint/validate', description: 'Validate student counterpoint against cantus firmus.', category: 'Theory', body: '{\n  "cantus_firmus": [60, 62, 64, 65, 64, 62, 60],\n  "counterpoint": [67, 69, 71, 72, 71, 69, 67],\n  "species": 1,\n  "position": "above"\n}' },
  { method: 'POST', path: '/counterpoint/solve', description: 'Generate counterpoint for a cantus firmus.', category: 'Theory', body: '{\n  "cantus_firmus": [60, 62, 64, 65, 64, 62, 60],\n  "species": 1,\n  "position": "above"\n}' },
  { method: 'GET', path: '/research/fingerprint/{chorale_id}', description: 'Feature profile for a chorale.', category: 'Research', params: [
    { name: 'chorale_id', type: 'string', description: 'BWV number', required: true },
  ]},
  { method: 'GET', path: '/research/corpus-baseline', description: 'Corpus averages and standard deviations for the feature profile.', category: 'Research' },
  { method: 'GET', path: '/research/anomalies', description: 'Chorales ranked by outlier score.', category: 'Research' },
  { method: 'GET', path: '/research/patterns', description: 'Most common harmonic progressions.', category: 'Research', params: [
    { name: 'length', type: 'integer', description: 'N-gram length (2-6)', default: '3' },
  ]},
  { method: 'GET', path: '/research/embeddings', description: 'Coordinates for the chorale map.', category: 'Research' },
  { method: 'GET', path: '/benchmark/latest', description: 'Most recent benchmark snapshot.', category: 'Benchmark' },
  { method: 'GET', path: '/benchmark/history', description: 'All benchmark history snapshots.', category: 'Benchmark' },
  { method: 'GET', path: '/encyclopedia/stats', description: 'Corpus-wide statistics for encyclopedia articles.', category: 'System' },
];

const CATEGORIES = [...new Set(ENDPOINTS.map((e) => e.category))];

interface HistoryEntry {
  method: string;
  path: string;
  status: number;
  time: number;
  timestamp: string;
}

export function ApiPlayground() {
  const [selectedEndpoint, setSelectedEndpoint] = useState(0);
  const [response, setResponse] = useState<string | null>(null);
  const [responseStatus, setResponseStatus] = useState<number | null>(null);
  const [responseTime, setResponseTime] = useState<number | null>(null);
  const [paramValues, setParamValues] = useState<Record<string, string>>({});
  const [bodyValue, setBodyValue] = useState('');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    staleTime: 30000,
  });

  const endpoint = ENDPOINTS[selectedEndpoint];

  const selectEndpoint = useCallback((i: number) => {
    setSelectedEndpoint(i);
    setResponse(null);
    setResponseStatus(null);
    setResponseTime(null);
    setParamValues({});
    setBodyValue(ENDPOINTS[i].body || '');
  }, []);

  const tryMutation = useMutation({
    mutationFn: async (ep: Endpoint) => {
      let path = ep.path;
      // Substitute path params
      for (const p of ep.params || []) {
        if (path.includes(`{${p.name}}`)) {
          path = path.replace(`{${p.name}}`, encodeURIComponent(paramValues[p.name] || 'BWV001'));
        }
      }
      // Build query string for GET params
      if (ep.method === 'GET' && ep.params) {
        const qs = new URLSearchParams();
        for (const p of ep.params) {
          if (!path.includes(p.name) && paramValues[p.name]) {
            qs.set(p.name, paramValues[p.name]);
          }
        }
        const qsStr = qs.toString();
        if (qsStr) path += `?${qsStr}`;
      }

      const url = `/api${path}`;
      const start = performance.now();
      const init: RequestInit = ep.method === 'POST'
        ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: bodyValue || ep.body }
        : {};
      const res = await fetch(url, init);
      const elapsed = Math.round(performance.now() - start);
      const data = await res.json();
      return { data, status: res.status, elapsed, path };
    },
    onSuccess: ({ data, status, elapsed, path }) => {
      setResponse(JSON.stringify(data, null, 2));
      setResponseStatus(status);
      setResponseTime(elapsed);
      setHistory((prev) => [
        { method: endpoint.method, path, status, time: elapsed, timestamp: new Date().toLocaleTimeString() },
        ...prev.slice(0, 9),
      ]);
    },
    onError: (err) => {
      setResponse(`Error: ${err}`);
      setResponseStatus(500);
    },
  });

  const copyToClipboard = (text: string) => navigator.clipboard.writeText(text);

  const curlExample = endpoint.method === 'POST'
    ? `curl -X POST -H "Content-Type: application/json" \\\n  -d '${(bodyValue || endpoint.body || '{}').replace(/\n/g, '')}' \\\n  http://localhost:8000${endpoint.path}`
    : `curl http://localhost:8000${endpoint.path}`;

  const pythonExample = `import httpx\nresponse = httpx.${endpoint.method.toLowerCase()}("http://localhost:8000${endpoint.path}"${
    endpoint.method === 'POST' ? `,\n    json=${(bodyValue || endpoint.body || '{}').replace(/\n/g, '')}` : ''
  })\ndata = response.json()`;

  const tsExample = `const res = await fetch("http://localhost:8000${endpoint.path}"${
    endpoint.method === 'POST' ? `, {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify(${(bodyValue || endpoint.body || '{}').replace(/\n/g, '')})\n}` : ''
  });\nconst data = await res.json();`;

  return (
    <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-8">
      <div className="mb-8">
        <div className="mb-2">
          <span className="inline-block text-secondary text-[11px] uppercase tracking-[0.28em] font-sans">
            Reference & Playground
          </span>
        </div>
        <h1 className="mb-3 text-4xl">API Reference</h1>
        <p className="text-ink-muted">
          Browse the endpoints and try a live request against the running app.
        </p>
        <BaroqueFlourish className="mt-4" />
        <StaffDivider className="pt-2" />
        <div className="mt-2 flex items-center gap-4 text-sm">
          {healthQuery.data && (
            <span className="flex items-center gap-2 text-ink-muted">
              <span className="w-2 h-2 rounded-full bg-fact" />
              API v{healthQuery.data.version} — {healthQuery.data.status}
            </span>
          )}
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="text-primary text-xs hover:text-primary-dark"
          >
            {showHistory ? 'Hide' : 'Show'} recent requests ({history.length})
          </button>
        </div>
      </div>

      {/* Request history */}
      {showHistory && history.length > 0 && (
        <div className="mb-6 p-3 rounded-xl border border-border bg-paper-light shadow-[0_12px_30px_rgba(43,43,43,0.04)]">
          <h3 className="text-xs font-semibold text-ink-light mb-2">Recent requests</h3>
          <div className="space-y-1">
            {history.map((h, i) => (
              <div key={i} className="flex items-center gap-3 text-xs font-mono">
                <span className={h.status < 400 ? 'text-fact' : 'text-structural'}>{h.status}</span>
                <span className="text-ink-muted">{h.method}</span>
                <span className="text-ink-light flex-1 truncate">{h.path}</span>
                <span className="text-ink-muted">{h.time}ms</span>
                <span className="text-ink-muted">{h.timestamp}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Endpoint list by category */}
        <div className="lg:col-span-1">
          {CATEGORIES.map((cat) => (
            <div key={cat} className="mb-4 rounded-xl border border-border bg-paper-light p-2 shadow-[0_12px_30px_rgba(43,43,43,0.04)]">
              <h4 className="text-xs font-semibold text-secondary uppercase tracking-[0.18em] mb-2 px-2">{cat}</h4>
              <div className="space-y-0.5">
                {ENDPOINTS.map((ep, i) => ep.category !== cat ? null : (
                  <button
                    key={i}
                    onClick={() => selectEndpoint(i)}
                    className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
                      selectedEndpoint === i ? 'bg-secondary/12 border border-secondary/30' : 'hover:bg-secondary/8'
                    }`}
                  >
                    <span className={`inline-block w-10 font-mono font-bold mr-1 ${ep.method === 'GET' ? 'text-fact' : 'text-primary'}`}>
                      {ep.method}
                    </span>
                    <span className="font-mono text-ink-light">{ep.path}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Endpoint detail */}
        <div className="lg:col-span-3">
          <div className="rounded-2xl border border-border bg-paper-light p-5 shadow-[0_16px_40px_rgba(43,43,43,0.05)]">
          <div className="flex items-center gap-3 mb-3">
            <span className={`px-2 py-1 rounded font-mono text-xs font-bold ${endpoint.method === 'GET' ? 'bg-fact/10 text-fact' : 'bg-primary/10 text-primary'}`}>
              {endpoint.method}
            </span>
            <code className="font-mono text-sm text-ink">{endpoint.path}</code>
          </div>
          <p className="text-sm text-ink-muted mb-4">{endpoint.description}</p>

          {/* Editable parameters */}
          {endpoint.params && (
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-ink-light mb-2">Parameters</h4>
              <div className="space-y-2">
                {endpoint.params.map((p) => (
                  <div key={p.name} className="flex items-center gap-3">
                    <label className="w-32 text-xs font-mono text-ink-light flex-shrink-0">
                      {p.name}{p.required && <span className="text-structural">*</span>}
                    </label>
                    <input
                      type="text"
                      value={paramValues[p.name] || ''}
                      onChange={(e) => setParamValues({ ...paramValues, [p.name]: e.target.value })}
                      placeholder={p.default || p.description}
                      className="flex-1 px-2 py-1.5 rounded border border-border bg-surface font-mono text-xs text-ink placeholder-ink-muted focus:outline-none focus:border-primary/50"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Editable request body */}
          {endpoint.body && (
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-ink-light mb-2">Request Body</h4>
              <textarea
                value={bodyValue || endpoint.body}
                onChange={(e) => setBodyValue(e.target.value)}
                className="w-full h-32 p-3 rounded-lg bg-charcoal text-paper-light font-mono text-xs focus:outline-none focus:ring-1 focus:ring-primary/30 resize-y"
              />
            </div>
          )}

          {/* Try it */}
          <button
            onClick={() => tryMutation.mutate(endpoint)}
            disabled={tryMutation.isPending}
            className="px-4 py-2 bg-primary text-paper-light rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors disabled:opacity-50 mb-4 shadow-[0_12px_24px_rgba(184,92,56,0.16)]"
          >
            {tryMutation.isPending ? 'Sending...' : 'Send request'}
          </button>

          {/* Response */}
          {response && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-ink-light">Response</h4>
                <div className="flex items-center gap-3 text-xs">
                  {responseStatus && (
                    <span className={`font-mono font-bold ${responseStatus < 400 ? 'text-fact' : 'text-structural'}`}>
                      {responseStatus}
                    </span>
                  )}
                  {responseTime && <span className="text-ink-muted font-mono">{responseTime}ms</span>}
                  <button onClick={() => copyToClipboard(response)} className="text-primary hover:text-primary-dark">Copy</button>
                </div>
              </div>
              <pre className="p-3 rounded-lg bg-charcoal text-paper-light font-mono text-xs overflow-x-auto max-h-80 overflow-y-auto">
                {response}
              </pre>
            </div>
          )}

          {/* Code examples */}
          <div>
            <h4 className="text-sm font-semibold text-ink-light mb-2">Examples</h4>
            <div className="space-y-3">
              {[
                { lang: 'Python', code: pythonExample },
                { lang: 'TypeScript', code: tsExample },
                { lang: 'curl', code: curlExample },
              ].map(({ lang, code }) => (
                <div key={lang}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-ink-muted">{lang}</span>
                    <button onClick={() => copyToClipboard(code)} className="text-xs text-primary hover:text-primary-dark">Copy</button>
                  </div>
                  <pre className="p-3 rounded-lg bg-charcoal text-paper-light font-mono text-xs overflow-x-auto mt-1">{code}</pre>
                </div>
              ))}
            </div>
          </div>
          </div>
        </div>
      </div>
    </div>
  );
}
