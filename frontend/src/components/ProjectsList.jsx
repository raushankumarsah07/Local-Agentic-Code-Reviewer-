import React, { useState, useEffect } from 'react';
import { FolderGit2, FileText, Code2, Trash2, ArrowRight, Upload, AlertCircle, RefreshCw } from 'lucide-react';
import { api } from '../api/client';

export default function ProjectsList({ onSelectProject, onNavigateUpload }) {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const fetchProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getProjects();
      setProjects(data);
    } catch (err) {
      setError(err.message || 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleDelete = async (e, projectId) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete project '${projectId}'?`)) return;

    setDeletingId(projectId);
    try {
      await api.deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.project_id !== projectId));
    } catch (err) {
      alert(`Failed to delete project: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-500"></div>
        <p className="text-slate-400 text-sm">Loading local repositories...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto mt-12 p-6 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-center">
        <AlertCircle className="h-10 w-10 text-rose-400 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-rose-300 mb-1">Failed to Load Projects</h3>
        <p className="text-sm text-slate-400 mb-4">{error}</p>
        <button
          onClick={fetchProjects}
          className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium transition"
        >
          <RefreshCw className="h-4 w-4" />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="max-w-xl mx-auto mt-16 text-center p-12 bg-slate-900/60 border border-slate-800 rounded-3xl shadow-xl">
        <div className="h-16 w-16 bg-slate-800 text-brand-400 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-slate-700">
          <FolderGit2 className="h-8 w-8" />
        </div>
        <h2 className="text-xl font-bold text-white mb-2">No Projects Uploaded Yet</h2>
        <p className="text-sm text-slate-400 mb-6">
          Upload a ZIP archive of your source code repository to analyze architecture, dependencies, and AST entities.
        </p>
        <button
          onClick={onNavigateUpload}
          className="inline-flex items-center space-x-2 px-6 py-3 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-medium shadow-lg shadow-brand-500/20 transition transform active:scale-95"
        >
          <Upload className="h-5 w-5" />
          <span>Upload Source ZIP</span>
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-slate-800 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Your Repositories</h1>
          <p className="text-sm text-slate-400 mt-1">
            Deterministic code architecture, dependency graphs, and static entity analysis.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={fetchProjects}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
            title="Refresh list"
          >
            <RefreshCw className="h-5 w-5" />
          </button>
          <button
            onClick={onNavigateUpload}
            className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium shadow-lg shadow-brand-500/20 transition"
          >
            <Upload className="h-4 w-4" />
            <span>Upload ZIP</span>
          </button>
        </div>
      </div>

      {/* Grid of Projects */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-8">
        {projects.map((project) => (
          <div
            key={project.project_id}
            onClick={() => onSelectProject(project.project_id)}
            className="group bg-slate-900/70 border border-slate-800 hover:border-brand-500/50 rounded-2xl p-6 transition-all duration-200 hover:shadow-xl hover:shadow-brand-500/5 cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <div className="h-10 w-10 rounded-xl bg-slate-800 border border-slate-700 text-brand-400 flex items-center justify-center group-hover:bg-brand-500/10 group-hover:border-brand-500/30 transition">
                    <FolderGit2 className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white group-hover:text-brand-300 transition text-base">
                      {project.name}
                    </h3>
                    <span className="text-xs font-mono text-slate-500">ID: {project.project_id}</span>
                  </div>
                </div>

                <button
                  onClick={(e) => handleDelete(e, project.project_id)}
                  disabled={deletingId === project.project_id}
                  className="text-slate-500 hover:text-rose-400 p-1.5 rounded-lg hover:bg-rose-500/10 transition"
                  title="Delete repository"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>

              {/* Stats Row */}
              <div className="grid grid-cols-2 gap-3 my-4 p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 text-xs text-slate-400">
                <div className="flex items-center space-x-2">
                  <FileText className="h-4 w-4 text-indigo-400" />
                  <span>
                    <strong className="text-slate-200">{project.total_files}</strong> files
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <Code2 className="h-4 w-4 text-emerald-400" />
                  <span>
                    <strong className="text-slate-200">{project.total_lines}</strong> lines
                  </span>
                </div>
              </div>

              {/* Language Pills */}
              {project.languages && Object.keys(project.languages).length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-4">
                  {Object.entries(project.languages).map(([lang, count]) => (
                    <span
                      key={lang}
                      className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700/60"
                    >
                      {lang}: {count}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-brand-400 font-medium group-hover:text-brand-300">
              <span>Explore Architecture Graph</span>
              <ArrowRight className="h-4 w-4 transform group-hover:translate-x-1 transition" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
