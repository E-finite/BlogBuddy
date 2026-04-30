/**
 * Drafts module – draft CRUD operations and loading.
 */

import { api } from '../api.js';
import { showAlert, escapeHtml } from '../ui.js';
import {
  activeDraftId,
  setActiveDraftId, persistDraftState,
  getDraftSignature, setLastSavedDraftSignature,
  setPublishSchedulingFields, clearPublishFormInputs
} from './state.js';
import { restorePublishPreview } from './preview.js';
import { updateTranslationBadges } from './translate.js';

export async function loadDrafts() {
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

    let html = '<div style="display: flex; flex-direction: column; gap: 1rem;">';
    
    for (const item of drafts) {
      const draft = item.draft;
      const title = draft.title || 'Geen titel';

      html += `
        <div class="draft-item" style="display:flex; align-items:center; gap:0.75rem; padding:0.6rem 0.85rem; border:1px solid var(--border-color); border-radius:var(--radius-md); background:var(--bg-secondary); cursor:pointer;" data-draft-id="${item.id}">
          <span style="flex:1; font-weight:600; font-size:0.95rem; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(title)}</span>
          ${item.publish_job_id ? '<span class="badge badge-success" style="flex-shrink:0;">Naar WP verstuurd</span>' : ''}
          <button class="btn btn-sm draft-delete-btn" data-delete-draft-id="${item.id}" style="flex-shrink:0; padding:0.3rem 0.5rem; min-height:0; background:transparent; border-color:var(--border-color); color:var(--text-secondary);" title="Verwijderen">
            <span class="material-icons-outlined" style="font-size:1.1rem;">delete</span>
          </button>
        </div>
      `;
    }
    
    html += '</div>';
    draftsListDiv.innerHTML = html;

    // Event delegation
    draftsListDiv.addEventListener('click', (e) => {
      const deleteBtn = e.target.closest('.draft-delete-btn');
      if (deleteBtn) {
        e.stopPropagation();
        deleteDraftById(parseInt(deleteBtn.dataset.deleteDraftId));
        return;
      }
      const draftItem = e.target.closest('[data-draft-id]');
      if (draftItem) {
        loadDraft(parseInt(draftItem.dataset.draftId));
      }
    });

  } catch (error) {
    console.error('Error loading drafts:', error);
    draftsListDiv.innerHTML = '<p class="text-muted" style="color: var(--error);">Fout bij laden van concepten.</p>';
  }
}

export async function loadDraft(draftId) {
  try {
    const draftData = await api.getDraft(draftId);
    const draft = draftData.draft;

    if (draft.image && draft.image.imageId && !draft.image.bytes_base64) {
      try {
        const fullImage = await api.getImage(draft.image.imageId);
        draft.image = fullImage;
      } catch (e) {
        console.warn('Could not load full image data:', e);
      }
    }

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

    setActiveDraftId(draftId);
    persistDraftState(draft);
    setLastSavedDraftSignature(getDraftSignature(draft));

    const titleInput = document.getElementById('title');
    const contentInput = document.getElementById('content');
    
    if (titleInput && draft.title) {
      titleInput.value = draft.title;
    }
    if (contentInput && draft.contentHtml) {
      contentInput.value = draft.contentHtml;
    }
    setPublishSchedulingFields(draft);

    restorePublishPreview();
    updateTranslationBadges();

    showAlert('Concept geladen!', 'success');
  } catch (error) {
    console.error('Error loading draft:', error);
    showAlert('Fout bij laden van concept: ' + error.message, 'error');
  }
}

export async function deleteDraftById(draftId, options = {}) {
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
    
    await loadDrafts();
  } catch (error) {
    console.error('Error deleting draft:', error);
    showAlert('Fout bij verwijderen van concept: ' + error.message, 'error');
  }
}

window.loadDraft = loadDraft;
window.deleteDraftById = deleteDraftById;
