import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { listProjects, createProject, type Project } from '@/api/fable';
import { Film, Plus, Loader2, ArrowRight } from 'lucide-react';

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState('');
  const [logline, setLogline] = useState('');

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const data = await listProjects();
      setProjects(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    try {
      await createProject({ title, logline: logline || undefined });
      setTitle('');
      setLogline('');
      await load();
    } catch (e) {
      alert(String(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
          <p className="text-white/50 mt-1">Manage your film projects.</p>
        </div>
      </div>

      <form onSubmit={handleCreate} className="bg-white/5 border border-white/10 rounded-xl p-5 space-y-3">
        <p className="font-medium text-sm">New Project</p>
        <div className="flex gap-3">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Project title..."
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400/50"
          />
          <input
            value={logline}
            onChange={(e) => setLogline(e.target.value)}
            placeholder="Logline (optional)..."
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400/50"
          />
          <button
            type="submit"
            disabled={creating || !title.trim()}
            className="bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 rounded-lg px-4 py-2 text-sm font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
          >
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Create
          </button>
        </div>
      </form>

      {loading && (
        <div className="flex items-center gap-2 text-white/50 py-8">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading...
        </div>
      )}

      {!loading && projects.length === 0 && (
        <div className="text-center py-16 border border-dashed border-white/10 rounded-xl">
          <Film className="w-8 h-8 text-white/20 mx-auto mb-3" />
          <p className="text-white/40">No projects yet.</p>
          <p className="text-white/30 text-sm">Create your first film project above.</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {projects.map((p) => (
          <Link
            key={p.id}
            to={`/projects/${p.id}`}
            className="group bg-white/5 border border-white/10 hover:border-emerald-400/30 rounded-xl p-5 transition-colors"
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-lg group-hover:text-emerald-400 transition-colors">{p.title}</h3>
                {p.logline && <p className="text-white/50 text-sm mt-1">{p.logline}</p>}
                <div className="flex gap-4 mt-3 text-xs text-white/40">
                  <span>{p.shot_count} shots</span>
                  <span>{p.asset_count} assets</span>
                  <span className={`capitalize ${
                    p.status === 'active' ? 'text-emerald-400' : p.status === 'complete' ? 'text-cyan-400' : 'text-white/40'
                  }`}>{p.status}</span>
                </div>
              </div>
              <ArrowRight className="w-5 h-5 text-white/20 group-hover:text-emerald-400/60 transition-colors" />
            </div>
            {p.vision && (
              <p className="text-white/30 text-xs mt-3 line-clamp-2">{p.vision}</p>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
