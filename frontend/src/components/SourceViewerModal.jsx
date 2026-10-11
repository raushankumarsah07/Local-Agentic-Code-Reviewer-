import React, { useEffect, useState } from 'react';
import { X, Copy, Check, FileCode, AlertCircle, Loader2 } from 'lucide-react';
import { api } from '../api/client';

export default function SourceViewerModal({ isOpen, onClose, projectId, filePath }) {
  const [fileData, setFileData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 lg:p-8 bg-slate-950/80 backdrop-blur-sm animate-fadeIn">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="h-9 w-9 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center shrink-0">
              <FileCode className="h-5 w-5" />
            </div>
            <div className="overflow-hidden">
              <h3 className="font-semibold text-white text-base truncate font-mono">{filePath}</h3>
              {fileData && (
                <div className="flex items-center space-x-3 text-xs text-slate-400 mt-0.5">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-brand-300 font-medium uppercase">
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
                  {fileData.lines.map((line) => (
                    <tr key={line.line_number} className="hover:bg-slate-900/60 transition-colors">
                      <td className="w-12 pr-4 text-right select-none text-slate-600 border-r border-slate-800/80 font-mono text-xs">
                        {line.line_number}
                      </td>
                      <td className="pl-4 text-slate-200 whitespace-pre font-mono text-xs leading-relaxed">
                        {line.content || ' '}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
