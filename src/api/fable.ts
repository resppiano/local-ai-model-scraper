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
export const updateCharacter = (projectId: number, characterId: number, data: Partial<CharacterCreate>) =>
  api<Character>(`/projects/${projectId}/characters/${characterId}`, { method: "PATCH", body: JSON.stringify(data) });
export const deleteCharacter = (projectId: number, characterId: number) =>
  api<void>(`/projects/${projectId}/characters/${characterId}`, { method: "DELETE" });

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

export const deleteAsset = (projectId: number, assetId: number) =>
  api<void>(`/projects/${projectId}/assets/${assetId}`, { method: "DELETE" });

// ── Upload ──────────────────────────────────────────────────────────────
export const uploadFile = (projectId: number, file: File, fileType?: string): Promise<{ url: string; asset: Asset }> => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("project_id", String(projectId));
  if (fileType) formData.append("file_type", fileType);
  return fetch(`${API_URL}/upload`, {
    method: "POST",
    body: formData,
  }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
    return r.json();
  });
};

// ── Script & Scene ──────────────────────────────────────────────────────
export interface Script {
  id: number;
  project_id: number;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
  scenes?: Scene[];
}

export interface ScriptCreate {
  title: string;
  content?: string;
}

export interface Scene {
  id: number;
  script_id: number;
  scene_number: number;
  heading: string;
  location: string | null;
  time_of_day: string | null;
  summary: string | null;
  content: string | null;
  panels?: Panel[];
  created_at: string;
}

export const listScripts = (projectId: number) =>
  api<Script[]>(`/projects/${projectId}/scripts`);
export const createScript = (projectId: number, data: ScriptCreate) =>
  api<Script>(`/projects/${projectId}/scripts`, { method: "POST", body: JSON.stringify(data) });
export const getScript = (projectId: number, scriptId: number) =>
  api<Script>(`/projects/${projectId}/scripts/${scriptId}`);
export const getScriptWithScenes = (projectId: number, scriptId: number) =>
  api<Script & { scenes: Scene[] }>(`/projects/${projectId}/scripts/${scriptId}`);
export const updateScript = (projectId: number, scriptId: number, data: Partial<ScriptCreate>) =>
  api<Script>(`/projects/${projectId}/scripts/${scriptId}`, { method: "PATCH", body: JSON.stringify(data) });
export const deleteScript = (projectId: number, scriptId: number) =>
  api<void>(`/projects/${projectId}/scripts/${scriptId}`, { method: "DELETE" });
export const breakdownScript = (projectId: number, scriptId: number) =>
  api<{ scenes_parsed: number; scenes: Scene[] }>(`/projects/${projectId}/scripts/${scriptId}/breakdown`, { method: "POST" });
export const autoPrompts = (projectId: number, scriptId: number) =>
  api<{ message: string; panels_updated: number }>(`/projects/${projectId}/scripts/${scriptId}/auto-prompts`, { method: "POST" });
export const updateScene = (sceneId: number, data: Partial<Scene>) =>
  api<Scene>(`/scenes/${sceneId}`, { method: "PATCH", body: JSON.stringify(data) });

// ── Panels (Storyboard) ─────────────────────────────────────────────────
export interface Panel {
  id: number;
  scene_id: number;
  panel_number: number;
  description: string | null;
  auto_prompt: string | null;
  override_prompt: string | null;
  camera_direction: string | null;
  panel_type: string | null;
  status: string;
  assigned_character_ids: string | null;
  assigned_asset_ids: string | null;
  driving_video_asset_id: number | null;
  thumbnail_url: string | null;
  output_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface PanelCreate {
  panel_number?: number;
  description?: string;
  panel_type?: string;
  camera_direction?: string;
}

export const createPanel = (sceneId: number, data: PanelCreate) =>
  api<Panel>(`/scenes/${sceneId}/panels`, { method: "POST", body: JSON.stringify(data) });
export const updatePanel = (panelId: number, data: Partial<Panel>) =>
  api<Panel>(`/panels/${panelId}`, { method: "PATCH", body: JSON.stringify(data) });
export const deletePanel = (panelId: number) =>
  api<void>(`/panels/${panelId}`, { method: "DELETE" });
export const generatePanel = (panelId: number) =>
  api<{ message: string; panel_id: number; render_job_id: number; status: string }>(`/panels/${panelId}/generate`, { method: "POST" });
export const generateAllPanels = (sceneId: number) =>
  api<{ message: string; panels_queued: number; total_panels: number }>(`/scenes/${sceneId}/generate-all`, { method: "POST" });

// ── Control Videos (TheoreticallyPose) ────────────────────────────────────
export interface ControlVideoOut {
  asset: Asset;
  panel: Panel | null;
}

export const listControlVideos = (projectId: number, panelId?: number) => {
  let path = `/projects/${projectId}/control-videos`;
  if (panelId) path += `?panel_id=${panelId}`;
  return api<ControlVideoOut[]>(path);
};

export const setPanelDrivingVideo = (panelId: number, assetId: number) =>
  api<{ status: string; panel_id: number; driving_video_asset_id: number }>(
    `/panels/${panelId}/driving-video`,
    { method: "POST", body: new URLSearchParams({ asset_id: String(assetId) }) }
  );

export const removePanelDrivingVideo = (panelId: number) =>
  api<{ status: string; panel_id: number; driving_video_asset_id: null }>(
    `/panels/${panelId}/driving-video`,
    { method: "DELETE" }
  );

export const THEORETICALLY_POSE_URL = `${API_URL.replace("/api/v1", "")}/theoreticallypose/v4`;

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