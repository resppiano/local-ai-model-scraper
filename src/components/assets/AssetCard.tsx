import { Trash2, FileImage, FileVideo, FileAudio } from "lucide-react";
import type { Asset } from "@/api/fable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface AssetCardProps {
  asset: Asset;
  onDelete?: (assetId: number) => void;
}

const typeIcons = {
  image: FileImage,
  video: FileVideo,
  audio: FileAudio,
  thumbnail: FileImage,
};

const typeColors: Record<string, string> = {
  image: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  video: "bg-purple-500/10 text-purple-500 border-purple-500/20",
  audio: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  thumbnail: "bg-green-500/10 text-green-500 border-green-500/20",
};

export default function AssetCard({ asset, onDelete }: AssetCardProps) {
  const Icon = typeIcons[asset.type] || FileImage;

  const filename = asset.url?.split("/").pop() || `asset-${asset.id}`;
  const tags = asset.local_path?.split(",").map((t) => t.trim()).filter(Boolean) || [];

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden hover:shadow-md transition-all">
      {/* Thumbnail */}
      <div className="aspect-video bg-muted relative">
        {asset.type === "image" || asset.type === "thumbnail" ? (
          <img
            src={asset.url}
            alt={filename}
            className="w-full h-full object-cover"
          />
        ) : asset.type === "video" ? (
          <video src={asset.url} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Icon className="w-10 h-10 text-muted-foreground/30" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3 space-y-2">
        <div className="flex items-center gap-2">
          <Icon className="w-3.5 h-3.5 text-muted-foreground" />
          <p className="text-xs font-medium truncate flex-1" title={filename}>
            {filename}
          </p>
        </div>

        <div className="flex items-center gap-1">
          <Badge
            variant="outline"
            className={cn("text-[10px] px-1.5 py-0", typeColors[asset.type])}
          >
            {asset.type}
          </Badge>
          {asset.width && asset.height && (
            <span className="text-[10px] text-muted-foreground">
              {asset.width}×{asset.height}
            </span>
          )}
        </div>

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="text-[10px]">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {onDelete && (
          <Button
            size="sm"
            variant="ghost"
            className="w-full h-7 text-xs text-red-500 hover:text-red-600 hover:bg-red-500/10 gap-1"
            onClick={() => onDelete(asset.id)}
          >
            <Trash2 className="w-3 h-3" />
            Delete
          </Button>
        )}
      </div>
    </div>
  );
}

function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(" ");
}