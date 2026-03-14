import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchEncyclopediaStats } from '@/lib/api';

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
    summary: 'Bach harmonized Lutheran hymn tunes in four voices. These 371 settings became the foundation of Western harmony pedagogy.',
    content: (s) => ({
      paragraphs: [
        `This corpus contains ${s.total_chorales || 361} Bach chorales. Each takes a pre-existing hymn melody in the soprano and harmonizes it for four voices: Soprano, Alto, Tenor, and Bass. Most are between 8 and 24 measures long.`,
        'Bach composed these settings throughout his career for use in church cantatas, oratorios, and passions. Many were collected posthumously by C.P.E. Bach and published as a set. They became the standard teaching material for tonal harmony and voice-leading — a role they still hold today.',
        `Across the corpus, chorales average ${s.avg_harmonic_events || '~24'} harmonic events and ${s.avg_cadences || '~5'} cadences per piece. Despite their brevity, each one is a concentrated study in functional harmony.`,
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
    summary: 'Bach\'s chord vocabulary, key relationships, and modulation techniques across the chorale corpus.',
    content: (s) => ({
      paragraphs: [
        `The chorales span ${s.total_keys || '~20'} distinct key areas. Major and minor modes are both well-represented, with chorales in every commonly used key.`,
        'Bach uses secondary dominants freely — V/V and V/vi appear in the majority of chorales, creating harmonic tension that resolves to tonicized chords. Modulations typically use common-chord pivots: a chord that belongs to both the old and new key serves as the hinge.',
        'The cadence vocabulary includes authentic cadences (both perfect and imperfect), half cadences, deceptive cadences, and plagal cadences. Perfect authentic cadences end most phrases, while half cadences and deceptive cadences create forward momentum mid-phrase.',
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
    summary: 'The contrapuntal rules Bach follows: parallel motion, spacing, tendency tones, and range.',
    content: () => ({
      paragraphs: [
        'Bach avoids parallel perfect fifths and octaves between any pair of voices. He prefers contrary motion (voices moving in opposite directions) and oblique motion (one voice holds while the other moves). Similar motion to a perfect interval is treated with care.',
        'Each voice stays within a singable range. The soprano and alto are kept within an octave of each other, as are the alto and tenor. The tenor and bass may be up to a 12th apart. Voice crossing is rare.',
        'Tendency tones resolve predictably: leading tones rise to the tonic, the seventh of a dominant chord falls by step. Passing tones, neighbor tones, and suspensions add melodic interest without disrupting the harmonic framework.',
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
    summary: 'Subjects, answers, stretto, and episode construction in the Well-Tempered Clavier.',
    content: () => ({
      paragraphs: [
        'The Well-Tempered Clavier contains 48 preludes and fugues in two books (1722 and 1742), one in each major and minor key. The fugues range from 2 to 5 voices.',
        'Each fugue begins with a subject stated alone. The answer enters in the dominant, either as a "real" answer (exact transposition) or a "tonal" answer (with adjusted intervals to stay in the home key). A countersubject often accompanies the answer and recurs throughout.',
        'Episodes develop fragments of the subject through sequence, modulating between key areas. Stretto — overlapping entries of the subject before the previous statement finishes — creates intensification, often near the end of the fugue.',
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
    summary: 'How Bach uses musical figures to illustrate the meaning of chorale texts.',
    content: () => ({
      paragraphs: [
        'Bach frequently paints the text with musical gestures. Rising lines (anabasis) accompany words about heaven, resurrection, or joy. Falling lines (catabasis) depict descent, death, or sorrow.',
        'The passus duriusculus — a chromatic descending line — is one of Bach\'s most characteristic devices for expressing anguish and suffering. Suspiratio, a "sighing" figure using short rests, conveys longing or grief.',
        'These techniques come from the Baroque tradition of musica poetica, which treated composition as a form of rhetoric. Bach was deeply steeped in this tradition and used it with extraordinary subtlety.',
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
      className="block p-6 rounded-xl border border-border bg-surface hover:border-primary/30 hover:shadow-sm transition-all no-underline"
    >
      <h3 className="font-serif text-lg font-semibold text-ink mb-1">{article.title}</h3>
      <p className="text-sm text-ink-light leading-relaxed">{article.summary}</p>
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
        <h1 className="text-3xl font-serif font-bold text-ink mb-2">Encyclopedia</h1>
        <p className="text-ink-light">
          Articles on Bach's compositional techniques, with statistics drawn from 361 analyzed chorales.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {ARTICLES.map((a) => <ArticleCard key={a.slug} article={a} />)}
      </div>
    </div>
  );
}
