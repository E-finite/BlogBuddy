/**
 * API Client - Handles all API communication
 */

const API_BASE = window.location.origin;

class APIError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
  }
}

async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }

  try {
    const response = await fetch(url, config);
    const data = await response.json();

    if (!response.ok) {
      throw new APIError(
        data.error || `HTTP ${response.status}`,
        response.status,
        data
      );
    }

    return data;
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }
    throw new APIError(
      error.message || 'Network error',
      0,
      null
    );
  }
}

// API Methods
export const api = {
  // Sites
  async getSites() {
    return apiRequest('/api/sites');
  },

  async connectSite(wpBaseUrl, wpUsername, wpApplicationPassword) {
    return apiRequest('/api/sites/connect', {
      method: 'POST',
      body: {
        wpBaseUrl,
        wpUsername,
        wpApplicationPassword,
      },
    });
  },

  // Posts
  async generatePost(payload) {
    return apiRequest('/api/posts/generate', {
      method: 'POST',
      body: payload,
    });
  },

  async publishPost(payload) {
    return apiRequest('/api/posts/publish', {
      method: 'POST',
      body: payload,
    });
  },

  // Jobs
  async getJobs(limit = 50) {
    return apiRequest(`/api/jobs?limit=${encodeURIComponent(limit)}`);
  },

  async getJob(jobId) {
    return apiRequest(`/api/jobs/${jobId}`);
  },

  // Drafts
  async getDrafts() {
    return apiRequest('/api/drafts');
  },

  async getDraft(draftId) {
    return apiRequest(`/api/drafts/${draftId}`);
  },

  async updateDraft(draftId, draft) {
    return apiRequest(`/api/drafts/${draftId}`, {
      method: 'PUT',
      body: { draft },
    });
  },

  async deleteDraft(draftId) {
    return apiRequest(`/api/drafts/${draftId}`, {
      method: 'DELETE',
    });
  },

  async getImage(imageId) {
    return apiRequest(`/api/images/${imageId}`);
  },

  // Text regeneration
  async regenerateSection(section, instruction, currentDraft, draftId, language) {
    return apiRequest('/api/posts/text/regenerate', {
      method: 'POST',
      body: { section, instruction, currentDraft, draftId: draftId || null, language: language || 'nl' },
    });
  },

  async regenerateInline(selectedText, instruction, contextBefore, contextAfter, language) {
    return apiRequest('/api/posts/text/regenerate-inline', {
      method: 'POST',
      body: {
        selectedText,
        instruction,
        contextBefore: contextBefore || '',
        contextAfter: contextAfter || '',
        language: language || 'nl',
      },
    });
  },

  // Health
  async health() {
    return apiRequest('/health');
  },

  // Translations
  async translateDraft(draftId, language, translateImage = true) {
    return apiRequest(`/api/drafts/${draftId}/translate`, {
      method: 'POST',
      body: { language, translateImage },
    });
  },

  async getDraftTranslations(draftId) {
    return apiRequest(`/api/drafts/${draftId}/translations`);
  },

  async getDraftTranslation(draftId, language) {
    return apiRequest(`/api/drafts/${draftId}/translations/${language}`);
  },

  async updateDraftTranslation(draftId, language, translated) {
    return apiRequest(`/api/drafts/${draftId}/translations/${language}`, {
      method: 'PUT',
      body: { translated },
    });
  },

  // Bug Reports
  async submitBugReport(category, title, description, pageUrl) {
    return apiRequest('/api/bug-reports', {
      method: 'POST',
      body: { category, title, description, pageUrl },
    });
  },

  async getAdminBugReports(status) {
    const qs = status ? `?status=${encodeURIComponent(status)}` : '';
    return apiRequest(`/api/admin/bug-reports${qs}`);
  },

  async updateBugReport(reportId, status, adminNotes) {
    return apiRequest(`/api/admin/bug-reports/${reportId}`, {
      method: 'PUT',
      body: { status, adminNotes },
    });
  },

  async getBugReportCounts() {
    return apiRequest('/api/admin/bug-reports/counts');
  },

  // Link Library
  async getLinks() {
    return apiRequest('/api/links');
  },

  async createLink(url, label, description) {
    return apiRequest('/api/links', {
      method: 'POST',
      body: { url, label, description },
    });
  },

  async updateLink(linkId, url, label, description) {
    return apiRequest(`/api/links/${linkId}`, {
      method: 'PUT',
      body: { url, label, description },
    });
  },

  async deleteLink(linkId) {
    return apiRequest(`/api/links/${linkId}`, {
      method: 'DELETE',
    });
  },

  // Changelogs
  async getUnseenChangelogs() {
    return apiRequest('/api/changelogs/unseen');
  },

  async dismissChangelog(changelogId) {
    return apiRequest(`/api/changelogs/${changelogId}/dismiss`, {
      method: 'POST',
    });
  },

  async getAdminChangelogs() {
    return apiRequest('/api/admin/changelogs');
  },

  async createChangelog(version, title, contentHtml, published) {
    return apiRequest('/api/admin/changelogs', {
      method: 'POST',
      body: { version, title, contentHtml, published },
    });
  },

  async updateChangelog(changelogId, version, title, contentHtml, published) {
    return apiRequest(`/api/admin/changelogs/${changelogId}`, {
      method: 'PUT',
      body: { version, title, contentHtml, published },
    });
  },

  async deleteChangelog(changelogId) {
    return apiRequest(`/api/admin/changelogs/${changelogId}`, {
      method: 'DELETE',
    });
  },
};

// Polling utility
export function pollJob(jobId, onUpdate, onComplete, maxAttempts = 60) {
  let attempts = 0;
  const interval = 2000; // 2 seconds

  const poll = async () => {
    if (attempts >= maxAttempts) {
      onComplete(null, new Error('Polling timeout'));
      return;
    }

    try {
      const job = await api.getJob(jobId);
      onUpdate(job);

      if (['success', 'partial_success', 'failed'].includes(job.status)) {
        onComplete(job, null);
        return;
      }

      attempts++;
      setTimeout(poll, interval);
    } catch (error) {
      onComplete(null, error);
    }
  };

  poll();
}
