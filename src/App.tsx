import { useState, useCallback, useMemo } from 'react';
import { Navbar } from '@/sections/Navbar';
import { Hero } from '@/sections/Hero';
import { StatsBar } from '@/sections/StatsBar';
import { ModelGrid } from '@/sections/ModelGrid';
import { Footer } from '@/sections/Footer';
import { useModels, useFilteredModels } from '@/hooks/useModels';
import type { Category } from '@/types';


export default function App() {
  const { models, githubModels, huggingfaceModels, loading, refresh } = useModels();

  const [activeCategories, setActiveCategories] = useState<Category[]>([]);
  const [activeTab, setActiveTab] = useState<Category | 'all'>('all');
  const [sourceFilter, setSourceFilter] = useState<'all' | 'github' | 'huggingface'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Sync hero pills with tab
  const effectiveCategory = useMemo<Category | 'all'>(() => {
    if (activeCategories.length === 1) return activeCategories[0];
    return activeTab;
  }, [activeCategories, activeTab]);

  const handleCategoryToggle = useCallback((cat: Category) => {
    setActiveCategories((prev) => {
      if (prev.includes(cat)) {
        const next = prev.filter((c) => c !== cat);
        // If unchecking the last active pill, reset tab to 'all'
        if (next.length === 0) setActiveTab('all');
        else if (next.length === 1) setActiveTab(next[0]);
        return next;
      }
      const next = [...prev, cat];
      if (next.length === 1) setActiveTab(next[0]);
      else setActiveTab('all');
      return next;
    });
  }, []);

  const handleTabChange = useCallback((tab: Category | 'all') => {
    setActiveTab(tab);
    if (tab === 'all') {
      setActiveCategories([]);
    } else {
      setActiveCategories([tab]);
    }
  }, []);

  const filteredModels = useFilteredModels(models, effectiveCategory, sourceFilter, searchQuery);

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <Navbar />
      <Hero
        activeCategories={activeCategories}
        onCategoryToggle={handleCategoryToggle}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />
      <StatsBar
        githubCount={githubModels.length}
        hfCount={huggingfaceModels.length}
        totalCount={models.length}
      />
      <ModelGrid
        models={filteredModels}
        loading={loading}
        onRefresh={refresh}
        activeTab={activeTab}
        onTabChange={handleTabChange}
        sourceFilter={sourceFilter}
        onSourceChange={setSourceFilter}
      />
      <Footer />
    </div>
  );
}
