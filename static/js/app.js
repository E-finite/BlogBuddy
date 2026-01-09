/**
 * Main Application Logic
 */

import { api, pollJob } from './api.js';
import { showAlert, showModal, setButtonLoading, formatDate, formatJobStatus } from './ui.js';

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initConnectSite();
  initGeneratePost();
  initPublishPost();
  initJobsView();
  
  // Check API health
  checkHealth();
});

// Navigation
function initNavigation() {
  const navLinks = document.querySelectorAll('.nav-link');
  const sections = document.querySelectorAll('.page-section');
  
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const target = link.dataset.page;
      
      // Update active nav
      navLinks.forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      
      // Show target section
      sections.forEach(s => s.classList.add('hidden'));
      const targetSection = document.getElementById(target);
      if (targetSection) {
        targetSection.classList.remove('hidden');
      }
    });
  });
}

// Connect Site
function initConnectSite() {
  const form = document.getElementById('connect-site-form');
  if (!form) return;
  
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    
    const formData = new FormData(form);
    const payload = {
      wpBaseUrl: formData.get('wpBaseUrl'),
      wpUsername: formData.get('wpUsername'),
      wpApplicationPassword: formData.get('wpApplicationPassword'),
    };
    
    setButtonLoading(submitBtn, true);
    
    try {
      const result = await api.connectSite(
        payload.wpBaseUrl,
        payload.wpUsername,
        payload.wpApplicationPassword
      );
      
      showAlert(`Site verbonden! Site ID: ${result.siteId}`, 'success');
      form.reset();
      
      // Store siteId for later use
      sessionStorage.setItem('currentSiteId', result.siteId);
      
    } catch (error) {
      showAlert(error.message || 'Fout bij verbinden met WordPress', 'error');
    } finally {
      setButtonLoading(submitBtn, false);
    }
  });
}

// Generate Post
function initGeneratePost() {
  const form = document.getElementById('generate-post-form');
  if (!form) return;
  
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    
    const formData = new FormData(form);
    const siteId = formData.get('siteId') || sessionStorage.getItem('currentSiteId');
    
    if (!siteId) {
      showAlert('Geen site geselecteerd. Verbind eerst een WordPress site.', 'error');
      return;
    }
    
    // Build payload
    const payload = {
      siteId,
      topic: formData.get('topic'),
      audience: {
        market: formData.get('audienceMarket'),
        level: formData.get('audienceLevel'),
        painPoints: formData.get('painPoints')?.split(',').map(s => s.trim()).filter(Boolean) || [],
        objections: formData.get('objections')?.split(',').map(s => s.trim()).filter(Boolean) || [],
      },
      toneOfVoice: {
        style: formData.get('toneStyle')?.split(',').map(s => s.trim()).filter(Boolean) || [],
        formality: formData.get('formality'),
        do: formData.get('toneDo')?.split(',').map(s => s.trim()).filter(Boolean) || [],
        dont: formData.get('toneDont')?.split(',').map(s => s.trim()).filter(Boolean) || [],
      },
      seo: {
        focusKeyword: formData.get('focusKeyword'),
        secondaryKeywords: formData.get('secondaryKeywords')?.split(',').map(s => s.trim()).filter(Boolean) || [],
        internalLinkTargets: [],
        metaTitlePattern: formData.get('metaTitlePattern') || '{topic} | {brand}',
        metaDescMaxLen: parseInt(formData.get('metaDescMaxLen')) || 155,
      },
      brand: {
        name: formData.get('brandName'),
        cta: formData.get('brandCta') || '',
      },
      language: formData.get('language') || 'nl',
      status: formData.get('status') || 'draft',
      generateImage: formData.get('generateImage') === 'on',  // Checkbox value
      multilang: {
        enabled: formData.get('multilangEnabled') === 'true',
        languages: formData.get('multilangLanguages')?.split(',').map(s => s.trim()).filter(Boolean) || [],
        strategy: formData.get('multilangStrategy') || 'translate',
      },
    };
    
    if (formData.get('scheduleDateGmt')) {
      payload.scheduleDateGmt = formData.get('scheduleDateGmt');
    }
    
    setButtonLoading(submitBtn, true);
    
    try {
      const result = await api.generatePost(payload);
      
      // Store draft for publishing
      sessionStorage.setItem('currentDraft', JSON.stringify(result));
      
      showAlert('Blog post gegenereerd!', 'success');
      
      // Show preview
      showDraftPreview(result);
      
    } catch (error) {
      showAlert(error.message || 'Fout bij genereren van blog post', 'error');
    } finally {
      setButtonLoading(submitBtn, false);
    }
  });
}

