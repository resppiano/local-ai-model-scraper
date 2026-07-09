import { Camera } from "lucide-react";
import { cn } from "@/lib/utils";

interface PreviewThumbnailProps {
  src?: string | null;
  alt?: string;
  status?: string;
  className?: string;
}

export default function PreviewThumbnail({ src, alt = "", status, className }: PreviewThumbnailProps) {
  if (src) {
    return (
      <img
        src={src}
        alt={alt}
        className={cn("w-full h-full object-cover rounded-md", className)}
      />
    );
  }

  const isGenerating = status === "queued" || status === "rendering";

  return (
    <div
      className={cn(
        "w-full h-full flex items-center justify-center rounded-md bg-muted",
        isGenerating && "animate-pulse",
        className
      )}
    >
      <Camera className="w-8 h-8 text-muted-foreground/40" />
    </div>
  );
}