export type Category = 'vision' | 'voice' | 'video';
export type Source = 'github' | 'huggingface';

export interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  description: string | null;
  html_url: string;
  stargazers_count: number;
  language: string | null;
  topics: string[];
  category: Category;
  license: string | null;
  forks_count: number;
}

export interface HFModel {
  id: string;
  modelId: string;
  likes: number;
  downloads: number;
  tags: string[];
  pipeline_tag: string;
  library_name: string;
  createdAt: string;
  category: Category;
}

export interface UnifiedModel {
  id: string;
  name: string;
  author: string;
  description: string;
  url: string;
  stars: number;
  downloads: number;
  language: string;
  tags: string[];
  category: Category;
  source: Source;
  license: string | null;
}
