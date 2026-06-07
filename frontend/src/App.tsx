import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { getRuntimeMode, RuntimeMode } from './api';
import Header from './components/Header';
import PlannerPage from './pages/PlannerPage';
import PreferencesPage from './pages/PreferencesPage';


export function getDefaultRuntime(viteMode: string): RuntimeMode {
  if (viteMode === 'hybrid') {
    return {
      mode: 'hybrid',
      llm: 'deepseek',
      amap: 'amap',
      actions: 'mock',
    };
  }
  if (viteMode === 'live') {
    return {
      mode: 'live',
      llm: 'deepseek',
      amap: 'amap',
      actions: 'mock_fallback',
    };
  }
  return {
    mode: 'demo',
    llm: 'mock',
    amap: 'mock',
    actions: 'mock',
  };
}

const VITE_DEFAULT_RUNTIME = getDefaultRuntime(import.meta.env.MODE);


export default function App() {
  const [runtime, setRuntime] = useState<RuntimeMode>(VITE_DEFAULT_RUNTIME);

  useEffect(() => {
    getRuntimeMode()
      .then(setRuntime)
      .catch(() => setRuntime(VITE_DEFAULT_RUNTIME));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <Header runtime={runtime} />
      <Routes>
        <Route path="/" element={<PlannerPage runtime={runtime} />} />
        <Route path="/settings" element={<PreferencesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
