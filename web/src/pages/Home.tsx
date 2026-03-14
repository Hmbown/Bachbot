import { Link } from 'react-router-dom';

const SECTIONS = [
  {
    title: 'Corpus Explorer',
    path: '/corpus',
    description:
      'Search, browse, and analyze 361 fully annotated Bach chorales with interactive score rendering, harmonic analysis, and evidence bundles.',
    stat: '361 chorales',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        <path d="M8 7h8M8 11h6" />
      </svg>
    ),
  },
  {
    title: 'Composition Workshop',
    path: '/compose',
    description:
      'Harmonize melodies, realize figured bass, generate soprano lines, and compose two-part inventions with real-time SATB rendering.',
    stat: '4 generators',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M9 18V5l12-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="18" cy="16" r="3" />
      </svg>
    ),
  },
  {
    title: 'Theory Classroom',
    path: '/theory',
    description:
      'Interactive species counterpoint exercises with real-time validation, Bach technique lessons, and corpus-backed pedagogy.',
    stat: '5 species',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
      </svg>
    ),
  },
  {
    title: 'Research Lab',
    path: '/research',
    description:
      'Style fingerprinting, anomaly detection, pattern mining, embedding visualization, and edition comparison for computational musicology.',
    stat: '35 features',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="11" cy="11" r="8" />
        <path d="M21 21l-4.35-4.35" />
        <path d="M11 8v6M8 11h6" />
      </svg>
    ),
  },
  {
    title: 'Benchmark Arena',
    path: '/benchmark',
    description:
      'BachBench evaluation suite, cross-system comparison, leaderboard, and blind A/B human evaluation protocol.',
    stat: '4 tasks',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M8 21h8M12 17v4M6 3h12l-3 7h4l-7 7 2-5H8l3-7H6z" />
      </svg>
    ),
  },
  {
    title: 'Bach Encyclopedia',
    path: '/encyclopedia',
    description:
      'Analytically grounded articles on Bach\'s life, works, and techniques — every claim backed by corpus-level statistical evidence.',
    stat: '15,594 works',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4M12 8h.01" />
      </svg>
    ),
  },
  {
    title: 'API Playground',
    path: '/api-docs',
    description:
      'Interactive API documentation — try analysis, composition, and evaluation endpoints live with code examples.',
    stat: '7 endpoints',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
        <line x1="14" y1="4" x2="10" y2="20" />
      </svg>
    ),
  },
];

export function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="py-20 px-6 text-center bg-gradient-to-b from-paper-light to-paper">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-serif font-bold text-ink tracking-tight mb-6">
            The Bach Intelligence Platform
          </h1>
          <p className="text-lg text-ink-light leading-relaxed mb-8">
            The most comprehensive, interactive, and analytically deep resource for
            Johann Sebastian Bach's music. Powered by deterministic analysis,
            backed by{' '}
            <span className="font-semibold text-ink">361 fully analyzed chorales</span>,{' '}
            <span className="font-semibold text-ink">15,594 normalized works</span>, and{' '}
            <span className="font-semibold text-ink">688 passing tests</span>.
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Link
              to="/corpus"
              className="px-6 py-3 bg-primary-dark text-white rounded-lg font-medium text-sm hover:bg-primary transition-colors no-underline"
            >
              Explore the Corpus
            </Link>
            <Link
              to="/compose"
              className="px-6 py-3 bg-surface border border-border rounded-lg font-medium text-sm text-ink hover:bg-paper-dark transition-colors no-underline"
            >
              Start Composing
            </Link>
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="border-y border-border bg-surface-warm">
        <div className="max-w-[1400px] mx-auto px-6 py-6 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          {[
            { label: 'Analyzed Chorales', value: '361' },
            { label: 'Chord Types', value: '19' },
            { label: 'Extracted Features', value: '65' },
            { label: 'Composition Engines', value: '4' },
          ].map(({ label, value }) => (
            <div key={label}>
              <div className="text-2xl font-serif font-bold text-primary-dark">{value}</div>
              <div className="text-xs text-ink-muted mt-1">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Sections grid */}
      <section className="max-w-[1400px] mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {SECTIONS.map(({ title, path, description, stat, icon }) => (
            <Link
              key={path}
              to={path}
              className="group block p-6 bg-surface rounded-xl border border-border hover:border-primary/30 hover:shadow-lg transition-all no-underline"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="text-primary-dark">{icon}</div>
                <span className="text-xs font-mono text-ink-muted bg-paper-dark px-2 py-0.5 rounded">
                  {stat}
                </span>
              </div>
              <h3 className="font-serif text-lg font-semibold text-ink mb-2 group-hover:text-primary-dark transition-colors">
                {title}
              </h3>
              <p className="text-sm text-ink-light leading-relaxed">{description}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* Design principles */}
      <section className="border-t border-border bg-paper-dark/30 py-16 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-2xl font-serif font-semibold mb-4">Deterministic Before Generative</h2>
          <p className="text-ink-light leading-relaxed">
            Every analytical claim carries an evidence status:{' '}
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-fact" />
              <span className="text-fact font-medium text-sm">Supported Fact</span>
            </span>,{' '}
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-inference" />
              <span className="text-inference font-medium text-sm">Inference</span>
            </span>,{' '}
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-speculation" />
              <span className="text-speculation font-medium text-sm">Speculation</span>
            </span>, or{' '}
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-disputed" />
              <span className="text-disputed font-medium text-sm">Disputed</span>
            </span>.
            Symbolic analysis is the source of truth. The LLM provides commentary, never invents facts.
          </p>
        </div>
      </section>
    </div>
  );
}
