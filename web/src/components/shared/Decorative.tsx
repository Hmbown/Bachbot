import type { ReactNode } from 'react';

export function StaffDivider({ className = '' }: { className?: string }) {
  return (
    <div className={`w-full py-4 ${className}`} aria-hidden="true">
      <svg viewBox="0 0 800 24" className="w-full max-w-3xl mx-auto opacity-60" preserveAspectRatio="xMidYMid meet">
        {[2, 6, 10, 14, 18].map((y) => (
          <line key={y} x1="0" y1={y} x2="800" y2={y} stroke="var(--color-secondary)" strokeWidth="0.45" />
        ))}
        <text x="12" y="16" fontFamily="var(--font-serif)" fontSize="20" fill="var(--color-secondary)" opacity="0.7">
          &#119070;
        </text>
        <circle cx="120" cy="10" r="2.2" fill="var(--color-secondary)" opacity="0.35" />
        <line x1="122.2" y1="10" x2="122.2" y2="2" stroke="var(--color-secondary)" strokeWidth="0.5" opacity="0.35" />
        <circle cx="260" cy="14" r="2.2" fill="var(--color-secondary)" opacity="0.3" />
        <line x1="262.2" y1="14" x2="262.2" y2="6" stroke="var(--color-secondary)" strokeWidth="0.5" opacity="0.3" />
        <circle cx="420" cy="6" r="2.2" fill="var(--color-secondary)" opacity="0.35" />
        <line x1="422.2" y1="6" x2="422.2" y2="-2" stroke="var(--color-secondary)" strokeWidth="0.5" opacity="0.35" />
        <circle cx="580" cy="10" r="2.2" fill="var(--color-secondary)" opacity="0.25" />
        <line x1="582.2" y1="10" x2="582.2" y2="2" stroke="var(--color-secondary)" strokeWidth="0.5" opacity="0.25" />
        <line x1="780" y1="2" x2="780" y2="18" stroke="var(--color-secondary)" strokeWidth="0.5" opacity="0.3" />
        <line x1="784" y1="2" x2="784" y2="18" stroke="var(--color-secondary)" strokeWidth="1" opacity="0.45" />
      </svg>
    </div>
  );
}

export function BaroqueFlourish({ className = '' }: { className?: string }) {
  return (
    <div className={`flex justify-center ${className}`} aria-hidden="true">
      <svg viewBox="0 0 240 30" className="w-48 h-8" preserveAspectRatio="xMidYMid meet">
        <path d="M30,15 Q15,5 8,15 Q15,25 30,15" fill="none" stroke="var(--color-secondary)" strokeWidth="0.8" opacity="0.7" />
        <path d="M8,15 Q4,10 2,15 Q4,20 8,15" fill="var(--color-secondary)" opacity="0.4" />
        <path
          d="M35,15 C55,3 75,27 95,12 C105,6 110,20 120,15 C130,10 135,24 145,18 C165,3 185,27 205,15"
          fill="none"
          stroke="var(--color-secondary)"
          strokeWidth="1.2"
          strokeLinecap="round"
        />
        <path d="M116,15 L120,11 L124,15 L120,19 Z" fill="var(--color-secondary)" opacity="0.5" />
        <path d="M210,15 Q225,5 232,15 Q225,25 210,15" fill="none" stroke="var(--color-secondary)" strokeWidth="0.8" opacity="0.7" />
        <path d="M232,15 Q236,10 238,15 Q236,20 232,15" fill="var(--color-secondary)" opacity="0.4" />
      </svg>
    </div>
  );
}

function CornerGlyph() {
  return (
    <svg viewBox="0 0 28 28" className="w-6 h-6" fill="none" aria-hidden="true">
      <path d="M3,3 L3,14 C3,6 6,3 14,3" stroke="var(--color-secondary)" strokeWidth="0.8" opacity="0.5" />
      <path d="M3,3 L3,8 C3,4.5 4.5,3 8,3" stroke="var(--color-secondary)" strokeWidth="0.5" opacity="0.3" />
      <circle cx="3" cy="3" r="1.5" fill="var(--color-secondary)" opacity="0.3" />
    </svg>
  );
}

