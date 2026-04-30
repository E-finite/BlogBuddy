/**
 * Publish Post module – publish form handling and submission.
 */

import { api, pollJob } from '../api.js';
import { showAlert, setButtonLoading, escapeHtml } from '../ui.js';
import {
  activeDraftId,
  syncPublishStatusControls, buildDraftFromPublishForm,
  persistDraftState, saveCurrentDraft, queueDraftAutosave,
  toWpGmtDate
} from './state.js';
import { restorePublishPreview, updatePublishPreviewFromForm, showPublishSuccess } from './preview.js';
import { loadDrafts, loadDraft } from './drafts.js';
import { loadJobs, updateJobStatus } from './jobs.js';
import { initSelectionRegenPopup } from './regen.js';
import { openTranslateModal } from './translate.js';

export function initPublishPost() {
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
  
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');
  
  if (titleInput && contentInput) {
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

      const warningMessage = 'Waarschuwing: dit verwijdert het geladen concept permanent.\n\nDeze actie kan niet ongedaan worden gemaakt.\n\nWeet je zeker dat je wilt doorgaan?';
      const confirmed = confirm(warningMessage);
      if (!confirmed) {
        return;
      }

      const { deleteDraftById } = await import('./drafts.js');
      await deleteDraftById(activeDraftId, { skipConfirm: true });
    });
  }
  
  publishForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = publishForm.querySelector('button[type="submit"]');
    const formData = new FormData(publishForm);
    const pubSiteId = formData.get('pubSiteId');
    
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
    
    const payload = {
      siteId: pubSiteId,
      draft: draft
    };

    if (activeDraftId) {
      payload.draftId = activeDraftId;
    }
    
    setButtonLoading(submitBtn, true);
    
    try {
      const result = await api.publishPost(payload);
      
      showAlert(`Publish job gestart! Job ID: ${result.jobId}`, 'success');
      loadDrafts();
      loadJobs();
      
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
              showPublishSuccess(job.result.wpPostIds, job.result.warnings);
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

  initSelectionRegenPopup();

  const translateBtn = document.getElementById('translate-draft-btn');
  if (translateBtn) {
    translateBtn.addEventListener('click', () => {
      openTranslateModal();
    });
  }
}
