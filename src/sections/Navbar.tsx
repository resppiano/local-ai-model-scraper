import { Terminal, Github } from 'lucide-react';

export function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-14 border-b border-[rgba(255,255,255,0.06)] bg-[#1a1a24]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-full max-w-[1200px] items-center justify-between px-6">
        <div className="flex items-center gap-2.5">
          <Terminal className="h-5 w-5 text-[#00d084]" />
          <span className="text-sm font-semibold tracking-[0.1em] text-[#e8e8ec]" style={{ fontFamily: "'Geist Mono', monospace" }}>
            LOCAL AI SCRAPER
          </span>
        </div>
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs tracking-wide text-[#00d084] transition-opacity hover:opacity-80"
          style={{ fontFamily: "'Geist Mono', monospace" }}
        >
          <Github className="h-3.5 w-3.5" />
          View on GitHub
        </a>
      </div>
    </nav>
  );
}
