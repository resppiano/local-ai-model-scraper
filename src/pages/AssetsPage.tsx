import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router";
import { Loader2, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  listAssets,
  uploadFile,
  deleteAsset,
  type Asset,
} from "@/api/fable";
import UploadDropzone from "@/components/assets/UploadDropzone";
import AssetCard from "@/components/assets/AssetCard";

const assetTypes = [
  { value: "reference", label: "Reference" },
  { value: "environment", label: "Environment" },
  { value: "prop", label: "Prop" },
  { value: "mood_board", label: "Mood Board" },
];

export default function AssetsPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || "0");

  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadType, setUploadType] = useState("reference");
  const [tagsInput, setTagsInput] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    load();
  }, [projectId]);

  async function load() {
    setLoading(true);
    try {
      const a = await listAssets(projectId);
      setAssets(a);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const handleUpload = useCallback(
    async (file: File) => {
      // If we have tags, append them as a query param or store them
      const result = await uploadFile(projectId, file, uploadType);
      // Reload to get updated list
      await load();
    },
    [projectId, uploadType]
  );

  async function handleDelete(assetId: number) {
    try {
      await deleteAsset(projectId, assetId);
      setAssets((prev) => prev.filter((a) => a.id !== assetId));
    } catch (e) {
      console.error(e);
    }
  }

  const filtered = assets.filter((a) => {
    if (filterType !== "all" && a.type !== filterType) return false;
    if (search) {
      const q = search.toLowerCase();
      const filename = a.url?.split("/").pop()?.toLowerCase() || "";
      return filename.includes(q);
    }
    return true;
  });

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
        <h1 className="text-3xl font-bold tracking-tight">Assets</h1>
        <p className="text-muted-foreground mt-1">
          Upload and manage visual assets for your production.
        </p>
      </div>

      {/* Upload section */}
      <div className="bg-card border border-border rounded-xl p-5 space-y-4">
        <h2 className="font-semibold text-sm">Upload Asset</h2>

        <div className="flex gap-3 flex-wrap">
          <div className="flex-1 min-w-[150px]">
            <label className="text-xs text-muted-foreground mb-1 block">Type</label>
            <Select value={uploadType} onValueChange={setUploadType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {assetTypes.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1 min-w-[150px]">
            <label className="text-xs text-muted-foreground mb-1 block">Tags</label>
            <Input
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="Comma-separated tags..."
              className="text-sm"
            />
          </div>
        </div>

        <UploadDropzone onUpload={handleUpload} />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search assets..."
            className="pl-9 text-sm"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {["all", "image", "video", "audio"].map((type) => (
            <Button
              key={type}
              variant={filterType === type ? "default" : "outline"}
              size="sm"
              onClick={() => setFilterType(type)}
              className="text-xs capitalize"
            >
              {type === "all" ? "All" : type}
            </Button>
          ))}
        </div>
        {assets.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {filtered.length} of {assets.length} assets
          </span>
        )}
      </div>

      {/* Asset grid */}
      {assets.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-border rounded-xl">
          <p className="text-muted-foreground">No assets yet.</p>
          <p className="text-muted-foreground/50 text-sm mt-1">
            Upload images, videos, or audio files above.
          </p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-border rounded-xl">
          <p className="text-muted-foreground">No assets match your filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {filtered.map((asset) => (
            <AssetCard key={asset.id} asset={asset} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
}