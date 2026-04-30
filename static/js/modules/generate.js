/**
 * Generate Post module – blog post generation form handling.
 */

import { api } from '../api.js';
import { showAlert, setButtonLoading } from '../ui.js';
import {
  activeDraftId, userLinks,
  setActiveDraftId, persistDraftState,
  getDraftSignature, setLastSavedDraftSignature
} from './state.js';
import { fillPublishForm, switchToPublishTab } from './preview.js';

export function initGeneratePost() {
  const form = document.getElementById('generate-post-form');
  if (!form) return;
  
  const generateImageCheckbox = document.getElementById('generateImage');
  const imageSettingsPanel = document.getElementById('image-settings-panel');
  
  if (generateImageCheckbox && imageSettingsPanel) {
    imageSettingsPanel.style.display = generateImageCheckbox.checked ? 'block' : 'none';
    generateImageCheckbox.addEventListener('change', () => {
      imageSettingsPanel.style.display = generateImageCheckbox.checked ? 'block' : 'none';
    });
  }
  
  const contextUrlInput = document.getElementById('contextWebsiteUrl');
  const contextStatusDiv = document.getElementById('context-status');
  const crawlBtn = document.getElementById('crawl-context-btn');
  const existingSitesSection = document.getElementById('existing-sites-section');
  const existingSitesDivider = document.getElementById('existing-sites-divider');
  const existingSiteSelect = document.getElementById('existingSiteSelect');
  
  let contextSiteId = null;
  
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
        
        existingSiteSelect.innerHTML = '<option value="">-- Kies een website --</option>';
        
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
  
  if (existingSiteSelect) {
    loadContextSites();
  }
  
  const confirmSiteBtn = document.getElementById('confirm-site-btn');
  const deleteContextSiteBtn = document.getElementById('delete-context-site-btn');
  
  if (existingSiteSelect) {
    existingSiteSelect.addEventListener('change', () => {
      const selectedSiteId = existingSiteSelect.value;
      if (selectedSiteId) {
        if (confirmSiteBtn) {
          confirmSiteBtn.classList.remove('hidden');
          confirmSiteBtn.disabled = false;
          confirmSiteBtn.textContent = 'Gebruik deze website';
        }
        if (deleteContextSiteBtn) {
          deleteContextSiteBtn.classList.remove('hidden');
        }
        contextUrlInput.value = '';
        crawlBtn.style.display = 'none';
        contextStatusDiv.style.display = 'none';
        contextSiteId = null;
      } else {
        if (confirmSiteBtn) {
          confirmSiteBtn.classList.add('hidden');
        }
        if (deleteContextSiteBtn) {
          deleteContextSiteBtn.classList.add('hidden');
        }
        contextStatusDiv.style.display = 'none';
        contextSiteId = null;
      }
    });
  }

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
      confirmSiteBtn.classList.remove('hidden');
      confirmSiteBtn.disabled = false;
      confirmSiteBtn.textContent = 'Gebruik deze website';
      if (deleteContextSiteBtn) deleteContextSiteBtn.classList.remove('hidden');
      crawlBtn.style.display = 'none';
    }
  }
  
  if (confirmSiteBtn) {
    confirmSiteBtn.addEventListener('click', async () => {
      const selectedSiteId = existingSiteSelect.value;
      if (!selectedSiteId) return;
      
      confirmSiteBtn.disabled = true;
      confirmSiteBtn.textContent = 'Laden...';
      
      contextSiteId = selectedSiteId;
      
      contextStatusDiv.style.display = 'block';
      contextStatusDiv.querySelector('.alert').textContent = 'Website gegevens laden...';
      contextStatusDiv.querySelector('.alert').className = 'alert alert-info';
      
      try {
        const detailsResponse = await fetch(`/api/context-sites/${selectedSiteId}/details`);
        if (detailsResponse.ok) {
          const details = await detailsResponse.json();
          
          contextStatusDiv.querySelector('.alert').textContent = 
            `${details.baseUrl} geselecteerd. ${details.pagesCount} pagina's, ${details.chunksCount} chunks. ${details.hasDna ? 'Site DNA beschikbaar.' : 'Geen Site DNA.'}`;
          contextStatusDiv.querySelector('.alert').className = 'alert alert-success';
        } else {
          contextStatusDiv.querySelector('.alert').textContent = 'Website geselecteerd.';
          contextStatusDiv.querySelector('.alert').className = 'alert alert-success';
        }
        
        await autoFillFromSiteDNA(selectedSiteId);
        
        confirmSiteBtn.textContent = 'Geladen';
        confirmSiteBtn.disabled = true;
      } catch (error) {
        console.error('Error loading site details:', error);
        contextStatusDiv.querySelector('.alert').textContent = 'Fout bij laden site gegevens';
        contextStatusDiv.querySelector('.alert').className = 'alert alert-error';
        
        confirmSiteBtn.textContent = 'Gebruik deze website';
        confirmSiteBtn.disabled = false;
      }
    });
  }
  
  if (deleteContextSiteBtn) {
    deleteContextSiteBtn.addEventListener('click', async () => {
      const selectedSiteId = existingSiteSelect.value;
      if (!selectedSiteId) return;

      const selectedOption = existingSiteSelect.options[existingSiteSelect.selectedIndex];
      if (!confirm(`Weet je zeker dat je "${selectedOption.textContent}" wilt verwijderen? Alle gecrawlde pagina's en Site DNA worden ook verwijderd.`)) return;

      deleteContextSiteBtn.disabled = true;
      try {
        const response = await fetch(`/api/context-sites/${selectedSiteId}`, { method: 'DELETE' });
        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.error || 'Verwijderen mislukt');
        }

        if (contextSiteId === selectedSiteId) {
          contextSiteId = null;
          sessionStorage.removeItem('contextSiteId');
          contextStatusDiv.style.display = 'none';
        }

        showAlert('Website en bijbehorende data verwijderd.', 'success');
        confirmSiteBtn.classList.add('hidden');
        deleteContextSiteBtn.classList.add('hidden');
        await loadContextSites();
      } catch (error) {
        showAlert(error.message || 'Fout bij verwijderen', 'error');
      } finally {
        deleteContextSiteBtn.disabled = false;
      }
    });
  }
  
  const topicInput = document.getElementById('topic');
  const focusKeywordInput = document.getElementById('focusKeyword');
  
  if (topicInput && focusKeywordInput) {
    topicInput.addEventListener('input', () => {
      const topic = topicInput.value.trim();
      if (topic) {
        focusKeywordInput.value = topic.toLowerCase();
      } else {
        focusKeywordInput.value = '';
      }
    });
  }
  
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
      
      if (dna.brand_name && document.getElementById('brandName')) {
        document.getElementById('brandName').value = dna.brand_name;
        fieldsFilledCount++;
      }
      
      if (dna.target_audiences && dna.target_audiences.length > 0 && document.getElementById('audienceMarket')) {
        document.getElementById('audienceMarket').value = dna.target_audiences[0];
        fieldsFilledCount++;
      }
      
      if (dna.pain_points && dna.pain_points.length > 0 && document.getElementById('painPoints')) {
        document.getElementById('painPoints').value = dna.pain_points.join(', ');
        fieldsFilledCount++;
      }
      
      if (dna.tone_keywords && dna.tone_keywords.length > 0 && document.getElementById('toneStyle')) {
        document.getElementById('toneStyle').value = dna.tone_keywords.slice(0, 5).join(', ');
        fieldsFilledCount++;
      }
      
      if (fieldsFilledCount > 0) {
        showAlert(`${fieldsFilledCount} velden automatisch ingevuld met Site DNA`, 'success', 3000);
      }
    } catch (error) {
      console.error('Error loading Site DNA:', error);
      showAlert('Fout bij laden Site DNA', 'error', 3000);
    }
  }
  
  if (contextUrlInput) {
    contextUrlInput.addEventListener('input', () => {
      const url = contextUrlInput.value.trim();
      if (url) {
        crawlBtn.style.display = 'block';
        if (existingSiteSelect) {
          existingSiteSelect.value = '';
        }
        if (confirmSiteBtn) {
          confirmSiteBtn.classList.add('hidden');
          confirmSiteBtn.disabled = false;
          confirmSiteBtn.textContent = 'Gebruik deze website';
        }
        if (deleteContextSiteBtn) {
          deleteContextSiteBtn.classList.add('hidden');
        }
      } else {
        crawlBtn.style.display = 'none';
        contextStatusDiv.style.display = 'none';
        contextSiteId = null;
      }
    });
  }

  syncContextUiState();
  
  if (crawlBtn) {
    crawlBtn.addEventListener('click', async () => {
      const url = contextUrlInput.value.trim();
      if (!url) return;
      
      setButtonLoading(crawlBtn, true);
      contextStatusDiv.style.display = 'block';
      contextStatusDiv.querySelector('.alert').textContent = 'Website wordt gecrawld (dit kan 30-60 seconden duren).';
      contextStatusDiv.querySelector('.alert').className = 'alert alert-info';
      
      try {
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
        
        if (data.pages_stored === 0) {
          if (data.is_js_site) {
            contextStatusDiv.querySelector('.alert').innerHTML = 
              `<strong>JavaScript-website gedetecteerd.</strong><br>
              Deze site laadt content via JavaScript (React/Vue/SPA).<br>
              <em>Tip: gebruik een statische site of WordPress/traditionele CMS.</em>`;
          } else {
            contextStatusDiv.querySelector('.alert').textContent = 
              `Geen pagina's gecrawld. De website is mogelijk niet bereikbaar.`;
          }
          contextStatusDiv.querySelector('.alert').className = 'alert alert-warning';
          crawlBtn.textContent = 'Geen content gevonden';
          crawlBtn.disabled = false;
        } else {
          contextStatusDiv.querySelector('.alert').textContent = 
            `Website gecrawld: ${data.pages_stored} pagina's, ${data.chunks_stored} chunks. ${data.site_dna_generated ? 'Site DNA gegenereerd.' : 'Site DNA kon niet worden gegenereerd.'}`;
          contextStatusDiv.querySelector('.alert').className = 'alert alert-success';
          
          crawlBtn.textContent = 'Context geladen';
          crawlBtn.disabled = true;
          
          sessionStorage.setItem('contextSiteId', contextSiteId);
          
          await loadContextSites();

          if (existingSiteSelect && contextSiteId) {
            existingSiteSelect.value = contextSiteId;
            if (confirmSiteBtn) {
              confirmSiteBtn.classList.add('hidden');
            }
            if (deleteContextSiteBtn) {
              deleteContextSiteBtn.classList.remove('hidden');
            }
          }
          
          if (data.site_dna_generated) {
            await autoFillFromSiteDNA(contextSiteId);
          }
        }
        
      } catch (error) {
        console.error('Crawl error:', error);
        contextStatusDiv.querySelector('.alert').textContent = 
          `Fout bij crawlen: ${error.message}. Controleer of de Flask app draait en de URL correct is.`;
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
    
    let siteId = contextSiteId || sessionStorage.getItem('currentSiteId') || null;
    
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
        internalLinkTargets: userLinks.map(l => ({ title: l.label, url: l.url, description: l.description || '' })),
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
      generateImage: formData.get('generateImage') === 'on',
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
    
    let loadingCleared = false;
    const clearGenerateLoading = () => {
      if (loadingCleared) return;
      loadingCleared = true;
      setButtonLoading(submitBtn, false);
    };

    setButtonLoading(submitBtn, true);
    
    try {
      const result = await api.generatePost(payload);

      clearGenerateLoading();

      await new Promise((resolve) => requestAnimationFrame(resolve));
      
      const draft = result.draft || (result.drafts && result.drafts[Object.keys(result.drafts)[0]]);
      
      if (!draft) {
        throw new Error('Geen draft ontvangen van API');
      }
      
      const draftWithoutImages = {
        ...draft,
        images: undefined
      };
      
      try {
        sessionStorage.setItem('currentDraft', JSON.stringify(draftWithoutImages));
        sessionStorage.setItem('currentSiteId', siteId);
      } catch (e) {
        console.warn('Could not store draft in sessionStorage (too large):', e);
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
      setLastSavedDraftSignature(getDraftSignature(draft));
      
      persistDraftState(draft);
      
      showAlert('Blog post gegenereerd!' + (contextSiteId ? ' (met website context)' : ''), 'success');
      
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