// Publish Post
function initPublishPost() {
  const publishBtn = document.getElementById('publish-post-btn');
  if (!publishBtn) return;
  
  publishBtn.addEventListener('click', async () => {
    const draftData = sessionStorage.getItem('currentDraft');
    const siteId = sessionStorage.getItem('currentSiteId');
    
    if (!draftData) {
      showAlert('Geen draft gevonden. Genereer eerst een blog post.', 'error');
      return;
    }
    
    if (!siteId) {
      showAlert('Geen site geselecteerd. Verbind eerst een WordPress site.', 'error');
      return;
    }
    
    const draft = JSON.parse(draftData);
    const payload = {
      siteId,
      ...draft,
    };
    
    setButtonLoading(publishBtn, true);
    
    try {
      const result = await api.publishPost(payload);
      
      showAlert(`Publish job gestart! Job ID: ${result.jobId}`, 'success');
      
      // Start polling
      pollJob(
        result.jobId,
        (job) => {
          updateJobStatus(job);
        },
        (job, error) => {
          setButtonLoading(publishBtn, false);
          if (error) {
            showAlert(`Fout bij job: ${error.message}`, 'error');
          } else if (job) {
            showAlert('Blog post gepubliceerd!', 'success');
            if (job.result?.wpPostIds) {
              showPublishSuccess(job.result.wpPostIds);
            }
          }
        }
      );
      
    } catch (error) {
      showAlert(error.message || 'Fout bij publiceren', 'error');
      setButtonLoading(publishBtn, false);
    }
  });
}

// Jobs View
function initJobsView() {
  const refreshBtn = document.getElementById('refresh-jobs-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', loadJobs);
  }
  
  // Auto-refresh every 5 seconds
  setInterval(loadJobs, 5000);
  loadJobs();
}

async function loadJobs() {
  // This would require a list endpoint - for now, we'll show a placeholder
  const jobsContainer = document.getElementById('jobs-list');
  if (!jobsContainer) return;
  
  // In a real implementation, you'd fetch a list of jobs
  // For now, we'll just show a message
  jobsContainer.innerHTML = '<p class="text-secondary">Gebruik de Job ID om een specifieke job te bekijken.</p>';
}

function updateJobStatus(job) {
  const statusContainer = document.getElementById('job-status');
  if (!statusContainer) return;
  
  statusContainer.innerHTML = `
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">Job Status: ${formatJobStatus(job.status)}</h3>
      </div>
      <div class="card-body">
        <p><strong>Job ID:</strong> ${job.jobId}</p>
        <p><strong>Status:</strong> ${job.status}</p>
        ${job.result ? `<pre>${JSON.stringify(job.result, null, 2)}</pre>` : ''}
        ${job.error ? `<div class="alert alert-error">${JSON.stringify(job.error, null, 2)}</div>` : ''}
        ${job.steps ? `
          <h4>Stappen:</h4>
          <ul>
            ${job.steps.map(step => `<li>${step.step}: ${step.status}</li>`).join('')}
          </ul>
        ` : ''}
      </div>
    </div>
  `;
}

function showDraftPreview(draft) {
  const content = draft.draft ? `
    ${draft.draft.image && draft.draft.image.bytes_base64 ? `
      <div style="margin-bottom: var(--spacing-lg);">
        <h5>Featured Image:</h5>
        <img src="data:${draft.draft.image.mime_type};base64,${draft.draft.image.bytes_base64}" 
             alt="Featured Image" 
             style="max-width: 100%; height: auto; border-radius: var(--radius-md); box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />
      </div>
    ` : ''}
    <h4>${draft.draft.title}</h4>
    <p><strong>Slug:</strong> ${draft.draft.slug}</p>
    <p><strong>Excerpt:</strong> ${draft.draft.excerpt}</p>
    <div class="mt-lg">
      <h5>Content Preview:</h5>
      <div style="max-height: 300px; overflow-y: auto; padding: var(--spacing-md); background: var(--bg-elevated); border-radius: var(--radius-md);">
        ${draft.draft.contentHtml}
      </div>
    </div>
  ` : `
    <p>Multi-language drafts gegenereerd:</p>
    <ul>
      ${Object.keys(draft.drafts || {}).map(lang => `<li>${lang}: ${draft.drafts[lang].title}</li>`).join('')}
    </ul>
  `;
  
  showModal('Draft Preview', content, '<button class="btn btn-primary" onclick="this.closest(\'.modal-overlay\').remove()">Sluiten</button>');
}

function showPublishSuccess(wpPostIds) {
  const content = `
    <p>Blog post(s) succesvol gepubliceerd!</p>
    <ul>
      ${Object.entries(wpPostIds).map(([lang, id]) => `<li><strong>${lang}:</strong> Post ID ${id}</li>`).join('')}
    </ul>
  `;
  
  showModal('Publicatie Succesvol', content, '<button class="btn btn-primary" onclick="this.closest(\'.modal-overlay\').remove()">Sluiten</button>');
}

async function checkHealth() {
  try {
    await api.health();
  } catch (error) {
    showAlert('API niet bereikbaar. Controleer of de server draait.', 'error', 0);
  }
}
