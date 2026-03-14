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
            Browse, hear, and study 361 four-part chorales. Follow how Bach harmonizes
            Lutheran tunes through the cadence points, the inner parts, and the pace of the
            harmony, note by note.
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
              Search by key, cadence type, or title. Each chorale opens into a piano roll,
              harmonic reading, cadence map, and part-writing view, with playback for every voice.
            </p>
          </Link>

          <Link to="/research" className="group block no-underline">
            <h3 className="font-serif text-lg font-semibold text-ink mb-2 group-hover:text-primary-dark transition-colors">
              Research Tools
            </h3>
            <p className="text-sm text-ink-light leading-relaxed">
              Compare one chorale with the rest of the collection, trace favorite progressions,
              and see which pieces sit closest together or furthest apart.
            </p>
          </Link>

          <Link to="/encyclopedia" className="group block no-underline">
            <h3 className="font-serif text-lg font-semibold text-ink mb-2 group-hover:text-primary-dark transition-colors">
              Encyclopedia
            </h3>
            <p className="text-sm text-ink-light leading-relaxed">
              Short essays on Bach's harmony, voice-leading, fugue writing, and text painting,
              with examples drawn from the chorales.
            </p>
          </Link>
        </div>
      </section>

      {/* About */}
      <section className="border-t border-border bg-paper-dark/30 py-16 px-6">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-serif font-semibold mb-4">About</h2>
          <p className="text-ink-light leading-relaxed mb-4">
            BachBot reads the scores directly. It marks Roman numerals, cadences, part-writing
            habits, and recurring progressions so you can move easily between the notation and the
            analysis.
          </p>
          <p className="text-ink-light leading-relaxed">
            The corpus comes from the{' '}
            <a href="https://github.com/DCMLab/bach_chorales" className="text-primary hover:text-primary-dark" target="_blank" rel="noopener noreferrer">
              DCML Bach Chorales
            </a>{' '}
            dataset. Playback, exports, and visual study tools all sit alongside the score.
          </p>
        </div>
      </section>
    </div>
  );
}
