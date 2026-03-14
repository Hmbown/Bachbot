import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchEncyclopediaStats } from '@/lib/api';
import { BaroqueFlourish, CornerOrnaments, SectionHeading, StaffDivider } from '@/components/shared/Decorative';

interface ArticleMeta {
  slug: string;
  title: string;
  summary: string;
  content: (stats: Record<string, unknown>) => { paragraphs: string[]; stats: { label: string; value: string }[] };
}

const ARTICLES: ArticleMeta[] = [
  {
    slug: 'chorale-tradition',
    title: 'The Chorale Tradition',
    summary: 'Bach turned Lutheran hymn tunes into four-part studies in balance, cadence, and inner-voice craft.',
    content: (s) => ({
      paragraphs: [
        `This corpus contains ${s.total_chorales || 361} Bach chorales. Each begins with a hymn melody, usually in the soprano, and sets it in four voices: soprano, alto, tenor, and bass.`,
        'Bach wrote these settings across much of his career for use in cantatas, passions, and other church music. Gathered together after his death, they became some of the most enduring teaching pieces in tonal harmony and voice-leading.',
        `Across the corpus, chorales average ${s.avg_harmonic_events || '~24'} harmonic events and ${s.avg_cadences || '~5'} cadences per piece. They are short, but rarely slight: a single phrase can carry an entire lesson in pacing, balance, and harmonic weight.`,
      ],
      stats: [
        { label: 'Chorales analyzed', value: String(s.total_chorales || 361) },
        { label: 'Avg. harmonic events', value: String(s.avg_harmonic_events || '~24') },
        { label: 'Avg. cadences', value: String(s.avg_cadences || '~5') },
      ],
    }),
  },
  {
    slug: 'harmonic-language',
    title: "Harmonic Language",
    summary: 'How Bach colors a phrase through key, cadence, tonicization, and harmonic pacing.',
    content: (s) => ({
      paragraphs: [
        `The chorales move through about ${s.total_keys || '~20'} distinct key areas. Major and minor are both well represented, and Bach is comfortable in every key a church musician of his day would have expected to meet.`,
        'Secondary dominants are one of his favorite ways of brightening a line. A brief V/V or V/vi can sharpen the pull of a phrase without feeling like a grand detour, especially when a common chord quietly links the old key to the new one.',
        'Cadences do much of the large-scale shaping. Perfect authentic cadences tend to settle the phrase; half and deceptive cadences keep it moving; plagal motion appears more sparingly, usually as a color rather than the main structural close.',
      ],
      stats: [
        { label: 'Key areas', value: String(s.total_keys || '~20') },
        { label: 'Avg. unique chords', value: String(s.avg_unique_chords || '~14') },
        { label: 'Cadence types', value: Object.keys((s.cadence_type_distribution as Record<string, number>) || {}).join(', ') || 'PAC, IAC, HC, DC' },
      ],
    }),
  },
  {
    slug: 'voice-leading',
    title: 'Voice-Leading',
    summary: 'How the four voices stay singable, independent, and tightly woven together.',
    content: () => ({
      paragraphs: [
        'Bach is careful with parallels, especially perfect fifths and octaves. Contrary and oblique motion help each line keep its own shape, while similar motion into a perfect interval is handled with restraint.',
        'The voices also remain singable. Soprano, alto, tenor, and bass each stay within a practical range, and the upper three parts are spaced closely enough to sound like one fabric rather than stacked blocks.',
        'Tendency tones behave with purpose: the leading tone rises, the seventh of the dominant falls, and dissonances such as passing tones or suspensions are prepared and resolved so that expression never clouds the underlying harmony.',
      ],
      stats: [
        { label: 'Ranges', value: 'S: C4-G5, A: F3-C5, T: C3-G4, B: E2-C4' },
        { label: 'Max spacing', value: 'S-A: octave, A-T: octave, T-B: 12th' },
        { label: 'Forbidden parallels', value: 'Perfect 5ths and octaves' },
      ],
    }),
  },
  {
    slug: 'fugue-technique',
    title: 'Fugue & Counterpoint',
    summary: 'Subjects, answers, stretto, and the patient art of spinning one idea into many.',
    content: () => ({
      paragraphs: [
        'The Well-Tempered Clavier contains 48 preludes and fugues in two books (1722 and 1742), one in each major and minor key. The fugues range from 2 to 5 voices.',
        'Each fugue begins with a subject stated alone. The answer follows, usually in the dominant, either as a real answer or a tonal one adjusted just enough to keep the tonal center clear. A countersubject may join it and return again and again.',
        'Episodes break the subject into smaller pieces and carry them through sequence into new key areas. Stretto, where entries overlap before the previous statement has ended, is one of Bach\'s surest ways of gathering energy near a climax.',
      ],
      stats: [
        { label: 'WTC fugues', value: '48 (24 per book)' },
        { label: 'Voices', value: '2 to 5' },
        { label: 'Keys', value: 'All 24 major and minor' },
      ],
    }),
  },
  {
    slug: 'text-music',
    title: 'Text & Music',
    summary: 'How Bach answers words with gesture, contour, chromatic color, and rhetorical figures.',
    content: () => ({
      paragraphs: [
        'Bach frequently paints the text with musical gestures. Rising lines (anabasis) accompany words about heaven, resurrection, or joy. Falling lines (catabasis) depict descent, death, or sorrow.',
        'The passus duriusculus — a chromatic descending line — is one of Bach\'s most characteristic devices for expressing anguish and suffering. Suspiratio, a "sighing" figure using short rests, conveys longing or grief.',
        'These figures belong to the Baroque tradition of musica poetica, where composition was understood as a kind of rhetoric. In Bach, the technique rarely feels decorative; it sounds as though the words have worked their way into the musical line itself.',
      ],
      stats: [
        { label: 'Common figures', value: 'Anabasis, Catabasis, Passus duriusculus' },
        { label: 'Tradition', value: 'Musica poetica (Baroque rhetoric)' },
        { label: 'Scope', value: 'Chorales with surviving text' },
      ],
    }),
  },
];

