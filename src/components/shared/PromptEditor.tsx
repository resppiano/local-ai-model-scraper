import { useState } from "react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface PromptEditorProps {
  autoPrompt: string;
  overridden?: boolean;
  value?: string;
  onChange?: (value: string) => void;
  onToggleOverride?: (override: boolean) => void;
  readOnly?: boolean;
  className?: string;
}

export default function PromptEditor({
  autoPrompt,
  overridden = false,
  value,
  onChange,
  onToggleOverride,
  readOnly = false,
  className,
}: PromptEditorProps) {
  const [localOverride, setLocalOverride] = useState(overridden);

  const handleToggle = (checked: boolean) => {
    setLocalOverride(checked);
    onToggleOverride?.(checked);
  };

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">Prompt</Label>
        {!readOnly && (
          <div className="flex items-center gap-2">
            <Label htmlFor="override-toggle" className="text-xs text-muted-foreground cursor-pointer">
              Override
            </Label>
            <Switch
              id="override-toggle"
              checked={localOverride}
              onCheckedChange={handleToggle}
            />
          </div>
        )}
      </div>

      {localOverride ? (
        <Textarea
          value={value ?? autoPrompt}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder="Enter your custom prompt..."
          rows={4}
          className="w-full resize-y"
          readOnly={readOnly}
        />
      ) : (
        <div className="w-full rounded-md border border-input bg-muted/30 px-3 py-2 text-sm text-muted-foreground min-h-[80px] whitespace-pre-wrap">
          {autoPrompt || "No auto-generated prompt available."}
        </div>
      )}

      {localOverride && (
        <p className="text-[10px] text-muted-foreground">
          Custom prompt will be used instead of the auto-generated one.
        </p>
      )}
    </div>
  );
}