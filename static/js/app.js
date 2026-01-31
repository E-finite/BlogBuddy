/**
 * Main Application Logic
 */

import { api, pollJob } from './api.js';
import { showAlert, showModal, setButtonLoading, formatDate, formatJobStatus } from './ui.js';

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  loadSitesDropdowns(); // Load sites into dropdowns
  initConnectSite();
  initGeneratePost();
  initPublishPost();
  initJobsView();
  
  // Check API health
  checkHealth();
  
  // Restore publish preview if available
  restorePublishPreview();
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
      
      // Restore publish preview when navigating to publish section
      if (target === 'publish') {
        restorePublishPreview();
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
      
      // Reload sites dropdowns
      await loadSitesDropdowns();
      
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
  
  // Website Context URL handling
  const contextUrlInput = document.getElementById('contextWebsiteUrl');
  const contextStatusDiv = document.getElementById('context-status');
  const crawlBtn = document.getElementById('crawl-context-btn');
  const siteIdInput = document.getElementById('siteId');
  
  let contextSiteId = null;
  
  // Show crawl button when URL is entered
  if (contextUrlInput) {
    contextUrlInput.addEventListener('input', () => {
      const url = contextUrlInput.value.trim();
      if (url) {
        crawlBtn.style.display = 'block';
      } else {
        crawlBtn.style.display = 'none';
        contextStatusDiv.style.display = 'none';
        contextSiteId = null;
      }
    });
  }
  
  // Crawl website for context
  if (crawlBtn) {
    crawlBtn.addEventListener('click', async () => {
      const url = contextUrlInput.value.trim();
      if (!url) return;
      
      setButtonLoading(crawlBtn, true);
      contextStatusDiv.style.display = 'block';
      contextStatusDiv.querySelector('.alert').textContent = '🕷️ Crawling website... (dit kan 30-60 seconden duren)';
      contextStatusDiv.querySelector('.alert').className = 'alert alert-info';
      
      try {
        // Use the context-only crawl endpoint
        const response = await fetch('/api/sites/crawl-for-context', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            websiteUrl: url,
            maxDepth: 2,
            maxPages: 30
          })
        });
        
        if (!response.ok) {
          const errorText = await response.text();
          let errorMessage = 'Crawl failed';
          try {
            const errorJson = JSON.parse(errorText);
            errorMessage = errorJson.error || errorMessage;
          } catch (e) {
            errorMessage = errorText || errorMessage;
          }
          throw new Error(errorMessage);
        }
        
        const data = await response.json();
        contextSiteId = data.siteId;
        
        // Update site ID input
        siteIdInput.value = contextSiteId;
        
        // Check if crawl was successful
        if (data.pages_stored === 0) {
          if (data.is_js_site) {
            contextStatusDiv.querySelector('.alert').innerHTML = 
              `⚠️ <strong>JavaScript-website gedetecteerd!</strong><br>
              Deze site laadt content via JavaScript (React/Vue/SPA).<br>
              💡 <em>Tip: Gebruik een statische site of WordPress/traditionele CMS.</em>`;
          } else {
            contextStatusDiv.querySelector('.alert').textContent = 
              `⚠️ Geen pagina's gecrawld! De website is mogelijk niet bereikbaar.`;
          }
          contextStatusDiv.querySelector('.alert').className = 'alert alert-warning';
          crawlBtn.textContent = '⚠️ Geen Content';
          crawlBtn.disabled = false;
        } else {
          contextStatusDiv.querySelector('.alert').textContent = 
            `✅ Website gecrawld! ${data.pages_stored} pagina's, ${data.chunks_stored} chunks. ${data.site_dna_generated ? 'Site DNA gegenereerd.' : 'Site DNA kon niet worden gegenereerd.'}`;
          contextStatusDiv.querySelector('.alert').className = 'alert alert-success';
          
          crawlBtn.textContent = '✅ Context Geladen';
          crawlBtn.disabled = true;
          
          // Store for use in generation
          sessionStorage.setItem('contextSiteId', contextSiteId);
        }
        
      } catch (error) {
        console.error('Crawl error:', error);
        contextStatusDiv.querySelector('.alert').textContent = 
          `❌ Fout bij crawlen: ${error.message}. Check of de Flask app draait en de URL correct is.`;
        contextStatusDiv.querySelector('.alert').className = 'alert alert-error';
      } finally {
        setButtonLoading(crawlBtn, false);
      }
    });
  }
  
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    
    const formData = new FormData(form);
    
    // Use context site ID if available, otherwise use siteId input or session
    let siteId = contextSiteId || formData.get('siteId') || sessionStorage.getItem('currentSiteId');
    
    if (!siteId) {
      showAlert('Geen site geselecteerd. Verbind eerst een WordPress site of vul een website URL in voor context.', 'error');
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
      
      console.log('Generate Post Result:', result);
      
      // Extract the actual draft from the result
      const draft = result.draft || (result.drafts && result.drafts[Object.keys(result.drafts)[0]]);
      
      if (!draft) {
        throw new Error('Geen draft ontvangen van API');
      }
      
      // Store draft for publishing
      sessionStorage.setItem('currentDraft', JSON.stringify(draft));
      sessionStorage.setItem('currentSiteId', siteId);
      
      console.log('Stored draft:', draft);
      
      showAlert('Blog post gegenereerd!' + (contextSiteId ? ' (met website context)' : ''), 'success');
      
      // Automatically fill publish form and switch to publish tab
      fillPublishForm(result, siteId);
      switchToPublishTab();
      
    } catch (error) {
      console.error('Generate error:', error);
      showAlert(error.message || 'Fout bij genereren van blog post', 'error');
    } finally {
      setButtonLoading(submitBtn, false);
    }
  });
}

