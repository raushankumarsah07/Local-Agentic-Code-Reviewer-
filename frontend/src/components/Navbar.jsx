import React, { useEffect, useState } from 'react';
import { Layers, Upload, FolderCode, Activity, RefreshCw } from 'lucide-react';
import { api } from '../api/client';

export default function Navbar({ activeTab, setActiveTab, onRefresh }) {
  const [serverHealth, setServerHealth] = useState({ status: 'checking', ollama: null });

  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const data = await api.checkHealth();
      setServerHealth({
        status: data.status,
        ollama: data.ollama_service?.status || 'unreachable',
      });
    } catch {
      setServerHealth({ status: 'offline', ollama: 'offline' });
    }
  };

  return (
    <header className="bg-slate-900/90 backdrop-blur border-b border-slate-800 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('projects')}>
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-brand-500/20">
            <Layers className="h-5 w-5 text-white" />
          </div>
          <div>
            <span className="font-bold text-lg text-white tracking-tight flex items-center gap-2">
              CodeReviewer <span className="text-xs px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-300 border border-brand-500/30 font-medium">Local AI</span>
            </span>
            <p className="text-xs text-slate-400">Architecture Grapher & Offline Code Reviewer</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center space-x-1 sm:space-x-2">
          <button
            onClick={() => setActiveTab('projects')}
            className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'projects'
                ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <FolderCode className="h-4 w-4" />
            <span>Projects</span>
          </button>

          <button
            onClick={() => setActiveTab('upload')}
            className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'upload'
                ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Upload className="h-4 w-4" />
            <span>Upload ZIP</span>
          </button>

          {/* Status Badge */}
          <div className="hidden md:flex items-center space-x-2 pl-4 border-l border-slate-800 text-xs">
            <span className={`inline-block h-2 w-2 rounded-full ${
              serverHealth.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'
            }`} />
            <span className="text-slate-400">
              API: <strong className={serverHealth.status === 'healthy' ? 'text-emerald-400' : 'text-rose-400'}>
                {serverHealth.status}
              </strong>
            </span>
          </div>
        </nav>
      </div>
    </header>
  );
}
