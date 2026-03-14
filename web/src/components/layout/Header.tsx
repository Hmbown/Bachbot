import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';

const NAV_ITEMS = [
  { path: '/corpus', label: 'Chorales' },
  { path: '/research', label: 'Research' },
  { path: '/encyclopedia', label: 'Encyclopedia' },
  { path: '/api-docs', label: 'API' },
];

export function Header() {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-primary-dark focus:text-white focus:rounded-lg focus:text-sm"
      >
        Skip to content
      </a>

      <header className="border-b border-border bg-surface-warm/80 backdrop-blur-sm sticky top-0 z-50" role="banner">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-16">
            <Link to="/" className="flex items-center gap-3 no-underline" aria-label="BachBot Home">
              <div className="w-8 h-8 rounded bg-primary-dark flex items-center justify-center">
                <span className="text-white font-serif font-bold text-sm" aria-hidden="true">B</span>
              </div>
              <span className="font-serif font-semibold text-xl text-ink tracking-tight">
                BachBot
              </span>
            </Link>

            <nav className="hidden lg:flex items-center gap-1" aria-label="Main navigation">
              {NAV_ITEMS.map(({ path, label }) => {
                const isActive = location.pathname.startsWith(path);
                return (
                  <Link
                    key={path}
                    to={path}
                    className={`px-3 py-2 text-sm rounded-md transition-colors no-underline ${
                      isActive
                        ? 'bg-primary/10 text-primary-dark font-medium'
                        : 'text-ink-light hover:text-ink hover:bg-paper-dark/50'
                    }`}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {label}
                  </Link>
                );
              })}
            </nav>

            <button
              className="lg:hidden p-2 text-ink-light hover:text-ink rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
              aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                {mobileOpen ? (
                  <path d="M5 5l10 10M15 5L5 15" />
                ) : (
                  <path d="M3 5h14M3 10h14M3 15h14" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {mobileOpen && (
          <>
            <div
              className="fixed inset-0 bg-ink/20 z-40 lg:hidden"
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />
            <nav
              className="fixed top-0 right-0 w-72 h-full bg-surface border-l border-border z-50 lg:hidden shadow-xl"
              aria-label="Mobile navigation"
            >
              <div className="flex items-center justify-between px-4 h-16 border-b border-border">
                <span className="font-serif font-semibold text-lg text-ink">Menu</span>
                <button
                  onClick={() => setMobileOpen(false)}
                  className="p-2 text-ink-light hover:text-ink rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
                  aria-label="Close menu"
                >
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M5 5l10 10M15 5L5 15" />
                  </svg>
                </button>
              </div>
              <div className="py-4 px-2">
                {NAV_ITEMS.map(({ path, label }) => {
                  const isActive = location.pathname.startsWith(path);
                  return (
                    <Link
                      key={path}
                      to={path}
                      className={`block px-4 py-3 text-sm rounded-lg transition-colors no-underline mb-1 ${
                        isActive
                          ? 'bg-primary/10 text-primary-dark font-medium'
                          : 'text-ink-light hover:text-ink hover:bg-paper-dark/50'
                      }`}
                      aria-current={isActive ? 'page' : undefined}
                    >
                      {label}
                    </Link>
                  );
                })}
              </div>
            </nav>
          </>
        )}
      </header>
    </>
  );
}
