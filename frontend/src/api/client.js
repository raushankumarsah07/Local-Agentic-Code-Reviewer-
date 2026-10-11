/**
 * Centralized API client module for interacting with the FastAPI backend.
 * Provides typed helper functions and unified error handling.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, options);

    if (!response.ok) {
      let errorDetail = `Request failed with status ${response.status}`;
      try {
        const errorJson = await response.json();
        errorDetail = errorJson.detail || errorDetail;
      } catch {
        // Fallback to text
        const text = await response.text();
        if (text) errorDetail = text;
      }
      throw new Error(errorDetail);
    }

    return await response.json();
  } catch (error) {
    console.error(`[API Error] ${options.method || 'GET'} ${endpoint}:`, error);
    throw error;
  }
}

export const api = {
  // System Health
  checkHealth: () => request('/health'),

  // Projects Management
  getProjects: () => request('/projects'),

  getProject: (projectId) => request(`/projects/${projectId}`),

  uploadProject: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request('/projects/upload', {
      method: 'POST',
      body: formData,
    });
  },

  deleteProject: (projectId) =>
    request(`/projects/${projectId}`, {
      method: 'DELETE',
    }),

  // Architecture Dependency Graph
  getProjectGraph: (projectId, includeExternal = true) =>
    request(`/projects/${projectId}/graph?include_external=${includeExternal}`),

  // Files & Source Code
  getProjectFiles: (projectId, language = null) => {
    const query = language ? `?language=${encodeURIComponent(language)}` : '';
    return request(`/projects/${projectId}/files${query}`);
  },

  getSourceFile: (projectId, filePath) =>
    request(`/projects/${projectId}/source?path=${encodeURIComponent(filePath)}`),

  // AST Parsing & Entities
  parseProject: (projectId) =>
    request(`/projects/${projectId}/parse`, {
      method: 'POST',
    }),

  getFileAst: (projectId, filePath) =>
    request(`/projects/${projectId}/ast?file_path=${encodeURIComponent(filePath)}`),

  getEntities: (projectId, entityType = null) => {
    const query = entityType ? `?entity_type=${encodeURIComponent(entityType)}` : '';
    return request(`/projects/${projectId}/entities${query}`);
  },

  // Static Analysis & Findings (Phase 7)
  analyzeComplexity: (projectId, thresholds = null) => {
    const options = {
      method: 'POST',
    };
    if (thresholds) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify(thresholds);
    }
    return request(`/projects/${projectId}/analyze/complexity`, options);
  },

  analyzeDeadCode: (projectId, entryPoints = null) => {
    const options = {
      method: 'POST',
    };
    if (entryPoints) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify({ entry_points: entryPoints });
    }
    return request(`/projects/${projectId}/analyze/dead-code`, options);
  },

  analyzeArchitecture: (projectId, thresholds = null) => {
    const options = {
      method: 'POST',
    };
    if (thresholds) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify(thresholds);
    }
    return request(`/projects/${projectId}/analyze/architecture`, options);
  },

  analyzeSecurity: (projectId, config = null) => {
    const options = {
      method: 'POST',
    };
    if (config) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify(config);
    }
    return request(`/projects/${projectId}/analyze/security`, options);
  },

  getFindings: (projectId, { type = null, severity = null, file = null, limit = null, offset = null } = {}) => {
    const params = new URLSearchParams();
    if (type) params.append('type', type);
    if (severity) params.append('severity', severity);
    if (file) params.append('file', file);
    if (limit) params.append('limit', limit);
    if (offset) params.append('offset', offset);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return request(`/projects/${projectId}/findings${queryString}`);
  },

  getFindingsSummary: (projectId) =>
    request(`/projects/${projectId}/findings/summary`),

  clearFindings: (projectId, type = null) => {
    const query = type ? `?type=${encodeURIComponent(type)}` : '';
    return request(`/projects/${projectId}/findings${query}`, { method: 'DELETE' });
  },

  // Local LLM Explanations (Phase 8)
  explainFinding: (findingId, force = false) =>
    request(`/findings/${findingId}/explain?force=${force}`, {
      method: 'POST',
    }),

  getFindingExplanation: (findingId) =>
    request(`/findings/${findingId}/explanation`),

  explainBatch: (projectId, { severityFilter = null, limit = 10, force = false } = {}) =>
    request(`/projects/${projectId}/explain-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        severity_filter: severityFilter,
        limit,
        force,
      }),
    }),

  checkLLMHealth: () =>
    request('/llm/health'),

  // Repository Chat (Phase 9d)
  chatWithRepository: (projectId, { message, history = [], topK = 5, enableGraphExpansion = true } = {}) =>
    request(`/projects/${projectId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        history,
        top_k: topK,
        enable_graph_expansion: enableGraphExpansion,
      }),
    }),

  // Agent Workflow & Documentation (Phase 10)
  triggerProjectAnalysis: (projectId) =>
    request(`/projects/${projectId}/analyze`, {
      method: 'POST',
    }),

  getProjectAnalysisStatus: (projectId) =>
    request(`/projects/${projectId}/status`),

  getProjectDocumentation: (projectId) =>
    request(`/projects/${projectId}/docs`),

  getDocumentationDownloadUrl: (projectId) =>
    `${API_BASE_URL}/projects/${projectId}/docs/download`,
};

