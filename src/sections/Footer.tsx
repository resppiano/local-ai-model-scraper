export function Footer() {
  return (
    <footer className="border-t border-[rgba(255,255,255,0.06)] px-6 py-8">
      <div className="mx-auto max-w-[1200px] text-center">
        <p
          className="text-xs text-[#44444d]"
          style={{ fontFamily: "'Geist Mono', monospace" }}
        >
          Built with React + Vite &middot; Data from GitHub API &amp; Hugging Face Hub &middot; Top 25 local AI models per platform
        </p>
      </div>
    </footer>
  );
}
