import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { searchCorpus } from '@/lib/api';
import type { CorpusSummary } from '@/types';

const KEY_OPTIONS = [
  'C major', 'C minor', 'D major', 'D minor', 'E major', 'E minor',
  'F major', 'F minor', 'G major', 'G minor', 'A major', 'A minor',
  'B major', 'B minor', 'Bb major', 'Bb minor', 'Eb major', 'Eb minor',
  'Ab major', 'F# minor',
];

export function CorpusExplorer() {
  const navigate = useNavigate();
  const [keyFilter, setKeyFilter] = useState('');
  const [searchText, setSearchText] = useState('');
  const [sortField, setSortField] = useState<keyof CorpusSummary>('chorale_id');
  const [sortAsc, setSortAsc] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggleSelection = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < 2) {
        next.add(id);
      }
      return next;
    });
  };

  const { data, isLoading, error } = useQuery({
    queryKey: ['corpus', 'list'],
    queryFn: () => searchCorpus({ limit: 500 }),
    staleTime: 5 * 60 * 1000,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    let results = data.results;

    if (keyFilter) {
      results = results.filter((r) => r.key?.toLowerCase() === keyFilter.toLowerCase());
    }
    if (searchText) {
      const q = searchText.toLowerCase();
      results = results.filter(
        (r) =>
          r.title.toLowerCase().includes(q) ||
          r.chorale_id.toLowerCase().includes(q),
      );
    }

    results = [...results].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      const cmp = typeof aVal === 'number' && typeof bVal === 'number'
        ? aVal - bVal
        : String(aVal).localeCompare(String(bVal));
      return sortAsc ? cmp : -cmp;
    });

    return results;
  }, [data, keyFilter, searchText, sortField, sortAsc]);

  const handleSort = (field: keyof CorpusSummary) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const SortIcon = ({ field }: { field: keyof CorpusSummary }) => {
    if (sortField !== field) return <span className="text-ink-muted/40 ml-1">&#8597;</span>;
    return <span className="text-primary ml-1">{sortAsc ? '&#9650;' : '&#9660;'}</span>;
  };

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-serif font-bold text-ink mb-2">Chorales</h1>
        <p className="text-ink-light">
          {data ? `${data.count} chorales` : 'Loading...'} from the DCML Bach Chorales corpus.
          Click any row for the full analysis.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="text"
          placeholder="Search by title or BWV number..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 w-64"
        />
        <select
          value={keyFilter}
          onChange={(e) => setKeyFilter(e.target.value)}
          className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink focus:outline-none focus:border-primary/50"
        >
          <option value="">All Keys</option>
          {KEY_OPTIONS.map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>
        {(keyFilter || searchText) && (
          <button
            onClick={() => { setKeyFilter(''); setSearchText(''); }}
            className="px-3 py-2 text-sm text-ink-muted hover:text-ink transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Results count + compare */}
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm text-ink-muted">
          {isLoading ? 'Loading...' : `${filtered.length} chorales`}
          {selected.size > 0 && (
            <span className="ml-2 text-primary font-medium">
              {selected.size} selected
              <button onClick={() => setSelected(new Set())} className="ml-1 text-ink-muted hover:text-ink">
                (clear)
              </button>
            </span>
          )}
        </div>
        {selected.size === 2 && (
          <button
            onClick={() => {
              const [a, b] = [...selected];
              navigate(`/corpus/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
            }}
            className="px-4 py-2 bg-primary-dark text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors"
          >
            Compare Selected
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-structural/10 border border-structural/20 rounded-lg text-sm text-structural mb-4">
          Could not load corpus. ({String(error)})
        </div>
      )}

      {!isLoading && !error && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-paper-dark/30">
                <th className="w-10 px-3 py-3"></th>
                <th className="text-left px-4 py-3 font-semibold text-ink-light cursor-pointer hover:text-ink" onClick={() => handleSort('chorale_id')}>
                  BWV <SortIcon field="chorale_id" />
                </th>
                <th className="text-left px-4 py-3 font-semibold text-ink-light cursor-pointer hover:text-ink" onClick={() => handleSort('title')}>
                  Title <SortIcon field="title" />
                </th>
                <th className="text-left px-4 py-3 font-semibold text-ink-light cursor-pointer hover:text-ink" onClick={() => handleSort('key')}>
                  Key <SortIcon field="key" />
                </th>
                <th className="text-right px-4 py-3 font-semibold text-ink-light cursor-pointer hover:text-ink" onClick={() => handleSort('harmonic_event_count')}>
                  Chords <SortIcon field="harmonic_event_count" />
                </th>
                <th className="text-right px-4 py-3 font-semibold text-ink-light cursor-pointer hover:text-ink" onClick={() => handleSort('cadence_count')}>
                  Cadences <SortIcon field="cadence_count" />
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((chorale) => (
                <tr key={chorale.chorale_id} className="border-b border-border-light hover:bg-paper-dark/20 transition-colors">
                  <td className="px-3 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(chorale.chorale_id)}
                      onChange={() => toggleSelection(chorale.chorale_id)}
                      disabled={!selected.has(chorale.chorale_id) && selected.size >= 2}
                      className="w-4 h-4 rounded border-border text-primary-dark accent-primary-dark"
                      aria-label={`Select ${chorale.chorale_id}`}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/corpus/${chorale.chorale_id}`} className="font-mono text-primary hover:text-primary-dark no-underline font-medium">
                      {chorale.chorale_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-ink">{chorale.title}</td>
                  <td className="px-4 py-3">
                    {chorale.key && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary-dark">
                        {chorale.key}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-light">{chorale.harmonic_event_count}</td>
                  <td className="px-4 py-3 text-right font-mono text-ink-light">{chorale.cadence_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="py-12 text-center text-ink-muted">No chorales match your filters.</div>
          )}
        </div>
      )}
    </div>
  );
}
