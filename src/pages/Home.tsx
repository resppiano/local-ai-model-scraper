import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { getDashboard, type DashboardStats } from '@/api/fable';
import { Film, Image, Video, Activity } from 'lucide-react';

export default function Home() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboard()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const cards = stats ? [
    { label: 'Projects', value: stats.total_projects, sub: `${stats.active_projects} active`, icon: Film, color: 'text-emerald-400' },
    { label: 'Shots', value: stats.total_shots, sub: `${stats.shots_rendered} rendered`, icon: Video, color: 'text-cyan-400' },
    { label: 'Assets', value: stats.total_assets, sub: 'generated', icon: Image, color: 'text-pink-400' },
  ] : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-white/50 mt-1">Welcome to Project Fable — your AI film studio.</p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-white/50">
          <Activity className="w-4 h-4 animate-spin" /> Loading...
        </div>
      )}

      {!loading && !stats && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400">
          Failed to load dashboard. Make sure the Fable API (port 8001) is running.
        </div>
      )}

      {stats && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {cards.map((c) => (
              <div key={c.label} className="bg-white/5 border border-white/10 rounded-xl p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white/50 text-sm">{c.label}</p>
                    <p className="text-3xl font-bold mt-1">{c.value}</p>
                    <p className="text-white/40 text-xs mt-1">{c.sub}</p>
                  </div>
                  <c.icon className={`w-8 h-8 ${c.color} opacity-60`} />
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white/5 border border-white/10 rounded-xl p-5">
              <h2 className="font-semibold text-lg mb-4">Recent Assets</h2>
              {stats.recent_assets.length === 0 ? (
                <p className="text-white/40 text-sm">No assets yet. Create a project and render some shots.</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {stats.recent_assets.map((a) => (
                    <a key={a.id} href={a.url} target="_blank" rel="noreferrer" className="group">
                      <div className="aspect-video bg-white/5 rounded-lg overflow-hidden border border-white/10 group-hover:border-emerald-400/50 transition-colors">
                        {a.type === 'image' || a.type === 'thumbnail' ? (
                          <img src={a.url} alt="" className="w-full h-full object-cover" loading="lazy" />
                        ) : (
                          <video src={a.url} className="w-full h-full object-cover" />
                        )}
                      </div>
                      <p className="text-xs text-white/40 mt-1 truncate">{a.type}</p>
                    </a>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-5">
              <h2 className="font-semibold text-lg mb-4">Quick Start</h2>
              <div className="space-y-3">
                <Link to="/projects" className="flex items-center gap-3 p-3 bg-white/5 hover:bg-white/10 rounded-lg transition-colors border border-white/10">
                  <Film className="w-5 h-5 text-emerald-400" />
                  <div>
                    <p className="font-medium">View Projects</p>
                    <p className="text-white/40 text-xs">Manage your film projects</p>
                  </div>
                </Link>
                <div className="text-white/40 text-sm pt-2">
                  API Status: <span className="text-emerald-400">Connected</span> at localhost:8001
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
