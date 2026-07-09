import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadDropzoneProps {
  onUpload: (file: File) => Promise<void>;
  accept?: Record<string, string[]>;
  maxSize?: number;
  className?: string;
}

export default function UploadDropzone({
  onUpload,
  accept,
  maxSize = 10 * 1024 * 1024, // 10MB default
  className,
}: UploadDropzoneProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;
      setUploading(true);
      setProgress(0);
      try {
        // Simulate progress
        const interval = setInterval(() => {
          setProgress((p) => Math.min(p + 20, 90));
        }, 300);
        await onUpload(file);
        clearInterval(interval);
        setProgress(100);
      } catch (e) {
        console.error("Upload failed", e);
      } finally {
        setUploading(false);
        setProgress(0);
      }
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    maxSize,
    multiple: false,
    disabled: uploading,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
        isDragActive
          ? "border-primary bg-primary/5"
          : "border-border hover:border-muted-foreground/30 hover:bg-accent/50",
        uploading && "pointer-events-none opacity-70",
        className
      )}
    >
      <input {...getInputProps()} />
      {uploading ? (
        <div className="space-y-3">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" />
          <p className="text-sm text-muted-foreground">Uploading...</p>
          {progress > 0 && (
            <div className="w-full max-w-xs mx-auto h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300 rounded-full"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <Upload className="w-8 h-8 mx-auto text-muted-foreground/50" />
          {isDragActive ? (
            <p className="text-sm font-medium text-primary">Drop file here...</p>
          ) : (
            <>
              <p className="text-sm font-medium">
                Drag & drop a file here, or click to browse
              </p>
              <p className="text-xs text-muted-foreground">
                Images, videos, audio — up to {Math.round(maxSize / 1024 / 1024)}MB
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}