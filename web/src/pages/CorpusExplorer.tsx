import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { searchCorpus } from '@/lib/api';
import { BaroqueFlourish, StaffDivider } from '@/components/shared/Decorative';
import type { CorpusSummary } from '@/types';

// ─── Shared Constants ──────────────────────────────────────────────

type Genre = 'chorales' | 'fugues';

const KEY_OPTIONS = [
  'C major', 'C minor', 'D major', 'D minor', 'E major', 'E minor',
  'F major', 'F minor', 'G major', 'G minor', 'A major', 'A minor',
  'B major', 'B minor', 'Bb major', 'Bb minor', 'Eb major', 'Eb minor',
  'Ab major', 'F# minor', 'C# major', 'C# minor', 'F# major',
  'G# minor', 'D# minor',
];

// ─── WTC Catalog ───────────────────────────────────────────────────
// The Well-Tempered Clavier: 48 preludes and fugues in all 24 keys.
// This is static reference data — voice counts are from the standard
// musicological catalog (Ledbetter, Tovey, et al.).

interface WtcFugue {
  bwv: string;
  key: string;
  book: 'I' | 'II';
  voices: number;
}

const WTC_FUGUES: WtcFugue[] = [
  // Book I (1722)
  { bwv: 'BWV 846', key: 'C major', book: 'I', voices: 4 },
  { bwv: 'BWV 847', key: 'C minor', book: 'I', voices: 3 },
  { bwv: 'BWV 848', key: 'C# major', book: 'I', voices: 3 },
  { bwv: 'BWV 849', key: 'C# minor', book: 'I', voices: 5 },
  { bwv: 'BWV 850', key: 'D major', book: 'I', voices: 4 },
  { bwv: 'BWV 851', key: 'D minor', book: 'I', voices: 3 },
  { bwv: 'BWV 852', key: 'Eb major', book: 'I', voices: 3 },
  { bwv: 'BWV 853', key: 'D# minor', book: 'I', voices: 4 },
  { bwv: 'BWV 854', key: 'E major', book: 'I', voices: 3 },
  { bwv: 'BWV 855', key: 'E minor', book: 'I', voices: 2 },
  { bwv: 'BWV 856', key: 'F major', book: 'I', voices: 3 },
  { bwv: 'BWV 857', key: 'F minor', book: 'I', voices: 4 },
  { bwv: 'BWV 858', key: 'F# major', book: 'I', voices: 3 },
  { bwv: 'BWV 859', key: 'F# minor', book: 'I', voices: 4 },
  { bwv: 'BWV 860', key: 'G major', book: 'I', voices: 3 },
  { bwv: 'BWV 861', key: 'G minor', book: 'I', voices: 4 },
  { bwv: 'BWV 862', key: 'Ab major', book: 'I', voices: 4 },
  { bwv: 'BWV 863', key: 'G# minor', book: 'I', voices: 4 },
  { bwv: 'BWV 864', key: 'A major', book: 'I', voices: 3 },
  { bwv: 'BWV 865', key: 'A minor', book: 'I', voices: 4 },
  { bwv: 'BWV 866', key: 'Bb major', book: 'I', voices: 3 },
  { bwv: 'BWV 867', key: 'Bb minor', book: 'I', voices: 5 },
  { bwv: 'BWV 868', key: 'B major', book: 'I', voices: 4 },
  { bwv: 'BWV 869', key: 'B minor', book: 'I', voices: 4 },
  // Book II (~1742)
  { bwv: 'BWV 870', key: 'C major', book: 'II', voices: 3 },
  { bwv: 'BWV 871', key: 'C minor', book: 'II', voices: 4 },
  { bwv: 'BWV 872', key: 'C# major', book: 'II', voices: 3 },
  { bwv: 'BWV 873', key: 'C# minor', book: 'II', voices: 3 },
  { bwv: 'BWV 874', key: 'D major', book: 'II', voices: 4 },
  { bwv: 'BWV 875', key: 'D minor', book: 'II', voices: 3 },
  { bwv: 'BWV 876', key: 'Eb major', book: 'II', voices: 4 },
  { bwv: 'BWV 877', key: 'D# minor', book: 'II', voices: 4 },
  { bwv: 'BWV 878', key: 'E major', book: 'II', voices: 4 },
  { bwv: 'BWV 879', key: 'E minor', book: 'II', voices: 3 },
  { bwv: 'BWV 880', key: 'F major', book: 'II', voices: 3 },
  { bwv: 'BWV 881', key: 'F minor', book: 'II', voices: 3 },
  { bwv: 'BWV 882', key: 'F# major', book: 'II', voices: 3 },
  { bwv: 'BWV 883', key: 'F# minor', book: 'II', voices: 3 },
  { bwv: 'BWV 884', key: 'G major', book: 'II', voices: 3 },
  { bwv: 'BWV 885', key: 'G minor', book: 'II', voices: 4 },
  { bwv: 'BWV 886', key: 'Ab major', book: 'II', voices: 4 },
  { bwv: 'BWV 887', key: 'G# minor', book: 'II', voices: 3 },
  { bwv: 'BWV 888', key: 'A major', book: 'II', voices: 3 },
  { bwv: 'BWV 889', key: 'A minor', book: 'II', voices: 3 },
  { bwv: 'BWV 890', key: 'Bb major', book: 'II', voices: 4 },
  { bwv: 'BWV 891', key: 'Bb minor', book: 'II', voices: 4 },
  { bwv: 'BWV 892', key: 'B major', book: 'II', voices: 4 },
  { bwv: 'BWV 893', key: 'B minor', book: 'II', voices: 3 },
];

