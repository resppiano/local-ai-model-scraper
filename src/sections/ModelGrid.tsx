import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw, SearchX, Github, Database } from 'lucide-react';
import type { UnifiedModel, Category } from '@/types';
import { ModelCard } from './ModelCard';

interface ModelGridProps {
  models: UnifiedModel[];
  loading: boolean;
  onRefresh: () => void;
  activeTab: Category | 'all';
  onTabChange: (tab: Category | 'all') => void;
  sourceFilter: 'all' | 'github' | 'huggingface';
  onSourceChange: (s: 'all' | 'github' | 'huggingface') => void;
}

const tabs: { key: Category | 'all'; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'vision', label: 'Vision' },
  { key: 'voice', label: 'Voice' },
  { key: 'video', label: 'Video' },
];

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#111118] p-5">
      <div className="mb-3 flex gap-2">
        <div className="h-5 w-16 animate-shimmer rounded" />
        <div className="h-5 w-14 animate-shimmer rounded" />
      </div>
      <div className="mb-1 h-4 w-3/4 animate-shimmer rounded" />
      <div className="mb-2 h-3 w-1/2 animate-shimmer rounded" />
      <div className="mb-1 h-3 w-full animate-shimmer rounded" />
      <div className="mb-3 h-3 w-2/3 animate-shimmer rounded" />
      <div className="mb-1 flex gap-4">
        <div className="h-3 w-12 animate-shimmer rounded" />
        <div className="h-3 w-12 animate-shimmer rounded" />
      </div>
    </div>
  );
}

export function ModelGrid({
  models,
  loading,
  onRefresh,
  activeTab,
  onTabChange,
  sourceFilter,
  onSourceChange,
}: ModelGridProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await onRefresh();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  return (
    <section className="px-6 pb-12">
      <div className="mx-auto max-w-[1200px]">
        {/* Category Tabs */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => onTabChange(tab.key)}
                className="relative px-6 py-3 text-[13px] font-medium uppercase tracking-wide transition-colors"
                style={{ fontFamily: "'Geist Mono', monospace" }}
              >
                {activeTab === tab.key && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#00d084]"
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  />
                )}
                <span className={activeTab === tab.key ? 'text-[#00d084]' : 'text-[#6b6b78] hover:text-[#e8e8ec]'}>
                  {tab.label}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Source Toggle + Refresh */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-1 rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#111118] p-1">
            <button
              onClick={() => onSourceChange('all')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors ${
                sourceFilter === 'all'
                  ? 'bg-[rgba(0,208,132,0.15)] text-[#00d084]'
                  : 'text-[#6b6b78] hover:text-[#e8e8ec]'
              }`}
              style={{ fontFamily: "'Geist Mono', monospace" }}
            >
              <LayersIcon className="h-3 w-3" />
              All
            </button>
            <button
              onClick={() => onSourceChange('github')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors ${
                sourceFilter === 'github'
                  ? 'bg-[rgba(0,208,132,0.15)] text-[#00d084]'
                  : 'text-[#6b6b78] hover:text-[#e8e8ec]'
              }`}
              style={{ fontFamily: "'Geist Mono', monospace" }}
            >
              <Github className="h-3 w-3" />
              GitHub
            </button>
            <button
              onClick={() => onSourceChange('huggingface')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors ${
                sourceFilter === 'huggingface'
                  ? 'bg-[rgba(0,208,132,0.15)] text-[#00d084]'
                  : 'text-[#6b6b78] hover:text-[#e8e8ec]'
              }`}
              style={{ fontFamily: "'Geist Mono', monospace" }}
            >
              <Database className="h-3 w-3" />
              Hugging Face
            </button>
          </div>

          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#111118] px-4 py-2 text-xs text-[#6b6b78] transition-colors hover:text-[#e8e8ec] disabled:opacity-50"
            style={{ fontFamily: "'Geist Mono', monospace" }}
          >
            <RefreshCw className={`h-3 w-3 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Results Count */}
        <div
          className="mb-4 text-xs text-[#44444d]"
          style={{ fontFamily: "'Geist Mono', monospace" }}
        >
          {loading ? 'Loading models...' : `Showing ${models.length} model${models.length !== 1 ? 's' : ''}`}
        </div>

        {/* Grid */}
        {loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : models.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-20"
          >
            <SearchX className="mb-4 h-12 w-12 text-[#44444d]" />
            <p className="text-base text-[#6b6b78]" style={{ fontFamily: "'Geist', sans-serif" }}>
              No models found matching your criteria
            </p>
            <p className="mt-1 text-sm text-[#44444d]" style={{ fontFamily: "'Geist', sans-serif" }}>
              Try adjusting your filters
            </p>
          </motion.div>
        ) : (
          <AnimatePresence mode="popLayout">
            <motion.div
              key={activeTab + sourceFilter}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
            >
              {models.map((model, i) => (
                <ModelCard key={model.id} model={model} index={i} />
              ))}
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </section>
  );
}

function LayersIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  );
}
