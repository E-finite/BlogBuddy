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
        loadDrafts(); // Load saved drafts from database
      }
    });
  });
}

// Connect Site
function initConnectSite() {
  const form = document.getElementById('connect-site-form');
  if (!form) return;
  
  // Check if user already has a site and show warning
  checkExistingSites(form);
  
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
      
      if (result.replaced) {
        showAlert(`Site vervangen! Oude site (${result.oldSiteUrl}) is verwijderd en nieuwe site is verbonden.`, 'success', 8000);
      } else {
        showAlert(`Site verbonden! Site ID: ${result.siteId}`, 'success');
      }
      
      form.reset();
      
      // Reload sites dropdowns
      await loadSitesDropdowns();
      
      // Store siteId for later use
      sessionStorage.setItem('currentSiteId', result.siteId);
      
      // Update warning message
      checkExistingSites(form);
      
    } catch (error) {
      showAlert(error.message || 'Fout bij verbinden met WordPress', 'error');
    } finally {
      setButtonLoading(submitBtn, false);
    }
  });
}

// Check if user has existing sites and show warning
async function checkExistingSites(form) {
  try {
    const sites = await api.getSites();
    
    // Remove existing warning
    const existingWarning = form.querySelector('.site-replace-warning');
    if (existingWarning) {
      existingWarning.remove();
    }
    
    if (sites && sites.length > 0) {
      // Show warning that connecting will replace existing site
      const warningDiv = document.createElement('div');
      warningDiv.className = 'alert alert-warning site-replace-warning';
      warningDiv.style.marginTop = '1rem';
      warningDiv.innerHTML = `
        <strong>⚠️ Let op!</strong><br>
        <small>Je hebt al een site verbonden: <strong>${sites[0].wp_base_url}</strong></small><br>
        <small>Als je een nieuwe site verbindt, wordt de oude site automatisch vervangen.</small>
      `;
      form.appendChild(warningDiv);
    }
  } catch (error) {
    console.error('Error checking existing sites:', error);
  }
}

