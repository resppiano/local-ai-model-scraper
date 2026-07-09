import { useEffect, useState } from "react";
import { useParams, Link } from "react-router";
import { Loader2, FileText, Wand2, ChevronDown, ChevronRight, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  listScripts,
  createScript,
  getScriptWithScenes,
  updateScript,
  breakdownScript,
  updateScene,
  type Script,
  type Scene,
} from "@/api/fable";

export default function ScriptPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || "0");

  const [scripts, setScripts] = useState<Script[]>([]);
  const [activeScript, setActiveScript] = useState<Script | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [loading, setLoading] = useState(true);
  const [scriptContent, setScriptContent] = useState("");
  const [scriptTitle, setScriptTitle] = useState("Untitled Script");
  const [breaking, setBreaking] = useState(false);
  const [expandedScenes, setExpandedScenes] = useState<Record<number, boolean>>({});
  const [savingScene, setSavingScene] = useState<Record<number, boolean>>({});

  useEffect(() => {
    loadScripts();
  }, [projectId]);

  async function loadScripts() {
    setLoading(true);
    try {
      const s = await listScripts(projectId);
      setScripts(s);
      if (s.length > 0 && !activeScript) {
        setActiveScript(s[0]);
        setScriptContent(s[0].content);
        setScriptTitle(s[0].title);
        loadScenes(s[0].id);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function loadScenes(scriptId: number) {
    try {
      const script = await getScriptWithScenes(projectId, scriptId);
      setScenes(script.scenes || []);
    } catch {
      setScenes([]);
    }
  }

  async function handleCreateScript() {
    try {
      const s = await createScript(projectId, { title: scriptTitle, content: scriptContent });
      setScripts((prev) => [...prev, s]);
      setActiveScript(s);
      setScenes([]);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleSaveScript() {
    if (!activeScript) return;
    try {
      const updated = await updateScript(projectId, activeScript.id, {
        title: scriptTitle,
        content: scriptContent,
      });
      setActiveScript(updated);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleBreakdown() {
    if (!activeScript) return;
    setBreaking(true);
    try {
      const result = await breakdownScript(projectId, activeScript.id);
      setScenes(result.scenes);
      result.scenes.forEach((s: Scene) => {
        setExpandedScenes((prev) => ({ ...prev, [s.id]: true }));
      });
    } catch (e) {
      console.error(e);
    } finally {
      setBreaking(false);
    }
  }

  async function handleSceneUpdate(sceneId: number, field: string, value: string) {
    setSavingScene((prev) => ({ ...prev, [sceneId]: true }));
    try {
      const updated = await updateScene(sceneId, {
        [field]: value,
      } as Partial<Scene>);
      setScenes((prev) => prev.map((s) => (s.id === sceneId ? updated : s)));
    } catch (e) {
      console.error(e);
    } finally {
      setSavingScene((prev) => ({ ...prev, [sceneId]: false }));
    }
  }

  const toggleScene = (sceneId: number) => {
    setExpandedScenes((prev) => ({ ...prev, [sceneId]: !prev[sceneId] }));
  };

  const selectScript = (script: Script) => {
    setActiveScript(script);
    setScriptContent(script.content);
    setScriptTitle(script.title);
    loadScenes(script.id);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-8">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Script</h1>
        <p className="text-muted-foreground mt-1">Write and break down your screenplay.</p>
      </div>

      {/* Script selector */}
      {scripts.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {scripts.map((s) => (
            <Button
              key={s.id}
              variant={activeScript?.id === s.id ? "default" : "outline"}
              size="sm"
              onClick={() => selectScript(s)}
            >
              <FileText className="w-3.5 h-3.5 mr-1.5" />
              {s.title}
            </Button>
          ))}
        </div>
      )}

      {/* Script editor */}
      <div className="bg-card border border-border rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-3">
          <Input
            value={scriptTitle}
            onChange={(e) => setScriptTitle(e.target.value)}
            className="text-lg font-semibold border-0 px-0 focus-visible:ring-0"
            placeholder="Script title..."
          />
          <div className="flex gap-2 ml-auto">
            {activeScript ? (
              <>
                <Button variant="outline" size="sm" onClick={handleSaveScript}>
                  <Save className="w-3.5 h-3.5 mr-1.5" /> Save
                </Button>
                <Button
                  size="sm"
                  onClick={handleBreakdown}
                  disabled={breaking || !scriptContent.trim()}
                >
                  {breaking ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  ) : (
                    <Wand2 className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  Auto-break into Scenes
                </Button>
              </>
            ) : (
              <Button size="sm" onClick={handleCreateScript}>
                Create Script
              </Button>
            )}
          </div>
        </div>

        <Textarea
          value={scriptContent}
          onChange={(e) => setScriptContent(e.target.value)}
          placeholder="Paste your screenplay text here..."
          rows={16}
          className="w-full font-mono text-sm resize-y"
        />
      </div>

      {/* Scenes list */}
      {scenes.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">
            Parsed Scenes ({scenes.length})
          </h2>
          {[...scenes]
            .sort((a, b) => a.scene_number - b.scene_number)
            .map((scene) => (
              <div
                key={scene.id}
                className="bg-card border border-border rounded-xl overflow-hidden"
              >
                <button
                  onClick={() => toggleScene(scene.id)}
                  className="w-full flex items-center gap-2 p-4 hover:bg-accent/50 transition-colors text-left"
                >
                  {expandedScenes[scene.id] ? (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  )}
                  <Badge variant="outline" className="font-mono">
                    Scene {scene.scene_number}
                  </Badge>
                  <span className="font-medium truncate flex-1">
                    {scene.heading || "Untitled Scene"}
                  </span>
                  {scene.location && (
                    <span className="text-xs text-muted-foreground hidden sm:inline">
                      {scene.location}
                    </span>
                  )}
                  {scene.time_of_day && (
                    <Badge variant="secondary" className="text-[10px]">
                      {scene.time_of_day}
                    </Badge>
                  )}
                </button>

                {expandedScenes[scene.id] && (
                  <div className="px-4 pb-4 space-y-3 border-t border-border pt-3">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div>
                        <label className="text-xs text-muted-foreground mb-1 block">Heading</label>
                        <Input
                          value={scene.heading}
                          onChange={(e) => handleSceneUpdate(scene.id, "heading", e.target.value)}
                          className="text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground mb-1 block">Location</label>
                        <Input
                          value={scene.location || ""}
                          onChange={(e) => handleSceneUpdate(scene.id, "location", e.target.value)}
                          className="text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground mb-1 block">Time of Day</label>
                        <Input
                          value={scene.time_of_day || ""}
                          onChange={(e) => handleSceneUpdate(scene.id, "time_of_day", e.target.value)}
                          className="text-sm"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground mb-1 block">Summary</label>
                      <Textarea
                        value={scene.summary || ""}
                        onChange={(e) => handleSceneUpdate(scene.id, "summary", e.target.value)}
                        className="text-sm resize-y"
                        rows={2}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <Link
                        to={`/project/${projectId}/storyboard?scene=${scene.id}`}
                        className="text-xs text-primary hover:underline"
                      >
                        Open in Storyboard →
                      </Link>
                      {savingScene[scene.id] && (
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <Loader2 className="w-3 h-3 animate-spin" /> Saving...
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}