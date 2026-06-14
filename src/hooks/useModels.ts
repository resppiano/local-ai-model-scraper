import { useState, useEffect, useCallback, useMemo } from 'react';
import type { UnifiedModel, Category, HFModel } from '@/types';
import { githubRepos } from '@/data/githubRepos';

function unifyGitHubRepos(): UnifiedModel[] {
  return githubRepos.map((repo) => ({
    id: `gh-${repo.id}`,
    name: repo.name,
    author: repo.full_name.split('/')[0],
    description: repo.description || '',
    url: repo.html_url,
    stars: repo.stargazers_count,
    downloads: repo.forks_count,
    language: repo.language || 'N/A',
    tags: repo.topics.slice(0, 6),
    category: repo.category,
    source: 'github' as const,
    license: repo.license,
  }));
}

function unifyHFModels(models: HFModel[]): UnifiedModel[] {
  return models.map((model) => ({
    id: `hf-${model.id}`,
    name: model.modelId.split('/').pop() || model.modelId,
    author: model.modelId.split('/')[0],
    description: model.pipeline_tag || model.tags[0] || 'Hugging Face Model',
    url: `https://huggingface.co/${model.modelId}`,
    stars: model.likes,
    downloads: model.downloads,
    language: model.library_name || 'transformers',
    tags: model.tags.filter(t => !['transformers', 'safetensors', 'pytorch', 'region:us', 'endpoints_compatible'].includes(t)).slice(0, 6),
    category: model.category,
    source: 'huggingface' as const,
    license: model.tags.find(t => t.startsWith('license:'))?.replace('license:', '') || null,
  }));
}

const HF_ENDPOINTS: { category: Category; url: string }[] = [
  {
    category: 'vision',
    url: 'https://huggingface.co/api/models?sort=downloads&direction=-1&limit=25&search=vision',
  },
  {
    category: 'voice',
    url: 'https://huggingface.co/api/models?sort=downloads&direction=-1&limit=25&search=voice',
  },
  {
    category: 'video',
    url: 'https://huggingface.co/api/models?sort=downloads&direction=-1&limit=25&search=video',
  },
];

async function fetchHFModels(): Promise<HFModel[]> {
  const results: HFModel[] = [];

  for (const { category, url } of HF_ENDPOINTS) {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as HFModel[];
      results.push(...data.map((m) => ({ ...m, category })));
    } catch (err) {
      console.warn(`Failed to fetch ${category} models from HF:`, err);
    }
  }

  return results;
}

export function useModels() {
  const [hfModels, setHfModels] = useState<HFModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const githubModels = useMemo(() => unifyGitHubRepos(), []);
  const huggingfaceModels = useMemo(() => unifyHFModels(hfModels), [hfModels]);

  const allModels = useMemo(() => {
    const combined = [...githubModels, ...huggingfaceModels];
    // Sort by stars/downloads descending
    return combined.sort((a, b) => b.stars - a.stars);
  }, [githubModels, huggingfaceModels]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const models = await fetchHFModels();
      setHfModels(models);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch models');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    models: allModels,
    githubModels,
    huggingfaceModels,
    loading,
    error,
    refresh,
  };
}

export function useFilteredModels(
  models: UnifiedModel[],
  category: Category | 'all',
  source: 'all' | 'github' | 'huggingface',
  searchQuery: string
) {
  return useMemo(() => {
    let filtered = models;

    if (category !== 'all') {
      filtered = filtered.filter((m) => m.category === category);
    }

    if (source !== 'all') {
      filtered = filtered.filter((m) => m.source === source);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (m) =>
          m.name.toLowerCase().includes(q) ||
          m.description.toLowerCase().includes(q) ||
          m.author.toLowerCase().includes(q) ||
          m.tags.some((t) => t.toLowerCase().includes(q))
      );
    }

    return filtered;
  }, [models, category, source, searchQuery]);
}