// Generate Post
function initGeneratePost() {
  const form = document.getElementById('generate-post-form');
  if (!form) return;
  
  // Image settings toggle
  const generateImageCheckbox = document.getElementById('generateImage');
  const imageSettingsPanel = document.getElementById('image-settings-panel');
  
  if (generateImageCheckbox && imageSettingsPanel) {
    // Initial state
    imageSettingsPanel.style.display = generateImageCheckbox.checked ? 'block' : 'none';
    
    // Toggle on change
    generateImageCheckbox.addEventListener('change', () => {
      imageSettingsPanel.style.display = generateImageCheckbox.checked ? 'block' : 'none';
    });
  }
  
  // Website Context URL handling
  const contextUrlInput = document.getElementById('contextWebsiteUrl');
  const contextStatusDiv = document.getElementById('context-status');
  const crawlBtn = document.getElementById('crawl-context-btn');
  const existingSitesSection = document.getElementById('existing-sites-section');
  const existingSiteSelect = document.getElementById('existingSiteSelect');
  
  let contextSiteId = null;
  
  // Load existing context sites
  async function loadContextSites() {
    try {
      const response = await fetch('/api/context-sites');
      if (!response.ok) return;
      
      const data = await response.json();
      if (data.sites && data.sites.length > 0) {
        existingSitesSection.style.display = 'block';
        
        // Clear existing options except first
        existingSiteSelect.innerHTML = '<option value="">-- Kies een website --</option>';
        
        // Add sites to dropdown (only sites with DNA are returned from API)
        data.sites.forEach(site => {
          const option = document.createElement('option');
          option.value = site.id;
          option.textContent = `${site.brandName || site.baseUrl} ✓`;
          existingSiteSelect.appendChild(option);
        });
        
        console.log(`Loaded ${data.sites.length} sites with DNA`);
      } else {
        console.log('No sites with DNA found');
      }
    } catch (error) {
      console.error('Error loading context sites:', error);
    }
  }
  
  // Load sites on page load
  if (existingSiteSelect) {
    loadContextSites();
  }
  
  // Handle existing site selection
  const confirmSiteBtn = document.getElementById('confirm-site-btn');
  
  if (existingSiteSelect) {
    existingSiteSelect.addEventListener('change', () => {
      const selectedSiteId = existingSiteSelect.value;
      if (selectedSiteId) {
        // Show confirmation button
        if (confirmSiteBtn) {
          confirmSiteBtn.style.display = 'block';
          confirmSiteBtn.disabled = false;
          confirmSiteBtn.textContent = '✓ Gebruik deze website';
        }
        contextUrlInput.value = ''; // Clear URL input
        crawlBtn.style.display = 'none';
        contextStatusDiv.style.display = 'none';
        contextSiteId = null; // Don't set yet, wait for confirmation
      } else {
        // Hide confirmation button if no selection
        if (confirmSiteBtn) {
          confirmSiteBtn.style.display = 'none';
        }
        contextStatusDiv.style.display = 'none';
        contextSiteId = null;
      }
    });
  }
  
  // Handle site confirmation
  if (confirmSiteBtn) {
    confirmSiteBtn.addEventListener('click', async () => {
      const selectedSiteId = existingSiteSelect.value;
      if (!selectedSiteId) return;
      
      // Disable button during loading
      confirmSiteBtn.disabled = true;
      confirmSiteBtn.textContent = '⏳ Laden...';
      
      contextSiteId = selectedSiteId;
      
      // Show loading status
      contextStatusDiv.style.display = 'block';
      contextStatusDiv.querySelector('.alert').textContent = '⏳ Website gegevens laden...';
      contextStatusDiv.querySelector('.alert').className = 'alert alert-info';
      
      try {
        // Get site details (pages, chunks count)
        const detailsResponse = await fetch(`/api/context-sites/${selectedSiteId}/details`);
        if (detailsResponse.ok) {
          const details = await detailsResponse.json();
          
          // Show detailed status like after crawl
          contextStatusDiv.querySelector('.alert').textContent = 
            `✅ ${details.baseUrl} geselecteerd! ${details.pagesCount} pagina's, ${details.chunksCount} chunks. ${details.hasDna ? 'Site DNA beschikbaar.' : 'Geen Site DNA.'}`;
          contextStatusDiv.querySelector('.alert').className = 'alert alert-success';
        } else {
          // Fallback to simple message
          contextStatusDiv.querySelector('.alert').textContent = '✅ Website geselecteerd!';
          contextStatusDiv.querySelector('.alert').className = 'alert alert-success';
        }
        
        // Auto-fill from Site DNA
        await autoFillFromSiteDNA(selectedSiteId);
        
        // Update button to show success
        confirmSiteBtn.textContent = '✅ Geladen';
        confirmSiteBtn.disabled = true;
      } catch (error) {
        console.error('Error loading site details:', error);
        contextStatusDiv.querySelector('.alert').textContent = '❌ Fout bij laden site gegevens';
        contextStatusDiv.querySelector('.alert').className = 'alert alert-error';
        
        // Re-enable button
        confirmSiteBtn.textContent = '✓ Gebruik deze website';
        confirmSiteBtn.disabled = false;
      }
    });
  }
  
  // Auto-fill SEO Focus Keyword from topic field
  const topicInput = document.getElementById('topic');
  const focusKeywordInput = document.getElementById('focusKeyword');
  
  if (topicInput && focusKeywordInput) {
    topicInput.addEventListener('input', () => {
      const topic = topicInput.value.trim();
      if (topic) {
        // Replace spaces with hyphens and convert to lowercase
        focusKeywordInput.value = topic.replace(/\s+/g, '-').toLowerCase();
      } else {
        focusKeywordInput.value = '';
      }
    });
  }
  
  // Auto-fill form from Site DNA
  async function autoFillFromSiteDNA(siteId) {
    try {
      const response = await fetch(`/api/sites/${siteId}/dna`);
      if (!response.ok) {
        const errorText = await response.text();
        console.log('No Site DNA found for this site:', errorText);
        return;
      }
      
      const dna = await response.json();
      console.log('Site DNA loaded:', dna);
      
      let fieldsFilledCount = 0;
      
      // Fill brand name
      if (dna.brand_name && document.getElementById('brandName')) {
        document.getElementById('brandName').value = dna.brand_name;
        fieldsFilledCount++;
        console.log('Filled brandName:', dna.brand_name);
      }
      
      // Fill audience (eerste target audience)
      if (dna.target_audiences && dna.target_audiences.length > 0 && document.getElementById('audienceMarket')) {
        document.getElementById('audienceMarket').value = dna.target_audiences[0];
        fieldsFilledCount++;
        console.log('Filled audienceMarket:', dna.target_audiences[0]);
      }
      
      // Fill pain points
      if (dna.pain_points && dna.pain_points.length > 0 && document.getElementById('painPoints')) {
        document.getElementById('painPoints').value = dna.pain_points.join(', ');
        fieldsFilledCount++;
        console.log('Filled painPoints:', dna.pain_points);
      }
      
      // Fill tone keywords
      if (dna.tone_keywords && dna.tone_keywords.length > 0 && document.getElementById('toneStyle')) {
        document.getElementById('toneStyle').value = dna.tone_keywords.slice(0, 5).join(', ');
        fieldsFilledCount++;
        console.log('Filled toneStyle:', dna.tone_keywords);
      }
      
      if (fieldsFilledCount > 0) {
        showAlert(`✅ ${fieldsFilledCount} velden automatisch ingevuld met Site DNA`, 'success', 3000);
      } else {
        console.warn('No fields were filled - DNA data may be empty');
      }
    } catch (error) {
      console.error('Error loading Site DNA:', error);
      showAlert('❌ Fout bij laden Site DNA', 'error', 3000);
    }
  }
  
  // Show crawl button when URL is entered
  if (contextUrlInput) {
    contextUrlInput.addEventListener('input', () => {
      const url = contextUrlInput.value.trim();
      if (url) {
        crawlBtn.style.display = 'block';
        // Reset dropdown selection when typing new URL
        if (existingSiteSelect) {
          existingSiteSelect.value = '';
        }
        // Hide and reset confirmation button
        if (confirmSiteBtn) {
          confirmSiteBtn.style.display = 'none';
          confirmSiteBtn.disabled = false;
          confirmSiteBtn.textContent = '✓ Gebruik deze website';
        }
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
          
          // Refresh the dropdown with newly crawled site
          await loadContextSites();
          
          // Auto-fill form with Site DNA
          if (data.site_dna_generated) {
            await autoFillFromSiteDNA(contextSiteId);
          }
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
    
    console.log('Generate form - Submit button found:', submitBtn);
    console.log('Generate form - Form element:', form);
    
    const formData = new FormData(form);
    
    // Use context site ID if available, otherwise use session
    let siteId = contextSiteId || sessionStorage.getItem('currentSiteId');
    
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
        colors: formData.get('brandColors')?.split(',').map(s => s.trim()).filter(Boolean) || [],
      },
      language: formData.get('language') || 'nl',
      status: formData.get('status') || 'draft',
      generateImage: formData.get('generateImage') === 'on',  // Checkbox value
      imageSettings: {
        preset: formData.get('imagePreset') || 'minimal-tech',
        aspectRatio: formData.get('aspectRatio') || '16:9',
        styleStrength: formData.get('styleStrength') || 'medium',
        useBrandColors: formData.get('useBrandColors') === 'on',
        colorStrictness: formData.get('colorStrictness') || 'medium',
        composition: formData.get('composition') || 'auto',
        lighting: formData.get('lighting') || 'soft-studio',
        lockSeed: formData.get('lockSeed') === 'on',
        seedValue: formData.get('seedValue') ? parseInt(formData.get('seedValue')) : null,
        negativePrompt: formData.get('negativePrompt') || 'blurry, low quality, watermark, text overlay, jpeg artifacts, deformed, pixelated',
        variations: parseInt(formData.get('variations')) || 1,
      },
      multilang: {
        enabled: formData.get('multilangEnabled') === 'true',
        languages: formData.get('multilangLanguages')?.split(',').map(s => s.trim()).filter(Boolean) || [],
        strategy: formData.get('multilangStrategy') || 'translate',
      },
    };
    
    if (formData.get('scheduleDateGmt')) {
      payload.scheduleDateGmt = formData.get('scheduleDateGmt');
    }
    
    console.log('Image Settings:', payload.imageSettings);
    
    setButtonLoading(submitBtn, true);
    
    try {
      const result = await api.generatePost(payload);
      
      console.log('Generate Post Result:', result);
      
      // Extract the actual draft from the result
      const draft = result.draft || (result.drafts && result.drafts[Object.keys(result.drafts)[0]]);
      
      if (!draft) {
        throw new Error('Geen draft ontvangen van API');
      }
      
      // Store draft WITHOUT images to avoid sessionStorage quota issues
      // Images will be stored separately in memory via fillPublishForm
      const draftWithoutImages = {
        ...draft,
        images: undefined  // Remove images array
        // Keep single 'image' field if it exists for compatibility
      };
      
      try {
        sessionStorage.setItem('currentDraft', JSON.stringify(draftWithoutImages));
        sessionStorage.setItem('currentSiteId', siteId);
      } catch (e) {
        console.warn('Could not store draft in sessionStorage (too large):', e);
        // Store minimal version without any images
        const minimalDraft = {
          title: draft.title,
          contentHtml: draft.contentHtml,
          excerpt: draft.excerpt,
          slug: draft.slug
        };
        sessionStorage.setItem('currentDraft', JSON.stringify(minimalDraft));
      }
      
      console.log('Stored draft:', draft);
      console.log('Draft has images array:', draft.images);
      console.log('Draft has single image:', draft.image);
      
      // Store the full draft with images in a module-level variable
      window._currentDraftWithImages = draft;
      
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
    
    // Add image data - always use global variable if available (has full base64 data)
    if (window._currentDraftWithImages && window._currentDraftWithImages.image) {
      draft.image = window._currentDraftWithImages.image;
      console.log('Added image from global variable (with base64 data)');
    } else if (imageData) {
      // Fallback: try sessionStorage (but this only has metadata now)
      try {
        const imageMetadata = JSON.parse(imageData);
        console.warn('Only image metadata available from sessionStorage:', imageMetadata);
        draft.image = imageMetadata;
      } catch (e) {
        console.error('Failed to parse image metadata:', e);
      }
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
  
  // Render preview using the renderPreview function (which uses global _currentDraftWithImages)
  if (previewDiv) {
    renderPreview(draft, previewDiv);
  }
  
  // Store ONLY image metadata (not base64 data) to avoid quota issues
  if (draft.image || draft._image) {
    try {
      const selectedImage = draft.image || draft._image;
      const imageMetadata = {
        imageId: selectedImage.imageId,
        mime_type: selectedImage.mime_type,
        filename: selectedImage.filename
      };
      sessionStorage.setItem('currentDraftImage', JSON.stringify(imageMetadata));
    } catch (e) {
      console.warn('Could not store image metadata:', e);
    }
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
  const previewDiv = document.getElementById('publish-preview');
  
  console.log('Restoring preview - using window._currentDraftWithImages');
  
  if (!previewDiv) return;
  
  try {
    // Prefer full draft with images from memory
    let draft;
    if (window._currentDraftWithImages) {
      draft = window._currentDraftWithImages;
      console.log('Using full draft from memory with images');
    } else if (draftData) {
      draft = JSON.parse(draftData);
      console.log('Using draft from sessionStorage (no images)');
    } else {
      return;
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
  
  // Add image data from memory (has full base64 data)
  if (window._currentDraftWithImages && window._currentDraftWithImages.image) {
    draft.image = window._currentDraftWithImages.image;
  }
  
  renderPreview(draft, previewDiv);
}

// Render preview HTML
function renderPreview(draft, previewDiv) {
  console.log('renderPreview called with draft:', draft);
  
  // Use the full draft with images if available
  const fullDraft = window._currentDraftWithImages || draft;
  
  let previewHtml = '';
  
  // Featured image(s) - handle single or multiple variations
  const images = fullDraft.images || (fullDraft.image ? [fullDraft.image] : []);
  const imageToDisplay = fullDraft.image || fullDraft._image;
  
  console.log('Images to render:', images);
  console.log('Images array length:', images.length);
  
  if (images.length > 0) {
    previewHtml += `
      <div class="card" style="margin-bottom: var(--spacing-lg);">
        <div class="card-header">
          <h3>Featured Image ${images.length > 1 ? `(${images.length} variations)` : ''}</h3>
        </div>
        <div class="card-body">
    `;
    
    // Show all variations if multiple
    if (images.length > 1) {
      previewHtml += '<div id="image-variations-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px;">';
      images.forEach((img, index) => {
        const isSelected = index === 0; // First one is default
        const borderStyle = isSelected ? '4px solid #10b981' : '2px solid #e2e8f0';
        const boxShadow = isSelected ? '0 0 0 3px rgba(16, 185, 129, 0.2)' : 'none';
        
        // Extract feedback chain if available
        const feedbackChain = img.feedbackChain || [];
        const generationNumber = img.generationNumber || 1;
        const imageId = img.imageId;
        
        previewHtml += `
          <div class="image-variation-card" style="position: relative; border: ${borderStyle}; box-shadow: ${boxShadow}; border-radius: 8px; padding: 8px; cursor: pointer; transition: all 0.2s ease;" 
               data-variation-index="${index}"
               data-image-id="${imageId || ''}">
            ${isSelected ? '<div class="variation-selected-badge" style="position: absolute; top: 12px; right: 12px; background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);">✓ Geselecteerd</div>' : ''}
            <img src="data:${img.mime_type || img.mime};base64,${img.bytes_base64}" 
                 alt="Variation ${index + 1}" 
                 style="max-width: 100%; height: auto; border-radius: 4px; pointer-events: none;" />
            <div style="text-align: center; margin-top: 8px; font-size: 13px; color: var(--text-secondary);">Variation ${index + 1}</div>
            
            ${feedbackChain.length > 0 ? `
              <div class="feedback-history" style="margin-top: 12px; padding: 8px; background: #f3f4f6; border-radius: 4px; font-size: 12px;">
                <div style="font-weight: 600; color: #374151; margin-bottom: 4px;">Toegepaste feedback:</div>
                <ol style="margin: 0; padding-left: 20px; color: #6b7280;">
                  ${feedbackChain.map(fb => `<li>${escapeHtml(fb)}</li>`).join('')}
                </ol>
              </div>
            ` : ''}
          </div>
        `;
      });
      previewHtml += '</div>';
      previewHtml += '<div style="margin-top: 16px; padding: 12px; background: #ecfdf5; border-left: 4px solid #10b981; border-radius: 8px; color: #047857; font-size: 14px;">💡 <strong>Tip:</strong> Klik op een image om deze te selecteren voor publicatie</div>';
      
      // Add regeneration controls for selected image
      previewHtml += `
        <div id="regenerate-section" style="margin-top: 24px;">
          <div class="card">
            <div class="card-header">
              <h4>🔄 Regenereer Geselecteerde Afbeelding</h4>
            </div>
            <div class="card-body">
              <p style="color: var(--text-secondary); margin-bottom: 16px;">Geef feedback om de geselecteerde afbeelding te verbeteren. Alle vorige feedback blijft behouden.</p>
              <textarea id="regenerate-feedback" 
                        placeholder="bijv. 'maak het feller', 'voeg bergen toe op de achtergrond', 'meer blauw gebruiken'..."
                        rows="3"
                        style="width: 100%; padding: 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; font-family: inherit; resize: vertical;"></textarea>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px;">
                <span id="regenerate-counter" style="font-size: 13px; color: var(--text-secondary);">Generatie <span id="gen-current">1</span> van 3</span>
                <button id="regenerate-btn" 
                        onclick="regenerateImage()"
                        class="btn btn-primary"
                        style="display: inline-flex; align-items: center; gap: 8px;">
                  <span>🔄 Regenereer</span>
                </button>
              </div>
              <div id="regenerate-status" style="margin-top: 12px; display: none;"></div>
            </div>
          </div>
        </div>
      `;
    } else if (imageToDisplay && imageToDisplay.bytes_base64) {
      // Single image
      const feedbackChain = imageToDisplay.feedbackChain || [];
      const generationNumber = imageToDisplay.generationNumber || 1;
      const imageId = imageToDisplay.imageId;
      
      previewHtml += `
        <div data-image-id="${imageId || ''}">
          <img src="data:${imageToDisplay.mime_type || imageToDisplay.mime};base64,${imageToDisplay.bytes_base64}" 
               alt="Featured Image" 
               style="max-width: 100%; height: auto; border-radius: var(--radius-md); box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />
          
          ${feedbackChain.length > 0 ? `
            <div class="feedback-history" style="margin-top: 16px; padding: 12px; background: #f3f4f6; border-radius: 8px; font-size: 13px;">
              <div style="font-weight: 600; color: #374151; margin-bottom: 8px;">Toegepaste feedback:</div>
              <ol style="margin: 0; padding-left: 20px; color: #6b7280;">
                ${feedbackChain.map(fb => `<li>${escapeHtml(fb)}</li>`).join('')}
              </ol>
            </div>
          ` : ''}
        </div>
      `;
      
      // Add regeneration controls
      previewHtml += `
        <div id="regenerate-section" style="margin-top: 24px;">
          <div style="padding: 16px; background: #f9fafb; border: 2px solid #e2e8f0; border-radius: 8px;">
            <h4 style="margin: 0 0 12px 0; font-size: 16px; color: #111827;">🔄 Regenereer Afbeelding</h4>
            <p style="color: var(--text-secondary); margin-bottom: 12px; font-size: 14px;">Geef feedback om de afbeelding te verbeteren. Alle vorige feedback blijft behouden.</p>
            <textarea id="regenerate-feedback" 
                      placeholder="bijv. 'maak het feller', 'voeg bergen toe op de achtergrond', 'meer blauw gebruiken'..."
                      rows="3"
                      style="width: 100%; padding: 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; font-family: inherit; resize: vertical;"></textarea>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px;">
              <span id="regenerate-counter" style="font-size: 13px; color: var(--text-secondary);">Generatie <span id="gen-current">${generationNumber}</span> van 3 ${generationNumber >= 3 ? '(Maximum bereikt)' : ''}</span>
              <button id="regenerate-btn" 
                      onclick="regenerateImage()"
                      class="btn btn-primary"
                      ${generationNumber >= 3 ? 'disabled' : ''}
                      style="display: inline-flex; align-items: center; gap: 8px;">
                <span>${generationNumber >= 3 ? '✓ Maximum bereikt' : '🔄 Regenereer'}</span>
              </button>
            </div>
            <div id="regenerate-status" style="margin-top: 12px; display: none;"></div>
          </div>
        </div>
      `;
    }
    
    previewHtml += `
        </div>
      </div>
    `;
  }
  
  // Content preview - separate card
  previewHtml += '<div class="card" style="margin-bottom: var(--spacing-lg);">';
  previewHtml += '<div class="card-header"><h3>Content Preview</h3></div>';
  previewHtml += '<div class="card-body">';
  previewHtml += `<h2>${fullDraft.title || 'Geen titel'}</h2>`;
  if (fullDraft.excerpt) {
    previewHtml += `<p style="color: var(--text-secondary); font-style: italic;">${fullDraft.excerpt}</p>`;
  }
  previewHtml += '<hr style="margin: var(--spacing-lg) 0;">';
  previewHtml += `<div style="line-height: 1.6;">${fullDraft.contentHtml || 'Geen content'}</div>`;
  previewHtml += '</div></div>';
  
  previewDiv.innerHTML = previewHtml;
  previewDiv.style.display = 'block';
  
  // Setup event delegation for image variation selection
  const variationsContainer = previewDiv.querySelector('#image-variations-container');
  if (variationsContainer) {
    variationsContainer.addEventListener('click', (e) => {
      const card = e.target.closest('.image-variation-card');
      if (card) {
        const index = parseInt(card.dataset.variationIndex);
        selectImageVariation(index);
      }
    });
  }
}

// Select image variation
function selectImageVariation(index) {
  console.log('Selecting variation:', index);
  
  // Use the global draft with images
  const draft = window._currentDraftWithImages;
  if (!draft) {
    console.error('No draft with images available');
    return;
  }
  
  try {
    // If we have multiple variations, select the chosen one
    if (draft.images && draft.images[index]) {
      draft.image = draft.images[index];
      
      // Store ONLY image metadata (without base64 data) to avoid quota issues
      try {
        const imageMetadata = {
          imageId: draft.image.imageId,
          mime_type: draft.image.mime_type,
          filename: draft.image.filename
        };
        sessionStorage.setItem('currentDraftImage', JSON.stringify(imageMetadata));
      } catch (e) {
        console.warn('Could not store image metadata in sessionStorage:', e);
      }
      
      // Update visual feedback - remove all selected badges first
      const container = document.querySelector('#image-variations-container');
      if (container) {
        const allCards = container.querySelectorAll('.image-variation-card');
        allCards.forEach((card, i) => {
          const badge = card.querySelector('.variation-selected-badge');
          if (badge) badge.remove();
          
          // Update border - groene rand voor geselecteerde
          if (i === index) {
            card.style.border = '4px solid #10b981';
            card.style.boxShadow = '0 0 0 3px rgba(16, 185, 129, 0.2)';
            // Add selected badge
            const newBadge = document.createElement('div');
            newBadge.className = 'variation-selected-badge';
            newBadge.style.cssText = 'position: absolute; top: 12px; right: 12px; background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);';
            newBadge.textContent = '✓ Geselecteerd';
            card.insertBefore(newBadge, card.firstChild);
          } else {
            card.style.border = '2px solid #e2e8f0';
            card.style.boxShadow = 'none';
          }
        });
      }
      
      showAlert(`Variation ${index + 1} geselecteerd!`, 'success', 2000);
    } else {
      console.error('No image at index:', index);
    }
  } catch (e) {
    console.error('Error selecting variation:', e);
  }
}

// Make function globally available
window.selectImageVariation = selectImageVariation;

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

// Regenerate image with feedback
async function regenerateImage() {
  const feedbackTextarea = document.getElementById('regenerate-feedback');
  const regenerateBtn = document.getElementById('regenerate-btn');
  const statusDiv = document.getElementById('regenerate-status');
  
  if (!feedbackTextarea || !regenerateBtn) {
    console.error('Regenerate controls not found');
    return;
  }
  
  const feedback = feedbackTextarea.value.trim();
  
  if (!feedback) {
    statusDiv.style.display = 'block';
    statusDiv.innerHTML = '<div style="padding: 12px; background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; border-radius: 4px;">⚠️ Voer feedback in om de afbeelding te regenereren.</div>';
    return;
  }
  
  if (feedback.length < 5) {
    statusDiv.style.display = 'block';
    statusDiv.innerHTML = '<div style="padding: 12px; background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; border-radius: 4px;">⚠️ Feedback moet minimaal 5 karakters bevatten.</div>';
    return;
  }
  
  // Get selected image ID
  const draft = window._currentDraftWithImages;
  if (!draft || !draft.image || !draft.image.imageId) {
    statusDiv.style.display = 'block';
    statusDiv.innerHTML = '<div style="padding: 12px; background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; border-radius: 4px;">⚠️ Geen afbeelding geselecteerd voor regeneratie.</div>';
    return;
  }
  
  const parentId = draft.image.imageId;
  
  // Disable button and show loading
  regenerateBtn.disabled = true;
  regenerateBtn.innerHTML = '<span>⏳ Regenereren...</span>';
  statusDiv.style.display = 'block';
  statusDiv.innerHTML = '<div style="padding: 12px; background: #eff6ff; border-left: 4px solid #3b82f6; color: #1e40af; border-radius: 4px;">🔄 Afbeelding wordt gegenereerd met je feedback...</div>';
  
  try {
    const response = await fetch('/api/image/regenerate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        parentId: parentId,
        feedback: feedback
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Regeneratie mislukt');
    }
    
    const data = await response.json();
    
    // Update draft with new image
    draft.image = data.image;
    
    // If multiple variations, replace the selected one
    if (draft.images) {
      const selectedIndex = draft.images.findIndex(img => img.imageId === parentId);
      if (selectedIndex >= 0) {
        draft.images[selectedIndex] = data.image;
      } else {
        // Add as new variation
        draft.images.push(data.image);
      }
    }
    
    // Update in global state (with full image data)
    window._currentDraftWithImages = draft;
    
    // Store draft WITHOUT base64 image data to avoid quota issues
    try {
      const draftMetadata = {
        ...draft,
        image: draft.image ? {
          imageId: draft.image.imageId,
          mime_type: draft.image.mime_type,
          filename: draft.image.filename
        } : undefined,
        images: draft.images ? draft.images.map(img => ({
          imageId: img.imageId,
          mime_type: img.mime_type,
          filename: img.filename
        })) : undefined
      };
      sessionStorage.setItem('currentDraft', JSON.stringify(draftMetadata));
    } catch (e) {
      console.warn('Could not store draft metadata:', e);
    }
    
    // Clear feedback textarea
    feedbackTextarea.value = '';
    
    // Show success and refresh preview
    statusDiv.innerHTML = '<div style="padding: 12px; background: #ecfdf5; border-left: 4px solid #10b981; color: #047857; border-radius: 4px;">✓ Afbeelding succesvol geregenereerd!</div>';
    
    // Refresh the preview immediately
    showDraftPreview(draft);
    showAlert('Afbeelding geregenereerd met je feedback!', 'success', 3000);
    
  } catch (error) {
    console.error('Regeneration error:', error);
    statusDiv.innerHTML = `<div style="padding: 12px; background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; border-radius: 4px;">❌ ${error.message}</div>`;
    regenerateBtn.disabled = false;
    regenerateBtn.innerHTML = '<span>🔄 Regenereer</span>';
  }
}

// HTML escape utility
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Load drafts from database
async function loadDrafts() {
  const draftsListDiv = document.getElementById('drafts-list');
  if (!draftsListDiv) return;

  try {
    draftsListDiv.innerHTML = '<p class="text-muted">Laden...</p>';
    
    const response = await api.getDrafts();
    const drafts = response.drafts || [];

    if (drafts.length === 0) {
      draftsListDiv.innerHTML = '<p class="text-muted">Geen opgeslagen concepten gevonden.</p>';
      return;
    }

    // Render drafts list
    let html = '<div style="display: flex; flex-direction: column; gap: 1rem;">';
    
    for (const item of drafts) {
      const draft = item.draft;
      const createdAt = new Date(item.created_at);
      const title = draft.title || 'Geen titel';
      const excerpt = draft.excerpt || '';
      const truncatedExcerpt = excerpt.length > 150 
        ? excerpt.substring(0, 150) + '...' 
        : excerpt;

      html += `
        <div class="draft-item" style="padding: 1rem; border: 1px solid var(--border-color); border-radius: var(--radius-md); background: var(--bg-secondary);">
          <div style="display: flex; justify-content: space-between; align-items: start; gap: 1rem;">
            <div style="flex: 1;">
              <h4 style="margin: 0 0 0.5rem 0; font-size: 1.1rem; color: var(--text-primary);">${escapeHtml(title)}</h4>
              ${truncatedExcerpt ? `<p style="margin: 0 0 0.5rem 0; color: var(--text-secondary); font-size: 0.9rem;">${escapeHtml(truncatedExcerpt)}</p>` : ''}
              <p style="margin: 0; color: var(--text-muted); font-size: 0.85rem;">
                Aangemaakt: ${formatDate(createdAt)}
              </p>
            </div>
            <div style="display: flex; gap: 0.5rem;">
              <button 
                class="btn btn-primary btn-sm" 
                onclick="loadDraft(${item.id})"
                style="white-space: nowrap;"
              >
                Laden
              </button>
              <button 
                class="btn btn-secondary btn-sm" 
                onclick="deleteDraftById(${item.id})"
                style="white-space: nowrap; background: var(--error); color: white;"
              >
                Verwijderen
              </button>
            </div>
          </div>
        </div>
      `;
    }
    
    html += '</div>';
    draftsListDiv.innerHTML = html;

  } catch (error) {
    console.error('Error loading drafts:', error);
    draftsListDiv.innerHTML = '<p class="text-muted" style="color: var(--error);">Fout bij laden van concepten.</p>';
  }
}

// Load a specific draft
async function loadDraft(draftId) {
  try {
    const draftData = await api.getDraft(draftId);
    const draft = draftData.draft;

    // Fetch full image data if we have imageId but not bytes_base64
    if (draft.image && draft.image.imageId && !draft.image.bytes_base64) {
      try {
        console.log('Fetching full image data for imageId:', draft.image.imageId);
        const fullImage = await api.getImage(draft.image.imageId);
        draft.image = fullImage;
      } catch (e) {
        console.warn('Could not load full image data:', e);
      }
    }

    // Fetch full image data for multiple variations
    if (draft.images && Array.isArray(draft.images)) {
      const imagePromises = draft.images.map(async (img) => {
        if (img.imageId && !img.bytes_base64) {
          try {
            return await api.getImage(img.imageId);
          } catch (e) {
            console.warn('Could not load full image data for variation:', e);
            return img;
          }
        }
        return img;
      });
      draft.images = await Promise.all(imagePromises);
    }

    // Store in sessionStorage and global variable
    window._currentDraftWithImages = draft;
    
    // Store draft WITHOUT base64 image data to avoid quota issues
    try {
      const draftMetadata = {
        ...draft,
        image: draft.image ? {
          imageId: draft.image.imageId,
          mime_type: draft.image.mime_type,
          filename: draft.image.filename
        } : undefined,
        images: draft.images ? draft.images.map(img => ({
          imageId: img.imageId,
          mime_type: img.mime_type,
          filename: img.filename
        })) : undefined
      };
      sessionStorage.setItem('currentDraft', JSON.stringify(draftMetadata));
    } catch (e) {
      console.warn('Could not store draft metadata:', e);
    }

    // Fill form fields
    const titleInput = document.getElementById('title');
    const contentInput = document.getElementById('content');
    
    if (titleInput && draft.title) {
      titleInput.value = draft.title;
    }
    if (contentInput && draft.contentHtml) {
      contentInput.value = draft.contentHtml;
    }

    // Restore preview
    restorePublishPreview();

    showAlert('Concept geladen!', 'success');
  } catch (error) {
    console.error('Error loading draft:', error);
    showAlert('Fout bij laden van concept: ' + error.message, 'error');
  }
}

// Delete a draft
async function deleteDraftById(draftId) {
  if (!confirm('Weet je zeker dat je dit concept wilt verwijderen?')) {
    return;
  }

  try {
    await api.deleteDraft(draftId);
    showAlert('Concept verwijderd!', 'success');
    
    // Reload drafts list
    await loadDrafts();
  } catch (error) {
    console.error('Error deleting draft:', error);
    showAlert('Fout bij verwijderen van concept: ' + error.message, 'error');
  }
}

// Make functions globally available
window.regenerateImage = regenerateImage;
window.escapeHtml = escapeHtml;
window.loadDraft = loadDraft;
window.deleteDraftById = deleteDraftById;
