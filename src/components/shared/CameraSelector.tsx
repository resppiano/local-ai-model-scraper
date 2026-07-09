import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const cameraDirections = [
  { value: "static", label: "Static" },
  { value: "pan_left", label: "Pan Left" },
  { value: "pan_right", label: "Pan Right" },
  { value: "dolly_in", label: "Dolly In" },
  { value: "dolly_out", label: "Dolly Out" },
  { value: "tilt_up", label: "Tilt Up" },
  { value: "tilt_down", label: "Tilt Down" },
  { value: "track_left", label: "Track Left" },
  { value: "track_right", label: "Track Right" },
  { value: "crane_up", label: "Crane Up" },
  { value: "crane_down", label: "Crane Down" },
];

interface CameraSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

export default function CameraSelector({ value, onChange }: CameraSelectorProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder="Select camera direction" />
      </SelectTrigger>
      <SelectContent>
        {cameraDirections.map((dir) => (
          <SelectItem key={dir.value} value={dir.value}>
            {dir.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}