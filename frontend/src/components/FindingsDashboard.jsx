import React, { useState, useEffect, useMemo } from 'react';
import {
  ShieldAlert,
  Zap,
  Ghost,
  Repeat,
  Share2,
  AlertTriangle,
  CheckCircle2,
  Filter,
  Search,
  RefreshCw,
  Play,
  FileCode,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Loader2,
  Info,
  X,
  SlidersHorizontal,
  Code2,
  Sparkles,
  Cpu,
  Brain,
  Copy,
  Check,
} from 'lucide-react';
import { api } from '../api/client';

export default function FindingsDashboard({
  projectId,
  onViewSource,
  onSwitchToGraph,
}) {
  const activeProjectId = typeof projectId === 'object' && projectId !== null
    ? (projectId.project_id || projectId.id || '')
    : String(projectId || '');

  const [findings, setFindings] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzingTask, setAnalyzingTask] = useState('');
  const [error, setError] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  // Filters State
  const [selectedType, setSelectedType] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');
  const [selectedFile, setSelectedFile] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFindingIds, setExpandedFindingIds] = useState(new Set());

  // LLM Explanations State
  const [explanationsMap, setExplanationsMap] = useState({});
  const [loadingExplainIds, setLoadingExplainIds] = useState(new Set());
  const [explainErrorMap, setExplainErrorMap] = useState({});
  const [batchExplaining, setBatchExplaining] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  // Load findings and summary data
  const loadData = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const [findingsRes, summaryRes] = await Promise.all([
        api.getFindings(activeProjectId, { limit: 1000 }),
        api.getFindingsSummary(activeProjectId),
      ]);
      setFindings(findingsRes.findings || []);
      setSummary(summaryRes);
    } catch (err) {
      setError(err.message || 'Failed to load static analysis findings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeProjectId]);

  // Run all analyzers sequentially with progress indicator
  const handleRunAllAnalyzers = async () => {
    if (!activeProjectId) return;
    setAnalyzing(true);
    try {
      setAnalyzingTask('Running McCabe Complexity Analyzer...');
      await api.analyzeComplexity(activeProjectId);

      setAnalyzingTask('Detecting Dead-Code Candidates...');
      await api.analyzeDeadCode(activeProjectId);

      setAnalyzingTask("Running Tarjan's Architecture Analysis...");
      await api.analyzeArchitecture(activeProjectId);

      setAnalyzingTask('Executing Bandit & AST Security Scanner...');
      await api.analyzeSecurity(activeProjectId);

      setToastMessage('All 4 analysis engines completed successfully!');
      setTimeout(() => setToastMessage(null), 5000);
      await loadData();
    } catch (err) {
      alert(`Analysis run failed: ${err.message}`);
    } finally {
      setAnalyzing(false);
      setAnalyzingTask('');
    }
  };

  const handleRunSingleAnalyzer = async (type) => {
    if (!activeProjectId) return;
    setAnalyzing(true);
    try {
      if (type === 'complexity') {
        setAnalyzingTask('Analyzing cyclomatic complexity...');
        await api.analyzeComplexity(activeProjectId);
      } else if (type === 'dead_code') {
        setAnalyzingTask('Scanning dead-code candidates...');
        await api.analyzeDeadCode(activeProjectId);
      } else if (type === 'architecture') {
        setAnalyzingTask('Analyzing architecture cycles & coupling...');
        await api.analyzeArchitecture(activeProjectId);
      } else if (type === 'security') {
        setAnalyzingTask('Running Bandit & AST security scan...');
        await api.analyzeSecurity(activeProjectId);
      }
      await loadData();
      setToastMessage(`${type.replace('_', ' ').toUpperCase()} analysis refreshed.`);
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err) {
      alert(`Analysis failed: ${err.message}`);
    } finally {
      setAnalyzing(false);
      setAnalyzingTask('');
    }
  };

  // Explain single finding with local LLM
  const handleExplainFinding = async (findingId, force = false) => {
    setLoadingExplainIds((prev) => new Set(prev).add(findingId));
    setExplainErrorMap((prev) => {
      const next = { ...prev };
      delete next[findingId];
      return next;
    });

    try {
      const result = await api.explainFinding(findingId, force);
      setExplanationsMap((prev) => ({
        ...prev,
        [findingId]: result,
      }));
      // Expand row if not already expanded
      setExpandedFindingIds((prev) => new Set(prev).add(findingId));
    } catch (err) {
      setExplainErrorMap((prev) => ({
        ...prev,
        [findingId]: err.message || 'Local model server error.',
      }));
    } finally {
      setLoadingExplainIds((prev) => {
        const next = new Set(prev);
        next.delete(findingId);
        return next;
      });
    }
  };

  // Batch explain all findings for project sequentially
  const handleBatchExplain = async () => {
    if (!activeProjectId) return;
    setBatchExplaining(true);
    setToastMessage('Running sequential local model batch explanations...');
    try {
      const res = await api.explainBatch(activeProjectId, { limit: 10, force: false });
      setToastMessage(
        `Batch complete: ${res.successful} explained, ${res.fallback_count} fallbacks, ${res.failed} errors.`
      );
      // Map results
      const newMap = { ...explanationsMap };
      res.results.forEach((item) => {
        if (item.explanation) {
          newMap[item.finding_id] = {
            id: item.finding_id,
            finding_id: item.finding_id,
            model_name: 'llama3.2',
            prompt_version: 'v1.0',
            explanation: item.explanation,
            latency_ms: item.latency_ms,
            tokens: 0,
            status: item.status,
            created_at: new Date().toISOString(),
          };
        }
      });
      setExplanationsMap(newMap);
      setTimeout(() => setToastMessage(null), 6000);
    } catch (err) {
      alert(`Batch explanation error: ${err.message}`);
    } finally {
      setBatchExplaining(false);
    }
  };

  // Toggle row expansion (and load cached explanation if available)
  const toggleExpand = async (id) => {
    setExpandedFindingIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        // If not already fetched, check DB for cached explanation
        if (!explanationsMap[id] && !loadingExplainIds.has(id)) {
          api
            .getFindingExplanation(id)
            .then((data) => {
              setExplanationsMap((m) => ({ ...m, [id]: data }));
            })
            .catch(() => {
              // Not yet explained, leave empty until user clicks Explain
            });
        }
      }
      return next;
    });
  };

  // Unique files for dropdown filter
  const uniqueFiles = useMemo(() => {
    const files = new Set();
    findings.forEach((f) => {
      if (f.file) files.add(f.file);
    });
    return Array.from(files).sort();
  }, [findings]);

  // Filtered Findings list
  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      if (selectedType !== 'all' && f.type !== selectedType) return false;
      if (selectedSeverity !== 'all' && f.severity !== selectedSeverity) return false;
      if (selectedFile !== 'all' && f.file !== selectedFile) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const titleMatch = (f.title || '').toLowerCase().includes(q);
        const fileMatch = (f.file || '').toLowerCase().includes(q);
        const snippetMatch = (f.evidence_snippet || '').toLowerCase().includes(q);
        const explMatch = (f.explanation || '').toLowerCase().includes(q);
        if (!titleMatch && !fileMatch && !snippetMatch && !explMatch) return false;
      }
      return true;
    });
  }, [findings, selectedType, selectedSeverity, selectedFile, searchQuery]);

  // Severity Helper Styles
  const getSeverityBadge = (severity) => {
    const s = (severity || '').toLowerCase();
    switch (s) {
      case 'critical':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      case 'high':
        return 'bg-orange-500/10 text-orange-400 border-orange-500/30';
      case 'medium':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'low':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
      default:
        return 'bg-slate-500/10 text-slate-400 border-slate-500/30';
    }
  };

  const getTypeIcon = (type) => {
    switch (type) {
      case 'security':
        return <ShieldAlert className="h-4 w-4 text-rose-400" />;
      case 'complexity':
        return <Zap className="h-4 w-4 text-amber-400" />;
      case 'dead_code':
        return <Ghost className="h-4 w-4 text-indigo-400" />;
      case 'cycle':
        return <Repeat className="h-4 w-4 text-purple-400" />;
      case 'coupling':
        return <Share2 className="h-4 w-4 text-cyan-400" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-slate-400" />;
    }
  };

  const getTypeLabel = (type) => {
    switch (type) {
      case 'security':
        return 'Security';
      case 'complexity':
        return 'Complexity';
      case 'dead_code':
        return 'Dead Code';
      case 'cycle':
        return 'Cycle';
      case 'coupling':
        return 'God Module';
      default:
        return type;
    }
  };

  // Severity counts
  const sevCounts = summary?.by_severity || {};
  const criticalCount = sevCounts['Critical'] || 0;
  const highCount = sevCounts['High'] || 0;
  const mediumCount = sevCounts['Medium'] || 0;
  const lowCount = sevCounts['Low'] || 0;
  const infoCount = sevCounts['Info'] || 0;
  const totalCount = summary?.total || findings.length;

  // Category counts
  const typeCounts = summary?.by_type || {};

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950 text-slate-100">
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

      {/* Main Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6">
        {/* Top Header & Action Controls */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 backdrop-blur">
          <div>
            <div className="flex items-center space-x-2.5">
              <div className="h-8 w-8 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                <SlidersHorizontal className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white tracking-tight">
                  Static Code Review & Grounded LLM Explanations
                </h2>
                <p className="text-xs text-slate-400">
                  Deterministic analysis decides facts; local llama.cpp explains findings grounded in code evidence.
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Batch Explain Button */}
            <button
              onClick={handleBatchExplain}
              disabled={batchExplaining || findings.length === 0}
              className="inline-flex items-center space-x-2 px-3 py-2 rounded-xl bg-purple-600/80 hover:bg-purple-600 text-white text-xs font-semibold shadow-md transition disabled:opacity-50"
              title="Explain findings sequentially using local llama-server"
            >
              {batchExplaining ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Explaining Batch...</span>
                </>
              ) : (
                <>
                  <Brain className="h-3.5 w-3.5" />
                  <span>Batch Explain (LLM)</span>
                </>
              )}
            </button>

            {/* Run All Analyzers */}
            <button
              onClick={handleRunAllAnalyzers}
              disabled={analyzing}
              className="inline-flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-brand-500/20 transition disabled:opacity-50"
            >
              {analyzing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>{analyzingTask || 'Analyzing...'}</span>
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5 fill-current" />
                  <span>Run All Engines</span>
                </>
              )}
            </button>

            {/* Individual Triggers */}
            <div className="hidden sm:flex items-center space-x-1 bg-slate-800/70 p-1 rounded-xl border border-slate-700/60 text-xs">
              <button
                onClick={() => handleRunSingleAnalyzer('complexity')}
                disabled={analyzing}
                className="px-2 py-1 rounded-lg hover:bg-slate-700 text-slate-300 transition"
                title="Run McCabe Cyclomatic Complexity"
              >
                Complexity
              </button>
              <button
                onClick={() => handleRunSingleAnalyzer('dead_code')}
                disabled={analyzing}
                className="px-2 py-1 rounded-lg hover:bg-slate-700 text-slate-300 transition"
                title="Run Graph Reachability & Vulture Dead Code"
              >
                Dead Code
              </button>
              <button
                onClick={() => handleRunSingleAnalyzer('architecture')}
                disabled={analyzing}
                className="px-2 py-1 rounded-lg hover:bg-slate-700 text-slate-300 transition"
                title="Run Tarjan's SCC & God Modules"
              >
                Architecture
              </button>
              <button
                onClick={() => handleRunSingleAnalyzer('security')}
                disabled={analyzing}
                className="px-2 py-1 rounded-lg hover:bg-slate-700 text-slate-300 transition"
                title="Run Bandit & AST Security Rules"
              >
                Security
              </button>
            </div>

            <button
              onClick={loadData}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              title="Refresh findings"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* 1. Summary Cards Metric Row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
          {/* Total Findings */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm hover:border-slate-700 transition">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Total Findings</span>
            <div className="flex items-baseline justify-between mt-2">
              <span className="text-2xl font-bold text-white font-mono">{totalCount}</span>
              <span className="text-xs text-slate-500">{uniqueFiles.length} files</span>
            </div>
          </div>

          {/* Critical */}
          <div
            onClick={() => setSelectedSeverity(selectedSeverity === 'Critical' ? 'all' : 'Critical')}
            className={`cursor-pointer bg-slate-900/80 border rounded-2xl p-4 transition shadow-sm ${
              selectedSeverity === 'Critical'
                ? 'border-rose-500 bg-rose-950/20 shadow-rose-950/50'
                : 'border-slate-800 hover:border-rose-500/50'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-rose-400 uppercase tracking-wider">Critical</span>
              <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
            </div>
            <div className="text-2xl font-bold text-rose-400 mt-2 font-mono">{criticalCount}</div>
          </div>

          {/* High */}
          <div
            onClick={() => setSelectedSeverity(selectedSeverity === 'High' ? 'all' : 'High')}
            className={`cursor-pointer bg-slate-900/80 border rounded-2xl p-4 transition shadow-sm ${
              selectedSeverity === 'High'
                ? 'border-orange-500 bg-orange-950/20'
                : 'border-slate-800 hover:border-orange-500/50'
            }`}
          >
            <span className="text-[11px] font-medium text-orange-400 uppercase tracking-wider">High</span>
            <div className="text-2xl font-bold text-orange-400 mt-2 font-mono">{highCount}</div>
          </div>

          {/* Medium */}
          <div
            onClick={() => setSelectedSeverity(selectedSeverity === 'Medium' ? 'all' : 'Medium')}
            className={`cursor-pointer bg-slate-900/80 border rounded-2xl p-4 transition shadow-sm ${
              selectedSeverity === 'Medium'
                ? 'border-amber-500 bg-amber-950/20'
                : 'border-slate-800 hover:border-amber-500/50'
            }`}
          >
            <span className="text-[11px] font-medium text-amber-400 uppercase tracking-wider">Medium</span>
            <div className="text-2xl font-bold text-amber-400 mt-2 font-mono">{mediumCount}</div>
          </div>

          {/* Low & Info */}
          <div
            onClick={() => setSelectedSeverity(selectedSeverity === 'Low' ? 'all' : 'Low')}
            className={`cursor-pointer bg-slate-900/80 border rounded-2xl p-4 transition shadow-sm col-span-2 sm:col-span-1 ${
              selectedSeverity === 'Low'
                ? 'border-blue-500 bg-blue-950/20'
                : 'border-slate-800 hover:border-blue-500/50'
            }`}
          >
            <span className="text-[11px] font-medium text-blue-400 uppercase tracking-wider">Low / Info</span>
            <div className="text-2xl font-bold text-blue-400 mt-2 font-mono">{lowCount + infoCount}</div>
          </div>
        </div>

        {/* 2. Visual Interactive Charts Dashboard */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Chart A: Severity Breakdown Bar Chart */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Severity Distribution</h3>
                <p className="text-[11px] text-slate-400">Click a bar to filter findings table</p>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">{totalCount} total</span>
            </div>

            <div className="space-y-3 pt-1">
              {[
                { label: 'Critical', count: criticalCount, color: 'bg-rose-500', text: 'text-rose-400', key: 'Critical' },
                { label: 'High', count: highCount, color: 'bg-orange-500', text: 'text-orange-400', key: 'High' },
                { label: 'Medium', count: mediumCount, color: 'bg-amber-400', text: 'text-amber-400', key: 'Medium' },
                { label: 'Low', count: lowCount, color: 'bg-blue-400', text: 'text-blue-400', key: 'Low' },
                { label: 'Info', count: infoCount, color: 'bg-slate-400', text: 'text-slate-400', key: 'Info' },
              ].map((item) => {
                const pct = totalCount > 0 ? Math.round((item.count / totalCount) * 100) : 0;
                const isSelected = selectedSeverity === item.key;

                return (
                  <div
                    key={item.label}
                    onClick={() => setSelectedSeverity(isSelected ? 'all' : item.key)}
                    className={`group cursor-pointer p-2 rounded-xl transition ${
                      isSelected ? 'bg-slate-800/90 ring-1 ring-slate-700' : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1.5 font-medium">
                      <span className={item.text}>{item.label}</span>
                      <div className="flex items-center space-x-2 text-slate-400 font-mono text-[11px]">
                        <span>{item.count}</span>
                        <span>({pct}%)</span>
                      </div>
                    </div>
                    <div className="h-2 w-full bg-slate-950 rounded-full overflow-hidden border border-slate-800/80">
                      <div
                        className={`h-full ${item.color} rounded-full transition-all duration-500`}
                        style={{ width: `${Math.max(item.count > 0 ? 4 : 0, pct)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Chart B: Category Breakdown Chart */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Engine Category Breakdown</h3>
                <p className="text-[11px] text-slate-400">Click a category card to filter</p>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">5 Engines</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {[
                { type: 'security', label: 'Security (Bandit/AST)', count: typeCounts['security'] || 0, icon: ShieldAlert, color: 'text-rose-400 border-rose-500/30' },
                { type: 'complexity', label: 'Complexity (McCabe)', count: typeCounts['complexity'] || 0, icon: Zap, color: 'text-amber-400 border-amber-500/30' },
                { type: 'dead_code', label: 'Dead Code (Reachability)', count: typeCounts['dead_code'] || 0, icon: Ghost, color: 'text-indigo-400 border-indigo-500/30' },
                { type: 'cycle', label: 'Architecture Cycles', count: typeCounts['cycle'] || 0, icon: Repeat, color: 'text-purple-400 border-purple-500/30' },
                { type: 'coupling', label: 'God Modules (Coupling)', count: typeCounts['coupling'] || 0, icon: Share2, color: 'text-cyan-400 border-cyan-500/30' },
              ].map((cat) => {
                const Icon = cat.icon;
                const isSelected = selectedType === cat.type;
                const pct = totalCount > 0 ? Math.round((cat.count / totalCount) * 100) : 0;

                return (
                  <div
                    key={cat.type}
                    onClick={() => setSelectedType(isSelected ? 'all' : cat.type)}
                    className={`cursor-pointer p-3 rounded-xl border transition flex items-center justify-between ${
                      isSelected
                        ? 'bg-slate-800 border-brand-500/60 shadow-md'
                        : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700 hover:bg-slate-800/40'
                    }`}
                  >
                    <div className="flex items-center space-x-2.5 truncate">
                      <div className={`p-1.5 rounded-lg bg-slate-900 border ${cat.color} shrink-0`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="truncate">
                        <div className="text-xs font-semibold text-slate-200 truncate">{cat.label}</div>
                        <div className="text-[10px] text-slate-500">{pct}% of total findings</div>
                      </div>
                    </div>
                    <span className="text-sm font-bold text-white font-mono ml-2">{cat.count}</span>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
              <span>All findings labeled as potential</span>
              <button
                onClick={() => {
                  setSelectedType('all');
                  setSelectedSeverity('all');
                  setSelectedFile('all');
                  setSearchQuery('');
                }}
                className="text-brand-400 hover:text-brand-300 font-medium transition"
              >
                Clear all filters
              </button>
            </div>
          </div>
        </div>

        {/* 3. Filter Bar & Search */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 backdrop-blur flex flex-wrap items-center justify-between gap-3 shadow-sm">
          {/* Left filters: Type & Severity pills */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Category Dropdown */}
            <div className="flex items-center space-x-1.5 bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs">
              <Filter className="h-3.5 w-3.5 text-slate-400" />
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="bg-transparent text-white focus:outline-none cursor-pointer pr-2"
              >
                <option value="all" className="bg-slate-900 text-white">All Categories ({totalCount})</option>
                <option value="security" className="bg-slate-900 text-white">Security</option>
                <option value="complexity" className="bg-slate-900 text-white">Complexity</option>
                <option value="dead_code" className="bg-slate-900 text-white">Dead Code</option>
                <option value="cycle" className="bg-slate-900 text-white">Architecture Cycles</option>
                <option value="coupling" className="bg-slate-900 text-white">God Modules</option>
              </select>
            </div>

            {/* Severity Dropdown */}
            <div className="flex items-center space-x-1.5 bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs">
              <span className="h-2 w-2 rounded-full bg-brand-400" />
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="bg-transparent text-white focus:outline-none cursor-pointer pr-2"
              >
                <option value="all" className="bg-slate-900 text-white">All Severities</option>
                <option value="Critical" className="bg-slate-900 text-white">Critical ({criticalCount})</option>
                <option value="High" className="bg-slate-900 text-white">High ({highCount})</option>
                <option value="Medium" className="bg-slate-900 text-white">Medium ({mediumCount})</option>
                <option value="Low" className="bg-slate-900 text-white">Low ({lowCount})</option>
                <option value="Info" className="bg-slate-900 text-white">Info ({infoCount})</option>
              </select>
            </div>

            {/* File Dropdown */}
            {uniqueFiles.length > 0 && (
              <div className="flex items-center space-x-1.5 bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs max-w-[220px]">
                <FileCode className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                <select
                  value={selectedFile}
                  onChange={(e) => setSelectedFile(e.target.value)}
                  className="bg-transparent text-white focus:outline-none cursor-pointer truncate pr-2 w-full"
                >
                  <option value="all" className="bg-slate-900 text-white">All Files ({uniqueFiles.length})</option>
                  {uniqueFiles.map((file) => (
                    <option key={file} value={file} className="bg-slate-900 text-white font-mono">
                      {file}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Right: Search box */}
          <div className="relative min-w-[220px] sm:min-w-[280px]">
            <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter findings title, snippet, file..."
              className="w-full pl-8 pr-8 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition"
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
        </div>

        {/* 4. Findings Table */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl shadow-lg overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-white uppercase tracking-wider">Findings List</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                {filteredFindings.length} of {findings.length}
              </span>
            </div>
            {filteredFindings.length !== findings.length && (
              <span className="text-[11px] text-amber-400">Filters active</span>
            )}
          </div>

          {loading ? (
            <div className="p-12 flex flex-col items-center justify-center space-y-3 text-slate-400">
              <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
              <p className="text-xs">Loading static analysis findings...</p>
            </div>
          ) : filteredFindings.length === 0 ? (
            <div className="p-16 text-center space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <h4 className="text-sm font-semibold text-white">No Findings Match Your Filter</h4>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                Try resetting your filters or run all analysis engines using the top control button.
              </p>
              <button
                onClick={() => {
                  setSelectedType('all');
                  setSelectedSeverity('all');
                  setSelectedFile('all');
                  setSearchQuery('');
                }}
                className="mt-2 px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 transition"
              >
                Reset Filters
              </button>
            </div>
          ) : (
            <div className="divide-y divide-slate-800/80">
              {filteredFindings.map((finding) => {
                const isExpanded = expandedFindingIds.has(finding.id);
                const isExplaining = loadingExplainIds.has(finding.id);
                const explanation = explanationsMap[finding.id];
                const explainError = explainErrorMap[finding.id];

                return (
                  <div key={finding.id} className="transition-colors hover:bg-slate-800/30">
                    {/* Primary Row Header */}
                    <div
                      onClick={() => toggleExpand(finding.id)}
                      className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer select-none"
                    >
                      <div className="flex items-start sm:items-center space-x-3 overflow-hidden">
                        <button className="text-slate-400 hover:text-white pt-0.5 sm:pt-0 shrink-0">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </button>

                        {/* Severity Badge */}
                        <span
                          className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border shrink-0 ${getSeverityBadge(
                            finding.severity
                          )}`}
                        >
                          {finding.severity}
                        </span>

                        {/* Category Badge */}
                        <div className="flex items-center space-x-1 text-slate-300 text-xs font-medium shrink-0">
                          {getTypeIcon(finding.type)}
                          <span className="hidden md:inline text-[11px] text-slate-400">
                            {getTypeLabel(finding.type)}
                          </span>
                        </div>

                        {/* Title */}
                        <div className="truncate">
                          <span className="text-xs font-semibold text-white group-hover:text-brand-300 transition truncate block">
                            {finding.title}
                          </span>
                        </div>
                      </div>

                      {/* File Link, AI Action & Source Action */}
                      <div className="flex items-center space-x-2 text-xs shrink-0 pl-7 sm:pl-0">
                        {/* File location */}
                        <span className="font-mono text-slate-400 text-[11px] truncate max-w-[140px] sm:max-w-[200px]">
                          {finding.file}:{finding.start_line}
                          {finding.end_line && finding.end_line !== finding.start_line
                            ? `-${finding.end_line}`
                            : ''}
                        </span>

                        {/* Source Tool Badge */}
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 font-mono hidden lg:inline">
                          {finding.source_tool}
                        </span>

                        {/* AI Explain Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleExplainFinding(finding.id, !!explanation);
                          }}
                          disabled={isExplaining}
                          className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 border border-purple-500/30 text-xs font-medium transition disabled:opacity-50"
                          title="Generate or refresh grounded AI explanation using local llama-server"
                        >
                          {isExplaining ? (
                            <>
                              <Loader2 className="h-3 w-3 animate-spin text-purple-400" />
                              <span className="hidden sm:inline">Running...</span>
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-3 w-3 text-purple-400" />
                              <span>{explanation ? 'Re-Explain' : 'Explain'}</span>
                            </>
                          )}
                        </button>

                        {/* Click-through View Source Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onViewSource(finding.file, {
                              id: finding.id,
                              start: finding.start_line,
                              end: finding.end_line,
                              severity: finding.severity,
                              title: finding.title,
                            });
                          }}
                          className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-xs font-medium transition"
                          title="Open file with highlighted lines"
                        >
                          <FileCode className="h-3.5 w-3.5" />
                          <span className="hidden sm:inline">Line {finding.start_line}</span>
                        </button>
                      </div>
                    </div>

                    {/* Expanded Detail Panel */}
                    {isExpanded && (
                      <div className="px-6 pb-5 pt-2 bg-slate-950/70 border-t border-slate-800/60 space-y-4 animate-fadeIn">
                        {/* 1. Grounded AI Explanation Card (Phase 8 Structured Output) */}
                        {isExplaining ? (
                          <div className="p-4 rounded-xl bg-slate-900/80 border border-purple-500/30 flex items-center justify-center space-x-3 text-xs text-purple-300">
                            <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                            <span>Running local model (llama-server) to explain finding grounded in evidence...</span>
                          </div>
                        ) : explainError ? (
                          <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-500/30 text-xs space-y-2">
                            <div className="flex items-center space-x-2 text-rose-400 font-semibold">
                              <AlertTriangle className="h-4 w-4" />
                              <span>Local LLM Server Unavailable</span>
                            </div>
                            <p className="text-slate-300 font-mono text-[11px] whitespace-pre-wrap">{explainError}</p>
                            <p className="text-slate-400">
                              Start llama-server on localhost and click <strong>Retry Explanation</strong>.
                            </p>
                            <button
                              onClick={() => handleExplainFinding(finding.id, true)}
                              className="mt-2 px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition"
                            >
                              Retry Explanation
                            </button>
                          </div>
                        ) : explanation ? (
                          <div className="bg-slate-900 border border-indigo-500/40 rounded-2xl p-4 shadow-xl space-y-3.5">
                            {/* Card Header with Mandatory Warning Badge */}
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5">
                              <div className="flex items-center space-x-2">
                                <Sparkles className="h-4 w-4 text-purple-400" />
                                <span className="text-xs font-bold text-white uppercase tracking-wider">
                                  AI-Grounded Finding Explanation
                                </span>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/30 font-medium">
                                  AI-generated explanation, verify before acting
                                </span>
                              </div>

                              <div className="flex items-center space-x-3 text-[11px] text-slate-400 font-mono">
                                <span>Model: <strong className="text-slate-200">{explanation.model_name}</strong></span>
                                <span>•</span>
                                <span>Latency: <strong className="text-slate-200">{explanation.latency_ms}ms</strong></span>
                                {explanation.status && (
                                  <>
                                    <span>•</span>
                                    <span className="uppercase text-[10px] text-brand-300">{explanation.status}</span>
                                  </>
                                )}
                              </div>
                            </div>

                            {/* 4 Structured Output Fields */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                              {/* Problem */}
                              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                                <div className="text-[11px] font-bold text-rose-400 uppercase tracking-wider mb-1">
                                  Problem & Defect
                                </div>
                                <p className="text-slate-200 leading-relaxed">
                                  {explanation.explanation.problem}
                                </p>
                              </div>

                              {/* Risk */}
                              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                                <div className="text-[11px] font-bold text-orange-400 uppercase tracking-wider mb-1">
                                  Architectural Risk
                                </div>
                                <p className="text-slate-200 leading-relaxed">
                                  {explanation.explanation.risk}
                                </p>
                              </div>

                              {/* Recommended Fix */}
                              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 md:col-span-2">
                                <div className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider mb-1">
                                  Recommended Remediation
                                </div>
                                <p className="text-slate-200 leading-relaxed font-mono text-[11px] bg-slate-900/90 p-2.5 rounded-lg border border-slate-800/80 whitespace-pre-wrap">
                                  {explanation.explanation.recommended_fix}
                                </p>
                              </div>

                              {/* Confidence Note */}
                              <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 md:col-span-2 text-[11px] text-slate-400">
                                <strong className="text-slate-300">Confidence Note: </strong>
                                {explanation.explanation.confidence_note}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="p-3 rounded-xl bg-slate-900/40 border border-slate-800 flex items-center justify-between">
                            <span className="text-xs text-slate-400">
                              Generate a grounded, structured AI explanation (problem, risk, fix) with local llama-server.
                            </span>
                            <button
                              onClick={() => handleExplainFinding(finding.id)}
                              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium transition"
                            >
                              <Sparkles className="h-3.5 w-3.5" />
                              <span>Explain with Local LLM</span>
                            </button>
                          </div>
                        )}

                        {/* Evidence Snippet */}
                        {finding.evidence_snippet && (
                          <div>
                            <div className="text-[11px] uppercase font-bold text-slate-400 tracking-wider mb-1 flex items-center justify-between">
                              <span>Code Evidence Snippet</span>
                              <span className="text-slate-500 font-mono text-[10px]">
                                Lines {finding.start_line}–{finding.end_line}
                              </span>
                            </div>
                            <div className="bg-slate-950 rounded-xl p-3 border border-slate-800 font-mono text-xs overflow-x-auto text-amber-200/90 whitespace-pre">
                              {finding.evidence_snippet}
                            </div>
                          </div>
                        )}

                        {/* Analysis & Reasoning (Tool Original Text) */}
                        {finding.explanation && (
                          <div>
                            <div className="text-[11px] uppercase font-bold text-slate-400 tracking-wider mb-1">
                              Static Tool Reasoning ({finding.source_tool})
                            </div>
                            <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/80 p-3 rounded-xl border border-slate-800">
                              {finding.explanation}
                            </p>
                          </div>
                        )}

                        {/* Footer details & Action */}
                        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-[11px] text-slate-400">
                          <div className="flex items-center space-x-3">
                            <span>Detected by: <strong className="text-slate-200">{finding.source_tool}</strong></span>
                            <span>•</span>
                            <span>Category: <strong className="text-slate-200">{finding.type}</strong></span>
                          </div>

                          <button
                            onClick={() =>
                              onViewSource(finding.file, {
                                id: finding.id,
                                start: finding.start_line,
                                end: finding.end_line,
                                severity: finding.severity,
                                title: finding.title,
                              })
                            }
                            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-medium text-xs transition"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            <span>Inspect in Source Viewer</span>
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
