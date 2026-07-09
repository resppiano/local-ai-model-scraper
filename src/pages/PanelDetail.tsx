import { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  Sparkles,
  Save,
  Trash2,
  X,
  Search,
  Film,
  Video,
  Trash,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  updatePanel,
  deletePanel,
  generatePanel,
  listAssets,
  listControlVideos,
  setPanelDrivingVideo,
  removePanelDrivingVideo,
  THEORETICALLY_POSE_URL,
  type Panel,
  type Character,
  type Asset,
  type ControlVideoOut,
} from "@/api/fable";
import PreviewThumbnail from "@/components/storyboard/PreviewThumbnail";
import CameraSelector from "@/components/shared/CameraSelector";
import PromptEditor from "@/components/shared/PromptEditor";

interface PanelDetailProps {
  panel: Panel;
  projectId: number;
  characters: Character[];
  onUpdated: (panel: Panel) => void;
  onDeleted: (panelId: number) => void;
  onClose: () => void;
}

function parseIds(ids: string | null): number[] {
  if (!ids) return [];
  try { return JSON.parse(ids); } catch { return []; }
}

export default function PanelDetail({
  panel,
  projectId,
  characters,
  onUpdated,
  onDeleted,
  onClose,
}: PanelDetailProps) {
  const [panelData, setPanelData] = useState<Panel>(panel);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [charSearch, setCharSearch] = useState("");
  const [assetSearch, setAssetSearch] = useState("");
  const [controlVideos, setControlVideos] = useState<ControlVideoOut[]>([]);
  const [showTPTool, setShowTPTool] = useState(false);
  const [tpDriverAssetId, setTpDriverAssetId] = useState<number | null>(null);

  const drivingVideo = controlVideos.find(
    (cv) => cv.asset.id === panelData.driving_video_asset_id
  );

  const assignedCharIds = parseIds(panelData.assigned_character_ids);
  const assignedAssetIds = parseIds(panelData.assigned_asset_ids);

  useEffect(() => {
    setPanelData(panel);
    loadAssets();
  }, [panel.id]);

  useEffect(() => {
    if (projectId) loadControlVideos();
  }, [projectId, panelData.id]);

  // Listen for TheoreticallyPose save events from popup
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (
        event.data?.type === "theoreticallypose:exported" &&
        event.data.panelId === panelData.id
      ) {
        // A control video was saved for this panel — refresh
        loadControlVideos();
        // Auto-link it as the driving video
        setPanelDrivingVideo(panelData.id, event.data.assetId).then(() => {
          setPanelData((prev) => ({
            ...prev,
            driving_video_asset_id: event.data.assetId,
          }));
        });
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [panelData.id, projectId]);

  async function loadAssets() {
    try {
      const a = await listAssets(projectId);
      setAssets(a);
    } catch {
      setAssets([]);
    }
  }

  async function loadControlVideos() {
    try {
      const cv = await listControlVideos(projectId, panelData.id);
      setControlVideos(cv);
    } catch {}
  }

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updatePanel(panelData.id, {
        description: panelData.description,
        camera_direction: panelData.camera_direction,
        panel_type: panelData.panel_type,
        assigned_character_ids: JSON.stringify(assignedCharIds),
        assigned_asset_ids: JSON.stringify(assignedAssetIds),
        override_prompt: null,
      });
      setPanelData(updated);
      onUpdated(updated);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      const result = await generatePanel(panelData.id);
      // Reload panel from parent via callback
      onUpdated({ ...panelData, status: "queued" });
    } catch (e) {
      console.error(e);
    } finally {
      setGenerating(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this panel?")) return;
    try {
      await deletePanel(panelData.id);
      onDeleted(panelData.id);
    } catch (e) {
      console.error(e);
    }
  }

  function toggleCharacter(charId: number) {
    const ids = assignedCharIds.includes(charId)
      ? assignedCharIds.filter((id) => id !== charId)
      : [...assignedCharIds, charId];
    setPanelData((prev) => ({ ...prev, assigned_character_ids: JSON.stringify(ids) }));
  }

  function toggleAsset(assetId: number) {
    const ids = assignedAssetIds.includes(assetId)
      ? assignedAssetIds.filter((id) => id !== assetId)
      : [...assignedAssetIds, assetId];
    setPanelData((prev) => ({ ...prev, assigned_asset_ids: JSON.stringify(ids) }));
  }

  const filteredChars = characters.filter(
    (c) =>
      c.name.toLowerCase().includes(charSearch.toLowerCase()) || charSearch === ""
  );
  const filteredAssets = assets.filter(
    (a) =>
      a.url?.toLowerCase().includes(assetSearch.toLowerCase()) || assetSearch === ""
  );

  const assignedChars = characters.filter((c) =>
    assignedCharIds.includes(c.id)
  );
  const assignedAssetList = assets.filter((a) =>
    assignedAssetIds.includes(a.id)
  );

  return (
    <Sheet open onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-[600px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>
            Panel #{panelData.panel_number}
            {panelData.panel_type && (
              <Badge variant="outline" className="ml-2">
                {panelData.panel_type}
              </Badge>
            )}
          </SheetTitle>
          <SheetDescription>
            Configure this panel's details, characters, and assets.
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6 mt-6">
          {/* Preview */}
          <div className="aspect-video rounded-lg overflow-hidden bg-muted">
            <PreviewThumbnail src={panelData.thumbnail_url || undefined} status={panelData.status} />
          </div>

          {/* Status indicator */}
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                panelData.status === "done"
                  ? "bg-green-500"
                  : panelData.status === "failed"
                  ? "bg-red-500"
                  : panelData.status === "rendering"
                  ? "bg-yellow-500"
                  : panelData.status === "queued"
                  ? "bg-blue-500"
                  : "bg-gray-400"
              }`}
            />
            <span className="text-sm font-medium capitalize">{panelData.status}</span>
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Description</label>
            <Textarea
              value={panelData.description || ""}
              onChange={(e) =>
                setPanelData((prev) => ({ ...prev, description: e.target.value }))
              }
              placeholder="Describe this panel..."
              rows={3}
              className="resize-y"
            />
          </div>

          {/* Panel type */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Panel Type</label>
            <Select
              value={panelData.panel_type || "wide"}
              onValueChange={(value) =>
                setPanelData((prev) => ({ ...prev, panel_type: value }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="wide">Wide</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="closeup">Close-up</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Camera direction */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Camera Direction</label>
            <CameraSelector
              value={panelData.camera_direction || "static"}
              onChange={(value) =>
                setPanelData((prev) => ({ ...prev, camera_direction: value }))
              }
            />
          </div>

          {/* Character assigner */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Characters</label>
            {assignedChars.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {assignedChars.map((ch) => (
                  <Badge
                    key={ch.id}
                    variant="secondary"
                    className="flex items-center gap-1 pr-1 cursor-pointer"
                    onClick={() => toggleCharacter(ch.id)}
                  >
                    {ch.reference_image_url ? (
                      <img
                        src={ch.reference_image_url}
                        alt=""
                        className="w-4 h-4 rounded-full object-cover"
                      />
                    ) : (
                      <div className="w-4 h-4 rounded-full bg-primary/20 flex items-center justify-center text-[8px] font-bold text-primary">
                        {ch.name[0]}
                      </div>
                    )}
                    {ch.name}
                    <X className="w-3 h-3 ml-1" />
                  </Badge>
                ))}
              </div>
            )}
            <Input
              value={charSearch}
              onChange={(e) => setCharSearch(e.target.value)}
              placeholder="Search characters..."
              className="text-sm"
            />
            <div className="max-h-[120px] overflow-y-auto space-y-1 border border-border rounded-lg p-2">
              {filteredChars.map((ch) => (
                <button
                  key={ch.id}
                  onClick={() => toggleCharacter(ch.id)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-left transition-colors ${
                    assignedCharIds.includes(ch.id)
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-accent"
                  }`}
                >
                  {ch.reference_image_url ? (
                    <img
                      src={ch.reference_image_url}
                      alt=""
                      className="w-6 h-6 rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-bold text-muted-foreground">
                      {ch.name[0]}
                    </div>
                  )}
                  {ch.name}
                </button>
              ))}
              {filteredChars.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-2">
                  No characters found
                </p>
              )}
            </div>
          </div>

          {/* Asset assigner */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Assets</label>
            {assignedAssetList.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {assignedAssetList.map((a) => (
                  <Badge
                    key={a.id}
                    variant="outline"
                    className="flex items-center gap-1 pr-1 cursor-pointer"
                    onClick={() => toggleAsset(a.id)}
                  >
                    {a.url?.split("/").pop() || `Asset ${a.id}`}
                    <X className="w-3 h-3 ml-1" />
                  </Badge>
                ))}
              </div>
            )}
            <Input
              value={assetSearch}
              onChange={(e) => setAssetSearch(e.target.value)}
              placeholder="Search assets..."
              className="text-sm"
            />
            <div className="max-h-[120px] overflow-y-auto space-y-1 border border-border rounded-lg p-2">
              {filteredAssets.map((a) => (
                <button
                  key={a.id}
                  onClick={() => toggleAsset(a.id)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-left transition-colors ${
                    assignedAssetIds.includes(a.id)
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-accent"
                  }`}
                >
                  {a.type === "image" || a.type === "thumbnail" ? (
                    <img
                      src={a.url}
                      alt=""
                      className="w-8 h-6 rounded object-cover"
                    />
                  ) : (
                    <div className="w-8 h-6 rounded bg-muted flex items-center justify-center text-[8px] text-muted-foreground">
                      {a.type}
                    </div>
                  )}
                  <span className="truncate">
                    {a.url?.split("/").pop() || `Asset ${a.id}`}
                  </span>
                </button>
              ))}
              {filteredAssets.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-2">
                  No assets found
                </p>
              )}
            </div>
          </div>

          {/* Driving Video (TheoreticallyPose) */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Driving Video</label>
            <p className="text-xs text-muted-foreground/70">
              A control video (pose skeleton, depth, silhouettes) extracted from a reference clip —
              used as motion guidance during generation.
            </p>

            {drivingVideo ? (
              <div className="bg-card border border-border rounded-lg p-3 space-y-2">
                <div className="aspect-video rounded overflow-hidden bg-black">
                  <video
                    src={drivingVideo.asset.url}
                    className="w-full h-full object-contain"
                    controls
                    preload="metadata"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Badge variant="secondary" className="text-[10px]">
                    Control Video #{drivingVideo.asset.id}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive h-7 text-xs"
                    onClick={async () => {
                      try {
                        await removePanelDrivingVideo(panelData.id);
                        setPanelData((prev) => ({
                          ...prev,
                          driving_video_asset_id: null,
                        }));
                        loadControlVideos();
                      } catch {}
                    }}
                  >
                    <Trash className="w-3 h-3 mr-1" />
                    Remove
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {/* Existing control videos that can be linked */}
                {controlVideos.length > 0 && (
                  <div className="max-h-[140px] overflow-y-auto space-y-1 border border-border rounded-lg p-2">
                    {controlVideos.map((cv) => (
                      <button
                        key={cv.asset.id}
                        onClick={async () => {
                          try {
                            await setPanelDrivingVideo(
                              panelData.id,
                              cv.asset.id
                            );
                            setPanelData((prev) => ({
                              ...prev,
                              driving_video_asset_id: cv.asset.id,
                            }));
                            loadControlVideos();
                          } catch {}
                        }}
                        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-left hover:bg-accent transition-colors"
                      >
                        <Video className="w-4 h-4 text-muted-foreground flex-none" />
                        <span className="truncate">
                          Control Video #{cv.asset.id}
                        </span>
                        <Badge
                          variant="outline"
                          className="text-[10px] ml-auto flex-none"
                        >
                          {new Date(
                            cv.asset.created_at
                          ).toLocaleDateString()}
                        </Badge>
                      </button>
                    ))}
                  </div>
                )}

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs flex-1"
                    onClick={() => {
                      const w = window.open(
                        `${THEORETICALLY_POSE_URL}?projectId=${projectId}&panelId=${panelData.id}`,
                        "theoreticallypose",
                        "width=1400,height=900"
                      );
                    }}
                  >
                    <Film className="w-3.5 h-3.5 mr-1.5" />
                    Open TheoreticallyPose
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Prompt editor */}
          <div className="space-y-1.5">
            <PromptEditor
              autoPrompt={panelData.auto_prompt || ""}
              overridden={!!panelData.override_prompt}
              value={panelData.override_prompt || ""}
              onChange={(v) =>
                setPanelData((prev) => ({ ...prev, override_prompt: v || null }))
              }
              onToggleOverride={(override) => {
                if (!override) {
                  setPanelData((prev) => ({ ...prev, override_prompt: null }));
                }
              }}
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between pt-4 border-t border-border">
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
            >
              <Trash2 className="w-3.5 h-3.5 mr-1.5" />
              Delete
            </Button>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                ) : (
                  <Save className="w-3.5 h-3.5 mr-1.5" />
                )}
                Save Draft
              </Button>
              <Button
                size="sm"
                onClick={handleGenerate}
                disabled={generating || panelData.status === "queued" || panelData.status === "rendering"}
              >
                {generating ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                )}
                Generate
              </Button>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}