// Publish Post
function initPublishPost() {
  const publishForm = document.getElementById('publish-post-form');
  if (!publishForm) return;
  
  // Setup real-time preview sync
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  
  if (titleInput && contentInput) {
    // Update preview when title or content changes
    titleInput.addEventListener('input', updatePublishPreviewFromForm);
    contentInput.addEventListener('input', updatePublishPreviewFromForm);
  }
  
  publishForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = publishForm.querySelector('button[type="submit"]');
    const draftData = sessionStorage.getItem('currentDraft');
    const imageData = sessionStorage.getItem('currentDraftImage');
    
    // Get form data
    const formData = new FormData(publishForm);
    const pubSiteId = formData.get('pubSiteId');
    
    // Validation
    if (!pubSiteId) {
      showAlert('Selecteer een WordPress site.', 'error');
      return;
    }
    
    // Get draft or use form values
    let draft;
    if (draftData) {
      draft = JSON.parse(draftData);
      console.log('Using stored draft:', draft);
    } else {
      // Fallback: use form values if no draft stored
      draft = {
        title: formData.get('title'),
        contentHtml: formData.get('content'),
        status: formData.get('isDraft') === 'on' ? 'draft' : 'publish'
      };
      console.log('Using form values as draft:', draft);
    }
    
    // Add image data to draft if available
    if (imageData) {
      draft.image = JSON.parse(imageData);
      console.log('Added image to draft');
    }
    
    // Build payload with correct structure - draft as nested object
    const payload = {
      siteId: pubSiteId,
      draft: draft
    };
    
    console.log('Publishing payload:', payload);
    
    setButtonLoading(submitBtn, true);
    
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
          setButtonLoading(submitBtn, false);
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
      console.error('Publish error:', error);
      showAlert(error.message || 'Fout bij publiceren', 'error');
      setButtonLoading(submitBtn, false);
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

// Fill publish form with generated draft
function fillPublishForm(result, siteId) {
  const draft = result.draft || (result.drafts && result.drafts[Object.keys(result.drafts)[0]]);
  
  if (!draft) return;
  
  // Fill form fields
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  const pubSiteIdSelect = document.getElementById('pubSiteId');
  const previewDiv = document.getElementById('publish-preview');
  
  if (titleInput) titleInput.value = draft.title || '';
  if (contentInput) contentInput.value = draft.contentHtml || '';
  if (pubSiteIdSelect && siteId) pubSiteIdSelect.value = siteId;
  
  // Show preview with image
  if (previewDiv) {
    let previewHtml = '<div class="card" style="margin-bottom: var(--spacing-lg);">';
    previewHtml += '<div class="card-header"><h3>Preview van Gegenereerde Post</h3></div>';
    previewHtml += '<div class="card-body">';
    
    // Featured image - check both draft.image and draft._image for compatibility
    const imageData = draft.image || draft._image;
    if (imageData && imageData.bytes_base64) {
      previewHtml += `
        <div style="margin-bottom: var(--spacing-lg);">
          <h5 style="margin-bottom: var(--spacing-sm); color: var(--text-secondary);">Featured Image Preview:</h5>
          <img src="data:${imageData.mime_type || imageData.mime};base64,${imageData.bytes_base64}" 
               alt="Featured Image" 
               style="max-width: 100%; height: auto; border-radius: var(--radius-md); box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />
        </div>
      `;
    }
    
    previewHtml += `<h2>${draft.title}</h2>`;
    if (draft.excerpt) {
      previewHtml += `<p style="color: var(--text-secondary); font-style: italic;">${draft.excerpt}</p>`;
    }
    previewHtml += '<hr style="margin: var(--spacing-lg) 0;">';
    previewHtml += `<div style="line-height: 1.6;">${draft.contentHtml}</div>`;
    previewHtml += '</div></div>';
    
    previewDiv.innerHTML = previewHtml;
    previewDiv.style.display = 'block';
  }
  
  // Store image data for publishing
  if (draft.image || draft._image) {
    sessionStorage.setItem('currentDraftImage', JSON.stringify(draft.image || draft._image));
  }
}

// Switch to publish tab
function switchToPublishTab() {
  const publishTab = document.querySelector('.nav-link[data-page="publish"]');
  if (publishTab) {
    publishTab.click();
  }
}

// Restore publish preview from sessionStorage
function restorePublishPreview() {
  const draftData = sessionStorage.getItem('currentDraft');
  const imageData = sessionStorage.getItem('currentDraftImage');
  const previewDiv = document.getElementById('publish-preview');
  
  console.log('Restoring preview - draftData:', draftData);
  console.log('Restoring preview - imageData:', imageData);
  
  if (!previewDiv || !draftData) return;
  
  try {
    const draft = JSON.parse(draftData);
    
    console.log('Parsed draft:', draft);
    
    // Add image data if available
    if (imageData) {
      draft.image = JSON.parse(imageData);
    }
    
    renderPreview(draft, previewDiv);
  } catch (error) {
    console.error('Error restoring publish preview:', error);
  }
}

// Update preview from form inputs (real-time sync)
function updatePublishPreviewFromForm() {
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  const previewDiv = document.getElementById('publish-preview');
  const imageData = sessionStorage.getItem('currentDraftImage');
  const draftData = sessionStorage.getItem('currentDraft');
  
  if (!previewDiv || !titleInput || !contentInput) return;
  
  // Build draft from current form values
  const draft = {
    title: titleInput.value || 'Geen titel',
    contentHtml: contentInput.value || 'Geen content'
  };
  
  // Add stored excerpt if available
  if (draftData) {
    try {
      const storedDraft = JSON.parse(draftData);
      if (storedDraft.excerpt) {
        draft.excerpt = storedDraft.excerpt;
      }
    } catch (e) {
      // Ignore parse errors
    }
  }
  
  // Add image data if available
  if (imageData) {
    try {
      draft.image = JSON.parse(imageData);
    } catch (e) {
      // Ignore parse errors
    }
  }
  
  renderPreview(draft, previewDiv);
}

// Render preview HTML
function renderPreview(draft, previewDiv) {
  let previewHtml = '';
  
  // Featured image - separate card
  const imageToDisplay = draft.image || draft._image;
  if (imageToDisplay && imageToDisplay.bytes_base64) {
    previewHtml += `
      <div class="card" style="margin-bottom: var(--spacing-lg);">
        <div class="card-header"><h3>Featured Image</h3></div>
        <div class="card-body">
          <img src="data:${imageToDisplay.mime_type || imageToDisplay.mime};base64,${imageToDisplay.bytes_base64}" 
               alt="Featured Image" 
               style="max-width: 100%; height: auto; border-radius: var(--radius-md); box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />
        </div>
      </div>
    `;
  }
  
  // Content preview - separate card
  previewHtml += '<div class="card" style="margin-bottom: var(--spacing-lg);">';
  previewHtml += '<div class="card-header"><h3>Content Preview</h3></div>';
  previewHtml += '<div class="card-body">';
  previewHtml += `<h2>${draft.title || 'Geen titel'}</h2>`;
  if (draft.excerpt) {
    previewHtml += `<p style="color: var(--text-secondary); font-style: italic;">${draft.excerpt}</p>`;
  }
  previewHtml += '<hr style="margin: var(--spacing-lg) 0;">';
  previewHtml += `<div style="line-height: 1.6;">${draft.contentHtml || 'Geen content'}</div>`;
  previewHtml += '</div></div>';
  
  previewDiv.innerHTML = previewHtml;
  previewDiv.style.display = 'block';
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

// Load sites into dropdowns
async function loadSitesDropdowns() {
  try {
    const response = await fetch('/api/sites');
    if (!response.ok) {
      console.error('Failed to load sites');
      return;
    }
    
    const sites = await response.json();
    
    // Update both dropdowns
    const siteIdSelect = document.getElementById('siteId');
    const pubSiteIdSelect = document.getElementById('pubSiteId');
    
    if (siteIdSelect) {
      siteIdSelect.innerHTML = '<option value="">-- Kies een site --</option>';
      sites.forEach(site => {
        const option = document.createElement('option');
        option.value = site.id;
        option.textContent = `${site.wp_base_url} (${site.wp_username})`;
        siteIdSelect.appendChild(option);
      });
    }
    
    if (pubSiteIdSelect) {
      pubSiteIdSelect.innerHTML = '<option value="">-- Kies een site --</option>';
      sites.forEach(site => {
        const option = document.createElement('option');
        option.value = site.id;
        option.textContent = `${site.wp_base_url} (${site.wp_username})`;
        pubSiteIdSelect.appendChild(option);
      });
    }
  } catch (error) {
    console.error('Error loading sites:', error);
  }
}

async function checkHealth() {
  try {
    await api.health();
  } catch (error) {
    showAlert('API niet bereikbaar. Controleer of de server draait.', 'error', 0);
  }
}