function ArticleCard({ article }: { article: ArticleMeta }) {
  return (
    <Link
      to={`/encyclopedia/${article.slug}`}
      className="group relative block p-6 rounded-2xl border border-border bg-paper-light hover:border-secondary hover:shadow-[0_18px_42px_rgba(201,168,76,0.12)] transition-all no-underline"
    >
      <CornerOrnaments />
      <div className="mb-4 h-1 w-20 rounded-full bg-gradient-to-r from-secondary to-primary opacity-70" aria-hidden="true" />
      <h3 className="font-serif text-lg font-semibold text-ink mb-2">{article.title}</h3>
      <p className="text-sm text-ink-muted leading-relaxed">{article.summary}</p>
      <div className="mt-4 text-sm text-primary opacity-0 transition-opacity group-hover:opacity-100">Read more →</div>
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
        <Link to="/encyclopedia" className="text-primary text-sm mt-4 inline-block no-underline">Back to Encyclopedia</Link>
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

      <h1 className="text-4xl mb-3">{article.title}</h1>
      <p className="text-lg text-ink-muted mb-4 leading-relaxed">{article.summary}</p>
      <BaroqueFlourish className="mb-2" />
      <StaffDivider className="pt-0 mb-6" />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
        {content.stats.map((s, i) => (
          <div key={i} className="p-4 rounded-xl border border-border bg-paper-light shadow-[0_12px_30px_rgba(43,43,43,0.04)]">
            <div className="text-lg font-semibold text-primary font-serif">{s.value}</div>
            <div className="text-xs uppercase tracking-[0.16em] text-ink-muted mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="space-y-4 mb-8">
        {content.paragraphs.map((p, i) => (
          <p key={i} className={`text-ink leading-relaxed ${i === 0 ? 'first-letter:float-left first-letter:mr-2 first-letter:text-5xl first-letter:font-serif first-letter:text-secondary' : ''}`}>
            {p}
          </p>
        ))}
      </div>

      <div className="p-5 rounded-2xl bg-paper-light border border-border shadow-[0_12px_30px_rgba(43,43,43,0.04)]">
        <h3 className="text-sm font-semibold text-ink-light mb-2">Keep Listening</h3>
        <div className="flex gap-3 flex-wrap">
          <Link to="/corpus" className="text-sm text-primary hover:text-primary-dark no-underline">Browse Chorales</Link>
          <Link to="/research" className="text-sm text-primary hover:text-primary-dark no-underline">Research Tools</Link>
        </div>
      </div>
    </div>
  );
}

export function Encyclopedia() {
  return (
    <div className="max-w-[1100px] mx-auto px-6 py-8">
      <div className="mb-8">
        <div className="mb-2">
          <span className="inline-block text-secondary text-[11px] uppercase tracking-[0.28em] font-sans">
            Essays & Figures
          </span>
        </div>
        <SectionHeading className="mb-3">Encyclopedia</SectionHeading>
        <p className="text-ink-muted">
          Short essays on Bach's craft, with examples and figures drawn from the chorales.
        </p>
        <BaroqueFlourish className="mt-4" />
        <StaffDivider className="pt-2" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {ARTICLES.map((a) => <ArticleCard key={a.slug} article={a} />)}
      </div>
    </div>
  );
}
