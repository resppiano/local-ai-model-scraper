"""
Knowledge RAG Module
====================
Lightweight, zero-dependency RAG over the knowledge-bundle OKF directory.

Loads markdown files from cinematography/, storytelling/, and authors/ domains,
chunks by ## headings, embeds via Ollama's nomic-embed-text, and retrieves the
most relevant chunks for a query using pure-Python cosine similarity.

Usage:
    from .knowledge_rag import KnowledgeRAG
    rag = KnowledgeRAG()
    rag.refresh()               # (re-)embed all knowledge
    results = rag.query("low angle shot feeling", top_k=3)
    for r in results:
        print(r["content"])
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ── Paths ──────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
BUNDLE_ROOT = Path(os.environ.get(
    "KNOWLEDGE_BUNDLE_DIR",
    "/home/gregjones/knowledge-bundle",
))
CACHE_FILE = HERE / "rag_cache.json"

# Which subdirectories to index (relative to bundle root)
DOMAINS = ["cinematography", "storytelling", "authors"]

# Embedding config
EMBED_MODEL = "nomic-embed-text"
EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_DIM = 768
EMBED_TIMEOUT = 30

# ── Utilities ──────────────────────────────────────────────────────────────


def _get_embedding(text: str) -> Optional[List[float]]:
    """Call Ollama's /api/embeddings for a single text string."""
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    req = urllib.request.Request(
        EMBED_URL, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data.get("embedding")
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        print(f"[KnowledgeRAG] Embedding failed: {e}")
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Pure-Python cosine similarity (no numpy dependency)."""
    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = sum(ai * ai for ai in a) ** 0.5
    norm_b = sum(bi * bi for bi in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _find_markdown_files() -> List[Path]:
    """Find all .md files under the configured domains, excluding index.md."""
    files = []
    for domain in DOMAINS:
        domain_dir = BUNDLE_ROOT / domain
        if not domain_dir.exists():
            continue
        for f in sorted(domain_dir.rglob("*.md")):
            if f.name == "index.md":
                continue
            files.append(f)
    return files


def _chunk_markdown(file_path: Path) -> List[Dict]:
    """
    Split a markdown file into chunks by ## headings.
    Returns list of dicts with: domain, source, heading, content, tags.
    """
    text = file_path.read_text(encoding="utf-8", errors="replace")
    domain = file_path.parent.name

    # Parse frontmatter tags
    tags = []
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        t_match = re.search(r"tags:\s*\[([^\]]+)\]", fm)
        if t_match:
            tags = [t.strip() for t in t_match.group(1).split(",")]

    # Remove frontmatter for chunking
    body = text[fm_match.end():] if fm_match else text

    # Split by ## headings
    sections = re.split(r"\n(?=## )", body)
    chunks = []
    for sec in sections:
        lines = sec.strip().split("\n")
        heading = ""
        content_lines = []
        for line in lines:
            if line.startswith("## "):
                heading = line[3:].strip()
            elif line.startswith("# ") and not heading:
                heading = line[2:].strip()
            else:
                content_lines.append(line)
        content = "\n".join(content_lines).strip()
        if not content or len(content) < 30:
            continue

        chunks.append({
            "domain": domain,
            "source": str(file_path.relative_to(BUNDLE_ROOT)),
            "heading": heading,
            "content": content[:3000],  # cap chunk size
            "tags": tags,
            "full_path": str(file_path),
        })
    return chunks


# ── RAG Class ──────────────────────────────────────────────────────────────


class KnowledgeRAG:
    """
    Lightweight RAG engine over the Fable knowledge bundle.

    State:
        chunks: List[Dict]  — the indexed chunks (content + metadata)
        embeddings: List[Optional[List[float]]]  — parallel vectors
        loaded: bool
    """

    def __init__(self):
        self.chunks: List[Dict] = []
        self.embeddings: List[Optional[List[float]]] = []
        self.loaded = False
        self.domain_map: Dict[str, List[int]] = {}  # domain → chunk indices

    # ── Public API ──────────────────────────────────────────────────────

    def refresh(self, force: bool = False) -> str:
        """
        Load all markdown files, chunk them, and compute embeddings.

        Args:
            force: If True, re-embed all chunks even if cached.

        Returns:
            Summary string.
        """
        files = _find_markdown_files()
        all_chunks = []
        for f in files:
            all_chunks.extend(_chunk_markdown(f))

        self.chunks = all_chunks
        self.domain_map = {}
        for i, chunk in enumerate(self.chunks):
            dom = chunk["domain"]
            self.domain_map.setdefault(dom, []).append(i)

        # Try loading cached embeddings
        cache_hit = False
        if not force and CACHE_FILE.exists():
            try:
                cached = json.loads(CACHE_FILE.read_text())
                if (cached.get("version") == 1
                        and len(cached.get("embeddings", [])) == len(self.chunks)):
                    # Verify same sources
                    cached_sources = cached.get("sources", [])
                    current_sources = [c["source"] for c in self.chunks]
                    if cached_sources == current_sources:
                        self.embeddings = cached["embeddings"]
                        cache_hit = True
            except (json.JSONDecodeError, KeyError):
                pass

        if not cache_hit:
            self.embeddings = []
            total = len(self.chunks)
            for i, chunk in enumerate(self.chunks):
                text = f"{chunk['heading']}: {chunk['content']}"
                emb = _get_embedding(text)
                self.embeddings.append(emb)
                if (i + 1) % 5 == 0 or i == total - 1:
                    print(f"[KnowledgeRAG] Embedded {i+1}/{total}")
                if emb is None:
                    print(f"[KnowledgeRAG] WARNING: failed to embed chunk {i}: {chunk['source']} / {chunk['heading']}")

            # Cache to disk
            cache_data = {
                "version": 1,
                "sources": [c["source"] for c in self.chunks],
                "embeddings": self.embeddings,
                "headings": [c["heading"] for c in self.chunks],
            }
            CACHE_FILE.write_text(json.dumps(cache_data, indent=2))
            print(f"[KnowledgeRAG] Embeddings cached to {CACHE_FILE}")

        self.loaded = True

        # Summary
        domain_counts = {}
        for c in self.chunks:
            domain_counts[c["domain"]] = domain_counts.get(c["domain"], 0) + 1
        parts = [f"{d}: {n} chunks" for d, n in sorted(domain_counts.items())]
        return (f"KnowledgeRAG loaded: {', '.join(parts)} "
                f"({sum(domain_counts.values())} total, cache={'hit' if cache_hit else 'built'})")

    def query(
        self,
        query_text: str,
        top_k: int = 3,
        domain_filter: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Retrieve the top_k most relevant chunks for a query.

        Args:
            query_text: Natural language query.
            top_k: Number of chunks to return.
            domain_filter: Optional list of domains to restrict to.

        Returns:
            List of dicts with content + metadata + score.
        """
        if not self.loaded or not self.chunks:
            return [{"content": "KnowledgeRAG not loaded. Call .refresh() first.", "score": 0.0}]

        # Determine which chunk indices to search
        if domain_filter:
            indices = []
            for dom in domain_filter:
                indices.extend(self.domain_map.get(dom, []))
        else:
            indices = list(range(len(self.chunks)))

        if not indices:
            return []

        # Embed the query
        query_emb = _get_embedding(query_text)
        if query_emb is None:
            return [{"content": f"Failed to embed query: '{query_text}'", "score": 0.0}]

        # Score all relevant chunks
        scored: List[Tuple[float, int]] = []
        for idx in indices:
            emb = self.embeddings[idx]
            if emb is not None:
                sim = _cosine_similarity(query_emb, emb)
                scored.append((sim, idx))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Build results with deduplication
        results = []
        seen = set()
        for score, idx in scored[:top_k * 2]:  # pull extra to still fill top_k after dedup
            chunk = self.chunks[idx]
            dedup_key = f"{chunk['source']}|{chunk['heading']}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            results.append({
                "domain": chunk["domain"],
                "source": chunk["source"],
                "heading": chunk["heading"],
                "content": chunk["content"],
                "tags": chunk.get("tags", []),
                "score": round(score, 4),
            })
            if len(results) >= top_k:
                break

        return results

    def get_domains(self) -> List[str]:
        """Return the available domains from loaded chunks."""
        return sorted(self.domain_map.keys())

    def reset(self) -> None:
        """Clear loaded state (call refresh() after)."""
        self.chunks = []
        self.embeddings = []
        self.loaded = False
        self.domain_map = {}


# ── Module-level convenience ───────────────────────────────────────────────

_global_rag: Optional[KnowledgeRAG] = None


def get_rag() -> KnowledgeRAG:
    """Lazy singleton accessor."""
    global _global_rag
    if _global_rag is None:
        _global_rag = KnowledgeRAG()
    return _global_rag


def query_knowledge(
    query_text: str,
    top_k: int = 3,
    domain_filter: Optional[List[str]] = None,
    auto_refresh: bool = True,
) -> List[Dict]:
    """
    One-shot convenience: get RAG instance, refresh if needed, query.
    """
    rag = get_rag()
    if auto_refresh and not rag.loaded:
        rag.refresh()
    return rag.query(query_text, top_k=top_k, domain_filter=domain_filter)


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    rag = get_rag()
    status = rag.refresh()
    print(status)
    print()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        results = rag.query(query)
        for r in results:
            print(f"[{r['domain']}] {r['heading']}  (score: {r['score']})")
            print(f"  from: {r['source']}")
            print(f"  {r['content'][:200]}...")
            print()
    else:
        print("Usage: python3 knowledge_rag.py '<query>'")