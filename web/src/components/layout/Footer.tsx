export function Footer() {
  return (
    <footer className="border-t border-border bg-paper-dark/50 mt-auto">
      <div className="max-w-[1400px] mx-auto px-6 py-8">
        <div className="flex flex-col md:flex-row justify-between items-start gap-6">
          <div>
            <h4 className="font-serif text-lg mb-2">BachBot</h4>
            <p className="text-sm text-ink-muted max-w-md">
              Deterministic, provenance-aware Bach research and composition platform.
              Every analytical claim is backed by corpus-level evidence.
            </p>
          </div>
          <div className="flex gap-8 text-sm text-ink-muted">
            <div>
              <h5 className="font-sans font-semibold text-ink-light mb-2">Corpus</h5>
              <p>361 DCML chorales</p>
              <p>15,594 Bach Digital works</p>
              <p>99 RISM sources</p>
            </div>
            <div>
              <h5 className="font-sans font-semibold text-ink-light mb-2">Engine</h5>
              <p>688 tests passing</p>
              <p>65 extracted features</p>
              <p>19 chord types</p>
            </div>
          </div>
        </div>
        <div className="mt-6 pt-4 border-t border-border text-xs text-ink-muted">
          Generated artifacts are truthfully labeled. This is a research tool, not a substitute for authentic Bach scores.
        </div>
      </div>
    </footer>
  );
}
