import { useDraggable } from "@dnd-kit/core";
import { GripVertical } from "lucide-react";
import type { Character } from "@/api/fable";

interface CharacterCardProps {
  character: Character;
  onEdit?: (character: Character) => void;
}

export default function CharacterCard({ character, onEdit }: CharacterCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `character-${character.id}`,
    data: { character },
  });

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        zIndex: isDragging ? 50 : undefined,
      }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={() => onEdit?.(character)}
      className="bg-card border border-border rounded-xl p-4 cursor-pointer hover:shadow-md transition-all space-y-3 w-[200px]"
    >
      {/* Drag handle */}
      <div
        {...listeners}
        {...attributes}
        className="flex items-center justify-center text-muted-foreground/50 hover:text-muted-foreground cursor-grab active:cursor-grabbing -mt-1 -mx-1 py-1"
      >
        <GripVertical className="w-4 h-4" />
      </div>

      {/* Image */}
      <div className="w-full aspect-square rounded-lg overflow-hidden bg-muted">
        {character.reference_image_url ? (
          <img
            src={character.reference_image_url}
            alt={character.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-3xl font-bold text-muted-foreground/30">
            {character.name[0]?.toUpperCase() || "?"}
          </div>
        )}
      </div>

      {/* Name + description */}
      <div className="text-center">
        <p className="font-semibold text-sm truncate">{character.name}</p>
        {character.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
            {character.description}
          </p>
        )}
      </div>
    </div>
  );
}