import { useEffect, useState, useCallback } from "react";
import { useParams, useSearchParams } from "react-router";
import {
  Loader2,
  Plus,
  Sparkles,
  PanelRightOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DndContext, type DragEndEvent, DragOverlay, useDroppable } from "@dnd-kit/core";
import {
  getScriptWithScenes,
  createPanel,
  generatePanel,
  generateAllPanels,
  listCharacters,
  type Scene,
  type Panel,
  type Character,
} from "@/api/fable";
import SceneTabs from "@/components/storyboard/SceneTabs";
import PanelCard from "@/components/storyboard/PanelCard";
import CharacterCard from "@/components/characters/CharacterCard";
import PanelDetail from "./PanelDetail";

export default function StoryboardPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const projectId = parseInt(id || "0");
  const initialSceneId = searchParams.get("scene")
    ? parseInt(searchParams.get("scene")!)
    : null;

  const [scenes, setScenes] = useState<Scene[]>([]);
  const [activeSceneId, setActiveSceneId] = useState<number | null>(initialSceneId);
  const [panels, setPanels] = useState<Panel[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [selectedPanel, setSelectedPanel] = useState<Panel | null>(null);
  const [draggedChar, setDraggedChar] = useState<Character | null>(null);

  useEffect(() => {
    loadAll();
  }, [projectId]);

  useEffect(() => {
    if (activeSceneId) {
      loadPanels(activeSceneId);
    } else if (scenes.length > 0) {
      setActiveSceneId(scenes[0].id);
    }
  }, [activeSceneId, scenes]);

  async function loadAll() {
    setLoading(true);
    try {
      const chars = await listCharacters(projectId);
      setCharacters(chars);

      // Get scenes through scripts
      try {
        const { listScripts } = await import("@/api/fable");
        const scripts = await listScripts(projectId);
        if (scripts.length > 0) {
          const sceneResults = await Promise.all(
            scripts.map((s) =>
              getScriptWithScenes(projectId, s.id)
                .then((script) => script.scenes || [])
                .catch(() => [] as Scene[])
            )
          );
          const finalScenes = sceneResults.flat();
          setScenes(finalScenes);
          if (finalScenes.length > 0) {
            const target = activeSceneId || initialSceneId || finalScenes[0].id;
            setActiveSceneId(target);
          }
        }
      } catch {}
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function loadPanels(sceneId: number) {
    // Panels are loaded from scenes via getScriptWithScenes
    // For now, find the scene and use its panels
    const scene = scenes.find((s) => s.id === sceneId);
    if (scene && (scene as any).panels) {
      setPanels((scene as any).panels);
    } else {
      setPanels([]);
    }
  }

  async function handleAddPanel() {
    if (!activeSceneId) return;
    try {
      const newPanel = await createPanel(projectId, {
        scene_id: activeSceneId,
        panel_number: panels.length + 1,
      });
      setPanels((prev) => [...prev, newPanel]);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleGenerate(panelId: number) {
    try {
      const updated = await generatePanel(projectId, panelId);
      setPanels((prev) => prev.map((p) => (p.id === panelId ? updated : p)));
    } catch (e) {
      console.error(e);
    }
  }

  async function handleGenerateAll() {
    if (!activeSceneId) return;
    setGeneratingAll(true);
    try {
      const result = await generateAllPanels(projectId, activeSceneId);
      setPanels(result.panels);
    } catch (e) {
      console.error(e);
    } finally {
      setGeneratingAll(false);
    }
  }

  function handleDragStart(event: DragEndEvent) {
    const data = event.active?.data?.current?.character;
    if (data) setDraggedChar(data);
  }

  function handleDragEnd(event: DragEndEvent) {
    setDraggedChar(null);
    const { active, over } = event;
    if (!over || !activeSceneId) return;
    const charId = active.data?.current?.character?.id;
    if (!charId) return;
    // If dropped on a panel, assign character
    const targetPanelId = over.data?.current?.panelId;
    if (targetPanelId) {
      setPanels((prev) =>
        prev.map((p) => {
          if (p.id === targetPanelId) {
            const ids = p.character_ids || [];
            if (!ids.includes(charId)) {
              return { ...p, character_ids: [...ids, charId] };
            }
          }
          return p;
        })
      );
    }
  }

  function handlePanelUpdated(updated: Panel) {
    setPanels((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  }

  function handlePanelDeleted(panelId: number) {
    setPanels((prev) => prev.filter((p) => p.id !== panelId));
    setSelectedPanel(null);
  }

  const activeScene = scenes.find((s) => s.id === activeSceneId);
  const sortedPanels = [...panels].sort((a, b) => a.panel_number - b.panel_number);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-8">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading...
      </div>
    );
  }

  return (
    <DndContext
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Storyboard</h1>
            <p className="text-muted-foreground mt-1">
              {activeScene
                ? `${activeScene.heading || `Scene ${activeScene.scene_number}`}`
                : "Arrange your visual narrative."}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleAddPanel}
              disabled={!activeSceneId}
            >
              <Plus className="w-4 h-4 mr-1.5" /> Add Panel
            </Button>
            <Button
              size="sm"
              onClick={handleGenerateAll}
              disabled={generatingAll || !activeSceneId || panels.length === 0}
            >
              {generatingAll ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
              ) : (
                <Sparkles className="w-4 h-4 mr-1.5" />
              )}
              Batch Generate All
            </Button>
          </div>
        </div>

        {/* Scene tabs */}
        <SceneTabs
          scenes={scenes}
          activeSceneId={activeSceneId}
          onSelect={(sceneId) => {
            setActiveSceneId(sceneId);
            setPanels([]);
            loadPanels(sceneId);
          }}
        />

        {/* Characters sidebar (for drag) */}
        {characters.length > 0 && (
          <div className="flex flex-wrap gap-2 items-center pb-2">
            <span className="text-xs text-muted-foreground font-medium">
              Drag characters onto panels:
            </span>
            {characters.map((ch) => (
              <div
                key={ch.id}
                className="flex items-center gap-1 text-xs bg-muted rounded-full px-2 py-1 cursor-grab active:cursor-grabbing border border-border"
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData("text/plain", String(ch.id));
                  e.dataTransfer.effectAllowed = "copy";
                }}
              >
                {ch.reference_image_url ? (
                  <img
                    src={ch.reference_image_url}
                    alt=""
                    className="w-5 h-5 rounded-full object-cover"
                  />
                ) : (
                  <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-[8px] font-bold text-primary">
                    {ch.name[0]}
                  </div>
                )}
                <span>{ch.name}</span>
              </div>
            ))}
          </div>
        )}

        {/* Panel grid */}
        {!activeSceneId ? (
          <div className="text-center py-16 border border-dashed border-border rounded-xl">
            <PanelRightOpen className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-muted-foreground">Select a scene to view storyboard panels.</p>
            <p className="text-muted-foreground/50 text-sm mt-1">
              Go to the Script page to parse scenes from your screenplay.
            </p>
          </div>
        ) : panels.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-border rounded-xl">
            <PanelRightOpen className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-muted-foreground">No panels yet for this scene.</p>
            <p className="text-muted-foreground/50 text-sm mt-1">
              Add panels to start storyboarding.
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-4">
            {sortedPanels.map((panel) => (
              <DroppablePanel key={panel.id} panel={panel}>
                <PanelCard
                  panel={panel}
                  characters={characters}
                  onGenerate={handleGenerate}
                  onClick={(p) => setSelectedPanel(p)}
                />
              </DroppablePanel>
            ))}
          </div>
        )}

        {/* Drag overlay */}
        <DragOverlay>
          {draggedChar ? (
            <div className="w-[200px] bg-card border border-primary rounded-xl p-4 shadow-lg">
              <div className="w-full aspect-square rounded-lg overflow-hidden bg-muted mb-2">
                {draggedChar.reference_image_url ? (
                  <img
                    src={draggedChar.reference_image_url}
                    alt={draggedChar.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-3xl font-bold text-muted-foreground/30">
                    {draggedChar.name[0]?.toUpperCase() || "?"}
                  </div>
                )}
              </div>
              <p className="font-semibold text-sm text-center">{draggedChar.name}</p>
            </div>
          ) : null}
        </DragOverlay>
      </div>

      {/* Panel Detail modal */}
      {selectedPanel && (
        <PanelDetail
          panel={selectedPanel}
          projectId={projectId}
          characters={characters}
          onUpdated={handlePanelUpdated}
          onDeleted={handlePanelDeleted}
          onClose={() => setSelectedPanel(null)}
        />
      )}
    </DndContext>
  );
}

// Droppable wrapper for panel cards
function DroppablePanel({
  panel,
  children,
}: {
  panel: Panel;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `panel-${panel.id}`,
    data: { panelId: panel.id },
  });

  return (
    <div ref={setNodeRef} className={isOver ? "opacity-80" : ""}>
      {children}
    </div>
  );
}