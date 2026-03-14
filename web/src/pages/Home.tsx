import { Link } from 'react-router-dom';
import {
  BaroqueFlourish,
  CornerOrnaments,
  FloatingNotes,
  SectionHeading,
  StaffDivider,
  TrebleClefWatermark,
} from '@/components/shared/Decorative';

const FEATURES = [
  {
    title: '361 Chorales',
    description: 'Browse the complete collection with playback, harmonic analysis, cadence maps, and voice-leading views.',
    path: '/corpus',
    icon: FeatureNoteIcon,
  },
  {
    title: 'Compose',
    description: 'Harmonize a soprano melody, realize figured bass, generate counterpoint, or write a two-part invention.',
    path: '/compose',
    icon: FeaturePenIcon,
  },
  {
    title: 'Theory Classroom',
    description: 'Study species counterpoint from first species through florid. Write against a cantus firmus and check your work.',
    path: '/theory',
    icon: FeatureRulerIcon,
  },
  {
    title: 'Research Tools',
    description: 'Trace progressions, inspect anomalies, compare profiles, and map the chorales in stylistic space.',
    path: '/research',
    icon: FeatureLensIcon,
  },
  {
    title: 'Encyclopedia',
    description: 'Nine essays on Bach\u2019s craft — chorales, fugue, the WTC, the cantatas, the passions — with links to free scores on IMSLP.',
    path: '/encyclopedia',
    icon: FeatureBookIcon,
  },
];

const PROGRESSION = ['I', 'vi', 'IV', 'ii', 'V7', 'I'];

function FeatureNoteIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M8 18a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Zm8-3a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z" transform="translate(-2 -2)" />
      <path d="M11 18V6l8-2v12" />
      <path d="M11 10l8-2" />
    </svg>
  );
}

function FeatureLensIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4.5 4.5" />
      <path d="M8.5 11h5" />
      <path d="M11 8.5v5" />
    </svg>
  );
}

function FeatureBookIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M5 4.5h10.5A2.5 2.5 0 0 1 18 7v12.5H7.5A2.5 2.5 0 0 0 5 22V4.5Z" />
      <path d="M5 4.5v15A2.5 2.5 0 0 1 7.5 17H18" />
      <path d="M9 8h5" />
      <path d="M9 11h4" />
    </svg>
  );
}

function FeaturePenIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M12 19l7-7 3 3-7 7-3 0Z" />
      <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18" />
      <path d="M2 2l7.586 7.586" />
      <circle cx="11" cy="11" r="2" />
    </svg>
  );
}

function FeatureRulerIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M3 5h18v14H3z" />
      <path d="M3 9h4M3 13h3M3 17h4M13 5v4M9 5v3M17 5v4M21 9h-4M21 13h-3M21 17h-4" />
    </svg>
  );
}

