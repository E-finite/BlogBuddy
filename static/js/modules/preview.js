/**
 * Preview module – render draft previews, image selection, image regeneration.
 */

import { api } from '../api.js';
import { showAlert, showModal, escapeHtml, setButtonLoading } from '../ui.js';
import {
  activeDraftId, clearPublishPreview,
  setActiveDraftId, persistDraftState,
  setPublishSchedulingFields, saveCurrentDraft
} from './state.js';

export function switchToPublishTab() {
  window.location.assign('/publish');
}

export function fillPublishForm(result, siteId) {
  const draft = result.draft || (result.drafts && result.drafts[Object.keys(result.drafts)[0]]);
  
  if (!draft) return;
  
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  const pubSiteIdSelect = document.getElementById('pubSiteId');
  const previewDiv = document.getElementById('publish-preview');
  
  if (titleInput) titleInput.value = draft.title || '';
  if (contentInput) contentInput.value = draft.contentHtml || '';
  if (pubSiteIdSelect && siteId) pubSiteIdSelect.value = siteId;
  setPublishSchedulingFields(draft);
  if (result.draftId) setActiveDraftId(result.draftId);
  
  if (previewDiv) {
    renderPreview(draft, previewDiv);
  }
  
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

export function restorePublishPreview() {
  const draftData = sessionStorage.getItem('currentDraft');
  const previewDiv = document.getElementById('publish-preview');
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  
  if (!previewDiv) return;

  if (!activeDraftId) {
    clearPublishPreview();
    return;
  }
  
  try {
    let draft;
    if (window._currentDraftWithImages) {
      draft = window._currentDraftWithImages;
    } else if (draftData) {
      draft = JSON.parse(draftData);
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
  } catch (error) {
    console.error('Error restoring publish preview:', error);
    clearPublishPreview();
  }
}

export function updatePublishPreviewFromForm() {
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  const contentPreview = document.getElementById('pub-content-preview');
  
  if (!titleInput || !contentInput) return;

  if (!activeDraftId) {
    clearPublishPreview();
    return;
  }

  if (contentPreview) {
    const titleBody = contentPreview.querySelector('#preview-title-body');
    const contentBody = contentPreview.querySelector('#preview-content-body');

    if (titleBody) {
      titleBody.textContent = titleInput.value || 'Geen titel';
    }
    if (contentBody) {
      contentBody.innerHTML = contentInput.value || 'Geen content';
    }
  }
}

export function renderPreview(draft, previewDiv) {
  const imageSourceDraft = window._currentDraftWithImages || draft;
  const previewDraft = {
    ...draft,
    title: draft.title || 'Geen titel',
    contentHtml: draft.contentHtml || 'Geen content'
  };
  
  let imageHtml = '';
  
  const images = imageSourceDraft.images || (imageSourceDraft.image ? [imageSourceDraft.image] : []);
  const imageToDisplay = imageSourceDraft.image || imageSourceDraft._image;
  
  if (images.length > 0) {
    imageHtml += `
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Featured Image ${images.length > 1 ? `(${images.length} variations)` : ''}</h3>
        </div>
        <div class="card-body">
    `;
    
    if (images.length > 1) {
      imageHtml += '<div id="image-variations-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px;">';
      images.forEach((img, index) => {
        const isSelected = index === 0;
        const borderStyle = isSelected ? '4px solid #10b981' : '2px solid #e2e8f0';
        const boxShadow = isSelected ? '0 0 0 3px rgba(16, 185, 129, 0.2)' : 'none';
        const feedbackChain = img.feedbackChain || [];
        const imageId = img.imageId;
        
        imageHtml += `
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
      imageHtml += '</div>';
      imageHtml += '<div style="margin-top: 16px; padding: 12px; background: #ecfdf5; border-left: 4px solid #10b981; border-radius: 8px; color: #047857; font-size: 14px;"><strong>Tip:</strong> Klik op een image om deze te selecteren voor publicatie</div>';
      
      imageHtml += `
        <div id="regenerate-section" style="margin-top: 24px;">
          <div class="card">
            <div class="card-header"><h4>Regenereer geselecteerde afbeelding</h4></div>
            <div class="card-body">
              <p style="color: var(--text-secondary); margin-bottom: 16px;">Geef feedback om de geselecteerde afbeelding te verbeteren.</p>
              <textarea id="regenerate-feedback" placeholder="bijv. 'maak het feller', 'voeg bergen toe op de achtergrond'..." rows="3"
                        style="width: 100%; padding: 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; font-family: inherit; resize: vertical;"></textarea>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px;">
                <span id="regenerate-counter" style="font-size: 13px; color: var(--text-secondary);">Generatie <span id="gen-current">1</span> van 3</span>
                <button id="regenerate-btn" class="btn btn-primary" style="display: inline-flex; align-items: center; gap: 8px;"><span>Regenereren</span></button>
              </div>
              <div id="regenerate-status" style="margin-top: 12px; display: none;"></div>
            </div>
          </div>
        </div>
      `;
    } else if (imageToDisplay && imageToDisplay.bytes_base64) {
      const feedbackChain = imageToDisplay.feedbackChain || [];
      const generationNumber = imageToDisplay.generationNumber || 1;
      const imageId = imageToDisplay.imageId;
      
      imageHtml += `
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
      
      imageHtml += `
        <div id="regenerate-section" style="margin-top: 24px;">
          <div style="padding: 16px; background: #f9fafb; border: 2px solid #e2e8f0; border-radius: 8px;">
            <h4 style="margin: 0 0 12px 0; font-size: 16px; color: #111827;">Afbeelding regenereren</h4>
            <p style="color: var(--text-secondary); margin-bottom: 12px; font-size: 14px;">Geef feedback om de afbeelding te verbeteren.</p>
            <textarea id="regenerate-feedback" placeholder="bijv. 'maak het feller', 'voeg bergen toe op de achtergrond'..." rows="3"
                      style="width: 100%; padding: 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; font-family: inherit; resize: vertical;"></textarea>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px;">
              <span id="regenerate-counter" style="font-size: 13px; color: var(--text-secondary);">Generatie <span id="gen-current">${generationNumber}</span> van 3 ${generationNumber >= 3 ? '(Maximum bereikt)' : ''}</span>
              <button id="regenerate-btn" class="btn btn-primary" ${generationNumber >= 3 ? 'disabled' : ''}
                      style="display: inline-flex; align-items: center; gap: 8px;">
                <span>${generationNumber >= 3 ? 'Maximum bereikt' : 'Regenereren'}</span>
              </button>
            </div>
            <div id="regenerate-status" style="margin-top: 12px; display: none;"></div>
          </div>
        </div>
      `;
    }
    
    imageHtml += `
        </div>
      </div>
    `;
  }

  if (previewDiv) {
    previewDiv.innerHTML = imageHtml;
    previewDiv.style.display = imageHtml ? 'block' : 'none';
  }

  if (previewDiv) {
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

    // Bind regenerate button
    const regenBtn = previewDiv.querySelector('#regenerate-btn');
    if (regenBtn) {
      regenBtn.addEventListener('click', () => regenerateImage());
    }
  }
  
  const contentPreview = document.getElementById('pub-content-preview');
  if (contentPreview) {
    let contentHtml = '';
    contentHtml += `<h2 id="preview-title-body" style="user-select:text;cursor:text;">${previewDraft.title}</h2>`;
    if (previewDraft.excerpt) {
      contentHtml += `<p style="color: var(--text-secondary); font-style: italic;">${previewDraft.excerpt}</p>`;
    }
    contentHtml += '<hr style="margin: var(--spacing-lg) 0;">';
    contentHtml += `<div id="preview-content-body" style="line-height: 1.6; user-select:text; cursor:text;">${previewDraft.contentHtml}</div>`;
    contentPreview.innerHTML = contentHtml;
  }
}

export function selectImageVariation(index) {
  const draft = window._currentDraftWithImages;
  if (!draft) {
    console.error('No draft with images available');
    return;
  }
  
  try {
    if (draft.images && draft.images[index]) {
      draft.image = draft.images[index];
      
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
      
      const container = document.querySelector('#image-variations-container');
      if (container) {
        const allCards = container.querySelectorAll('.image-variation-card');
        allCards.forEach((card, i) => {
          const badge = card.querySelector('.variation-selected-badge');
          if (badge) badge.remove();
          
          if (i === index) {
            card.style.border = '4px solid #10b981';
            card.style.boxShadow = '0 0 0 3px rgba(16, 185, 129, 0.2)';
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
    }
  } catch (e) {
    console.error('Error selecting variation:', e);
  }
}

window.selectImageVariation = selectImageVariation;

export function showDraftPreview(draft) {
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

export function showPublishSuccess(wpPostIds, warnings) {
  const warningsHtml = warnings && warnings.length
    ? `<div class="alert alert-warning" style="margin-top:var(--spacing-md);padding:var(--spacing-md);border-radius:var(--radius-md);background:rgba(255,152,0,0.1);border:1px solid rgba(255,152,0,0.3);color:var(--text-primary);font-size:0.9rem">
        <strong style="display:flex;align-items:center;gap:4px;margin-bottom:4px">
          <span class="material-icons-outlined" style="font-size:1.1rem;color:#ff9800">warning</span>
          Let op
        </strong>
        ${warnings.map(w => `<p style="margin:0">${escapeHtml(w)}</p>`).join('')}
      </div>`
    : '';

  const content = `
    <p>Blog post(s) succesvol gepubliceerd!</p>
    <ul>
      ${Object.entries(wpPostIds).map(([lang, id]) => `<li><strong>${lang}:</strong> Post ID ${id}</li>`).join('')}
    </ul>
    ${warningsHtml}
  `;
  
  showModal('Publicatie Succesvol', content, '<button class="btn btn-primary" onclick="this.closest(\'.modal-overlay\').remove()">Sluiten</button>');
}

export async function regenerateImage() {
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
    statusDiv.innerHTML = '<div style="padding: 12px; background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; border-radius: 4px;">Voer feedback in om de afbeelding te regenereren.</div>';
    return;
  }
  
  if (feedback.length < 5) {
    statusDiv.style.display = 'block';
    statusDiv.innerHTML = '<div style="padding: 12px; background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; border-radius: 4px;">Feedback moet minimaal 5 karakters bevatten.</div>';
    return;
  }
  
  const draft = window._currentDraftWithImages;
  if (!draft || !draft.image || !draft.image.imageId) {
    statusDiv.style.display = 'block';
    statusDiv.innerHTML = '<div style="padding: 12px; background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; border-radius: 4px;">Geen afbeelding geselecteerd voor regeneratie.</div>';
    return;
  }
  
  const parentId = draft.image.imageId;
  
  regenerateBtn.disabled = true;
  regenerateBtn.innerHTML = '<span>Regenereren...</span>';
  statusDiv.style.display = 'block';
  statusDiv.innerHTML = '<div style="padding: 12px; background: #eff6ff; border-left: 4px solid #3b82f6; color: #1e40af; border-radius: 4px;">Afbeelding wordt gegenereerd met je feedback...</div>';
  
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
    
    draft.image = regeneratedImage;
    
    if (draft.images) {
      const selectedIndex = draft.images.findIndex(img => img.imageId === parentId);
      if (selectedIndex >= 0) {
        draft.images[selectedIndex] = regeneratedImage;
      } else {
        draft.images.push(regeneratedImage);
      }
    }
    
    persistDraftState(draft);

    if (activeDraftId) {
      await saveCurrentDraft({ silent: true });
      persistDraftState(draft);
    }
    
    feedbackTextarea.value = '';
    
    statusDiv.innerHTML = '<div style="padding: 12px; background: #ecfdf5; border-left: 4px solid #10b981; color: #047857; border-radius: 4px;">✓ Afbeelding succesvol geregenereerd!</div>';

    const previewDiv = document.getElementById('publish-preview');
    if (previewDiv) {
      renderPreview(draft, previewDiv);
    }

    showAlert('Afbeelding geregenereerd met je feedback!', 'success', 3000);
    
  } catch (error) {
    console.error('Regeneration error:', error);
    statusDiv.innerHTML = `<div style="padding: 12px; background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; border-radius: 4px;">${error.message}</div>`;
    regenerateBtn.disabled = false;
    regenerateBtn.innerHTML = '<span>Regenereren</span>';
  }
}

window.regenerateImage = regenerateImage;
