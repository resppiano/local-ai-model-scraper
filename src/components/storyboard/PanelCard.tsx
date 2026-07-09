import { useState } from "react";
import { Camera, Sparkles, GripVertical } from "lucide-react";
import type { Panel } from "@/api/fable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import PreviewThumbnail from "./PreviewThumbnail";

interface PanelCardProps {
  panel: Panel;
  characters?: { id: number; name: string; reference_image_url: string | null }[];
  onGenerate: (panelId: number) => void;
  onClick: (panel: Panel) => void;
  isDragOver?: boolean;
}

const statusColors: Record<string, string> = {
  draft: "bg-gray-500",
  queued: "bg-blue-500",
  rendering: "bg-yellow-500",
  done: "bg-green-500",
  failed: "bg-red-500",
};

export default function PanelCard({ panel, characters = [], onGenerate, onClick, isDragOver }: PanelCardProps) {
  const [generating, setGenerating] = useState(false);
  const assignedChars = characters.filter((c) => panel.character_ids?.includes(c.id));

  const handleGenerate = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setGenerating(true);
    try {
      await onGenerate(panel.id);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div
      onClick={() => onClick(panel)}
      className={cn(
        "w-[280px] bg-card border border-border rounded-xl p-3 space-y-2 cursor-pointer transition-all hover:shadow-md",
        isDragOver && "border-primary ring-2 ring-primary/30",
        panel.status === "done" ? "bg-card" : "bg-muted/50"
      )}
    >
      {/* Preview */}
      <div className="aspect-[16/9] rounded-lg overflow-hidden bg-muted">
        <PreviewThumbnail src={panel.preview_url} status={panel.status} />
      </div>

      {/* Panel number + type badge */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-muted-foreground">
          #{panel.panel_number}
        </span>
        {panel.panel_type && (
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
            {panel.panel_type}
          </Badge>
        )}
      </div>

      {/* Character chips */}
      {assignedChars.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {assignedChars.map((ch) => (
            <div
              key={ch.id}
              className="flex items-center gap-1 text-[10px] bg-muted rounded-full px-1.5 py-0.5"
              title={ch.name}
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
              <span className="truncate max-w-[50px]">{ch.name}</span>
            </div>
          ))}
        </div>
      )}

      {/* Camera direction badge */}
      {panel.camera_direction && (
        <Badge variant="secondary" className="text-[10px]">
          <Camera className="w-3 h-3 mr-1" />
          {panel.camera_direction.replace("_", " ")}
        </Badge>
      )}

      {/* Status + Generate */}
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              statusColors[panel.status] || "bg-gray-400"
            )}
          />
          <span className="text-[10px] text-muted-foreground capitalize">{panel.status}</span>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={handleGenerate}
          disabled={generating || panel.status === "queued" || panel.status === "rendering"}
          className="h-7 text-xs gap-1"
        >
          <Sparkles className={cn("w-3 h-3", generating && "animate-spin")} />
          Generate
        </Button>
      </div>
    </div>
  );
}