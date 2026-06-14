import { useEffect, useState } from 'react';
import { useParams } from 'react-router';
import { listShots, createShot, queueRender, getRenderStatus, listCharacters, type Shot, type Character } from '@/api/fable';
import { Video, Loader2, Play, Plus, AlertCircle, CheckCircle, Clock } from 'lucide-react';

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || '0');

  const [shots, setShots] = useState<Shot[]>([]);
  const [, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [desc, setDesc] = useState('');
  const [prompt, setPrompt] = useState('');
  const [shotType, setShotType] = useState('wide');
  const [rendering, setRendering] = useState<Record<number, boolean>>({});
  const [jobStatus, setJobStatus] = useState<Record<number, { status: string; error?: string }>>({});

  useEffect(() => { load(); }, [projectId]);

  async function load() {
    setLoading(true);
    try {
      const [s, c] = await Promise.all([
        listShots(projectId),
        listCharacters(projectId),
      ]);
      setShots(s);
      setCharacters(c);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleAddShot(e: React.FormEvent) {
    e.preventDefault();
    if (!desc.trim() || !prompt.trim()) return;
    setAdding(true);
    try {
      await createShot(projectId, {
        description: desc,
        prompt,
        shot_type: shotType,
        scene_number: 1,
        shot_number: shots.length + 1,
      });
      setDesc('');
      setPrompt('');
      await load();
    } catch (e) {
      alert(String(e));
    } finally {
      setAdding(false);
    }
  }

  async function handleRender(shotId: number, provider: 'comfyui' | 'higgsfield') {
    setRendering((r) => ({ ...r, [shotId]: true }));
    try {
      const job = await queueRender(shotId, provider);
      setJobStatus((j) => ({ ...j, [shotId]: { status: job.status } }));
      // Poll status
      const interval = setInterval(async () => {
        const status = await getRenderStatus(job.job_id);
        setJobStatus((j) => ({ ...j, [shotId]: { status: status.status, error: status.error_message || undefined } }));
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(interval);
          setRendering((r) => ({ ...r, [shotId]: false }));
          await load();
        }
      }, 3000);
    } catch (e) {
      setRendering((r) => ({ ...r, [shotId]: false }));
      setJobStatus((j) => ({ ...j, [shotId]: { status: 'failed', error: String(e) } }));
    }
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case 'done': return <CheckCircle className="w-4 h-4 text-emerald-400" />;
      case 'failed': return <AlertCircle className="w-4 h-4 text-red-400" />;
      case 'rendering': case 'queued': return <Clock className="w-4 h-4 text-cyan-400" />;
      default: return <Clock className="w-4 h-4 text-white/30" />;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Project #{projectId}</h1>
        <p className="text-white/50 mt-1">Manage shots and renders.</p>
      </div>

      <form onSubmit={handleAddShot} className="bg-white/5 border border-white/10 rounded-xl p-5 space-y-3">
        <p className="font-medium text-sm">Add Shot</p>
        <input
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          placeholder="Shot description..."
          className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400/50"
        />
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="AI generation prompt..."
          rows={2}
          className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400/50"
        />
        <div className="flex gap-3">
          <select value={shotType} onChange={(e) => setShotType(e.target.value)} className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm">
            <option value="wide">Wide</option>
            <option value="medium">Medium</option>
            <option value="close-up">Close-up</option>
            <option value="extreme-close-up">Extreme Close-up</option>
          </select>
          <button
            type="submit"
            disabled={adding || !desc.trim() || !prompt.trim()}
            className="bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 rounded-lg px-4 py-2 text-sm font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
          >
            {adding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Add Shot
          </button>
        </div>
      </form>

      {loading && (
        <div className="flex items-center gap-2 text-white/50 py-8">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading...
        </div>
      )}

      {!loading && shots.length === 0 && (
        <div className="text-center py-16 border border-dashed border-white/10 rounded-xl">
          <Video className="w-8 h-8 text-white/20 mx-auto mb-3" />
          <p className="text-white/40">No shots yet.</p>
          <p className="text-white/30 text-sm">Add your first shot above.</p>
        </div>
      )}

      <div className="space-y-3">
        {shots.map((s) => (
          <div key={s.id} className="bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-white/30">{s.scene_number}.{s.shot_number}</span>
                  {statusIcon(s.status)}
                  <span className="font-medium">{s.description || 'Untitled'}</span>
                </div>
                <p className="text-white/40 text-xs mt-1 line-clamp-2">{s.prompt}</p>
                {s.assets.length > 0 && (
                  <div className="flex gap-2 mt-2">
                    {s.assets.map((a) => (
                      <a key={a.id} href={a.url} target="_blank" rel="noreferrer">
                        {a.type === 'image' || a.type === 'thumbnail' ? (
                          <img src={a.url} alt="" className="w-20 h-14 object-cover rounded-lg border border-white/10" />
                        ) : (
                          <video src={a.url} className="w-20 h-14 object-cover rounded-lg border border-white/10" />
                        )}
                      </a>
                    ))}
                  </div>
                )}
                {jobStatus[s.id]?.error && (
                  <p className="text-red-400 text-xs mt-1">Error: {jobStatus[s.id].error}</p>
                )}
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => handleRender(s.id, 'comfyui')}
                  disabled={rendering[s.id] || s.status === 'queued' || s.status === 'rendering'}
                  className="bg-white/5 hover:bg-emerald-500/20 text-emerald-400 border border-white/10 hover:border-emerald-500/30 rounded-lg px-3 py-1.5 text-xs flex items-center gap-1 transition-colors disabled:opacity-50"
                >
                  {rendering[s.id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                  ComfyUI
                </button>
                <button
                  onClick={() => handleRender(s.id, 'higgsfield')}
                  disabled={rendering[s.id] || s.status === 'queued' || s.status === 'rendering'}
                  className="bg-white/5 hover:bg-cyan-500/20 text-cyan-400 border border-white/10 hover:border-cyan-500/30 rounded-lg px-3 py-1.5 text-xs flex items-center gap-1 transition-colors disabled:opacity-50"
                >
                  <Play className="w-3 h-3" />
                  Higgsfield
                </button>
              </div>
            </div>
            {s.status === 'rendering' || s.status === 'queued' ? (
              <div className="mt-2 h-1 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-400 animate-pulse w-3/4" />
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
