import { Routes, Route } from 'react-router';
import Layout from '@/components/Layout';
import Home from '@/pages/Home';
import ProjectsPage from '@/pages/Projects';
import ProjectDetail from '@/pages/ProjectDetail';
import ScriptPage from '@/pages/ScriptPage';
import CharactersPage from '@/pages/CharactersPage';
import AssetsPage from '@/pages/AssetsPage';
import StoryboardPage from '@/pages/StoryboardPage';
import ControlVideosPage from '@/pages/ControlVideosPage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/:id" element={<ProjectDetail />} />
        <Route path="/project/:id/script" element={<ScriptPage />} />
        <Route path="/project/:id/characters" element={<CharactersPage />} />
        <Route path="/project/:id/assets" element={<AssetsPage />} />
        <Route path="/project/:id/storyboard" element={<StoryboardPage />} />
        <Route path="/project/:id/control-videos" element={<ControlVideosPage />} />
      </Routes>
    </Layout>
  );
}