export function Home() {
  return (
    <div>
      <section className="relative overflow-hidden bg-gradient-to-b from-paper via-surface to-paper py-24 md:py-32">
        <TrebleClefWatermark />
        <FloatingNotes count={6} />

        <div className="relative max-w-5xl mx-auto px-6 text-center">
          <div className="mb-4">
            <span className="inline-block text-secondary text-[11px] uppercase tracking-[0.35em] font-sans">
              A Digital Manuscript
            </span>
          </div>
          <h1 className="mb-3">Johann Sebastian Bach</h1>
          <p className="text-xl italic text-ink-muted mb-5">
            Chorales, Fugues, and Counterpoint — Browse, Hear, Study
          </p>
          <BaroqueFlourish className="mb-6" />

          <div className="flex justify-center gap-3 mb-8 flex-wrap">
            {PROGRESSION.map((chord, index) => (
              <span
                key={index}
                className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-secondary/70 bg-paper-light/80 font-serif text-lg font-semibold text-ink-light shadow-[0_8px_24px_rgba(201,168,76,0.08)]"
              >
                {chord}
              </span>
            ))}
          </div>

          <p className="max-w-3xl mx-auto text-lg text-ink-light leading-relaxed mb-8">
            361 four-part chorales with playback, harmonic analysis, and voice-leading views.
            Composition tools for harmonization, figured bass, and counterpoint. Nine essays on
            Bach's craft, from the chorale tradition to the Well-Tempered Clavier.
          </p>

          <div className="flex justify-center">
            <Link
              to="/corpus"
              className="group inline-flex items-center gap-2 rounded-lg bg-primary px-8 py-3.5 text-sm font-medium text-paper-light shadow-[0_14px_32px_rgba(184,92,56,0.18)] transition-all hover:-translate-y-0.5 hover:bg-primary-dark no-underline"
            >
              <span aria-hidden="true">♩</span>
              Explore the Chorales
            </Link>
          </div>

          <StaffDivider className="mt-10" />
        </div>
      </section>

      <section className="relative -mt-8 max-w-6xl mx-auto px-6 z-10">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map(({ title, description, path, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              className="group relative block rounded-2xl border border-border bg-paper-light px-8 py-9 text-center shadow-[0_16px_40px_rgba(43,43,43,0.05)] transition-all duration-300 hover:-translate-y-1 hover:border-secondary hover:shadow-[0_20px_48px_rgba(201,168,76,0.14)] no-underline"
            >
              <CornerOrnaments />
              <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-primary/8 text-primary transition-colors group-hover:bg-primary/14">
                <Icon />
              </div>
              <h3 className="mb-2">{title}</h3>
              <p className="text-sm text-ink-muted leading-relaxed">{description}</p>
              <div className="mt-4 text-sm text-primary opacity-0 transition-opacity group-hover:opacity-100">
                Explore →
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-16 overflow-hidden">
        <div className="bg-charcoal py-5">
          <div className="score-marquee-track flex w-[1600px] gap-12 whitespace-nowrap">
            {Array.from({ length: 2 }).map((_, repetition) => (
              <svg key={repetition} viewBox="0 0 800 40" className="h-10 w-[800px] flex-shrink-0" preserveAspectRatio="xMidYMid meet">
                {[8, 14, 20, 26, 32].map((y) => (
                  <line key={y} x1="0" y1={y} x2="800" y2={y} stroke="var(--color-secondary)" strokeWidth="0.35" opacity="0.24" />
                ))}
                {Array.from({ length: 36 }).map((_, index) => {
                  const x = index * 22 + 8;
                  const voiceData = [
                    { y: 10 + Math.sin(index * 0.6 + repetition) * 4, color: 'var(--color-soprano)' },
                    { y: 17 + Math.sin(index * 0.7 + repetition + 1) * 3, color: 'var(--color-alto)' },
                    { y: 24 + Math.sin(index * 0.5 + repetition + 2) * 3, color: 'var(--color-tenor)' },
                    { y: 31 + Math.sin(index * 0.8 + repetition + 3) * 3, color: 'var(--color-bass)' },
                  ];
                  return (
                    <g key={index}>
                      {voiceData.map((voice, voiceIndex) => (
                        <rect key={voiceIndex} x={x} y={voice.y} width={16} height={2} rx={1} fill={voice.color} opacity={0.62} />
                      ))}
                    </g>
                  );
                })}
              </svg>
            ))}
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="grid grid-cols-1 md:grid-cols-[120px_minmax(0,1fr)] gap-8 items-start">
          <div className="hidden md:flex justify-center" aria-hidden="true">
            <svg viewBox="0 0 20 320" className="w-5 h-72">
              {[4, 7, 10, 13, 16].map((x) => (
                <line key={x} x1={x} y1="0" x2={x} y2="320" stroke="var(--color-secondary)" strokeWidth="0.3" opacity="0.4" />
              ))}
              {[28, 72, 116, 162, 208, 254].map((y, index) => (
                <g key={index}>
                  <ellipse cx={7 + (index % 3) * 3} cy={y} rx="2.4" ry="1.9" fill="var(--color-secondary)" opacity={0.22 + (index % 3) * 0.05} transform={`rotate(-15 ${7 + (index % 3) * 3} ${y})`} />
                  <line x1={9.4 + (index % 3) * 3} y1={y} x2={9.4 + (index % 3) * 3} y2={y - 12} stroke="var(--color-secondary)" strokeWidth="0.4" opacity={0.22 + (index % 3) * 0.05} />
                </g>
              ))}
            </svg>
          </div>

          <div>
            <SectionHeading className="mb-6">About BachBot</SectionHeading>
            <p className="text-ink-muted mb-5">
              BachBot reads scores directly. It marks Roman numerals, cadences, part-writing habits,
              and recurring progressions so you can move between notation and analysis without leaving the page.
              Composition tools let you harmonize melodies, realize figured bass, and study counterpoint.
            </p>
            <p className="text-ink-muted mb-8">
              The chorale corpus comes from the{' '}
              <a
                href="https://github.com/DCMLab/bach_chorales"
                className="text-primary hover:text-primary-dark"
                target="_blank"
                rel="noopener noreferrer"
              >
                DCML Bach Chorales
              </a>{' '}
              dataset. The encyclopedia links to free scores on{' '}
              <a
                href="https://imslp.org/wiki/Category:Bach,_Johann_Sebastian"
                className="text-primary hover:text-primary-dark"
                target="_blank"
                rel="noopener noreferrer"
              >
                IMSLP
              </a>
              .
            </p>

            <div className="rounded-2xl border border-border bg-paper-light px-6 py-6 shadow-[0_16px_40px_rgba(43,43,43,0.05)]">
              <div className="flex flex-wrap gap-8">
                {[
                  { value: '361', label: 'Chorales' },
                  { value: '~14k', label: 'Harmonic Events' },
                  { value: '4', label: 'Voices' },
                  { value: '1685–1750', label: 'Period' },
                ].map((stat) => (
                  <div key={stat.label} className="text-center min-w-20">
                    <div className="font-mono text-xl text-primary">{stat.value}</div>
                    <div className="text-[11px] uppercase tracking-[0.2em] text-ink-muted">{stat.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
