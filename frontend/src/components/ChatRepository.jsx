import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  Send,
  Loader2,
  Trash2,
  FileCode,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Info,
  HelpCircle,
  AlertTriangle,
  GitBranch,
  Network,
  CornerDownLeft,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../api/client';

export default function ChatRepository({ projectId, onOpenSourceViewer }) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Hello! I am your offline code architecture assistant. Ask me questions about functions, dependencies, architecture, or security in this repository. All my answers are grounded in indexed code chunks and call graphs, and I will strictly cite file sources as `[file:line-range]`.',
      citations: [],
      retrievedChunks: [],
      graphSummary: '',
      hasSufficientContext: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [enableGraphExpansion, setEnableGraphExpansion] = useState(true);
  const [expandedContexts, setExpandedContexts] = useState({});

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const toggleContextDrawer = (msgId) => {
    setExpandedContexts((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  const handleSendMessage = async (textToSend = null) => {
    const query = (textToSend || inputMessage).trim();
    if (!query || loading) return;

    setError(null);
    setInputMessage('');

    const userTurnId = `user-${Date.now()}`;
    const userMsg = {
      id: userTurnId,
      role: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const updatedHistory = [...messages, userMsg];
    setMessages(updatedHistory);
    setLoading(true);

    try {
      // Build lightweight prior conversation history for backend context
      const chatHistoryPayload = updatedHistory
        .filter((m) => m.id !== 'welcome')
        .slice(-6)
        .map((m) => ({
          role: m.role,
          content: m.content,
        }));

      const res = await api.chatWithRepository(projectId, {
        message: query,
        history: chatHistoryPayload,
        topK: 5,
        enableGraphExpansion,
      });

      const assistantTurnId = `assistant-${Date.now()}`;
      const assistantMsg = {
        id: assistantTurnId,
        role: 'assistant',
        content: res.answer,
        citations: res.citations || [],
        retrievedChunks: res.retrieved_chunks || [],
        graphSummary: res.graph_context_summary || '',
        hasSufficientContext: res.has_sufficient_context,
        latencyMs: res.latency_ms,
        tokensUsed: res.tokens_used,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setError(err.message || 'Failed to get answer from local model.');
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleClearChat = () => {
    setMessages([
      {
        id: 'welcome-reset',
        role: 'assistant',
        content:
          'Chat history cleared. What else would you like to explore in this repository?',
        citations: [],
        retrievedChunks: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    setError(null);
  };

  const sampleQuestions = [
    'Where is login handled?',
    'What are the main entry points of the repository?',
    'How does the calculation engine work?',
    'Are there any hardcoded secrets or insecure functions?',
    'How is cryptocurrency mining configured in this project?',
  ];

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* Top Controls Bar */}
      <div className="px-6 py-3 bg-slate-900/60 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-3 shrink-0 backdrop-blur z-10">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400">
            <MessageSquare className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-semibold text-white tracking-tight">
                Repository Architecture & Code Q&A
              </h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                RAG Active
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Grounded answers strictly cited from AST chunks, call graphs & imported modules
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {/* Call-Graph Expansion Toggle */}
          <button
            onClick={() => setEnableGraphExpansion(!enableGraphExpansion)}
            className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
              enableGraphExpansion
                ? 'bg-brand-500/10 text-brand-300 border-brand-500/30'
                : 'bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200'
            }`}
            title="When active, pulls callers, callees, and importing modules from the architectural graph"
          >
            <Network className="h-3.5 w-3.5" />
            <span>Graph Expansion</span>
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                enableGraphExpansion ? 'bg-brand-400 animate-pulse' : 'bg-slate-500'
              }`}
            />
          </button>

          <button
            onClick={handleClearChat}
            className="inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-slate-200 text-xs transition border border-slate-700/60"
            title="Clear chat messages"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>Clear</span>
          </button>
        </div>
      </div>

      {/* Messages Thread */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.role === 'user' ? 'items-end' : 'items-start'
            } animate-fadeIn`}
          >
            <div className="flex items-center space-x-2 mb-1 px-1">
              <span className="text-[11px] font-semibold text-slate-400">
                {msg.role === 'user' ? 'You' : 'Repository Agent'}
              </span>
              <span className="text-[10px] text-slate-500">{msg.timestamp}</span>
              {msg.latencyMs && (
                <span className="text-[10px] text-slate-500 font-mono">
                  • {msg.latencyMs}ms ({msg.tokensUsed} tokens)
                </span>
              )}
            </div>

            {/* Bubble */}
            <div
              className={`max-w-3xl rounded-2xl p-4 sm:p-5 text-sm leading-relaxed shadow-lg ${
                msg.role === 'user'
                  ? 'bg-brand-600 text-white rounded-tr-sm shadow-brand-500/10 font-normal'
                  : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-sm shadow-black/30'
              }`}
            >
              {/* Message text with pre-line whitespace */}
              <div className="whitespace-pre-wrap font-sans text-[13px] sm:text-sm">
                {msg.content}
              </div>

              {/* Insufficient context banner */}
              {msg.role === 'assistant' && msg.hasSufficientContext === false && (
                <div className="mt-3 p-2.5 rounded-xl bg-amber-950/40 border border-amber-500/30 flex items-center space-x-2 text-xs text-amber-300">
                  <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                  <span>
                    The repository does not contain enough information to answer this query.
                  </span>
                </div>
              )}

              {/* Cited Sources Cards (Phase 9d requirement) */}
              {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-800/80">
                  <div className="flex items-center space-x-1.5 mb-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="text-xs font-semibold text-slate-300 tracking-wide uppercase">
                      Cited Sources ({msg.citations.length})
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {msg.citations.map((cite, idx) => (
                      <button
                        key={idx}
                        onClick={() =>
                          onOpenSourceViewer &&
                          onOpenSourceViewer(cite.file_path, {
                            start: cite.start_line,
                            end: cite.end_line,
                          })
                        }
                        className="group inline-flex items-center space-x-2 px-2.5 py-1.5 rounded-lg bg-slate-950/80 border border-slate-800 hover:border-brand-500/50 hover:bg-slate-800 text-xs text-slate-300 hover:text-white transition shadow-sm"
                        title={`Click to view ${cite.file_path} at lines ${cite.start_line}-${cite.end_line}`}
                      >
                        <FileCode className="h-3.5 w-3.5 text-brand-400 group-hover:scale-110 transition-transform" />
                        <span className="font-mono text-[11px] text-brand-300 font-medium">
                          {cite.label}
                        </span>
                        <ExternalLink className="h-3 w-3 text-slate-500 group-hover:text-brand-400 transition-colors" />
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Collapsible Retrieved Context Drawer */}
              {msg.role === 'assistant' && msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                <div className="mt-3">
                  <button
                    onClick={() => toggleContextDrawer(msg.id)}
                    className="inline-flex items-center space-x-1.5 text-xs text-slate-400 hover:text-brand-300 transition font-medium"
                  >
                    <span>
                      {expandedContexts[msg.id] ? 'Hide' : 'Inspect'} Retrieved Evidence (
                      {msg.retrievedChunks.length} chunks)
                    </span>
                    {expandedContexts[msg.id] ? (
                      <ChevronUp className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5" />
                    )}
                  </button>

                  {expandedContexts[msg.id] && (
                    <div className="mt-2.5 space-y-2 p-3 rounded-xl bg-slate-950/90 border border-slate-800/80 text-xs animate-fadeIn">
                      {msg.graphSummary && (
                        <div className="p-2 rounded-lg bg-brand-950/30 border border-brand-500/20 text-[11px] text-brand-200">
                          <span className="font-semibold text-brand-400">Graph Relation:</span>{' '}
                          {msg.graphSummary}
                        </div>
                      )}
                      <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                        {msg.retrievedChunks.map((chunk, cIdx) => (
                          <div
                            key={cIdx}
                            className="p-2.5 rounded-lg bg-slate-900 border border-slate-800"
                          >
                            <div className="flex items-center justify-between text-[11px] mb-1">
                              <span className="font-mono text-slate-300 font-semibold">
                                {chunk.file_path}:{chunk.start_line}-{chunk.end_line}
                              </span>
                              <span
                                className={`px-1.5 py-0.2 rounded text-[10px] font-mono ${
                                  chunk.is_expanded
                                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                }`}
                              >
                                {chunk.is_expanded
                                  ? `expanded (${chunk.expansion_type || 'neighbor'})`
                                  : 'primary cosine hit'}
                              </span>
                            </div>
                            {chunk.expansion_reason && (
                              <p className="text-[10px] text-slate-400 italic mb-1">
                                {chunk.expansion_reason}
                              </p>
                            )}
                            <pre className="text-[11px] font-mono text-slate-400 bg-slate-950 p-2 rounded overflow-x-auto max-h-24">
                              {chunk.content}
                            </pre>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading Indicator */}
        {loading && (
          <div className="flex items-start space-x-3 animate-fadeIn">
            <div className="max-w-md rounded-2xl rounded-tl-sm p-4 bg-slate-900 border border-slate-800 text-slate-300 flex items-center space-x-3">
              <Loader2 className="h-4 w-4 text-brand-400 animate-spin" />
              <div className="text-xs">
                <span className="font-medium text-white">Searching repository & graph...</span>
                <p className="text-[11px] text-slate-400">
                  Retrieving AST chunks, expanding call neighbors & generating grounded answer...
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-200 text-xs flex items-center justify-between animate-fadeIn">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => handleSendMessage()}
              className="px-2.5 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-[11px] font-medium transition"
            >
              Retry
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Questions Chips (Helpful starters) */}
      <div className="px-6 py-2 bg-slate-950 border-t border-slate-900 shrink-0 overflow-x-auto">
        <div className="flex items-center space-x-2">
          <span className="text-[11px] text-slate-500 font-medium whitespace-nowrap flex items-center">
            <Sparkles className="h-3 w-3 text-brand-400 mr-1" /> Quick questions:
          </span>
          {sampleQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(q)}
              disabled={loading}
              className="text-xs px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white transition whitespace-nowrap disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form Bar */}
      <div className="p-4 sm:p-5 bg-slate-900/90 border-t border-slate-800 shrink-0 backdrop-blur">
        <div className="max-w-4xl mx-auto relative flex items-center">
          <textarea
            ref={inputRef}
            rows={1}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder="Ask a question about the repository (e.g. 'Where is login handled?')..."
            className="w-full pl-4 pr-12 py-3 bg-slate-950/80 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition resize-none leading-normal disabled:opacity-50 shadow-inner"
          />

          <button
            onClick={() => handleSendMessage()}
            disabled={loading || !inputMessage.trim()}
            className="absolute right-2 p-2 rounded-lg bg-brand-500 hover:bg-brand-600 disabled:bg-slate-800 disabled:text-slate-600 text-white transition shadow-sm"
            title="Send query (Enter)"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
        <div className="max-w-4xl mx-auto mt-2 flex items-center justify-between text-[11px] text-slate-500 px-1">
          <span>Press Enter to send, Shift+Enter for new line</span>
          <span>Offline & private: running strictly against local LLM</span>
        </div>
      </div>
    </div>
  );
}
