/**
 * Main Application Logic
 */

import { api, pollJob } from './api.js';
import { showAlert, showModal, setButtonLoading, formatDate, formatJobStatus } from './ui.js';

let activeDraftId = null;
let draftAutosaveTimeout = null;
let draftSaveInFlight = false;
let lastSavedDraftSignature = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
  initializeActiveDraftId();
  loadSitesDropdowns(); // Load sites into dropdowns
  initConnectSite();
  initGeneratePost();
  initPublishPost();
  initJobsView();
  
  // Check API health
  checkHealth();
});

function initializeActiveDraftId() {
  const storedDraftId = sessionStorage.getItem('currentDraftId');
  if (!storedDraftId) {
    sessionStorage.removeItem('currentDraft');
    sessionStorage.removeItem('currentDraftImage');
    return;
  }

  const parsedDraftId = Number(storedDraftId);
  if (Number.isFinite(parsedDraftId) && parsedDraftId > 0) {
    activeDraftId = parsedDraftId;
  }
}

function setActiveDraftId(draftId) {
  const parsedDraftId = Number(draftId);
  if (Number.isFinite(parsedDraftId) && parsedDraftId > 0) {
    activeDraftId = parsedDraftId;
    sessionStorage.setItem('currentDraftId', String(parsedDraftId));
    return;
  }

  activeDraftId = null;
  sessionStorage.removeItem('currentDraftId');
  sessionStorage.removeItem('currentDraft');
  sessionStorage.removeItem('currentDraftImage');
  window._currentDraftWithImages = null;
  lastSavedDraftSignature = null;
  clearPublishPreview();
}

function clearPublishPreview() {
  const previewDiv = document.getElementById('publish-preview');
  if (!previewDiv) return;

  previewDiv.innerHTML = '';
  previewDiv.style.display = 'none';
}

function toDraftMetadata(draft) {
  return {
    ...draft,
    image: draft.image ? {
      imageId: draft.image.imageId,
      mime_type: draft.image.mime_type,
      filename: draft.image.filename,
      url: draft.image.url,
      sourceUrl: draft.image.sourceUrl
    } : undefined,
    images: draft.images ? draft.images.map(img => ({
      imageId: img.imageId,
      mime_type: img.mime_type,
      filename: img.filename,
      url: img.url,
      sourceUrl: img.sourceUrl
    })) : undefined
  };
}

function persistDraftState(draft) {
  window._currentDraftWithImages = draft;

  try {
    sessionStorage.setItem('currentDraft', JSON.stringify(toDraftMetadata(draft)));
  } catch (e) {
    console.warn('Could not store draft metadata:', e);
    const minimalDraft = {
      title: draft.title,
      contentHtml: draft.contentHtml,
      excerpt: draft.excerpt,
      slug: draft.slug
    };
    sessionStorage.setItem('currentDraft', JSON.stringify(minimalDraft));
  }

  if (draft.image) {
    try {
      const imageMetadata = {
        imageId: draft.image.imageId,
        mime_type: draft.image.mime_type,
        filename: draft.image.filename,
        url: draft.image.url,
        sourceUrl: draft.image.sourceUrl
      };
      sessionStorage.setItem('currentDraftImage', JSON.stringify(imageMetadata));
    } catch (e) {
      console.warn('Could not store image metadata:', e);
    }
  }
}

function toWpGmtDate(localDateTimeValue) {
  if (!localDateTimeValue) return null;
  const localDate = new Date(localDateTimeValue);
  if (Number.isNaN(localDate.getTime())) {
    return null;
  }

  const year = localDate.getUTCFullYear();
  const month = String(localDate.getUTCMonth() + 1).padStart(2, '0');
  const day = String(localDate.getUTCDate()).padStart(2, '0');
  const hours = String(localDate.getUTCHours()).padStart(2, '0');
  const minutes = String(localDate.getUTCMinutes()).padStart(2, '0');
  const seconds = String(localDate.getUTCSeconds()).padStart(2, '0');

  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
}

