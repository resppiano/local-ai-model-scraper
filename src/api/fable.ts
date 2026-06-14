/**
 * Fable API Client
 * ================
 * Talks to the FastAPI backend at localhost:8001
 */

const API_URL = import.meta.env.VITE_FABLE_API_URL || "http://localhost:8001";

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  }
  return resp.json() as Promise<T>;
}

// ── Projects ────────────────────────────────────────────────────────────
export interface Project {
  id: number;
  title: string;
  logline: string | null;
  vision: string | null;
  tone: string | null;
  genre: string | null;
  format: string | null;
  target_length: string | null;
  audience: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  shot_count: number;
  asset_count: number;
}

export interface ProjectCreate {
  title: string;
  logline?: string;
  vision?: string;
  tone?: string;
  genre?: string;
  format?: string;
  target_length?: string;
  audience?: string;
}

export const listProjects = () => api<Project[]>("/projects");
export const createProject = (data: ProjectCreate) =>
  api<Project>("/projects", { method: "POST", body: JSON.stringify(data) });

// ── Shots ───────────────────────────────────────────────────────────────
export interface Shot {
  id: number;
  project_id: number;
  scene_number: number;
  shot_number: number;
  description: string | null;
  prompt: string | null;
  negative_prompt: string | null;
  motion_prompt: string | null;
  shot_type: string | null;
  duration: number | null;
  status: string;
  render_provider: string | null;
  render_model: string | null;
  character_id: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  assets: Asset[];
}

export interface ShotCreate {
  scene_number?: number;
  shot_number?: number;
  description?: string;
  prompt?: string;
  negative_prompt?: string;
  motion_prompt?: string;
  shot_type?: string;
  duration?: number;
  character_id?: number;
  notes?: string;
}

export const listShots = (projectId: number) =>
  api<Shot[]>(`/projects/${projectId}/shots`);
export const createShot = (projectId: number, data: ShotCreate) =>
  api<Shot>(`/projects/${projectId}/shots`, { method: "POST", body: JSON.stringify(data) });

// ── Characters ──────────────────────────────────────────────────────────
export interface Character {
  id: number;
  project_id: number;
  name: string;
  description: string | null;
  reference_image_url: string | null;
  created_at: string;
}

export interface CharacterCreate {
  name: string;
  description?: string;
  reference_image_url?: string;
}

export const listCharacters = (projectId: number) =>
  api<Character[]>(`/projects/${projectId}/characters`);
export const createCharacter = (projectId: number, data: CharacterCreate) =>
  api<Character>(`/projects/${projectId}/characters`, { method: "POST", body: JSON.stringify(data) });

// ── Assets ──────────────────────────────────────────────────────────────
export interface Asset {
  id: number;
  project_id: number;
  shot_id: number | null;
  type: "image" | "video" | "audio" | "thumbnail";
  url: string;
  local_path: string | null;
  provider: string | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  created_at: string;
}

export const listAssets = (projectId: number, type?: string) => {
  let path = `/projects/${projectId}/assets`;
  if (type) path += `?type=${type}`;
  return api<Asset[]>(path);
};

// ── Render ──────────────────────────────────────────────────────────────
export interface RenderJob {
  job_id: number;
  shot_id: number;
  provider: string;
  status: string;
  external_job_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export const queueRender = (shotId: number, provider: "comfyui" | "higgsfield", model?: string) =>
  api<RenderJob>("/render", {
    method: "POST",
    body: JSON.stringify({ shot_id: shotId, provider, model }),
  });

export const getRenderStatus = (jobId: number) =>
  api<RenderJob>(`/render/${jobId}`);

// ── Dashboard ───────────────────────────────────────────────────────────
export interface DashboardStats {
  total_projects: number;
  active_projects: number;
  total_shots: number;
  shots_rendered: number;
  total_assets: number;
  recent_assets: Asset[];
}

export const getDashboard = () => api<DashboardStats>("/dashboard/stats");