// ─── Chorales Table ────────────────────────────────────────────────

function ChoraleTable() {
  const navigate = useNavigate();
  const [keyFilter, setKeyFilter] = useState('');
  const [searchText, setSearchText] = useState('');
  const [sortField, setSortField] = useState<keyof CorpusSummary>('chorale_id');
  const [sortAsc, setSortAsc] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggleSelection = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 2) next.add(id);
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
    if (keyFilter) results = results.filter((r) => r.key?.toLowerCase() === keyFilter.toLowerCase());
    if (searchText) {
      const q = searchText.toLowerCase();
      results = results.filter((r) => r.title.toLowerCase().includes(q) || r.chorale_id.toLowerCase().includes(q));
    }
    results = [...results].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      const cmp = typeof aVal === 'number' && typeof bVal === 'number' ? aVal - bVal : String(aVal).localeCompare(String(bVal));
      return sortAsc ? cmp : -cmp;
    });
    return results;
  }, [data, keyFilter, searchText, sortField, sortAsc]);

  const handleSort = (field: keyof CorpusSummary) => {
    if (sortField === field) setSortAsc(!sortAsc);
    else { setSortField(field); setSortAsc(true); }
  };

  const SortIcon = ({ field }: { field: keyof CorpusSummary }) => {
    if (sortField !== field) return <span className="text-ink-muted/40 ml-1">&#8597;</span>;
    return <span className="text-primary ml-1">{sortAsc ? '&#9650;' : '&#9660;'}</span>;
  };

  return (
    <>
      <p className="text-ink-muted mb-6">
        {data ? `${data.count} chorales` : 'Loading...'} from the DCML Bach Chorales corpus.
        Click any row for the full analysis.
      </p>

      {/* Filters */}
      <div className="mb-6 rounded-2xl border border-border bg-paper-light p-4 shadow-[0_12px_30px_rgba(43,43,43,0.04)]">
        <div className="flex flex-wrap gap-3 items-center">
          <input
            type="text"
            placeholder="Search by title or BWV number..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink placeholder-ink-muted focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 w-72"
          />
          <select
            value={keyFilter}
            onChange={(e) => setKeyFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink focus:outline-none focus:border-primary/50"
          >
            <option value="">All Keys</option>
            {KEY_OPTIONS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          {(keyFilter || searchText) && (
            <button onClick={() => { setKeyFilter(''); setSearchText(''); }} className="px-3 py-2 text-sm text-primary hover:text-primary-dark transition-colors">
              Clear Filters
            </button>
          )}
        </div>
      </div>

      {/* Results count + compare */}
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm text-ink-muted">
          {isLoading ? 'Loading...' : `${filtered.length} chorales`}
          {selected.size > 0 && (
            <span className="ml-2 text-primary font-medium">
              {selected.size} selected
              <button onClick={() => setSelected(new Set())} className="ml-1 text-ink-muted hover:text-ink">(clear)</button>
            </span>
          )}
        </div>
        {selected.size === 2 && (
          <button
            onClick={() => {
              const [a, b] = [...selected];
              navigate(`/corpus/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
            }}
            className="px-4 py-2 bg-primary text-paper-light rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors shadow-[0_12px_24px_rgba(184,92,56,0.18)]"
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
        <div className="overflow-x-auto rounded-2xl border border-border bg-paper-light shadow-[0_16px_40px_rgba(43,43,43,0.05)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#3a3530] bg-charcoal text-secondary">
                <th className="w-10 px-3 py-3"></th>
                <th className="text-left px-4 py-3 font-semibold cursor-pointer hover:text-paper-light" onClick={() => handleSort('chorale_id')}>BWV <SortIcon field="chorale_id" /></th>
                <th className="text-left px-4 py-3 font-semibold cursor-pointer hover:text-paper-light" onClick={() => handleSort('title')}>Title <SortIcon field="title" /></th>
                <th className="text-left px-4 py-3 font-semibold cursor-pointer hover:text-paper-light" onClick={() => handleSort('key')}>Key <SortIcon field="key" /></th>
                <th className="text-right px-4 py-3 font-semibold cursor-pointer hover:text-paper-light" onClick={() => handleSort('harmonic_event_count')}>Chords <SortIcon field="harmonic_event_count" /></th>
                <th className="text-right px-4 py-3 font-semibold cursor-pointer hover:text-paper-light" onClick={() => handleSort('cadence_count')}>Cadences <SortIcon field="cadence_count" /></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((chorale) => (
                <tr key={chorale.chorale_id} className="border-b border-border-light hover:bg-secondary/8 transition-colors">
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
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-secondary/20 text-ink">{chorale.key}</span>
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
    </>
  );
}

// ─── Fugues Table ──────────────────────────────────────────────────

function FugueTable() {
  const [bookFilter, setBookFilter] = useState<'' | 'I' | 'II'>('');
  const [keyFilter, setKeyFilter] = useState('');
  const [voiceFilter, setVoiceFilter] = useState<number | ''>('');

  const filtered = useMemo(() => {
    let results = WTC_FUGUES;
    if (bookFilter) results = results.filter((f) => f.book === bookFilter);
    if (keyFilter) results = results.filter((f) => f.key.toLowerCase() === keyFilter.toLowerCase());
    if (voiceFilter) results = results.filter((f) => f.voices === voiceFilter);
    return results;
  }, [bookFilter, keyFilter, voiceFilter]);

  const hasFilters = bookFilter || keyFilter || voiceFilter;

  return (
    <>
      <p className="text-ink-muted mb-2">
        48 fugues from the Well-Tempered Clavier, Books I & II.
      </p>
      <p className="text-xs text-ink-muted mb-6">
        Import MusicXML scores with <code className="px-1.5 py-0.5 rounded bg-charcoal text-secondary text-[11px]">bachbot corpus import fugue.musicxml --genre fugue</code> to enable full analysis — subject detection, answer type, stretto, episodes.
      </p>

      {/* Filters */}
      <div className="mb-6 rounded-2xl border border-border bg-paper-light p-4 shadow-[0_12px_30px_rgba(43,43,43,0.04)]">
        <div className="flex flex-wrap gap-3 items-center">
          <select
            value={bookFilter}
            onChange={(e) => setBookFilter(e.target.value as '' | 'I' | 'II')}
            className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink focus:outline-none focus:border-primary/50"
          >
            <option value="">Both Books</option>
            <option value="I">Book I (1722)</option>
            <option value="II">Book II (~1742)</option>
          </select>
          <select
            value={keyFilter}
            onChange={(e) => setKeyFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink focus:outline-none focus:border-primary/50"
          >
            <option value="">All Keys</option>
            {KEY_OPTIONS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <select
            value={voiceFilter}
            onChange={(e) => setVoiceFilter(e.target.value ? Number(e.target.value) : '')}
            className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-ink focus:outline-none focus:border-primary/50"
          >
            <option value="">All Voices</option>
            <option value="2">2 voices</option>
            <option value="3">3 voices</option>
            <option value="4">4 voices</option>
            <option value="5">5 voices</option>
          </select>
          {hasFilters && (
            <button onClick={() => { setBookFilter(''); setKeyFilter(''); setVoiceFilter(''); }} className="px-3 py-2 text-sm text-primary hover:text-primary-dark transition-colors">
              Clear Filters
            </button>
          )}
        </div>
      </div>

      <div className="text-sm text-ink-muted mb-3">{filtered.length} fugues</div>

      <div className="overflow-x-auto rounded-2xl border border-border bg-paper-light shadow-[0_16px_40px_rgba(43,43,43,0.05)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#3a3530] bg-charcoal text-secondary">
              <th className="text-left px-4 py-3 font-semibold">BWV</th>
              <th className="text-left px-4 py-3 font-semibold">Key</th>
              <th className="text-center px-4 py-3 font-semibold">Book</th>
              <th className="text-center px-4 py-3 font-semibold">Voices</th>
              <th className="text-left px-4 py-3 font-semibold">Analysis</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((fugue) => (
              <tr key={fugue.bwv} className="border-b border-border-light hover:bg-secondary/8 transition-colors">
                <td className="px-4 py-3 font-mono text-ink-light">{fugue.bwv}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-secondary/20 text-ink">{fugue.key}</span>
                </td>
                <td className="px-4 py-3 text-center font-serif text-ink-light">{fugue.book}</td>
                <td className="px-4 py-3 text-center font-mono text-ink-light">{fugue.voices}</td>
                <td className="px-4 py-3 text-xs text-ink-muted italic">Import to analyze</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-12 text-center text-ink-muted">No fugues match your filters.</div>
        )}
      </div>
    </>
  );
}

// ─── Page ──────────────────────────────────────────────────────────

export function CorpusExplorer() {
  const [genre, setGenre] = useState<Genre>('chorales');

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      <div className="mb-6">
        <div className="mb-2">
          <span className="inline-block text-secondary text-[11px] uppercase tracking-[0.28em] font-sans">
            Corpus Explorer
          </span>
        </div>

        {/* Genre tabs */}
        <div className="flex gap-1 mb-4">
          <button
            onClick={() => setGenre('chorales')}
            className={`px-5 py-2.5 text-lg font-serif transition-colors rounded-t-lg ${
              genre === 'chorales'
                ? 'bg-paper-light text-ink border border-b-0 border-border font-semibold'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            Chorales
          </button>
          <button
            onClick={() => setGenre('fugues')}
            className={`px-5 py-2.5 text-lg font-serif transition-colors rounded-t-lg ${
              genre === 'fugues'
                ? 'bg-paper-light text-ink border border-b-0 border-border font-semibold'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            Fugues
          </button>
        </div>

        <BaroqueFlourish className="mt-1" />
        <StaffDivider className="pt-2" />
      </div>

      {genre === 'chorales' ? <ChoraleTable /> : <FugueTable />}
    </div>
  );
}
