/**
 * Jobs module – job list and status display.
 */

import { api } from '../api.js';
import { escapeHtml, formatDate, formatJobStatus } from '../ui.js';

export function initJobsView() {
  const jobsContainer = document.getElementById('jobs-list');
  if (!jobsContainer) {
    return;
  }

  const refreshBtn = document.getElementById('refresh-jobs-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', loadJobs);
  }
  
  setInterval(loadJobs, 5000);
  loadJobs();
}

export async function loadJobs() {
  const jobsContainer = document.getElementById('jobs-list');
  if (!jobsContainer) return;

  const safe = (value) => escapeHtml(String(value ?? '-'));

  try {
    const response = await api.getJobs(50);
    const jobs = response.jobs || [];

    if (jobs.length === 0) {
      jobsContainer.innerHTML = `
        <div class="dashboard-jobs-empty">
          <span class="material-icons-outlined">inventory_2</span>
          <span>Nog geen jobs gevonden.</span>
        </div>
      `;
      return;
    }

    jobsContainer.innerHTML = jobs.map((job) => {
      const draftId = job.payload?.draftId;
      const siteId = job.payload?.siteId || '-';
      const siteName = job.siteName || siteId;
      const title = job.title || safe(job.jobId || job.id || '-');
      const createdAt = job.createdAt ? formatDate(job.createdAt) : '-';
      const updatedAt = job.updatedAt ? formatDate(job.updatedAt) : '-';
      const statusBadge = formatJobStatus(job.status);
      const type = safe(job.type || '-');

      return `
        <article class="dashboard-job-item">
          <div class="dashboard-job-top">
            <div class="dashboard-job-id-wrap">
              <span class="dashboard-job-code">${safe(title)}</span>
              <span class="dashboard-job-type">${type}</span>
            </div>
            <div class="dashboard-job-status">${statusBadge}</div>
          </div>

          <dl class="dashboard-job-grid">
            <div>
              <dt>Site</dt>
              <dd>${safe(siteName)}</dd>
            </div>
            <div>
              <dt>Draft</dt>
              <dd>${safe(draftId || '-')}</dd>
            </div>
            <div>
              <dt>Aangemaakt</dt>
              <dd>${safe(createdAt)}</dd>
            </div>
            <div>
              <dt>Laatst bijgewerkt</dt>
              <dd>${safe(updatedAt)}</dd>
            </div>
          </dl>
        </article>
      `;
    }).join('');
  } catch (error) {
    console.error('Error loading jobs:', error);
    jobsContainer.innerHTML = `
      <div class="dashboard-jobs-error">
        <span class="material-icons-outlined">error</span>
        <span>Fout bij laden van jobs.</span>
      </div>
    `;
  }
}

export function updateJobStatus(job) {
  const statusContainer = document.getElementById('job-status');
  if (!statusContainer) return;

  const safe = (value) => escapeHtml(String(value ?? '-'));
  const resultJson = job.result
    ? `<pre class="dashboard-status-pre">${escapeHtml(JSON.stringify(job.result, null, 2))}</pre>`
    : '';
  const errorJson = job.error
    ? `<pre class="dashboard-status-pre">${escapeHtml(JSON.stringify(job.error, null, 2))}</pre>`
    : '';
  const warnings = job.result?.warnings || [];
  const warningsHtml = warnings.length > 0
    ? `<div style="padding:var(--spacing-md);border-radius:var(--radius-md);background:rgba(255,152,0,0.1);border:1px solid rgba(255,152,0,0.3);margin-bottom:var(--spacing-md)">
        <strong style="display:flex;align-items:center;gap:4px;margin-bottom:4px;color:var(--text-primary)">
          <span class="material-icons-outlined" style="font-size:1.1rem;color:#ff9800">warning</span>
          Waarschuwingen
        </strong>
        ${warnings.map(w => `<p style="margin:0;font-size:0.9rem;color:var(--text-secondary)">${escapeHtml(w)}</p>`).join('')}
      </div>`
    : '';
  const steps = Array.isArray(job.steps) ? job.steps : [];
  const stepsHtml = steps.length > 0
    ? `
      <ol class="dashboard-status-steps">
        ${steps.map((step) => `<li>${safe(step.step)}: ${safe(step.status)}</li>`).join('')}
      </ol>
    `
    : '<p class="text-muted">Geen stappen beschikbaar.</p>';
  
  statusContainer.innerHTML = `
    <div class="dashboard-status-block">
      <div>
        ${formatJobStatus(job.status)}
      </div>

      <div class="dashboard-status-kv">
        <div class="dashboard-status-kv-item">
          <small>Job ID</small>
          <span>${safe(job.jobId || job.id || '-')}</span>
        </div>
        <div class="dashboard-status-kv-item">
          <small>Type</small>
          <span>${safe(job.type || '-')}</span>
        </div>
      </div>

      ${warningsHtml}

      ${resultJson ? `
        <div>
          <h4>Resultaat</h4>
          ${resultJson}
        </div>
      ` : ''}

      ${errorJson ? `
        <div>
          <h4>Foutmelding</h4>
          ${errorJson}
        </div>
      ` : ''}

      <div>
        <h4>Stappen</h4>
        ${stepsHtml}
      </div>
    </div>
  `;
}
