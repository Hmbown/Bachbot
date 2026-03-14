import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchEncyclopediaStats } from '@/lib/api';

interface ArticleMeta {
  slug: string;
  title: string;
  summary: string;
  icon: string;
  content: (stats: Record<string, unknown>) => { paragraphs: string[]; stats: { label: string; value: string }[] };
}

const ARTICLES: ArticleMeta[] = [
  {
    slug: 'chorale-tradition',
    title: 'The Bach Chorale Tradition',
    summary: 'Four-part harmonization of Lutheran hymn tunes, the cornerstone of Western tonal harmony pedagogy.',
    icon: 'M12 3v10.586l-3.293-3.293a1 1 0 00-1.414 1.414l5 5a1 1 0 001.414 0l5-5a1 1 0 00-1.414-1.414L14 13.586V3',
    content: (s) => ({
      paragraphs: [
        `The DCML corpus contains ${s.total_chorales || 361} analyzed Bach chorales spanning the complete range of keys and styles. Each chorale harmonizes a Lutheran hymn tune (chorale melody) in four voices: Soprano, Alto, Tenor, and Bass.`,
        'Bach composed these harmonizations throughout his career, with many collected posthumously by C.P.E. Bach. They represent the pinnacle of functional tonal harmony and remain the primary teaching material for voice-leading and part-writing.',
        `The chorales use an average of ${s.avg_harmonic_events || '~24'} harmonic events and ${s.avg_cadences || '~5'} cadences per piece, demonstrating remarkable harmonic density within compact forms.`,
      ],
      stats: [
        { label: 'Total chorales', value: String(s.total_chorales || 361) },
        { label: 'Avg. harmonic events', value: String(s.avg_harmonic_events || '~24') },
        { label: 'Avg. cadences per chorale', value: String(s.avg_cadences || '~5') },
      ],
    }),
  },
  {
    slug: 'harmonic-language',
    title: "Bach's Harmonic Language",
    summary: 'Secondary dominants, pivot chord modulations, and the rich harmonic vocabulary that defines the Bach style.',
    icon: 'M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM21 16c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z',
    content: (s) => ({
      paragraphs: [
        `Bach's harmonic vocabulary encompasses ${s.total_keys || '~20'} distinct key areas across the corpus. The distribution between major and minor modes reflects the full range of tonal expression.`,
        'Secondary dominants (V/V, V/vi, etc.) appear in the vast majority of chorales, creating moments of increased harmonic tension and forward motion. Common-chord pivot modulations connect key areas smoothly.',
        `The cadence type distribution across the corpus shows the predominance of authentic cadences alongside half, deceptive, and plagal cadences, each serving specific phrase-structural and expressive functions.`,
      ],
      stats: [
        { label: 'Distinct key areas', value: String(s.total_keys || '~20') },
        { label: 'Avg. unique chords', value: String(s.avg_unique_chords || '~14') },
        { label: 'Cadence types', value: Object.keys((s.cadence_type_distribution as Record<string, number>) || {}).join(', ') || 'authentic, half, deceptive, plagal' },
      ],
    }),
  },
  {
    slug: 'voice-leading',
    title: 'Voice-Leading Principles',
    summary: 'Parallel motion restrictions, tendency tones, and the contrapuntal foundation of Bach chorales.',
    icon: 'M4 6h16M4 10h16M4 14h16M4 18h16',
    content: () => ({
      paragraphs: [
        'Voice-leading in Bach chorales follows strict contrapuntal principles: parallel perfect fifths and octaves are avoided between all voice pairs, voice crossing is rare, and each voice maintains a singable range.',
        'Tendency tones (leading tones resolve up, seventh of V resolves down) are treated with remarkable consistency. Nonharmonic tones — passing tones, neighbor tones, suspensions, and anticipations — add melodic fluency.',
        'The soprano voice typically moves by step, with leaps balanced by contrary stepwise motion. Inner voices (alto and tenor) favor oblique and contrary motion. The bass provides harmonic foundation with characteristic patterns.',
      ],
      stats: [
        { label: 'SATB range', value: 'S: C4-G5, A: F3-C5, T: C3-G4, B: E2-C4' },
        { label: 'Max spacing', value: 'S-A: 12st, A-T: 12st, T-B: 19st' },
        { label: 'Preferred motion', value: 'Contrary > Oblique > Similar > Parallel' },
      ],
    }),
  },
  {
    slug: 'fugue-technique',
    title: 'Fugue & Counterpoint',
    summary: "Imitative techniques from the Well-Tempered Clavier: subjects, answers, stretto, and episode construction.",
    icon: 'M5 3v18l7-4 7 4V3H5z',
    content: () => ({
      paragraphs: [
        'The Well-Tempered Clavier (WTC) contains 48 fugues across two books, each in a different key. Subjects range from compact 4-note motifs to extended melodies spanning multiple measures.',
        'Tonal answers transpose the subject to the dominant, adjusting intervals to maintain tonal coherence. Real answers preserve exact intervals. Countersubjects provide invertible counterpoint at the octave.',
        'Episodes develop subject fragments through sequential patterns, modulating between key areas. Stretto entries overlap subject statements, creating heightened contrapuntal intensity near the fugue climax.',
      ],
      stats: [
        { label: 'WTC fugues', value: '48 (24 per book)' },
        { label: 'Voice count', value: '2-5 voices' },
        { label: 'Key coverage', value: 'All 24 major/minor keys' },
      ],
    }),
  },
  {
    slug: 'text-music',
    title: 'Text-Music Relationships',
    summary: 'Word-painting, rhetorical figures, and the expressive interplay between chorale text and musical setting.',
    icon: 'M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9',
    content: () => ({
      paragraphs: [
        "Bach's chorales frequently employ word-painting techniques that musically illustrate textual meaning. Ascending lines (anabasis) depict resurrection, heaven, or joy; descending lines (catabasis) express descent, grief, or humility.",
        'The passus duriusculus (chromatic descent) signals suffering and anguish, while suspiratio (sighing figures with rests) evokes longing. Cross-motifs (sharp accidentals forming cross shapes) symbolize the crucifixion.',
        'These rhetorical figures operate within the broader framework of musica poetica — the Baroque practice of composing music as a form of rhetoric, with clearly defined figures of speech.',
      ],
      stats: [
        { label: 'Common figures', value: 'Anabasis, Catabasis, Passus duriusculus, Suspiratio' },
        { label: 'Detection method', value: 'Contour + chromatic analysis' },
        { label: 'Coverage', value: 'All chorales with text data' },
      ],
    }),
  },
  {
    slug: 'disputed-attributions',
    title: 'Disputed Attributions',
    summary: 'Statistical style analysis identifies chorales whose compositional fingerprints deviate from the Bach norm.',
    icon: 'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    content: () => ({
      paragraphs: [
        'Not all chorales in the traditional Bach corpus are universally accepted as authentic. Style fingerprinting with 35 features and z-score anomaly detection can identify statistical outliers.',
        'Chorales with anomaly scores exceeding 2 standard deviations from the corpus mean warrant closer examination. Common indicators include unusual harmonic vocabulary, atypical voice-leading patterns, and anomalous cadence distributions.',
        'The Research Lab\'s anomaly detection tool ranks all chorales by deviation from the norm, providing evidence-based support for attribution discussions — always labeled as INFERENCE or SPECULATION, never as definitive judgments.',
      ],
      stats: [
        { label: 'Features analyzed', value: '35 per chorale' },
        { label: 'Anomaly threshold', value: '|z| > 2.0' },
        { label: 'Method', value: 'Cosine similarity + Euclidean distance' },
      ],
    }),
  },
];