function fromWpGmtDateToLocalInput(gmtDateValue) {
  if (!gmtDateValue) return '';

  const withTimezone = gmtDateValue.endsWith('Z')
    ? gmtDateValue
    : `${gmtDateValue}Z`;

  const utcDate = new Date(withTimezone);
  if (Number.isNaN(utcDate.getTime())) {
    return '';
  }

  const year = utcDate.getFullYear();
  const month = String(utcDate.getMonth() + 1).padStart(2, '0');
  const day = String(utcDate.getDate()).padStart(2, '0');
  const hours = String(utcDate.getHours()).padStart(2, '0');
  const minutes = String(utcDate.getMinutes()).padStart(2, '0');

  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function setPublishSchedulingFields(draft = {}) {
  const isDraftCheckbox = document.getElementById('isDraft');
  const isScheduledCheckbox = document.getElementById('isScheduled');
  const scheduleDateGroup = document.getElementById('schedule-date-group');
  const scheduleDateInput = document.getElementById('scheduleDateLocal');

  if (!isDraftCheckbox || !isScheduledCheckbox || !scheduleDateGroup || !scheduleDateInput) {
    return;
  }

  const status = draft.status || 'draft';
  const isScheduled = status === 'future';

  isScheduledCheckbox.checked = isScheduled;
  isDraftCheckbox.checked = status === 'draft';
  isDraftCheckbox.disabled = isScheduled;

  scheduleDateGroup.style.display = isScheduled ? 'block' : 'none';
  scheduleDateInput.required = isScheduled;
  scheduleDateInput.value = isScheduled
    ? fromWpGmtDateToLocalInput(draft.scheduleDateGmt)
    : '';
}

function syncPublishStatusControls() {
  const isDraftCheckbox = document.getElementById('isDraft');
  const isScheduledCheckbox = document.getElementById('isScheduled');
  const scheduleDateGroup = document.getElementById('schedule-date-group');
  const scheduleDateInput = document.getElementById('scheduleDateLocal');

  if (!isDraftCheckbox || !isScheduledCheckbox || !scheduleDateGroup || !scheduleDateInput) {
    return;
  }

  if (isScheduledCheckbox.checked) {
    isDraftCheckbox.checked = false;
    isDraftCheckbox.disabled = true;
    scheduleDateGroup.style.display = 'block';
    scheduleDateInput.required = true;
  } else {
    isDraftCheckbox.disabled = false;
    scheduleDateGroup.style.display = 'none';
    scheduleDateInput.required = false;
    scheduleDateInput.value = '';
  }
}

function buildDraftFromPublishForm(publishForm) {
  const formData = new FormData(publishForm);

  let baseDraft = {};
  if (window._currentDraftWithImages) {
    baseDraft = { ...window._currentDraftWithImages };
  } else {
    const draftData = sessionStorage.getItem('currentDraft');
    if (draftData) {
      try {
        baseDraft = JSON.parse(draftData);
      } catch (e) {
        console.warn('Could not parse currentDraft from sessionStorage:', e);
      }
    }
  }

  const isScheduled = formData.get('isScheduled') === 'on';
  const scheduleDateLocal = formData.get('scheduleDateLocal');

  let status = 'publish';
  if (isScheduled) {
    status = 'future';
  } else if (formData.get('isDraft') === 'on') {
    status = 'draft';
  }

  const draft = {
    ...baseDraft,
    title: formData.get('title') || '',
    contentHtml: formData.get('content') || '',
    status
  };

  if (isScheduled) {
    draft.scheduleDateGmt = toWpGmtDate(scheduleDateLocal);
  } else {
    delete draft.scheduleDateGmt;
  }

  if (window._currentDraftWithImages?.image) {
    draft.image = window._currentDraftWithImages.image;
  }
  if (window._currentDraftWithImages?.images) {
    draft.images = window._currentDraftWithImages.images;
  }

  return draft;
}

function getDraftSignature(draft) {
  const signaturePayload = {
    title: draft.title || '',
    contentHtml: draft.contentHtml || '',
    status: draft.status || 'draft',
    scheduleDateGmt: draft.scheduleDateGmt || '',
    imageId: draft.image?.imageId || '',
    imageUrl: draft.image?.url || draft.image?.sourceUrl || '',
    imageFilename: draft.image?.filename || ''
  };

  return JSON.stringify(signaturePayload);
}

async function saveCurrentDraft({ showSuccess = false, silent = false, button = null } = {}) {
  if (!activeDraftId) {
    if (showSuccess && !silent) {
      showAlert('Laad eerst een bestaand concept om op te slaan.', 'error');
    }
    return false;
  }

  const publishForm = document.getElementById('publish-post-form');
  if (!publishForm) {
    return false;
  }

  const draft = buildDraftFromPublishForm(publishForm);
  const draftSignature = getDraftSignature(draft);
  if (!showSuccess && draftSignature === lastSavedDraftSignature) {
    return true;
  }

  if (draftSaveInFlight) {
    return false;
  }

  draftSaveInFlight = true;
  if (button) {
    setButtonLoading(button, true);
  }

  try {
    const response = await api.updateDraft(activeDraftId, draft);
    const savedDraft = response?.draft?.draft || draft;
    persistDraftState(savedDraft);
    lastSavedDraftSignature = getDraftSignature(savedDraft);

    if (showSuccess && !silent) {
      showAlert('Concept opgeslagen!', 'success', 2000);
    }
    return true;
  } catch (error) {
    console.error('Save draft error:', error);
    if (!silent) {
      showAlert('Fout bij opslaan van concept: ' + error.message, 'error');
    }
    return false;
  } finally {
    draftSaveInFlight = false;
    if (button) {
      setButtonLoading(button, false);
    }
  }
}

function queueDraftAutosave() {
  if (!activeDraftId) return;

  clearTimeout(draftAutosaveTimeout);
  draftAutosaveTimeout = setTimeout(() => {
    saveCurrentDraft({ silent: true });
  }, 1200);
}

// Connect Site
function initConnectSite() {
  const form = document.getElementById('connect-site-form');
  const connectorSelect = document.getElementById('connectorType');
  const connectorSitesPanel = document.getElementById('connector-sites-panel');
  const connectedSitesList = document.getElementById('connected-sites-list');
  const showConnectFormBtn = document.getElementById('show-connect-form-btn');
  const connectFormPanel = document.getElementById('connect-form-panel');
  const connectFormTitle = document.getElementById('connect-form-title');
  const connectFormDescription = document.getElementById('connect-form-description');
  const connectFormContext = document.getElementById('connect-form-context');
  const baseUrlInput = document.getElementById('wpBaseUrl');
  const usernameInput = document.getElementById('wpUsername');
  const passwordInput = document.getElementById('wpApplicationPassword');
  if (!form) return;

  let connectedSites = [];

  function renderConnectedSites() {
    if (!connectedSitesList) {
      return;
    }

    if (connectedSites.length === 0) {
      connectedSitesList.innerHTML = `
        <div class="connector-empty-state">
          Nog geen WordPress website verbonden. Kies hieronder voor een nieuwe verbinding om te starten.
        </div>
      `;
      return;
    }

    connectedSitesList.innerHTML = connectedSites.map((site) => `
      <button type="button" class="connector-site-button" data-site-id="${site.id}">
        <div class="connector-site-copy">
          <span class="connector-site-name">${site.wp_base_url}</span>
          <p class="connector-site-meta">Gebruiker: ${site.wp_username}</p>
        </div>
        <span class="badge badge-primary">Openen</span>
      </button>
    `).join('');
  }

  function showFormForSite(site = null) {
    if (!connectFormPanel || !connectFormTitle || !connectFormDescription || !connectFormContext) {
      return;
    }

    connectFormPanel.classList.remove('hidden');

    if (site) {
      connectFormTitle.textContent = 'Verbonden WordPress Site';
      connectFormDescription.textContent = 'Werk deze verbinding bij of vervang ze met een nieuwe application password.';
      connectFormContext.classList.remove('hidden');
      connectFormContext.classList.remove('alert-warning');
      connectFormContext.classList.add('alert-info');
      connectFormContext.innerHTML = `
        <span>Je bekijkt de verbinding voor <strong>${site.wp_base_url}</strong>. Vul opnieuw een application password in om deze verbinding te updaten.</span>
      `;
      if (baseUrlInput) baseUrlInput.value = site.wp_base_url || '';
      if (usernameInput) usernameInput.value = site.wp_username || '';
      if (passwordInput) passwordInput.value = '';
    } else {
      connectFormTitle.textContent = 'Nieuwe WordPress Site Verbinden';
      connectFormDescription.textContent = 'Vul je WordPress-gegevens in om een nieuwe verbinding te maken.';
      form.reset();
      connectFormContext.classList.remove('hidden');
      connectFormContext.classList.remove('alert-info');
      connectFormContext.classList.add('alert-warning');
      connectFormContext.innerHTML = connectedSites.length > 0
        ? '<span>Je hebt al een WordPress site verbonden. Als je nu opslaat, wordt de bestaande verbinding vervangen.</span>'
        : '<span>Vul hieronder je eerste WordPress verbinding in.</span>';
    }
  }

  async function loadConnectedSites() {
    if (!connectorSelect || connectorSelect.value !== 'wordpress') {
      if (connectorSitesPanel) connectorSitesPanel.classList.add('hidden');
      if (connectFormPanel) connectFormPanel.classList.add('hidden');
      return;
    }

    try {
      const sitesResponse = await api.getSites();
      connectedSites = Array.isArray(sitesResponse)
        ? sitesResponse
        : (Array.isArray(sitesResponse?.sites) ? sitesResponse.sites : []);

      renderConnectedSites();

      if (connectorSitesPanel) {
        connectorSitesPanel.classList.remove('hidden');
      }
    } catch (error) {
      console.error('Error loading connected sites:', error);
      connectedSites = [];
      if (connectedSitesList) {
        connectedSitesList.innerHTML = `
          <div class="connector-empty-state">
            Verbonden websites konden niet geladen worden. Probeer de pagina opnieuw te laden.
          </div>
        `;
      }
      if (connectorSitesPanel) {
        connectorSitesPanel.classList.remove('hidden');
      }
    }
  }

  if (connectorSelect) {
    connectorSelect.addEventListener('change', async () => {
      await loadConnectedSites();
    });
  }

  if (connectedSitesList) {
    connectedSitesList.addEventListener('click', (event) => {
      const siteButton = event.target.closest('[data-site-id]');
      if (!siteButton) {
        return;
      }

      const selectedSite = connectedSites.find((site) => String(site.id) === String(siteButton.dataset.siteId));
      if (selectedSite) {
        showFormForSite(selectedSite);
      }
    });
  }

  if (showConnectFormBtn) {
    showConnectFormBtn.addEventListener('click', () => {
      showFormForSite();
    });
  }
  
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
      await loadConnectedSites();
      
      // Store siteId for later use
      sessionStorage.setItem('currentSiteId', result.siteId);

      const savedSite = connectedSites.find((site) => String(site.id) === String(result.siteId));
      showFormForSite(savedSite || null);
      
    } catch (error) {
      showAlert(error.message || 'Fout bij verbinden met WordPress', 'error');
    } finally {
      setButtonLoading(submitBtn, false);
    }
  });

  if (connectorSelect && connectorSelect.value === 'wordpress') {
    loadConnectedSites();
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
  const existingSitesDivider = document.getElementById('existing-sites-divider');
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
        if (existingSitesDivider) {
          existingSitesDivider.style.display = 'block';
        }
        
        // Clear existing options except first
        existingSiteSelect.innerHTML = '<option value="">-- Kies een website --</option>';
        
        // Add sites to dropdown and indicate whether Site DNA is available.
        data.sites.forEach(site => {
          const option = document.createElement('option');
          option.value = site.id;
          const label = site.brandName || site.baseUrl;
          option.textContent = site.hasDna ? `${label} ✓` : `${label} (zonder DNA)`;
          existingSiteSelect.appendChild(option);
        });

        console.log(`Loaded ${data.sites.length} context sites`);
      } else {
        if (existingSitesDivider) {
          existingSitesDivider.style.display = 'none';
        }
        console.log('No context sites found');
      }
    } catch (error) {
      if (existingSitesDivider) {
        existingSitesDivider.style.display = 'none';
      }
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

  // Restore initial UI state (e.g., browser auto-fill or persisted selection)
  function syncContextUiState() {
    if (!contextUrlInput || !crawlBtn || !contextStatusDiv) {
      return;
    }

    const hasUrl = Boolean(contextUrlInput.value.trim());
    const selectedSiteId = existingSiteSelect ? existingSiteSelect.value : '';

    if (hasUrl) {
      crawlBtn.style.display = 'block';
    }

    if (selectedSiteId && confirmSiteBtn) {
      confirmSiteBtn.style.display = 'block';
      confirmSiteBtn.disabled = false;
      confirmSiteBtn.textContent = '✓ Gebruik deze website';
      crawlBtn.style.display = 'none';
    }
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

  syncContextUiState();
  
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
        negativePrompt: formData.get('negativePrompt') || 'blurry, low quality, watermark, jpeg artifacts, deformed, pixelated',
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
    
    let loadingCleared = false;
    const clearGenerateLoading = () => {
      if (loadingCleared) return;
      loadingCleared = true;
      setButtonLoading(submitBtn, false);
    };

    setButtonLoading(submitBtn, true);
    
    try {
      const result = await api.generatePost(payload);

      // Stop loading as soon as the API call completes.
      clearGenerateLoading();

      // Allow browser paint before potentially heavy preview rendering.
      await new Promise((resolve) => requestAnimationFrame(resolve));
      
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

      if (result.draftId) {
        setActiveDraftId(result.draftId);
      }
      lastSavedDraftSignature = getDraftSignature(draft);
      
      console.log('Stored draft:', draft);
      console.log('Draft has images array:', draft.images);
      console.log('Draft has single image:', draft.image);
      
      // Store the full draft with images in a module-level variable
      persistDraftState(draft);
      
      showAlert('Blog post gegenereerd!' + (contextSiteId ? ' (met website context)' : ''), 'success');
      
      // Automatically fill publish form and switch to publish tab
      fillPublishForm(result, siteId);
      switchToPublishTab();
      
    } catch (error) {
      console.error('Generate error:', error);
      showAlert(error.message || 'Fout bij genereren van blog post', 'error');
    } finally {
      clearGenerateLoading();
    }
  });
}

