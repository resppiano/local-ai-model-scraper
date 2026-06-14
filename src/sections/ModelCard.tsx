import { motion } from 'framer-motion';
import { Star, Download, Code2, ExternalLink } from 'lucide-react';
import type { UnifiedModel, Category, Source } from '@/types';

interface ModelCardProps {
  model: UnifiedModel;
  index: number;
}

const categoryConfig: Record<Category, { bg: string; color: string; border: string; label: string }> = {
  vision: {
    bg: 'rgba(0,168,255,0.15)',
    color: '#4db8ff',
    border: 'rgba(0,168,255,0.3)',
    label: 'VISION',
  },
  voice: {
    bg: 'rgba(0,208,132,0.15)',
    color: '#00d084',
    border: 'rgba(0,208,132,0.3)',
    label: 'VOICE',
  },
  video: {
    bg: 'rgba(255,170,0,0.15)',
    color: '#ffaa00',
    border: 'rgba(255,170,0,0.3)',
    label: 'VIDEO',
  },
};

const sourceConfig: Record<Source, { bg: string; color: string; border: string; label: string }> = {
  github: {
    bg: 'rgba(139,92,246,0.15)',
    color: '#b388ff',
    border: 'rgba(139,92,246,0.3)',
    label: 'GITHUB',
  },
  huggingface: {
    bg: 'rgba(255,171,0,0.15)',
    color: '#ffcc44',
    border: 'rgba(255,171,0,0.3)',
    label: 'HUGGING FACE',
  },
};

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toString();
}

export function ModelCard({ model, index }: ModelCardProps) {
  const cat = categoryConfig[model.category];
  const src = sourceConfig[model.source];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05, ease: 'easeOut' }}
      layout
    >
      <a
        href={model.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group block rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#111118] p-5 transition-all duration-250 hover:-translate-y-0.5 hover:border-[rgba(0,208,132,0.3)] hover:shadow-[0_8px_32px_rgba(0,208,132,0.08)]"
      >
        {/* Badges Row */}
        <div className="mb-3 flex flex-wrap gap-2">
          <span
            className="inline-block rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider"
            style={{
              fontFamily: "'Geist Mono', monospace",
              background: src.bg,
              color: src.color,
              border: `1px solid ${src.border}`,
            }}
          >
            {src.label}
          </span>
          <span
            className="inline-block rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider"
            style={{
              fontFamily: "'Geist Mono', monospace",
              background: cat.bg,
              color: cat.color,
              border: `1px solid ${cat.border}`,
            }}
          >
            {cat.label}
          </span>
          <ExternalLink className="ml-auto h-3.5 w-3.5 text-[#44444d] opacity-0 transition-opacity group-hover:opacity-100" />
        </div>

        {/* Name */}
        <h3
          className="truncate text-[15px] font-medium text-[#e8e8ec]"
          style={{ fontFamily: "'Geist', sans-serif" }}
        >
          {model.name}
        </h3>

        {/* Author */}
        <p
          className="mt-0.5 truncate text-xs text-[#44444d]"
          style={{ fontFamily: "'Geist Mono', monospace" }}
        >
          @{model.author}
        </p>

        {/* Description */}
        <p
          className="mt-2 line-clamp-2 text-[13px] leading-[1.5] text-[#6b6b78]"
          style={{ fontFamily: "'Geist', sans-serif" }}
        >
          {model.description}
        </p>

        {/* Stats Row */}
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1 text-xs text-[#6b6b78]" style={{ fontFamily: "'Geist Mono', monospace" }}>
            <Star className="h-3 w-3" />
            <span className="text-[#e8e8ec]">{formatCount(model.stars)}</span>
          </div>
          <div className="flex items-center gap-1 text-xs text-[#6b6b78]" style={{ fontFamily: "'Geist Mono', monospace" }}>
            <Download className="h-3 w-3" />
            <span className="text-[#e8e8ec]">{formatCount(model.downloads)}</span>
          </div>
          {model.language && (
            <div className="flex items-center gap-1 text-xs text-[#44444d]" style={{ fontFamily: "'Geist Mono', monospace" }}>
              <Code2 className="h-3 w-3" />
              <span>{model.language}</span>
            </div>
          )}
        </div>

        {/* Tags Row */}
        {model.tags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {model.tags.slice(0, 4).map((tag) => (
              <span
                key={tag}
                className="rounded px-2 py-0.5 text-[10px] uppercase tracking-wide text-[#44444d]"
                style={{
                  fontFamily: "'Geist Mono', monospace",
                  background: 'rgba(255,255,255,0.04)',
                }}
              >
                {tag.length > 20 ? tag.slice(0, 20) + '...' : tag}
              </span>
            ))}
          </div>
        )}
      </a>
    </motion.div>
  );
}
