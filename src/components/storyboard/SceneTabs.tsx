import { cn } from "@/lib/utils";

interface SceneTabsProps {
  scenes: { id: number; scene_number: number; heading: string }[];
  activeSceneId: number | null;
  onSelect: (sceneId: number) => void;
}

export default function SceneTabs({ scenes, activeSceneId, onSelect }: SceneTabsProps) {
  const sorted = [...scenes].sort((a, b) => a.scene_number - b.scene_number);
  return (
    <div className="flex gap-1 overflow-x-auto pb-1">
      {sorted.map((scene) => (
        <button
          key={scene.id}
          onClick={() => onSelect(scene.id)}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-lg border whitespace-nowrap transition-colors",
            scene.id === activeSceneId
              ? "bg-primary text-primary-foreground border-primary"
              : "bg-card text-muted-foreground border-border hover:bg-accent hover:text-accent-foreground"
          )}
        >
          {scene.heading || `Scene ${scene.scene_number}`}
        </button>
      ))}
    </div>
  );
}