// Publish Post
function initPublishPost() {
  const publishForm = document.getElementById('publish-post-form');
  if (!publishForm) return;
  const saveDraftBtn = document.getElementById('save-draft-btn');
  const deleteActiveDraftBtn = document.getElementById('delete-active-draft-btn');
  const isScheduledCheckbox = document.getElementById('isScheduled');
  const isDraftCheckbox = document.getElementById('isDraft');

  if (isScheduledCheckbox) {
    isScheduledCheckbox.addEventListener('change', () => {
      syncPublishStatusControls();
      queueDraftAutosave();
    });
  }
  if (isDraftCheckbox) {
    isDraftCheckbox.addEventListener('change', () => {
      queueDraftAutosave();
    });
  }

  syncPublishStatusControls();
  loadDrafts();

  if (activeDraftId) {
    loadDraft(activeDraftId);
  } else {
    restorePublishPreview();
  }
  
  // Setup real-time preview sync
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  
  if (titleInput && contentInput) {
    // Update preview when title or content changes
    titleInput.addEventListener('input', () => {
      updatePublishPreviewFromForm();
      queueDraftAutosave();
    });
    contentInput.addEventListener('input', () => {
      updatePublishPreviewFromForm();
      queueDraftAutosave();
    });
  }

  if (saveDraftBtn) {
    saveDraftBtn.addEventListener('click', async () => {
      await saveCurrentDraft({ showSuccess: true, button: saveDraftBtn });
    });
  }

  if (deleteActiveDraftBtn) {
    deleteActiveDraftBtn.addEventListener('click', async () => {
      if (!activeDraftId) {
        showAlert('Laad eerst een concept om te verwijderen.', 'error');
        return;
      }

      const warningMessage = '⚠️ WAARSCHUWING: Dit verwijdert het geladen concept permanent.\n\nDeze actie kan niet ongedaan worden gemaakt.\n\nWeet je zeker dat je wilt doorgaan?';
      const confirmed = confirm(warningMessage);
      if (!confirmed) {
        return;
      }

      await deleteDraftById(activeDraftId, { skipConfirm: true });
    });
  }
  
  publishForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = publishForm.querySelector('button[type="submit"]');
    // Get form data
    const formData = new FormData(publishForm);
    const pubSiteId = formData.get('pubSiteId');
    
    // Validation
    if (!pubSiteId) {
      showAlert('Selecteer een WordPress site.', 'error');
      return;
    }

    if (formData.get('isScheduled') === 'on') {
      const scheduleDateLocal = formData.get('scheduleDateLocal');
      const scheduleDateGmt = toWpGmtDate(scheduleDateLocal);
      if (!scheduleDateLocal || !scheduleDateGmt) {
        showAlert('Kies een geldige datum/tijd voor geplande publicatie.', 'error');
        return;
      }
    }
    
    const draft = buildDraftFromPublishForm(publishForm);
    persistDraftState(draft);

    if (activeDraftId) {
      await saveCurrentDraft({ silent: true });
    }
    
    // Build payload with correct structure - draft as nested object
    const payload = {
      siteId: pubSiteId,
      draft: draft
    };

    if (activeDraftId) {
      payload.draftId = activeDraftId;
    }
    
    console.log('Publishing payload:', payload);
    
    setButtonLoading(submitBtn, true);
    
    try {
      const result = await api.publishPost(payload);
      
      showAlert(`Publish job gestart! Job ID: ${result.jobId}`, 'success');
      loadDrafts();
      loadJobs();
      
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

  // Tekst hergenereren via selectie-popup
  initSelectionRegenPopup();
}

// ── Floating selection regeneration popup ──────────────────────────────────
let _regenSel = null;
// _regenSel shape A – textarea:  { mode:'textarea', el, start, end, text }
// _regenSel shape B – preview:   { mode:'preview',  range, text, containerId }
let _regenPopupEl = null;
let _regenSelChangeTimer = null;
let _mouseIsDown = false; // true while the primary mouse button is held — never show popup during drag

document.addEventListener('mousedown', (e) => { if (e.button === 0) _mouseIsDown = true; });
document.addEventListener('mouseup',   (e) => { if (e.button === 0) _mouseIsDown = false; });

function _buildRegenPopup() {
  if (_regenPopupEl) return _regenPopupEl;

  const popup = document.createElement('div');
  popup.id = 'regen-selection-popup';
  popup.style.cssText = [
    'display:none',
    'position:fixed',
    'z-index:2147483647',
    'background:#fff',
    'border:1px solid #d0d0d0',
    'border-radius:10px',
    'box-shadow:0 6px 28px rgba(0,0,0,0.22)',
    'padding:14px',
    'width:340px',
    'box-sizing:border-box',
    'font-family:inherit',
  ].join(';');

  popup.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:8px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:0.78rem;font-weight:600;color:#555;">✍ Herschrijf selectie</span>
        <button id="regen-sel-close" style="background:none;border:none;cursor:pointer;font-size:1rem;color:#888;padding:0;line-height:1;" title="Sluiten">✕</button>
      </div>
      <div id="regen-sel-preview" style="font-size:0.74rem;color:#777;background:#f5f5f5;padding:4px 7px;border-radius:4px;max-height:42px;overflow:hidden;font-style:italic;"></div>
      <textarea id="regen-sel-instruction" rows="2"
        placeholder="Aanpasinstructie… (Enter = verzenden, Shift+Enter = nieuwe regel)"
        style="width:100%;box-sizing:border-box;padding:6px 8px;border:1px solid #ccc;border-radius:6px;font-size:0.85rem;resize:vertical;font-family:inherit;"></textarea>
      <div style="display:flex;gap:8px;align-items:center;">
        <button id="regen-sel-btn"
          style="background:#0070f3;color:#fff;border:none;border-radius:6px;padding:6px 16px;font-size:0.85rem;cursor:pointer;font-family:inherit;">
          Hergenereren
        </button>
        <span id="regen-sel-status" style="font-size:0.8rem;color:#666;"></span>
      </div>
    </div>`;

  document.body.appendChild(popup);
  _regenPopupEl = popup;
  return popup;
}

function _hideRegenPopup() {
  if (_regenPopupEl) _regenPopupEl.style.display = 'none';
  _regenSel = null;
}

function _rangeToHtml(range) {
  const wrapper = document.createElement('div');
  wrapper.appendChild(range.cloneContents());
  return wrapper.innerHTML;
}

function _positionAndShowPopup(selectedText, selData, anchorX, anchorY) {
  const popup = _buildRegenPopup();
  _regenSel = selData;

  const previewEl = popup.querySelector('#regen-sel-preview');
  if (previewEl) {
    previewEl.textContent = selectedText.length > 90
      ? selectedText.substring(0, 90) + '…'
      : selectedText;
  }
  popup.querySelector('#regen-sel-status').textContent = '';
  popup.querySelector('#regen-sel-instruction').value = '';

  // Measure before final position
  popup.style.visibility = 'hidden';
  popup.style.display = 'block';
  const W  = popup.offsetWidth  || 340;
  const H  = popup.offsetHeight || 160;
  const VW = window.innerWidth;
  const VH = window.innerHeight;
  let x = anchorX + 14;
  let y = anchorY + 14;
  if (x + W > VW - 8) x = anchorX - W - 8;
  if (y + H > VH - 8) y = anchorY - H - 8;
  popup.style.left = `${Math.max(8, x)}px`;
  popup.style.top  = `${Math.max(8, y)}px`;
  popup.style.visibility = 'visible';

  setTimeout(() => popup.querySelector('#regen-sel-instruction')?.focus(), 30);
}

function initSelectionRegenPopup() {
  // Textarea inputs (title + content)
  const titleInput   = document.getElementById('title');
  const contentInput = document.getElementById('content');
  const textareaEls  = [titleInput, contentInput].filter(Boolean);

  // Build popup upfront
  const popup = _buildRegenPopup();

  // ── Preview div: use window.getSelection() via selectionchange ────────────
  document.addEventListener('selectionchange', () => {
    // Never interrupt an active drag
    if (_mouseIsDown) return;

    clearTimeout(_regenSelChangeTimer);
    _regenSelChangeTimer = setTimeout(() => {
      const active = document.activeElement;

      // If focus is inside the popup itself, do nothing
      if (popup.contains(active)) return;

      // ── Textarea mode (keyboard selection only — mouse is handled by mouseup) ─
      if (textareaEls.includes(active)) {
        const start = active.selectionStart;
        const end   = active.selectionEnd;
        if (start === end) { _hideRegenPopup(); return; }
        const selectedText = active.value.substring(start, end);
        if (!selectedText.trim()) { _hideRegenPopup(); return; }

        const rect = active.getBoundingClientRect();
        _positionAndShowPopup(
          selectedText,
          { mode: 'textarea', el: active, start, end, text: selectedText },
          rect.left + rect.width / 2,
          rect.top - 8
        );
        return;
      }

      // ── Preview mode (keyboard selection only) ────────────────────────────
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
        if (_regenSel?.mode === 'preview') _hideRegenPopup();
        return;
      }

      const previewDiv = document.getElementById('publish-preview');
      if (!previewDiv) return;

      const range = sel.getRangeAt(0);
      if (!previewDiv.contains(range.commonAncestorContainer)) {
        if (_regenSel?.mode === 'preview') _hideRegenPopup();
        return;
      }

      const selectedText = sel.toString().trim();
      if (!selectedText) return;
      const selectedHtml = _rangeToHtml(range);

      const titleBody   = document.getElementById('preview-title-body');
      const contentBody = document.getElementById('preview-content-body');
      let containerId = null;
      if (titleBody   && titleBody.contains(range.commonAncestorContainer))   containerId = 'preview-title-body';
      if (contentBody && contentBody.contains(range.commonAncestorContainer)) containerId = 'preview-content-body';

      const frozenRange = range.cloneRange();
      const rects    = range.getClientRects();
      const lastRect = rects[rects.length - 1] || range.getBoundingClientRect();

      _positionAndShowPopup(
        selectedText,
        { mode: 'preview', range: frozenRange, text: selectedText, html: selectedHtml, containerId },
        lastRect.right,
        lastRect.bottom
      );
    }, 80);
  });

  // ── mouseup on textareas: best position via actual mouse coordinates ──────
  textareaEls.forEach(el => {
    el.addEventListener('mouseup', (e) => {
      // Give browser a tick to finalise selectionStart/End
      setTimeout(() => {
        const start = el.selectionStart;
        const end   = el.selectionEnd;
        if (start === end) { _hideRegenPopup(); return; }
        const selectedText = el.value.substring(start, end);
        if (!selectedText.trim()) { _hideRegenPopup(); return; }
        _positionAndShowPopup(
          selectedText,
          { mode: 'textarea', el, start, end, text: selectedText },
          e.clientX, e.clientY
        );
      }, 0);
    });
  });

  // ── mouseup on preview div: show popup at release point ──────────────────
  document.addEventListener('mouseup', (e) => {
    const previewDiv = document.getElementById('publish-preview');
    if (!previewDiv || !previewDiv.contains(e.target)) return;
    if (popup.contains(e.target)) return;

    setTimeout(() => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) return;

      const range = sel.getRangeAt(0);
      if (!previewDiv.contains(range.commonAncestorContainer)) return;

      const selectedText = sel.toString().trim();
      if (!selectedText) return;
      const selectedHtml = _rangeToHtml(range);

      const titleBody   = document.getElementById('preview-title-body');
      const contentBody = document.getElementById('preview-content-body');
      let containerId = null;
      if (titleBody   && titleBody.contains(range.commonAncestorContainer))   containerId = 'preview-title-body';
      if (contentBody && contentBody.contains(range.commonAncestorContainer)) containerId = 'preview-content-body';

      const frozenRange = range.cloneRange();
      _positionAndShowPopup(
        selectedText,
        { mode: 'preview', range: frozenRange, text: selectedText, html: selectedHtml, containerId },
        e.clientX, e.clientY
      );
    }, 0);
  });

  // ── Hide on outside click ─────────────────────────────────────────────────
  document.addEventListener('mousedown', (e) => {
    if (popup.style.display === 'none') return;
    if (popup.contains(e.target)) return;
    if (textareaEls.includes(e.target)) return;
    const previewDiv = document.getElementById('publish-preview');
    if (previewDiv && previewDiv.contains(e.target)) return;
    _hideRegenPopup();
  });

  // ── Close button ──────────────────────────────────────────────────────────
  popup.addEventListener('click', (e) => {
    if (e.target.id === 'regen-sel-close') _hideRegenPopup();
  });

  // ── Submit ────────────────────────────────────────────────────────────────
  popup.addEventListener('click', (e) => {
    if (e.target.id === 'regen-sel-btn') submitInlineRegen();
  });
  popup.addEventListener('keydown', (e) => {
    if (e.target.id === 'regen-sel-instruction' && e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitInlineRegen();
    }
  });
}

async function submitInlineRegen() {
  if (!_regenSel) return;
  const popup = _regenPopupEl;
  if (!popup) return;

  const instruction = (popup.querySelector('#regen-sel-instruction')?.value || '').trim();
  if (!instruction) { showAlert('Voer een aanpasinstructie in.', 'error'); return; }

  const language  = window._currentDraftWithImages?.language || 'nl';
  const statusEl  = popup.querySelector('#regen-sel-status');
  const regenBtn  = popup.querySelector('#regen-sel-btn');
  if (statusEl) statusEl.textContent = 'Bezig…';
  if (regenBtn) regenBtn.disabled = true;

  try {
    const sel = _regenSel;

    // Build context snippets
    let selectedText = sel.mode === 'preview' ? (sel.html || sel.text) : sel.text;
    let contextBefore = '';
    let contextAfter  = '';

    if (sel.mode === 'textarea') {
      const full = sel.el.value;
      contextBefore = full.substring(Math.max(0, sel.start - 300), sel.start);
      contextAfter  = full.substring(sel.end, Math.min(full.length, sel.end + 300));
    } else {
      // preview mode: use surrounding HTML context to preserve markup patterns
      const container = sel.containerId
        ? document.getElementById(sel.containerId)
        : document.getElementById('publish-preview');
      if (container) {
        const full = container.innerHTML || '';
        const lookup = sel.html || selectedText;
        const idx  = full.indexOf(lookup);
        if (idx !== -1) {
          contextBefore = full.substring(Math.max(0, idx - 300), idx);
          contextAfter  = full.substring(idx + lookup.length, idx + lookup.length + 300);
        }
      }
    }

    const result = await api.regenerateInline(
      selectedText, instruction, contextBefore, contextAfter, language
    );
    const replacement = result.replacementText || '';

    if (sel.mode === 'textarea') {
      // Replace in textarea
      const full = sel.el.value;
      sel.el.value = full.substring(0, sel.start) + replacement + full.substring(sel.end);
      if (window._currentDraftWithImages) {
        if (sel.el.id === 'title')   window._currentDraftWithImages.title       = sel.el.value;
        if (sel.el.id === 'content') window._currentDraftWithImages.contentHtml = sel.el.value;
      }
    } else {
      // Replace in preview DOM via the frozen Range
      const range = sel.range;
      range.deleteContents();

      // Insert replacement as HTML fragment
      const tpl = document.createElement('template');
      tpl.innerHTML = replacement;
      const frag = tpl.content.cloneNode(true);
      range.insertNode(frag);

      // Sync back to the content textarea and in-memory draft
      const contentBody = document.getElementById('preview-content-body');
      const titleBody   = document.getElementById('preview-title-body');
      const contentInput = document.getElementById('content');
      const titleInput   = document.getElementById('title');

      if (sel.containerId === 'preview-content-body' && contentBody && contentInput) {
        contentInput.value = contentBody.innerHTML;
        if (window._currentDraftWithImages) window._currentDraftWithImages.contentHtml = contentInput.value;
      } else if (sel.containerId === 'preview-title-body' && titleBody && titleInput) {
        titleInput.value = titleBody.textContent || titleBody.innerText || '';
        if (window._currentDraftWithImages) window._currentDraftWithImages.title = titleInput.value;
      }
    }

    _hideRegenPopup();
    if (sel.mode === 'textarea') updatePublishPreviewFromForm();
    queueDraftAutosave();
    showAlert('Selectie succesvol herschreven.', 'success');

  } catch (error) {
    console.error('Inline regen error:', error);
    if (statusEl) statusEl.textContent = '';
    showAlert(error.message || 'Fout bij hergenereren', 'error');
  } finally {
    if (regenBtn) regenBtn.disabled = false;
  }
}

// Jobs View
function initJobsView() {
  const jobsContainer = document.getElementById('jobs-list');
  if (!jobsContainer) {
    return;
  }

  const refreshBtn = document.getElementById('refresh-jobs-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', loadJobs);
  }
  
  // Auto-refresh every 5 seconds
  setInterval(loadJobs, 5000);
  loadJobs();
}

async function loadJobs() {
  const jobsContainer = document.getElementById('jobs-list');
  if (!jobsContainer) return;

  try {
    const response = await api.getJobs(50);
    const jobs = response.jobs || [];

    if (jobs.length === 0) {
      jobsContainer.innerHTML = '<p class="text-secondary">Nog geen jobs gevonden.</p>';
      return;
    }

    jobsContainer.innerHTML = jobs.map((job) => {
      const draftId = job.payload?.draftId;
      const siteId = job.payload?.siteId || '-';
      const createdAt = job.createdAt ? formatDate(job.createdAt) : '-';
      const statusBadge = formatJobStatus(job.status);

      return `
        <div class="card" style="margin-bottom: 0.75rem;">
          <div class="card-body">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:0.75rem; flex-wrap:wrap;">
              <div>
                <div><strong>Job:</strong> ${job.jobId}</div>
                <div><strong>Type:</strong> ${job.type}</div>
                <div><strong>Site:</strong> ${siteId}</div>
                <div><strong>Draft:</strong> ${draftId || '-'}</div>
                <div><strong>Aangemaakt:</strong> ${createdAt}</div>
              </div>
              <div>${statusBadge}</div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  } catch (error) {
    console.error('Error loading jobs:', error);
    jobsContainer.innerHTML = '<p class="text-secondary" style="color: var(--color-error);">Fout bij laden van jobs.</p>';
  }
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
  setPublishSchedulingFields(draft);
  if (result.draftId) setActiveDraftId(result.draftId);
  
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
  window.location.assign('/publish');
}

