import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Download,
  Copy,
  Check,
  RefreshCw,
  FolderTree,
  FileCode,
  Layers,
  Sparkles,
  ChevronRight,
  ChevronDown,
  ShieldAlert,
  ArrowUpRight,
} from 'lucide-react';
import { api } from '../api/client';

export default function DocumentationViewer({ projectId, onTriggerAnalysis, isAnalyzing }) {
  const [docData, setDocData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState('overview'); // 'overview', 'modules', 'markdown'
  const [expandedModules, setExpandedModules] = useState({});

  useEffect(() => {
    loadDocumentation();
  }, [projectId]);

  const loadDocumentation = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getProjectDocumentation(projectId);
      setDocData(data);
      // Expand all modules by default
      if (data?.structure?.modules) {
        const initialExpanded = {};
        data.structure.modules.forEach((m, idx) => {
          initialExpanded[m.module_name] = idx === 0;
        });
        setExpandedModules(initialExpanded);
      }
    } catch (err) {
      console.warn('Documentation not available yet:', err);
      setDocData(null);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopyMarkdown = () => {
    if (!docData?.overview_md) return;
    navigator.clipboard.writeText(docData.overview_md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleModule = (modName) => {
    setExpandedModules((prev) => ({
      ...prev,
      [modName]: !prev[modName],
    }));
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin text-indigo-400 mb-3" />
        <p className="text-sm">Loading repository documentation...</p>
      </div>
    );
  }

  if (!docData) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center max-w-xl mx-auto my-12 backdrop-blur-md">
        <div className="w-14 h-14 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4 text-indigo-400">
          <BookOpen className="w-7 h-7" />
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">Documentation Not Generated Yet</h3>
        <p className="text-sm text-slate-400 mb-6 leading-relaxed">
          The agent pipeline produces a complete hierarchical architecture guide (per-file summaries,
          subsystem modules, and repository overview). Run the automated agent analysis to generate it.
        </p>
        <button
          onClick={onTriggerAnalysis}
          disabled={isAnalyzing}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 text-white font-medium rounded-xl shadow-lg shadow-indigo-500/20 transition-all text-sm cursor-pointer"
        >
          {isAnalyzing ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Agent Analysis in Progress...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Run Agent Workflow & Generate Docs</span>
            </>
          )}
        </button>
      </div>
    );
  }

  const overview = docData.structure?.overview || {};
  const modules = docData.structure?.modules || [];
  const files = docData.structure?.files || [];

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 sm:p-5 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-indigo-400">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              Architecture & Repository Documentation
              <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Phase 10 Map-Reduce
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Generated automatically from AST extraction, dependency graphs, and static reviews.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            onClick={handleCopyMarkdown}
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-3.5 py-2 bg-slate-800/80 hover:bg-slate-700/80 text-slate-200 text-xs font-medium rounded-xl border border-slate-700/60 transition-colors"
            title="Copy Markdown to Clipboard"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied!' : 'Copy Markdown'}</span>
          </button>

          <a
            href={api.getDocumentationDownloadUrl(projectId)}
            download
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-3.5 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white text-xs font-medium rounded-xl shadow-sm transition-all"
            title="Download ARCHITECTURE.md"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download .md</span>
          </a>

          <button
            onClick={loadDocumentation}
            className="p-2 bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 rounded-xl border border-slate-700/60 transition-colors"
            title="Refresh Documentation"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Sub-view Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium transition-colors ${
            activeTab === 'overview'
              ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Executive Overview</span>
        </button>

        <button
          onClick={() => setActiveTab('modules')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium transition-colors ${
            activeTab === 'modules'
              ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <FolderTree className="w-3.5 h-3.5" />
          <span>Subsystems & Modules ({modules.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('markdown')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium transition-colors ${
            activeTab === 'markdown'
              ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <FileCode className="w-3.5 h-3.5" />
          <span>Raw Markdown Report</span>
        </button>
      </div>

      {/* TAB 1: EXECUTIVE OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Key Stat Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block mb-1">
                Scanned Files
              </span>
              <div className="text-2xl font-bold text-white">{overview.total_files || files.length}</div>
              <span className="text-[11px] text-slate-400 mt-1 block">
                Across {modules.length} modules
              </span>
            </div>

            <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block mb-1">
                Source Lines
              </span>
              <div className="text-2xl font-bold text-white">
                {(overview.total_lines || 0).toLocaleString()}
              </div>
              <span className="text-[11px] text-indigo-400 mt-1 block">AST parsed</span>
            </div>

            <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block mb-1">
                AST Classes & Funcs
              </span>
              <div className="text-2xl font-bold text-white">
                {(overview.total_classes || 0) + (overview.total_functions || 0)}
              </div>
              <span className="text-[11px] text-slate-400 mt-1 block">
                {overview.total_classes || 0} classes, {overview.total_functions || 0} funcs
              </span>
            </div>

            <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block mb-1">
                Quality Findings
              </span>
              <div className="text-2xl font-bold text-amber-400">
                {overview.findings_total || 0}
              </div>
              <span className="text-[11px] text-slate-400 mt-1 block">Deterministic checks</span>
            </div>
          </div>

          {/* Entry Points & Core Components */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <ArrowUpRight className="w-4 h-4 text-emerald-400" />
                Detected Entry Points & Public Callers
              </h3>
              {overview.entry_points && overview.entry_points.length > 0 ? (
                <div className="space-y-2">
                  {overview.entry_points.map((ep, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2.5 bg-slate-800/50 border border-slate-700/50 rounded-xl font-mono text-xs text-emerald-300"
                    >
                      <span>{ep}</span>
                      <span className="text-[10px] uppercase font-sans text-slate-400 bg-slate-700/60 px-2 py-0.5 rounded">
                        Executable
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic">No conventional entry point files detected.</p>
              )}
            </div>

            <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-400" />
                Static Findings Posture
              </h3>
              {overview.findings_by_severity && Object.keys(overview.findings_by_severity).length > 0 ? (
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(overview.findings_by_severity).map(([sev, count]) => (
                    <div
                      key={sev}
                      className="p-2.5 bg-slate-800/40 border border-slate-700/40 rounded-xl flex items-center justify-between"
                    >
                      <span className="text-xs text-slate-300 font-medium">{sev}</span>
                      <span className="text-xs font-bold text-amber-300 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
                        {count}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400">Zero static findings flagged for this project.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: MODULES & SUBSYSTEMS ACCORDION */}
      {activeTab === 'modules' && (
        <div className="space-y-4">
          {modules.map((mod) => {
            const isExpanded = !!expandedModules[mod.module_name];
            return (
              <div
                key={mod.module_name}
                className="bg-slate-900/50 border border-slate-800/80 rounded-2xl overflow-hidden transition-all"
              >
                <button
                  onClick={() => toggleModule(mod.module_name)}
                  className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/30 transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg">
                      <FolderTree className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-white font-mono">
                        {mod.module_name}
                      </h4>
                      <p className="text-xs text-slate-400">{mod.role}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right hidden sm:block">
                      <span className="text-xs text-slate-300 font-mono">
                        {mod.file_count} file(s) · {mod.total_lines} lines
                      </span>
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-slate-400" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-slate-400" />
                    )}
                  </div>
                </button>

                {isExpanded && (
                  <div className="p-4 pt-0 border-t border-slate-800/60 bg-slate-950/30 space-y-4">
                    {/* Files inside module */}
                    <div className="pt-3">
                      <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block mb-2">
                        Files in this Module
                      </span>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {mod.files.map((fp) => (
                          <div
                            key={fp}
                            className="p-2 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center gap-2 font-mono text-xs text-slate-300"
                          >
                            <FileCode className="w-3.5 h-3.5 text-indigo-400" />
                            <span>{fp}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Exported symbols */}
                    {(mod.exported_classes.length > 0 || mod.exported_functions.length > 0) && (
                      <div>
                        <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block mb-2">
                          Exported Classes & Functions
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {mod.exported_classes.map((cls) => (
                            <span
                              key={cls}
                              className="px-2 py-1 bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs rounded-md font-mono"
                            >
                              class {cls}
                            </span>
                          ))}
                          {mod.exported_functions.map((fn) => (
                            <span
                              key={fn}
                              className="px-2 py-1 bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 text-xs rounded-md font-mono"
                            >
                              def {fn}()
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 3: RAW MARKDOWN REPORT */}
      {activeTab === 'markdown' && (
        <div className="bg-slate-950/90 border border-slate-800 rounded-2xl p-5 overflow-x-auto">
          <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed">
            {docData.overview_md}
          </pre>
        </div>
      )}
    </div>
  );
}
