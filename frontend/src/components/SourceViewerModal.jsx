import React, { useEffect, useRef, useState } from 'react';
import { X, Copy, Check, FileCode, AlertCircle, Loader2, Sparkles, AlertTriangle } from 'lucide-react';
import { api } from '../api/client';

export default function SourceViewerModal({
  isOpen,
  onClose,
  projectId,
  filePath,
  highlightRange = null,
}) {
  const [fileData, setFileData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const highlightedRowRef = useRef(null);

  // Local LLM explanation state in Source Viewer
  const [explanation, setExplanation] = useState(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState(null);
  const [showExplanationCard, setShowExplanationCard] = useState(false);

  useEffect(() => {
    if (isOpen && highlightRange?.id) {
      // Attempt to load existing explanation if available
      api.getFindingExplanation(highlightRange.id)
        .then((data) => {
          setExplanation(data);
          setShowExplanationCard(true);
        })
        .catch(() => {
          setExplanation(null);
          setShowExplanationCard(false);
        });
    } else {
      setExplanation(null);
      setShowExplanationCard(false);
    }
  }, [isOpen, highlightRange?.id]);

  const handleExplainCurrentFinding = async () => {
    if (!highlightRange?.id || explaining) return;
    setExplaining(true);
    setExplainError(null);
    setShowExplanationCard(true);
    try {
      const result = await api.explainFinding(highlightRange.id, true);
      setExplanation(result);
    } catch (err) {
      setExplainError(err.message || 'Failed to explain finding with local LLM');
    } finally {
      setExplaining(false);
    }
  };

  useEffect(() => {
    if (isOpen && projectId && filePath) {
      loadFile();
    } else {
      setFileData(null);
      setError(null);
    }
  }, [isOpen, projectId, filePath]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Scroll to highlighted line once file lines are rendered
  useEffect(() => {
    if (fileData && highlightRange?.start && highlightedRowRef.current) {
      setTimeout(() => {
        highlightedRowRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
      }, 120);
    }
  }, [fileData, highlightRange]);

  const loadFile = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSourceFile(projectId, filePath);
      setFileData(data);
    } catch (err) {
      setError(err.message || 'Failed to load source file');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!fileData?.raw_content) return;
    navigator.clipboard.writeText(fileData.raw_content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const scrollToHighlight = () => {
    highlightedRowRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    });
  };

  if (!isOpen) return null;

  const severityColorClass = () => {
    const sev = highlightRange?.severity?.toLowerCase();
    if (sev === 'critical') return 'bg-rose-500/20 border-l-4 border-rose-500 text-rose-100 font-semibold';
    if (sev === 'high') return 'bg-orange-500/20 border-l-4 border-orange-500 text-orange-100 font-semibold';
    if (sev === 'medium') return 'bg-amber-500/20 border-l-4 border-amber-400 text-amber-100 font-semibold';
    return 'bg-blue-500/20 border-l-4 border-blue-400 text-blue-100 font-semibold';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 lg:p-8 bg-slate-950/80 backdrop-blur-sm animate-fadeIn">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-5xl h-[88vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/70">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="h-9 w-9 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center shrink-0">
              <FileCode className="h-5 w-5" />
            </div>
            <div className="overflow-hidden">
              <div className="flex items-center space-x-2">
                <h3 className="font-semibold text-white text-base truncate font-mono">{filePath}</h3>
              </div>
              {fileData && (
                <div className="flex items-center space-x-3 text-xs text-slate-400 mt-0.5">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-brand-300 font-medium uppercase text-[10px]">
                    {fileData.language || 'text'}
                  </span>
                  <span>{fileData.total_lines} lines</span>
                  <span>{(fileData.size_bytes / 1024).toFixed(1)} KB</span>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-2 shrink-0">
            {fileData && (
              <button
                onClick={handleCopy}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition"
                title="Copy entire file contents"
              >
                {copied ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5 text-slate-400" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            )}

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Close modal (Esc)"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Highlight Banner if viewing a finding */}
        {highlightRange?.start && (
          <div className="px-6 py-2.5 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex items-center space-x-2 truncate">
              <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
              <span className="text-slate-300">
                Flagged Finding: <strong className="text-white">{highlightRange.title || 'Potential Finding'}</strong>
              </span>
              <span className="text-slate-400">
                (Lines {highlightRange.start}{highlightRange.end && highlightRange.end !== highlightRange.start ? `–${highlightRange.end}` : ''})
              </span>
            </div>
            
            <div className="flex items-center space-x-2">
              {highlightRange.id && (
                <button
                  onClick={handleExplainCurrentFinding}
                  disabled={explaining}
                  className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-xs font-medium transition disabled:opacity-50"
                  title="Generate or reload AI explanation"
                >
                  {explaining ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Running local model...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                      <span>{explanation ? 'Re-Explain' : 'Explain'}</span>
                    </>
                  )}
                </button>
              )}

              <button
                onClick={scrollToHighlight}
                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-brand-300 font-mono text-[11px] transition shrink-0"
              >
                Scroll to Line {highlightRange.start}
              </button>
            </div>
          </div>
        )}

        {/* AI Explanation Card in Source Viewer */}
        {showExplanationCard && (
          <div className="px-6 py-3 bg-slate-900/90 border-b border-slate-800 max-h-56 overflow-y-auto text-xs">
            {explaining ? (
              <div className="flex items-center space-x-2.5 text-indigo-300 py-2">
                <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                <span className="font-medium">Running local model... Analyzing finding context</span>
              </div>
            ) : explainError ? (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 space-y-1">
                <div className="flex items-center justify-between font-semibold">
                  <span>Failed to generate explanation</span>
                  <button onClick={() => setExplainError(null)} className="text-slate-400 hover:text-white">✕</button>
                </div>
                <p className="text-[11px]">{explainError}</p>
                <p className="text-[10px] text-slate-400 font-mono mt-1">
                  Start server: llama-server -m /path/to/model.gguf --port 8080 -c 4096
                </p>
              </div>
            ) : explanation?.explanation ? (
              <div className="p-3.5 rounded-xl bg-slate-950/70 border border-indigo-500/30 space-y-2">
                <div className="flex items-center justify-between pb-1.5 border-b border-slate-800">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="h-4 w-4 text-indigo-400" />
                    <span className="font-semibold text-white">Local LLM Explanation</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      AI-generated explanation, verify before acting
                    </span>
                  </div>
                  <div className="flex items-center space-x-2 text-[11px] text-slate-400 font-mono">
                    <span>{explanation.model_name}</span>
                    <span>•</span>
                    <span>{(explanation.latency_ms / 1000).toFixed(1)}s</span>
                    <button
                      onClick={() => setShowExplanationCard(false)}
                      className="ml-2 text-slate-400 hover:text-white"
                      title="Collapse"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 text-slate-300 pt-1">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">Problem</span>
                    <p className="mt-0.5 leading-relaxed">{explanation.explanation.problem}</p>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-amber-500/80 tracking-wider block">Risk</span>
                    <p className="mt-0.5 leading-relaxed">{explanation.explanation.risk}</p>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-emerald-500/80 tracking-wider block">Recommended Fix</span>
                    <p className="mt-0.5 leading-relaxed">{explanation.explanation.recommended_fix}</p>
                  </div>
                </div>

                {explanation.explanation.confidence_note && (
                  <div className="text-[11px] text-slate-400 italic pt-1 border-t border-slate-800/60">
                    Note: {explanation.explanation.confidence_note}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}

        {/* Modal Content */}
        <div className="flex-1 overflow-auto bg-slate-950 p-4 font-mono text-xs">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full space-y-3 text-slate-400">
              <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
              <p>Fetching source code with line numbers...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full space-y-3 text-rose-400">
              <AlertCircle className="h-10 w-10 text-rose-500" />
              <p className="font-semibold text-sm">Failed to Load Source</p>
              <p className="text-xs text-slate-400 max-w-md text-center">{error}</p>
              <button
                onClick={loadFile}
                className="px-4 py-1.5 rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 text-xs transition"
              >
                Retry
              </button>
            </div>
          ) : fileData ? (
            <div className="min-w-full inline-block">
              <table className="border-collapse w-full">
                <tbody>
                  {fileData.lines.map((line) => {
                    const isHighlighted =
                      highlightRange &&
                      line.line_number >= highlightRange.start &&
                      line.line_number <= (highlightRange.end || highlightRange.start);
                    const isFirstHighlighted = highlightRange && line.line_number === highlightRange.start;

                    return (
                      <tr
                        key={line.line_number}
                        ref={isFirstHighlighted ? highlightedRowRef : null}
                        className={`transition-colors ${
                          isHighlighted
                            ? severityColorClass()
                            : 'hover:bg-slate-900/60'
                        }`}
                      >
                        <td
                          className={`w-14 pr-3 text-right select-none font-mono text-xs border-r ${
                            isHighlighted
                              ? 'text-amber-300 font-bold border-amber-500/50 bg-amber-500/10'
                              : 'text-slate-600 border-slate-800/80'
                          }`}
                        >
                          {line.line_number}
                        </td>
                        <td className="pl-4 pr-4 text-slate-200 whitespace-pre font-mono text-xs leading-relaxed">
                          {line.content || ' '}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
