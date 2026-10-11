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
  Network,
  ShieldAlert,
  MessageSquare,
  BookOpen,
  Sparkles,
} from 'lucide-react';
import { api } from '../api/client';
import ArchitectureGraph from './ArchitectureGraph';
import NodeDetailPanel from './NodeDetailPanel';
import SourceViewerModal from './SourceViewerModal';
import FindingsDashboard from './FindingsDashboard';
import ChatRepository from './ChatRepository';
import DocumentationViewer from './DocumentationViewer';


export default function ProjectDashboard({ projectId, onBack }) {
  const activeProjectId = typeof projectId === 'object' && projectId !== null
    ? (projectId.project_id || projectId.id || '')
    : String(projectId || '');

  // Sub-view tab: 'graph' | 'findings'
  const [activeTab, setActiveTab] = useState('graph');

  const [project, setProject] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Findings count badge
  const [findingsCount, setFindingsCount] = useState(0);

  // Filters & Controls (Graph View)
  const [searchQuery, setSearchQuery] = useState('');
  const [includeExternal, setIncludeExternal] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);

  // Source Viewer Modal State
  const [sourceModalFile, setSourceModalFile] = useState(null);
  const [sourceModalHighlight, setSourceModalHighlight] = useState(null);

  // AST Parsing State
  const [parsing, setParsing] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  // Phase 10: Agent Analysis Workflow State
  const [analysisStatus, setAnalysisStatus] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showAnalysisSuccess, setShowAnalysisSuccess] = useState(false);

  // Poll analysis status
  useEffect(() => {
    let intervalId = null;
    if (isAnalyzing && activeProjectId) {
      intervalId = setInterval(async () => {
        try {
          const status = await api.getProjectAnalysisStatus(activeProjectId);
          setAnalysisStatus(status);
          if (status.status === 'completed') {
            setIsAnalyzing(false);
            setShowAnalysisSuccess(true);
            setTimeout(() => setShowAnalysisSuccess(false), 5000);
            loadProjectAndGraph();
            setToastMessage('Agent analysis completed! Graph, findings, vector index, and docs generated.');
          } else if (status.status === 'failed') {
            setIsAnalyzing(false);
            setError(status.error_message || 'Agent analysis failed.');
          }
        } catch (err) {
          console.warn('Analysis status polling error:', err);
        }
      }, 1500);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isAnalyzing, activeProjectId]);

  const handleTriggerAnalysis = async () => {
    if (!activeProjectId) return;
    try {
      setIsAnalyzing(true);
      setError(null);
      setAnalysisStatus({
        status: 'running',
        step: 'Initializing agent workflow',
        progress_percent: 5,
        current_activity: 'Starting LangGraph agent analysis...',
      });
      const res = await api.triggerProjectAnalysis(activeProjectId);
      setToastMessage(res.message || 'Agent analysis started in background.');
    } catch (err) {
      setIsAnalyzing(false);
      setError(`Failed to trigger analysis: ${err.message}`);
    }
  };

  const loadProjectAndGraph = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const [projData, graphRes, summaryRes] = await Promise.all([
        api.getProject(activeProjectId),
        api.getProjectGraph(activeProjectId, includeExternal),
        api.getFindingsSummary(activeProjectId).catch(() => ({ total: 0 })),
      ]);
      setProject(projData);
      setGraphData(graphRes);
      setFindingsCount(summaryRes?.total || 0);
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

  // Open Source Viewer with optional highlighted lines
  const handleOpenSourceViewer = (filePath, highlightRange = null) => {
    setSourceModalFile(filePath);
    setSourceModalHighlight(highlightRange);
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
              <h2 className="font-bold text-white text-sm sm:text-base tracking-tight truncate max-w-[160px] sm:max-w-xs">
                {project ? project.name : activeProjectId}
              </h2>
              {project && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20 font-mono hidden md:inline">
                  {project.total_files} files • {project.total_lines} lines
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Center: View Switcher Tabs (Graph vs Findings) */}
        <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 shadow-inner">
          <button
            onClick={() => setActiveTab('graph')}
            className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === 'graph'
                ? 'bg-slate-800 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Network className="h-3.5 w-3.5 text-brand-400" />
            <span>Architecture Graph</span>
          </button>

          <button
            onClick={() => setActiveTab('findings')}
            className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === 'findings'
                ? 'bg-slate-800 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
            <span>Findings & Review</span>
            {findingsCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/30 font-mono">
                {findingsCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('chat')}
            className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === 'chat'
                ? 'bg-slate-800 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5 text-purple-400" />
            <span>Chat with Repo</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono">
              RAG
            </span>
          </button>

          <button
            onClick={() => setActiveTab('docs')}
            className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === 'docs'
                ? 'bg-slate-800 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="h-3.5 w-3.5 text-emerald-400" />
            <span>Repository Docs</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
              Phase 10
            </span>
          </button>
        </div>

        {/* Global Agent Analysis Trigger Button */}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleTriggerAnalysis}
            disabled={isAnalyzing}
            className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white text-xs font-semibold shadow-md shadow-indigo-500/20 transition disabled:opacity-50 cursor-pointer"
            title="Execute complete LangGraph agent workflow automatically (graph, findings, index, docs)"
          >
            {isAnalyzing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            <span>{isAnalyzing ? 'Analyzing...' : 'Analyze'}</span>
          </button>
        </div>


        {/* Right Controls: Graph Mode Filters or Actions */}
        {activeTab === 'graph' ? (
          <div className="flex items-center space-x-2">
            {/* Search file in graph */}
            <div className="relative min-w-[160px] sm:min-w-[200px]">
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

            {/* External Libs Toggle */}
            <label className="flex items-center space-x-1.5 text-xs text-slate-300 bg-slate-800/60 px-2.5 py-1.5 rounded-lg border border-slate-700/50 cursor-pointer select-none hover:bg-slate-800 transition">
              <input
                type="checkbox"
                checked={includeExternal}
                onChange={(e) => setIncludeExternal(e.target.checked)}
                className="rounded bg-slate-900 border-slate-700 text-brand-600 focus:ring-0 focus:ring-offset-0 h-3.5 w-3.5"
              />
              <Globe className="h-3.5 w-3.5 text-slate-400" />
              <span className="hidden lg:inline">External Libs</span>
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
              <span className="hidden sm:inline">Parse AST</span>
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
        ) : (
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setActiveTab('graph')}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition"
            >
              <Network className="h-3.5 w-3.5" />
              <span>Back to Graph</span>
            </button>
          </div>
        )}
      </header>

      {/* Phase 10: Live Agent Workflow Progress Banner */}
      {(isAnalyzing || showAnalysisSuccess) && analysisStatus && (
        <div className="bg-slate-900/95 border-b border-indigo-500/30 px-4 py-3 backdrop-blur-md z-30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xl animate-fadeIn">
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shrink-0">
              {showAnalysisSuccess ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              ) : (
                <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-white">
                  {showAnalysisSuccess ? 'Analysis Complete!' : analysisStatus.step || 'Running Agent Workflow'}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-mono font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  {analysisStatus.progress_percent || 0}%
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate max-w-lg">
                {showAnalysisSuccess
                  ? 'All artifacts generated: architecture graph, findings, vector index, and docs.'
                  : analysisStatus.current_activity || 'Processing repository AST and graph...'}
              </p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="w-full sm:w-64 shrink-0 flex items-center gap-3">
            <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden border border-slate-700/50">
              <div
                className={`h-full transition-all duration-500 rounded-full ${
                  showAnalysisSuccess
                    ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                    : 'bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500'
                }`}
                style={{ width: `${Math.max(5, analysisStatus.progress_percent || 0)}%` }}
              />
            </div>
            {showAnalysisSuccess && (
              <button
                onClick={() => setActiveTab('docs')}
                className="text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 whitespace-nowrap cursor-pointer"
              >
                View Docs →
              </button>
            )}
          </div>
        </div>
      )}

      {/* Main Body Area: Graph View, Findings View, Chat View, or Docs View */}
      {activeTab === 'graph' ? (
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
                  onViewSource={(path) => handleOpenSourceViewer(path)}
                />
              )}
            </>
          )}
        </div>
      ) : activeTab === 'findings' ? (
        /* Findings & Code Review Dashboard View */
        <FindingsDashboard
          projectId={activeProjectId}
          onViewSource={handleOpenSourceViewer}
          onSwitchToGraph={() => setActiveTab('graph')}
        />
      ) : activeTab === 'chat' ? (
        /* Repository Chat Q&A View (Phase 9d) */
        <ChatRepository
          projectId={activeProjectId}
          onOpenSourceViewer={handleOpenSourceViewer}
        />
      ) : (
        /* Repository Documentation View (Phase 10) */
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 bg-slate-950">
          <div className="max-w-6xl mx-auto">
            <DocumentationViewer
              projectId={activeProjectId}
              onTriggerAnalysis={handleTriggerAnalysis}
              isAnalyzing={isAnalyzing}
            />
          </div>
        </div>
      )}


      {/* Source Code Viewer Modal (with line highlighting) */}
      <SourceViewerModal
        isOpen={!!sourceModalFile}
        onClose={() => {
          setSourceModalFile(null);
          setSourceModalHighlight(null);
        }}
        projectId={activeProjectId}
        filePath={sourceModalFile}
        highlightRange={sourceModalHighlight}
      />
    </div>
  );
}
