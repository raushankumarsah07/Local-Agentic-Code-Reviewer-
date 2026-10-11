import React, { useEffect, useState } from 'react';
import { X, FileCode, Globe, Code2, ArrowDownRight, ArrowUpRight, BookOpen, Layers, Eye, Loader2 } from 'lucide-react';
import { api } from '../api/client';

export default function NodeDetailPanel({
  node,
  allEdges = [],
  projectId,
  onClose,
  onViewSource,
}) {
  const [astData, setAstData] = useState(null);
  const [loadingAst, setLoadingAst] = useState(false);

  useEffect(() => {
    if (node && !node.is_external && node.path) {
      loadAst();
    } else {
      setAstData(null);
    }
  }, [node]);

  const loadAst = async () => {
    setLoadingAst(true);
    try {
      const data = await api.getFileAst(projectId, node.path);
      setAstData(data);
    } catch {
      setAstData(null);
    } finally {
      setLoadingAst(false);
    }
  };

  if (!node) return null;

  // Dependents: other files in graph that import this file (edges pointing TO this node)
  const dependents = allEdges
    .filter((e) => e.target === node.id)
    .map((e) => ({ source: e.source, symbols: e.imported_symbols }));

  // Dependencies: files or libraries that this file imports (edges pointing FROM this node)
  const dependencies = allEdges
    .filter((e) => e.source === node.id)
    .map((e) => ({ target: e.target, symbols: e.imported_symbols, isExternal: e.is_external }));

  return (
    <aside className="w-96 bg-slate-900/95 border-l border-slate-800 h-full flex flex-col shadow-2xl backdrop-blur z-30 transition-all">
      {/* Header */}
      <div className="p-5 border-b border-slate-800 flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-brand-400 shrink-0">
            {node.is_external ? <Globe className="h-5 w-5" /> : <FileCode className="h-5 w-5" />}
          </div>
          <div className="overflow-hidden">
            <h3 className="font-bold text-white text-base truncate">{node.label}</h3>
            <p className="text-xs text-slate-400 font-mono truncate">{node.path || 'external package'}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 gap-2 p-4 bg-slate-950/60 border-b border-slate-800 text-xs">
        <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800/80">
          <span className="text-slate-500 block mb-0.5 flex items-center gap-1">
            <ArrowDownRight className="h-3 w-3 text-emerald-400" />
            In-Degree (Imported by)
          </span>
          <strong className="text-base text-white">{node.in_degree}</strong> files
        </div>
        <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800/80">
          <span className="text-slate-500 block mb-0.5 flex items-center gap-1">
            <ArrowUpRight className="h-3 w-3 text-indigo-400" />
            Out-Degree (Imports)
          </span>
          <strong className="text-base text-white">{node.out_degree}</strong> modules
        </div>
      </div>

      {/* Source View Button */}
      {!node.is_external && (
        <div className="p-4 border-b border-slate-800">
          <button
            onClick={() => onViewSource(node.path)}
            className="w-full flex items-center justify-center space-x-2 px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition shadow-lg shadow-brand-500/10 active:scale-98"
          >
            <Eye className="h-4 w-4" />
            <span>View Source Code with Line Numbers</span>
          </button>
        </div>
      )}

      {/* Content Scrollable Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6 text-sm">
        {/* AST Functions & Classes */}
        {!node.is_external && (
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Code2 className="h-3.5 w-3.5 text-brand-400" />
              AST Code Entities
            </h4>

            {loadingAst ? (
              <div className="flex items-center space-x-2 text-xs text-slate-400 py-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Extracting AST symbols...</span>
              </div>
            ) : astData ? (
              <div className="space-y-3">
                {/* Classes */}
                {astData.classes?.length > 0 && (
                  <div>
                    <span className="text-xs text-slate-500 font-medium block mb-1.5">
                      Classes ({astData.classes.length}):
                    </span>
                    <div className="space-y-1.5">
                      {astData.classes.map((cls) => (
                        <div
                          key={cls.name}
                          className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs"
                        >
                          <div className="font-mono font-semibold text-emerald-300">
                            class {cls.name}
                            {cls.bases?.length > 0 && (
                              <span className="text-slate-400 font-normal">
                                ({cls.bases.join(', ')})
                              </span>
                            )}
                          </div>
                          {cls.methods?.length > 0 && (
                            <p className="text-[11px] text-slate-400 mt-1">
                              Methods: {cls.methods.map((m) => m.name).join(', ')}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Functions */}
                {astData.functions?.length > 0 && (
                  <div>
                    <span className="text-xs text-slate-500 font-medium block mb-1.5">
                      Functions ({astData.functions.length}):
                    </span>
                    <div className="space-y-1.5">
                      {astData.functions.map((fn) => (
                        <div
                          key={fn.name}
                          className="p-2 rounded-lg bg-slate-800/40 border border-slate-700/40 text-xs font-mono text-indigo-300 truncate"
                        >
                          def {fn.name}({fn.params?.join(', ') || ''})
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {astData.classes?.length === 0 && astData.functions?.length === 0 && (
                  <p className="text-xs text-slate-500 italic">No classes or top-level functions defined.</p>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No AST data available.</p>
            )}
          </div>
        )}

        {/* Dependents (Who imports this) */}
        <div>
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-emerald-400" />
            Dependents ({dependents.length})
          </h4>
          {dependents.length > 0 ? (
            <div className="space-y-1.5">
              {dependents.map((dep, idx) => (
                <div
                  key={idx}
                  className="p-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-xs"
                >
                  <p className="font-mono text-slate-200 truncate">{dep.source}</p>
                  {dep.symbols?.length > 0 && (
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      imports: {dep.symbols.join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No internal files import this module directly.</p>
          )}
        </div>

        {/* Dependencies (What this file imports) */}
        <div>
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <BookOpen className="h-3.5 w-3.5 text-indigo-400" />
            Dependencies ({dependencies.length})
          </h4>
          {dependencies.length > 0 ? (
            <div className="space-y-1.5">
              {dependencies.map((dep, idx) => (
                <div
                  key={idx}
                  className="p-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-xs flex items-center justify-between"
                >
                  <span className="font-mono text-slate-200 truncate">{dep.target}</span>
                  {dep.isExternal && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-700 text-slate-300 rounded">
                      external
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">This file imports no modules.</p>
          )}
        </div>
      </div>
    </aside>
  );
}
