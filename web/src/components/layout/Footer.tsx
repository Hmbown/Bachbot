import { Link } from 'react-router-dom';
import { BaroqueFlourish } from '@/components/shared/Decorative';

export function Footer() {
  return (
    <footer className="mt-auto border-t border-[#3a3530] bg-charcoal text-[#9E9891]">
      <div className="max-w-[1400px] mx-auto px-6 py-10">
        <BaroqueFlourish className="mb-5" />
        <div className="flex justify-center gap-3 mb-4" aria-hidden="true">
          {['♩', '♪', '♬', '♫', '♩'].map((note, index) => (
            <span key={index} className="text-secondary/25 text-sm select-none">{note}</span>
          ))}
        </div>
        <div className="text-center mb-6">
          <p className="font-serif text-lg text-secondary">BachBot — chorales, counterpoint, and the craft of J. S. Bach</p>
          <p className="text-xs text-[#6B6560] mt-2">361 chorales from the DCML corpus, composition tools, and essays on Bach's music.</p>
        </div>
        <div className="flex flex-wrap justify-center gap-5 text-sm">
          <Link to="/corpus" className="hover:text-secondary no-underline">Chorales</Link>
          <Link to="/compose" className="hover:text-secondary no-underline">Compose</Link>
          <Link to="/theory" className="hover:text-secondary no-underline">Theory</Link>
          <Link to="/research" className="hover:text-secondary no-underline">Research</Link>
          <Link to="/encyclopedia" className="hover:text-secondary no-underline">Encyclopedia</Link>
          <Link to="/api-docs" className="hover:text-secondary no-underline">API</Link>
          <a href="https://github.com/Hmbown/Bachbot" className="hover:text-secondary no-underline" target="_blank" rel="noopener noreferrer">GitHub</a>
        </div>
        <div className="mt-6 text-center text-xs text-[#6B6560]">
          Scores on{' '}
          <a href="https://imslp.org/wiki/Category:Bach,_Johann_Sebastian" className="hover:text-secondary" target="_blank" rel="noopener noreferrer">IMSLP</a>
          {' '}· Corpus from{' '}
          <a href="https://github.com/DCMLab/bach_chorales" className="hover:text-secondary" target="_blank" rel="noopener noreferrer">DCML</a>
        </div>
      </div>
    </footer>
  );
}
