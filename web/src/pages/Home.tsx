import { Link } from 'react-router-dom';

export function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="py-20 px-6 bg-gradient-to-b from-paper-light to-paper">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-serif font-bold text-ink tracking-tight mb-6">
            Johann Sebastian Bach
          </h1>
          <p className="text-lg text-ink-light leading-relaxed mb-8">
            Browse, listen to, and analyze 361 four-part chorales. See how Bach harmonizes
            Lutheran hymn tunes &mdash; the voice-leading, the cadences, the harmonic rhythm &mdash;
            down to every note.
          </p>
          <Link
            to="/corpus"
            className="inline-block px-6 py-3 bg-primary-dark text-white rounded-lg font-medium text-sm hover:bg-primary transition-colors no-underline"
          >
            Explore the Chorales
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-[1100px] mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <Link to="/corpus" className="group block no-underline">
            <h3 className="font-serif text-lg font-semibold text-ink mb-2 group-hover:text-primary-dark transition-colors">
              361 Chorales
            </h3>
            <p className="text-sm text-ink-light leading-relaxed">
              Search by key, cadence type, or title. Each chorale has a piano roll, harmonic analysis,
              cadence map, and voice-leading report. Listen with per-voice playback controls.
            </p>
          </Link>

          <Link to="/research" className="group block no-underline">
            <h3 className="font-serif text-lg font-semibold text-ink mb-2 group-hover:text-primary-dark transition-colors">
              Research Tools
            </h3>
            <p className="text-sm text-ink-light leading-relaxed">
              Style fingerprinting across 35 features, anomaly detection, harmonic pattern mining,
              and corpus-wide embedding visualization. Tools for computational musicology.
            </p>
          </Link>

          <Link to="/encyclopedia" className="group block no-underline">
            <h3 className="font-serif text-lg font-semibold text-ink mb-2 group-hover:text-primary-dark transition-colors">
              Encyclopedia
            </h3>
            <p className="text-sm text-ink-light leading-relaxed">
              Articles on Bach's harmonic language, voice-leading principles, fugue technique,
              and text-music relationships &mdash; grounded in corpus statistics.
            </p>
          </Link>
        </div>
      </section>

      {/* About */}
      <section className="border-t border-border bg-paper-dark/30 py-16 px-6">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-serif font-semibold mb-4">About</h2>
          <p className="text-ink-light leading-relaxed mb-4">
            BachBot analyzes Bach's chorales using symbolic music analysis &mdash; no neural networks,
            no guessing. It extracts harmony (Roman numerals), detects cadences, checks voice-leading
            rules, and identifies harmonic patterns across the entire corpus.
          </p>
          <p className="text-ink-light leading-relaxed">
            The corpus comes from the{' '}
            <a href="https://github.com/DCMLab/bach_chorales" className="text-primary hover:text-primary-dark" target="_blank" rel="noopener noreferrer">
              DCML Bach Chorales
            </a>{' '}
            dataset. Analysis, playback, and visualization are all handled in the browser.
          </p>
        </div>
      </section>
    </div>
  );
}
