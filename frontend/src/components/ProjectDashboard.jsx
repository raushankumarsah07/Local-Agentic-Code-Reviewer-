import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  Search,
  RefreshCw,
  Layers,
  FolderCode,
  FileCode,
  Globe,
  Play,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import ArchitectureGraph from './ArchitectureGraph';
import NodeDetailPanel from './NodeDetailPanel';
import SourceViewerModal from './SourceViewerModal';

export default function ProjectDashboard({ projectId, onBack }) {
  const activeProjectId = typeof projectId === 'object' && projectId !== null
    ? (projectId.project_id || projectId.id || '')
    : String(projectId || '');

  const [project, setProject] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters & Controls
  const [searchQuery, setSearchQuery] = useState('');
  const [includeExternal, setIncludeExternal] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [sourceModalFile, setSourceModalFile] = useState(null);

  // AST Parsing State
  const [parsing, setParsing] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  const loadProjectAndGraph = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const [projData, graphRes] = await Promise.all([
        api.getProject(activeProjectId),
        api.getProjectGraph(activeProjectId, includeExternal),
      ]);
      setProject(projData);
      setGraphData(graphRes);
    } catch (err) {
      setError(err.message || 'Failed to load project architecture');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjectAndGraph();
  }, [activeProjectId, includeExternal]);

  // Handler for parsing AST
  const handleParseAST = async () => {
    if (!activeProjectId) return;
    setParsing(true);
    try {
      const result = await api.parseProject(activeProjectId);
      setToastMessage(
        `AST parsed: ${result.total_functions} functions, ${result.total_classes} classes detected across ${result.parsed_files_count} files.`
      );
      // Reload graph to pick up fresh entities/edges
      const updatedGraph = await api.getProjectGraph(activeProjectId, includeExternal);
      setGraphData(updatedGraph);
      setTimeout(() => setToastMessage(null), 5000);
    } catch (err) {
      alert(`AST Parsing error: ${err.message}`);
    } finally {
      setParsing(false);
    }
  };

  const handleNodeClick = (nodeData) => {
    setSelectedNode(nodeData);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-slate-950 text-slate-100 overflow-hidden relative">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-50 bg-emerald-950/90 border border-emerald-500/40 text-emerald-200 px-4 py-2 rounded-xl shadow-2xl flex items-center space-x-2 text-xs backdrop-blur animate-fadeIn">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          <span>{toastMessage}</span>
          <button onClick={() => setToastMessage(null)} className="ml-2 hover:text-white">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Top Dashboard Control Bar */}
      <header className="px-4 py-3 bg-slate-900/90 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 shrink-0 backdrop-blur z-20">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition"
            title="Back to all projects"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Projects</span>
          </button>

          <div className="h-5 w-px bg-slate-800 hidden sm:block" />

          <div>
            <div className="flex items-center space-x-2">
              <h2 className="font-bold text-white text-sm sm:text-base tracking-tight truncate max-w-[200px] sm:max-w-md">
                {project ? project.name : activeProjectId}
              </h2>
              {project && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20 font-mono">
                  {project.total_files} files • {project.total_lines} lines
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Center / Search bar */}
        <div className="flex-1 max-w-xs sm:max-w-sm relative min-w-[180px]">
          <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search file name..."
            className="w-full pl-8 pr-7 py-1.5 bg-slate-950/80 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        {/* Right Controls: Filters & Actions */}
        <div className="flex items-center space-x-2">
          {/* External Libs Toggle */}
          <label className="flex items-center space-x-1.5 text-xs text-slate-300 bg-slate-800/60 px-2.5 py-1.5 rounded-lg border border-slate-700/50 cursor-pointer select-none hover:bg-slate-800 transition">
            <input
              type="checkbox"
              checked={includeExternal}
              onChange={(e) => setIncludeExternal(e.target.checked)}
              className="rounded bg-slate-900 border-slate-700 text-brand-600 focus:ring-0 focus:ring-offset-0 h-3.5 w-3.5"
            />
            <Globe className="h-3.5 w-3.5 text-slate-400" />
            <span className="hidden sm:inline">External Libs</span>
          </label>

          {/* AST Parse Action */}
          <button
            onClick={handleParseAST}
            disabled={parsing}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/80 hover:bg-indigo-600 text-white text-xs font-medium transition disabled:opacity-50"
            title="Scan and extract functions, classes, and inheritance via AST"
          >
            {parsing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5 fill-current" />
            )}
            <span className="hidden md:inline">Parse AST</span>
          </button>

          {/* Refresh Graph */}
          <button
            onClick={loadProjectAndGraph}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            title="Refresh graph"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      {/* Main Graph Area with Side Panel */}
      <div className="flex-1 flex overflow-hidden relative">
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center space-y-4">
            <Loader2 className="h-10 w-10 text-brand-500 animate-spin" />
            <p className="text-sm text-slate-400">Constructing interactive architecture graph...</p>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center space-y-4 p-6 text-center">
            <AlertCircle className="h-12 w-12 text-rose-500" />
            <h3 className="text-lg font-bold text-white">Error Loading Graph</h3>
            <p className="text-sm text-slate-400 max-w-md">{error}</p>
            <button
              onClick={loadProjectAndGraph}
              className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium transition"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            {/* Graph Canvas */}
            <div className="flex-1 h-full relative">
              <ArchitectureGraph
                graphData={graphData}
                searchQuery={searchQuery}
                onNodeClick={handleNodeClick}
                selectedNodeId={selectedNode?.id}
              />

              {/* Graph Legend & Status Overlay */}
              <div className="absolute bottom-4 left-4 z-10 bg-slate-900/90 border border-slate-800 rounded-xl p-3 text-[11px] backdrop-blur flex flex-col gap-1.5 shadow-xl max-w-xs">
                <span className="font-semibold text-slate-300">Graph Stats</span>
                <div className="flex items-center space-x-3 text-slate-400">
                  <span>{graphData?.nodes?.length || 0} nodes</span>
                  <span>•</span>
                  <span>{graphData?.edges?.length || 0} imports</span>
                </div>
                <div className="flex items-center gap-2 pt-1 border-t border-slate-800 text-[10px] text-slate-400">
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-brand-400 inline-block" /> Internal File
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-slate-600 inline-block" /> External Lib
                  </span>
                </div>
              </div>
            </div>

            {/* Side Drawer for Node Details */}
            {selectedNode && (
              <NodeDetailPanel
                node={selectedNode}
                allEdges={graphData?.edges || []}
                projectId={activeProjectId}
                onClose={() => setSelectedNode(null)}
                onViewSource={(path) => setSourceModalFile(path)}
              />
            )}
          </>
        )}
      </div>

      {/* Source Code Viewer Modal */}
      <SourceViewerModal
        isOpen={!!sourceModalFile}
        onClose={() => setSourceModalFile(null)}
        projectId={activeProjectId}
        filePath={sourceModalFile}
      />
    </div>
  );
}
