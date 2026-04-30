/**
 * Shared application state and utility functions used across modules.
 */

import { api } from '../api.js';
import { showAlert, setButtonLoading, escapeHtml } from '../ui.js';

// ── Shared mutable state ────────────────────────────────────────────────
export let activeDraftId = null;
export let lastSavedDraftSignature = null;
export let userLinks = [];

let draftAutosaveTimeout = null;
let draftSaveInFlight = false;

// ── Active draft ID management ──────────────────────────────────────────

export function initializeActiveDraftId() {
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

export function setActiveDraftId(draftId) {
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

export function setLastSavedDraftSignature(sig) {
  lastSavedDraftSignature = sig;
}

export function setUserLinks(links) {
  userLinks = links;
}

// ── Publish preview clearing ────────────────────────────────────────────

export function clearPublishPreview() {
  const previewDiv = document.getElementById('publish-preview');
  if (previewDiv) {
    previewDiv.innerHTML = '';
    previewDiv.style.display = 'none';
  }

  const contentPreview = document.getElementById('pub-content-preview');
  if (contentPreview) {
    contentPreview.innerHTML = '<p class="text-muted">Laad een concept of genereer eerst een post.</p>';
  }
}

// ── Draft metadata helpers ──────────────────────────────────────────────

export function toDraftMetadata(draft) {
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

export function persistDraftState(draft) {
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

export function getDraftSignature(draft) {
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

// ── Date helpers ────────────────────────────────────────────────────────

export function toWpGmtDate(localDateTimeValue) {
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

export function fromWpGmtDateToLocalInput(gmtDateValue) {
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

// ── Scheduling helpers ──────────────────────────────────────────────────

export function setPublishSchedulingFields(draft = {}) {
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

export function syncPublishStatusControls() {
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

// ── Draft form building ─────────────────────────────────────────────────

export function buildDraftFromPublishForm(publishForm) {
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

// ── Draft save / autosave ───────────────────────────────────────────────

export async function saveCurrentDraft({ showSuccess = false, silent = false, button = null } = {}) {
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

export function queueDraftAutosave() {
  if (!activeDraftId) return;

  clearTimeout(draftAutosaveTimeout);
  draftAutosaveTimeout = setTimeout(() => {
    saveCurrentDraft({ silent: true });
  }, 1200);
}

export function clearPublishFormInputs() {
  const titleInput = document.getElementById('title');
  const contentInput = document.getElementById('content');

  if (titleInput) {
    titleInput.value = '';
  }
  if (contentInput) {
    contentInput.value = '';
  }
}