function ArticleCard({ article }: { article: ArticleMeta }) {
  return (
    <Link
      to={`/encyclopedia/${article.slug}`}
      className="block p-6 rounded-xl border border-border bg-surface hover:border-primary/30 hover:shadow-sm transition-all no-underline"
    >
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary-dark)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d={article.icon} />
          </svg>
        </div>
        <div>
          <h3 className="font-serif text-lg font-semibold text-ink mb-1">{article.title}</h3>
          <p className="text-sm text-ink-light leading-relaxed">{article.summary}</p>
        </div>
      </div>
    </Link>
  );
}

export function EncyclopediaArticle() {
  const { slug } = useParams<{ slug: string }>();
  const article = ARTICLES.find((a) => a.slug === slug);

  const { data: stats } = useQuery({
    queryKey: ['encyclopedia', 'stats'],
    queryFn: fetchEncyclopediaStats,
    staleTime: 10 * 60 * 1000,
  });

  if (!article) {
    return (
      <div className="max-w-[800px] mx-auto px-6 py-12">
        <p className="text-ink-muted">Article not found.</p>
        <Link to="/encyclopedia" className="text-primary text-sm mt-4 inline-block">Back to Encyclopedia</Link>
      </div>
    );
  }

  const content = article.content(stats || {});

  return (
    <div className="max-w-[900px] mx-auto px-6 py-8">
      <div className="flex items-center gap-2 text-sm text-ink-muted mb-6">
        <Link to="/encyclopedia" className="hover:text-ink no-underline">Encyclopedia</Link>
        <span>/</span>
        <span className="text-ink font-medium">{article.title}</span>
      </div>

      <h1 className="text-3xl font-serif font-bold text-ink mb-4">{article.title}</h1>
      <p className="text-lg text-ink-light mb-8 leading-relaxed">{article.summary}</p>

      <div className="grid grid-cols-3 gap-3 mb-8">
        {content.stats.map((s, i) => (
          <div key={i} className="p-4 rounded-lg border border-border bg-surface">
            <div className="text-sm font-semibold text-primary-dark font-serif">{s.value}</div>
            <div className="text-xs text-ink-muted mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="space-y-4 mb-8">
        {content.paragraphs.map((p, i) => (
          <p key={i} className="text-ink leading-relaxed">{p}</p>
        ))}
      </div>

      <div className="p-4 rounded-xl bg-surface-warm border border-border">
        <h3 className="text-sm font-semibold text-ink-light mb-2">Explore Further</h3>
        <div className="flex gap-3 flex-wrap">
          <Link to="/corpus" className="text-sm text-primary hover:text-primary-dark no-underline">Corpus Explorer</Link>
          <Link to="/research" className="text-sm text-primary hover:text-primary-dark no-underline">Research Lab</Link>
          <Link to="/compose" className="text-sm text-primary hover:text-primary-dark no-underline">Composition Workshop</Link>
        </div>
      </div>
    </div>
  );
}

export function Encyclopedia() {
  return (
    <div className="max-w-[1400px] mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-serif font-bold text-ink mb-2">Encyclopedia</h1>
        <p className="text-ink-light">
          Data-driven articles on Bach's compositional techniques, backed by live corpus statistics from 361 analyzed chorales.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {ARTICLES.map((a) => <ArticleCard key={a.slug} article={a} />)}
      </div>
    </div>
  );
}
