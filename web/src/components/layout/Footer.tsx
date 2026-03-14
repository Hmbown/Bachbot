import { Link } from 'react-router-dom';

export function Footer() {
  return (
    <footer className="border-t border-border bg-paper-dark/50 mt-auto">
      <div className="max-w-[1400px] mx-auto px-6 py-6">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="text-sm text-ink-muted">
            <span className="font-serif font-semibold text-ink-light">BachBot</span>
            {' '}&mdash; 361 analyzed Bach chorales
          </div>
          <div className="flex gap-4 text-sm text-ink-muted">
            <Link to="/corpus" className="hover:text-ink no-underline">Chorales</Link>
            <Link to="/research" className="hover:text-ink no-underline">Research</Link>
            <Link to="/encyclopedia" className="hover:text-ink no-underline">Encyclopedia</Link>
            <a href="https://github.com/Hmbown/Bachbot" className="hover:text-ink no-underline" target="_blank" rel="noopener noreferrer">GitHub</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