export function CornerOrnaments({ className = '' }: { className?: string }) {
  return (
    <>
      <div className={`pointer-events-none absolute top-2 left-2 ${className}`}><CornerGlyph /></div>
      <div className={`pointer-events-none absolute top-2 right-2 rotate-90 ${className}`}><CornerGlyph /></div>
      <div className={`pointer-events-none absolute bottom-2 left-2 -rotate-90 ${className}`}><CornerGlyph /></div>
      <div className={`pointer-events-none absolute bottom-2 right-2 rotate-180 ${className}`}><CornerGlyph /></div>
    </>
  );
}

export function TrebleClefWatermark() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-[48%] opacity-[0.04]">
        <svg viewBox="0 0 100 200" className="w-72 h-auto fill-current text-charcoal">
          <text x="50" y="130" textAnchor="middle" fontFamily="var(--font-serif)" fontSize="180">
            &#119070;
          </text>
        </svg>
      </div>
      {[
        { symbol: '♩', x: '14%', y: '18%', size: '2rem', delay: '0s' },
        { symbol: '♪', x: '78%', y: '28%', size: '1.4rem', delay: '1.2s' },
        { symbol: '♬', x: '72%', y: '70%', size: '1.8rem', delay: '2.8s' },
        { symbol: '𝄞', x: '22%', y: '74%', size: '2.4rem', delay: '0.6s' },
        { symbol: '♭', x: '10%', y: '52%', size: '1.6rem', delay: '3.2s' },
      ].map((note, index) => (
        <span
          key={index}
          className="decorative-note absolute text-charcoal opacity-[0.045] select-none"
          style={{ left: note.x, top: note.y, fontSize: note.size, animationDelay: note.delay }}
        >
          {note.symbol}
        </span>
      ))}
    </div>
  );
}

export function FloatingNotes({ count = 5 }: { count?: number }) {
  const notes = Array.from({ length: count }, (_, index) => ({
    symbol: ['♩', '♪', '♬', '♫', '♩'][index % 5],
    left: `${10 + (index * 78) / Math.max(count, 1)}%`,
    delay: `${index * 0.8}s`,
    duration: `${4.5 + (index % 3) * 1.1}s`,
  }));

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
      {notes.map((note, index) => (
        <span
          key={index}
          className="floating-note absolute bottom-0 text-secondary/55 select-none"
          style={{ left: note.left, animationDelay: note.delay, animationDuration: note.duration }}
        >
          {note.symbol}
        </span>
      ))}
    </div>
  );
}

export function SectionHeading({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`flex items-center gap-4 ${className}`}>
      <svg viewBox="0 0 50 14" className="w-10 h-4 flex-shrink-0" aria-hidden="true">
        <path d="M2,7 Q12,2 22,7 Q32,12 42,7" fill="none" stroke="var(--color-secondary)" strokeWidth="0.8" />
        <circle cx="48" cy="7" r="1.5" fill="var(--color-secondary)" opacity="0.45" />
        <circle cx="1" cy="7" r="1" fill="var(--color-secondary)" opacity="0.3" />
      </svg>
      <h2 className="mb-0">{children}</h2>
      <svg viewBox="0 0 50 14" className="w-10 h-4 flex-shrink-0" aria-hidden="true">
        <path d="M8,7 Q18,12 28,7 Q38,2 48,7" fill="none" stroke="var(--color-secondary)" strokeWidth="0.8" />
        <circle cx="2" cy="7" r="1.5" fill="var(--color-secondary)" opacity="0.45" />
        <circle cx="49" cy="7" r="1" fill="var(--color-secondary)" opacity="0.3" />
      </svg>
    </div>
  );
}
