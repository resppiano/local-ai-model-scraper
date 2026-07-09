import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router";
import {
  Loader2,
  ArrowLeft,
  ExternalLink,
  Video,
  Film,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  listControlVideos,
  THEORETICALLY_POSE_URL,
  type ControlVideoOut,
} from "@/api/fable";

export default function ControlVideosPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = parseInt(id || "0");

  const [controlVideos, setControlVideos] = useState<ControlVideoOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTool, setShowTool] = useState(false);

  useEffect(() => {
    if (projectId) loadVideos();
  }, [projectId]);

  async function loadVideos() {
    setLoading(true);
    try {
      const vids = await listControlVideos(projectId);
      setControlVideos(vids);
    } catch {
      setControlVideos([]);
    } finally {
      setLoading(false);
    }
  }

  const tpUrl = `${THEORETICALLY_POSE_URL}?projectId=${projectId}`;

  if (showTool) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between mb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setShowTool(false);
              loadVideos();
            }}
          >
            <ArrowLeft className="w-4 h-4 mr-1.5" />
            Back to Control Videos
          </Button>
          <Badge variant="outline" className="text-xs">
            Project #{projectId}
          </Badge>
        </div>
        <div className="flex-1 min-h-0 rounded-xl overflow-hidden border border-border bg-black">
          <iframe
            src={tpUrl}
            className="w-full h-full"
            allow="clipboard-read; clipboard-write"
            title="TheoreticallyPose V4"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Control Videos
          </h1>
          <p className="text-muted-foreground mt-1">
            Process video clips into pose skeletons, depth maps, and silhouettes
            for AI video generation.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowTool(true)}>
          <Film className="w-4 h-4 mr-1.5" />
          Open TheoreticallyPose
        </Button>
      </div>

      {/* How it works card */}
      <div className="bg-card border border-border rounded-xl p-5 space-y-2">
        <h3 className="font-semibold text-sm">How it works</h3>
        <ol className="text-sm text-muted-foreground space-y-1 ml-4 list-decimal">
          <li>Click <strong>Open TheoreticallyPose</strong> to launch the pose/depth extraction tool</li>
          <li>Drag a video clip onto the tool and hit <strong>Track</strong> to extract skeletons</li>
          <li>Hit <strong>Bake</strong> in the Depth panel (optional)</li>
          <li>Click <strong>Export MP4</strong>, then <strong>Save to Fable</strong> to store as a project asset</li>
          <li>Assign control videos as "Driving Videos" on individual panels</li>
        </ol>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Everything runs locally in your browser. Nothing gets uploaded to external servers.
        </p>
      </div>

      {/* Control Videos list */}
      <div className="space-y-2">
        <h2 className="text-lg font-semibold">Saved Control Videos</h2>

        {loading ? (
          <div className="flex items-center gap-2 text-muted-foreground py-8">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading...
          </div>
        ) : controlVideos.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-border rounded-xl">
            <Video className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-muted-foreground">
              No control videos saved yet.
            </p>
            <p className="text-muted-foreground/50 text-sm mt-1">
              Process a video with TheoreticallyPose and click "Save to Fable" to see it here.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {controlVideos.map((cv) => (
              <div
                key={cv.asset.id}
                className="bg-card border border-border rounded-xl overflow-hidden group"
              >
                {/* Video preview */}
                <div className="aspect-video bg-muted relative">
                  <video
                    src={cv.asset.url}
                    className="w-full h-full object-contain bg-black"
                    controls
                    preload="metadata"
                  />
                </div>
                <div className="p-3 space-y-2">
                  <div className="flex items-center gap-1.5">
                    <Badge variant="outline" className="text-[10px]">
                      {cv.asset.type}
                    </Badge>
                    <Badge variant="secondary" className="text-[10px]">
                      Control Video
                    </Badge>
                  </div>
                  {cv.panel && (
                    <p className="text-xs text-muted-foreground">
                      Assigned to Panel #{cv.panel.panel_number}
                    </p>
                  )}
                  <div className="flex gap-1.5">
                    <a
                      href={cv.asset.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-primary hover:underline inline-flex items-center gap-1"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Open
                    </a>
                  </div>
                  <p className="text-[10px] text-muted-foreground/50">
                    {new Date(cv.asset.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
