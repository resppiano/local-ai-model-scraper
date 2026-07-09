import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { Loader2, Plus, X, Upload, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  listCharacters,
  createCharacter,
  updateCharacter,
  deleteCharacter,
  uploadFile,
  type Character,
} from "@/api/fable";
import CharacterCard from "@/components/characters/CharacterCard";

export default function CharactersPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || "0");

  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingChar, setEditingChar] = useState<Character | null>(null);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploadingRef, setUploadingRef] = useState(false);
  const [uploadingGallery, setUploadingGallery] = useState(false);
  const [galleryImages, setGalleryImages] = useState<string[]>([]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  useEffect(() => {
    load();
  }, [projectId]);

  async function load() {
    setLoading(true);
    try {
      const chars = await listCharacters(projectId);
      setCharacters(chars);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleAddCharacter() {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      const char = await createCharacter(projectId, {
        name: newName,
        description: newDesc || undefined,
      });
      setCharacters((prev) => [...prev, char]);
      setNewName("");
      setNewDesc("");
      setShowAddForm(false);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdateCharacter(char: Character) {
    if (!char.name.trim()) return;
    setSaving(true);
    try {
      const updated = await updateCharacter(projectId, char.id, {
        name: char.name,
        description: char.description || undefined,
      });
      setCharacters((prev) => prev.map((c) => (c.id === char.id ? updated : c)));
      setEditingChar(null);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  }

  async function handleUploadRef(char: Character, file: File) {
    setUploadingRef(true);
    try {
      const result = await uploadFile(projectId, file, "reference");
      const updated = await updateCharacter(projectId, char.id, {
        reference_image_url: result.url,
      });
      setCharacters((prev) => prev.map((c) => (c.id === char.id ? updated : c)));
      if (editingChar?.id === char.id) {
        setEditingChar(updated);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setUploadingRef(false);
    }
  }

  async function handleUploadGallery(char: Character, file: File) {
    setUploadingGallery(true);
    try {
      const result = await uploadFile(projectId, file, "reference");
      setGalleryImages((prev) => [...prev, result.url]);
    } catch (e) {
      console.error(e);
    } finally {
      setUploadingGallery(false);
    }
  }

  async function handleDelete(charId: number) {
    try {
      await deleteCharacter(projectId, charId);
      setCharacters((prev) => prev.filter((c) => c.id !== charId));
      setEditingChar(null);
    } catch (e) {
      console.error(e);
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    // DnD handler — character data is carried via the drag event
    const { active, over } = event;
    if (over) {
      console.log("Character dragged:", active.data.current?.character, "over:", over.id);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-8">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Characters</h1>
          <p className="text-muted-foreground mt-1">
            Manage your cast — drag characters to assign them to storyboard panels.
          </p>
        </div>
        <Button onClick={() => setShowAddForm(true)}>
          <Plus className="w-4 h-4 mr-1.5" /> Add Character
        </Button>
      </div>

      {/* Add character inline form */}
      {showAddForm && (
        <div className="bg-card border border-border rounded-xl p-4 space-y-3">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Character name..."
            className="text-sm"
          />
          <Textarea
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="Description (optional)..."
            className="text-sm resize-y"
            rows={2}
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleAddCharacter}
              disabled={saving || !newName.trim()}
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
              Create
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowAddForm(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Character grid */}
      {characters.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-border rounded-xl">
          <p className="text-muted-foreground">No characters yet.</p>
          <p className="text-muted-foreground/50 text-sm mt-1">
            Add your first character to get started.
          </p>
        </div>
      ) : (
        <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
          <div className="flex flex-wrap gap-4">
            {characters.map((char) => (
              <CharacterCard
                key={char.id}
                character={char}
                onEdit={setEditingChar}
              />
            ))}
          </div>
        </DndContext>
      )}

      {/* Edit dialog */}
      <Dialog
        open={editingChar !== null}
        onOpenChange={(open) => {
          if (!open) setEditingChar(null);
        }}
      >
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Edit Character</DialogTitle>
          </DialogHeader>
          {editingChar && (
            <div className="space-y-4">
              {/* Reference image */}
              <div className="flex items-center gap-4">
                <div className="w-20 h-20 rounded-lg overflow-hidden bg-muted shrink-0">
                  {editingChar.reference_image_url ? (
                    <img
                      src={editingChar.reference_image_url}
                      alt={editingChar.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-muted-foreground/30">
                      {editingChar.name[0]?.toUpperCase() || "?"}
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">{editingChar.name}</p>
                  <label className="relative cursor-pointer">
                    <span className="text-xs text-primary hover:underline flex items-center gap-1 mt-1">
                      <Upload className="w-3 h-3" />
                      {uploadingRef ? "Uploading..." : "Upload reference image"}
                    </span>
                    <input
                      type="file"
                      accept="image/*"
                      className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                      disabled={uploadingRef}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadRef(editingChar, file);
                      }}
                    />
                  </label>
                </div>
              </div>

              {/* Name & description */}
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Name</label>
                  <Input
                    value={editingChar.name}
                    onChange={(e) =>
                      setEditingChar({ ...editingChar, name: e.target.value })
                    }
                    className="text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Description</label>
                  <Textarea
                    value={editingChar.description || ""}
                    onChange={(e) =>
                      setEditingChar({ ...editingChar, description: e.target.value })
                    }
                    className="text-sm resize-y"
                    rows={3}
                  />
                </div>
              </div>

              {/* Gallery upload */}
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">
                  Gallery Images
                </label>
                <div className="flex flex-wrap gap-2">
                  {galleryImages.map((url, i) => (
                    <div key={i} className="relative w-16 h-16 rounded-lg overflow-hidden bg-muted">
                      <img src={url} alt="" className="w-full h-full object-cover" />
                      <button
                        onClick={() => setGalleryImages((prev) => prev.filter((_, j) => j !== i))}
                        className="absolute top-0.5 right-0.5 bg-black/60 rounded-full p-0.5"
                      >
                        <X className="w-3 h-3 text-white" />
                      </button>
                    </div>
                  ))}
                  <label className="w-16 h-16 rounded-lg border-2 border-dashed border-border flex items-center justify-center cursor-pointer hover:border-primary transition-colors">
                    <Plus className="w-4 h-4 text-muted-foreground" />
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      disabled={uploadingGallery}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadGallery(editingChar, file);
                      }}
                    />
                  </label>
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-between pt-2">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDelete(editingChar.id)}
                >
                  Delete Character
                </Button>
                <Button
                  size="sm"
                  onClick={() => handleUpdateCharacter(editingChar)}
                  disabled={saving}
                >
                  {saving ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  ) : (
                    <Save className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  Save Changes
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}