// Restore publish preview from sessionStorage
function restorePublishPreview() {
  const draftData = sessionStorage.getItem('currentDraft');
  const previewDiv = document.getElementById('publish-preview');
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  
  console.log('Restoring preview - using window._currentDraftWithImages');
  
  if (!previewDiv) return;

  if (!activeDraftId) {
    clearPublishPreview();
    return;
  }
  
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
      clearPublishPreview();
      return;
    }

    if (titleInput && contentInput) {
      draft = {
        ...draft,
        title: titleInput.value || draft.title || 'Geen titel',
        contentHtml: contentInput.value || draft.contentHtml || 'Geen content'
      };
    }
    
    renderPreview(draft, previewDiv);
    lastSavedDraftSignature = getDraftSignature(draft);
  } catch (error) {
    console.error('Error restoring publish preview:', error);
    clearPublishPreview();
  }
}

// Update preview from form inputs (real-time sync)
function updatePublishPreviewFromForm() {
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  const previewDiv = document.getElementById('publish-preview');
  const draftData = sessionStorage.getItem('currentDraft');
  
  if (!previewDiv || !titleInput || !contentInput) return;

  if (!activeDraftId) {
    clearPublishPreview();
    return;
  }
  
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

  const imageSourceDraft = window._currentDraftWithImages || draft;
  const previewDraft = {
    ...draft,
    title: draft.title || 'Geen titel',
    contentHtml: draft.contentHtml || 'Geen content'
  };
  
  let previewHtml = '';
  
  // Featured image(s) - handle single or multiple variations
  const images = imageSourceDraft.images || (imageSourceDraft.image ? [imageSourceDraft.image] : []);
  const imageToDisplay = imageSourceDraft.image || imageSourceDraft._image;
  
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
  previewHtml += `<h2 id="preview-title-body" style="user-select:text;cursor:text;">${previewDraft.title}</h2>`;
  if (previewDraft.excerpt) {
    previewHtml += `<p style="color: var(--text-secondary); font-style: italic;">${previewDraft.excerpt}</p>`;
  }
  previewHtml += '<hr style="margin: var(--spacing-lg) 0;">';
  previewHtml += `<div id="preview-content-body" style="line-height: 1.6; user-select:text; cursor:text;">${previewDraft.contentHtml}</div>`;
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

    const regeneratedImage = {
      ...(data.image || {}),
      feedbackChain: data.feedbackChain || [],
      generationNumber: data.generationNumber || ((draft.image?.generationNumber || 1) + 1)
    };
    
    // Update draft with new image
    draft.image = regeneratedImage;
    
    // If multiple variations, replace the selected one
    if (draft.images) {
      const selectedIndex = draft.images.findIndex(img => img.imageId === parentId);
      if (selectedIndex >= 0) {
        draft.images[selectedIndex] = regeneratedImage;
      } else {
        // Add as new variation
        draft.images.push(regeneratedImage);
      }
    }
    
    persistDraftState(draft);

    // Persist updated imageId to the database so it survives a page refresh.
    // saveCurrentDraft overwrites window._currentDraftWithImages with the DB
    // response (which has no bytes_base64), so we restore the full in-memory
    // draft afterwards so renderPreview can still display the image.
    if (activeDraftId) {
      await saveCurrentDraft({ silent: true });
      persistDraftState(draft);
    }
    
    // Clear feedback textarea
    feedbackTextarea.value = '';
    
    // Show success and refresh the publish preview in-place.
    statusDiv.innerHTML = '<div style="padding: 12px; background: #ecfdf5; border-left: 4px solid #10b981; color: #047857; border-radius: 4px;">✓ Afbeelding succesvol geregenereerd!</div>';

    const previewDiv = document.getElementById('publish-preview');
    if (previewDiv) {
      renderPreview(draft, previewDiv);
    }

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
              <h4 style="margin: 0 0 0.5rem 0; font-size: 1.1rem; color: var(--text-primary); display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">
                <span>${escapeHtml(title)}</span>
                ${item.publish_job_id ? '<span class="badge badge-success">Naar WP verstuurd</span>' : ''}
              </h4>
              ${truncatedExcerpt ? `<p style="margin: 0 0 0.5rem 0; color: var(--text-secondary); font-size: 0.9rem;">${escapeHtml(truncatedExcerpt)}</p>` : ''}
              <p style="margin: 0; color: var(--text-muted); font-size: 0.85rem;">
                Aangemaakt: ${formatDate(createdAt)}
              </p>
              ${item.publish_site_url ? `<p style="margin: 0.25rem 0 0 0; color: var(--text-muted); font-size: 0.85rem;">Website: ${escapeHtml(item.publish_site_url)}</p>` : (item.publish_site_id ? `<p style="margin: 0.25rem 0 0 0; color: var(--text-muted); font-size: 0.85rem;">Website ID: ${escapeHtml(String(item.publish_site_id))}</p>` : '')}
              ${item.publish_sent_at ? `<p style="margin: 0.25rem 0 0 0; color: var(--text-muted); font-size: 0.85rem;">Verstuurd: ${formatDate(item.publish_sent_at)}</p>` : ''}
              ${item.publish_job_id ? `<p style="margin: 0.25rem 0 0 0; color: var(--text-muted); font-size: 0.85rem;">Job: ${item.publish_job_id}</p>` : ''}
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
                class="btn btn-sm" 
                onclick="deleteDraftById(${item.id})"
                style="white-space: nowrap; background: var(--color-error); border-color: var(--color-error); color: white;"
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
    setActiveDraftId(draftId);
    persistDraftState(draft);
    lastSavedDraftSignature = getDraftSignature(draft);

    // Fill form fields
    const titleInput = document.getElementById('title');
    const contentInput = document.getElementById('content');
    
    if (titleInput && draft.title) {
      titleInput.value = draft.title;
    }
    if (contentInput && draft.contentHtml) {
      contentInput.value = draft.contentHtml;
    }
    setPublishSchedulingFields(draft);

    // Restore preview
    restorePublishPreview();

    showAlert('Concept geladen!', 'success');
  } catch (error) {
    console.error('Error loading draft:', error);
    showAlert('Fout bij laden van concept: ' + error.message, 'error');
  }
}

function clearPublishFormInputs() {
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');

  if (titleInput) {
    titleInput.value = '';
  }
  if (contentInput) {
    contentInput.value = '';
  }
}

// Delete a draft
async function deleteDraftById(draftId, options = {}) {
  const { skipConfirm = false } = options;

  if (!skipConfirm && !confirm('Weet je zeker dat je dit concept wilt verwijderen?')) {
    return;
  }

  try {
    await api.deleteDraft(draftId);

    if (activeDraftId === Number(draftId)) {
      setActiveDraftId(null);
      clearPublishFormInputs();
    }

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
