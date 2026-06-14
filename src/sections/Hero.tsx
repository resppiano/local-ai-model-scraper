import { Search } from 'lucide-react';
import type { Category } from '@/types';

interface HeroProps {
  activeCategories: Category[];
  onCategoryToggle: (cat: Category) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
}

const categoryConfig: { key: Category; label: string }[] = [
  { key: 'vision', label: 'VISION' },
  { key: 'voice', label: 'VOICE' },
  { key: 'video', label: 'VIDEO' },
];

export function Hero({ activeCategories, onCategoryToggle, searchQuery, onSearchChange }: HeroProps) {
  return (
    <section className="pt-24 pb-12 px-6">
      <div className="mx-auto max-w-[1200px]">
        <h1
          className="text-[32px] font-medium leading-[1.1] tracking-[-0.02em] text-[#e8e8ec] sm:text-[48px]"
          style={{ fontFamily: "'Geist', sans-serif" }}
        >
          Scrape The Top 25 Local AI Models
        </h1>
        <p className="mt-4 max-w-[600px] text-base text-[#6b6b78] sm:text-lg" style={{ fontFamily: "'Geist', sans-serif" }}>
          From GitHub and HuggingFace — Vision, Voice & Video models you can run locally
        </p>

        <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="flex flex-wrap gap-2">
            {categoryConfig.map(({ key, label }) => {
              const isActive = activeCategories.includes(key);
              return (
                <button
                  key={key}
                  onClick={() => onCategoryToggle(key)}
                  className={`
                    rounded-full px-5 py-2 text-[11px] font-medium uppercase tracking-wide
                    transition-all duration-200
                    ${
                      isActive
                        ? 'border border-[#00d084] bg-[rgba(0,208,132,0.15)] text-[#00d084]'
                        : 'border border-[rgba(255,255,255,0.06)] bg-transparent text-[#6b6b78] hover:border-[rgba(255,255,255,0.12)]'
                    }
                  `}
                  style={{ fontFamily: "'Geist Mono', monospace" }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          <div className="relative flex-1 sm:max-w-[360px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#44444d]" />
            <input
              type="text"
              placeholder="Search models..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#111118] py-2.5 pl-10 pr-4 text-sm text-[#e8e8ec] placeholder:text-[#44444d] focus:border-[#00d084] focus:outline-none focus:ring-[3px] focus:ring-[rgba(0,208,132,0.1)]"
              style={{ fontFamily: "'Geist', sans-serif" }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
